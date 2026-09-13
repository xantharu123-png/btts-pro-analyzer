param(
    [Parameter(Mandatory=$true)][ValidateSet('prepare','success','failure')][string]$Mode,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$prefixWorkspace = 'C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910'
$prefixTemplatePath = Join-Path $prefixWorkspace '.superpowers/sdd/2026-09-10-context-capacity-recovery/evidence/task61-native-prefix-entry.py'
if ((Get-Item -LiteralPath $prefixTemplatePath).Length -gt 65536) { throw 'Prefix template control cap' }
$prefixTemplateBytes = [IO.File]::ReadAllBytes($prefixTemplatePath)
if ($prefixTemplateBytes.Length -gt 65536) { throw 'Prefix template control cap' }
if ([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($prefixTemplateBytes)).ToLowerInvariant() -ne '5e1bd97571eaf3c306e304aff4d339a880fcdb69a1baf1f06501a502e640f868') { throw 'Prefix template pin differs' }
$prefixTemplate = [Text.UTF8Encoding]::new($false, $true).GetString($prefixTemplateBytes)
$prefixPins = [ordered]@{
    'tests/native_context_receipt_diagnostic.py' = '249aa84f12de528d0bbb268de794582ff44bcc6eb1330099793aa1de86a1feb5'
    'tests/native_context_receipt_diagnostic_catalogue.py' = 'c05241df7965b5b185f2df63945806eb89d5b4a37f3fa69c4bd400e17b8249d7'
    'tests/native_context_chain_catalogue.py' = '48fd59c0660843c530a079c53556b630622085e0ce09f0b9878e7230371dd935'
    'tests/native_context_diagnostic_admission.py' = 'f0b0821195d6ebce89bc47e5d37f21dedc36fc8e223678816a932b1aae5d60ad'
    'context_preparation_process_guard.py' = '62fcfcacaa7e658eefa8a2f8ceced9dc465846a8ca61dc38c2691dc9984685e4'
    'context_preparation_budget.py' = 'fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478'
    'context_preparation_supervisor.py' = 'c6c1c8e82107d48b66d7714577004e7d9e7e400525620b23070d4258ab554dc8'
}
$prefixBundle = [ordered]@{}
foreach ($prefixName in $prefixPins.Keys) {
    $prefixBytes = [IO.File]::ReadAllBytes((Join-Path $prefixWorkspace $prefixName))
    if ([Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($prefixBytes)).ToLowerInvariant() -ne $prefixPins[$prefixName]) { throw "Prefix held member pin differs: $prefixName" }
    $prefixBundle[$prefixName] = [Convert]::ToBase64String($prefixBytes)
}
$prefixBundleBytes = [Text.Encoding]::ASCII.GetBytes(($prefixBundle | ConvertTo-Json -Compress))
if ([regex]::Matches($prefixTemplate, '"BUNDLE_BASE64"').Count -ne 1 -or [regex]::Matches($prefixTemplate, '"PREFIX_MODE"').Count -ne 1) { throw 'Ambiguous fixed prefix placeholders' }
$prefixProgram = $prefixTemplate.Replace('"BUNDLE_BASE64"', '"' + [Convert]::ToBase64String($prefixBundleBytes) + '"').Replace('"PREFIX_MODE"', '"' + $Mode + '"')
$prefixProgramBytes = [Text.Encoding]::UTF8.GetBytes($prefixProgram)
if ($prefixProgramBytes.Length -gt 1048576) { throw 'Prefix stdin control cap' }
$prefixProgramHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($prefixProgramBytes)).ToLowerInvariant()
"mode=$Mode stdin_bytes=$($prefixProgramBytes.Length) stdin_sha256=$prefixProgramHash dry_run=$DryRun"
if ($DryRun) { exit 0 }

$prefixStdoutPath = Join-Path $prefixWorkspace ".pytest_tmp/task61-native-prefix-$Mode-01.stdout.json"
$prefixStderrPath = Join-Path $prefixWorkspace ".pytest_tmp/task61-native-prefix-$Mode-01.stderr.log"
$prefixOut = [IO.File]::Open($prefixStdoutPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
try {
    $prefixErr = [IO.File]::Open($prefixStderrPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try {
        $prefixStart = [Diagnostics.ProcessStartInfo]::new('ssh')
        $prefixStart.UseShellExecute = $false
        $prefixStart.CreateNoWindow = $true
        $prefixStart.RedirectStandardInput = $true
        $prefixStart.RedirectStandardOutput = $true
        $prefixStart.RedirectStandardError = $true
        $prefixRemote = 'exec sudo -n env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/time -f "TASK61_PREFIX exit=%x wall=%e user=%U sys=%S rss_kib=%M" /usr/bin/python3 -I -S -B -'
        foreach ($prefixArgument in @('-T','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3','betboy-vps',$prefixRemote)) { $prefixStart.ArgumentList.Add($prefixArgument) }
        $prefixProcess = [Diagnostics.Process]::Start($prefixStart)
        $prefixOutTask = $prefixProcess.StandardOutput.BaseStream.CopyToAsync($prefixOut)
        $prefixErrTask = $prefixProcess.StandardError.BaseStream.CopyToAsync($prefixErr)
        $prefixProcess.StandardInput.BaseStream.Write($prefixProgramBytes)
        $prefixProcess.StandardInput.BaseStream.Flush()
        $prefixProcess.StandardInput.Close()
        $prefixWatch = [Diagnostics.Stopwatch]::StartNew()
        $prefixNextStatus = 30
        while (-not $prefixProcess.WaitForExit(1000)) {
            if ($prefixWatch.Elapsed.TotalSeconds -ge $prefixNextStatus) {
                "prefix_transport_waiting_seconds=$([int]$prefixWatch.Elapsed.TotalSeconds); no automatic retry or process termination"
                $prefixNextStatus += 30
            }
        }
        [void]$prefixOutTask.GetAwaiter().GetResult()
        [void]$prefixErrTask.GetAwaiter().GetResult()
        $prefixOut.Flush($true)
        $prefixErr.Flush($true)
    } finally { $prefixErr.Dispose() }
} finally { $prefixOut.Dispose() }
"ssh_exit=$($prefixProcess.ExitCode)"
Get-Content -Raw -LiteralPath $prefixStdoutPath
Get-Content -Raw -LiteralPath $prefixStderrPath
Get-Item -LiteralPath $prefixStdoutPath,$prefixStderrPath | Select-Object Name,Length | ConvertTo-Json -Compress
Get-FileHash -LiteralPath $prefixStdoutPath,$prefixStderrPath -Algorithm SHA256 | Format-List
exit $prefixProcess.ExitCode
