"use client";

import { useState, useCallback } from "react";
import { Radio, RotateCcw } from "lucide-react";
import FileUpload from "@/components/FileUpload";
import ProcessingStatus from "@/components/ProcessingStatus";
import AudioPlayer from "@/components/AudioPlayer";

type Stage = "upload" | "processing" | "complete";

export default function Home() {
  const [stage, setStage] = useState<Stage>("upload");
  const [taskId, setTaskId] = useState<string | null>(null);

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

  return (
    <main className="flex min-h-screen flex-col items-center px-4 py-16">
      {/* Header */}
      <div className="mb-12 text-center">
        <div className="mb-4 flex items-center justify-center gap-3">
          <Radio className="h-10 w-10 text-indigo-400" />
          <h1 className="text-4xl font-bold tracking-tight text-white">
            Radio Show Editor
          </h1>
        </div>
        <p className="max-w-md text-gray-400">
          Upload your AI-generated podcast and get a professionally mixed radio
          show with separated speakers, sound effects, and background music.
        </p>
      </div>

      {/* Stage indicator */}
      <div className="mb-10 flex items-center gap-2 text-sm text-gray-500">
        <span className={stage === "upload" ? "text-indigo-400 font-medium" : "text-gray-500"}>
          Upload
        </span>
        <span className="text-gray-700">/</span>
        <span className={stage === "processing" ? "text-indigo-400 font-medium" : "text-gray-500"}>
          Process
        </span>
        <span className="text-gray-700">/</span>
        <span className={stage === "complete" ? "text-indigo-400 font-medium" : "text-gray-500"}>
          Listen
        </span>
      </div>

      {/* Content */}
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
            className="flex items-center gap-2 text-sm text-gray-400 transition hover:text-gray-200"
          >
            <RotateCcw className="h-4 w-4" />
            Process another file
          </button>
        </div>
      )}

      {/* Footer */}
      <footer className="mt-auto pt-16 text-center text-xs text-gray-600">
        Radio Show Editor &mdash; AI-powered audio production
      </footer>
    </main>
  );
}
