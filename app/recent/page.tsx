"use client";

import React, { useEffect, useState } from 'react';
import Link from 'next/link';

export default function RecentShows() {
  const [shows, setShows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  
  // NEW: State to show a loading spinner on the button while the file downloads
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  // Your live Hugging Face backend URL!
  const BACKEND_URL = "https://realametsikor-radio-show-backend.hf.space";

  useEffect(() => {
    const fetchShows = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/recent`);
        const data = await response.json();
        setShows(data.recent_shows || []);
      } catch (error) {
        console.error("Failed to fetch recent shows:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchShows();
  }, []);

  const handleDelete = async (taskId: string) => {
    if (!window.confirm("Are you sure you want to permanently delete this show?")) return;

    setDeletingId(taskId);
    try {
      const response = await fetch(`${BACKEND_URL}/delete/${taskId}`, { method: "DELETE" });
      if (response.ok) {
        setShows((prevShows) => prevShows.filter((show: any) => show.task_id !== taskId));
      } else {
        alert("Failed to delete the show from the server.");
      }
    } catch (error) {
      console.error("Delete error:", error);
      alert("An error occurred while deleting.");
    } finally {
      setDeletingId(null);
    }
  };

  // =========================================================================
  # 📥 THE BLOB DOWNLOADER
  # Downloads the file in the background so the site never visually breaks!
  // =========================================================================
  const handleDownload = async (taskId: string, format: string, filename: string) => {
    // Set loading state for this specific button
    setDownloadingId(`${taskId}-${format}`);
    
    try {
      const response = await fetch(`${BACKEND_URL}/download/${taskId}?format=${format}`);
      
      if (!response.ok) {
        throw new Error("File not found on server.");
      }

      // Fetch the audio data as a raw Blob
      const blob = await response.blob();
      
      // Create a hidden, temporary link to force the browser to download it
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      
      // Clean up the filename so it saves nicely
      const safeFilename = filename.replace(/[^a-z0-9]/gi, '_').toLowerCase();
      a.download = `Radio_Show_${safeFilename}.${format}`;
      
      document.body.appendChild(a);
      a.click();
      
      // Clean up the temporary link
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
    } catch (error) {
      console.error("Download error:", error);
      alert("Download failed. The server may have cleared this file to save space. Please process it again!");
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0F] text-white p-8 font-sans animate-fade-in">
      <div className="max-w-3xl mx-auto">
        
        <div className="mb-8">
          <Link 
            href="/" 
            className="inline-flex items-center text-sm font-medium text-gray-400 hover:text-indigo-400 transition-colors mb-6 group"
          >
            <svg className="w-4 h-4 mr-2 transform group-hover:-translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back to Home
          </Link>

          <h1 className="text-3xl font-bold mb-2">Your Audio Vault</h1>
          <p className="text-gray-400">Download or manage your recently processed radio shows here.</p>
        </div>

        {loading ? (
          <div className="flex justify-center items-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
            <span className="ml-3 text-gray-400">Fetching vault...</span>
          </div>
        ) : shows.length === 0 ? (
          <div className="bg-[#13131A] border border-gray-800 rounded-xl p-8 text-center">
            <p className="text-gray-400 mb-4">Your vault is empty.</p>
            <p className="text-sm text-gray-500">Shows will appear here after they finish processing.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {shows.map((show: any) => (
              <div 
                key={show.task_id} 
                className="bg-[#13131A] border border-gray-800 hover:border-indigo-500/50 transition-all duration-300 rounded-xl p-6 flex flex-col justify-between gap-5 shadow-lg"
              >
                <div>
                  <h2 className="text-lg font-semibold text-gray-100 truncate w-full">
                    {show.filename}
                  </h2>
                  <p className="text-sm text-gray-500 mt-1">
                    Processed: {show.time_processed}
                  </p>
                </div>
                
                <div className="flex flex-wrap items-center gap-3 border-t border-gray-800/60 pt-4">
                  
                  {/* UPDATE: Changed from <a> to <button> calling handleDownload */}
                  <button
                    onClick={() => handleDownload(show.task_id, "mp3", show.filename)}
                    disabled={downloadingId === `${show.task_id}-mp3`}
                    className="flex-1 sm:flex-none bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition-all shadow-[0_0_15px_rgba(79,70,229,0.3)] hover:shadow-[0_0_20px_rgba(79,70,229,0.5)] flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {downloadingId === `${show.task_id}-mp3` ? (
                      <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
                    ) : (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                    )}
                    Download MP3
                    <span className="opacity-70 font-normal text-xs ml-1">(Fast)</span>
                  </button>

                  <button
                    onClick={() => handleDownload(show.task_id, "wav", show.filename)}
                    disabled={downloadingId === `${show.task_id}-wav`}
                    className="flex-1 sm:flex-none bg-transparent hover:bg-gray-800 text-gray-300 px-5 py-2.5 rounded-lg border border-gray-700 hover:border-gray-500 text-sm font-semibold transition-all flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {downloadingId === `${show.task_id}-wav` ? (
                       <div className="animate-spin h-4 w-4 border-2 border-gray-400 border-t-transparent rounded-full"></div>
                    ) : (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                    )}
                    Download WAV
                    <span className="opacity-50 font-normal text-xs ml-1">(HQ)</span>
                  </button>

                  <button
                    onClick={() => handleDelete(show.task_id)}
                    disabled={deletingId === show.task_id}
                    className="flex-1 sm:flex-none bg-transparent hover:bg-red-500/10 text-red-400 px-5 py-2.5 rounded-lg border border-red-500/20 hover:border-red-500/50 text-sm font-semibold transition-all flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {deletingId === show.task_id ? (
                      <div className="animate-spin h-4 w-4 border-2 border-red-400 border-t-transparent rounded-full"></div>
                    ) : (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    )}
                    Delete
                  </button>

                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
