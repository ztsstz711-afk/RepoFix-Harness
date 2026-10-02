$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dockerfile = Join-Path $projectRoot "sandbox\Dockerfile"
$buildContext = Join-Path $projectRoot "sandbox"
$baseImage = "python:3.12-slim"
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

# BuildKit occasionally cannot obtain Docker Hub auth metadata through some
# desktop proxy routes. Reuse a local pinned base image when available; only
# contact the registry when a new machine does not yet have it.
& $docker image inspect $baseImage *> $null
if ($LASTEXITCODE -ne 0) {
    & $docker pull $baseImage
    if ($LASTEXITCODE -ne 0) {
        throw "RepoFix sandbox base image pull failed with exit code $LASTEXITCODE. Check Docker Desktop network/proxy settings, then retry."
    }
}

& $docker build --pull=false --tag repofix-pytest:latest --file $dockerfile $buildContext
if ($LASTEXITCODE -ne 0) {
    throw "RepoFix sandbox image build failed with exit code $LASTEXITCODE."
}
