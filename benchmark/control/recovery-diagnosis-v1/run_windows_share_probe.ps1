$ErrorActionPreference = 'Stop'
$diagRoot = $PSScriptRoot
$wslRoot = '/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021/control/recovery-diagnosis-v1'
$pythonPath = '/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python'
$resultRows = [System.Collections.Generic.List[object]]::new()
foreach ($case in @('baseline', 'windows_read_without_delete', 'windows_read_with_delete', 'windows_readwrite_with_delete')) {
    $target = Join-Path $diagRoot ($case + '.synthetic.json')
    [System.IO.File]::WriteAllText($target, '{"synthetic_only":true,"before":true}')
    $handle = $null
    try {
        if ($case -eq 'windows_read_without_delete') {
            $handle = [System.IO.FileStream]::new($target, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
        } elseif ($case -eq 'windows_read_with_delete') {
            $sharing = [System.IO.FileShare]::Read -bor [System.IO.FileShare]::Delete
            $handle = [System.IO.FileStream]::new($target, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, $sharing)
        } elseif ($case -eq 'windows_readwrite_with_delete') {
            $sharing = [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
            $handle = [System.IO.FileStream]::new($target, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, $sharing)
        }
        $stdoutPath = Join-Path $diagRoot ($case + '.stdout.json')
        $stderrPath = Join-Path $diagRoot ($case + '.stderr.txt')
        & wsl.exe -d Ubuntu-22.04 -u root -- $pythonPath "$wslRoot/atomic_replace_probe.py" --target "$wslRoot/$case.synthetic.json" --receipt "$wslRoot/$case.receipt.json" --scenario $case 1> $stdoutPath 2> $stderrPath
        $resultRows.Add([PSCustomObject]@{ scenario=$case; exit_code=$LASTEXITCODE; handle_was_held=($null -ne $handle) })
    } finally {
        if ($null -ne $handle) { $handle.Dispose() }
    }
}
$resultRows | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $diagRoot 'share-probe-command-receipts.json') -Encoding utf8
$resultRows | Format-Table -AutoSize
