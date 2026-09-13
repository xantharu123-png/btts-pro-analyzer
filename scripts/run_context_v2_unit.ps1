param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$Revision,
    [Parameter(Mandatory=$true)][ValidateSet('portable-native','root-process','qualification')][string]$Mode,
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
if ($Mode -eq 'qualification') {
    $qaNames = @(& git -c core.autocrlf=false -c safe.directory=$($qaWork.Replace('\','/')) -C $qaWork ls-tree -r --name-only $Revision | Where-Object { $_.EndsWith('.py') -and -not $_.StartsWith('.') })
    if ($LASTEXITCODE -ne 0 -or $qaNames.Count -lt 100) { throw 'Full tracked Python source selection failed' }
}
$qaRun = Join-Path $qaWork ('.pytest_tmp/qav2-unit-'+$Revision.Substring(0,7)+'-'+$Mode)
if ($DryRun) { $qaRun += '-dryrun-'+[guid]::NewGuid().ToString('N') }
if (Test-Path -LiteralPath $qaRun) { throw 'Retained unit transport already exists; no implicit retry' }
New-Item -ItemType Directory -Path $qaRun | Out-Null
$qaArchivePath = Join-Path $qaRun 'source.tar'
& git -c core.autocrlf=false -c safe.directory=$($qaWork.Replace('\','/')) -C $qaWork archive --format=tar --output=$qaArchivePath $Revision -- @qaNames
if ($LASTEXITCODE -ne 0) { throw 'Exact tracked-source archive failed' }
$qaArchive = [IO.File]::ReadAllBytes($qaArchivePath)
if ($qaArchive.Length -gt $(if($Mode -eq 'qualification'){67108864}else{2097152})) { throw 'QA archive exceeds bound' }
$qaChecksum = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($qaArchive)).ToLowerInvariant()
$qaEntryName = if($Mode -eq 'qualification'){'scripts/qa_context_v2_qualification_entry.py'}else{'scripts/qa_context_v2_unit_entry.py'}
$qaTemplateLines = & git -c core.autocrlf=false -c safe.directory=$($qaWork.Replace('\','/')) -C $qaWork show "${Revision}:${qaEntryName}"
if ($LASTEXITCODE -ne 0) { throw 'Unit entry must exist in the exact requested revision' }
$qaTemplate = ($qaTemplateLines -join [char]10)+[char]10
$qaPairs = @(@('SOURCE_REVISION',$Revision),@('ARCHIVE_SHA256',$qaChecksum),@('ARCHIVE_BASE64',[Convert]::ToBase64String($qaArchive)))
if ($Mode -eq 'qualification') {
    foreach ($qaMeta in @(@('KNOWN_JOURNALS','.pytest_tmp/task61-known-journals-01.json'),@('PRIOR_ROOTS','.pytest_tmp/task61-retained-metadata-01.json'))) {
        $qaMetaBytes = [IO.File]::ReadAllBytes((Join-Path $qaWork $qaMeta[1]))
        if ($qaMetaBytes.Length -gt 262144) { throw 'Retained metadata exceeds bound' }
        $qaPairs += ,@(($qaMeta[0]+'_BASE64'),[Convert]::ToBase64String($qaMetaBytes))
        $qaPairs += ,@(($qaMeta[0]+'_SHA256'),[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($qaMetaBytes)).ToLowerInvariant())
    }
} else { $qaPairs += ,@('NATIVE_MODE',$Mode) }
foreach ($qaPair in $qaPairs) {
    $qaToken = '"'+$qaPair[0]+'"'
    if ([regex]::Matches($qaTemplate,[regex]::Escape($qaToken)).Count -ne 1) { throw "QA template placeholder differs: $qaToken" }
    $qaTemplate = $qaTemplate.Replace($qaToken,'"'+$qaPair[1]+'"')
}
$qaPayload = [Text.Encoding]::UTF8.GetBytes($qaTemplate)
if ($qaPayload.Length -gt $(if($Mode -eq 'qualification'){94371840}else{3145728})) { throw 'Bounded QA payload exceeded' }
"mode=$Mode source=$Revision archive_sha256=$qaChecksum bytes=$($qaPayload.Length)"
if ($DryRun) { exit 0 }
$qaStart = [Diagnostics.ProcessStartInfo]::new('ssh')
$qaStart.UseShellExecute=$false
$qaStart.CreateNoWindow=$true
$qaStart.RedirectStandardInput=$true
$qaStart.RedirectStandardOutput=$true
$qaStart.RedirectStandardError=$true
$qaTimeout = if($Mode -eq 'qualification'){930}else{120}
$qaRemote = 'exec '+$(if($Mode -ne 'portable-native'){'sudo -n '}else{''})+'env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/time -f "QA_RUN exit=%x wall=%e user=%U sys=%S rss_kib=%M" /usr/bin/timeout --signal=TERM --kill-after=5s '+$qaTimeout+'s /usr/bin/python3 -I -S -B -'
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
$qaLogBytes = 0
while (-not $qaProcess.HasExited -or ($qaReaders | Where-Object { $_.Active }).Count -gt 0) {
    foreach ($qaReader in $qaReaders) {
        if ($qaReader.Active -and $qaReader.Task.IsCompleted) {
            $qaCount = $qaReader.Task.GetAwaiter().GetResult()
            if ($qaCount -eq 0) { $qaReader.Active=$false; continue }
            $qaChunk = [string]::new($qaReader.Buffer,0,$qaCount)
            $qaLogBytes += [Text.Encoding]::UTF8.GetByteCount($qaChunk)
            if ($qaLogBytes -gt 1048576) {
                if (-not $qaProcess.HasExited) { $qaProcess.Kill() }
                throw 'Unit log cap reached during capture; no accepted result'
            }
            [void]$qaReader.Text.Append($qaReader.Buffer,0,$qaCount)
            [Console]::Write($qaChunk)
            $qaReader.Task=$qaReader.Reader.ReadAsync($qaReader.Buffer,0,4096)
        }
    }
    if ($qaClock.Elapsed.TotalSeconds -ge $qaNext) { "native_unit_running_seconds=$([int]$qaClock.Elapsed.TotalSeconds)"; $qaNext+=30 }
    if ($qaClock.Elapsed.TotalSeconds -gt ($qaTimeout+15)) { $qaProcess.Kill(); throw 'SSH terminal observation timed out; retain remote state' }
    [Threading.Thread]::Sleep(20)
}
$qaProcess.WaitForExit()
$qaOutText = $qaReaders[0].Text.ToString()
$qaErrText = $qaReaders[1].Text.ToString()
if ($qaOutText.Length+$qaErrText.Length -gt 1048576) { throw 'Unit log bound exceeded; result not accepted' }
[IO.File]::WriteAllText((Join-Path $qaRun 'stdout.log'),$qaOutText)
[IO.File]::WriteAllText((Join-Path $qaRun 'stderr.log'),$qaErrText)
"ssh_exit=$($qaProcess.ExitCode)"
exit $qaProcess.ExitCode
