$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'VTrackShotTrackerCLI.exe') start @args
exit $LASTEXITCODE
