"use client";

import { useEffect, useState, useRef } from "react";
import axios from "axios";
import { Loader2, CheckCircle2, AlertCircle, Radio } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ProcessingStatusProps {
  taskId: string;
  onComplete: () => void;
}

const STAGES = [
  { key: "PENDING", label: "Queued", description: "Waiting for an available worker..." },
  { key: "PROCESSING", label: "Processing", description: "Analyzing speakers & mixing audio..." },
  { key: "SUCCESS", label: "Complete", description: "Your radio show is ready!" },
];

export default function ProcessingStatus({ taskId, onComplete }: ProcessingStatusProps) {
  const [status, setStatus] = useState("PENDING");
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const response = await axios.get(`${API_BASE}/status/${taskId}`);
        const newStatus = response.data.status;
        setStatus(newStatus);

        if (newStatus === "SUCCESS") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          onComplete();
        } else if (newStatus === "FAILURE") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setError(response.data.error || "Processing failed. Please try again.");
        }
      } catch {
        if (intervalRef.current) clearInterval(intervalRef.current);
        setError("Lost connection to the server.");
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 3000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [taskId, onComplete]);

  const currentIndex = STAGES.findIndex((s) => s.key === status);

  return (
    <div className="w-full max-w-lg mx-auto">
      <div className="rounded-2xl border border-gray-700 bg-gray-800/50 p-8">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Radio className="h-6 w-6 text-indigo-400" />
          <h2 className="text-xl font-semibold text-white">Processing Your Show</h2>
        </div>

        {/* Progress steps */}
        <div className="space-y-6">
          {STAGES.map((stage, index) => {
            const isActive = stage.key === status;
            const isComplete = index < currentIndex || status === "SUCCESS";
            const isPending = index > currentIndex;

            return (
              <div key={stage.key} className="flex items-start gap-4">
                {/* Icon */}
                <div className="flex-shrink-0 mt-0.5">
                  {isComplete ? (
                    <CheckCircle2 className="h-6 w-6 text-green-400" />
                  ) : isActive ? (
                    <Loader2 className="h-6 w-6 text-indigo-400 animate-spin" />
                  ) : (
                    <div className="h-6 w-6 rounded-full border-2 border-gray-600" />
                  )}
                </div>

                {/* Text */}
                <div>
                  <p
                    className={`font-medium ${
                      isComplete
                        ? "text-green-400"
                        : isActive
                        ? "text-white"
                        : "text-gray-500"
                    }`}
                  >
                    {stage.label}
                  </p>
                  <p
                    className={`text-sm ${
                      isPending ? "text-gray-600" : "text-gray-400"
                    }`}
                  >
                    {stage.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Animated progress bar */}
        {status !== "SUCCESS" && !error && (
          <div className="mt-8">
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-700">
              <div className="h-full animate-pulse rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-500"
                style={{ width: status === "PENDING" ? "30%" : "70%" }}
              />
            </div>
            <p className="mt-3 text-center text-xs text-gray-500">
              Task ID: {taskId}
            </p>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="mt-6 flex items-center gap-2 rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-400">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
