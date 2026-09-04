$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'VTrackShotTracker.exe') start @args
exit $LASTEXITCODE
