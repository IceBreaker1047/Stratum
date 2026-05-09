"use client";

import React, { useState, useRef } from "react";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.type === "application/pdf") {
        setFile(droppedFile);
        setError(null);
      } else {
        setError("Please upload a valid PDF document.");
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setIsLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${apiUrl}/parse-pdf`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Error ${response.status}: ${await response.text()}`);
      }

      const data = await response.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || "Something went wrong during upload.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#f5f5f7] text-[#1d1d1f] flex flex-col items-center p-6 md:p-20 font-sans selection:bg-black/10">

      {/* Dynamic Background Glow */}
      <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-[20%] -left-[10%] w-[60%] h-[60%] rounded-full bg-indigo-500/[0.03] blur-[120px]"></div>
        <div className="absolute top-[40%] -right-[10%] w-[50%] h-[50%] rounded-full bg-blue-500/[0.02] blur-[100px]"></div>
      </div>

      <div className="z-10 w-full max-w-5xl mb-16 flex flex-col items-center text-center mt-10">
        <h1 className="text-5xl md:text-7xl font-semibold tracking-tight mb-5 text-transparent bg-clip-text bg-gradient-to-b from-black to-black/60">
          Semantic PDF Parser.
        </h1>
        <p className="text-black/50 text-xl md:text-2xl max-w-2xl font-light tracking-wide">
          Intelligence extracted with absolute precision.
        </p>
      </div>

      <div className="z-10 w-full max-w-6xl grid grid-cols-1 lg:grid-cols-2 gap-12">

        {/* Upload Interface */}
        <div className="flex flex-col gap-6">
          <div
            onClick={() => fileInputRef.current?.click()}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`
              relative flex flex-col items-center justify-center w-full h-[380px] rounded-[32px] cursor-pointer
              transition-all duration-500 ease-out overflow-hidden group backdrop-blur-2xl shadow-sm
              ${isDragging
                ? "bg-white/80 border-black/20 scale-[1.02]"
                : "bg-white/40 border-black/5 hover:bg-white/60 hover:border-black/10 hover:scale-[1.01]"
              }
              border-[0.5px]
              ${file ? "bg-white/60 border-black/20" : ""}
            `}
          >
            <div className="flex flex-col items-center justify-center pt-5 pb-6 z-10 transition-transform duration-500">
              {file ? (
                <>
                  <div className="w-20 h-20 mb-6 rounded-2xl bg-black/5 flex items-center justify-center shadow-inner">
                    <svg className="w-10 h-10 text-black/80" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <p className="mb-2 text-2xl font-medium tracking-tight text-black">{file.name}</p>
                  <p className="text-md text-black/40 font-light">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                </>
              ) : (
                <>
                  <div className="w-20 h-20 mb-6 rounded-full bg-black/[0.02] flex items-center justify-center group-hover:bg-black/[0.04] transition-colors duration-500">
                    <svg className={`w-8 h-8 text-black/40 transition-transform duration-500 ${isDragging ? "scale-125 text-black" : "group-hover:scale-110 group-hover:text-black"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                  </div>
                  <p className="mb-2 text-xl tracking-tight text-black/60">
                    <span className="font-medium text-black">Click to browse</span> or drag a file here
                  </p>
                  <p className="text-sm text-black/30 font-light tracking-wide">Supported format: PDF</p>
                </>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".pdf,application/pdf"
              onChange={handleFileChange}
            />
          </div>

          {error && (
            <div className="px-6 py-4 rounded-2xl bg-red-500/5 border-[0.5px] border-red-500/10 text-red-600 text-sm font-medium backdrop-blur-md">
              {error}
            </div>
          )}

          <button
            onClick={handleUpload}
            disabled={!file || isLoading}
            className={`
              w-full py-5 rounded-full font-medium text-lg transition-all duration-500
              flex items-center justify-center relative overflow-hidden tracking-wide
              ${!file
                ? "bg-black/5 text-black/20 cursor-not-allowed"
                : "bg-black text-white hover:bg-[#333333] hover:scale-[1.02] shadow-[0_10px_30px_rgba(0,0,0,0.1)]"
              }
            `}
          >
            {isLoading ? (
              <span className="flex items-center">
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Extracting Data...
              </span>
            ) : (
              "Extract Intelligence"
            )}
          </button>
        </div>

        {/* Results Interface */}
        <div className="flex flex-col h-[520px] w-full">
          <div className="w-full h-full rounded-[32px] bg-white/80 backdrop-blur-3xl border-[0.5px] border-black/5 overflow-hidden flex flex-col relative shadow-[0_20px_50px_rgba(0,0,0,0.05)]">
            {/* macOS Window Header */}
            <div className="h-14 bg-black/[0.01] border-b-[0.5px] border-black/5 flex items-center px-6 shrink-0 z-10 w-full relative">
              <div className="flex items-center space-x-2 absolute left-6">
              </div>
              <div className="flex-1 flex justify-center">
                <span className="text-xs font-mono tracking-widest text-black/20 uppercase">output.json</span>
              </div>
            </div>

            {/* Content Body */}
            <div className="flex-1 overflow-auto bg-transparent relative p-8">
              {result ? (
                <div className="animate-in fade-in slide-in-from-bottom-4 duration-1000 ease-out">
                  <div className="mb-6 inline-flex items-center px-3 py-1.5 rounded-full bg-black/5 border-[0.5px] border-black/10 text-black/60 text-xs font-medium tracking-wide">
                    Extracted {result.chunks_extracted} contextual chunks
                  </div>
                  <pre className="text-sm font-mono text-black/70 whitespace-pre-wrap leading-relaxed tracking-tight">
                    {JSON.stringify(result.chunks, null, 2)}
                  </pre>
                </div>
              ) : isLoading ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-black/30">
                  <div className="relative w-12 h-12 mb-6">
                    <div className="absolute inset-0 border-[2px] border-t-black/40 border-r-transparent border-b-transparent border-l-transparent rounded-full animate-spin"></div>
                    <div className="absolute inset-1 border-[2px] border-b-black/20 border-t-transparent border-r-transparent border-l-transparent rounded-full animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.2s' }}></div>
                  </div>
                  <p className="font-mono text-xs tracking-widest uppercase animate-pulse">Processing semantic tree...</p>
                </div>
              ) : (
                <div className="absolute inset-0 flex items-center justify-center">
                  <p className="font-mono text-xs tracking-widest text-black/10 uppercase">Waiting for input</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
