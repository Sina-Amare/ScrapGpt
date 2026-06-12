# Kill backend and frontend dev servers started by dev-start.ps1.
# Also clears anything left on ports 8000 and 5173 as a fallback.

$root = $PSScriptRoot
$pidFile = "$root\.dev-pids"

if (Test-Path $pidFile) {
    Get-Content $pidFile | ForEach-Object {
        $id = [int]$_
        if (Get-Process -Id $id -ErrorAction SilentlyContinue) {
            Stop-Process -Id $id -Force
            Write-Host "Killed PID $id"
        }
    }
    Remove-Item $pidFile
}

# Fallback: clear any remaining processes on the dev ports
Get-NetTCPConnection -LocalPort 8000,5173 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object {
        Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
        Write-Host "Killed leftover PID $_ on dev port"
    }

# Clean up the redirected dev log files written by dev-start.ps1.
@(".dev-backend.log", ".dev-backend.err.log", ".dev-frontend.log", ".dev-frontend.err.log") |
    ForEach-Object {
        $logPath = Join-Path $root $_
        if (Test-Path $logPath) { Remove-Item $logPath -Force -ErrorAction SilentlyContinue }
    }

Write-Host "Dev servers stopped."
