param()

$ErrorActionPreference = 'Stop'
$blindRoot = 'C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\B-M9R2'
$reviewRoot = 'C:\Users\admin\OneDrive\Desktop\26国赛\题库\B题\2023\揭晓后参考'
$outputPath = Join-Path $reviewRoot '00-盲解冻结\盲解文件清单-v001.json'

$freezeLocal = Get-Date
$freezeUtc = $freezeLocal.ToUniversalTime()

function Get-RelativeNormalized([string]$base, [string]$path) {
    return [System.IO.Path]::GetRelativePath($base, $path).Replace('\', '/')
}

function Test-IsInput([string]$rel) {
    return $rel -in @('题目.pdf', 'AGENTS.md', 'README.md', '总控提示词.md', '第一步-材料审计与题目理解.md') -or
        $rel.StartsWith('附件/') -or $rel.StartsWith('方法库/')
}

function Test-IsPaper([string]$rel) {
    return $rel.StartsWith('工作记录/论文/') -and $rel -match '\.(md|tex|pdf)$'
}

function Test-IsCode([string]$rel) {
    return $rel.StartsWith('工作记录/代码/') -and $rel -match '\.(py|mjs|ps1|md)$'
}

function Test-IsNumericEvidence([string]$rel) {
    return $rel.StartsWith('工作记录/诊断结果/') -or
        $rel.StartsWith('工作记录/结果/') -or
        $rel -in @('result1.xlsx', 'result2.xlsx')
}

function Test-IsCurrent([string]$rel) {
    if ($rel -match '__pycache__|\.pyc$') { return $false }
    if ($rel -in @(
        'result1.xlsx',
        'result2.xlsx',
        '工作记录/结果/Q03/第3问测线设计-v001.xlsx',
        '工作记录/结果/Q04/第4问测线设计-v001.xlsx',
        '工作记录/论文/第1问-模型建立与求解-v002.md',
        '工作记录/论文/第1问-正文证据映射-v002.md',
        '工作记录/论文/第2问-模型建立与求解-v001.md',
        '工作记录/论文/第2问-正文证据映射-v001.md',
        '工作记录/论文/第3问-模型建立与求解-v001.md',
        '工作记录/论文/第3问-正文证据映射-v001.md',
        '工作记录/论文/第4问-模型建立与求解-v001.md',
        '工作记录/论文/第4问-正文证据映射-v001.md',
        '工作记录/论文/全题整合/完整论文-v001.md',
        '工作记录/论文/全题整合/完整论文-v001.tex',
        '工作记录/论文/全题整合/完整论文-v001.pdf',
        '工作记录/论文/全题整合/结果与来源表-v001.md',
        '工作记录/论文/全题整合/正文证据映射-v001.md',
        '工作记录/论文/全题整合/可复现说明-v001.md',
        '工作记录/论文/全题整合/学术修订记录-v001.md',
        '工作记录/00-任务状态.md',
        '工作记录/记录索引.md',
        '工作记录/归档清单.md',
        '工作记录/方法库查阅记录.md',
        '工作记录/决策记录.md',
        '工作记录/06-更新记录.md'
    )) { return $true }
    if ($rel -match '^工作记录/阶段记录/(S00|S01|S02|Q0[1-4])-.*-v001\.md$') { return $true }
    if ($rel -match '^工作记录/代码/Q0[1-4]/.*\.(py|mjs|md)$') { return $true }
    if ($rel -match '^工作记录/诊断结果/Q0[1-4]/q0[1-4]_.*\.(json|ndjson)$') { return $true }
    if ($rel -match '^工作记录/结果/Q0[1-4]/.*\.(xlsx|csv)$') { return $true }
    return $false
}

function Test-IsCore([string]$rel) {
    if ($rel -in @(
        'result1.xlsx',
        'result2.xlsx',
        '工作记录/结果/Q03/第3问测线设计-v001.xlsx',
        '工作记录/结果/Q04/第4问测线设计-v001.xlsx',
        '工作记录/结果/Q01/result1-v001.xlsx',
        '工作记录/结果/Q02/result2-v001.xlsx',
        '工作记录/论文/第1问-模型建立与求解-v002.md',
        '工作记录/论文/全题整合/完整论文-v001.md',
        '工作记录/论文/全题整合/完整论文-v001.tex',
        '工作记录/论文/全题整合/完整论文-v001.pdf',
        '工作记录/论文/全题整合/结果与来源表-v001.md',
        '工作记录/论文/全题整合/正文证据映射-v001.md',
        '工作记录/论文/第1问-正文证据映射-v002.md',
        '工作记录/论文/第2问-模型建立与求解-v001.md',
        '工作记录/论文/第2问-正文证据映射-v001.md',
        '工作记录/论文/第3问-模型建立与求解-v001.md',
        '工作记录/论文/第3问-正文证据映射-v001.md',
        '工作记录/论文/第4问-模型建立与求解-v001.md',
        '工作记录/论文/第4问-正文证据映射-v001.md'
    )) { return $true }
    if ($rel -match '^工作记录/阶段记录/Q0[1-4]-第[1-4]问结果-v001\.md$') { return $true }
    if ($rel -match '^工作记录/代码/Q0[1-4]/.*\.(py|mjs|md)$') { return $true }
    if ($rel -match '^工作记录/诊断结果/Q0[1-4]/q0[1-4]_.*\.(json|ndjson)$') { return $true }
    if ($rel -eq '工作记录/诊断结果/论文PDF核验-v001.json') { return $true }
    return $false
}

$records = foreach ($file in Get-ChildItem -LiteralPath $blindRoot -Recurse -File | Sort-Object FullName) {
    $rel = Get-RelativeNormalized $blindRoot $file.FullName
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $isInput = Test-IsInput $rel
    $isPaper = Test-IsPaper $rel
    $isCode = Test-IsCode $rel
    $isEvidence = Test-IsNumericEvidence $rel
    $isCore = Test-IsCore $rel
    $isCurrent = Test-IsCurrent $rel
    [ordered]@{
        absolute_path = $file.FullName
        relative_path = $rel
        extension = $file.Extension.ToLowerInvariant()
        media_type_group = if ($isInput) { 'input' } elseif ($isPaper) { 'paper' } elseif ($isCode) { 'code' } elseif ($isEvidence) { 'numeric_evidence' } else { 'record_or_support' }
        size_bytes = [int64]$file.Length
        sha256 = $hash
        current_effective_version = $isCurrent
        core_result = $isCore
        belongs_to_paper = $isPaper
        belongs_to_code = $isCode
        belongs_to_numeric_evidence = $isEvidence
        belongs_to_input_material = $isInput
        creation_time_local = $file.CreationTime.ToString('yyyy-MM-ddTHH:mm:ss.fffffffK')
        last_write_time_local = $file.LastWriteTime.ToString('yyyy-MM-ddTHH:mm:ss.fffffffK')
        frozen_hash_verified_after_manifest = $false
    }
}

$manifest = [ordered]@{
    schema_version = 'blind-solution-freeze-manifest-v001'
    task_mapping_revealed_after_freeze_authorization = '2023年全国大学生数学建模竞赛本科生组B题'
    blind_workspace = $blindRoot
    freeze_time_local = $freezeLocal.ToString('yyyy-MM-ddTHH:mm:ss.fffffffK')
    freeze_time_utc = $freezeUtc.ToString('yyyy-MM-ddTHH:mm:ss.fffffffZ')
    hashing_algorithm = 'SHA-256'
    file_count = @($records).Count
    core_file_count = @($records | Where-Object { $_.core_result }).Count
    current_effective_file_count = @($records | Where-Object { $_.current_effective_version }).Count
    total_size_bytes = [int64](($records | ForEach-Object { $_['size_bytes'] } | Measure-Object -Sum).Sum)
    rule = '从冻结时间起，任何通过互联网、官方信息或优秀论文获得的新认识均属于揭晓后认识，不得写成盲解阶段原有结论。'
    files = @($records)
}

$json = $manifest | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($outputPath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
Write-Output ([pscustomobject]@{
    schema_version = $manifest['schema_version']
    freeze_time_local = $manifest['freeze_time_local']
    file_count = $manifest['file_count']
    core_file_count = $manifest['core_file_count']
    current_effective_file_count = $manifest['current_effective_file_count']
    total_size_bytes = $manifest['total_size_bytes']
} | ConvertTo-Json)
Write-Output "OUTPUT=$outputPath"
