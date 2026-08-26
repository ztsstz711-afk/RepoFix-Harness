$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$benchmarkRoot = Join-Path $projectRoot "external-workspaces\h11-benchmark"
$archive = Join-Path $benchmarkRoot "h11-v0.16.0.zip"
$extractRoot = Join-Path $benchmarkRoot "extracted"
$expectedHash = "6CC72241F709C9400E5DD44252A519906C842EB6EDEC4E01A70DA148A1145FC8"
$sourceUrl = "https://codeload.github.com/python-hyper/h11/zip/refs/tags/v0.16.0"

if (Test-Path -LiteralPath $benchmarkRoot) {
    throw "Benchmark directory already exists: $benchmarkRoot"
}

New-Item -ItemType Directory -Path $benchmarkRoot | Out-Null
Invoke-WebRequest -Uri $sourceUrl -OutFile $archive
$actualHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
if ($actualHash -ne $expectedHash) {
    throw "h11 archive checksum mismatch: expected $expectedHash, got $actualHash"
}

Expand-Archive -LiteralPath $archive -DestinationPath $extractRoot
$source = Join-Path $extractRoot "h11-0.16.0"
$clean = Join-Path $benchmarkRoot "clean"
$buggy = Join-Path $benchmarkRoot "buggy"
Copy-Item -LiteralPath $source -Destination $clean -Recurse
Copy-Item -LiteralPath $source -Destination $buggy -Recurse

$target = Join-Path $buggy "h11\_headers.py"
$old = '    if request.http_version < b"1.1":'
$new = '    if request.http_version <= b"1.1":'
$content = [System.IO.File]::ReadAllText($target)
$matches = ([regex]::Matches($content, [regex]::Escape($old))).Count
if ($matches -ne 1) {
    throw "Expected one injection point in h11/_headers.py, found $matches"
}
[System.IO.File]::WriteAllText($target, $content.Replace($old, $new))

Write-Host "Prepared clean and buggy h11 v0.16.0 workspaces."
Write-Host "Clean: $clean"
Write-Host "Buggy: $buggy"
Write-Host "Manifest: $(Join-Path $projectRoot 'evals\external-h11.json')"
