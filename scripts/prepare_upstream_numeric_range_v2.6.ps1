$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$benchmarkRoot = Join-Path $projectRoot "external-workspaces\upstream-numeric-range-v2.6"

if (Test-Path -LiteralPath $benchmarkRoot) {
    throw "Benchmark directory already exists: $benchmarkRoot"
}

$repository = "more-itertools/more-itertools"
$repositoryName = "more-itertools"
$parentCommit = "247e15b3a489d5805375c95dfa79486c9bd0eb1b"
$fixCommit = "edb3346f835ca917efbfda5e2d6664ab952da369"
$parentExpectedHash = "D2D39F52F258CEF07E27AD65C44FBCCCECB1267EC78D45C68455FB09E267BE5C"
$fixExpectedHash = "5B568172373DE1C0C7EDC70E512C4BD25DEC5E8DA9D21814E0E79B238EF9A50B"

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

$testFile = "tests/test_more.py"
$implementationFile = "more_itertools/more.py"
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
    id = "more-itertools-numeric-range-empty-reversed"
    repository = "https://github.com/$repository"
    parent_commit = $parentCommit
    fix_commit = $fixCommit
    parent_archive_sha256 = $parentHash
    fix_archive_sha256 = $fixHash
    imported_regression_tests = @($testFile)
    protected_upstream_implementation = @($implementationFile)
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $benchmarkRoot "provenance.json") -Encoding utf8

Write-Host "Prepared more-itertools-numeric-range-empty-reversed"
Write-Host "Root: $benchmarkRoot"
Write-Host "Manifest: $(Join-Path $projectRoot 'evals\upstream-numeric-range-v2.6.json')"
