param(
    [switch]$BuildSandbox
)

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venv = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    $systemPython = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $systemPython) {
        throw "Python was not found. Install Python 3.10 or newer and open a new terminal."
    }
    & $systemPython -m venv $venv
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the RepoFix virtual environment."
    }
}

& $venvPython -m pip install -e "$projectRoot[dev]"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install RepoFix and its development dependencies."
}

if ($BuildSandbox) {
    & (Join-Path $PSScriptRoot "build_sandbox.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build the RepoFix Docker sandbox image."
    }
}

Write-Host "RepoFix project setup complete."
Write-Host "Python: $venvPython"
Write-Host "Next: .\scripts\setup_deepseek.ps1"
Write-Host "Demo: .\scripts\run_demo.ps1"
