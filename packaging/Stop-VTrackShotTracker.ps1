$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'VTrackShotTrackerCLI.exe') stop @args
exit $LASTEXITCODE
