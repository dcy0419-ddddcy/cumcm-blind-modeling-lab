param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[ABC]-[A-Z0-9]{4}$')]
    [string]$BlindId,

    [Parameter(Mandatory = $false)]
    [string]$DestinationRoot = 'C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$source = Join-Path 'C:\Users\admin\OneDrive\Desktop\26国赛-盲解题库' $BlindId
if (-not (Test-Path -LiteralPath $source)) {
    throw "盲题不存在：$BlindId"
}

$destination = Join-Path $DestinationRoot $BlindId
if (Test-Path -LiteralPath $destination) {
    throw "目标目录已存在，为避免覆盖历史记录已停止：$destination"
}

New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -Path (Join-Path $source '*') -Destination $destination -Recurse -Force
Copy-Item -LiteralPath (Join-Path $repoRoot 'prompts\00-总控提示词.md') -Destination (Join-Path $destination '总控提示词.md')

Write-Output "已导出到：$destination"
Write-Output '请仅把该目录作为 Codex 工作区，不要把 26国赛 主仓库同时加入工作区。'
