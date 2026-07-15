# AstraCortex — fully local (this PC only)
# - Ollama on host
# - API via uvicorn on host (not Docker api container, not Railway)
# - Postgres/Redis: docker compose services only (local DB)
# - Web: Next.js on host
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\run-local.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "== AstraCortex local (no remote server) ==" -ForegroundColor Cyan

# 1) Ollama required
try {
  $null = curl.exe -s --connect-timeout 2 http://127.0.0.1:11434/api/tags
  Write-Host "[ok] Ollama http://127.0.0.1:11434"
} catch {
  Write-Host "[!] Start Ollama first: ollama serve   (and: ollama pull qwen2.5:3b)" -ForegroundColor Yellow
  exit 1
}

# 2) Local DB only — not the API "server" container
Write-Host "[..] postgres + redis (docker local volumes only)"
docker compose up -d postgres redis | Out-Host
Start-Sleep -Seconds 3

# Free port 8000 from Docker API if it owns it
$apiUp = docker compose ps --status running --services 2>$null
if ($apiUp -match "api") {
  Write-Host "[..] stopping Docker API container (host will run uvicorn)"
  docker compose stop api | Out-Null
}

# 3) Python venv + deps
$venv = Join-Path $Root "backend\.venv"
$py = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Host "[..] creating backend\.venv"
  python -m venv $venv
  & $py -m pip install -q --upgrade pip
  & $py -m pip install -q -r (Join-Path $Root "backend\requirements.txt")
}

# Load .env.local into process env
$envFile = Join-Path $Root ".env.local"
Get-Content $envFile | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith("#")) { return }
  $i = $line.IndexOf("=")
  if ($i -lt 1) { return }
  $k = $line.Substring(0, $i).Trim()
  $v = $line.Substring($i + 1).Trim()
  Set-Item -Path "Env:$k" -Value $v
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root "data\uploads") | Out-Null
Set-Location (Join-Path $Root "backend")

Write-Host "[ok] INFERENCE_MODE=$env:INFERENCE_MODE  OLLAMA=$env:OLLAMA_BASE_URL"
Write-Host "[..] starting API on http://127.0.0.1:8000 (host uvicorn)"
Write-Host "     Web: from another terminal -> cd frontend; `$env:NEXT_PUBLIC_API_URL='http://127.0.0.1:8000'; npm run dev"
Write-Host ""

& $py -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --timeout-keep-alive 300
