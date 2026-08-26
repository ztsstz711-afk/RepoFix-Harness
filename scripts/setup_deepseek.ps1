param(
    [string]$Model = "deepseek-v4-flash"
)

$secureKey = Read-Host "Paste your DeepSeek API key (input is hidden)" -AsSecureString
$plainKey = [System.Net.NetworkCredential]::new("", $secureKey).Password

if ([string]::IsNullOrWhiteSpace($plainKey)) {
    throw "API key cannot be empty."
}

$baseUrl = "https://api.deepseek.com"

# Conservative peak-hour prices in USD per 1M tokens, checked 2026-08-26.
$inputPrice = "0.44"
$cachedInputPrice = "0.014"
$outputPrice = "1.32"

[Environment]::SetEnvironmentVariable("REPOFIX_API_KEY", $plainKey, "User")
[Environment]::SetEnvironmentVariable("REPOFIX_BASE_URL", $baseUrl, "User")
[Environment]::SetEnvironmentVariable("REPOFIX_MODEL", $Model, "User")
[Environment]::SetEnvironmentVariable("REPOFIX_INPUT_COST_PER_MILLION", $inputPrice, "User")
[Environment]::SetEnvironmentVariable("REPOFIX_CACHED_INPUT_COST_PER_MILLION", $cachedInputPrice, "User")
[Environment]::SetEnvironmentVariable("REPOFIX_OUTPUT_COST_PER_MILLION", $outputPrice, "User")

$env:REPOFIX_API_KEY = $plainKey
$env:REPOFIX_BASE_URL = $baseUrl
$env:REPOFIX_MODEL = $Model
$env:REPOFIX_INPUT_COST_PER_MILLION = $inputPrice
$env:REPOFIX_CACHED_INPUT_COST_PER_MILLION = $cachedInputPrice
$env:REPOFIX_OUTPUT_COST_PER_MILLION = $outputPrice

Remove-Variable plainKey
Remove-Variable secureKey
Write-Host "DeepSeek configuration saved for RepoFix-Harness."
Write-Host "Model: $Model"
Write-Host "Cost estimate uses conservative peak-hour prices."
Write-Host "Open a new terminal before running RepoFix outside this script."
