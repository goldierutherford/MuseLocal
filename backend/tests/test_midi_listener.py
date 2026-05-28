import pytest
from backend.midi_listener import MIDIListener

def test_port_enumeration_does_not_crash():
    """
    Ensure port scanning returns a list structure without raising crashes, 
    even when rtmidi is missing or physical hardware is disconnected.
    """
    listener = MIDIListener()
    ports = listener.get_available_ports()
    assert isinstance(ports, list)

def test_quantization_empty_events():
    """
    Quantizer should gracefully return empty lists if no input events exist.
    """
    listener = MIDIListener()
    res = listener.quantize_events([], tempo=120.0, grid_division="1/16")
    assert res == []

def test_quantization_math_boundaries():
    """
    Verify absolute timestamp rounding matches expected musical grid lines:
    At 120 BPM:
    - Beat duration = 60 / 120 = 0.5s
    - 1/16 grid division = 0.5 * 0.25 = 0.125s
    - An event at 0.06s should round to 0.0s or 0.125s based on proximity.
      0.06 / 0.125 = 0.48 -> rounds to 0.0s.
      0.07 / 0.125 = 0.56 -> rounds to 0.125s.
    """
    listener = MIDIListener()
    
    mock_events = [
        # Note on event at 0.05 seconds (closer to 0.0 than 0.125)
        {"status_byte": 0x90, "note_number": 60, "velocity": 100, "timestamp": 0.05},
        # Note on event at 0.09 seconds (closer to 0.125 than 0.0)
        {"status_byte": 0x90, "note_number": 62, "velocity": 90, "timestamp": 0.09},
        # Meta event (e.g. program change) which should bypass quantisation changes
        {"status_byte": 0xC0, "note_number": 1, "velocity": 0, "timestamp": 0.5}
    ]
    
    quantized = listener.quantize_events(mock_events, tempo=120.0, grid_division="1/16")
    
    assert len(quantized) == 3
    # Event 0: 0.05 / 0.125 = 0.4 -> rounded to 0.0s
    assert quantized[0]["timestamp"] == 0.0
    # Event 1: 0.09 / 0.125 = 0.72 -> rounded to 0.125s
    assert quantized[1]["timestamp"] == 0.125
    # Event 2: should bypass quantisation, timestamp remains 0.5
    assert quantized[2]["timestamp"] == 0.5

def test_capture_lifecycle_standby():
    """
    Verify capture start and stop updates state toggles safely.
    """
    listener = MIDIListener()
    started = listener.start_capture(port_index=0)
    assert started is True
    assert listener.is_capturing is True
    
    events = listener.stop_capture()
    assert listener.is_capturing is False
    assert isinstance(events, list)
