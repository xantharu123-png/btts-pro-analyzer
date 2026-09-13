param([Parameter(Mandatory=$true)][ValidateSet('upload','catalogue')][string]$Mode, [switch]$DryRun)
$ErrorActionPreference = 'Stop'
$prepWorkspace = 'C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910'
$prepEvidence = Join-Path $prepWorkspace '.superpowers/sdd/2026-09-10-context-capacity-recovery/evidence'
function Read-PrepHeld([string]$Path, [long]$Cap, [string]$Expected) {
    if ((Get-Item -LiteralPath $Path).Length -gt $Cap) { throw 'Preparation input cap' }
    $heldBytes = [IO.File]::ReadAllBytes($Path)
    if ($heldBytes.Length -gt $Cap -or [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($heldBytes)).ToLowerInvariant() -ne $Expected) { throw "Preparation held pin differs: $Path" }
    return ,$heldBytes
}
$prepTemplateName = if ($Mode -eq 'upload') { 'task61-native-input-upload.py' } else { 'task61-native-catalogue-prepare.py' }
$prepTemplatePin = if ($Mode -eq 'upload') { 'c118672160b6fdcd5f4699e0fd63c6b89d3affeafd28ecaaf62656dc807580f0' } else { '97b605c2b29bcce2d9b401847cc5ea4fb942f591453122e59accddbabcc895e6' }
$prepTemplateBytes = Read-PrepHeld (Join-Path $prepEvidence $prepTemplateName) 65536 $prepTemplatePin
$prepProgram = [Text.UTF8Encoding]::new($false, $true).GetString($prepTemplateBytes)
if ($Mode -eq 'upload') {
    $prepPayload = Read-PrepHeld (Join-Path $prepWorkspace '.pytest_tmp/task61-1632072-01.tar') 67108864 'daf6ac61183bb3a42f8401f7568b2020a0f4bdef07d07a72d295e61363bc4d4c'
    if ($prepPayload.Length -ne 9533440) { throw 'Fixed archive size differs' }
    $prepEncoded = [Convert]::ToBase64String($prepTemplateBytes)
    $prepRemote = 'exec sudo -n env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/time -f "TASK61_PREP exit=%x wall=%e user=%U sys=%S rss_kib=%M" /usr/bin/python3 -I -S -B -c ''import base64;exec(compile(base64.b64decode("' + $prepEncoded + '"),"<reviewed-task61-upload>","exec"))'''
} else {
    $prepPins = [ordered]@{
        'tests/native_context_receipt_diagnostic.py' = '22faafb79d08f956b11693106cf933f4e6c9869f755c6f3e23628b5f5cca17c1'
        'tests/native_context_receipt_diagnostic_catalogue.py' = '8ebd29f82bd8c92a8601adf8a339f9eb27ddbdf7dcb02bcc0f61d56ea03012e8'
        'tests/native_context_chain_catalogue.py' = '48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935'
        'tests/native_context_diagnostic_admission.py' = 'f0b0821195d6ebce89bc47e5d37f21dedc36fc8e223678816a932b1aae5d60ad'
        'context_preparation_process_guard.py' = '62fcfcacaa7e658eefa8a2f8ceced9dc465846a8ca61dc38c2691dc9984685e4'
        'context_preparation_budget.py' = 'fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478'
        'context_preparation_supervisor.py' = 'c6c1c8e82107d48b66d7714577004e7d9e7e400525620b23070d4258ab554dc8'
    }
    $prepBundle = [ordered]@{}
    foreach ($prepName in $prepPins.Keys) { $prepBundle[$prepName] = [Convert]::ToBase64String((Read-PrepHeld (Join-Path $prepWorkspace $prepName) 1048576 $prepPins[$prepName])) }
    $prepValues = [ordered]@{
        BUNDLE_BASE64 = [Text.Encoding]::ASCII.GetBytes(($prepBundle | ConvertTo-Json -Compress))
        JOURNALS_BASE64 = Read-PrepHeld (Join-Path $prepWorkspace '.pytest_tmp/task61-known-journals-01.json') 262144 '4b88319870c1cc504a52e1842f29d40337cf1c355f5e098c5ae242a8ad5536cd'
        PREVIOUS_ROOTS_BASE64 = Read-PrepHeld (Join-Path $prepWorkspace '.pytest_tmp/task61-retained-metadata-01.json') 262144 '2e1699479e0bae473ac9f8bfd7038dbac4ec7bf9f2060081cfc6652ec4be1171'
    }
    foreach ($prepName in $prepValues.Keys) {
        $prepPlaceholder = '"' + $prepName + '"'
        if ([regex]::Matches($prepProgram, [regex]::Escape($prepPlaceholder)).Count -ne 1) { throw 'Ambiguous preparation placeholder' }
        $prepProgram = $prepProgram.Replace($prepPlaceholder, '"' + [Convert]::ToBase64String($prepValues[$prepName]) + '"')
    }
    $prepPayload = [Text.Encoding]::UTF8.GetBytes($prepProgram)
    if ($prepPayload.Length -gt 2097152) { throw 'Preparation stdin bound' }
    $prepRemote = 'exec sudo -n env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/time -f "TASK61_PREP exit=%x wall=%e user=%U sys=%S rss_kib=%M" /usr/bin/python3 -I -S -B -'
}
$prepProgramHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($prepProgram))).ToLowerInvariant()
$prepPayloadHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($prepPayload)).ToLowerInvariant()
"mode=$Mode program_sha256=$prepProgramHash stdin_bytes=$($prepPayload.Length) stdin_sha256=$prepPayloadHash dry_run=$DryRun"
if ($DryRun) { exit 0 }
$prepOutPath = Join-Path $prepWorkspace ".pytest_tmp/task61-native-prepare-$Mode-01.stdout.log"
$prepErrPath = Join-Path $prepWorkspace ".pytest_tmp/task61-native-prepare-$Mode-01.stderr.log"
$prepOut = [IO.File]::Open($prepOutPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
try {
    $prepErr = [IO.File]::Open($prepErrPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try {
        $prepStart = [Diagnostics.ProcessStartInfo]::new('ssh')
        $prepStart.UseShellExecute = $false
        $prepStart.CreateNoWindow = $true
        $prepStart.RedirectStandardInput = $true
        $prepStart.RedirectStandardOutput = $true
        $prepStart.RedirectStandardError = $true
        foreach ($prepArgument in @('-T','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3','betboy-vps',$prepRemote)) { $prepStart.ArgumentList.Add($prepArgument) }
        $prepProcess = [Diagnostics.Process]::Start($prepStart)
        $prepOutTask = $prepProcess.StandardOutput.BaseStream.CopyToAsync($prepOut)
        $prepErrTask = $prepProcess.StandardError.BaseStream.CopyToAsync($prepErr)
        $prepProcess.StandardInput.BaseStream.Write($prepPayload)
        $prepProcess.StandardInput.BaseStream.Flush()
        $prepProcess.StandardInput.Close()
        $prepClock = [Diagnostics.Stopwatch]::StartNew()
        $prepNextStatus = 30
        while (-not $prepProcess.WaitForExit(1000)) {
            if ($prepClock.Elapsed.TotalSeconds -ge $prepNextStatus) { "preparation_waiting_seconds=$([int]$prepClock.Elapsed.TotalSeconds); no retry"; $prepNextStatus += 30 }
        }
        [void]$prepOutTask.GetAwaiter().GetResult()
        [void]$prepErrTask.GetAwaiter().GetResult()
        $prepOut.Flush($true)
        $prepErr.Flush($true)
    } finally { $prepErr.Dispose() }
} finally { $prepOut.Dispose() }
"ssh_exit=$($prepProcess.ExitCode)"
Get-Content -Raw -LiteralPath $prepOutPath
Get-Content -Raw -LiteralPath $prepErrPath
Get-Item -LiteralPath $prepOutPath,$prepErrPath | Select-Object Name,Length | ConvertTo-Json -Compress
Get-FileHash -LiteralPath $prepOutPath,$prepErrPath -Algorithm SHA256 | Format-List
exit $prepProcess.ExitCode
