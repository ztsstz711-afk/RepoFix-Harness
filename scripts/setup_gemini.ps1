param(
    [string]$Model = "gemini-3.5-flash-lite"
)

$secureKey = Read-Host "Paste your Gemini API key (input is hidden)" -AsSecureString
$plainKey = [System.Net.NetworkCredential]::new("", $secureKey).Password

if ([string]::IsNullOrWhiteSpace($plainKey)) {
    throw "API key cannot be empty."
}

$baseUrl = "https://generativelanguage.googleapis.com/v1beta/openai/"

[Environment]::SetEnvironmentVariable("REPOFIX_API_KEY", $plainKey, "User")
[Environment]::SetEnvironmentVariable("REPOFIX_BASE_URL", $baseUrl, "User")
[Environment]::SetEnvironmentVariable("REPOFIX_MODEL", $Model, "User")

$env:REPOFIX_API_KEY = $plainKey
$env:REPOFIX_BASE_URL = $baseUrl
$env:REPOFIX_MODEL = $Model

Remove-Variable plainKey
Write-Host "Gemini configuration saved for RepoFix-Harness."
Write-Host "Model: $Model"
Write-Host "Open a new terminal before running RepoFix outside this script."
