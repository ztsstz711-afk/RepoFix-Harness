$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$benchmarkRoot = Join-Path $projectRoot "external-workspaces\upstream-bugs-v1.5"

if (Test-Path -LiteralPath $benchmarkRoot) {
    throw "Benchmark directory already exists: $benchmarkRoot"
}

$cases = @(
    @{
        Id = "more-itertools-sliced-negative"
        Repository = "more-itertools/more-itertools"
        ParentCommit = "ed86a1528aa015f219f8d3385ea2ebd3f63a5212"
        FixCommit = "958990e22c4ab6daf434d89cf2b86d7a4a7a9e3c"
        ParentHash = "41D40F5D92AD22564A47E8551C84C3907B836D3C25003654276D509251CF2A8B"
        FixHash = "14B5ED2F4B99CBCABB5CE24FE7F041B2E94B896A37E25C8DBACF040FF93938B8"
        TestFiles = @("tests/test_more.py")
        ImplementationFiles = @("more_itertools/more.py")
    },
    @{
        Id = "more-itertools-running-stability"
        Repository = "more-itertools/more-itertools"
        ParentCommit = "cb75bb9c55f7ed3e77ce599097e1ba8da411746d"
        FixCommit = "d992be0de9383ddcaae3a24866a2d96b52132b07"
        ParentHash = "41FE8319EFA12487731047FD7A905F9A55803BE2EE0EC3594E142F85E1FEE94C"
        FixHash = "97AEAD57062C8F36AAFAD7B504BAEB851041AB5120352F62ADA8290EF960A685"
        TestFiles = @("tests/test_more.py")
        ImplementationFiles = @("more_itertools/recipes.py")
    },
    @{
        Id = "tomli-key-parts-limit"
        Repository = "hukkin/tomli"
        ParentCommit = "c20c49113890c226ffb27a67befe20d14fcf0c73"
        FixCommit = "e1fdb94bc998377f1c2545c7cd4f70ff2a3fb4e4"
        ParentHash = "BF9001D791D8DE9B1C95FC42A02CB419376C9E0382CE69F4F73A2E194266F9E5"
        FixHash = "4DEBDB98D94BF7BD642FEC8A2ED31A2DD0CA6178ADB64072601F328901E92D9D"
        TestFiles = @("tests/test_misc.py")
        ImplementationFiles = @("src/tomli/_parser.py")
    }
)

New-Item -ItemType Directory -Path $benchmarkRoot | Out-Null

foreach ($case in $cases) {
    $caseRoot = Join-Path $benchmarkRoot $case.Id
    $downloads = Join-Path $caseRoot "downloads"
    $extracted = Join-Path $caseRoot "extracted"
    New-Item -ItemType Directory -Path $downloads, $extracted | Out-Null

    $repositoryName = ($case.Repository -split "/")[-1]
    $parentArchive = Join-Path $downloads "parent.zip"
    $fixArchive = Join-Path $downloads "fix.zip"
    $parentUrl = "https://codeload.github.com/$($case.Repository)/zip/$($case.ParentCommit)"
    $fixUrl = "https://codeload.github.com/$($case.Repository)/zip/$($case.FixCommit)"

    Invoke-WebRequest -Uri $parentUrl -OutFile $parentArchive
    Invoke-WebRequest -Uri $fixUrl -OutFile $fixArchive

    $parentHash = (Get-FileHash -LiteralPath $parentArchive -Algorithm SHA256).Hash
    $fixHash = (Get-FileHash -LiteralPath $fixArchive -Algorithm SHA256).Hash
    if ($parentHash -ne $case.ParentHash) {
        throw "$($case.Id) parent archive checksum mismatch: expected $($case.ParentHash), got $parentHash"
    }
    if ($fixHash -ne $case.FixHash) {
        throw "$($case.Id) fix archive checksum mismatch: expected $($case.FixHash), got $fixHash"
    }

    $parentExtracted = Join-Path $extracted "parent"
    $fixExtracted = Join-Path $extracted "fix"
    Expand-Archive -LiteralPath $parentArchive -DestinationPath $parentExtracted
    Expand-Archive -LiteralPath $fixArchive -DestinationPath $fixExtracted

    $parentSource = Join-Path $parentExtracted "$repositoryName-$($case.ParentCommit)"
    $fixSource = Join-Path $fixExtracted "$repositoryName-$($case.FixCommit)"
    $buggy = Join-Path $caseRoot "buggy"
    $fixedReference = Join-Path $caseRoot "fixed-reference"
    Copy-Item -LiteralPath $parentSource -Destination $buggy -Recurse
    Copy-Item -LiteralPath $fixSource -Destination $fixedReference -Recurse

    foreach ($relativeTest in $case.TestFiles) {
        $sourceTest = Join-Path $fixSource ($relativeTest -replace "/", "\")
        $targetTest = Join-Path $buggy ($relativeTest -replace "/", "\")
        Copy-Item -LiteralPath $sourceTest -Destination $targetTest -Force
        $sourceTestHash = (Get-FileHash -LiteralPath $sourceTest -Algorithm SHA256).Hash
        $targetTestHash = (Get-FileHash -LiteralPath $targetTest -Algorithm SHA256).Hash
        if ($sourceTestHash -ne $targetTestHash) {
            throw "$($case.Id) regression test copy verification failed: $relativeTest"
        }
    }

    foreach ($relativeImplementation in $case.ImplementationFiles) {
        $parentImplementation = Join-Path $parentSource ($relativeImplementation -replace "/", "\")
        $buggyImplementation = Join-Path $buggy ($relativeImplementation -replace "/", "\")
        $parentImplementationHash = (Get-FileHash -LiteralPath $parentImplementation -Algorithm SHA256).Hash
        $buggyImplementationHash = (Get-FileHash -LiteralPath $buggyImplementation -Algorithm SHA256).Hash
        if ($parentImplementationHash -ne $buggyImplementationHash) {
            throw "$($case.Id) parent implementation was modified during preparation: $relativeImplementation"
        }
    }

    $metadata = [ordered]@{
        id = $case.Id
        repository = "https://github.com/$($case.Repository)"
        parent_commit = $case.ParentCommit
        fix_commit = $case.FixCommit
        parent_archive_sha256 = $parentHash
        fix_archive_sha256 = $fixHash
        imported_regression_tests = $case.TestFiles
        protected_upstream_implementation = $case.ImplementationFiles
    }
    $metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $caseRoot "provenance.json") -Encoding utf8
    Write-Host "Prepared $($case.Id)"
}

Write-Host "Prepared three upstream regression workspaces."
Write-Host "Root: $benchmarkRoot"
Write-Host "Manifest: $(Join-Path $projectRoot 'evals\upstream-bugs-v1.5.json')"
