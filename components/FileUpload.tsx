"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import axios from "axios";
import {
  Upload,
  FileAudio,
  Loader2,
  AlertCircle,
  CheckCircle2,
  ChevronDown,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const MOOD_OPTIONS = [
  { value: "lo-fi", label: "Lo-Fi Chill" },
  { value: "upbeat", label: "Upbeat & Energetic" },
  { value: "news", label: "News Broadcast" },
  { value: "ambient", label: "Ambient & Atmospheric" },
  { value: "jazz", label: "Smooth Jazz" },
  { value: "cinematic", label: "Cinematic & Epic" },
  { value: "acoustic", label: "Acoustic & Warm" },
  { value: "electronic", label: "Electronic & Modern" },
];

interface FileUploadProps {
  onUploadComplete: (taskId: string) => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileUpload({ onUploadComplete }: FileUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileSize, setFileSize] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectedMood, setSelectedMood] = useState("lo-fi");

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;

      setFileName(file.name);
      setFileSize(formatFileSize(file.size));
      setError(null);
      setUploading(true);
      setUploadProgress(0);

      const formData = new FormData();
      formData.append("file", file);
      formData.append("mood", selectedMood);

      try {
        const response = await axios.post(`${API_BASE}/upload`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
          onUploadProgress: (progressEvent) => {
            if (progressEvent.total) {
              const percent = Math.round(
                (progressEvent.loaded * 100) / progressEvent.total
              );
              setUploadProgress(percent);
            }
          },
        });
        onUploadComplete(response.data.task_id);
      } catch (err) {
        if (axios.isAxiosError(err) && err.response) {
          setError(
            err.response.data?.detail || "Upload failed. Please try again."
          );
        } else {
          setError(
            "Could not connect to the server. Is the backend running?"
          );
        }
        setUploading(false);
      }
    },
    [onUploadComplete, selectedMood]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "audio/wav": [".wav"],
      "audio/mpeg": [".mp3"],
    },
    maxFiles: 1,
    disabled: uploading,
  });

  return (
    <div className="w-full max-w-xl mx-auto">
      {/* Mood / Vibe Selector */}
      <div className="mb-6">
        <label
          htmlFor="mood-select"
          className="block text-sm font-medium text-gray-300 mb-2"
        >
          Choose a Vibe for your radio show
        </label>
        <div className="relative">
          <select
            id="mood-select"
            value={selectedMood}
            onChange={(e) => setSelectedMood(e.target.value)}
            disabled={uploading}
            className="w-full appearance-none rounded-xl border border-gray-700 bg-[rgba(15,15,25,0.8)] px-4 py-3 pr-10 text-sm text-white transition focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {MOOD_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        </div>
        <p className="mt-1.5 text-xs text-gray-500">
          This sets the background music style for your finished radio show.
        </p>
      </div>

      <div
        {...getRootProps()}
        className={`glass-card relative flex flex-col items-center justify-center rounded-2xl p-12 transition-all duration-300 cursor-pointer
          ${
            isDragActive
              ? "!border-indigo-400 !bg-indigo-500/10 scale-[1.02]"
              : "hover:!border-indigo-500/30 hover:!bg-[rgba(22,22,35,0.7)]"
          }
          ${uploading ? "pointer-events-none" : ""}`}
      >
        <input {...getInputProps()} />

        {uploading ? (
          <div className="flex w-full flex-col items-center gap-5 text-center">
            <div className="relative">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-500/10 ring-1 ring-indigo-500/20">
                <FileAudio className="h-8 w-8 text-indigo-400" />
              </div>
              <div className="absolute -bottom-1 -right-1 flex h-6 w-6 items-center justify-center rounded-full bg-surface-50">
                <Loader2 className="h-4 w-4 text-indigo-400 animate-spin" />
              </div>
            </div>

            <div>
              <p className="text-lg font-semibold text-white">{fileName}</p>
              <p className="mt-1 text-sm text-gray-400">{fileSize}</p>
            </div>

            {/* Progress bar */}
            <div className="w-full max-w-xs">
              <div className="h-2 w-full overflow-hidden rounded-full bg-gray-800">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-300 ease-out"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <div className="mt-2 flex justify-between text-xs text-gray-500">
                <span>Uploading...</span>
                <span>{uploadProgress}%</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-5 text-center">
            <div
              className={`flex h-16 w-16 items-center justify-center rounded-2xl transition-all duration-300 ${
                isDragActive
                  ? "bg-indigo-500/20 ring-2 ring-indigo-400/40 scale-110"
                  : "bg-gray-800 ring-1 ring-gray-700"
              }`}
            >
              {isDragActive ? (
                <FileAudio className="h-8 w-8 text-indigo-400" />
              ) : (
                <Upload className="h-8 w-8 text-gray-400" />
              )}
            </div>

            <div>
              <p className="text-lg font-semibold text-white">
                {isDragActive
                  ? "Drop your audio file here"
                  : "Drag & drop your podcast file"}
              </p>
              <p className="mt-2 text-sm text-gray-400">
                Supports WAV and MP3 files up to 500 MB
              </p>
            </div>

            <button
              type="button"
              className="mt-1 rounded-xl bg-indigo-600 px-6 py-2.5 text-sm font-semibold text-white transition btn-glow hover:bg-indigo-500"
            >
              Browse Files
            </button>

            <div className="flex items-center gap-4 text-xs text-gray-600">
              <span className="flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" /> .wav
              </span>
              <span className="flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" /> .mp3
              </span>
              <span className="flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" /> Up to 500 MB
              </span>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-4 flex items-center gap-2.5 rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}
    </div>
  );
}
