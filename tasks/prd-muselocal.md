# Product Requirements Document (PRD)

## Project Name: MuseLocal
## Document Version: 1.0.0
## Target Audience: Junior Developer Implementation Guide
## Status: Ready for Development

---

## 1. Overview & Core Problem
Musicians, producers, and composers often lose creative momentum when navigating complex music theory concepts or manually drawing intricate MIDI velocity and controller data inside a Digital Audio Workstation (DAW). Existing AI-driven musical tools are largely cloud-based, threatening data sovereignty, charging subscription fees, introducing latency, and outputting flat audio waveforms rather than raw, editable multi-track MIDI arrangements.

**MuseLocal** is a 100% offline, privacy-first desktop utility that operates as a local AI music accompaniment and style transfer engine. It enables users to generate complex musical patterns using natural language prompts, transform existing MIDI tracks, or capture live performances directly from hardware controllers, outputting pristine, sync'd multi-track MIDI data straight back into their DAW via native OS drag-and-drop mechanisms.

---

## 2. Goals
* **G-1: Absolute Privacy & Sovereignty:** Process all user input, performance captures, and machine learning inference completely offline. Zero data packets must leave the user's physical machine.
* **G-2: Zero-Latency Generation Loop:** Deliver note-generation arrays in under 12 seconds for an 8-bar multi-track setup on modern local hardware acceleration baselines.
* **G-3: High Structural Editability:** Target symbolic MIDI data exclusively (MIDI Spec 1.0). Avoid audio rendering or wave generation entirely for the initial release version.
* **G-4: Seamless DAW Interoperability:** Provide an unhindered drag-and-drop interface layer allowing the immediate deployment of target files straight onto active DAW timelines.

---

## 3. User Stories

* **US-1: Generative Seed Pitching:** As a songwriter, I want to write a descriptive music theory prompt (e.g., *"Syncopated neo-soul chord progression, Rhodes style, key of F# minor, 95 BPM"*) so that I can instantly generate editable MIDI structures to kickstart my track.
* **US-2: Section Overhaul (Style Transfer):** As a producer, I want to drop a rigid, mechanically quantized block-chord MIDI file into the application and modify it via text prompts (e.g., *"Make it a highly syncopated funk clavinet part in Herbie Hancock's style"*) to infuse organic movement and complex syncopation.
* **US-3: Multi-Track Arrangement Overdub:** As a solo composer, I want to drop an original keyboard chord track into the interface and selectively generate up to 3 to 4 distinct, harmonically locked backing layers (e.g., matching bassline, rhythmic top line, and an expressive solo lead) simultaneously.
* **US-4: Expressive Articulation Post-Processing:** As a media composer, I want to adjust physical dashboard sliders (Humanisation, Velocity Accents, Note Lengths) to instantly inject non-destructive performance parameters and smooth CC curves without re-running the underlying AI generation core.
* **US-5: Live Stream Capture Canvas:** As an improvisational keyboardist, I want to engage a direct record mode to capture live performance notes straight from my hardware controller, saving it as a local baseline canvas for subsequent multi-track accompaniment workflows.

---

## 4. Functional Requirements

### 4.1 Ingestion & Realtime MIDI Capture
1. **File Drop Handling:** The system must accept physical `.mid` (Format 0 and Format 1) file drag-and-drop actions across the designated browser viewport area.
2. **rtmidi Hardware Port Initialization:** The backend must spin up low-level cross-platform hardware port hooks using `python-rtmidi` to actively listen for incoming stream packets from connected USB/Hardware MIDI devices.
3. **Live Stream Caching:** When the capture toggle is armed, incoming packets must write sequentially into an unquantised volatile local memory cache array containing: `[status_byte, note_number, velocity, delta_timestamp]`.
4. **On-Demand Input Quantisation:** The interface must offer an input processing toggle enabling the immediate alignment of captured performance note-on sequences to the nearest musical grid boundary (1/8, 1/16, 1/32 notes) based on the target tempo, while natively preserving the raw unquantised array as a baseline default.
5. **Local Canvas Serialization:** Upon hitting "Stop Capture", the cached performance sequence must instantly serialize into an internal structural reference asset (`Captured_Baseline`), bypassing local file system storage boundaries.

### 4.2 Machine Learning Inference & Multi-Track Synthesis
1. **Resident FastAPI Server Lifecycle:** The application launcher must spin up a background Python FastAPI worker instance. This process must remain active in system memory to cache the tokenization structures and local model weights, completely avoiding initialization cold-start penalties across consecutive user requests.
2. **Harmonic Interrogation Parsing:** Incoming source arrays must execute through a preprocessing script (`pretty_midi`) to map the structural timeline, calculate primary base note velocities, and compute implied scale matrices across the timeline.
3. **Hidden System Conditioning Mask:** The extracted harmonic profile must automatically combine with the active user prompt into a hidden structural context token block before passing to the model architecture.
4. **Simultaneous Multi-Track Orchestration:** The core model execution layer must sustain the concurrent synthesis of 3 to 4 independent target instrumental tracks derived from a singular ingestion canvas. The engine must systematically route note synthesis streams into distinct destination profiles based on user choices:
   * **Bassline Layer:** Restrict generation explicitly to octaves $C1 \rightarrow C3$, forcing downbeat alignment on bar lines while predicting syncopated intervals on off-beats.
   * **Solo Lead Line Layer:** Restrict notes to octaves $C4 \rightarrow G6$, utilizing modal scale scales (e.g., Dorian, Mixolydian) linked to the calculated chord changes.
   * **Counter-Melody/Movement Layer:** Extrapolate voice-leading inversions and rhythmic variations directly spanning the middle registers.
5. **Generation Task Interruption:** The interface must surface an active, responsive "Cancel Generation" controller button during execution. Engaging this element must pass a termination call to the FastAPI thread, immediately freeing local VRAM/RAM allocations and resetting the client UI to a stable waiting layout state.

### 4.3 Heuristic Articulation Engine (Post-Processing)
1. **Decoupled Realtime Execution Modifiers:** Post-processing adjustments (Rhythmic Humanisation, Velocity Scale, Length Ratios) must calculate strictly outside the main AI generation stack, executing via rapid Python arithmetic loops for immediate file manipulation.
2. **Micro-Timing Randomisation:** The system must evaluate note-on intervals against a user-defined threshold slider (0-100ms) to introduce controlled micro-timing offsets, simulating a human player's organic groove.
3. **Dynamic Accent Re-scaling:** The post-processor must map note velocities against a relative scale vector based on metric positions, emphasizing primary downbeats while proportionally lowering passing intervals or ghost notes.
4. **Automated Continuous Controller (CC) Vector Paths:** The system must append smooth automation curves for CC#11 (Expression) and CC#1 (Modulation Wheel) underneath long note events, calculating exponential or linear swelling variations according to dashboard control settings.
5. **Legato/Staccato Note Extension Alterations:** The length controller must adjust absolute note durations, inducing automatic overlaps ($legato$) or tightening gate durations ($staccato$) based on current dashboard parameters.

### 4.4 Compilation & OS Export Interaction
1. **Target Multi-Track Compilation Assembler:** Output files must compile into verified standard MIDI Specification 1.0 structures. The tracks must introduce empty leading time paddings to ensure exact synchronization with the original source track placement when pulled onto external DAW grids.
2. **Browser Drag-Out Handle Protocol:** The system must construct temporary physical `.mid` references inside an internal cache folder upon successful generation. The UI must present a distinct drag component utilizing OS-level file system event registration, allowing users to select and drop files cleanly into popular external timelines (such as Ableton Live, Logic Pro, or Windows Explorer).

---

## 5. Non-Goals (Out of Scope)
* **NG-1: Internal Audio Waveform Rendering:** The tool will not host virtual instruments, sampler modules, soundfont engines, or produce physical `.wav`/`.mp3` audio file outputs.
* **NG-2: Linear MIDI Piano Roll Editor Interface:** Users will not perform granular note-by-note mouse grid edits inside this utility; all note manipulation remains handled via natural language prompts, performance capture, or global articulation dials.
* **NG-3: Bidirectional External MIDI Sync:** The initial version will not support real-time MTC/MIDI Clock master/slave listening synchronization with running DAW hosts.

---

## 6. Design & UI/UX Guidelines
* **Theme Profile:** Enforce a strict low-contrast dark mode palette tailored for low-light recording studio aesthetics. Avoid stark white highlights or excessive decorative elements.
* **Layout Paradigm:** Establish a single-screen layout focusing entirely on the input canvas, role assignments, and output blocks. 
* **State Indications:** The file-drop area must transition cleanly into an active visual track visualization state upon registering an ingestion event, switching labels between "File Processing Mode" and "Live MIDI Capture Mode" dynamically.

---

## 7. Technical Considerations & Multi-Platform Strategy
* **Launch Phasing Target:** **Phase 1: Windows 10/11 x64** native executable distribution. **Phase 2: macOS Application Architecture** (Universal Binary supporting Apple Silicon M-Series and Legacy Intel architectures).
* **Multi-Platform Architecture Implementation Blueprint:** To fulfill Phase 2 requirements without rewritten layers, the developer must employ a **decoupled application shell structure**:
  * **Frontend & Window Orchestration:** Built inside **Tauri (Rust)**, utilizing the operating system's native embedded web view rendering (WebView2 on Windows, WebKit on macOS). This guarantees a minimal application footprint (under 15MB base installer) and avoids Chromium engine memory bloat.
  * **Machine Learning Core Sidecar Distribution:** Package the Python FastAPI backend module via **PyInstaller** using the single-file execution flag (`--onefile`). Configure Tauri’s bundle definitions (`tauri.conf.json > bundle > externalBin`) to handle the resulting binary bundle as an OS-specific **Sidecar Binary**.
  * **Target-Triple Asset Management:** Compile matching platform-specific versions named exactly according to host target configurations (e.g., `server-x86_64-pc-windows-msvc.exe` and `server-aarch64-apple-darwin`). Tauri will launch the appropriate child process matching the host machine at runtime.
* **Local Python Package Boundaries:** Limit all backend packages strictly to local processing libraries (`torch`, `transformers`, `mido`, `pretty_midi`, `python-rtmidi`). Do not use any third-party external calling APIs or cloud authentication hooks, ensuring compliance with strict onshore data sovereignty profiles.

---

## 8. Success Metrics
* **Inference Efficiency Compliance:** Achieve complete note token matrix generation under 12 seconds for full 4-track, 8-bar musical loops.
* **Structural Generation Success Rating:** Maintain a 0% occurrence rate of orphaned Note-On commands, broken file structures, or missing timeline headers upon file export verification.
* **Interprocess Call Stability:** Ensure that force-killing generation via the user interface cancel element immediately frees system RAM/VRAM resources without locking or crashing the parent Tauri process thread wrapper.

---

## 9. Open Questions & Investigative Tasks
1. **Model Parameter Quantisation Tuning:** Can a 4-bit AWQ or GGUF quantised variant of the text-to-midi transformer model preserve the complex modal voice-leading behavior needed for genre-specific solos while running on systems limited to 8GB of system RAM?
2. **Virtual Port Allocation Handling on Windows Platforms:** Unlike macOS which handles virtual MIDI loopback configurations natively out of the box, Windows lacks a native virtual input device driver architecture. Should the junior developer integrate a silent system fallback check that defaults to physical hardware endpoint polling if a virtual loop driver (like loopMIDI) is absent?