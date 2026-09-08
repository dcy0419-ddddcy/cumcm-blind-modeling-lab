param()

$ErrorActionPreference = 'Stop'
$reviewRoot = 'C:\Users\admin\OneDrive\Desktop\26国赛\题库\B题\2023\揭晓后参考'
$manifestPath = Join-Path $reviewRoot '00-盲解冻结\盲解文件清单-v001.json'
$auditPath = Join-Path $reviewRoot '10-审计结果\冻结后核心哈希复核-v001.json'

$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$comparisons = @()
foreach ($record in $manifest.files | Where-Object { $_.core_result }) {
    $exists = Test-Path -LiteralPath $record.absolute_path -PathType Leaf
    $actual = if ($exists) { (Get-FileHash -LiteralPath $record.absolute_path -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    $matched = $exists -and $actual -eq $record.sha256
    $record.frozen_hash_verified_after_manifest = $matched
    $comparisons += [pscustomobject]@{
        relative_path = $record.relative_path
        expected_sha256 = $record.sha256
        actual_sha256 = $actual
        exists = $exists
        matched = $matched
    }
}

$allMatched = ($comparisons | Where-Object { -not $_.matched }).Count -eq 0
$manifestJson = $manifest | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($manifestPath, $manifestJson + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))

$audit = [ordered]@{
    schema_version = 'blind-solution-freeze-verification-v001'
    freeze_time_local = $manifest.freeze_time_local
    verification_time_local = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss.fffffffK')
    manifest_path = $manifestPath
    core_file_count = $comparisons.Count
    matched_count = @($comparisons | Where-Object { $_.matched }).Count
    all_core_hashes_matched = $allMatched
    comparisons = $comparisons
}
$auditJson = $audit | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($auditPath, $auditJson + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
Write-Output ([pscustomobject]@{
    freeze_time_local = $manifest.freeze_time_local
    verification_time_local = $audit['verification_time_local']
    core_file_count = $audit['core_file_count']
    matched_count = $audit['matched_count']
    all_core_hashes_matched = $audit['all_core_hashes_matched']
    audit_path = $auditPath
} | ConvertTo-Json)
if (-not $allMatched) { throw '冻结后核心文件哈希复核失败' }
