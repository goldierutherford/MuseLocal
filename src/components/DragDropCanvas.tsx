"use client";

import React, { useState, useRef } from "react";

interface DragDropCanvasProps {
  onFileLoaded: (midiBase64: string, filename: string) => void;
  isRecording: boolean;
  onToggleRecording: () => void;
  selectedPort: string;
  portsList: string[];
  onPortChange: (portName: string) => void;
}

export default function DragDropCanvas({
  onFileLoaded,
  isRecording,
  onToggleRecording,
  selectedPort,
  portsList,
  onPortChange,
}: DragDropCanvasProps) {
  const [isDragActive, setIsDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragActive(true);
    } else if (e.type === "dragleave") {
      setIsDragActive(false);
    }
  };

  const processMidiFile = (file: File) => {
    if (!file.name.endsWith(".mid") && !file.name.endsWith(".midi")) {
      alert("Invalid file format. Please drop a standard .mid or .midi file.");
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      if (event.target?.result) {
        // Convert to base64
        const resultString = event.target.result as string;
        const base64Data = resultString.split(",")[1] || resultString;
        onFileLoaded(base64Data, file.name);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processMidiFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      processMidiFile(e.target.files[0]);
    }
  };

  return (
    <div className="w-full flex flex-col gap-4">
      {/* File Drop Area */}
      <div
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`relative w-full h-64 border-2 border-dashed rounded-xl flex flex-col items-center justify-center cursor-pointer transition-all duration-300 ${
          isDragActive
            ? "border-emerald-500 bg-emerald-950/10 scale-[0.99]"
            : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-700"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".mid,.midi"
          onChange={handleFileChange}
          className="hidden"
        />

        <div className="flex flex-col items-center text-center px-6">
          {/* Ingestion Canvas Icons / Labels */}
          <div className="w-12 h-12 rounded-full bg-zinc-800/80 flex items-center justify-center mb-4 border border-zinc-700">
            <svg
              className="w-6 h-6 text-zinc-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
              />
            </svg>
          </div>

          <h3 className="text-sm font-medium text-zinc-200">
            Drag & Drop MIDI Timeline
          </h3>
          <p className="text-xs text-zinc-500 mt-1 max-w-xs">
            Supports Standard MIDI format 0 and 1. Click to browse files locally.
          </p>
        </div>
      </div>

      {/* Real-time Hardware Ingestion Tray */}
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          {/* Pulse recording ring */}
          <div
            className={`w-3.5 h-3.5 rounded-full ${
              isRecording
                ? "bg-red-500 animate-pulse ring-4 ring-red-500/20"
                : "bg-zinc-700"
            }`}
          />
          <div>
            <h4 className="text-xs font-semibold text-zinc-300">
              {isRecording ? "Live MIDI Ingestion Active" : "Hardware Port Offline"}
            </h4>
            <p className="text-[10px] text-zinc-500 mt-0.5">
              {isRecording
                ? "Capturing MIDI packets sequentially in memory cache..."
                : "Awaiting physical hardware MIDI triggers..."}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Port Selector */}
          <select
            disabled={isRecording}
            value={selectedPort}
            onChange={(e) => onPortChange(e.target.value)}
            className="bg-zinc-800/80 border border-zinc-700 text-zinc-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-zinc-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {portsList.length === 0 ? (
              <option value="">No hardware inputs detected</option>
            ) : (
              portsList.map((port, idx) => (
                <option key={idx} value={port}>
                  {port}
                </option>
              ))
            )}
          </select>

          {/* Capture Trigger */}
          <button
            onClick={onToggleRecording}
            className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
              isRecording
                ? "bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-900/20"
                : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700"
            }`}
          >
            {isRecording ? "Stop Capture" : "Arm Capture"}
          </button>
        </div>
      </div>
    </div>
  );
}
