param([switch]$DryRun)
$ErrorActionPreference = 'Stop'
$unitWorkspace = 'C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910'
function Read-UnitHeld([string]$Path, [long]$Cap, [string]$Pin) {
    if ((Get-Item -LiteralPath $Path).Length -gt $Cap) { throw 'Unit input bound' }
    $held = [IO.File]::ReadAllBytes($Path)
    if ($held.Length -gt $Cap -or [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($held)).ToLowerInvariant() -ne $Pin) { throw "Unit input pin: $Path" }
    return ,$held
}
$unitTemplate = Read-UnitHeld (Join-Path $unitWorkspace '.superpowers/sdd/2026-09-10-context-capacity-recovery/evidence/task62-native-unit-entry.py') 65536 '3f290ec20e4a14c613e3866e0ae9ad92ac0dd70cc77599f66eb001a99f55c00e'
$unitProgram = [Text.UTF8Encoding]::new($false,$true).GetString($unitTemplate)
$unitInputs = [ordered]@{
    NEW_ARCHIVE_BASE64 = Read-UnitHeld (Join-Path $unitWorkspace '.pytest_tmp/task62-unit-6eb267a-01.tar') 1048576 '817d2ed8a7f529881537d6007c136b829267c6452182cbc923c91a465ce04e6d'
    OLD_ARCHIVE_BASE64 = Read-UnitHeld (Join-Path $unitWorkspace '.pytest_tmp/task62-previous-68c1ff8-01.tar') 1048576 '69ee6d43caa2f1d95ed5af5ced9d3f4aeda79023c74bf27447f8baca75a6d1a0'
}
foreach ($unitName in $unitInputs.Keys) {
    $unitPlaceholder = '"' + $unitName + '"'
    if ([regex]::Matches($unitProgram,[regex]::Escape($unitPlaceholder)).Count -ne 1) { throw 'Unit placeholder differs' }
    $unitProgram = $unitProgram.Replace($unitPlaceholder,'"' + [Convert]::ToBase64String($unitInputs[$unitName]) + '"')
}
$unitPayload = [Text.Encoding]::UTF8.GetBytes($unitProgram)
if ($unitPayload.Length -gt 1048576) { throw 'Unit transport bound' }
"stdin_bytes=$($unitPayload.Length) stdin_sha256=$([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($unitPayload)).ToLowerInvariant()) dry_run=$DryRun"
if ($DryRun) { exit 0 }
$unitOutPath = Join-Path $unitWorkspace '.pytest_tmp/task62-native-unit-6eb267a-01.stdout.jsonl'
$unitErrPath = Join-Path $unitWorkspace '.pytest_tmp/task62-native-unit-6eb267a-01.stderr.log'
$unitOut = [IO.File]::Open($unitOutPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
try {
    $unitErr = [IO.File]::Open($unitErrPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
    try {
        $unitStart = [Diagnostics.ProcessStartInfo]::new('ssh')
        $unitStart.UseShellExecute=$false
        $unitStart.CreateNoWindow=$true
        $unitStart.RedirectStandardInput=$true
        $unitStart.RedirectStandardOutput=$true
        $unitStart.RedirectStandardError=$true
        # External deadline starts before Python/archive setup and includes both children.
        # No --foreground or --preserve-status: timeout remains a failed terminal result.
        $unitRemote = 'exec env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/time -f "TASK62_UNIT exit=%x wall=%e user=%U sys=%S rss_kib=%M" /usr/bin/timeout --signal=TERM --kill-after=5s 210s /usr/bin/python3 -I -S -B -'
        foreach ($unitArg in @('-T','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3','betboy-vps',$unitRemote)) { $unitStart.ArgumentList.Add($unitArg) }
        $unitProcess = [Diagnostics.Process]::Start($unitStart)
        $unitOutTask=$unitProcess.StandardOutput.BaseStream.CopyToAsync($unitOut)
        $unitErrTask=$unitProcess.StandardError.BaseStream.CopyToAsync($unitErr)
        $unitProcess.StandardInput.BaseStream.Write($unitPayload)
        $unitProcess.StandardInput.BaseStream.Flush()
        $unitProcess.StandardInput.Close()
        $unitClock=[Diagnostics.Stopwatch]::StartNew()
        $unitNext=30
        while (-not $unitProcess.WaitForExit(1000)) {
            if ($unitClock.Elapsed.TotalSeconds -ge $unitNext) { "unit_waiting_seconds=$([int]$unitClock.Elapsed.TotalSeconds); no retry"; $unitNext+=30 }
        }
        [void]$unitOutTask.GetAwaiter().GetResult()
        [void]$unitErrTask.GetAwaiter().GetResult()
        $unitOut.Flush($true)
        $unitErr.Flush($true)
    } finally { $unitErr.Dispose() }
} finally { $unitOut.Dispose() }
"ssh_exit=$($unitProcess.ExitCode)"
Get-Content -Raw -LiteralPath $unitOutPath
Get-Content -Raw -LiteralPath $unitErrPath
Get-Item -LiteralPath $unitOutPath,$unitErrPath | Select-Object Name,Length | ConvertTo-Json -Compress
Get-FileHash -LiteralPath $unitOutPath,$unitErrPath -Algorithm SHA256 | Format-List
exit $unitProcess.ExitCode
