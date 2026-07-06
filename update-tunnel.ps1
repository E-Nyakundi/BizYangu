<#
  update-tunnel.ps1
  ------------------
  Starts a cloudflared quick tunnel to localhost:8000, captures the random
  *.trycloudflare.com URL from its output, and rewrites every file in the
  BizYangu repo that hardcodes the tunnel hostname.

  Usage (from the project root, e.g. C:\path\to\BizYanguClaudeCopy):
      ..\update-tunnel.ps1

  What it updates:
    backend\.env
    backend\.env.example
    frontend\.env.local
    docker-compose.yml
    env.download

  After it finishes:
    - If you only changed something in the browser dev flow, just restart
      `npm run dev` (frontend) and the Django server (backend) â€" they read
      .env / .env.local fresh on start.
    - If you are testing the Android APK, NEXT_PUBLIC_API_URL is baked in at
      `next build` time, so you MUST rebuild + re-sync + reinstall:
          cd frontend
          npm run build
          npx cap sync android
          npx cap open android   # then Run in Android Studio
#>

param(
    [int]$Port = 8000,
    [string]$ProjectRoot = "."
)

$files = @(
    "backend\.env",
    "backend\.env.example",
    "frontend\.env.local",
    "docker-compose.yml",
    "env.download"
)

Write-Host "Starting cloudflared tunnel to localhost:$Port ..." -ForegroundColor Cyan

# Launch cloudflared, capture stdout+stderr as it logs to stderr by default
$proc = Start-Process -FilePath "cloudflared" `
    -ArgumentList "tunnel --url http://localhost:$Port" `
    -NoNewWindow -PassThru -RedirectStandardError "cloudflared_out.log" -RedirectStandardOutput "cloudflared_out.log"

$newUrl = $null
$timeout = (Get-Date).AddSeconds(30)

while (-not $newUrl -and (Get-Date) -lt $timeout) {
    Start-Sleep -Milliseconds 500
    if (Test-Path "cloudflared_out.log") {
        $content = Get-Content "cloudflared_out.log" -Raw
        if ($content -match "https://([a-z0-9\-]+\.trycloudflare\.com)") {
            $newUrl = $matches[1]
        }
    }
}

if (-not $newUrl) {
    Write-Host "Could not detect tunnel URL within 30s. Check cloudflared_out.log." -ForegroundColor Red
    exit 1
}

Write-Host "New tunnel URL: $newUrl" -ForegroundColor Green
Write-Host "cloudflared is running in the background as PID $($proc.Id) â€" leave it running." -ForegroundColor Yellow

# Regex matches any *.trycloudflare.com hostname currently in each file
$pattern = "[a-z0-9\-]+\.trycloudflare\.com"

foreach ($rel in $files) {
    $path = Join-Path $ProjectRoot $rel
    if (Test-Path $path) {
        $text = Get-Content $path -Raw
        $updated = [regex]::Replace($text, $pattern, $newUrl)
        if ($updated -ne $text) {
            Set-Content -Path $path -Value $updated -NoNewline
            Write-Host "Updated: $rel" -ForegroundColor Green
        } else {
            Write-Host "No tunnel reference found in: $rel (skipped)" -ForegroundColor DarkGray
        }
    } else {
        Write-Host "Not found, skipped: $rel" -ForegroundColor DarkGray
    }
}

Write-Host ""
Write-Host "Done. Remember:" -ForegroundColor Cyan
Write-Host "  - Restart Django + Next dev servers to pick up the new .env values."
Write-Host "  - If testing the Android APK: rebuild frontend, npx cap sync android, reinstall."
Write-Host "  - Re-register MPESA_CALLBACK_URL with Daraja if you are past sandbox."