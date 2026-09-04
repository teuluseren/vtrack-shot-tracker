$ErrorActionPreference = 'Stop'

# Start VTrackToolKit before opening the Shot Tracker. Avoid launching another
# copy when Home Assistant calls this script while VTrack is already running.
$vtrackRunning = Get-Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.ProcessName -match 'VTrackToolKit|VTrackToolkit'
    } |
    Select-Object -First 1

if (-not $vtrackRunning) {
    $app = Get-StartApps |
        Where-Object {
            $_.Name -match 'VTrack\s*Tool\s*Kit|VTrackToolKit'
        } |
        Select-Object -First 1

    if (-not $app) {
        throw 'VTrackToolKit not found.'
    }

    Start-Process "shell:AppsFolder\$($app.AppID)"
}

$installed = Join-Path $env:ProgramFiles 'VTrack Shot Tracker\VTrackShotTrackerCLI.exe'
if (Test-Path -LiteralPath $installed) {
    & $installed start @args
}
else {
    & py -3 (Join-Path $PSScriptRoot 'vtrack_shot_tracker.py') start @args
}
exit $LASTEXITCODE
