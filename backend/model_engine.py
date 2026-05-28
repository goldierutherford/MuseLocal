import os
import io
import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("muselocal-model-engine")

try:
    import torch
    import pretty_midi
except ImportError:
    logger.warning("torch or pretty_midi not installed yet. Placeholders will be active.")
    torch = None
    pretty_midi = None

import mido

class ModelEngine:
    def __init__(self):
        self.device = self._detect_acceleration_device()
        self.is_interrupted = False
        self.is_model_loaded = False
        logger.info(f"Model Engine initialized. Targeted backend device: {self.device}")

    def _detect_acceleration_device(self) -> str:
        if torch is not None:
            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        return "cpu"

    def load_model_weights(self, model_path: Optional[str] = None):
        if self.is_model_loaded:
            return True
        time.sleep(0.1)
        self.is_model_loaded = True
        return True

    def analyze_harmonic_canvas(self, midi_bytes: bytes) -> Dict[str, Any]:
        if pretty_midi is None:
            return {"key": "C Minor", "tempo": 120.0, "time_signature": "4/4"}
        try:
            midi_io = io.BytesIO(midi_bytes)
            pm = pretty_midi.PrettyMIDI(midi_io)
            tempo = pm.estimate_tempo()
            return {
                "estimated_tempo": float(tempo),
                "key_signature": "C Minor",
                "duration_seconds": pm.get_end_time()
            }
        except Exception as e:
            logger.error(f"Error parsing harmonic canvas: {e}")
            return {"key": "C Minor", "tempo": 120.0, "error": str(e)}

    def generate_tracks(self, prompt: str, instrument_roles: List[str], base_chords: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Synthesize multi-track MIDI note sequences based on user prompt instructions.
        Dynamically adjusts arrangement lengths, scale registers, and chord evolving speed.
        """
        self.is_interrupted = False
        self.load_model_weights()
        
        logger.info(f"Generating backing accompaniment tracks for roles: {instrument_roles}")
        
        # 1. Parse prompt keywords to determine length and mood
        prompt_lower = prompt.lower()
        is_long = "long" in prompt_lower or "evolv" in prompt_lower or "slow" in prompt_lower or "ambient" in prompt_lower
        is_minor = "minor" in prompt_lower or "sad" in prompt_lower or "dark" in prompt_lower or "psychedelic" in prompt_lower or "rock" in prompt_lower
        builds_complexity = "build" in prompt_lower or "complex" in prompt_lower or "crescendo" in prompt_lower or "evolv" in prompt_lower or "climax" in prompt_lower
        
        # Evolving layout parameters: parse custom bar counts e.g. "16 bars", "32 bars"
        import re
        bar_match = re.search(r'(\d+)\s*bar', prompt_lower)
        if bar_match:
            bar_count = int(bar_match.group(1))
            bar_count = max(4, min(32, bar_count))
        else:
            bar_count = 8 if is_long else 4
            
        seconds_per_bar = 2.0 # Assuming 120 BPM, 4 beats @ 0.5s per beat = 2.0s per bar
        
        # Formulate chord progression roots and scales
        # Minor progression: i -> bVI -> bIII -> bVII (A minor, F major, C major, G major)
        # Major progression: I -> V -> vi -> IV (C major, G major, A minor, F major)
        if is_minor:
            chord_roots = [45, 41, 48, 43]  # A2, F2, C3, G2
            chord_types = ["min", "maj", "maj", "maj"]
        else:
            chord_roots = [48, 43, 45, 41]  # C3, G2, A2, F2
            chord_types = ["maj", "maj", "min", "maj"]
            
        progression = []
        for bar in range(bar_count):
            idx = bar % len(chord_roots)
            root = chord_roots[idx]
            ctype = chord_types[idx]
            progression.append({
                "bar": bar,
                "start_time": bar * seconds_per_bar,
                "end_time": (bar + 1) * seconds_per_bar,
                "root": root,
                "type": ctype
            })

        # simulated steps
        total_steps = 3
        for step in range(total_steps):
            if self.is_interrupted:
                self.clear_vram_resources()
                return {"status": "cancelled", "message": "Inference cancelled."}
            time.sleep(0.01)

        generated_data = {}
        for role in instrument_roles:
            if role == "bassline":
                generated_data["bassline"] = self._synthesize_bassline(progression, is_long, builds_complexity)
            elif role == "lead":
                generated_data["lead"] = self._synthesize_lead_melody(progression, is_long, builds_complexity)
            elif role == "counter-melody":
                generated_data["counter-melody"] = self._synthesize_counter_melody(progression, is_long, builds_complexity)
            else:
                generated_data[role] = []

        return {"status": "completed", "tracks": generated_data}

    def trigger_cancel(self):
        self.is_interrupted = True

    def clear_vram_resources(self):
        if torch is not None:
            if self.device == "cuda":
                torch.cuda.empty_cache()

    def compile_to_midi_bytes(self, tracks_data: Dict[str, List[Dict[str, Any]]], tempo_bpm: float = 120.0) -> bytes:
        mid = mido.MidiFile(type=1)
        ticks_per_beat = mid.ticks_per_beat
        
        meta_track = mido.MidiTrack()
        mid.tracks.append(meta_track)
        meta_track.append(mido.MetaMessage('time_signature', numerator=4, denominator=4, time=0))
        meta_track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(tempo_bpm), time=0))
        meta_track.append(mido.MetaMessage('end_of_track', time=0))
        
        for role, notes in tracks_data.items():
            if not notes:
                continue
            track = mido.MidiTrack()
            mid.tracks.append(track)
            track.append(mido.MetaMessage('track_name', name=role.capitalize(), time=0))
            
            messages = []
            for note in notes:
                on_tick = int(note["start"] * (tempo_bpm / 60.0) * ticks_per_beat)
                off_tick = int(note["end"] * (tempo_bpm / 60.0) * ticks_per_beat)
                
                on_tick = max(0, on_tick)
                off_tick = max(on_tick + 1, off_tick)
                
                messages.append((on_tick, 'note_on', note["note"], note["velocity"]))
                messages.append((off_tick, 'note_off', note["note"], 0))
                
            messages.sort(key=lambda x: x[0])
            
            prev_tick = 0
            for tick, msg_type, note_num, velocity in messages:
                delta_tick = tick - prev_tick
                delta_tick = max(0, delta_tick)
                
                if msg_type == 'note_on':
                    track.append(mido.Message('note_on', note=note_num, velocity=velocity, time=delta_tick))
                elif msg_type == 'note_off':
                    track.append(mido.Message('note_off', note=note_num, velocity=velocity, time=delta_tick))
                prev_tick = tick
                
            track.append(mido.MetaMessage('end_of_track', time=0))
            
        bytes_io = io.BytesIO()
        mid.save(file=bytes_io)
        return bytes_io.getvalue()

    def _synthesize_bassline(self, progression: List[Dict[str, Any]], is_long: bool, builds_complexity: bool = False) -> List[Dict[str, Any]]:
        """
        Bassline Layer Rules: Play deep solid roots on downbeats, matching chord structures.
        If 'builds_complexity' is true, complexity and rhythm build up dynamically across phases.
        """
        bass_notes = []
        bar_count = len(progression)
        
        for item in progression:
            bar_idx = item["bar"]
            root = item["root"] - 12 # drop another octave
            start = item["start_time"]
            end = item["end_time"]
            
            if not builds_complexity:
                if is_long:
                    bass_notes.append({
                        "note": root,
                        "start": start,
                        "end": end - 0.1,
                        "velocity": 90
                    })
                else:
                    bass_notes.append({
                        "note": root,
                        "start": start,
                        "end": start + 0.8,
                        "velocity": 100
                    })
                    bass_notes.append({
                        "note": root + 7,
                        "start": start + 1.25,
                        "end": start + 1.75,
                        "velocity": 85
                    })
                continue
                
            progress = bar_idx / bar_count
            if progress < 0.25:
                # Phase 1: Sparse long root holding down the bottom
                bass_notes.append({
                    "note": root,
                    "start": start,
                    "end": end - 0.1,
                    "velocity": 75
                })
            elif progress < 0.50:
                # Phase 2: Root + sustained fifth on beat 3
                bass_notes.append({
                    "note": root,
                    "start": start,
                    "end": start + 0.8,
                    "velocity": 85
                })
                bass_notes.append({
                    "note": root + 7,
                    "start": start + 1.0,
                    "end": start + 1.8,
                    "velocity": 80
                })
            elif progress < 0.75:
                # Phase 3: Walking syncopated roots and octaves
                bass_notes.append({
                    "note": root,
                    "start": start,
                    "end": start + 0.5,
                    "velocity": 95
                })
                bass_notes.append({
                    "note": root + 7,
                    "start": start + 0.75,
                    "end": start + 1.25,
                    "velocity": 90
                })
                bass_notes.append({
                    "note": root + 12,
                    "start": start + 1.25,
                    "end": start + 1.75,
                    "velocity": 90
                })
            else:
                # Phase 4: High intensity eighth note drive (crescendo)
                notes_to_play = [root, root + 12, root + 7, root + 12]
                for offset_idx, note_val in enumerate(notes_to_play):
                    note_start = start + offset_idx * 0.5
                    bass_notes.append({
                        "note": note_val,
                        "start": note_start,
                        "end": note_start + 0.4,
                        "velocity": 105
                    })
        return bass_notes

    def _synthesize_lead_melody(self, progression: List[Dict[str, Any]], is_long: bool, builds_complexity: bool = False) -> List[Dict[str, Any]]:
        """
        Lead Line Layer: Expressive modal variations.
        If 'builds_complexity' is true, melodies grow from simple long tones into complex rising arpeggios.
        """
        lead_notes = []
        bar_count = len(progression)
        
        minor_pentatonic = [0, 3, 5, 7, 10, 12, 15, 17, 19, 22]
        major_pentatonic = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21]
        
        for item in progression:
            bar_idx = item["bar"]
            root = item["root"] + 24 # High register
            start = item["start_time"]
            ctype = item["type"]
            scale = minor_pentatonic if ctype == "min" else major_pentatonic
            
            if not builds_complexity:
                if is_long:
                    lead_notes.append({
                        "note": root + scale[2],
                        "start": start + 0.5,
                        "end": start + 1.25,
                        "velocity": 95
                    })
                    lead_notes.append({
                        "note": root + scale[3],
                        "start": start + 1.25,
                        "end": start + 1.9,
                        "velocity": 102
                    })
                else:
                    lead_notes.append({
                        "note": root + scale[0],
                        "start": start,
                        "end": start + 0.25,
                        "velocity": 105
                    })
                    lead_notes.append({
                        "note": root + scale[1],
                        "start": start + 0.5,
                        "end": start + 0.75,
                        "velocity": 98
                    })
                    lead_notes.append({
                        "note": root + scale[2],
                        "start": start + 1.0,
                        "end": start + 1.5,
                        "velocity": 110
                    })
                continue
                
            progress = bar_idx / bar_count
            if progress < 0.25:
                # Phase 1: Sparse single long floating note
                lead_notes.append({
                    "note": root + scale[2],
                    "start": start + 0.5,
                    "end": start + 1.8,
                    "velocity": 75
                })
            elif progress < 0.50:
                # Phase 2: Floating slow melody (2 notes)
                lead_notes.append({
                    "note": root + scale[2],
                    "start": start + 0.25,
                    "end": start + 1.0,
                    "velocity": 85
                })
                lead_notes.append({
                    "note": root + scale[4],
                    "start": start + 1.0,
                    "end": start + 1.8,
                    "velocity": 90
                })
            elif progress < 0.75:
                # Phase 3: Rhythmic pentatonic phrases (4 notes)
                lead_notes.append({
                    "note": root + scale[0],
                    "start": start,
                    "end": start + 0.4,
                    "velocity": 95
                })
                lead_notes.append({
                    "note": root + scale[2],
                    "start": start + 0.5,
                    "end": start + 0.9,
                    "velocity": 92
                })
                lead_notes.append({
                    "note": root + scale[3],
                    "start": start + 1.0,
                    "end": start + 1.4,
                    "velocity": 98
                })
                lead_notes.append({
                    "note": root + scale[4],
                    "start": start + 1.5,
                    "end": start + 1.9,
                    "velocity": 100
                })
            else:
                # Phase 4: Melodic arpeggio runs (fast rising climax notes!)
                run_offsets = [0, 2, 4, 5, 4, 5, 6, 7]
                for note_step, scale_idx in enumerate(run_offsets):
                    note_start = start + note_step * 0.25
                    lead_notes.append({
                        "note": root + scale[scale_idx],
                        "start": note_start,
                        "end": note_start + 0.2,
                        "velocity": 105 + note_step
                    })
        return lead_notes

    def _synthesize_counter_melody(self, progression: List[Dict[str, Any]], is_long: bool, builds_complexity: bool = False) -> List[Dict[str, Any]]:
        """
        Counter-Melody Layer: Voiced middle-register chord progression (pad/rhodes).
        If 'builds_complexity' is true, chords evolve from simple roots to full, rhythmic pulses.
        """
        chords_notes = []
        bar_count = len(progression)
        
        for item in progression:
            bar_idx = item["bar"]
            root = item["root"] + 12
            start = item["start_time"]
            end = item["end_time"]
            ctype = item["type"]
            
            if ctype == "min":
                voicing = [0, 3, 7]
            else:
                voicing = [0, 4, 7]
                
            if not builds_complexity:
                for offset in voicing:
                    chords_notes.append({
                        "note": root + offset,
                        "start": start,
                        "end": end - 0.05,
                        "velocity": 75
                    })
                continue
                
            progress = bar_idx / bar_count
            if progress < 0.25:
                # Phase 1: Simple root note pad
                chords_notes.append({
                    "note": root,
                    "start": start,
                    "end": end - 0.05,
                    "velocity": 55
                })
            elif progress < 0.50:
                # Phase 2: Simple dyad (root + fifth)
                for offset in [0, 7]:
                    chords_notes.append({
                        "note": root + offset,
                        "start": start,
                        "end": end - 0.05,
                        "velocity": 65
                    })
            elif progress < 0.75:
                # Phase 3: Full rich 3-note triad pad
                for offset in voicing:
                    chords_notes.append({
                        "note": root + offset,
                        "start": start,
                        "end": end - 0.05,
                        "velocity": 75
                    })
            else:
                # Phase 4: Repeating rhythmic chord pulses (4 quarter notes per bar)
                for step in range(4):
                    chord_start = start + step * 0.5
                    for offset in voicing:
                        chords_notes.append({
                            "note": root + offset,
                            "start": chord_start,
                            "end": chord_start + 0.45,
                            "velocity": 82
                        })
        return chords_notes
