import random
import logging
from typing import List, Dict, Any

logger = logging.getLogger("muselocal-articulation")

class ArticulationEngine:
    @staticmethod
    def apply_humanization(notes: List[Dict[str, Any]], humanize_ms: float) -> List[Dict[str, Any]]:
        """
        Apply micro-timing randomisation. Shift note-on timings by small, controlled offsets.
        humanize_ms determines the maximum shift limit (0 to 100ms).
        """
        if humanize_ms <= 0:
            return notes

        humanize_seconds = humanize_ms / 1000.0
        adjusted_notes = []

        for note in notes:
            # Generate a small random shift (positive or negative)
            offset = random.uniform(-humanize_seconds, humanize_seconds)
            
            # Make sure we don't shift start times below zero
            new_start = max(0.0, note["start"] + offset)
            new_end = max(new_start + 0.05, note["end"] + offset) # Keep a minimum note duration of 50ms
            
            new_note = note.copy()
            new_note["start"] = new_start
            new_note["end"] = new_end
            adjusted_notes.append(new_note)
            
        logger.info(f"Applied humanization timing offset up to {humanize_ms}ms to {len(notes)} notes.")
        return adjusted_notes

    @staticmethod
    def scale_velocities(notes: List[Dict[str, Any]], accent_scale: float) -> List[Dict[str, Any]]:
        """
        Rescale note velocities dynamically. Primary downbeats (beats 1 & 3 in a standard 4/4)
        receive heavier emphasis, whereas passing/ghost notes are scaled down, all multiplied by accent_scale.
        """
        adjusted_notes = []

        for note in notes:
            start_time = note["start"]
            
            # Estimate position inside a 4-beat bar (assuming standard 4/4 time and 120 bpm, i.e. 2 seconds per bar, 0.5s per beat)
            # Find time offset within 4 beats
            beat_offset = (start_time % 2.0) / 0.5
            
            is_strong_downbeat = abs(beat_offset - 0.0) < 0.05 or abs(beat_offset - 2.0) < 0.05
            is_medium_downbeat = abs(beat_offset - 1.0) < 0.05 or abs(beat_offset - 3.0) < 0.05
            
            # Strong beats get more volume, syncopations / off-beats get less volume
            if is_strong_downbeat:
                beat_multiplier = 1.15
            elif is_medium_downbeat:
                beat_multiplier = 1.0
            else:
                beat_multiplier = 0.85
                
            new_velocity = int(note["velocity"] * beat_multiplier * accent_scale)
            # Clip between MIDI spec boundaries (1-127)
            new_velocity = max(1, min(127, new_velocity))
            
            new_note = note.copy()
            new_note["velocity"] = new_velocity
            adjusted_notes.append(new_note)
            
        logger.info(f"Applied metric velocity re-scaling with base scale {accent_scale}.")
        return adjusted_notes

    @staticmethod
    def adjust_note_lengths(notes: List[Dict[str, Any]], length_ratio: float) -> List[Dict[str, Any]]:
        """
        Adjust gate duration lengths.
        length_ratio > 1.0 introduces legato overlaps.
        length_ratio < 1.0 shortens gates for staccato articulation.
        """
        adjusted_notes = []

        for note in notes:
            duration = note["end"] - note["start"]
            new_duration = duration * length_ratio
            # Guarantee notes have a minor soundable duration (e.g. 20ms)
            new_duration = max(0.02, new_duration)
            
            new_note = note.copy()
            new_note["end"] = note["start"] + new_duration
            adjusted_notes.append(new_note)
            
        logger.info(f"Adjusted note duration lengths using ratio: {length_ratio}.")
        return adjusted_notes

    @staticmethod
    def generate_cc_curves(notes: List[Dict[str, Any]], cc_number: int, curve_type: str = "linear") -> List[Dict[str, Any]]:
        """
        Synthesize automated continuous controller (CC) vectors beneath long note events.
        CC#11 (Expression) or CC#1 (Modulation Wheel) generated as sequential control frames.
        """
        cc_events = []
        
        for index, note in enumerate(notes):
            duration = note["end"] - note["start"]
            
            # Only apply swells to long note events (> 0.8 seconds)
            if duration >= 0.8:
                steps = 10
                step_size = duration / steps
                
                for step in range(steps + 1):
                    t = step / steps
                    timestamp = note["start"] + (step * step_size)
                    
                    # Generate CC value based on curve type
                    if curve_type == "exponential":
                        # Exponential swell up
                        val = int(127 * (t ** 2))
                    else:
                        # Linear swell up and fade down
                        if t <= 0.5:
                            val = int(127 * (t * 2))
                        else:
                            val = int(127 * (2 - t * 2))
                            
                    val = max(0, min(127, val))
                    cc_events.append({
                        "cc_number": cc_number,
                        "value": val,
                        "timestamp": timestamp,
                        "linked_note_index": index
                    })
                    
        logger.info(f"Generated {len(cc_events)} CC#{cc_number} modulation frames under active timeline tracks.")
        return cc_events
