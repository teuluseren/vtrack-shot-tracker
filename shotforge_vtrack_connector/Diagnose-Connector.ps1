param([string]$Bundle = '')
$ErrorActionPreference = 'Stop'
if (-not $Bundle) {
    $Bundle = if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'connector.json')) { $PSScriptRoot } else { Join-Path $PSScriptRoot 'dist' }
}
Write-Output '=== Connector files ==='
foreach ($name in @('GSPLauncher.exe', 'GSPro.exe', 'GSPconnect.exe', 'bridge.py', 'connector.json')) {
    $path = Join-Path $Bundle $name
    Write-Output "$name present: $(Test-Path -LiteralPath $path)"
}
$ports = @(12485, 921)
if (Test-Path -LiteralPath (Join-Path $Bundle 'connector.json')) {
    $config = Get-Content -LiteralPath (Join-Path $Bundle 'connector.json') -Raw | ConvertFrom-Json
    $ports = @($config.listen_port, $config.shotforge_port)
    Write-Output "Route: $($config.listen_host):$($config.listen_port) -> $($config.shotforge_host):$($config.shotforge_port)"
}
Write-Output '=== Relevant processes and main windows ==='
Get-Process | Where-Object { $_.ProcessName -match '^(GSPLauncher|GSPro|GSPconnect|LPGAgent|VTrackToolKit|ShotForge|rela|python.*)$' } |
    Select-Object ProcessName, Id, MainWindowHandle, MainWindowTitle | Format-Table -AutoSize
Write-Output '=== TCP endpoints (last column is owner PID) ==='
# netstat works without the WMI/CIM permissions required by the old probe.
$pattern = ':(' + (($ports | ForEach-Object { [regex]::Escape([string]$_) }) -join '|') + ')\s'
netstat -ano -p tcp | Select-String -Pattern $pattern | ForEach-Object { $_.Line.Trim() }
Write-Output '=== Recent connector messages ==='
foreach ($name in @('launcher.log', 'bridge.log')) {
    $path = Join-Path $Bundle "logs\$name"
    if (Test-Path -LiteralPath $path) {
        Write-Output $name
        Get-Content -LiteralPath $path -Tail 15
    }
}
Write-Output '=== Latest VTrack launch/connection messages ==='
$packages = Join-Path $env:LOCALAPPDATA 'Packages'
$logs = Get-ChildItem -LiteralPath $packages -Directory | ForEach-Object {
    $appLogs = Join-Path $_.FullName 'LocalState\LAON PEOPLE\VTrackToolKit\AppLogs'
    if (Test-Path -LiteralPath $appLogs) { Get-ChildItem -LiteralPath $appLogs -Recurse -Filter 'VTrackToolKit_*.log' }
}
$latest = $logs | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($latest) {
    Select-String -LiteralPath $latest.FullName -Pattern 'ProcessMonitor|SimulatorManager|GSProJsonClient|LPGolf_IsReady failed' |
        Select-Object -Last 25 -ExpandProperty Line
}
