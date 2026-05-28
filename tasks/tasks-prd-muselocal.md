Relevant Files
src/tauri.conf.json - Configuration for the Tauri desktop wrapper, defining window properties and the local Python sidecar layout.

src-tauri/src/main.rs - The Rust entry point responsible for managing windows and orchestrating the background Python sidecar process lifetime.

backend/main.py - Core FastAPI web application routing client prompt payloads to specialized internal execution modules.

backend/tests/test_main.py - Integration testing suite verifying local loopback API routing and payload validation.

backend/midi_listener.py - Isolated runtime thread handling low-level python-rtmidi port registration and live package stream ingestion.

backend/tests/test_midi_listener.py - Functional unit tests mocking raw hardware MIDI hardware frames to evaluate stream isolation.

backend/model_engine.py - Core machine learning execution block managing PyTorch model allocation, text-to-MIDI conversions, and multi-track generation grids.

backend/articulation.py - Pure mathematical post-processing script applying non-destructive micro-timing shifts, velocity transformations, and automated CC vectors.

backend/tests/test_articulation.py - Numerical tests verifying that post-processing functions accurately scale arrays without corrupting structural headers.

src/app/page.tsx - Next.js landing workspace surfacing prompt workspaces, tracking roles, and managing drag-out interactions.

src/components/DragDropCanvas.tsx - Integrated user drop-zone handling HTML5 drag boundaries alongside live hardware capture buttons.

Notes
Python test suites utilize pytest. Execute tests locally using pytest backend/tests/.

Frontend UI components follow Next.js conventions. Execute component test suites using npm run test or npx jest.

Tasks
# MuseLocal Development Tasks

- `[x]` 1.0 Project Scaffolding & Initial Setup
  - `[x]` 1.1 Scaffold the core repository workspace layout linking Next.js and Python backend directories
    - `[x]` Run Next.js installation and initialization
    - `[x]` Scaffold Python backend directories and `requirements.txt`
    - `[x]` Create FastAPI shell and backend python file skeletons (`main.py`, `midi_listener.py`, `model_engine.py`, `articulation.py`)
    - `[x]` Create Python unit test templates
    - `[x]` Scaffold `src-tauri` directory shell structure
  - `[x]` 1.2 Configure Tauri wrapper settings & sidecar definitions in `tauri.conf.json`
  - `[x]` 1.3 Implement Rust parent process management in `main.rs` for Python sidecar lifetime tracking
  - `[x]` 1.4 Construct the automated `build.py` compilation script for multi-platform target-triple binaries

[x] 2.0 Real-time MIDI Ingestion, Hardware Port Listening, and Live Canvas Caching Engine

[x] 2.1 Set up the midi_listener.py file with safe OS hardware input listening pools utilizing the cross-platform python-rtmidi driver.

[x] 2.2 Construct the asynchronous live capture thread routine, caching streaming packets into a volatile thread-safe structure.

[x] 2.3 Program structural grid-quantisation matrix helpers allowing quick alignment of performance notes to configurable musical boundaries.

[x] 2.4 Expose a FastAPI stream lifecycle controller endpoint (/api/capture/toggle) enabling remote frontend commands to control background recording.


[x] 3.0 Local Machine Learning Engine & Multi-Track Synthesizer Backend (FastAPI Layer)

[x] 3.1 Initialize the FastAPI application infrastructure, implementing strict CORS permissions restricted to the local Tauri runtime origin.

[x] 3.2 Develop the input parsing matrix (model_engine.py) leveraging pretty_midi to compute keys, tempo properties, and root note structures from source elements.

[x] 3.3 Set up the PyTorch model initialization routine, mapping weights to local hardware acceleration backends (MPS for Apple Silicon or CUDA for NVIDIA).

[x] 3.4 Build out the simultaneous multi-track synthesis block, executing structural mask infills to output up to 3 to 4 distinct accompaniment layers.

[x] 3.5 Implement a secure endpoint cancelation handler that immediately drops running pipeline tasks and clears local RAM/VRAM resource pools.


[x] 4.0 Decoupled Heuristic Post-Processing & Articulation Engine

[x] 4.1 Construct the decoupled post-processing file (articulation.py) to adjust properties completely outside the heavy machine learning engine.

[x] 4.2 Write mathematical randomisation algorithms to shift absolute note onset frames by small, user-controlled millisecond boundaries.

[x] 4.3 Develop dynamic velocity scaling math modules to reshape performance accents based on their metric position in the bar.

[x] 4.4 Program automated MIDI continuous controller vector generators to write smooth linear or exponential CC#11/CC#1 parameter layers.


[x] 5.0 Desktop User Interface Development & Native OS Drag-and-Drop Integration

[x] 5.1 Develop the single-screen dark mode workspace utilizing TailwindCSS primitives.

[x] 5.2 Build out the unified canvas component, supporting drag file ingestion alongside visual recording indicator states.

[x] 5.3 Implement the manual articulation slider dashboard, connecting adjustments to immediate client-side API state payloads.

[x] 5.4 Program the native HTML5 file export component using browser drag-out handle protocols to drop files straight into external DAW timelines.


