param(
    [string]$Suite = "evals\demo.json"
)

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment not found. Run python -m venv .venv and install the project first."
}

$names = @(
    "REPOFIX_API_KEY",
    "REPOFIX_BASE_URL",
    "REPOFIX_MODEL",
    "REPOFIX_INPUT_COST_PER_MILLION",
    "REPOFIX_CACHED_INPUT_COST_PER_MILLION",
    "REPOFIX_OUTPUT_COST_PER_MILLION"
)
foreach ($name in $names) {
    $value = [Environment]::GetEnvironmentVariable($name, "User")
    if ($value) {
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

if ([string]::IsNullOrWhiteSpace($env:REPOFIX_API_KEY)) {
    throw "REPOFIX_API_KEY is not configured. Run a provider setup script first."
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$suitePath = (Resolve-Path (Join-Path $projectRoot $Suite)).Path
$suiteName = [System.IO.Path]::GetFileNameWithoutExtension($suitePath)
$output = Join-Path $projectRoot "eval-results\$suiteName-$stamp"

Write-Host "RepoFix isolated demo"
Write-Host "Model: $env:REPOFIX_MODEL"
Write-Host "Output: $output"

Push-Location $projectRoot
try {
    & $python -m repofix.eval_cli --suite $suitePath --output $output
    $demoExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

if ($demoExitCode -ne 0) {
    throw "RepoFix demo failed with exit code $demoExitCode."
}
