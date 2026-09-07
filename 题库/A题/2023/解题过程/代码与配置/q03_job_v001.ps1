param([string]$Action,[string]$Arg1='', [string]$Arg2='')
$ErrorActionPreference='Stop'
$taskRoot='C:\Users\admin\OneDrive\Desktop\26国赛-单题盲解区\A-P8C3'
Set-Location -LiteralPath $taskRoot
$env:OPENBLAS_NUM_THREADS='1'; $env:OMP_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'
$roundOutput=Join-Path $taskRoot '工作记录/诊断结果/Q03-实施-v001'
$slug=($Action+'-'+$Arg1+'-'+$Arg2) -replace '[^a-zA-Z0-9_-]','_'
$logPath=Join-Path $roundOutput ('run-'+$slug+'-'+[DateTime]::Now.ToString('yyyyMMddHHmmssfff')+'.log')
$clockJob=[Diagnostics.Stopwatch]::StartNew()
& 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -I -B -X utf8 '工作记录/诊断代码/q03_run_v001.py' $Action $Arg1 $Arg2 *> $logPath
$codeJob=$LASTEXITCODE
$ledgerPath=Join-Path $roundOutput '累计计算预算.json'
$ledger=Get-Content -LiteralPath $ledgerPath -Raw | ConvertFrom-Json
$last=$ledger.records[-1]
$clockJob.Stop()
$outside=[Math]::Max(0.,$clockJob.Elapsed.TotalSeconds-[double]$last.elapsed_seconds)
$ledger.used_seconds=[double]$ledger.used_seconds+$outside
$last.elapsed_seconds=[double]$last.elapsed_seconds+$outside
$last | Add-Member -NotePropertyName external_wrapper_wall_seconds -NotePropertyValue $clockJob.Elapsed.TotalSeconds -Force
$last | Add-Member -NotePropertyName included_interpreter_startup_exit_and_log_seconds -NotePropertyValue $outside -Force
$last | Add-Member -NotePropertyName stdout_log -NotePropertyValue $logPath -Force
$ledger | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $ledgerPath -Encoding utf8
Get-Content -LiteralPath $logPath -Tail 2
if($codeJob -ne 0){throw ('Q3 job failed; retained '+$logPath)}
