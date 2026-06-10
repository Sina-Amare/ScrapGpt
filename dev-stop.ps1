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

Write-Host "Dev servers stopped."
