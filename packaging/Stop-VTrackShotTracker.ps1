$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'VTrackShotTracker.exe') stop @args
exit $LASTEXITCODE
