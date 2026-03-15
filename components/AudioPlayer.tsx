"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import WaveSurfer from "wavesurfer.js";
import {
  Play,
  Pause,
  Download,
  Volume2,
  VolumeX,
  SkipBack,
  Radio,
  CheckCircle2,
  Loader2,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AudioPlayerProps {
  taskId: string;
}

export default function AudioPlayer({ taskId }: AudioPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState("0:00");
  const [duration, setDuration] = useState("0:00");
  const [volume, setVolume] = useState(0.8);
  const [muted, setMuted] = useState(false);
  const blobUrlRef = useRef<string | null>(null);

  const formatTime = (seconds: number): string => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  useEffect(() => {
    if (!containerRef.current) return;

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "#4f46e5",
      progressColor: "#818cf8",
      cursorColor: "#c7d2fe",
      barWidth: 3,
      barGap: 2,
      barRadius: 4,
      height: 80,
      normalize: true,
    });

    wavesurferRef.current = ws;

    // Fetch audio as blob to avoid CORS issues with WebAudio
    const loadAudio = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await fetch(`${API_BASE}/download/${taskId}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob);
        blobUrlRef.current = blobUrl;

        ws.load(blobUrl);
      } catch (err) {
        setError("Failed to load audio. Please try downloading instead.");
        setLoading(false);
      }
    };

    loadAudio();

    ws.on("ready", () => {
      setReady(true);
      setLoading(false);
      setDuration(formatTime(ws.getDuration()));
      ws.setVolume(0.8);
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

    ws.on("error", (err) => {
      setError("Audio playback error. Please download the file.");
      setLoading(false);
    });

    return () => {
      ws.destroy();
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
      }
    };
  }, [taskId]);

  const togglePlay = useCallback(() => {
    if (!wavesurferRef.current || !ready) return;
    wavesurferRef.current.playPause();
    setPlaying((prev) => !prev);
  }, [ready]);

  const handleRestart = useCallback(() => {
    if (!wavesurferRef.current) return;
    wavesurferRef.current.seekTo(0);
    setCurrentTime("0:00");
  }, []);

  const handleVolumeChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = parseFloat(e.target.value);
      setVolume(val);
      setMuted(val === 0);
      if (wavesurferRef.current) {
        wavesurferRef.current.setVolume(val);
      }
    },
    []
  );

  const toggleMute = useCallback(() => {
    if (!wavesurferRef.current) return;
    if (muted) {
      wavesurferRef.current.setVolume(volume || 0.8);
      setMuted(false);
    } else {
      wavesurferRef.current.setVolume(0);
      setMuted(true);
    }
  }, [muted, volume]);

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
      <div className="glass-card rounded-2xl p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-green-500/10 ring-1 ring-green-500/20">
              <Radio className="h-5 w-5 text-green-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">
                Your Radio Show
              </h2>
              <p className="text-xs text-gray-500">
                Processed and ready to broadcast
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5 rounded-full bg-green-500/10 px-3 py-1 text-xs font-medium text-green-400 ring-1 ring-green-500/20">
            <CheckCircle2 className="h-3 w-3" />
            Ready
          </div>
        </div>

        {/* Waveform */}
        <div
          ref={containerRef}
          className={`rounded-xl bg-surface-50 p-4 ring-1 ring-white/5 transition-opacity duration-500 ${
            ready ? "opacity-100" : "opacity-30"
          }`}
        />

        {/* Loading state */}
        {loading && !error && (
          <div className="mt-3 flex items-center justify-center gap-2 text-xs text-gray-500">
            <Loader2 className="h-3 w-3 animate-spin" />
            Loading audio...
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="mt-3 text-center text-xs text-red-400">{error}</div>
        )}

        {/* Time display */}
        <div className="mt-2 flex justify-between text-xs font-medium text-gray-500">
          <span>{currentTime}</span>
          <span>{duration}</span>
        </div>

        {/* Playback controls */}
        <div className="mt-5 flex items-center justify-center gap-3">
          <button
            onClick={handleRestart}
            disabled={!ready}
            className="flex h-10 w-10 items-center justify-center rounded-xl text-gray-400 transition hover:bg-gray-800 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <SkipBack className="h-4 w-4" />
          </button>

          <button
            onClick={togglePlay}
            disabled={!ready}
            className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-600 text-white transition btn-glow hover:bg-indigo-500 disabled:opacity-30 disabled:cursor-not-allowed disabled:shadow-none"
          >
            {playing ? (
              <Pause className="h-6 w-6" />
            ) : (
              <Play className="h-6 w-6 ml-0.5" />
            )}
          </button>

          <button
            onClick={toggleMute}
            disabled={!ready}
            className="flex h-10 w-10 items-center justify-center rounded-xl text-gray-400 transition hover:bg-gray-800 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
          >
            {muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
          </button>
        </div>

        {/* Volume slider */}
        <div className="mt-4 flex items-center justify-center gap-3">
          <Volume2 className="h-3.5 w-3.5 text-gray-600" />
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={muted ? 0 : volume}
            onChange={handleVolumeChange}
            className="h-1 w-32 appearance-none rounded-full bg-gray-700 accent-indigo-500"
          />
        </div>

        {/* Download button */}
        <div className="mt-6 flex justify-center">
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 rounded-xl bg-gray-800 px-6 py-2.5 text-sm font-medium text-gray-200 ring-1 ring-white/10 transition hover:bg-gray-700 hover:text-white"
          >
            <Download className="h-4 w-4" />
            Download Final Show
          </button>
        </div>
      </div>
    </div>
  );
}
