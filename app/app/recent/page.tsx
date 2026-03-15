"use client";

import React, { useEffect, useState } from 'react';

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
    <div className="min-h-screen bg-[#0A0A0F] text-white p-8 font-sans">
      <div className="max-w-3xl mx-auto">
        
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Your Audio Vault</h1>
          <p className="text-gray-400">Download your recently processed radio shows here.</p>
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
                className="bg-[#13131A] border border-gray-800 hover:border-indigo-500/50 transition-colors rounded-xl p-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4"
              >
                <div>
                  <h2 className="text-lg font-semibold text-gray-100 truncate max-w-xs">
                    {show.filename}
                  </h2>
                  <p className="text-sm text-gray-500 mt-1">
                    Processed: {show.time_processed}
                  </p>
                </div>
                
                <a
                  href={`${BACKEND_URL}${show.download_link}`}
                  download
                  className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2 rounded-lg font-medium transition-colors flex items-center justify-center min-w-[140px]"
                >
                  Download MP3
                </a>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
