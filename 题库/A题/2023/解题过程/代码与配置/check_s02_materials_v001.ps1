$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$taskPrefix = $taskRoot.TrimEnd('\') + '\'
$checks = @()
foreach ($packetName in @('方法库','补充资料')) {
    $packetDir = Join-Path $taskRoot $packetName
    $manifestFile = Join-Path $packetDir 'manifest-v001.json'
    $packet = Get-Content -LiteralPath $manifestFile -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($entry in $packet.files) {
        $targetFile = [IO.Path]::GetFullPath((Join-Path $packetDir $entry.path))
        if (-not $targetFile.StartsWith($taskPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Manifest path leaves task workspace' }
        $present = Test-Path -LiteralPath $targetFile -PathType Leaf
        $actualHash = $null
        $size = $null
        if ($present) {
            $actualHash = (Get-FileHash -LiteralPath $targetFile -Algorithm SHA256).Hash.ToLowerInvariant()
            $size = (Get-Item -LiteralPath $targetFile).Length
        }
        $checks += [pscustomobject]@{
            path = $packetName + '/' + $entry.path
            version = $entry.version
            exists = $present
            expected_sha256 = $entry.sha256
            actual_sha256 = $actualHash
            bytes = $size
            bytes_match = ($size -eq $entry.bytes)
            hash_match = ($actualHash -eq $entry.sha256)
            content_screened = $entry.content_screened
            source_checked_by_administrator = $entry.source_checked
            allowed_scope = $entry.allowed_scope
            coverage = $entry.coverage
            excludes = $entry.excludes
            physical_assumption_approved_in_packet = $entry.physical_assumption_approved
        }
    }
}
$result = [pscustomobject]@{
    stage = 'S02-v001'
    purpose = 'Only verify local whitelist files, hashes, versions and permitted scope; not a solver or reading-completion proof'
    checked_at = (Get-Date).ToString('o')
    powershell_version = $PSVersionTable.PSVersion.ToString()
    network_used = $false
    raw_problem_or_attachment_content_read = $false
    seed = $null
    files = $checks
    all_pass = (@($checks | Where-Object { -not ($_.exists -and $_.hash_match -and $_.bytes_match -and $_.content_screened) }).Count -eq 0)
}
$outFile = Join-Path $taskRoot '工作记录/诊断结果/S02-资料入场核对-v001.json'
if (Test-Path -LiteralPath $outFile) { throw 'Evidence already exists; preserve it and use a new version' }
$result | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $outFile -Encoding UTF8
$result | Select-Object stage, checked_at, powershell_version, all_pass, @{Name='file_count';Expression={$_.files.Count}} | ConvertTo-Json
if (-not $result.all_pass) { exit 1 }
