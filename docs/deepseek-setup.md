# DeepSeek setup

RepoFix uses the same `OpenAICompatibleProvider` for Gemini and DeepSeek. Switching providers changes environment variables only; Agent Loop, tools, permissions, evaluation, and artifacts remain unchanged.

## Configure

```powershell
.\scripts\setup_deepseek.ps1
```

The script reads the key as a `SecureString`, stores it in the current Windows user's environment, and never writes it to the repository. It configures:

- `REPOFIX_BASE_URL=https://api.deepseek.com`
- `REPOFIX_MODEL=deepseek-v4-flash`
- conservative peak-hour input, cached-input, and output prices for cost estimation

The endpoint and model follow the official DeepSeek OpenAI-compatible API documentation checked on 2026-08-26. Pricing remains an estimate; provider billing is authoritative.

## Verify without exposing the key

After opening a new terminal, verify only whether configuration exists:

```powershell
$model = [Environment]::GetEnvironmentVariable("REPOFIX_MODEL", "User")
$key = [Environment]::GetEnvironmentVariable("REPOFIX_API_KEY", "User")
Write-Host "Model=$model KeyConfigured=$([bool]$key)"
```

Do not print `$key` and do not paste it into chat, `.env`, screenshots, or Git.
