$ErrorActionPreference = 'Stop'
$task60Workspace = 'C:/Projekt/BetBoy/betboy-app/.worktrees/context-capacity-recovery-20260910'
$task60TemplatePath = Join-Path $task60Workspace '.superpowers/sdd/2026-09-10-context-capacity-recovery/evidence/task60-native-admission-protocol.py'
if ((Get-FileHash -LiteralPath $task60TemplatePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'b73951134de6d0ffd06d2a9e3ebd0a8501864eb52953d9be857d98e7930132b1') { throw 'Reviewed template pin differs' }
$task60SourcePaths = [ordered]@{
    context_preparation_budget = 'context_preparation_budget.py'
    admission = 'tests/native_context_diagnostic_admission.py'
}
$task60SourcePins = @{
    context_preparation_budget = 'fb12aa3b2170dc2dbed7d70d2aa5846d5928b4fda42de00d4828f9f411482478'
    admission = 'f0b0821195d6ebce89bc47e5d37f21dedc36fc8e223678816a932b1aae5d60ad'
}
$task60Bundle = [ordered]@{}
foreach ($task60Name in $task60SourcePaths.Keys) {
    $task60Bytes = [IO.File]::ReadAllBytes((Join-Path $task60Workspace $task60SourcePaths[$task60Name]))
    $task60Hash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($task60Bytes)).ToLowerInvariant()
    if ($task60Hash -ne $task60SourcePins[$task60Name]) { throw 'Held source pin differs' }
    $task60Bundle[$task60Name] = [Convert]::ToBase64String($task60Bytes)
}
$task60BundleBytes = [Text.Encoding]::ASCII.GetBytes(($task60Bundle | ConvertTo-Json -Compress))
$task60Template = Get-Content -Raw -LiteralPath $task60TemplatePath
if ([regex]::Matches($task60Template, '"BUNDLE_BASE64"').Count -ne 1) { throw 'Ambiguous bundle placeholder' }
$task60Program = $task60Template.Replace('"BUNDLE_BASE64"', '"' + [Convert]::ToBase64String($task60BundleBytes) + '"')
$task60ProgramBytes = [Text.Encoding]::UTF8.GetBytes($task60Program)
if ($task60ProgramBytes.Length -gt 262144) { throw 'Native stdin exceeds control cap' }
$task60ProgramHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($task60ProgramBytes)).ToLowerInvariant()
"stdin_bytes=$($task60ProgramBytes.Length) stdin_sha256=$task60ProgramHash"

$task60StdoutPath = Join-Path $task60Workspace '.pytest_tmp/task60-native-protocol-8574747-01.stdout.json'
$task60StderrPath = Join-Path $task60Workspace '.pytest_tmp/task60-native-protocol-8574747-01.stderr.log'
$task60Out = [IO.File]::Open($task60StdoutPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
$task60Err = [IO.File]::Open($task60StderrPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
$task60Start = [Diagnostics.ProcessStartInfo]::new('ssh')
$task60Start.UseShellExecute = $false
$task60Start.CreateNoWindow = $true
$task60Start.RedirectStandardInput = $true
$task60Start.RedirectStandardOutput = $true
$task60Start.RedirectStandardError = $true
$task60Remote = 'exec sudo -n env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/time -f "TASK60_NATIVE exit=%x wall=%e user=%U sys=%S rss_kib=%M" /usr/bin/python3 -I -S -B -'
foreach ($task60Argument in @('-T','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3','betboy-vps',$task60Remote)) { $task60Start.ArgumentList.Add($task60Argument) }
$task60Process = [Diagnostics.Process]::Start($task60Start)
$task60OutTask = $task60Process.StandardOutput.BaseStream.CopyToAsync($task60Out)
$task60ErrTask = $task60Process.StandardError.BaseStream.CopyToAsync($task60Err)
$task60Process.StandardInput.BaseStream.Write($task60ProgramBytes)
$task60Process.StandardInput.BaseStream.Flush()
$task60Process.StandardInput.Close()
$task60Watch = [Diagnostics.Stopwatch]::StartNew()
while (-not $task60Process.WaitForExit(1000)) {
    if ($task60Watch.Elapsed.TotalSeconds -gt 45) { throw 'Nonterminal SSH transport; inspect exact native root/process before any retry' }
}
[void]$task60OutTask.GetAwaiter().GetResult()
[void]$task60ErrTask.GetAwaiter().GetResult()
$task60Out.Flush($true)
$task60Err.Flush($true)
$task60Out.Dispose()
$task60Err.Dispose()
"ssh_exit=$($task60Process.ExitCode)"
Get-Content -Raw -LiteralPath $task60StdoutPath
Get-Content -Raw -LiteralPath $task60StderrPath
Get-Item -LiteralPath $task60StdoutPath,$task60StderrPath | Select-Object Name,Length | ConvertTo-Json -Compress
(Get-FileHash -LiteralPath $task60StdoutPath -Algorithm SHA256).Hash
(Get-FileHash -LiteralPath $task60StderrPath -Algorithm SHA256).Hash
exit $task60Process.ExitCode
