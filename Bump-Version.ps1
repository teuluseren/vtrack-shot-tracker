[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('minor', 'feature', 'major')]
    [string]$Type
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$versionPath = Join-Path $projectRoot 'vtrack_version.py'
$content = [System.IO.File]::ReadAllText($versionPath)
$pattern = '(?m)^__version__\s*=\s*"(?<major>0|[1-9]\d*)\.(?<minor>0|[1-9]\d*)\.(?<patch>0|[1-9]\d*)"\s*$'
$match = [regex]::Match($content, $pattern)

if (-not $match.Success) {
    throw 'Could not find a stable x.y.z __version__ value in vtrack_version.py.'
}

$major = [int]$match.Groups['major'].Value
$minor = [int]$match.Groups['minor'].Value
$patch = [int]$match.Groups['patch'].Value
$oldVersion = "$major.$minor.$patch"

switch ($Type.ToLowerInvariant()) {
    'minor' {
        # A small compatible correction: SemVer patch bump.
        $patch++
    }
    'feature' {
        # A compatible feature release: SemVer minor bump.
        $minor++
        $patch = 0
    }
    'major' {
        # A breaking or first stable release: SemVer major bump.
        $major++
        $minor = 0
        $patch = 0
    }
}

$newVersion = "$major.$minor.$patch"
$replacement = "__version__ = `"$newVersion`""
$updated = [regex]::Replace($content, $pattern, $replacement, 1)
[System.IO.File]::WriteAllText($versionPath, $updated, [System.Text.UTF8Encoding]::new($false))

Write-Host "VTrack version bumped: $oldVersion -> $newVersion ($Type)"
Write-Host 'Next: update CHANGELOG.md, then run .\packaging\build.ps1'
