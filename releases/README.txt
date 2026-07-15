# AstraCortex — GO LIVE (verified)

## Model proof (live, offline Ollama)
Answer: "I am the AstraCortex cognitive operating system designed to assist with tasks and information retrieval."
Provider: ollama · Model: qwen2.5:3b

## Releases folder
C:\Users\synov\.grok\downloads\astracortex\releases\
- AstraCortex-OS-Portable-2.1.0.exe   (desktop, no install)
- AstraCortex-OS-2.1.0-win-x64.exe    (Windows installer)
- AstraCortex-OS-2.1.0.apk            (Android Play-ready package id com.astracortex.os)

## Start stack (every boot)
1. Open Docker Desktop
2. Open terminal:
   cd C:\Users\synov\.grok\downloads\astracortex
   docker compose up -d postgres redis api
3. Frontend (if not running):
   cd frontend
   $env:NEXT_PUBLIC_API_URL="http://127.0.0.1:8000"
   npm run start
4. Keep Ollama running: ollama serve  (usually auto)

## Use
- Web: http://localhost:3000  (hard refresh Ctrl+Shift+R)
- Desktop: double-click Portable exe
- Android: install APK, set API URL to http://YOUR_PC_IP:8000 (Wi-Fi IP)

## Offline
INFERENCE_MODE=local · no internet required if Ollama + Docker are local.
