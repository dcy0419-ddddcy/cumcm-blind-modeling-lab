[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$PythonPath,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$NodePath,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$NodeModulesPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$workspaceRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$attachmentRoot = [System.IO.Path]::GetFullPath((Join-Path $workspaceRoot '附件'))
$workspacePrefix = $workspaceRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) +
    [System.IO.Path]::DirectorySeparatorChar

if (-not ($attachmentRoot + [System.IO.Path]::DirectorySeparatorChar).StartsWith(
        $workspacePrefix,
        [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Attachment path escapes the annual problem directory: $attachmentRoot"
}

$pythonExe = (Resolve-Path -LiteralPath $PythonPath).Path
$nodeExe = (Resolve-Path -LiteralPath $NodePath).Path
$nodeModules = (Resolve-Path -LiteralPath $NodeModulesPath).Path

if ((Get-Item -LiteralPath $pythonExe).PSIsContainer) {
    throw "PythonPath must be an executable file: $pythonExe"
}
if ((Get-Item -LiteralPath $nodeExe).PSIsContainer) {
    throw "NodePath must be an executable file: $nodeExe"
}
if (-not (Get-Item -LiteralPath $nodeModules).PSIsContainer) {
    throw "NodeModulesPath must be a directory: $nodeModules"
}

$inputAliases = @(
    @{ Source = '附件1.csv'; Target = '附件01.csv' },
    @{ Source = '附件2.csv'; Target = '附件02.csv' },
    @{ Source = '附件3.csv'; Target = '附件03.csv' },
    @{ Source = '附件4.xlsx'; Target = '附件04.xlsx' }
)

$createdAliases = [System.Collections.Generic.List[string]]::new()

try {
    foreach ($mapping in $inputAliases) {
        $sourcePath = [System.IO.Path]::GetFullPath(
            (Join-Path $attachmentRoot $mapping.Source))
        $targetPath = [System.IO.Path]::GetFullPath(
            (Join-Path $attachmentRoot $mapping.Target))

        foreach ($candidate in @($sourcePath, $targetPath)) {
            if (-not $candidate.StartsWith(
                    $attachmentRoot + [System.IO.Path]::DirectorySeparatorChar,
                    [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Input alias path escapes the attachment directory: $candidate"
            }
        }

        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            throw "Required annual attachment is missing: $sourcePath"
        }
        if (Test-Path -LiteralPath $targetPath) {
            throw "Refusing to overwrite an existing blind input alias: $targetPath"
        }

        Copy-Item -LiteralPath $sourcePath -Destination $targetPath
        $createdAliases.Add($targetPath)
    }

    & $pythonExe (Join-Path $PSScriptRoot 'solve_all.py')
    if ($LASTEXITCODE -ne 0) {
        throw "solve_all.py failed with exit code $LASTEXITCODE"
    }

    & (Join-Path $PSScriptRoot 'build_result.ps1') `
        -NodePath $nodeExe `
        -NodeModulesPath $nodeModules
    if ($LASTEXITCODE -ne 0) {
        throw "build_result.ps1 failed with exit code $LASTEXITCODE"
    }

    & $pythonExe (Join-Path $PSScriptRoot 'make_paper_figures.py')
    if ($LASTEXITCODE -ne 0) {
        throw "make_paper_figures.py failed with exit code $LASTEXITCODE"
    }

    Write-Output "Reproduction completed in $workspaceRoot"
}
finally {
    foreach ($aliasPath in $createdAliases) {
        if (Test-Path -LiteralPath $aliasPath -PathType Leaf) {
            Remove-Item -LiteralPath $aliasPath -Force
        }
    }
}
