param(
    [string]$Suite = "evals\demo.json",
    [string]$Output = "",
    [switch]$Resume
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
if ($Resume -and [string]::IsNullOrWhiteSpace($Output)) {
    throw "-Resume requires -Output with the existing evaluation directory."
}
if ([string]::IsNullOrWhiteSpace($Output)) {
    $outputPath = Join-Path $projectRoot "eval-results\$suiteName-$stamp"
}
elseif ([System.IO.Path]::IsPathRooted($Output)) {
    $outputPath = [System.IO.Path]::GetFullPath($Output)
}
else {
    $outputPath = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $Output))
}

Write-Host "RepoFix isolated demo"
Write-Host "Model: $env:REPOFIX_MODEL"
Write-Host "Output: $outputPath"

Push-Location $projectRoot
try {
    $arguments = @("-m", "repofix.eval_cli", "--suite", $suitePath, "--output", $outputPath)
    if ($Resume) {
        $arguments += "--resume"
    }
    & $python @arguments
    $demoExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

if ($demoExitCode -ne 0) {
    throw "RepoFix demo failed with exit code $demoExitCode."
}
