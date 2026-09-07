$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$exampleFile = Join-Path $taskRoot '方法库/验证/check_examples.py'
$expectedHash = '71b75eeda1a5dbd82d72a700063600524ebc2201afcec20bd4e1f4bcb1977c27'
if ((Get-FileHash -LiteralPath $exampleFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) { throw 'Teaching script changed; reread before execution' }
$resultFile = Join-Path $taskRoot '工作记录/诊断结果/S02-通用例子复核-v001.json'
if (Test-Path -LiteralPath $resultFile) { throw 'Evidence exists; preserve it and use a new version' }
# Existing bundled interpreter previously used in this task; no dependency installation.
$pythonRuntime = 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$resultText = & $pythonRuntime -I -B $exampleFile
$runExitCode = $LASTEXITCODE
$resultText | Set-Content -LiteralPath $resultFile -Encoding UTF8
if ($runExitCode -ne 0) { throw "Teaching checks failed with exit code $runExitCode; output preserved" }
$parsedResult = ($resultText -join "`n") | ConvertFrom-Json
$parsedResult | Select-Object scope, python, dependencies, tests, passed | ConvertTo-Json
