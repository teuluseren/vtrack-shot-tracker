$ErrorActionPreference = 'Stop'
$installed = Join-Path $env:ProgramFiles 'VTrack Shot Tracker\VTrackShotTracker.exe'

# Stop the Shot Tracker cleanly first, then always close the VTrack processes
# that the original automation script managed.
try {
    if (Test-Path -LiteralPath $installed) {
        & $installed stop @args
    }
    else {
        & py -3 (Join-Path $PSScriptRoot 'vtrack_shot_tracker.py') stop @args
    }
    $trackerExitCode = $LASTEXITCODE
}
finally {
    $processes = Get-Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ProcessName -match 'LPGAgent|VTrack|VTrackToolKit|VTrackToolkit|VGPconnect|GSPconnect' -and
            $_.ProcessName -notmatch '^VTrackShotTracker$'
        }

    if (-not $processes) {
        Write-Output 'VTrack is not running.'
    }
    else {
        $processes | ForEach-Object {
            try {
                $_.CloseMainWindow() | Out-Null
                Start-Sleep -Seconds 3

                if (-not $_.HasExited) {
                    Stop-Process -Id $_.Id -Force
                }
            }
            catch {
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

exit $trackerExitCode
