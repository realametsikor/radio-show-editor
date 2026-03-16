"use client";

import { useEffect, useState, useRef } from "react";
import axios from "axios";
import {
  Loader2,
  CheckCircle2,
  AlertCircle,
  Radio,
  Clock,
  Cpu,
} from "lucide-react";

// Pointing directly to your live Hugging Face backend!
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://realametsikor-radio-show-backend.hf.space";

interface ProcessingStatusProps {
  taskId: string;
  onComplete: () => void;
}

// Honest stages that perfectly match the backend database
const STAGES = [
  { key: "PENDING", label: "Queued", description: "Waiting for an available server...", icon: Clock },
  { key: "PROCESSING", label: "AI Engine Processing", description: "Separating speakers & mixing audio (Takes 5-15 mins on free tier)...", icon: Cpu },
  { key: "SUCCESS", label: "Complete", description: "Your radio show is ready to play!", icon: Radio },
];

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function ProcessingStatus({ taskId, onComplete }: ProcessingStatusProps) {
  const [status, setStatus] = useState("PENDING");
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // 1. THE BULLETPROOF TIMER (Survives closed tabs and sleeping browsers)
  useEffect(() => {
    const storageKey = `timer_start_${taskId}`;
    let startTime = localStorage.getItem(storageKey);

    if (!startTime) {
      startTime = Date.now().toString();
      localStorage.setItem(storageKey, startTime);
    }

    const timerInterval = setInterval(() => {
      // Calculate true time elapsed based on the real-world clock
      setElapsed(Math.floor((Date.now() - parseInt(startTime as string, 10)) / 1000));
    }, 1000);

    return () => clearInterval(timerInterval);
  }, [taskId]);

  // 2. HONEST POLLING (No fake animations, stubborn network retries)
  useEffect(() => {
    const poll = async () => {
      try {
        const response = await axios.get(`${API_BASE}/status/${taskId}`);
        const newStatus = response.data.status;

        setStatus(newStatus);

        if (newStatus === "SUCCESS") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          localStorage.removeItem(`timer_start_${taskId}`); // Cleanup timer
          onComplete(); // Instantly push to the Audio Player
        } else if (newStatus === "FAILURE") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          localStorage.removeItem(`timer_start_${taskId}`);
          setError(response.data.error || "Processing failed. Please try again.");
        }
      } catch (err) {
        console.warn("Network blip while polling. Will retry...", err);
        // We purposely DO NOT clear the interval here. 
        // If the user's Wi-Fi drops temporarily, we just wait for the next tick!
      }
    };

    poll(); // Initial check
    intervalRef.current = setInterval(poll, 3000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [taskId, onComplete]);

  const getDisplayIndex = () => {
    if (status === "PENDING") return 0;
    if (status === "PROCESSING") return 1;
    if (status === "SUCCESS") return 2;
    return 0; // Fallback
  };

  const currentIndex = getDisplayIndex();

  return (
    <div className="w-full max-w-lg mx-auto animate-fade-up">
      <div className="glass-card rounded-2xl p-8 border border-white/5 bg-[#13131A]">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 ring-1 ring-indigo-500/20">
              <Radio className="h-5 w-5 text-indigo-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Processing Your Show</h2>
              <p className="text-xs text-gray-500">True Elapsed Time: {formatElapsed(elapsed)}</p>
            </div>
          </div>
        </div>

        {/* Live progress message */}
        {!error && (
          <div className="mb-6 flex items-center gap-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 px-4 py-3">
            <Loader2 className={`h-5 w-5 flex-shrink-0 text-indigo-400 ${status !== "SUCCESS" ? "animate-spin" : ""}`} />
            <p className="text-sm font-medium text-indigo-300">
              {status === "PENDING" ? "Waiting in queue..." : 
               status === "PROCESSING" ? "Server is actively processing..." : 
               "Finalizing mix..."}
            </p>
          </div>
        )}

        {/* Progress steps */}
        <div className="space-y-2">
          {STAGES.map((stage, index) => {
            const isActive = index === currentIndex;
            const isComplete = index < currentIndex;
            const isPending = index > currentIndex;
            const Icon = stage.icon;

            return (
              <div key={stage.key} className="flex items-start gap-4 relative">
                <div className="flex flex-col items-center">
                  <div className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl transition-all duration-500 ${
                    isComplete ? "bg-green-500/15 ring-1 ring-green-500/30 shadow-[0_0_15px_rgba(34,197,94,0.2)]"
                    : isActive ? "bg-indigo-500/15 ring-1 ring-indigo-500/30 shadow-[0_0_15px_rgba(99,102,241,0.2)]"
                    : "bg-gray-800/50 ring-1 ring-gray-700/50"
                  }`}>
                    {isComplete ? (
                      <CheckCircle2 className="h-5 w-5 text-green-400" />
                    ) : isActive ? (
                      <Loader2 className="h-5 w-5 text-indigo-400 animate-spin" />
                    ) : (
                      <Icon className={`h-5 w-5 ${isPending ? "text-gray-600" : "text-gray-400"}`} />
                    )}
                  </div>
                  {index < STAGES.length - 1 && (
                    <div className={`w-px h-8 transition-colors duration-500 my-1 ${isComplete ? "bg-green-500/40" : "bg-gray-800"}`} />
                  )}
                </div>
                <div className="pt-2 pb-4">
                  <p className={`text-base font-semibold transition-colors duration-300 ${
                    isComplete ? "text-green-400" : isActive ? "text-white" : "text-gray-600"
                  }`}>
                    {stage.label}
                  </p>
                  {(isActive || isComplete) && (
                    <p className="mt-1 text-sm text-gray-500 leading-relaxed max-w-[260px]">{stage.description}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Honest Progress bar */}
        {status !== "SUCCESS" && !error && (
          <div className="mt-4">
            <div className="h-2 w-full overflow-hidden rounded-full bg-gray-800/50 ring-1 ring-white/5">
              <div
                className="relative h-full rounded-full bg-gradient-to-r from-indigo-600 to-violet-500 transition-all duration-1000 ease-out"
                style={{ width: `${Math.min(15 + currentIndex * 40, 95)}%` }}
              >
                <div className="absolute inset-0 h-full w-full animate-pulse rounded-full bg-white/20" />
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-6 flex items-start gap-3 rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-4 text-sm text-red-400">
            <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
            <div className="flex flex-col gap-1">
              <span className="font-semibold text-red-300">Processing Failed</span>
              <span className="opacity-90">{error}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
