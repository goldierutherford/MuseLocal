import io
import logging
import base64
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from backend.midi_listener import MIDIListener
from backend.model_engine import ModelEngine
from backend.articulation import ArticulationEngine

import mido

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("muselocal-backend")

app = FastAPI(title="MuseLocal AI Backend", version="1.0.0")

# Strict CORS configuration restricted to Tauri native origins and Next.js local development
origins = [
    "http://localhost:3000",       # Next.js dev server (localhost)
    "http://127.0.0.1:3000",       # Next.js dev server (IPv4 loopback)
    "http://[::1]:3000",           # Next.js dev server (IPv6 loopback)
    "tauri://localhost",           # Tauri custom protocol (macOS/Linux)
    "http://tauri.localhost",      # Tauri custom protocol (Windows)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global thread-safe states
midi_listener = MIDIListener()
model_engine = ModelEngine()
CAPTURED_BASELINE: List[Dict[str, Any]] = []

class GenerationRequest(BaseModel):
    prompt: str
    instrument_roles: List[str]  # e.g., ["bassline", "lead", "counter-melody"]
    source_midi_base64: Optional[str] = None  # Dropped MIDI file
    use_captured_canvas: bool = False
    tempo: Optional[float] = 120.0
    key_signature: Optional[str] = "C minor"

class ArticulationRequest(BaseModel):
    midi_base64: str
    humanize_ms: float = 0.0          # 0 to 100ms offset
    velocity_accent_scale: float = 1.0  # relative scale multiplier
    length_ratio: float = 1.0          # gate ratio adjustment (legato/staccato)
    add_cc_modulation: bool = False
    add_cc_expression: bool = False

def parse_midi_bytes_to_notes(midi_bytes: bytes) -> tuple[Dict[str, List[Dict[str, Any]]], float]:
    """
    Parse a binary MIDI Spec 1.0 byte stream using mido.
    Reconstructs absolute float timestamp note lists grouped by track names and extracts BPM.
    """
    try:
        mid = mido.MidiFile(file=io.BytesIO(midi_bytes))
    except Exception as e:
        logger.error(f"Failed to parse MIDI bytes: {e}")
        return {}, 120.0

    ticks_per_beat = mid.ticks_per_beat
    
    # 1. Query for tempo metadata
    tempo_bpm = 120.0
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                tempo_bpm = mido.tempo2bpm(msg.tempo)
                break

    seconds_per_tick = 60.0 / (tempo_bpm * ticks_per_beat)
    tracks_data = {}

    for idx, track in enumerate(mid.tracks):
        track_name = f"track_{idx}"
        notes = []
        active_notes = {} # note_num -> (start_time, velocity)
        
        abs_tick = 0
        for msg in track:
            abs_tick += msg.time
            abs_time = abs_tick * seconds_per_tick
            
            if msg.type == 'track_name':
                track_name = msg.name.lower()
                
            if msg.type == 'note_on' and msg.velocity > 0:
                active_notes[msg.note] = (abs_time, msg.velocity)
            elif msg.type in ['note_off'] or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in active_notes:
                    start_time, velocity = active_notes.pop(msg.note)
                    notes.append({
                        "note": msg.note,
                        "start": start_time,
                        "end": abs_time,
                        "velocity": velocity
                    })
        
        if notes:
            notes.sort(key=lambda x: x["start"])
            tracks_data[track_name] = notes

    return tracks_data, tempo_bpm

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "MuseLocal Backend is running offline."}

@app.get("/api/capture/ports")
def get_midi_ports():
    """
    List all physical and virtual hardware MIDI input ports detected on the system.
    """
    ports = midi_listener.get_available_ports()
    logger.info(f"Polled MIDI hardware ports: {ports}")
    return {"status": "success", "ports": ports}

@app.post("/api/capture/toggle")
def toggle_capture(active: bool, port_index: int = 0):
    """
    Control low-level MIDI hardware capture listener loop.
    Enables remote arming/disarming of isolated threads.
    """
    global CAPTURED_BASELINE
    logger.info(f"MIDI Hardware Capture Toggle Requested: {'ARMED' if active else 'DISARMED'} on port index {port_index}")
    
    if active:
        started = midi_listener.start_capture(port_index=port_index)
        if not started:
            raise HTTPException(status_code=500, detail="Failed to initialize low-level hardware MIDI hook.")
        return {"status": "success", "capture_active": True, "message": "MIDI Recording thread armed."}
    else:
        recorded_events = midi_listener.stop_capture()
        CAPTURED_BASELINE = recorded_events
        logger.info(f"MIDI Recording completed. {len(CAPTURED_BASELINE)} raw events serialized to volatile memory.")
        return {
            "status": "success",
            "capture_active": False,
            "recorded_events_count": len(CAPTURED_BASELINE),
            "message": "MIDI Recording stopped. Session cached in memory."
        }

@app.get("/api/capture/canvas")
def get_captured_canvas(
    quantize: bool = Query(default=False),
    grid_division: str = Query(default="1/16"),
    tempo: float = Query(default=120.0)
):
    """
    Retrieve the current volatile session recording with optional on-demand quantisation parameters.
    """
    global CAPTURED_BASELINE
    logger.info(f"Requesting Captured Canvas. Quantize: {quantize}, Grid: {grid_division}, Tempo: {tempo} BPM")
    
    events = CAPTURED_BASELINE
    if quantize:
        events = midi_listener.quantize_events(events, tempo=tempo, grid_division=grid_division)
        logger.info(f"Applied on-demand quantisation grid {grid_division} to canvas events.")
        
    return {
        "status": "success",
        "canvas_size": len(events),
        "quantized": quantize,
        "grid_division": grid_division if quantize else None,
        "tempo_bpm": tempo if quantize else None,
        "events": events
    }

@app.post("/api/generate")
def generate_accompaniment(req: GenerationRequest):
    """
    Execute AI multi-track accompaniment synthesis.
    Integrates dropped MIDI analysis, canvas parsing, and standard Spec 1.0 compilation.
    """
    global CAPTURED_BASELINE
    logger.info(f"Initiating AI accompaniment synthesis for prompt: '{req.prompt}'")
    
    source_chords = None
    target_tempo = req.tempo or 120.0
    
    # 1. Check if user dropped a physical source MIDI file
    if req.source_midi_base64:
        logger.info("Parsing dropped MIDI file canvas...")
        try:
            midi_bytes = base64.b64decode(req.source_midi_base64)
            analysis = model_engine.analyze_harmonic_canvas(midi_bytes)
            if "estimated_tempo" in analysis:
                target_tempo = analysis["estimated_tempo"]
                logger.info(f"Harmonic analysis complete. Estimated Tempo: {target_tempo} BPM.")
        except Exception as e:
            logger.error(f"Failed to parse dropped MIDI: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid MIDI base64 encoding: {e}")

    # 2. Check if user targeted active capture ingestion canvas
    elif req.use_captured_canvas:
        if not CAPTURED_BASELINE:
            raise HTTPException(
                status_code=400, 
                detail="Request specified Captured Canvas but the active ingestion memory is currently empty."
            )
        source_chords = CAPTURED_BASELINE
        logger.info(f"Locking generation thread to Captured Canvas ({len(source_chords)} events).")
    
    # 3. Trigger model track generation
    result = model_engine.generate_tracks(
        prompt=req.prompt,
        instrument_roles=req.instrument_roles,
        base_chords=source_chords
    )
    
    if result["status"] == "cancelled":
        return {"status": "cancelled", "message": "Accompaniment synthesis halted. VRAM cleared."}
        
    # 4. Compile synthesized tracks into a standard Base64 MIDI Spec 1.0 file
    try:
        compiled_midi_bytes = model_engine.compile_to_midi_bytes(result["tracks"], tempo_bpm=target_tempo)
        compiled_midi_base64 = base64.b64encode(compiled_midi_bytes).decode("utf-8")
        
        return {
            "status": "success",
            "tempo_bpm": target_tempo,
            "midi_base64": compiled_midi_base64,
            "tracks": result["tracks"]
        }
    except Exception as e:
        logger.error(f"Error compiling MIDI tracks: {e}")
        raise HTTPException(status_code=500, detail=f"MIDI speculative compiler error: {e}")

@app.post("/api/generate/cancel")
def cancel_generation():
    """
    Abruptly terminate active model inference and reclaim VRAM/RAM pools.
    """
    logger.info("Cancellation command received. Terminating generation loops...")
    model_engine.trigger_cancel()
    return {"status": "success", "message": "Inference thread interrupted. Resources cleared."}

@app.post("/api/process/articulate")
def process_articulation(req: ArticulationRequest):
    """
    Apply fast heuristic adjustments outside the ML inference pipeline.
    Unpacks base64 MIDI, processes parameters, and re-compiles Spec 1.0 output.
    """
    logger.info("Applying post-processing articulation transformations.")
    
    try:
        # 1. Decode incoming MIDI stream
        midi_bytes = base64.b64decode(req.midi_base64)
        
        # 2. Parse MIDI back into seconds-based note tracks
        tracks_data, tempo_bpm = parse_midi_bytes_to_notes(midi_bytes)
        
        if not tracks_data:
            raise HTTPException(status_code=400, detail="Parsed MIDI stream contains no active note events.")
            
        # 3. Apply transformations to each track
        articulated_tracks = {}
        for role, notes in tracks_data.items():
            processed_notes = notes
            
            # Apply Humanisation Offset
            if req.humanize_ms > 0:
                processed_notes = ArticulationEngine.apply_humanization(processed_notes, req.humanize_ms)
                
            # Apply Velocity Scaling Accents
            if req.velocity_accent_scale != 1.0:
                processed_notes = ArticulationEngine.scale_velocities(processed_notes, req.velocity_accent_scale)
                
            # Apply Length Ratio Gate Duration Adjustments
            if req.length_ratio != 1.0:
                processed_notes = ArticulationEngine.adjust_note_lengths(processed_notes, req.length_ratio)
                
            articulated_tracks[role] = processed_notes
            
        # 4. Compile tracks back into standard MIDI Spec 1.0 binary stream
        compiled_bytes = model_engine.compile_to_midi_bytes(articulated_tracks, tempo_bpm=tempo_bpm)
        compiled_base64 = base64.b64encode(compiled_bytes).decode("utf-8")
        
        return {
            "status": "success",
            "tempo_bpm": tempo_bpm,
            "midi_base64": compiled_base64
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in articulation post-processing: {e}")
        raise HTTPException(status_code=500, detail=f"Articulation post-processor calculation error: {e}")
