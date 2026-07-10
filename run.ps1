$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
  Write-Host "Virtual environment not found. Running setup first..."
  & .\setup.ps1
}

if (-not (Test-Path .\models\mobile_sam.pt)) {
  throw "models\mobile_sam.pt was not found. Smart annotation requires MobileSAM. Restore the models folder or download the release zip that includes the model."
}

& .\.venv\Scripts\python.exe -m smart_labelimg.app
