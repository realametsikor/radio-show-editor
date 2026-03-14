"use client";

import { useEffect, useState, useRef } from "react";
import axios from "axios";
import {
  Loader2,
  CheckCircle2,
  AlertCircle,
  Users,
  Sparkles,
  Music,
  Radio,
  Clock,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ProcessingStatusProps {
  taskId: string;
  onComplete: () => void;
}

const STAGES = [
  {
    key: "PENDING",
    label: "Queued",
    description: "Waiting for an available worker...",
    icon: Clock,
  },
  {
    key: "PROCESSING",
    label: "Separating Speakers",
    description: "AI is identifying and isolating individual voices...",
    icon: Users,
  },
  {
    key: "PROCESSING_SFX",
    label: "Adding Sound Effects",
    description: "Detecting keywords and overlaying contextual SFX...",
    icon: Sparkles,
  },
  {
    key: "PROCESSING_MIX",
    label: "Mixing & Mastering",
    description: "Blending background music with intelligent ducking...",
    icon: Music,
  },
  {
    key: "SUCCESS",
    label: "Complete",
    description: "Your radio show is ready to play!",
    icon: Radio,
  },
];

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function ProcessingStatus({
  taskId,
  onComplete,
}: ProcessingStatusProps) {
  const [status, setStatus] = useState("PENDING");
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Simulate detailed sub-stages for PROCESSING since the backend only reports PROCESSING
  const [visualStage, setVisualStage] = useState(0);

  useEffect(() => {
    timerRef.current = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  useEffect(() => {
    const poll = async () => {
      try {
        const response = await axios.get(`${API_BASE}/status/${taskId}`);
        const newStatus = response.data.status;
        setStatus(newStatus);

        if (newStatus === "PROCESSING" && visualStage === 0) {
          setVisualStage(1);
          // Simulate sub-stage progression for visual feedback
          setTimeout(() => setVisualStage(2), 8000);
          setTimeout(() => setVisualStage(3), 16000);
        }

        if (newStatus === "SUCCESS") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          if (timerRef.current) clearInterval(timerRef.current);
          setVisualStage(4);
          onComplete();
        } else if (newStatus === "FAILURE") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          if (timerRef.current) clearInterval(timerRef.current);
          setError(
            response.data.error || "Processing failed. Please try again."
          );
        }
      } catch {
        if (intervalRef.current) clearInterval(intervalRef.current);
        if (timerRef.current) clearInterval(timerRef.current);
        setError("Lost connection to the server.");
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 3000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [taskId, onComplete, visualStage]);

  // Map visual stage to the display
  const getDisplayIndex = () => {
    if (status === "PENDING") return 0;
    if (status === "SUCCESS") return 4;
    return Math.max(1, visualStage);
  };

  const currentIndex = getDisplayIndex();

  return (
    <div className="w-full max-w-lg mx-auto">
      <div className="glass-card rounded-2xl p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 ring-1 ring-indigo-500/20">
              <Radio className="h-5 w-5 text-indigo-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">
                Processing Your Show
              </h2>
              <p className="text-xs text-gray-500">
                Elapsed: {formatElapsed(elapsed)}
              </p>
            </div>
          </div>
        </div>

        {/* Progress steps */}
        <div className="space-y-1">
          {STAGES.map((stage, index) => {
            const isActive = index === currentIndex;
            const isComplete = index < currentIndex;
            const isPending = index > currentIndex;
            const Icon = stage.icon;

            return (
              <div key={stage.key} className="flex items-start gap-4">
                {/* Timeline rail */}
                <div className="flex flex-col items-center">
                  <div
                    className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl transition-all duration-500 ${
                      isComplete
                        ? "bg-green-500/15 ring-1 ring-green-500/30"
                        : isActive
                        ? "bg-indigo-500/15 ring-1 ring-indigo-500/30"
                        : "bg-gray-800/50 ring-1 ring-gray-700/50"
                    }`}
                  >
                    {isComplete ? (
                      <CheckCircle2 className="h-4.5 w-4.5 text-green-400" />
                    ) : isActive ? (
                      <Loader2 className="h-4.5 w-4.5 text-indigo-400 animate-spin" />
                    ) : (
                      <Icon
                        className={`h-4 w-4 ${
                          isPending ? "text-gray-600" : "text-gray-400"
                        }`}
                      />
                    )}
                  </div>
                  {index < STAGES.length - 1 && (
                    <div
                      className={`w-px h-5 transition-colors duration-500 ${
                        isComplete ? "bg-green-500/30" : "bg-gray-800"
                      }`}
                    />
                  )}
                </div>

                {/* Text */}
                <div className="pt-1.5 pb-3">
                  <p
                    className={`text-sm font-medium transition-colors duration-300 ${
                      isComplete
                        ? "text-green-400"
                        : isActive
                        ? "text-white"
                        : "text-gray-600"
                    }`}
                  >
                    {stage.label}
                  </p>
                  {(isActive || isComplete) && (
                    <p className="mt-0.5 text-xs text-gray-500">
                      {stage.description}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Animated progress bar */}
        {status !== "SUCCESS" && !error && (
          <div className="mt-6">
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-800">
              <div
                className="relative h-full rounded-full bg-gradient-to-r from-indigo-500 via-violet-500 to-indigo-500 transition-all duration-1000 ease-out"
                style={{
                  width: `${Math.min(15 + currentIndex * 22, 90)}%`,
                }}
              >
                <div className="absolute inset-0 h-full w-1/2 animate-shimmer rounded-full bg-gradient-to-r from-transparent via-white/20 to-transparent" />
              </div>
            </div>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="mt-6 flex items-center gap-2.5 rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
