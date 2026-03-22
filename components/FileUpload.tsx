"use client";

import { useState, useRef, ChangeEvent } from "react";
import { UploadCloud, Music, FileAudio, Settings2, Sparkles, Loader2, Mic2, X } from "lucide-react";

type FileUploadProps = {
  onUploadComplete: (taskId: string) => void;
};

// NOTE: Ensure this matches your Hugging Face Backend URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://realametsikor-radio-show-backend.hf.space";

export default function FileUpload({ onUploadComplete }: FileUploadProps) {
  // Changed from a single file to an array of files
  const [files, setFiles] = useState<File[]>([]);
  const [customIntroFile, setCustomIntroFile] = useState<File | null>(null);
  
  const [mood, setMood] = useState("documentary");
  const [introSelection, setIntroSelection] = useState("none");
  const [isUploading, setIsUploading] = useState(false);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const customIntroInputRef = useRef<HTMLInputElement>(null);

  const handleMainFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      // Append the newly selected files to the existing array
      setFiles((prevFiles) => [...prevFiles, ...Array.from(e.target.files!)]);
    }
  };

  const handleRemoveFile = (indexToRemove: number, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevents opening the file browser when clicking the X
    setFiles((prevFiles) => prevFiles.filter((_, i) => i !== indexToRemove));
  };

  const handleCustomIntroChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setCustomIntroFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (files.length === 0) return;

    setIsUploading(true);
    const formData = new FormData();
    
    // Attach every file in the array to the form data
    files.forEach((file) => {
      formData.append("files", file);
    });
    
    formData.append("mood", mood);
    formData.append("intro_selection", introSelection);

    if (introSelection === "custom" && customIntroFile) {
      formData.append("custom_intro", customIntroFile);
    }

    try {
      const res = await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error("Upload failed");

      const data = await res.json();
      onUploadComplete(data.task_id);
    } catch (error) {
      console.error(error);
      alert("An error occurred during upload. Check console for details.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-2xl animate-fade-in">
      {/* Configuration Panel */}
      <div className="mb-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        
        {/* Vibe Selection */}
        <div className="glass-card rounded-2xl p-5 border border-gray-800 bg-[#13131A]">
          <label className="flex items-center gap-2 text-sm font-semibold text-white mb-3">
            <Settings2 className="h-4 w-4 text-indigo-400" />
            Background Music Vibe
          </label>
          <div className="relative">
            <select
              value={mood}
              onChange={(e) => setMood(e.target.value)}
              className="w-full appearance-none rounded-xl border border-gray-700 bg-gray-900/50 px-4 py-3 text-sm text-gray-200 outline-none transition-all focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            >
              <option value="documentary">Documentary (Ambient & Focused)</option>
              <option value="science">Science (Pulsing & Deep)</option>
              <option value="lo-fi">Lo-Fi (Chill & Jazzy)</option>
              <option value="true_crime">True Crime (Tense & Mysterious)</option>
              <option value="upbeat">Upbeat (High Energy)</option>
            </select>
            <div className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-gray-500">
              ▼
            </div>
          </div>
        </div>

        {/* Intro Selection */}
        <div className="glass-card rounded-2xl p-5 border border-gray-800 bg-[#13131A]">
          <label className="flex items-center gap-2 text-sm font-semibold text-white mb-3">
            <Sparkles className="h-4 w-4 text-indigo-400" />
            Show Intro / Bumper
          </label>
          <div className="relative">
            <select
              value={introSelection}
              onChange={(e) => setIntroSelection(e.target.value)}
              className="w-full appearance-none rounded-xl border border-gray-700 bg-gray-900/50 px-4 py-3 text-sm text-gray-200 outline-none transition-all focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            >
              <option value="none">No Intro (Start immediately)</option>
              <option value="documentary">Built-in: Deep Documentary Stinger</option>
              <option value="ethereal">Built-in: Ethereal Sci-Fi Drone</option>
              <option value="energetic">Built-in: High Energy Swell</option>
              <option value="custom">Upload Custom Voiceover/Intro...</option>
            </select>
            <div className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-gray-500">
              ▼
            </div>
          </div>
        </div>
      </div>

      {/* Custom Intro Upload */}
      {introSelection === "custom" && (
        <div className="mb-6 p-4 rounded-xl border border-indigo-500/30 bg-indigo-500/5 flex items-center justify-between gap-4 animate-fade-in">
          <div className="flex items-center gap-3 overflow-hidden">
            <Mic2 className="h-5 w-5 text-indigo-400 shrink-0" />
            <div className="truncate">
              <p className="text-sm font-medium text-indigo-200">Custom Intro Audio</p>
              <p className="text-xs text-gray-400 truncate">
                {customIntroFile ? customIntroFile.name : "Select an MP3 or WAV file"}
              </p>
            </div>
          </div>
          <button
            onClick={() => customIntroInputRef.current?.click()}
            className="shrink-0 rounded-lg bg-indigo-500/20 px-4 py-2 text-xs font-semibold text-indigo-300 hover:bg-indigo-500/30 transition-colors"
          >
            {customIntroFile ? "Change File" : "Browse..."}
          </button>
          <input
            type="file"
            accept="audio/*"
            ref={customIntroInputRef}
            onChange={handleCustomIntroChange}
            className="hidden"
          />
        </div>
      )}

      {/* MULTI-FILE Podcast Dropzone */}
      <div 
        onClick={() => fileInputRef.current?.click()}
        className={`group relative cursor-pointer rounded-3xl border-2 border-dashed transition-all duration-300 ${
          files.length > 0 ? "border-indigo-500 bg-indigo-500/5" : "border-gray-700 bg-[#13131A] hover:border-indigo-500 hover:bg-gray-800/50"
        } p-8 sm:p-12 text-center`}
      >
        <input
          type="file"
          accept="audio/*,video/*"
          multiple // Enables selecting multiple files at once!
          ref={fileInputRef}
          onChange={handleMainFileChange}
          className="hidden"
        />
        
        <div className="flex flex-col items-center justify-center">
          <div className={`mb-6 flex h-20 w-20 items-center justify-center rounded-2xl transition-all duration-300 ${
            files.length > 0 ? "bg-indigo-500/20 ring-4 ring-indigo-500/20" : "bg-gray-800 group-hover:bg-indigo-500/10 group-hover:scale-105"
          }`}>
            {files.length > 0 ? <FileAudio className="h-10 w-10 text-indigo-400" /> : <UploadCloud className="h-10 w-10 text-gray-400 group-hover:text-indigo-400" />}
          </div>
          
          {files.length > 0 ? (
            <div className="w-full space-y-3 mt-2">
              <h3 className="text-xl font-semibold text-white mb-4">
                {files.length} File{files.length > 1 ? "s" : ""} Ready
              </h3>
              <div className="max-h-40 overflow-y-auto space-y-2 pr-2">
                {files.map((f, index) => (
                  <div key={index} className="flex items-center justify-between bg-gray-900/80 border border-gray-700 rounded-lg p-3 text-left">
                    <span className="text-sm text-gray-300 truncate pr-4">{f.name}</span>
                    <button 
                      onClick={(e) => handleRemoveFile(index, e)}
                      className="text-gray-500 hover:text-red-400 hover:bg-red-400/10 p-1.5 rounded-md transition-colors"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
              <p className="text-xs text-indigo-300 pt-2">Click anywhere to add more files.</p>
            </div>
          ) : (
            <>
              <h3 className="mb-2 text-xl font-semibold text-white">Upload AI Podcast Parts</h3>
              <p className="text-sm text-gray-400 max-w-sm">
                Click to browse or drag and drop your raw NotebookLM files here. <br/>
                <span className="text-indigo-400/80">You can upload multiple files and they will be stitched together automatically!</span>
              </p>
            </>
          )}
        </div>
      </div>

      {/* Submit Button */}
      {files.length > 0 && (
        <button
          onClick={handleUpload}
          disabled={isUploading || (introSelection === "custom" && !customIntroFile)}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-6 py-4 text-base font-bold text-white transition-all btn-glow hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isUploading ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              Processing Episode...
            </>
          ) : (
            <>
              <Music className="h-5 w-5" />
              Produce Radio Show
            </>
          )}
        </button>
      )}
    </div>
  );
}
