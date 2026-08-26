$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dockerfile = Join-Path $projectRoot "sandbox\Dockerfile"
$docker = (Get-Command docker -ErrorAction SilentlyContinue).Source
if (-not $docker) {
    $candidate = Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin\docker.exe"
    if (Test-Path -LiteralPath $candidate) {
        $docker = $candidate
    }
}
if (-not $docker) {
    throw "Docker CLI not found. Install Docker Desktop and open a new terminal."
}
$dockerBin = Split-Path -Parent $docker
$env:Path = "$dockerBin;$env:Path"

& $docker build --tag repofix-pytest:latest --file $dockerfile (Join-Path $projectRoot "sandbox")
if ($LASTEXITCODE -ne 0) {
    throw "RepoFix sandbox image build failed with exit code $LASTEXITCODE."
}
