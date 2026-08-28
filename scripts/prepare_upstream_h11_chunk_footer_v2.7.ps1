$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$benchmarkRoot = Join-Path $projectRoot "external-workspaces\upstream-h11-chunk-footer-v2.7"

if (Test-Path -LiteralPath $benchmarkRoot) {
    throw "Benchmark directory already exists: $benchmarkRoot"
}

$repository = "python-hyper/h11"
$repositoryName = "h11"
$parentCommit = "31e626c64e1e28db3cd73a6aa0ac057f1b915c18"
$fixCommit = "dff7cc397a26ed4acdedd92d1bda6c8f18a6ed9f"
$parentExpectedHash = "47B2775922ECAC85B42A16D8B9FB634747DD80B31868C2832DA3E28E179DE9B4"
$fixExpectedHash = "251D7CAB68C49C87078149F223B696F9BE3AEA052BF013613BB4660544ED2645"

$downloads = Join-Path $benchmarkRoot "downloads"
$extracted = Join-Path $benchmarkRoot "extracted"
New-Item -ItemType Directory -Path $downloads, $extracted | Out-Null

$parentArchive = Join-Path $downloads "parent.zip"
$fixArchive = Join-Path $downloads "fix.zip"
Invoke-WebRequest -Uri "https://codeload.github.com/$repository/zip/$parentCommit" -OutFile $parentArchive
Invoke-WebRequest -Uri "https://codeload.github.com/$repository/zip/$fixCommit" -OutFile $fixArchive

$parentHash = (Get-FileHash -LiteralPath $parentArchive -Algorithm SHA256).Hash
$fixHash = (Get-FileHash -LiteralPath $fixArchive -Algorithm SHA256).Hash
if ($parentHash -ne $parentExpectedHash) {
    throw "Parent archive checksum mismatch: expected $parentExpectedHash, got $parentHash"
}
if ($fixHash -ne $fixExpectedHash) {
    throw "Fix archive checksum mismatch: expected $fixExpectedHash, got $fixHash"
}

$parentExtracted = Join-Path $extracted "parent"
$fixExtracted = Join-Path $extracted "fix"
Expand-Archive -LiteralPath $parentArchive -DestinationPath $parentExtracted
Expand-Archive -LiteralPath $fixArchive -DestinationPath $fixExtracted

$parentSource = Join-Path $parentExtracted "$repositoryName-$parentCommit"
$fixSource = Join-Path $fixExtracted "$repositoryName-$fixCommit"
$buggy = Join-Path $benchmarkRoot "buggy"
$fixedReference = Join-Path $benchmarkRoot "fixed-reference"
Copy-Item -LiteralPath $parentSource -Destination $buggy -Recurse
Copy-Item -LiteralPath $fixSource -Destination $fixedReference -Recurse

$testFile = "h11/tests/test_io.py"
$implementationFile = "h11/_readers.py"
$fixTest = Join-Path $fixSource ($testFile -replace "/", "\")
$buggyTest = Join-Path $buggy ($testFile -replace "/", "\")
Copy-Item -LiteralPath $fixTest -Destination $buggyTest -Force

if ((Get-FileHash $buggyTest -Algorithm SHA256).Hash -ne (Get-FileHash $fixTest -Algorithm SHA256).Hash) {
    throw "Regression test copy verification failed: $testFile"
}

$parentImplementation = Join-Path $parentSource ($implementationFile -replace "/", "\")
$buggyImplementation = Join-Path $buggy ($implementationFile -replace "/", "\")
if ((Get-FileHash $parentImplementation -Algorithm SHA256).Hash -ne (Get-FileHash $buggyImplementation -Algorithm SHA256).Hash) {
    throw "Parent implementation was modified during preparation: $implementationFile"
}

$metadata = [ordered]@{
    id = "h11-chunk-footer-validation"
    repository = "https://github.com/$repository"
    parent_commit = $parentCommit
    fix_commit = $fixCommit
    parent_archive_sha256 = $parentHash
    fix_archive_sha256 = $fixHash
    imported_regression_tests = @($testFile)
    protected_upstream_implementation = @($implementationFile)
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $benchmarkRoot "provenance.json") -Encoding utf8

Write-Host "Prepared h11-chunk-footer-validation"
Write-Host "Root: $benchmarkRoot"
Write-Host "Manifest: $(Join-Path $projectRoot 'evals\upstream-h11-chunk-footer-v2.7.json')"
