"use client";

import { useEffect, useRef, useState, useCallback } from "react";
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
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.8);
  const [muted, setMuted] = useState(false);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const blobUrlRef = useRef<string | null>(null);

  const formatTime = (seconds: number): string => {
    if (!seconds || isNaN(seconds)) return "0:00";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  useEffect(() => {
    let objectUrl: string | null = null;

    const loadAudio = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await fetch(`${API_BASE}/download/${taskId}`);
        if (!response.ok) {
          const text = await response.text();
          throw new Error(`HTTP ${response.status}: ${text}`);
        }

        const contentLength = response.headers.get("content-length");
        if (contentLength && parseInt(contentLength) === 0) {
          throw new Error("Empty file received from server");
        }

        const blob = await response.blob();
        if (blob.size === 0) {
          throw new Error("Downloaded file is empty");
        }

        objectUrl = URL.createObjectURL(blob);
        blobUrlRef.current = objectUrl;
        setBlobUrl(objectUrl);
        setError(null);
      } catch (err: any) {
        console.error("Audio load error:", err);
        setError("Failed to load audio. Try downloading instead.");
        setLoading(false);
      }
    };

    loadAudio();

    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [taskId]);

  const togglePlay = useCallback(async () => {
    const audio = audioRef.current;
    if (!audio || !ready) return;
    if (playing) {
      audio.pause();
      setPlaying(false);
    } else {
      try {
        await audio.play();
        setPlaying(true);
      } catch (err) {
        setError("Playback blocked. Tap play again.");
      }
    }
  }, [playing, ready]);

  const handleRestart = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = 0;
    setCurrentTime(0);
  }, []);

  const handleVolumeChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = parseFloat(e.target.value);
      setVolume(val);
      setMuted(val === 0);
      if (audioRef.current) audioRef.current.volume = val;
    },
    []
  );

  const toggleMute = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (muted) {
      audio.volume = volume || 0.8;
      setMuted(false);
    } else {
      audio.volume = 0;
      setMuted(true);
    }
  }, [muted, volume]);

  const handleDownload = useCallback(() => {
    const link = document.createElement("a");
    link.href = `${API_BASE}/download/${taskId}`;
    link.download = "radio_show_final.mp3";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [taskId]);

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="w-full max-w-2xl mx-auto">
      {blobUrl && (
        <audio
          ref={audioRef}
          src={blobUrl}
          preload="auto"
          onCanPlayThrough={() => {
            setReady(true);
            setLoading(false);
          }}
          onTimeUpdate={() =>
            setCurrentTime(audioRef.current?.currentTime || 0)
          }
          onDurationChange={() =>
            setDuration(audioRef.current?.duration || 0)
          }
          onEnded={() => setPlaying(false)}
          onError={() => {
            setError("Playback error. Please download the file.");
            setLoading(false);
          }}
        />
      )}

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

        {/* Progress bar */}
        <div className="rounded-xl bg-gray-900 p-4 ring-1 ring-white/5">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-6 text-xs text-gray-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading audio...
            </div>
          )}

          {!loading && !error && (
            <div
              className="relative h-2 w-full cursor-pointer rounded-full bg-gray-700"
              onClick={(e) => {
                const rect = e.currentTarget.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const pct = x / rect.width;
                if (audioRef.current) {
                  audioRef.current.currentTime = pct * duration;
                }
              }}
            >
              <div
                className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-100"
                style={{ width: `${progress}%` }}
              />
              <div
                className="absolute top-1/2 -translate-y-1/2 h-4 w-4 rounded-full bg-indigo-400 shadow-lg transition-all duration-100"
                style={{ left: `calc(${progress}% - 8px)` }}
              />
            </div>
          )}

          {error && (
            <p className="py-4 text-center text-xs text-red-400">{error}</p>
          )}
        </div>

        {/* Time display */}
        <div className="mt-2 flex justify-between text-xs font-medium text-gray-500">
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(duration)}</span>
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
            className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-600 text-white transition btn-glow hover:bg-indigo-500 disabled:opacity-30 disabled:cursor-not-allowed"
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
            {muted ? (
              <VolumeX className="h-4 w-4" />
            ) : (
              <Volume2 className="h-4 w-4" />
            )}
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
            Download MP3
          </button>
        </div>
      </div>
    </div>
  );
}
