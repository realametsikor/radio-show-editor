"use client";

import React, { useEffect, useState } from 'react';
import Link from 'next/link';

export default function RecentShows() {
  const [shows, setShows] = useState([]);
  const [loading, setLoading] = useState(true);

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

  return (
    <div className="min-h-screen bg-[#0A0A0F] text-white p-8 font-sans animate-fade-in">
      <div className="max-w-3xl mx-auto">
        
        {/* Navigation / Back Button */}
        <div className="mb-8">
          <Link 
            href="/" 
            className="inline-flex items-center text-sm font-medium text-gray-400 hover:text-indigo-400 transition-colors mb-6 group"
          >
            <svg 
              className="w-4 h-4 mr-2 transform group-hover:-translate-x-1 transition-transform" 
              fill="none" 
              viewBox="0 0 24 24" 
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back to Home
          </Link>

          <h1 className="text-3xl font-bold mb-2">Your Audio Vault</h1>
          <p className="text-gray-400">Download your recently processed radio shows here.</p>
        </div>

        {/* Loading State */}
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
          /* The Shows List */
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
                
                {/* The Dual Download Buttons */}
                <div className="flex flex-wrap items-center gap-3 border-t border-gray-800/60 pt-4">
                  
                  {/* MP3 Button */}
                  <a
                    href={`${BACKEND_URL}/download/${show.task_id}?format=mp3`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 sm:flex-none bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition-all shadow-[0_0_15px_rgba(79,70,229,0.3)] hover:shadow-[0_0_20px_rgba(79,70,229,0.5)] flex items-center justify-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Download MP3
                    <span className="opacity-70 font-normal text-xs ml-1">(Fast)</span>
                  </a>

                  {/* WAV Button */}
                  <a
                    href={`${BACKEND_URL}/download/${show.task_id}?format=wav`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 sm:flex-none bg-transparent hover:bg-gray-800 text-gray-300 px-5 py-2.5 rounded-lg border border-gray-700 hover:border-gray-500 text-sm font-semibold transition-all flex items-center justify-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Download WAV
                    <span className="opacity-50 font-normal text-xs ml-1">(HQ)</span>
                  </a>

                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
