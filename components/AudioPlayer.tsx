"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import WaveSurfer from "wavesurfer.js";
import { Play, Pause, Download, Volume2 } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AudioPlayerProps {
  taskId: string;
}

export default function AudioPlayer({ taskId }: AudioPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const [currentTime, setCurrentTime] = useState("0:00");
  const [duration, setDuration] = useState("0:00");

  const formatTime = (seconds: number): string => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  useEffect(() => {
    if (!containerRef.current) return;

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "#6366f1",
      progressColor: "#a78bfa",
      cursorColor: "#c7d2fe",
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      height: 100,
      normalize: true,
      backend: "WebAudio",
    });

    ws.load(`${API_BASE}/download/${taskId}`);

    ws.on("ready", () => {
      setReady(true);
      setDuration(formatTime(ws.getDuration()));
    });

    ws.on("audioprocess", () => {
      setCurrentTime(formatTime(ws.getCurrentTime()));
    });

    ws.on("seeking", () => {
      setCurrentTime(formatTime(ws.getCurrentTime()));
    });

    ws.on("finish", () => {
      setPlaying(false);
    });

    wavesurferRef.current = ws;

    return () => {
      ws.destroy();
    };
  }, [taskId]);

  const togglePlay = useCallback(() => {
    if (!wavesurferRef.current) return;
    wavesurferRef.current.playPause();
    setPlaying((prev) => !prev);
  }, []);

  const handleDownload = useCallback(() => {
    const link = document.createElement("a");
    link.href = `${API_BASE}/download/${taskId}`;
    link.download = "radio_show_final.wav";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [taskId]);

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="rounded-2xl border border-gray-700 bg-gray-800/50 p-8">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <Volume2 className="h-6 w-6 text-indigo-400" />
          <h2 className="text-xl font-semibold text-white">Your Radio Show</h2>
        </div>

        {/* Waveform */}
        <div
          ref={containerRef}
          className={`rounded-xl bg-gray-900/60 p-4 transition-opacity ${
            ready ? "opacity-100" : "opacity-40"
          }`}
        />

        {/* Time display */}
        <div className="mt-3 flex justify-between text-xs text-gray-400">
          <span>{currentTime}</span>
          <span>{duration}</span>
        </div>

        {/* Controls */}
        <div className="mt-6 flex items-center justify-center gap-4">
          <button
            onClick={togglePlay}
            disabled={!ready}
            className="flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600 text-white transition hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-gray-900 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {playing ? (
              <Pause className="h-6 w-6" />
            ) : (
              <Play className="h-6 w-6 ml-0.5" />
            )}
          </button>
        </div>

        {/* Download button */}
        <div className="mt-6 flex justify-center">
          <button
            onClick={handleDownload}
            disabled={!ready}
            className="flex items-center gap-2 rounded-lg bg-gray-700 px-5 py-2.5 text-sm font-medium text-gray-200 transition hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 focus:ring-offset-gray-900 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Download className="h-4 w-4" />
            Download Final Show
          </button>
        </div>
      </div>
    </div>
  );
}
