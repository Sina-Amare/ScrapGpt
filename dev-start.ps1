# Start backend and frontend dev servers as background processes.
# PIDs are saved to .dev-pids so dev-stop.ps1 can kill them cleanly.

$root = $PSScriptRoot

# Backend
$backend = Start-Process `
    -FilePath "$root\venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -PassThru

# Frontend
$frontend = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList "/c", "npm.cmd run dev" `
    -WorkingDirectory "$root\frontend" `
    -WindowStyle Hidden `
    -PassThru

# Save PIDs
"$($backend.Id)`n$($frontend.Id)" | Set-Content "$root\.dev-pids"

Write-Host "Backend  started (PID $($backend.Id))  -> http://127.0.0.1:8000"
Write-Host "Frontend started (PID $($frontend.Id)) -> http://127.0.0.1:5173"
Write-Host ""
Write-Host "Run .\dev-stop.ps1 to stop both."
