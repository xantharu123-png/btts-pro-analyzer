param([switch]$DryRun)
$ErrorActionPreference = 'Stop'
$descriptorWorkspace = 'C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910'
function Read-DescriptorHeld([string]$Path, [long]$Cap, [string]$Pin) {
    if ((Get-Item -LiteralPath $Path).Length -gt $Cap) { throw 'Descriptor input bound' }
    $held = [IO.File]::ReadAllBytes($Path)
    if ($held.Length -gt $Cap -or [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($held)).ToLowerInvariant() -ne $Pin) { throw "Descriptor input pin: $Path" }
    return ,$held
}
$descriptorTemplate = Read-DescriptorHeld (Join-Path $descriptorWorkspace '.superpowers/sdd/2026-09-10-context-capacity-recovery/evidence/task63-native-unit-entry.py') 65536 'bb0e4a79d89a8266d45db81032fcb67f0c1139a75d3396944c36d78546015257'
$descriptorProgram = [Text.UTF8Encoding]::new($false,$true).GetString($descriptorTemplate)
$descriptorArchive = Read-DescriptorHeld (Join-Path $descriptorWorkspace '.pytest_tmp/task63-unit-bb54ec5-01.tar') 1048576 '6d93ed7db2d1fb29167deceda86e4910f0fe99f951a2dfc3cf0f421f89d4ea10'
$descriptorPlaceholder = '"NEW_ARCHIVE_BASE64"'
if ([regex]::Matches($descriptorProgram,[regex]::Escape($descriptorPlaceholder)).Count -ne 1) { throw 'Descriptor placeholder differs' }
$descriptorProgram = $descriptorProgram.Replace($descriptorPlaceholder,'"' + [Convert]::ToBase64String($descriptorArchive) + '"')
$descriptorPayload = [Text.Encoding]::UTF8.GetBytes($descriptorProgram)
if ($descriptorPayload.Length -gt 1048576) { throw 'Descriptor transport bound' }
"stdin_bytes=$($descriptorPayload.Length) stdin_sha256=$([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($descriptorPayload)).ToLowerInvariant()) dry_run=$DryRun"
if ($DryRun) { exit 0 }
$descriptorOutPath = Join-Path $descriptorWorkspace '.pytest_tmp/task63-native-unit-bb54ec5-01.stdout.jsonl'
$descriptorErrPath = Join-Path $descriptorWorkspace '.pytest_tmp/task63-native-unit-bb54ec5-01.stderr.log'
$descriptorOut = [IO.File]::Open($descriptorOutPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
try {
    $descriptorErr = [IO.File]::Open($descriptorErrPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
    try {
        $descriptorStart = [Diagnostics.ProcessStartInfo]::new('ssh')
        $descriptorStart.UseShellExecute=$false
        $descriptorStart.CreateNoWindow=$true
        $descriptorStart.RedirectStandardInput=$true
        $descriptorStart.RedirectStandardOutput=$true
        $descriptorStart.RedirectStandardError=$true
        # Whole ordinary-user test tree, including setup and child subprocesses; no retry.
        # No --foreground or --preserve-status: timeout is a failed terminal result.
        $descriptorRemote = 'exec env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/time -f "TASK63_UNIT exit=%x wall=%e user=%U sys=%S rss_kib=%M" /usr/bin/timeout --signal=TERM --kill-after=5s 90s /usr/bin/python3 -I -S -B -'
        foreach ($descriptorArg in @('-T','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3','betboy-vps',$descriptorRemote)) { $descriptorStart.ArgumentList.Add($descriptorArg) }
        $descriptorProcess = [Diagnostics.Process]::Start($descriptorStart)
        $descriptorOutTask=$descriptorProcess.StandardOutput.BaseStream.CopyToAsync($descriptorOut)
        $descriptorErrTask=$descriptorProcess.StandardError.BaseStream.CopyToAsync($descriptorErr)
        $descriptorProcess.StandardInput.BaseStream.Write($descriptorPayload)
        $descriptorProcess.StandardInput.BaseStream.Flush()
        $descriptorProcess.StandardInput.Close()
        $descriptorClock=[Diagnostics.Stopwatch]::StartNew()
        $descriptorNext=30
        while (-not $descriptorProcess.WaitForExit(1000)) {
            if ($descriptorClock.Elapsed.TotalSeconds -ge $descriptorNext) { "descriptor_waiting_seconds=$([int]$descriptorClock.Elapsed.TotalSeconds); no retry"; $descriptorNext+=30 }
        }
        [void]$descriptorOutTask.GetAwaiter().GetResult()
        [void]$descriptorErrTask.GetAwaiter().GetResult()
        $descriptorOut.Flush($true)
        $descriptorErr.Flush($true)
    } finally { $descriptorErr.Dispose() }
} finally { $descriptorOut.Dispose() }
"ssh_exit=$($descriptorProcess.ExitCode)"
Get-Content -Raw -LiteralPath $descriptorOutPath
Get-Content -Raw -LiteralPath $descriptorErrPath
Get-Item -LiteralPath $descriptorOutPath,$descriptorErrPath | Select-Object Name,Length | ConvertTo-Json -Compress
Get-FileHash -LiteralPath $descriptorOutPath,$descriptorErrPath -Algorithm SHA256 | Format-List
exit $descriptorProcess.ExitCode


