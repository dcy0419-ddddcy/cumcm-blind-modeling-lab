[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$NodePath,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$NodeModulesPath,

    [switch]$KeepQaArtifacts
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$workspaceRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$workspacePrefix = $workspaceRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) +
    [System.IO.Path]::DirectorySeparatorChar

function Resolve-WorkspaceChild {
    param([Parameter(Mandatory = $true)][string]$Candidate)
    $full = [System.IO.Path]::GetFullPath($Candidate)
    if (-not $full.StartsWith($workspacePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path escapes the isolated workspace: $full"
    }
    return $full
}

$nodeFull = [System.IO.Path]::GetFullPath($NodePath)
$modulesFull = [System.IO.Path]::GetFullPath($NodeModulesPath)
$builderPath = Resolve-WorkspaceChild (Join-Path $PSScriptRoot 'build_result.mjs')
$junctionPath = Resolve-WorkspaceChild (Join-Path $PSScriptRoot 'node_modules')
$qaDirectory = Resolve-WorkspaceChild (Join-Path $workspaceRoot '.artifact_build')
$inspectSidecar = Resolve-WorkspaceChild (Join-Path $workspaceRoot 'result.xlsx.inspect.ndjson')

if (-not (Test-Path -LiteralPath $nodeFull -PathType Leaf)) {
    throw "Bundled Node.js executable not found: $nodeFull"
}
if (-not (Test-Path -LiteralPath $modulesFull -PathType Container)) {
    throw "Bundled node_modules directory not found: $modulesFull"
}
if (-not (Test-Path -LiteralPath $builderPath -PathType Leaf)) {
    throw "Workbook builder not found: $builderPath"
}
if (Test-Path -LiteralPath $junctionPath) {
    throw "Refusing to replace existing path: $junctionPath"
}
if (Test-Path -LiteralPath $qaDirectory) {
    throw "Refusing to reuse existing QA directory: $qaDirectory"
}
if (Test-Path -LiteralPath $inspectSidecar) {
    throw "Refusing to overwrite existing inspect sidecar: $inspectSidecar"
}

$junctionCreated = $false
$locationPushed = $false
try {
    New-Item -ItemType Junction -Path $junctionPath -Target $modulesFull | Out-Null
    $junctionCreated = $true

    Push-Location -LiteralPath $workspaceRoot
    $locationPushed = $true
    & $nodeFull $builderPath
    if ($LASTEXITCODE -ne 0) {
        throw "Workbook builder failed with exit code $LASTEXITCODE"
    }
}
finally {
    if ($locationPushed) {
        Pop-Location
    }

    if ($junctionCreated -and (Test-Path -LiteralPath $junctionPath)) {
        $junction = Get-Item -LiteralPath $junctionPath -Force
        if (-not ($junction.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
            throw "Cleanup stopped because the temporary dependency path is not a junction"
        }
        [System.IO.Directory]::Delete($junctionPath, $false)
    }

    if (-not $KeepQaArtifacts) {
        if (Test-Path -LiteralPath $qaDirectory) {
            $qaItem = Get-Item -LiteralPath $qaDirectory -Force
            if ($qaItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                throw "Cleanup stopped because the QA directory is a reparse point"
            }
            [System.IO.Directory]::Delete($qaDirectory, $true)
        }
        if (Test-Path -LiteralPath $inspectSidecar -PathType Leaf) {
            [System.IO.File]::Delete($inspectSidecar)
        }
    }
}

$resultPath = Resolve-WorkspaceChild (Join-Path $workspaceRoot 'result.xlsx')
if (-not (Test-Path -LiteralPath $resultPath -PathType Leaf)) {
    throw "Expected workbook was not created: $resultPath"
}
Write-Output "Workbook created and verified: $resultPath"
