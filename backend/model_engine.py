import os
import io
import time
import logging
import random
import re
import json
from typing import List, Dict, Any, Optional

import httpx
import mido
import torch
try:
    import torch
except ImportError:
    torch = None
from pathlib import Path
logger = logging.getLogger("muselocal-model-engine")

try:
    import pretty_midi
except ImportError:
    logger.warning("pretty_midi not installed yet. Placeholders will be active.")
    pretty_midi = None

class ModelEngine:
    def __init__(self):
        self.is_interrupted = False
        self.is_model_loaded = False
        
        # Local LLM API Settings (Ollama OpenAI-compatible endpoint)
        self.base_url = "http://127.0.0.1:11434/v1"
        self.model_name = "Qwen/Qwen2.5-Coder-3B-Instruct"
        self.device = "cpu"  # Kept for API compatibility with existing layers
        
        logger.info(f"Model Engine initialized. Routing locally to Ollama at {self.base_url} with model {self.model_name}.")
        # Load model config
        config_path = Path(__file__).resolve().parents[1] / "src" / "config" / "model_config.json"
        if not config_path.is_file():
            raise FileNotFoundError(f"Model config file not found: {config_path}")
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
            self.model_path = Path(cfg.get("model_path"))
        except Exception as e:
            raise FileNotFoundError(f"Failed to read model config: {e}")
        if not self.model_path.is_dir():
            raise FileNotFoundError(f"Configured model_path does not exist or is not a directory: {self.model_path}")
        # Deferred LoRA loading; will be performed on first generation request


    def load_model_weights(self, model_path: Optional[str] = None):
        """Load the fine‑tuned LoRA model from a fixed location.
        Raises an exception if the model cannot be loaded.
        """
        if self.is_model_loaded:
            return True
            
        # Determine model path: use provided argument or default hard‑coded path
        if model_path is None:
            model_path = self.model_path
        else:
            model_path = Path(model_path)
        if not model_path.is_dir():
            logger.error(f"Fine‑tuned model directory not found: {model_path}")
            raise FileNotFoundError(f"Model directory missing: {model_path}")
        if not (model_path / "adapter_model.bin").exists() and not (model_path / "adapter_model.safetensors").exists():
            logger.error(f"LoRA adapter files missing in: {model_path}")
            raise FileNotFoundError(f"Adapter weights missing in: {model_path}")

        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import PeftModel

            tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)

            logger.warning("Forcing model load on CPU (may be slow).")
            base_model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16,
                device_map="cpu",
                low_cpu_mem_usage=True,
                trust_remote_code=True
            )
            self.device = "cpu"


            # Verify that the adapter config exists
            adapter_config_path = model_path / "adapter_config.json"
            if not adapter_config_path.is_file():
                logger.error(f"Adapter config not found at {adapter_config_path}")
                raise FileNotFoundError(
                    f"Missing 'adapter_config.json' in LoRA directory: {model_path}. "
                    "Ensure the adapter was saved with peft.save_pretrained()."
                )

            # Load the LoRA adapter on top of the base model
            try:
                lora_model = PeftModel.from_pretrained(base_model, "C:\\MuseLocalModel")
                self.model = lora_model
            except OSError as e:
                logger.warning(f"Could not load LoRA weights, falling back to base model: {e}")
                self.model = base_model
                
            self.base_model = base_model
            self.tokenizer = tokenizer
            self.is_model_loaded = True
            logger.info(f"Model loaded from {model_path}")
            return True
        except Exception as e:
            logger.error(f"Error loading LoRA model: {e}")
            raise

    def trigger_cancel(self):
        self.is_interrupted = True

    def clear_vram_resources(self):
        pass

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
        Synthesizes highly advanced multi-track MIDI arrangements.
        Routes to local LLM APIs (Ollama/LM Studio) if available, with a high-fidelity algorithmic fallback.
        """
        self.is_interrupted = False
        if not self.is_model_loaded:
            try:
                self.load_model_weights()
            except Exception as e:
                logger.warning(f"Could not load model weights ({e}). Proceeding to API/fallback.")
        # Execution delay loop simulation for async pipeline tests / cancellation interlock
        for _ in range(3):
            if self.is_interrupted:
                self.clear_vram_resources()
                return {"status": "cancelled", "message": "Inference cancelled."}
            time.sleep(0.01)

        logger.info(f"Generating session tracks for roles: {instrument_roles}")
        
        prompt_lower = prompt.lower()
        bar_match = re.search(r'(\d+)\s*bar', prompt_lower)
        bar_count = int(bar_match.group(1)) if bar_match else 8
        bar_count = max(4, min(32, bar_count))
        
        style_meta = {
            "is_cuban": any(k in prompt_lower for k in ["cuban", "montuno", "salsa", "latin", "afro-cuban"]),
            "is_reggae": any(k in prompt_lower for k in ["reggae", "skank", "dub", "riddim"]),
            "is_jazz": any(k in prompt_lower for k in ["jazz", "jazzy", "swing", "modal", "ii-v-i"]),
            "is_blues": any(k in prompt_lower for k in ["blues", "bluesy", "shuffle", "slurs"]),
            "is_minor": any(k in prompt_lower for k in ["minor", "sad", "dark", "dorian", "aeolian"])
        }
        
        if not any([style_meta["is_cuban"], style_meta["is_reggae"], style_meta["is_jazz"], style_meta["is_blues"]]):
            style_meta["is_jazz"] = True

        seconds_per_bar = 2.0  # 120 BPM baseline
        progression = self._build_harmonic_progression(bar_count, seconds_per_bar, style_meta)

        # Attempt local PyTorch LoRA model generation
        chords_str = ", ".join([f"Bar {c['bar']}: {c['type']} on root {c['root']}" for c in progression])
        
        full_inference_prompt = (
            "<|im_start|>system\n"
            "You are an expert AI MIDI composer and elite studio session musician.\n"
            f"Your task is to generate a multi-track MIDI arrangement in raw JSON format for the following roles: {instrument_roles}.\n"
            f"The progression chord map is: {chords_str}.\n"
            "Represent the notes as a JSON object where keys are the exact instrument roles, and values are arrays of note objects:\n"
            '{"role_name": [{"note": midi_pitch_integer, "start": start_seconds_float, "end": end_seconds_float, "velocity": velocity_integer}]}\n\n'
            "Strict MIDI Pitch Rules:\n"
            "- 'bassline' pitches must be in the C1-C3 range (MIDI values 24-48).\n"
            "- 'lead' solo pitches must be in the C4-C6 range (MIDI values 60-84).\n"
            "- 'counter-melody' chords/pads must be in the C3-C5 range (MIDI values 48-72).\n\n"
            "Formatting Rules:\n"
            "- All note 'start' and 'end' values must be positive floats representing absolute time in seconds.\n"
            "- Do not overlap notes on the same track unless it is 'counter-melody' (which allows polyphonic chords).\n"
            "- Output ONLY valid raw JSON. Do not write any markdown code wrappers (like ```json), introduction, or explanations.\n"
            "<|im_end|>\n"
            f"<|im_start|>user\nGenerate notes based on this creative style prompt: {prompt}\n<|im_end|>\n"
            "<|im_start|>assistant\n"
        )

        raw_response = self._query_local_llm(full_inference_prompt)
        
        llm_success = False
        generated_tracks = {}
        if raw_response:
            try:
                cleaned_content = raw_response.strip()
                if cleaned_content.startswith("```"):
                    cleaned_content = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned_content)
                    cleaned_content = re.sub(r"\s*```$", "", cleaned_content)
                
                parsed_tracks = json.loads(cleaned_content)
                for role in instrument_roles:
                    if role in parsed_tracks and isinstance(parsed_tracks[role], list):
                        validated_notes = []
                        for note in parsed_tracks[role]:
                            if all(k in note for k in ["note", "start", "end", "velocity"]):
                                validated_notes.append({
                                    "note": int(note["note"]),
                                    "start": float(note["start"]),
                                    "end": float(note["end"]),
                                    "velocity": int(note["velocity"])
                                })
                        generated_tracks[role] = validated_notes
                    else:
                        generated_tracks[role] = []
                llm_success = True
            except Exception as parse_err:
                logger.error(f"Failed to parse or validate local PyTorch model output: {parse_err}. Raw output was: {raw_response}")

        if llm_success and generated_tracks:
            logger.info("Successfully synthesized tracks utilizing local PyTorch LoRA model.")
            return {"status": "completed", "tracks": generated_tracks}
            
        logger.info("Local PyTorch LoRA model returned invalid payload. Utilizing high-fidelity algorithmic fallback.")
        
        # High-fidelity algorithmic music theory fallback
        generated_data = {}
        for role in instrument_roles:
            if role == "bassline":
                generated_data["bassline"] = self._generate_session_bassline(progression, style_meta)
            elif role == "lead":
                generated_data["lead"] = self._generate_session_lead(progression, style_meta)
            elif role == "counter-melody" or role == "chords":
                generated_data["counter-melody"] = self._generate_session_harmony(progression, style_meta)
            else:
                generated_data[role] = []

        return {"status": "completed", "tracks": generated_data}

    def _query_local_llm(self, prompt: str) -> str:
        """Queries the loaded local PyTorch LoRA model directly."""
        try:
            if not getattr(self, 'model', None) or not getattr(self, 'tokenizer', None):
                print("Model or tokenizer not loaded in memory!")
                return ""

            print("Starting PyTorch inference with custom LoRA...")
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

            outputs = self.model.generate(
                **inputs,
                max_new_tokens=1500,
                temperature=0.7,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )

            # Decode only the newly generated tokens
            input_length = inputs.input_ids.shape[1]
            generated_tokens = outputs[0][input_length:]
            response_text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
            
            print("Inference complete. Response received.")
            return response_text

        except Exception as e:
            print(f"PyTorch Inference Error: {e}")
            return ""

    def _build_harmonic_progression(self, bar_count: int, seconds_per_bar: float, style: Dict[str, bool]) -> List[Dict[str, Any]]:
        """Compiles sophisticated extended chord maps including root, type, and specific jazz/latin extensions."""
        progression = []
        if style["is_jazz"] or style["is_cuban"]:
            roots = [50, 43, 48, 45] 
            types = ["min9", "dom13", "maj9", "dom7alt"]
        elif style["is_blues"]:
            roots = [48, 48, 48, 48, 53, 53, 48, 48, 55, 53, 48, 55]
            types = ["dom7", "dom7", "dom7", "dom7", "dom7", "dom7", "dom7", "dom7", "dom7", "dom7", "dom7", "dom7"]
        elif style["is_reggae"]:
            roots = [45, 40, 45, 40]
            types = ["min", "min", "min", "min"]
        else:
            roots = [45, 41, 48, 43] if style["is_minor"] else [48, 43, 45, 41]
            types = ["min7", "maj7", "maj7", "dom7"] if style["is_minor"] else ["maj7", "dom7", "min7", "maj7"]

        for bar in range(bar_count):
            idx = bar % len(roots)
            progression.append({
                "bar": bar,
                "start_time": bar * seconds_per_bar,
                "end_time": (bar + 1) * seconds_per_bar,
                "root": roots[idx],
                "type": types[idx]
            })
        return progression

    def _generate_session_harmony(self, progression: List[Dict[str, Any]], style: Dict[str, bool]) -> List[Dict[str, Any]]:
        """Generates premium voice-leading chord voicings with syncopation."""
        notes = []
        prev_voicing = None
        for item in progression:
            start = item["start_time"]
            root = item["root"] + 12
            ctype = item["type"]
            
            if ctype == "min9":
                voicing_offsets = [3, 7, 10, 14]
            elif ctype == "dom13":
                voicing_offsets = [4, 10, 14, 21]
            elif ctype == "maj9":
                voicing_offsets = [4, 7, 11, 14]
            elif ctype == "dom7alt":
                voicing_offsets = [4, 10, 13, 20]
            elif "7" in ctype:
                voicing_offsets = [0, 4, 7, 10] if "dom" in ctype else [0, 3, 7, 10]
            else:
                voicing_offsets = [0, 3, 7, 12] if "min" in ctype else [0, 4, 7, 12]

            current_voicing = [root + offset for offset in voicing_offsets]
            if prev_voicing is not None:
                optimized_voicing = []
                for note_val in current_voicing:
                    closest = min(prev_voicing, key=lambda x: abs((note_val % 12) - (x % 12)))
                    octave_shift = (closest // 12) * 12
                    target_note = octave_shift + (note_val % 12)
                    if abs(target_note - closest) > 6:
                        target_note += 12 if target_note < closest else -12
                    optimized_voicing.append(target_note)
                current_voicing = sorted(optimized_voicing)
            prev_voicing = current_voicing

            if style["is_cuban"]:
                montuno_rhythms = [0.0, 0.375, 0.75, 1.25, 1.625]
                for idx, step_offset in enumerate(montuno_rhythms):
                    note_start = start + step_offset
                    note_end = note_start + 0.22
                    vel = 95 if idx % 2 == 1 else 80
                    for v_note in current_voicing:
                        notes.append({"note": v_note, "start": note_start, "end": note_end, "velocity": vel})
            elif style["is_reggae"]:
                skank_beats = [0.5, 1.5]
                for beat_offset in skank_beats:
                    for double_strike in [0.0, 0.04]:
                        note_start = start + beat_offset + double_strike
                        note_end = note_start + 0.15
                        for v_note in current_voicing:
                            notes.append({"note": v_note, "start": note_start, "end": note_end, "velocity": 90})
            elif style["is_jazz"]:
                rhythm_pool = [[0.0, 0.75], [0.0, 0.375, 1.25], [0.375, 1.0]]
                chosen_rhythm = random.choice(rhythm_pool)
                for step_offset in chosen_rhythm:
                    note_start = start + step_offset
                    note_end = note_start + random.uniform(0.25, 0.45)
                    vel = random.randint(85, 100)
                    for v_note in current_voicing:
                        notes.append({"note": v_note, "start": note_start, "end": note_end, "velocity": vel})
            else:
                for v_note in current_voicing:
                    notes.append({"note": v_note, "start": start, "end": start + 1.92, "velocity": 72})
        return notes

    def _generate_session_bassline(self, progression: List[Dict[str, Any]], style: Dict[str, bool]) -> List[Dict[str, Any]]:
        """Generates dynamic bass grooves."""
        notes = []
        for item in progression:
            start = item["start_time"]
            root = item["root"] - 12
            
            if style["is_reggae"]:
                reggae_pattern = [(0.5, 0.35, root), (1.0, 0.25, root + 7), (1.5, 0.3, root + 5)]
                for b_start, b_dur, b_note in reggae_pattern:
                    notes.append({"note": b_note, "start": start + b_start, "end": start + b_start + b_dur, "velocity": 105})
            elif style["is_cuban"]:
                tumbao_rhythms = [(0.375, 0.3, root), (0.75, 0.4, root + 7), (1.75, 0.3, root + 12)]
                for b_start, b_dur, b_note in tumbao_rhythms:
                    notes.append({"note": b_note, "start": start + b_start, "end": start + b_start + b_dur, "velocity": 100})
            elif style["is_jazz"] or style["is_blues"]:
                for step in range(4):
                    b_start = start + step * 0.5
                    b_dur = 0.44
                    if step == 0: b_note = root
                    elif step == 1: b_note = root + 4
                    elif step == 2: b_note = root + 7
                    else: b_note = root + 11
                    notes.append({"note": b_note, "start": b_start, "end": b_start + b_dur, "velocity": random.randint(88, 98)})
            else:
                for step in [0.0, 0.5, 1.0, 1.5]:
                    notes.append({"note": root, "start": start + step, "end": start + step + 0.4, "velocity": 90})
        return notes

    def _generate_session_lead(self, progression: List[Dict[str, Any]], style: Dict[str, bool]) -> List[Dict[str, Any]]:
        """Generates lyrical solos with grace notes and bluesy slurs."""
        notes = []
        jazz_dorian = [0, 2, 3, 5, 7, 9, 10, 12]
        blues_scale = [0, 3, 5, 6, 7, 10, 12]
        
        for item in progression:
            start = item["start_time"]
            root = item["root"] + 24
            scale = blues_scale if style["is_blues"] or style["is_cuban"] else jazz_dorian
            
            if style["is_jazz"] or style["is_blues"] or style["is_cuban"]:
                phrasing_offsets = [0.0, 0.25, 0.375, 0.75, 1.125, 1.5]
                for idx, step_offset in enumerate(phrasing_offsets):
                    if random.random() < 0.25:
                        continue
                    note_start = start + step_offset
                    note_end = note_start + random.uniform(0.12, 0.28)
                    scale_deg = random.choice([2, 3, 4, 5])
                    note_val = root + scale[scale_deg]
                    
                    if random.random() < 0.35:
                        notes.append({
                            "note": note_val - 1, 
                            "start": note_start, 
                            "end": note_start + 0.04, 
                            "velocity": 75
                        })
                        note_start += 0.04
                        
                    vel = random.randint(95, 115) if idx == 0 or idx == 3 else random.randint(80, 95)
                    notes.append({"note": note_val, "start": note_start, "end": note_end, "velocity": vel})
            else:
                lyrical_flow = [0.0, 0.5, 1.0]
                for step in lyrical_flow:
                    notes.append({
                        "note": root + scale[random.choice([0, 2, 4])], 
                        "start": start + step, 
                        "end": start + step + 0.4, 
                        "velocity": 85
                    })
        return notes

    def compile_to_midi_bytes(self, tracks_data: Dict[str, List[Dict[str, Any]]], tempo_bpm: float = 120.0) -> bytes:
        mid = mido.MidiFile(type=1)
        ticks_per_beat = mid.ticks_per_beat
        
        meta_track = mido.MidiTrack()
        mid.tracks.append(meta_track)
        meta_track.append(mido.MetaMessage('time_signature', numerator=4, denominator=4, time=0))
        meta_track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(tempo_bpm), time=0))
        meta_track.append(mido.MetaMessage('end_of_track', time=0))
        
        for role, notes_list in tracks_data.items():
            if not notes_list:
                continue
            track = mido.MidiTrack()
            mid.tracks.append(track)
            track.append(mido.MetaMessage('track_name', name=role.capitalize(), time=0))
            
            messages = []
            for note in notes_list:
                on_tick = int(note["start"] * (tempo_bpm / 60.0) * ticks_per_beat)
                off_tick = int(note["end"] * (tempo_bpm / 60.0) * ticks_per_beat)
                
                on_tick = max(0, on_tick)
                off_tick = max(on_tick + 1, off_tick)
                
                messages.append((on_tick, 'note_on', note["note"], note["velocity"]))
                messages.append((off_tick, 'note_off', note["note"], 0))
                
            messages.sort(key=lambda x: (x[0], 0 if x[1] == 'note_off' else 1))
            
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
