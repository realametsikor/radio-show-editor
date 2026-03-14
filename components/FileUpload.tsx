"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import axios from "axios";
import { Upload, FileAudio, Loader2, AlertCircle } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FileUploadProps {
  onUploadComplete: (taskId: string) => void;
}

export default function FileUpload({ onUploadComplete }: FileUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;

      setFileName(file.name);
      setError(null);
      setUploading(true);

      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await axios.post(`${API_BASE}/upload`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        onUploadComplete(response.data.task_id);
      } catch (err) {
        if (axios.isAxiosError(err) && err.response) {
          setError(err.response.data?.detail || "Upload failed. Please try again.");
        } else {
          setError("Could not connect to the server. Is the backend running?");
        }
        setUploading(false);
      }
    },
    [onUploadComplete]
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
      <div
        {...getRootProps()}
        className={`relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-12 transition-all duration-200 cursor-pointer
          ${
            isDragActive
              ? "border-indigo-400 bg-indigo-500/10"
              : "border-gray-600 bg-gray-800/40 hover:border-indigo-500 hover:bg-gray-800/60"
          }
          ${uploading ? "pointer-events-none opacity-60" : ""}`}
      >
        <input {...getInputProps()} />

        {uploading ? (
          <div className="flex flex-col items-center gap-4 text-center">
            <Loader2 className="h-12 w-12 text-indigo-400 animate-spin" />
            <p className="text-lg font-medium text-gray-200">
              Uploading {fileName}...
            </p>
            <p className="text-sm text-gray-400">
              Sending your file to the processing server
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-4 text-center">
            {isDragActive ? (
              <FileAudio className="h-12 w-12 text-indigo-400" />
            ) : (
              <Upload className="h-12 w-12 text-gray-400" />
            )}
            <div>
              <p className="text-lg font-medium text-gray-200">
                {isDragActive
                  ? "Drop your audio file here"
                  : "Drag & drop your podcast file"}
              </p>
              <p className="mt-1 text-sm text-gray-400">
                Supports .wav and .mp3 files up to 500 MB
              </p>
            </div>
            <button
              type="button"
              className="mt-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-gray-900"
            >
              Browse Files
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-4 flex items-center gap-2 rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3 text-sm text-red-400">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}
    </div>
  );
}
