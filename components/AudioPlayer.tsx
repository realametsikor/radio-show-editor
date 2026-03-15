"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  Play, Pause, Download, Volume2, VolumeX,
  SkipBack, Radio, CheckCircle2, Loader2,
  FileText, ChevronDown, Clock, Tag,
  Sparkles, Music, Share2,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Highlight {
  start: number;
  end: number;
  title: string;
  reason: string;
}

interface Segment {
  start: number;
  end: number;
  title: string;
  type: string;
  description: string;
}

interface ShowMetadata {
  show_title: string;
  show_tagline: string;
  show_summary: string;
  keywords: string[];
  segments: Segment[];
  highlights: Highlight[];
  production_notes: string;
  mood: string;
}

interface AudioPlayerProps {
  taskId: string;
}

const FORMAT_OPTIONS = [
  {
    value: "mp3",
    label: "MP3 Standard",
    desc: "~40MB · Best for sharing",
    icon: "🎵",
  },
  {
    value: "mp3_high",
    label: "MP3 High Quality",
    desc: "~80MB · 320kbps",
    icon: "🎧",
  },
  {
    value: "mp3_low",
    label: "MP3 Small Size",
    desc: "~15MB · 96kbps",
    icon: "📱",
  },
  {
    value: "wav",
    label: "WAV Lossless",
    desc: "~300MB · Studio quality",
    icon: "🏆",
  },
];

export default function AudioPlayer({ taskId }: AudioPlayerProps) {
  const audioRef                        = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying]           = useState(false);
  const [ready, setReady]               = useState(false);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState<string | null>(null);
  const [currentTime, setCurrentTime]   = useState(0);
  const [duration, setDuration]         = useState(0);
  const [volume, setVolume]             = useState(0.8);
  const [muted, setMuted]               = useState(false);
  const [blobUrl, setBlobUrl]           = useState<string | null>(null);
  const blobUrlRef                      = useRef<string | null>(null);

  // UI state
  const [activeTab, setActiveTab]       = useState<"player" | "notes" | "highlights">("player");
  const [showFormats, setShowFormats]   = useState(false);
  const [metadata, setMetadata]         = useState<ShowMetadata | null>(null);
  const [loadingMeta, setLoadingMeta]   = useState(true);

  const formatTime = (s: number): string => {
    if (!s || isNaN(s)) return "0:00";
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  // Load audio blob
  useEffect(() => {
    let url: string | null = null;
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch(`${API_BASE}/download/${taskId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        if (blob.size === 0) throw new Error("Empty file");
        url = URL.createObjectURL(blob);
        blobUrlRef.current = url;
        setBlobUrl(url);
      } catch (err: any) {
        setError("Failed to load audio. Try downloading instead.");
        setLoading(false);
      }
    };
    load();
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [taskId]);

  // Load metadata
  useEffect(() => {
    const loadMeta = async () => {
      try {
        setLoadingMeta(true);
        const res = await fetch(`${API_BASE}/metadata/${taskId}`);
        if (res.ok) {
          const data = await res.json();
          setMetadata(data);
        }
      } catch {
        // metadata is optional
      } finally {
        setLoadingMeta(false);
      }
    };
    loadMeta();
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
      } catch {
        setError("Tap play to start.");
      }
    }
  }, [playing, ready]);

  const handleRestart = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.currentTime = 0;
      setCurrentTime(0);
    }
  }, []);

  const seekTo = useCallback((seconds: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = seconds;
      setCurrentTime(seconds);
    }
  }, []);

  const handleVolumeChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = parseFloat(e.target.value);
      setVolume(val);
      setMuted(val === 0);
      if (audioRef.current) audioRef.current.volume = val;
    }, []
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

  const handleDownload = useCallback((format: string = "mp3") => {
    const url  = format === "mp3"
      ? `${API_BASE}/download/${taskId}`
      : `${API_BASE}/download/${taskId}/${format}`;
    const link = document.createElement("a");
    link.href  = url;
    link.download = `radio_show_final.${format.startsWith("mp3") ? "mp3" : format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setShowFormats(false);
  }, [taskId]);

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="w-full max-w-2xl mx-auto">
      {blobUrl && (
        <audio
          ref={audioRef}
          src={blobUrl}
          preload="auto"
          onCanPlayThrough={() => { setReady(true); setLoading(false); }}
          onTimeUpdate={() => setCurrentTime(audioRef.current?.currentTime || 0)}
          onDurationChange={() => setDuration(audioRef.current?.duration || 0)}
          onEnded={() => setPlaying(false)}
          onError={() => { setError("Playback error. Try downloading."); setLoading(false); }}
        />
      )}

      <div className="glass-card rounded-2xl overflow-hidden">

        {/* Show Branding Header */}
        <div className="bg-gradient-to-r from-indigo-900/50 to-violet-900/50 px-6 pt-6 pb-4 border-b border-white/5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-green-500/15 ring-1 ring-green-500/25">
                <Radio className="h-5 w-5 text-green-400" />
              </div>
              <div>
                {loadingMeta ? (
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-3 w-3 animate-spin text-gray-500" />
                    <span className="text-xs text-gray-500">Loading show info...</span>
                  </div>
                ) : (
                  <>
                    <h2 className="text-lg font-bold text-white leading-tight">
                      {metadata?.show_title || "Your Radio Show"}
                    </h2>
                    {metadata?.show_tagline && (
                      <p className="text-xs text-indigo-300 mt-0.5 italic">
                        {metadata.show_tagline}
                      </p>
                    )}
                  </>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1.5 rounded-full bg-green-500/10 px-3 py-1 text-xs font-medium text-green-400 ring-1 ring-green-500/20 shrink-0">
              <CheckCircle2 className="h-3 w-3" />
              Ready
            </div>
          </div>

          {/* Keywords */}
          {metadata?.keywords && metadata.keywords.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {metadata.keywords.slice(0, 5).map((kw) => (
                <span
                  key={kw}
                  className="flex items-center gap-1 rounded-full bg-white/5 px-2.5 py-0.5 text-xs text-gray-400 ring-1 ring-white/10"
                >
                  <Tag className="h-2.5 w-2.5" />
                  {kw}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Tabs */}
        <div className="flex border-b border-white/5">
          {[
            { key: "player",     label: "Player",     icon: Music },
            { key: "notes",      label: "Show Notes", icon: FileText },
            { key: "highlights", label: "Highlights", icon: Sparkles },
          ].map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key as any)}
              className={`flex flex-1 items-center justify-center gap-1.5 py-3 text-xs font-medium transition-colors ${
                activeTab === key
                  ? "border-b-2 border-indigo-500 text-indigo-400"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>

        <div className="p-6">

          {/* ── PLAYER TAB ── */}
          {activeTab === "player" && (
            <>
              {/* Progress bar */}
              <div className="rounded-xl bg-gray-900/80 p-4 ring-1 ring-white/5">
                {loading && (
                  <div className="flex items-center justify-center gap-2 py-5 text-xs text-gray-500">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading audio...
                  </div>
                )}
                {!loading && !error && (
                  <div
                    className="relative h-2 w-full cursor-pointer rounded-full bg-gray-700"
                    onClick={(e) => {
                      const rect = e.currentTarget.getBoundingClientRect();
                      seekTo((e.clientX - rect.left) / rect.width * duration);
                    }}
                  >
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-100"
                      style={{ width: `${progress}%` }}
                    />
                    <div
                      className="absolute top-1/2 -translate-y-1/2 h-4 w-4 rounded-full bg-white shadow-lg transition-all duration-100"
                      style={{ left: `calc(${progress}% - 8px)` }}
                    />
                  </div>
                )}
                {error && (
                  <p className="py-3 text-center text-xs text-red-400">{error}</p>
                )}
              </div>

              {/* Time */}
              <div className="mt-2 flex justify-between text-xs text-gray-500">
                <span>{formatTime(currentTime)}</span>
                <span>{formatTime(duration)}</span>
              </div>

              {/* Controls */}
              <div className="mt-4 flex items-center justify-center gap-3">
                <button
                  onClick={handleRestart}
                  disabled={!ready}
                  className="flex h-10 w-10 items-center justify-center rounded-xl text-gray-400 hover:bg-gray-800 hover:text-white disabled:opacity-30"
                >
                  <SkipBack className="h-4 w-4" />
                </button>
                <button
                  onClick={togglePlay}
                  disabled={!ready}
                  className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-600 text-white btn-glow hover:bg-indigo-500 disabled:opacity-30"
                >
                  {playing
                    ? <Pause className="h-6 w-6" />
                    : <Play className="h-6 w-6 ml-0.5" />
                  }
                </button>
                <button
                  onClick={toggleMute}
                  disabled={!ready}
                  className="flex h-10 w-10 items-center justify-center rounded-xl text-gray-400 hover:bg-gray-800 hover:text-white disabled:opacity-30"
                >
                  {muted
                    ? <VolumeX className="h-4 w-4" />
                    : <Volume2 className="h-4 w-4" />
                  }
                </button>
              </div>

              {/* Volume */}
              <div className="mt-4 flex items-center justify-center gap-3">
                <Volume2 className="h-3.5 w-3.5 text-gray-600" />
                <input
                  type="range" min="0" max="1" step="0.01"
                  value={muted ? 0 : volume}
                  onChange={handleVolumeChange}
                  className="h-1 w-32 appearance-none rounded-full bg-gray-700 accent-indigo-500"
                />
              </div>

              {/* Download with format picker */}
              <div className="mt-6 relative">
                <div className="flex rounded-xl overflow-hidden ring-1 ring-white/10">
                  <button
                    onClick={() => handleDownload("mp3")}
                    className="flex flex-1 items-center justify-center gap-2 bg-gray-800 py-2.5 text-sm font-medium text-gray-200 hover:bg-gray-700 hover:text-white transition-colors"
                  >
                    <Download className="h-4 w-4" />
                    Download MP3
                  </button>
                  <div className="w-px bg-white/10" />
                  <button
                    onClick={() => setShowFormats(!showFormats)}
                    className="flex items-center justify-center bg-gray-800 px-3 hover:bg-gray-700 transition-colors"
                  >
                    <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${showFormats ? "rotate-180" : ""}`} />
                  </button>
                </div>

                {/* Format dropdown */}
                {showFormats && (
                  <div className="absolute bottom-full mb-2 left-0 right-0 rounded-xl bg-gray-800 ring-1 ring-white/10 overflow-hidden z-10">
                    {FORMAT_OPTIONS.map((fmt) => (
                      <button
                        key={fmt.value}
                        onClick={() => handleDownload(fmt.value)}
                        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-gray-700 transition-colors border-b border-white/5 last:border-0"
                      >
                        <span className="text-lg">{fmt.icon}</span>
                        <div>
                          <p className="text-sm font-medium text-white">{fmt.label}</p>
                          <p className="text-xs text-gray-500">{fmt.desc}</p>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}

          {/* ── SHOW NOTES TAB ── */}
          {activeTab === "notes" && (
            <div className="space-y-5">
              {loadingMeta ? (
                <div className="flex items-center justify-center py-8 gap-2 text-gray-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">Loading show notes...</span>
                </div>
              ) : metadata ? (
                <>
                  {/* Summary */}
                  {metadata.show_summary && (
                    <div className="rounded-xl bg-indigo-500/10 border border-indigo-500/20 p-4">
                      <h3 className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-2">
                        Episode Summary
                      </h3>
                      <p className="text-sm text-gray-300 leading-relaxed">
                        {metadata.show_summary}
                      </p>
                    </div>
                  )}

                  {/* Segments */}
                  {metadata.segments && metadata.segments.length > 0 && (
                    <div>
                      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                        Show Segments
                      </h3>
                      <div className="space-y-2">
                        {metadata.segments.map((seg, i) => (
                          <button
                            key={i}
                            onClick={() => {
                              seekTo(seg.start);
                              setActiveTab("player");
                            }}
                            className="flex w-full items-start gap-3 rounded-xl bg-white/5 p-3 text-left hover:bg-white/10 transition-colors ring-1 ring-white/5"
                          >
                            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-500/20 text-xs font-bold text-indigo-400">
                              {i + 1}
                            </div>
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-white truncate">
                                {seg.title}
                              </p>
                              <div className="flex items-center gap-2 mt-0.5">
                                <Clock className="h-3 w-3 text-gray-600" />
                                <span className="text-xs text-gray-500">
                                  {formatTime(seg.start)} — {formatTime(seg.end)}
                                </span>
                              </div>
                              {seg.description && (
                                <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                                  {seg.description}
                                </p>
                              )}
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Production notes */}
                  {metadata.production_notes && (
                    <div className="rounded-xl bg-white/5 p-4 ring-1 ring-white/5">
                      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                        Producer Notes
                      </h3>
                      <p className="text-xs text-gray-500 leading-relaxed italic">
                        {metadata.production_notes}
                      </p>
                    </div>
                  )}

                  {!metadata.show_summary && !metadata.segments?.length && (
                    <div className="py-8 text-center text-sm text-gray-500">
                      No show notes available for this episode.
                    </div>
                  )}
                </>
              ) : (
                <div className="py-8 text-center text-sm text-gray-500">
                  Could not load show notes.
                </div>
              )}
            </div>
          )}

          {/* ── HIGHLIGHTS TAB ── */}
          {activeTab === "highlights" && (
            <div className="space-y-4">
              {loadingMeta ? (
                <div className="flex items-center justify-center py-8 gap-2 text-gray-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">Loading highlights...</span>
                </div>
              ) : metadata?.highlights && metadata.highlights.length > 0 ? (
                <>
                  <p className="text-xs text-gray-500">
                    AI-identified best moments — tap to jump to that moment
                  </p>
                  {metadata.highlights.map((h, i) => (
                    <div
                      key={i}
                      className="rounded-xl bg-white/5 ring-1 ring-white/5 overflow-hidden"
                    >
                      <div className="p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-lg">
                                {i === 0 ? "🥇" : i === 1 ? "🥈" : "🥉"}
                              </span>
                              <h3 className="text-sm font-semibold text-white">
                                {h.title}
                              </h3>
                            </div>
                            <p className="text-xs text-gray-500 leading-relaxed">
                              {h.reason}
                            </p>
                            <div className="flex items-center gap-1.5 mt-2">
                              <Clock className="h-3 w-3 text-gray-600" />
                              <span className="text-xs text-gray-500">
                                {formatTime(h.start)} — {formatTime(h.end)}
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="flex gap-2 mt-3">
                          <button
                            onClick={() => {
                              seekTo(h.start);
                              setActiveTab("player");
                            }}
                            className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-indigo-600/80 py-2 text-xs font-medium text-white hover:bg-indigo-500 transition-colors"
                          >
                            <Play className="h-3 w-3" />
                            Play Clip
                          </button>
                          <button
                            onClick={() => {
                              const url = `${API_BASE}/download/${taskId}/mp3_low`;
                              const link = document.createElement("a");
                              link.href = url;
                              link.download = `highlight_${i + 1}.mp3`;
                              link.click();
                            }}
                            className="flex items-center justify-center gap-1.5 rounded-lg bg-gray-700 px-3 py-2 text-xs font-medium text-gray-300 hover:bg-gray-600 transition-colors"
                          >
                            <Share2 className="h-3 w-3" />
                            Share
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </>
              ) : (
                <div className="py-8 text-center">
                  <Sparkles className="h-8 w-8 text-gray-700 mx-auto mb-3" />
                  <p className="text-sm text-gray-500">
                    No highlights found for this episode.
                  </p>
                  <p className="text-xs text-gray-600 mt-1">
                    Highlights are identified by Claude AI during processing.
                  </p>
                </div>
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
