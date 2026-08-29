$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$caseRoot = Join-Path $projectRoot "external-workspaces\upstream-itsdangerous-separator-v4.0"

if (Test-Path -LiteralPath $caseRoot) {
    throw "Benchmark directory already exists: $caseRoot"
}

$parentCommit = "10d548995409eee7632d911164013112b1b07d9f"
$fixCommit = "ce5e2cd0afebadb5dd732ee1c151824a0de8b5d4"
$parentExpectedHash = "C045C8C0CCC7AF0E723B00949399705A5380BE1A0C41A93A0AE39DD784721C84"
$fixExpectedHash = "10572AA78FF7480982A1273180EBB66855F28270BB5655CE636F516621EB23EB"

$downloads = Join-Path $caseRoot "downloads"
$extracted = Join-Path $caseRoot "extracted"
New-Item -ItemType Directory -Path $downloads, $extracted | Out-Null

$parentArchive = Join-Path $downloads "parent.zip"
$fixArchive = Join-Path $downloads "fix.zip"
Invoke-WebRequest -Uri "https://codeload.github.com/pallets/itsdangerous/zip/$parentCommit" -OutFile $parentArchive
Invoke-WebRequest -Uri "https://codeload.github.com/pallets/itsdangerous/zip/$fixCommit" -OutFile $fixArchive

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

$parentSource = Join-Path $parentExtracted "itsdangerous-$parentCommit"
$fixSource = Join-Path $fixExtracted "itsdangerous-$fixCommit"
$buggy = Join-Path $caseRoot "buggy"
$fixedReference = Join-Path $caseRoot "fixed-reference"
Copy-Item -LiteralPath $parentSource -Destination $buggy -Recurse
Copy-Item -LiteralPath $fixSource -Destination $fixedReference -Recurse
Copy-Item -LiteralPath (Join-Path $fixSource "tests.py") -Destination (Join-Path $buggy "tests.py") -Force

$parentImplementationHash = (Get-FileHash -LiteralPath (Join-Path $parentSource "itsdangerous.py") -Algorithm SHA256).Hash
$buggyImplementationHash = (Get-FileHash -LiteralPath (Join-Path $buggy "itsdangerous.py") -Algorithm SHA256).Hash
if ($parentImplementationHash -ne $buggyImplementationHash) {
    throw "Parent implementation changed while importing the regression test."
}

$fixTestHash = (Get-FileHash -LiteralPath (Join-Path $fixSource "tests.py") -Algorithm SHA256).Hash
$buggyTestHash = (Get-FileHash -LiteralPath (Join-Path $buggy "tests.py") -Algorithm SHA256).Hash
if ($fixTestHash -ne $buggyTestHash) {
    throw "Imported upstream regression test checksum mismatch."
}

$metadata = [ordered]@{
    id = "itsdangerous-unsafe-separator"
    repository = "https://github.com/pallets/itsdangerous"
    parent_commit = $parentCommit
    fix_commit = $fixCommit
    parent_archive_sha256 = $parentHash
    fix_archive_sha256 = $fixHash
    imported_regression_tests = @("tests.py")
    protected_upstream_implementation = @("itsdangerous.py")
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $caseRoot "provenance.json") -Encoding utf8

Write-Host "Prepared checksum-qualified ItsDangerous separator benchmark."
Write-Host "Root: $caseRoot"
Write-Host "Manifest: $(Join-Path $projectRoot 'evals\upstream-itsdangerous-separator-v4.0.json')"
