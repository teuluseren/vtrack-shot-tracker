param(
    [string]$Python = 'python',
    [string]$FFmpegPath,
    [string]$IsccPath,
    [switch]$SkipInstaller,
    [switch]$SkipPortable
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$DistRoot = Join-Path $ProjectRoot 'dist'
$BuildRoot = Join-Path $ProjectRoot 'build\pyinstaller'
$BundleRoot = Join-Path $DistRoot 'VTrackShotTracker'

function New-PortableZip {
    param(
        [Parameter(Mandatory = $true)][string]$SourceDirectory,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem

    if (Test-Path -LiteralPath $DestinationPath) {
        Remove-Item -LiteralPath $DestinationPath -Force
    }

    $source = (Resolve-Path -LiteralPath $SourceDirectory).Path.TrimEnd('\')
    $stream = [System.IO.File]::Open(
        $DestinationPath,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
    )

    try {
        $archive = New-Object System.IO.Compression.ZipArchive(
            $stream,
            [System.IO.Compression.ZipArchiveMode]::Create,
            $false
        )

        try {
            Get-ChildItem -LiteralPath $source -Recurse -File | ForEach-Object {
                $relative = $_.FullName.Substring($source.Length).TrimStart('\')
                $zipName = $relative.Replace('\', '/')

                # pywebview's Android JAR is irrelevant to the Windows build.
                # Skip it even if an older PyInstaller hook happened to copy it.
                if ($zipName -ieq 'webview/lib/pywebview-android.jar') {
                    Write-Host "Skipping unused $zipName"
                    return
                }

                [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                    $archive,
                    $_.FullName,
                    $zipName,
                    [System.IO.Compression.CompressionLevel]::Optimal
                ) | Out-Null
            }
        }
        finally {
            $archive.Dispose()
        }
    }
    catch {
        $stream.Dispose()
        Remove-Item -LiteralPath $DestinationPath -Force -ErrorAction SilentlyContinue
        throw
    }
    finally {
        if ($stream) { $stream.Dispose() }
    }
}

Push-Location $ProjectRoot
try {
    $PythonPrefix = @()
    if ((Split-Path -Leaf $Python) -match '^py(?:\.exe)?$') { $PythonPrefix = @('-3') }

    $Version = (& $Python @PythonPrefix -c 'from vtrack_version import __version__; print(__version__)').Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Could not read the application version.' }
    if ($Version -notmatch '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$') {
        throw "Version '$Version' is not valid SemVer."
    }
    $NumericVersion = "$($Matches[1]).$($Matches[2]).$($Matches[3]).0"

    if (-not $FFmpegPath) {
        $ffmpeg = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
        if ($ffmpeg) { $FFmpegPath = $ffmpeg.Source }
    }

    if ($FFmpegPath) {
        $env:VTRACK_FFMPEG = (Resolve-Path -LiteralPath $FFmpegPath).Path
        Write-Host "Bundling FFmpeg from $env:VTRACK_FFMPEG"
    }
    else {
        Remove-Item Env:VTRACK_FFMPEG -ErrorAction SilentlyContinue
        Write-Warning 'FFmpeg was not found. The package will require ffmpeg.exe on PATH for replay generation.'
    }

    & $Python @PythonPrefix -m PyInstaller --noconfirm --clean --distpath $DistRoot --workpath $BuildRoot packaging\VTrackShotTracker.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }

    Copy-Item packaging\Start-VTrackShotTracker.ps1 $BundleRoot -Force
    Copy-Item packaging\Stop-VTrackShotTracker.ps1 $BundleRoot -Force
    Copy-Item README.md $BundleRoot -Force

    # Build the installer first. A portable-ZIP issue should never prevent the
    # installer from being produced.
    $InstallerPath = Join-Path $DistRoot "VTrackShotTracker-Setup-$Version.exe"
    if (-not $SkipInstaller) {
        if (-not $IsccPath) {
            $candidates = @(
                (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
                (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
                (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
            )
            $IsccPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        }

        if (-not $IsccPath -or -not (Test-Path -LiteralPath $IsccPath)) {
            throw 'Inno Setup 6 was not found. Install it or pass -SkipInstaller.'
        }

        & $IsccPath "/DAppVersion=$Version" "/DNumericVersion=$NumericVersion" "/DSourceDir=$BundleRoot" "/DOutputDir=$DistRoot" packaging\VTrackShotTracker.iss
        if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed.' }
        Write-Host "Created $InstallerPath" -ForegroundColor Green
    }

    $PortableZip = Join-Path $DistRoot "VTrackShotTracker-$Version-portable.zip"
    if (-not $SkipPortable) {
        New-PortableZip -SourceDirectory $BundleRoot -DestinationPath $PortableZip
        Write-Host "Created $PortableZip" -ForegroundColor Green
    }

    $ChecksumArtifacts = @()
    if (-not $SkipPortable -and (Test-Path -LiteralPath $PortableZip)) {
        $ChecksumArtifacts += $PortableZip
    }
    if (-not $SkipInstaller -and (Test-Path -LiteralPath $InstallerPath)) {
        $ChecksumArtifacts += $InstallerPath
    }

    if ($ChecksumArtifacts.Count -gt 0) {
        $ChecksumLines = $ChecksumArtifacts | ForEach-Object {
            $Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_).Hash.ToLowerInvariant()
            "$Hash  $(Split-Path -Leaf $_)"
        }
        $ChecksumPath = Join-Path $DistRoot "VTrackShotTracker-$Version-SHA256SUMS.txt"
        Set-Content -LiteralPath $ChecksumPath -Value $ChecksumLines -Encoding ascii
        Write-Host "Created $ChecksumPath" -ForegroundColor Green
    }
}
finally {
    Pop-Location
}
