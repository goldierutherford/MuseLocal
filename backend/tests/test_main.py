import pytest
import base64
from fastapi.testclient import TestClient
from backend.main import app, CAPTURED_BASELINE
import backend.main as main_module

client = TestClient(app)

# A valid mock Standard MIDI File header + tracks Base64 string for dropped file testing
MOCK_MIDI_BASE64 = (
    "TVRoZAAAAAYAAQADAGQADVRyawAAAAYAAQBkAAAAAABUUmsAAAAaAP8DCEJhc3NsaW5lAMBkAJA8"
    "AGCQPAAAAFRyawAAABoA/wMJTWVsb2R5IDIAwGQAwDwAkDwAYJA8AAA="
)

@pytest.fixture(autouse=True)
def reset_global_states():
    """
    Reset the global volatile states before every test run.
    """
    main_module.CAPTURED_BASELINE = []
    main_module.model_engine.is_interrupted = False

def test_health_check():
    """
    Verify the local health route returns a valid, healthy JSON response.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "MuseLocal Backend is running offline."}

def test_get_midi_ports():
    """
    Verify MIDI ports listing returns a success status and list of devices.
    """
    response = client.get("/api/capture/ports")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert isinstance(data["ports"], list)

def test_capture_lifecycle_integration():
    """
    Verify full capture arm/disarm and volatile state serialization.
    """
    # 1. Arm recording
    response = client.post("/api/capture/toggle?active=true&port_index=0")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["capture_active"] is True

    # Inject dummy captured notes
    main_module.midi_listener.cached_events = [
        {"status_byte": 0x90, "note_number": 60, "velocity": 100, "timestamp": 0.1, "delta_time": 0.1},
        {"status_byte": 0x80, "note_number": 60, "velocity": 0, "timestamp": 0.5, "delta_time": 0.4}
    ]

    # 2. Disarm recording
    response = client.post("/api/capture/toggle?active=false")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["capture_active"] is False
    assert data["recorded_events_count"] == 2

    # 3. Retrieve canvas without quantisation
    response = client.get("/api/capture/canvas")
    assert response.status_code == 200
    canvas_data = response.json()
    assert canvas_data["status"] == "success"
    assert canvas_data["canvas_size"] == 2
    assert canvas_data["quantized"] is False

    # 4. Retrieve canvas WITH grid quantisation
    response = client.get("/api/capture/canvas?quantize=true&grid_division=1/8&tempo=120.0")
    assert response.status_code == 200
    q_data = response.json()
    assert q_data["status"] == "success"
    assert q_data["quantized"] is True
    assert q_data["grid_division"] == "1/8"
    assert q_data["events"][0]["timestamp"] == 0.0

def test_generate_accompaniment_empty_canvas_error():
    """
    Verify generate API returns 400 Bad Request if use_captured_canvas is requested but the session is empty.
    """
    payload = {
        "prompt": "Funky baseline in F minor",
        "instrument_roles": ["bassline"],
        "use_captured_canvas": True
    }
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 400
    assert "ingestion memory is currently empty" in response.json()["detail"]

def test_generate_accompaniment_valid_payload():
    """
    Verify generation routing and response structures on successful payload submissions.
    Asserts standard MIDI base64 compilation payload is returned.
    """
    payload = {
        "prompt": "Syncopated Neo-Soul chords, Rhodes style, F# minor, 95 BPM",
        "instrument_roles": ["bassline", "lead"],
        "tempo": 95.0,
        "key_signature": "F# minor"
    }
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "midi_base64" in data
    assert "tracks" in data
    assert "bassline" in data["tracks"]
    
    # Check that returned midi_base64 is a valid base64 string and has MIDI headers
    midi_bytes = base64.b64decode(data["midi_base64"])
    assert midi_bytes.startswith(b"MThd") # Standard MIDI File Header (MThd)

def test_generate_with_dropped_midi_canvas():
    """
    Verify generation routing processes a physical dropped MIDI canvas input correctly.
    """
    payload = {
        "prompt": "Funky baseline in G minor",
        "instrument_roles": ["bassline"],
        "source_midi_base64": MOCK_MIDI_BASE64
    }
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "midi_base64" in data
    assert data["tempo_bpm"] > 0.0

def test_generate_accompaniment_valid_captured_canvas():
    """
    Verify generation routing succeeds when use_captured_canvas is requested and events exist in buffer.
    """
    # Pre-populate global CAPTURED_BASELINE
    main_module.CAPTURED_BASELINE = [
        {"status_byte": 0x90, "note_number": 60, "velocity": 100, "timestamp": 0.0}
    ]
    
    payload = {
        "prompt": "Funky baseline in F minor",
        "instrument_roles": ["bassline"],
        "use_captured_canvas": True
    }
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "tracks" in data

def test_generate_accompaniment_invalid_payload():
    """
    Verify API input validation fails on missing mandatory fields (e.g. prompt).
    """
    payload = {
        "instrument_roles": ["bassline"],
        "tempo": 120.0
    }
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 422 # Unprocessable Entity

def test_cancel_generation():
    """
    Verify cancel route returns success status.
    """
    response = client.post("/api/generate/cancel")
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "Inference thread interrupted. Resources cleared."}

def test_generate_cancellation_interlock(monkeypatch):
    """
    Assert that calling cancel during generation abruptly stops active inference loops.
    """
    import time
    
    original_sleep = time.sleep
    
    # Intercept time.sleep during loop to simulate an asynchronous user cancel trigger
    def mock_sleep(seconds):
        main_module.model_engine.trigger_cancel()
        original_sleep(0.001) # keep it fast

        
    monkeypatch.setattr("backend.model_engine.time.sleep", mock_sleep)
    
    payload = {
        "prompt": "Syncopated Neo-Soul chords, Rhodes style, F# minor, 95 BPM",
        "instrument_roles": ["bassline"],
        "tempo": 95.0
    }
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"
    assert "halted" in data["message"]


def test_process_articulation():
    """
    Verify post-processing endpoints decode, process, and re-compile successfully.
    """
    # Programmatically compile a guaranteed valid MIDI stream using our model engine
    mock_notes = {
        "bassline": [
            {"note": 60, "start": 0.0, "end": 0.5, "velocity": 100},
            {"note": 64, "start": 1.0, "end": 2.2, "velocity": 100}
        ]
    }
    midi_bytes = main_module.model_engine.compile_to_midi_bytes(mock_notes, tempo_bpm=120.0)
    midi_base64_payload = base64.b64encode(midi_bytes).decode("utf-8")

    payload = {
        "midi_base64": midi_base64_payload,
        "humanize_ms": 25.0,
        "velocity_accent_scale": 1.1,
        "length_ratio": 0.95
    }
    response = client.post("/api/process/articulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "midi_base64" in data
    assert data["tempo_bpm"] > 0.0
    
    # Assert returned stream is a valid compiled MIDI Spec 1.0 structure
    returned_midi_bytes = base64.b64decode(data["midi_base64"])
    assert returned_midi_bytes.startswith(b"MThd")


