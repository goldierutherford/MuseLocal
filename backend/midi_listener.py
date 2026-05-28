import time
import threading
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("muselocal-midi-listener")

class MIDIListener:
    def __init__(self):
        self.is_capturing = False
        self.capture_thread: Optional[threading.Thread] = None
        self.cached_events: List[Dict[str, Any]] = [] # Raw unquantised buffer
        self.lock = threading.Lock()
        self.rtmidi_in = None
        self.port_name = None

    def get_available_ports(self) -> List[str]:
        """
        List all physical hardware MIDI input ports.
        """
        try:
            import rtmidi
            midi_in = rtmidi.MidiIn()
            ports = midi_in.get_ports()
            return ports
        except ImportError:
            logger.warning("rtmidi library not installed. Falling back to empty port list.")
            return []
        except Exception as e:
            logger.error(f"Error querying MIDI ports: {e}")
            return []

    def start_capture(self, port_index: int = 0) -> bool:
        """
        Initialize MIDI hardware port hook and start background record thread.
        """
        with self.lock:
            if self.is_capturing:
                logger.info("MIDI Capture already running.")
                return True

            try:
                import rtmidi
                self.rtmidi_in = rtmidi.MidiIn()
                ports = self.rtmidi_in.get_ports()
                
                if not ports:
                    logger.warning("No physical hardware MIDI ports detected. Recording is in standby.")
                    self.is_capturing = True
                    self.cached_events = []
                    return True
                
                if port_index >= len(ports):
                    logger.error(f"Invalid port index {port_index}. Max index available: {len(ports)-1}")
                    return False
                
                self.port_name = ports[port_index]
                self.rtmidi_in.open_port(port_index)
                logger.info(f"Successfully connected to hardware MIDI Port: '{self.port_name}'")
            except ImportError:
                logger.warning("rtmidi is absent. Running virtual canvas mocking session.")
                self.is_capturing = True
                self.cached_events = []
                return True
            except Exception as e:
                logger.error(f"Failed to open hardware MIDI port: {e}")
                return False

            self.is_capturing = True
            self.cached_events = []
            self.capture_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.capture_thread.start()
            return True

    def _listen_loop(self):
        """
        Asynchronous listener reading raw hardware frames and storing events.
        """
        logger.info("MIDI background thread loop initialized.")
        start_time = time.time()
        
        while self.is_capturing:
            try:
                # Poll port for events
                event = self.rtmidi_in.get_message()
                if event:
                    message, delta_time = event
                    # Extract MIDI data
                    status_byte = message[0]
                    note_number = message[1] if len(message) > 1 else 0
                    velocity = message[2] if len(message) > 2 else 0
                    absolute_time = time.time() - start_time
                    
                    event_data = {
                        "status_byte": status_byte,
                        "note_number": note_number,
                        "velocity": velocity,
                        "delta_time": delta_time,
                        "timestamp": absolute_time
                    }
                    
                    with self.lock:
                        self.cached_events.append(event_data)
                        logger.debug(f"Captured MIDI event: {event_data}")
                
                time.sleep(0.001) # Keep thread sleeping to yield time
            except Exception as e:
                logger.error(f"Error in MIDI listen loop: {e}")
                break

    def stop_capture(self) -> List[Dict[str, Any]]:
        """
        Safely disarm MIDI capture loop and return the accumulated raw buffer.
        """
        with self.lock:
            self.is_capturing = False
            
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=1.0)
            
        if self.rtmidi_in:
            try:
                self.rtmidi_in.close_port()
            except Exception as e:
                logger.error(f"Error closing MIDI port: {e}")
            self.rtmidi_in = None

        logger.info(f"MIDI Capture stopped. Total events recorded: {len(self.cached_events)}")
        return self.cached_events

    def quantize_events(self, events: List[Dict[str, Any]], tempo: float, grid_division: str = "1/16") -> List[Dict[str, Any]]:
        """
        Align notes on the timeline to the nearest musical grid division.
        grid_division can be "1/8", "1/16", "1/32".
        """
        if not events:
            return []

        # Calculate duration of one beat in seconds
        beat_duration = 60.0 / tempo
        
        # Grid unit mapping
        grid_multiplier = {
            "1/8": 0.5,
            "1/16": 0.25,
            "1/32": 0.125
        }.get(grid_division, 0.25)
        
        grid_step_duration = beat_duration * grid_multiplier
        quantized_events = []
        
        for ev in events:
            # Only quantize note-on / note-off events
            status = ev["status_byte"] & 0xF0
            if status in [0x90, 0x80]:
                raw_time = ev["timestamp"]
                # Round to nearest grid boundary
                quantized_time = round(raw_time / grid_step_duration) * grid_step_duration
                
                q_ev = ev.copy()
                q_ev["timestamp"] = quantized_time
                quantized_events.append(q_ev)
            else:
                quantized_events.append(ev)
                
        return quantized_events
