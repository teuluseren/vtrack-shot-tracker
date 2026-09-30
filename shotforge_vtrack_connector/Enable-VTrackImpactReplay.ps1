param([string]$SettingsPath = '')
$ErrorActionPreference = 'Stop'

# VTrack saves settings on exit, so changing the file while it runs would be lost.
if (Get-Process -Name LPGAgent -ErrorAction SilentlyContinue) {
    throw 'Close VTrackToolKit before enabling impact replay, then run this script again.'
}
if (-not $SettingsPath) {
    $packages = Join-Path $env:LOCALAPPDATA 'Packages'
    $candidates = @(Get-ChildItem -LiteralPath $packages -Directory -Filter '02ce737d-b4f8-4bbb-92b2-1355681ff1e8_*' |
        ForEach-Object { Join-Path $_.FullName 'LocalState\LAON PEOPLE\VTrackToolKit\Settings.xml' } |
        Where-Object { Test-Path -LiteralPath $_ })
    if ($candidates.Count -ne 1) {
        throw 'Cannot identify one VTrack Settings.xml. Specify its full path with -SettingsPath.'
    }
    $SettingsPath = $candidates[0]
}
$resolvedPath = (Resolve-Path -LiteralPath $SettingsPath).Path
$document = New-Object System.Xml.XmlDocument
$document.PreserveWhitespace = $true
$document.Load($resolvedPath)
$game = $document.SelectSingleNode('/*/GlobalGame')
if (-not $game -or -not $game.HasAttribute('IsEnableOverlay')) {
    throw 'This Settings.xml does not contain the expected VTrack impact-overlay setting.'
}
if ($game.GetAttribute('IsEnableOverlay') -eq 'true') {
    Write-Output 'VTrack impact replay is already enabled.'
    return
}
$backup = $resolvedPath + '.shotforge-' + [Guid]::NewGuid().ToString('N') + '.bak'
$temporary = $resolvedPath + '.shotforge-' + [Guid]::NewGuid().ToString('N') + '.tmp'
try {
    $game.SetAttribute('IsEnableOverlay', 'true')
    $document.Save($temporary)
    # Atomically replace the settings, preserving a backup of the original.
    [System.IO.File]::Replace($temporary, $resolvedPath, $backup)
} finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary }
}
Write-Output "Enabled VTrack impact replay. Original settings saved to: $backup"
