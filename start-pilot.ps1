# start-pilot.ps1 - serve the study and expose it on a temporary public URL.
#
# For the pilot with friends, before the study is properly hosted. Run it, send the
# printed URL to one friend at a time, and keep this window open while they work:
# closing it (or letting the PC sleep) takes the study offline immediately.
#
# Pilot answers go to a separate folder so they can never mix with the real run.
# The URL changes every time this script starts - always send the newest one.

$ErrorActionPreference = "Stop"

$Backend  = "C:\Users\jiach\Documents\Claude\Projects\tehsis\hems-demo\backend"
$Python   = "C:\Users\jiach\AppData\Local\Programs\Python\Python312\python.exe"
$Cloudflared = "C:\cloudflared\cloudflared.exe"
$DataDir  = "D:\Claude\Projects\hems-thesis\pilot-runs"
$LogDir   = "D:\Claude\Projects\hems-thesis\pilot-runs\_logs"

New-Item -ItemType Directory -Force $DataDir, $LogDir | Out-Null

# A fresh token each run: the export and summary endpoints are reachable from the
# internet while the tunnel is open, and they return participant data.
$env:RESEARCHER_TOKEN = [guid]::NewGuid().ToString("N")
$env:DATA_DIR = $DataDir

# Qualitative interviews: fixed order P1..P6 = A, B, A, B, A, B (3 per condition, option
# order balanced within each). See _pilot_cell in backend/session_service.py.
# After six sessions the backend falls back to block randomisation.
$env:PILOT_CELL_SEQUENCE = "A:accept_first,B:accept_first,A:reject_first,B:reject_first,A:accept_first,B:reject_first"

$busy = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($busy) { Stop-Process -Id $busy.OwningProcess -Force; Start-Sleep -Seconds 1 }

Write-Host "Starting the study backend..." -ForegroundColor Cyan
$api = Start-Process -FilePath $Python `
    -ArgumentList "-m","uvicorn","main:app","--port","8000","--host","127.0.0.1" `
    -WorkingDirectory $Backend -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput "$LogDir\api.out.log" -RedirectStandardError "$LogDir\api.err.log"

for ($i = 0; $i -lt 30; $i++) {
    try { Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 2 | Out-Null; break }
    catch { Start-Sleep -Milliseconds 500 }
}

Write-Host "Opening the public tunnel..." -ForegroundColor Cyan
$tunnelLog = "$LogDir\tunnel.log"
Remove-Item $tunnelLog -ErrorAction SilentlyContinue
$tun = Start-Process -FilePath $Cloudflared `
    -ArgumentList "tunnel","--url","http://127.0.0.1:8000","--no-autoupdate" `
    -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput "$LogDir\tunnel.out.log" -RedirectStandardError $tunnelLog

$url = $null
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-Path $tunnelLog) {
        $m = Select-String -Path $tunnelLog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue
        if ($m) { $url = $m.Matches[0].Value; break }
    }
}

if (-not $url) { Write-Host "Could not read the tunnel URL - check $tunnelLog" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  Send this link to your friends:" -ForegroundColor Green
Write-Host "  $url" -ForegroundColor Green
Write-Host ""
Write-Host "  Researcher token (for /api/export/all?token=...): $env:RESEARCHER_TOKEN" -ForegroundColor DarkGray
Write-Host "  Pilot data: $DataDir" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Keep this window open. Press Ctrl+C to take the study offline." -ForegroundColor Yellow

try { Wait-Process -Id $tun.Id }
finally {
    Stop-Process -Id $tun.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
    Write-Host "Study is offline." -ForegroundColor Yellow
}
