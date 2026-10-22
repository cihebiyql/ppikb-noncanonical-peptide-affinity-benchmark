$ErrorActionPreference='Stop'
$diagRoot=$PSScriptRoot
$target=Join-Path $diagRoot 'actual_get_content_wait.synthetic.json'
[System.IO.File]::WriteAllText($target, '{"synthetic_only":true,"reader_ready_marker":true}')
$reader=Start-Job -ScriptBlock {
    param($ownedTarget)
    Write-Output ('owned_reader_pid=' + $PID)
    Get-Content -LiteralPath $ownedTarget -Wait
} -ArgumentList $target
$clock=[System.Diagnostics.Stopwatch]::StartNew()
$ready=$false
$ownedReaderPid=$null
try {
    while ($clock.Elapsed.TotalSeconds -lt 8) {
        $messages=@(Receive-Job -Job $reader -Keep)
        foreach ($message in $messages) {
            if ([string]$message -like 'owned_reader_pid=*') {$ownedReaderPid=([string]$message).Split('=')[1]}
            if ([string]$message -like '*reader_ready_marker*') {$ready=$true}
        }
        if ($ready) {break}
        Start-Sleep -Milliseconds 100
    }
    if (-not $ready) {throw 'Own synthetic Get-Content reader did not become ready'}
    $wslRoot='/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021/control/recovery-diagnosis-v1'
    & wsl.exe -d Ubuntu-22.04 -u root -- /root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python "$wslRoot/atomic_replace_probe.py" --target "$wslRoot/actual_get_content_wait.synthetic.json" --receipt "$wslRoot/actual_get_content_wait.receipt.json" --scenario actual_Get_Content_Wait 1> (Join-Path $diagRoot 'actual_get_content_wait.stdout.json') 2> (Join-Path $diagRoot 'actual_get_content_wait.stderr.txt')
    [PSCustomObject]@{own_job_id=$reader.Id; own_reader_pid=$ownedReaderPid; synthetic_reader_ready=$ready; wsl_probe_exit=$LASTEXITCODE} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $diagRoot 'actual_get_content_wait.command-receipt.json') -Encoding utf8
} finally {
    Stop-Job -Job $reader -ErrorAction SilentlyContinue
    Remove-Job -Job $reader -Force -ErrorAction SilentlyContinue
}
