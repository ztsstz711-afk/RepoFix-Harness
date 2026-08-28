$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$benchmarkRoot = Join-Path $projectRoot "external-workspaces\upstream-last-v2.5"

if (Test-Path -LiteralPath $benchmarkRoot) {
    throw "Benchmark directory already exists: $benchmarkRoot"
}

$repository = "more-itertools/more-itertools"
$repositoryName = "more-itertools"
$parentCommit = "c834d6e4a0c4280b7b7750cb0de8dd8acb3d4c2c"
$fixCommit = "cca32949f12d473fd823e37a5530c30d2faa1332"
$parentExpectedHash = "F9FC264F4AA1A9E424628495928FECB96EB3A7B594CDAD5E5EF17A1C2032BECA"
$fixExpectedHash = "A5FE924A3A9C663CC2169015FDC7D75481364EFA0324F705F201376FFFDBDB95"

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

$copiedTestHash = (Get-FileHash -LiteralPath $buggyTest -Algorithm SHA256).Hash
$fixTestHash = (Get-FileHash -LiteralPath $fixTest -Algorithm SHA256).Hash
if ($copiedTestHash -ne $fixTestHash) {
    throw "Regression test copy verification failed: $testFile"
}

$parentImplementation = Join-Path $parentSource ($implementationFile -replace "/", "\")
$buggyImplementation = Join-Path $buggy ($implementationFile -replace "/", "\")
$parentImplementationHash = (Get-FileHash -LiteralPath $parentImplementation -Algorithm SHA256).Hash
$buggyImplementationHash = (Get-FileHash -LiteralPath $buggyImplementation -Algorithm SHA256).Hash
if ($parentImplementationHash -ne $buggyImplementationHash) {
    throw "Parent implementation was modified during preparation: $implementationFile"
}

$metadata = [ordered]@{
    id = "more-itertools-last-reversed-none"
    repository = "https://github.com/$repository"
    issue = "https://github.com/more-itertools/more-itertools/issues/1001"
    parent_commit = $parentCommit
    fix_commit = $fixCommit
    parent_archive_sha256 = $parentHash
    fix_archive_sha256 = $fixHash
    imported_regression_tests = @($testFile)
    protected_upstream_implementation = @($implementationFile)
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $benchmarkRoot "provenance.json") -Encoding utf8

Write-Host "Prepared more-itertools-last-reversed-none"
Write-Host "Root: $benchmarkRoot"
Write-Host "Manifest: $(Join-Path $projectRoot 'evals\upstream-last-v2.5.json')"
