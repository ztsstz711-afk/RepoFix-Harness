$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$benchmarkRoot = Join-Path $projectRoot "external-workspaces\upstream-click-help-v3.6"

if (Test-Path -LiteralPath $benchmarkRoot) {
    throw "Benchmark directory already exists: $benchmarkRoot"
}

$repository = "pallets/click"
$repositoryName = "click"
$parentCommit = "04ef3a6f473deb2499721a8d11f92a7d2c0912f2"
$fixCommit = "1458800409ed12076f18451889b0857db36aa522"
$parentExpectedHash = "3FC294E523DCEE35928EDD27A98F549A1EC24E2ABD7352FEC947E668DD4EDCAB"
$fixExpectedHash = "39B2C14FB55C876352822AA1DED3466E8DE4F52B67B298D2DDD518891ADD7CC8"

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

$testFile = "tests/test_options.py"
$implementationFile = "src/click/core.py"
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
    id = "click-help-strict-equality"
    repository = "https://github.com/$repository"
    issue = "https://github.com/pallets/click/issues/3298"
    pull_request = "https://github.com/pallets/click/pull/3299"
    parent_commit = $parentCommit
    fix_commit = $fixCommit
    parent_archive_sha256 = $parentHash
    fix_archive_sha256 = $fixHash
    imported_regression_tests = @($testFile)
    protected_upstream_implementation = @($implementationFile)
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $benchmarkRoot "provenance.json") -Encoding utf8

Write-Host "Prepared click-help-strict-equality"
Write-Host "Root: $benchmarkRoot"
Write-Host "Manifest: $(Join-Path $projectRoot 'evals\upstream-click-help-v3.6.json')"
