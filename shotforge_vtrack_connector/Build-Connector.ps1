param([string]$Python = 'python.exe', [string]$OutputDirectory = '')
$ErrorActionPreference = 'Stop'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw '.NET Framework C# compiler was not found.' }
$pythonExe = (Get-Command $Python -ErrorAction Stop).Source
& $pythonExe -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10 or newer is required"'
if ($LASTEXITCODE -ne 0) { throw 'Python verification failed.' }
$output = if ($OutputDirectory) { [System.IO.Path]::GetFullPath($OutputDirectory) } else { Join-Path $PSScriptRoot 'dist' }
New-Item -ItemType Directory -Path $output -Force | Out-Null
# Check every destination before compiling any of them, avoiding a partially
# updated bundle when an active connector still holds one executable open.
foreach ($name in @('GSPLauncher', 'GSPro', 'GSPconnect')) {
    $destination = Join-Path $output "$name.exe"
    if (Test-Path -LiteralPath $destination) {
        try {
            $probe = [System.IO.File]::Open($destination, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
            $probe.Dispose()
        } catch { throw "Close the connector before rebuilding; $name.exe is in use." }
    }
}
foreach ($name in @('GSPLauncher', 'GSPro', 'GSPconnect')) {
    & $compiler /nologo /target:winexe /platform:x64 /optimize+ "/out:$output\$name.exe" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll (Join-Path $PSScriptRoot 'CompatibilityHost.cs')
    if ($LASTEXITCODE -ne 0) { throw "Failed to build $name.exe. Close the connector before rebuilding." }
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'bridge.py') -Destination $output
$configPath = Join-Path $output 'connector.json'
if (-not (Test-Path -LiteralPath $configPath)) {
    $config = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'connector.example.json') -Raw | ConvertFrom-Json
    $config.python = $pythonExe
    $config | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8
}
Write-Output "Built connector: $output\GSPLauncher.exe"
Write-Output 'Set this as the GSPro executable in VTrackToolKit. ShotForge opens automatically when needed.'
