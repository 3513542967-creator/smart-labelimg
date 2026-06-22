param(
  [switch]$SkipAi,
  [switch]$Build
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-BasePython {
  param([string[]]$Arguments)

  if ($env:PYTHON_BIN) {
    & $env:PYTHON_BIN @Arguments
    return
  }
  if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.11 @Arguments
    return
  }
  if (Get-Command python -ErrorAction SilentlyContinue) {
    & python @Arguments
    return
  }
  throw "Python 3.11 is required. Install it from https://www.python.org/downloads/windows/ and run this script again."
}

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
  Invoke-BasePython -Arguments @("-m", "venv", ".venv")
}

$venvPython = ".\.venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt

if (-not $SkipAi) {
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is required to install MobileSAM from requirements-ai.txt. Install Git for Windows, or rerun with -SkipAi for UI-only development."
  }
  & $venvPython -m pip install -r requirements-ai.txt
}

if ($Build) {
  & $venvPython -m pip install -r requirements-build.txt
}

Write-Host "Setup complete."
Write-Host "Run .\run.ps1 to start Smart LabelImg from source."
Write-Host "Run .\build_app.ps1 to build the Windows release package."
