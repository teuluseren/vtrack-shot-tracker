param([string]$Python = 'python.exe', [string]$PythonArchive = '')
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$version = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'version.txt') -Raw).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$') { throw 'Invalid connector version.' }
$runtimeVersion = '3.13.15'
$runtimeHash = 'd1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf'
$buildRoot = Join-Path $repoRoot ('build\connector-package-' + [Guid]::NewGuid().ToString('N'))
$name = "ShotForgeVTrackConnector-$version-windows-x64"
$bundle = Join-Path $buildRoot $name
New-Item -ItemType Directory -Path $bundle -Force | Out-Null
if (-not $PythonArchive) {
    $PythonArchive = Join-Path $buildRoot "python-$runtimeVersion-embed-amd64.zip"
    Invoke-WebRequest -UseBasicParsing -Uri "https://www.python.org/ftp/python/$runtimeVersion/python-$runtimeVersion-embed-amd64.zip" -OutFile $PythonArchive
}
$PythonArchive = (Resolve-Path -LiteralPath $PythonArchive).Path
if ((Get-FileHash -LiteralPath $PythonArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $runtimeHash) {
    throw 'Embedded Python archive does not match the pinned official SHA-256 checksum.'
}
& (Join-Path $PSScriptRoot 'Build-Connector.ps1') -Python $Python -OutputDirectory $bundle
$runtime = Join-Path $bundle 'python'
Expand-Archive -LiteralPath $PythonArchive -DestinationPath $runtime
$config = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'connector.example.json') -Raw | ConvertFrom-Json
$config.python = 'python\python.exe'
$config | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $bundle 'connector.json') -Encoding UTF8
foreach ($file in @('README.md', 'QUICKSTART.txt', 'RELEASE_NOTES.md', 'THIRD_PARTY_NOTICES.md', 'version.txt', 'Enable-VTrackImpactReplay.ps1', 'Diagnose-Connector.ps1')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination $bundle
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'connector.example.json') -Destination $bundle
Copy-Item -LiteralPath (Join-Path $repoRoot 'LICENSE') -Destination $bundle
Copy-Item -LiteralPath (Join-Path $repoRoot 'COMMERCIAL_LICENSE.md') -Destination $bundle
# Exercise the exact shipped runtime and script before creating the download.
& (Join-Path $runtime 'python.exe') (Join-Path $bundle 'bridge.py') --help | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Packaged Python runtime could not start the bridge.' }
$output = Join-Path $repoRoot 'dist'
New-Item -ItemType Directory -Path $output -Force | Out-Null
$zip = Join-Path $output "$name.zip"
Compress-Archive -LiteralPath $bundle -DestinationPath $zip -Force
$digest = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
"$digest  $name.zip" | Set-Content -LiteralPath (Join-Path $output "ShotForgeVTrackConnector-$version-SHA256SUMS.txt") -Encoding ASCII
Write-Output "Package: $zip"
Write-Output "Test bundle: $bundle"
# CI and the local release run use this path to smoke-test the shipped runtime.
$bundle | Set-Content -LiteralPath (Join-Path $output 'connector-test-bundle.txt') -Encoding UTF8
