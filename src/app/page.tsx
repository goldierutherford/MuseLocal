"use client";

import React, { useState, useEffect, useRef } from "react";
import DragDropCanvas from "../components/DragDropCanvas";

const API_BASE = "http://127.0.0.1:8000";

interface NoteEvent {
  note: number;
  start: number;
  end: number;
  velocity: number;
}

interface TracksData {
  [role: string]: NoteEvent[];
}

export default function Home() {
  // Ingestion states
  const [prompt, setPrompt] = useState("");
  const [selectedRoles, setSelectedRoles] = useState<string[]>(["bassline", "lead"]);
  const [sourceMidiBase64, setSourceMidiBase64] = useState<string | null>(null);
  const [sourceMidiFilename, setSourceMidiFilename] = useState<string | null>(null);
  const [useCapturedCanvas, setUseCapturedCanvas] = useState(false);

  // Live Hardware Capture states
  const [isRecording, setIsRecording] = useState(false);
  const [portsList, setPortsList] = useState<string[]>([]);
  const [selectedPort, setSelectedPort] = useState("");
  const [capturedNotesCount, setCapturedNotesCount] = useState(0);

  // Articulation Dashboard states (sliders)
  const [humanizeMs, setHumanizeMs] = useState(0);
  const [velocityAccent, setVelocityAccent] = useState(1.0);
  const [lengthRatio, setLengthRatio] = useState(1.0);

  // Generation & Output states
  const [isGenerating, setIsGenerating] = useState(false);
  const [originalMidiBase64, setOriginalMidiBase64] = useState<string | null>(null); // base MIDI without articulation
  const [activeMidiBase64, setActiveMidiBase64] = useState<string | null>(null); // articulated MIDI
  const [rawTracks, setRawTracks] = useState<TracksData | null>(null);
  const [activeTempo, setActiveTempo] = useState(120.0);

  // Fetch physical hardware MIDI ports on mount
  useEffect(() => {
    fetchPorts();
  }, []);

  const fetchPorts = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/capture/ports`);
      const data = await res.json();
      if (data.status === "success" && data.ports) {
        setPortsList(data.ports);
        if (data.ports.length > 0) {
          setSelectedPort(data.ports[0]);
        }
      }
    } catch (err) {
      console.warn("Failed to fetch hardware MIDI ports. Running in virtual mode.", err);
    }
  };

  const handleToggleRecording = async () => {
    const nextState = !isRecording;
    const portIndex = portsList.indexOf(selectedPort);
    const targetPortIdx = portIndex >= 0 ? portIndex : 0;

    try {
      const res = await fetch(
        `${API_BASE}/api/capture/toggle?active=${nextState}&port_index=${targetPortIdx}`,
        { method: "POST" }
      );
      const data = await res.json();
      if (data.status === "success") {
        setIsRecording(nextState);
        if (nextState) {
          // Armed capture
          setUseCapturedCanvas(true);
          setSourceMidiBase64(null);
          setSourceMidiFilename(null);
          setCapturedNotesCount(0);
        } else {
          // Capture stopped
          setCapturedNotesCount(data.recorded_events_count || 0);
        }
      }
    } catch (err) {
      console.error("Error toggling MIDI capture:", err);
      alert("Failed to communicate with local MIDI ingestion server.");
    }
  };

  const handleFileDrop = (base64Data: string, filename: string) => {
    setSourceMidiBase64(base64Data);
    setSourceMidiFilename(filename);
    setUseCapturedCanvas(false);
    if (isRecording) {
      handleToggleRecording(); // Disarm recording if a file is dropped
    }
  };

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      alert("Please write a musical layout or prompt first.");
      return;
    }
    if (selectedRoles.length === 0) {
      alert("Please select at least one instrumental role to synthesize.");
      return;
    }

    setIsGenerating(true);
    setRawTracks(null);
    setOriginalMidiBase64(null);
    setActiveMidiBase64(null);

    const payload = {
      prompt,
      instrument_roles: selectedRoles,
      source_midi_base64: sourceMidiBase64,
      use_captured_canvas: useCapturedCanvas,
      tempo: 120.0,
    };

    try {
      const res = await fetch(`${API_BASE}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Synthesis request failed.");
      }

      const data = await res.json();
      if (data.status === "success") {
        setRawTracks(data.tracks);
        setOriginalMidiBase64(data.midi_base64);
        setActiveMidiBase64(data.midi_base64);
        setActiveTempo(data.tempo_bpm);
        
        // Reset sliders on new synthesis
        setHumanizeMs(0);
        setVelocityAccent(1.0);
        setLengthRatio(1.0);
      } else if (data.status === "cancelled") {
        console.log("Accompaniment generation cancelled successfully.");
      }

    } catch (err: any) {
      console.error("Generation failed:", err);
      alert(err.message || "Accompaniment generation failed.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCancelGeneration = async () => {
    try {
      await fetch(`${API_BASE}/api/generate/cancel`, { method: "POST" });
      setIsGenerating(false);
    } catch (err) {
      console.error("Failed to send cancellation request:", err);
    }
  };

  // Dynamic Heuristic post-processing trigger (called on-release of sliders)
  const applyArticulation = async (
    hMs: number,
    vScale: number,
    lenRatio: number
  ) => {
    if (!originalMidiBase64) return;

    const payload = {
      midi_base64: originalMidiBase64, // Always scale from original base to prevent decay degradation
      humanize_ms: hMs,
      velocity_accent_scale: vScale,
      length_ratio: lenRatio,
    };

    try {
      const res = await fetch(`${API_BASE}/api/process/articulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.status === "success") {
        setActiveMidiBase64(data.midi_base64);
      }
    } catch (err) {
      console.error("Post-processing transformation failed:", err);
    }
  };

  const toggleRole = (role: string) => {
    if (selectedRoles.includes(role)) {
      setSelectedRoles(selectedRoles.filter((r) => r !== role));
    } else {
      setSelectedRoles([...selectedRoles, role]);
    }
  };

  // DAW Drag-Out Handle Protocol
  const handleDragStart = (e: React.DragEvent) => {
    if (!activeMidiBase64) return;

    const filename = `${prompt.slice(0, 15).replace(/\s+/g, "_")}_muselocal.mid`;
    const downloadURL = `application/octet-stream:${filename}:data:audio/midi;base64,${activeMidiBase64}`;
    
    e.dataTransfer.setData("DownloadURL", downloadURL);
    e.dataTransfer.effectAllowed = "copy";
  };

  return (
    <div className="min-h-screen bg-[#070709] text-zinc-100 flex flex-col font-sans select-none overflow-x-hidden">
      {/* Sleek Low-Light Header */}
      <header className="border-b border-zinc-900 bg-zinc-950/80 backdrop-blur-md px-8 py-4 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 rounded-lg bg-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <span className="text-[10px] font-black text-black">M</span>
          </div>
          <h1 className="text-sm font-semibold tracking-wide uppercase text-zinc-200">
            MuseLocal <span className="text-zinc-600 font-normal">v1.0.0</span>
          </h1>
        </div>
        <div className="flex items-center gap-2.5">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">
            Local AI Engine: Online
          </span>
        </div>
      </header>

      {/* Main Single-Screen Workspace */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 p-6 max-w-7xl mx-auto w-full">
        {/* Left Input Desk (Column 1-5) */}
        <section className="lg:col-span-5 flex flex-col gap-5">
          {/* Prompt Engine */}
          <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 backdrop-blur-sm flex flex-col gap-4">
            <div className="flex justify-between items-center">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                1. Musical Style Prompt
              </h2>
            </div>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Syncopated neo-soul chord progression, Rhodes style, key of F# minor, 95 BPM"
              className="w-full h-24 bg-zinc-950/80 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-700 resize-none transition-colors duration-200"
            />

            {/* Instrument Role Assignment tags */}
            <div className="flex flex-col gap-2">
              <label className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">
                Accompaniment Roles
              </label>
              <div className="flex flex-wrap gap-2">
                {["bassline", "lead", "counter-melody"].map((role) => (
                  <button
                    key={role}
                    onClick={() => toggleRole(role)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all duration-200 ${
                      selectedRoles.includes(role)
                        ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-400"
                        : "bg-zinc-950/80 border-zinc-800 text-zinc-400 hover:border-zinc-700"
                    }`}
                  >
                    {role.replace("-", " ").toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Ingestion Canvas Block */}
          <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 backdrop-blur-sm flex flex-col gap-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              2. Source Ingestion
            </h2>
            <DragDropCanvas
              onFileLoaded={handleFileDrop}
              isRecording={isRecording}
              onToggleRecording={handleToggleRecording}
              selectedPort={selectedPort}
              portsList={portsList}
              onPortChange={(port) => setSelectedPort(port)}
            />

            {/* Ingestion status badge */}
            <div className="mt-1 flex items-center justify-between text-[10px] font-mono text-zinc-500 px-1 border-t border-zinc-900 pt-3">
              <span>ACTIVE SOURCE:</span>
              <span className="text-zinc-300 font-semibold uppercase">
                {sourceMidiFilename
                  ? `File: ${sourceMidiFilename}`
                  : useCapturedCanvas
                  ? `Captured Baseline (${capturedNotesCount} events)`
                  : "None (Generative Seed Mode)"}
              </span>
            </div>
          </div>

          {/* Synthesis Action Button */}
          <div className="flex gap-3">
            {isGenerating ? (
              <button
                onClick={handleCancelGeneration}
                className="w-full py-3 bg-red-950/20 border border-red-800/40 text-red-400 hover:bg-red-950/40 rounded-xl text-xs font-bold tracking-wider uppercase transition-all duration-200 flex items-center justify-center gap-2"
              >
                <div className="w-1.5 h-1.5 bg-red-400 rounded-full animate-ping" />
                Cancel Generation
              </button>
            ) : (
              <button
                onClick={handleGenerate}
                className="w-full py-3 bg-emerald-500 hover:bg-emerald-600 text-black shadow-lg shadow-emerald-500/10 rounded-xl text-xs font-bold tracking-wider uppercase transition-all duration-200 flex items-center justify-center gap-2"
              >
                Generate Accompaniment
              </button>
            )}
          </div>
        </section>

        {/* Right Output Desk (Column 6-12) */}
        <section className="lg:col-span-7 flex flex-col gap-5">
          {/* Post-Processing Articulation Sliders */}
          <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 backdrop-blur-sm flex flex-col gap-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              3. Heuristic Articulation Dashboard
            </h2>

            <div className="flex flex-col gap-4 mt-1">
              {/* Rhythmic Humanise */}
              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-300">Rhythmic Humanisation</span>
                  <span className="text-emerald-400 font-mono">{humanizeMs} ms</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  disabled={!originalMidiBase64}
                  value={humanizeMs}
                  onChange={(e) => setHumanizeMs(Number(e.target.value))}
                  onMouseUp={() => applyArticulation(humanizeMs, velocityAccent, lengthRatio)}
                  onTouchEnd={() => applyArticulation(humanizeMs, velocityAccent, lengthRatio)}
                  className="w-full accent-emerald-500 h-1.5 bg-zinc-950 border border-zinc-850 rounded-lg cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                />
              </div>

              {/* Velocity accents */}
              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-300">Velocity Accent Scale</span>
                  <span className="text-emerald-400 font-mono">{velocityAccent.toFixed(2)}x</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="1.5"
                  step="0.05"
                  disabled={!originalMidiBase64}
                  value={velocityAccent}
                  onChange={(e) => setVelocityAccent(Number(e.target.value))}
                  onMouseUp={() => applyArticulation(humanizeMs, velocityAccent, lengthRatio)}
                  onTouchEnd={() => applyArticulation(humanizeMs, velocityAccent, lengthRatio)}
                  className="w-full accent-emerald-500 h-1.5 bg-zinc-950 border border-zinc-850 rounded-lg cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                />
              </div>

              {/* Note Length ratios */}
              <div className="flex flex-col gap-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-300">Gate Length Ratio</span>
                  <span className="text-emerald-400 font-mono">
                    {lengthRatio.toFixed(2)}x{" "}
                    <span className="text-[10px] text-zinc-500 ml-1 uppercase">
                      ({lengthRatio < 1.0 ? "Staccato" : lengthRatio > 1.0 ? "Legato" : "Normal"})
                    </span>
                  </span>
                </div>
                <input
                  type="range"
                  min="0.2"
                  max="2.0"
                  step="0.05"
                  disabled={!originalMidiBase64}
                  value={lengthRatio}
                  onChange={(e) => setLengthRatio(Number(e.target.value))}
                  onMouseUp={() => applyArticulation(humanizeMs, velocityAccent, lengthRatio)}
                  onTouchEnd={() => applyArticulation(humanizeMs, velocityAccent, lengthRatio)}
                  className="w-full accent-emerald-500 h-1.5 bg-zinc-950 border border-zinc-850 rounded-lg cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                />
              </div>
            </div>
          </div>

          {/* Timeline lanes */}
          <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 backdrop-blur-sm flex-1 flex flex-col gap-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              4. Track Lane Monitor
            </h2>

            {/* Glowing Tracks visualizer block */}
            <div className="flex-1 min-h-48 bg-zinc-950/80 border border-zinc-900 rounded-lg p-4 flex flex-col gap-3 font-mono text-[10px]">
              {rawTracks ? (
                Object.keys(rawTracks).map((role) => (
                  <div key={role} className="flex flex-col gap-1 border-b border-zinc-900/50 pb-2.5 last:border-0 last:pb-0">
                    <div className="flex justify-between text-zinc-500 font-semibold uppercase text-[9px] mb-1">
                      <span>{role}</span>
                      <span className="text-zinc-400 font-normal">
                        {rawTracks[role].length} synthesized notes
                      </span>
                    </div>
                    {/* Visual note line lane */}
                    <div className="relative w-full h-6 bg-zinc-900/30 rounded border border-zinc-850 overflow-hidden">
                      {rawTracks[role].slice(0, 15).map((note, idx) => (
                        <div
                          key={idx}
                          style={{
                            left: `${(note.start % 4.0) * 25}%`,
                            width: `${Math.max(4, (note.end - note.start) * 20)}%`,
                            opacity: note.velocity / 127,
                          }}
                          className="absolute top-1.5 h-2 bg-emerald-500/80 rounded-sm shadow-[0_0_8px_rgba(16,185,129,0.3)]"
                        />
                      ))}
                    </div>
                  </div>
                ))
              ) : (
                <div className="flex flex-col items-center justify-center flex-1 text-center text-zinc-600 gap-2">
                  <svg
                    className="w-8 h-8 opacity-40 text-zinc-500"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                    />
                  </svg>
                  <span>Active track lane monitors will visualize synthesized structures.</span>
                </div>
              )}
            </div>
          </div>

          {/* Export card with Drag-Out handle */}
          <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-5 backdrop-blur-sm flex flex-col gap-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              5. DAW Timeline Export Desk
            </h2>

            {activeMidiBase64 ? (
              <div
                draggable="true"
                onDragStart={handleDragStart}
                className="w-full bg-zinc-950/90 border-2 border-emerald-500/30 hover:border-emerald-500/70 hover:bg-zinc-950 text-zinc-300 rounded-xl p-4 flex items-center justify-between cursor-grab active:cursor-grabbing transition-all duration-300 shadow-lg shadow-emerald-500/5 group"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 group-hover:scale-105 transition-transform duration-200">
                    <svg
                      className="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                      />
                    </svg>
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-zinc-200">
                      {prompt.slice(0, 18) || "Accompaniment"}.mid
                    </h4>
                    <p className="text-[10px] text-zinc-500 mt-0.5">
                      Type 1 Spec 1.0 MIDI File. Drag directly onto Ableton / DAW tracks.
                    </p>
                  </div>
                </div>
                <div className="text-[10px] bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 px-2 py-1 rounded font-mono uppercase tracking-wider">
                  DRAG ME OUT
                </div>
              </div>
            ) : (
              <div className="w-full bg-zinc-950/40 border border-zinc-900 border-dashed rounded-xl p-4 text-center text-zinc-600 text-xs">
                Awaiting successful AI MIDI generation to activate timeline export handle.
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
