"use client";

import { useState, useCallback, useRef } from "react";
import Link from "next/link";
import {
  Radio,
  RotateCcw,
  Mic2,
  Music,
  Sparkles,
  Waves,
  Users,
  Zap,
  ArrowDown,
  ChevronRight,
  Library,
} from "lucide-react";
import FileUpload from "@/components/FileUpload";
import ProcessingStatus from "@/components/ProcessingStatus";
import AudioPlayer from "@/components/AudioPlayer";

type Stage = "upload" | "processing" | "complete";

function WaveformVisual() {
  const bars = [3, 5, 8, 12, 9, 14, 7, 11, 6, 13, 10, 8, 15, 6, 9, 12, 7, 10, 5, 8];
  return (
    <div className="flex items-end gap-[3px] h-16">
      {bars.map((h, i) => (
        <div
          key={i}
          className="w-1 rounded-full bg-gradient-to-t from-indigo-500 to-violet-400 animate-wave-bar"
          style={{
            height: `${h * 4}px`,
            animationDuration: `${1 + (i % 5) * 0.3}s`,
            animationDelay: `${i * 0.08}s`,
          }}
        />
      ))}
    </div>
  );
}

const features = [
  {
    icon: Users,
    title: "Speaker Separation",
    description:
      "AI-powered diarization splits your podcast into individual speaker tracks for precise control.",
  },
  {
    icon: Sparkles,
    title: "Smart Sound Effects",
    description:
      "Keyword detection triggers contextual sound effects at exactly the right moments.",
  },
  {
    icon: Music,
    title: "Background Music Mixing",
    description:
      "Intelligent audio ducking automatically balances music and speech volumes.",
  },
  {
    icon: Waves,
    title: "Professional Mastering",
    description:
      "Studio-quality output with proper levels, stereo imaging, and broadcast-ready audio.",
  },
];

const steps = [
  {
    number: "01",
    title: "Upload",
    description: "Drop in your AI-generated podcast audio file (WAV or MP3).",
  },
  {
    number: "02",
    title: "Process",
    description: "The engine separates speakers, detects keywords, adds SFX, and mixes background music.",
  },
  {
    number: "03",
    title: "Download",
    description: "Get your professionally mixed radio show, ready for broadcast.",
  },
];

export default function Home() {
  const [stage, setStage] = useState<Stage>("upload");
  const [taskId, setTaskId] = useState<string | null>(null);
  const editorRef = useRef<HTMLDivElement>(null);

  const handleUploadComplete = useCallback((id: string) => {
    setTaskId(id);
    setStage("processing");
  }, []);

  const handleProcessingComplete = useCallback(() => {
    setStage("complete");
  }, []);

  const handleReset = useCallback(() => {
    setStage("upload");
    setTaskId(null);
  }, []);

  const scrollToEditor = () => {
    editorRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div className="min-h-screen">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/5 bg-[#06060b]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10 ring-1 ring-indigo-500/20">
              <Radio className="h-5 w-5 text-indigo-400" />
            </div>
            <span className="text-lg font-semibold text-white">
              Radio Show Editor
            </span>
          </div>
          
          {/* NEW NAV BUTTONS CONTAINER */}
          <div className="flex items-center gap-3 sm:gap-4">
            <Link
              href="/recent"
              className="flex items-center gap-2 rounded-lg border border-gray-800 bg-[#13131A] px-3 py-2 text-sm font-medium text-gray-300 transition-colors hover:border-indigo-500 hover:text-white sm:px-4"
            >
              <Library className="h-4 w-4 text-indigo-400" />
              <span className="hidden sm:inline">My Vault</span>
              <span className="sm:hidden">Vault</span>
            </Link>
            
            <button
              onClick={scrollToEditor}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition btn-glow hover:bg-indigo-500"
            >
              Get Started
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="hero-gradient relative flex min-h-[90vh] flex-col items-center justify-center px-6 pt-20">
        <div className="mx-auto max-w-4xl text-center">
          <div className="animate-fade-up mb-6 inline-flex items-center gap-2 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-4 py-1.5 text-sm text-indigo-300">
            <Zap className="h-3.5 w-3.5" />
            AI-Powered Audio Production
          </div>

          <h1 className="animate-fade-up-delay-1 text-5xl font-extrabold leading-tight tracking-tight text-white sm:text-6xl lg:text-7xl">
            Transform AI Podcasts
            <br />
            <span className="gradient-text">Into Radio Shows</span>
          </h1>

          <p className="animate-fade-up-delay-2 mx-auto mt-6 max-w-2xl text-lg text-gray-400 leading-relaxed">
            Upload a single AI-generated podcast file and get back a
            professionally produced radio show — complete with speaker
            separation, sound effects, and background music.
          </p>

          <div className="animate-fade-up-delay-3 mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <button
              onClick={scrollToEditor}
              className="flex items-center gap-2 rounded-xl bg-indigo-600 px-8 py-3.5 text-base font-semibold text-white transition btn-glow hover:bg-indigo-500"
            >
              <Mic2 className="h-5 w-5" />
              Start Editing
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="animate-fade-up-delay-4 mt-16">
            <WaveformVisual />
          </div>
        </div>

        <button
          onClick={scrollToEditor}
          className="absolute bottom-10 animate-float text-gray-500 transition hover:text-gray-300"
          aria-label="Scroll down"
        >
          <ArrowDown className="h-5 w-5" />
        </button>
      </section>

      {/* Features Section */}
      <section className="relative py-24 px-6">
        <div className="mx-auto max-w-6xl">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-white sm:text-4xl">
              Everything you need for
              <span className="gradient-text"> professional radio</span>
            </h2>
            <p className="mt-4 text-gray-400 max-w-xl mx-auto">
              Powered by AI speaker diarization, intelligent keyword detection,
              and broadcast-grade audio mixing.
            </p>
          </div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="glass-card-hover rounded-2xl p-6"
              >
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-500/10 ring-1 ring-indigo-500/20">
                  <feature.icon className="h-6 w-6 text-indigo-400" />
                </div>
                <h3 className="mb-2 text-lg font-semibold text-white">
                  {feature.title}
                </h3>
                <p className="text-sm text-gray-400 leading-relaxed">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="relative py-24 px-6">
        <div className="mx-auto max-w-4xl">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-white sm:text-4xl">
              How it works
            </h2>
            <p className="mt-4 text-gray-400">
              Three simple steps to your professional radio show.
            </p>
          </div>

          <div className="grid gap-8 sm:grid-cols-3">
            {steps.map((step) => (
              <div key={step.number} className="relative text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500/10 ring-1 ring-indigo-500/20">
                  <span className="text-xl font-bold text-indigo-400">
                    {step.number}
                  </span>
                </div>
                <h3 className="mb-2 text-lg font-semibold text-white">
                  {step.title}
                </h3>
                <p className="text-sm text-gray-400 leading-relaxed">
                  {step.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Editor Section */}
      <section ref={editorRef} className="relative py-24 px-6" id="editor">
        <div className="mx-auto max-w-3xl">
          {/* Section header */}
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold text-white sm:text-4xl">
              Start editing
            </h2>
            <p className="mt-3 text-gray-400">
              Upload your AI-generated podcast to begin.
            </p>
          </div>

          {/* Stage indicator */}
          <div className="mb-10 flex items-center justify-center gap-1">
            {[
              { key: "upload", label: "Upload" },
              { key: "processing", label: "Process" },
              { key: "complete", label: "Listen" },
            ].map((s, i) => {
              const isActive = stage === s.key;
              const stageOrder = ["upload", "processing", "complete"];
              const isCompleted = stageOrder.indexOf(stage) > stageOrder.indexOf(s.key);
              return (
                <div key={s.key} className="flex items-center">
                  {i > 0 && (
                    <div
                      className={`mx-3 h-px w-8 transition-colors duration-300 ${
                        isCompleted ? "bg-indigo-500" : "bg-gray-700"
                      }`}
                    />
                  )}
                  <div className="flex items-center gap-2">
                    <div
                      className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold transition-all duration-300 ${
                        isActive
                          ? "bg-indigo-600 text-white ring-4 ring-indigo-500/20"
                          : isCompleted
                          ? "bg-indigo-600/50 text-indigo-200"
                          : "bg-gray-800 text-gray-500 ring-1 ring-gray-700"
                      }`}
                    >
                      {i + 1}
                    </div>
                    <span
                      className={`text-sm font-medium transition-colors duration-300 ${
                        isActive
                          ? "text-white"
                          : isCompleted
                          ? "text-indigo-300"
                          : "text-gray-500"
                      }`}
                    >
                      {s.label}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Content area */}
          <div className="animate-fade-up">
            {stage === "upload" && (
              <FileUpload onUploadComplete={handleUploadComplete} />
            )}

            {stage === "processing" && taskId && (
              <ProcessingStatus
                taskId={taskId}
                onComplete={handleProcessingComplete}
              />
            )}

            {stage === "complete" && taskId && (
              <div className="flex flex-col items-center gap-6">
                <AudioPlayer taskId={taskId} />
                <button
                  onClick={handleReset}
                  className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm text-gray-400 transition hover:bg-gray-800 hover:text-gray-200"
                >
                  <RotateCcw className="h-4 w-4" />
                  Process another file
                </button>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-12 px-6">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 sm:flex-row">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 ring-1 ring-indigo-500/20">
              <Radio className="h-4 w-4 text-indigo-400" />
            </div>
            <span className="text-sm font-medium text-gray-400">
              Radio Show Editor
            </span>
          </div>
          <p className="text-xs text-gray-600">
            AI-powered audio production. Transform podcasts into radio shows.
          </p>
        </div>
      </footer>
    </div>
  );
}

