param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$Revision,
    [Parameter(Mandatory=$true)][ValidateSet('portable-native','root-process')][string]$Mode,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$qaWork = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$qaNames = @(
    'tests/native_context_receipt_diagnostic.py','tests/native_context_receipt_diagnostic_catalogue.py',
    'tests/native_context_chain_catalogue.py','tests/native_context_diagnostic_admission.py',
    'context_preparation_process_guard.py','context_preparation_budget.py','context_preparation_supervisor.py',
    'tests/native_context_qa_coordinator.py','tests/native_context_qa_budget.py',
    'tests/test_native_context_qa_budget.py','tests/test_native_context_qa_retained_v2.py','tests/test_native_context_qa_coordinator.py',
    'tests/test_native_context_receipt_diagnostic.py','tests/native_context_receipt_diagnostic_worker.py',
    'tests/context_growth_profile.py','context_storage_v2/receipt_corpus.py','context_storage_v2/copying.py',
    'context_storage_v2/inventory.py','context_storage_v2/receipt_append.py','context_storage_v2/sqlite_profile.py',
    'tests/native_context_chain.py','tests/native_context_chain_worker.py'
)
$qaRun = Join-Path $qaWork ('.pytest_tmp/qav2-unit-'+$Revision.Substring(0,7)+'-'+$Mode)
if (Test-Path -LiteralPath $qaRun) { throw 'Retained unit transport already exists; no implicit retry' }
New-Item -ItemType Directory -Path $qaRun | Out-Null
$qaArchivePath = Join-Path $qaRun 'source.tar'
& git -c core.autocrlf=false -c safe.directory=$($qaWork.Replace('\','/')) -C $qaWork archive --format=tar --output=$qaArchivePath $Revision -- @qaNames
if ($LASTEXITCODE -ne 0) { throw 'Exact tracked-source archive failed' }
$qaArchive = [IO.File]::ReadAllBytes($qaArchivePath)
if ($qaArchive.Length -gt 2097152) { throw 'Unit archive exceeds bound' }
$qaChecksum = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($qaArchive)).ToLowerInvariant()
$qaTemplateLines = & git -c core.autocrlf=false -c safe.directory=$($qaWork.Replace('\','/')) -C $qaWork show "${Revision}:scripts/qa_context_v2_unit_entry.py"
if ($LASTEXITCODE -ne 0) { throw 'Unit entry must exist in the exact requested revision' }
$qaTemplate = ($qaTemplateLines -join [char]10)+[char]10
foreach ($qaPair in @(@('SOURCE_REVISION',$Revision),@('ARCHIVE_SHA256',$qaChecksum),@('NATIVE_MODE',$Mode),@('ARCHIVE_BASE64',[Convert]::ToBase64String($qaArchive)))) {
    $qaToken = '"'+$qaPair[0]+'"'
    if ([regex]::Matches($qaTemplate,[regex]::Escape($qaToken)).Count -ne 1) { throw 'Unit template placeholder differs' }
    $qaTemplate = $qaTemplate.Replace($qaToken,'"'+$qaPair[1]+'"')
}
$qaPayload = [Text.Encoding]::UTF8.GetBytes($qaTemplate)
if ($qaPayload.Length -gt 3145728) { throw 'Bounded unit payload exceeded' }
"mode=$Mode source=$Revision archive_sha256=$qaChecksum bytes=$($qaPayload.Length)"
if ($DryRun) { exit 0 }
$qaStart = [Diagnostics.ProcessStartInfo]::new('ssh')
$qaStart.UseShellExecute=$false
$qaStart.CreateNoWindow=$true
$qaStart.RedirectStandardInput=$true
$qaStart.RedirectStandardOutput=$true
$qaStart.RedirectStandardError=$true
$qaRemote = 'exec '+$(if($Mode -eq 'root-process'){'sudo -n '}else{''})+'env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/time -f "QA_UNIT exit=%x wall=%e user=%U sys=%S rss_kib=%M" /usr/bin/timeout --signal=TERM --kill-after=5s 120s /usr/bin/python3 -I -S -B -'
foreach ($qaArg in @('-T','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3','betboy-vps',$qaRemote)) { $qaStart.ArgumentList.Add($qaArg) }
$qaProcess = [Diagnostics.Process]::Start($qaStart)
$qaReaders = @(
    @{ Reader=$qaProcess.StandardOutput; Buffer=[char[]]::new(4096); Text=[Text.StringBuilder]::new(); Active=$true },
    @{ Reader=$qaProcess.StandardError; Buffer=[char[]]::new(4096); Text=[Text.StringBuilder]::new(); Active=$true }
)
foreach ($qaReader in $qaReaders) { $qaReader.Task=$qaReader.Reader.ReadAsync($qaReader.Buffer,0,4096) }
$qaProcess.StandardInput.BaseStream.Write($qaPayload)
$qaProcess.StandardInput.Close()
$qaClock = [Diagnostics.Stopwatch]::StartNew()
$qaNext = 30
$qaLogChars = 0
while (-not $qaProcess.HasExited -or ($qaReaders | Where-Object { $_.Active }).Count -gt 0) {
    foreach ($qaReader in $qaReaders) {
        if ($qaReader.Active -and $qaReader.Task.IsCompleted) {
            $qaCount = $qaReader.Task.GetAwaiter().GetResult()
            if ($qaCount -eq 0) { $qaReader.Active=$false; continue }
            $qaLogChars += $qaCount
            if ($qaLogChars -gt 1048576) {
                if (-not $qaProcess.HasExited) { $qaProcess.Kill() }
                throw 'Unit log cap reached during capture; no accepted result'
            }
            [void]$qaReader.Text.Append($qaReader.Buffer,0,$qaCount)
            $qaReader.Task=$qaReader.Reader.ReadAsync($qaReader.Buffer,0,4096)
        }
    }
    if ($qaClock.Elapsed.TotalSeconds -ge $qaNext) { "native_unit_running_seconds=$([int]$qaClock.Elapsed.TotalSeconds)"; $qaNext+=30 }
    if ($qaClock.Elapsed.TotalSeconds -gt 135) { $qaProcess.Kill(); throw 'SSH terminal observation timed out; retain remote state' }
    [Threading.Thread]::Sleep(20)
}
$qaProcess.WaitForExit()
$qaOutText = $qaReaders[0].Text.ToString()
$qaErrText = $qaReaders[1].Text.ToString()
if ($qaOutText.Length+$qaErrText.Length -gt 1048576) { throw 'Unit log bound exceeded; result not accepted' }
[IO.File]::WriteAllText((Join-Path $qaRun 'stdout.log'),$qaOutText)
[IO.File]::WriteAllText((Join-Path $qaRun 'stderr.log'),$qaErrText)
"ssh_exit=$($qaProcess.ExitCode)"
$qaOutText
$qaErrText
exit $qaProcess.ExitCode
