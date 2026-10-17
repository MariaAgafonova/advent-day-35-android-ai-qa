param([switch]$DownloadMaestro)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
uv sync --project tools/android-ai-qa --frozen
if ($LASTEXITCODE -ne 0) { throw 'Python environment setup failed' }
if ($DownloadMaestro) {
    New-Item -ItemType Directory -Force .tools | Out-Null
    $archive = Join-Path $PSScriptRoot '.tools/maestro.zip'
    if (-not (Test-Path -LiteralPath $archive)) {
        Invoke-WebRequest 'https://github.com/mobile-dev-inc/maestro/releases/download/cli-2.11.0/maestro.zip' -OutFile $archive
    }
    $expected = '5384593CB4E7A106489E75A821D157DD43F4E438DF6BC308B72E82C685E1283A'
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected) { throw 'Maestro archive checksum mismatch' }
    if (-not (Test-Path -LiteralPath '.tools/maestro/bin/maestro.bat')) {
        Expand-Archive -LiteralPath $archive -DestinationPath .tools
    }
}
Write-Output 'Activate: .\tools\android-ai-qa\.venv\Scripts\Activate.ps1'
Write-Output 'Then: python -m android_qa doctor'
