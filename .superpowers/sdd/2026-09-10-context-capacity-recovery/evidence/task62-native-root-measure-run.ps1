param([switch]$DryRun)
$ErrorActionPreference = 'Stop'
$measureWorkspace = 'C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910'
function Read-MeasureHeld([string]$Path, [long]$Cap, [string]$Pin) {
    if ((Get-Item -LiteralPath $Path).Length -gt $Cap) { throw 'Measure input bound' }
    $held = [IO.File]::ReadAllBytes($Path)
    if ($held.Length -gt $Cap -or [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($held)).ToLowerInvariant() -ne $Pin) { throw "Measure input pin: $Path" }
    return ,$held
}
$measureTemplate = Read-MeasureHeld (Join-Path $measureWorkspace '.superpowers/sdd/2026-09-10-context-capacity-recovery/evidence/task62-native-root-measure.py') 65536 '93272441757aa51c547a18a671c26e64e67c7a88c7d01a3d8cbfb5b6f3d593d6'
$measureProgram = [Text.UTF8Encoding]::new($false,$true).GetString($measureTemplate)
$measureArchive = Read-MeasureHeld (Join-Path $measureWorkspace '.pytest_tmp/task62-unit-6eb267a-01.tar') 1048576 '817d2ed8a7f529881537d6007c136b829267c6452182cbc923c91a465ce04e6d'
$measurePlaceholder = '"NEW_ARCHIVE_BASE64"'
if ([regex]::Matches($measureProgram,[regex]::Escape($measurePlaceholder)).Count -ne 1) { throw 'Measure placeholder differs' }
$measureProgram = $measureProgram.Replace($measurePlaceholder,'"' + [Convert]::ToBase64String($measureArchive) + '"')
$measurePayload = [Text.Encoding]::UTF8.GetBytes($measureProgram)
if ($measurePayload.Length -gt 1048576) { throw 'Measure transport bound' }
"stdin_bytes=$($measurePayload.Length) stdin_sha256=$([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($measurePayload)).ToLowerInvariant()) dry_run=$DryRun"
if ($DryRun) { exit 0 }
$measureOutPath = Join-Path $measureWorkspace '.pytest_tmp/task62-root-measure-6eb267a-01.stdout.jsonl'
$measureErrPath = Join-Path $measureWorkspace '.pytest_tmp/task62-root-measure-6eb267a-01.stderr.log'
$measureOut = [IO.File]::Open($measureOutPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
try {
    $measureErr = [IO.File]::Open($measureErrPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
    try {
        $measureStart = [Diagnostics.ProcessStartInfo]::new('ssh')
        $measureStart.UseShellExecute=$false
        $measureStart.CreateNoWindow=$true
        $measureStart.RedirectStandardInput=$true
        $measureStart.RedirectStandardOutput=$true
        $measureStart.RedirectStandardError=$true
        # Whole single-process read, including imports and archive checks; no retry.
        # No --foreground or --preserve-status: timeout is a failed terminal result.
        $measureRemote = 'exec sudo -n env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/time -f "TASK62_ROOT exit=%x wall=%e user=%U sys=%S rss_kib=%M" /usr/bin/timeout --signal=TERM --kill-after=5s 300s /usr/bin/python3 -I -S -B -'
        foreach ($measureArg in @('-T','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3','betboy-vps',$measureRemote)) { $measureStart.ArgumentList.Add($measureArg) }
        $measureProcess = [Diagnostics.Process]::Start($measureStart)
        $measureOutTask=$measureProcess.StandardOutput.BaseStream.CopyToAsync($measureOut)
        $measureErrTask=$measureProcess.StandardError.BaseStream.CopyToAsync($measureErr)
        $measureProcess.StandardInput.BaseStream.Write($measurePayload)
        $measureProcess.StandardInput.BaseStream.Flush()
        $measureProcess.StandardInput.Close()
        $measureClock=[Diagnostics.Stopwatch]::StartNew()
        $measureNext=30
        while (-not $measureProcess.WaitForExit(1000)) {
            if ($measureClock.Elapsed.TotalSeconds -ge $measureNext) { "measure_waiting_seconds=$([int]$measureClock.Elapsed.TotalSeconds); no retry"; $measureNext+=30 }
        }
        [void]$measureOutTask.GetAwaiter().GetResult()
        [void]$measureErrTask.GetAwaiter().GetResult()
        $measureOut.Flush($true)
        $measureErr.Flush($true)
    } finally { $measureErr.Dispose() }
} finally { $measureOut.Dispose() }
"ssh_exit=$($measureProcess.ExitCode)"
Get-Content -Raw -LiteralPath $measureOutPath
Get-Content -Raw -LiteralPath $measureErrPath
Get-Item -LiteralPath $measureOutPath,$measureErrPath | Select-Object Name,Length | ConvertTo-Json -Compress
Get-FileHash -LiteralPath $measureOutPath,$measureErrPath -Algorithm SHA256 | Format-List
exit $measureProcess.ExitCode
