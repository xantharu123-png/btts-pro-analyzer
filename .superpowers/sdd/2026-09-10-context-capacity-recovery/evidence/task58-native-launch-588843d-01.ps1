$task58NoWorker = @'
sudo -n /usr/bin/python3 -I -S -B - <<'PY'
from pathlib import Path
found=[]
for p in Path('/proc').iterdir():
    if not p.name.isdigit(): continue
    try: lines=(p/'status').read_text().splitlines()
    except (FileNotFoundError,ProcessLookupError): continue
    uid=next((x for x in lines if x.startswith('Uid:')),None)
    if uid and '65534' in uid.split()[1:]: found.append(p.name)
assert not found, found
print('preflight_uid65534_count=0')
PY
'@
& ssh -o BatchMode=yes -o ConnectTimeout=10 betboy-vps $task58NoWorker
if ($LASTEXITCODE -ne 0) { throw 'Existing guarded worker blocks this launch' }
$task57InputPath = Join-Path (Get-Location) '.pytest_tmp/task58-588843d-01-stdin.py'
$task57OutputPath = Join-Path (Get-Location) '.pytest_tmp/task58-native-run-588843d-01.stdout'
$task57ErrorPath = Join-Path (Get-Location) '.pytest_tmp/task58-native-run-588843d-01.stderr'
$task57Input = [System.IO.File]::Open($task57InputPath,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::Read)
try {
 $task57InputHash = [Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData($task57Input)).ToLowerInvariant()
 if ($task57InputHash -ne '64e5f89560a9e91db123bd2b7cd7a23665e60c56968c98ceac6d63d38ad3bdd2') { throw 'Held input pin differs' }
 $task57Input.Position=0
 $task57Output=[System.IO.File]::Open($task57OutputPath,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
 $task57Error=[System.IO.File]::Open($task57ErrorPath,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
 try {
  $task57Start=[System.Diagnostics.ProcessStartInfo]::new()
  $task57Start.FileName='ssh'
  $task57Start.UseShellExecute=$false
  $task57Start.CreateNoWindow=$true
  $task57Start.RedirectStandardInput=$true
  $task57Start.RedirectStandardOutput=$true
  $task57Start.RedirectStandardError=$true
  foreach ($a in @('-o','BatchMode=yes','-o','ConnectTimeout=10','betboy-vps','umask 022; exec sudo -n /usr/bin/time -f "TASK57_TIME exit=%x wall=%e user=%U system=%S maxrss_kib=%M" env -i PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/python3 -I -S -B - --manifest /tmp/betboy-context-qa.9xr68INa/task58-588843d-01-catalogue.json --manifest-sha256 13007f35071d4bc2653969059297e8c2a29b229f3cfa0ae6c95d8d90ec3dd857 --archive /tmp/betboy-context-qa.9xr68INa/task58-588843d-01.tar --directory /var/lib/betboy-context-chain-task58-588843d-01 --commit 588843d1da2b32bdb864fe21fe577f513dd421e6 --launcher-sha256 64e5f89560a9e91db123bd2b7cd7a23665e60c56968c98ceac6d63d38ad3bdd2')) { $task57Start.ArgumentList.Add($a) }
  $task57Process=[System.Diagnostics.Process]::new()
  $task57Process.StartInfo=$task57Start
  $task57Watch=[System.Diagnostics.Stopwatch]::StartNew()
  if (-not $task57Process.Start()) { throw 'Process start failed' }
  $task57OutCopy=$task57Process.StandardOutput.BaseStream.CopyToAsync($task57Output)
  $task57ErrCopy=$task57Process.StandardError.BaseStream.CopyToAsync($task57Error)
  $task57Input.CopyTo($task57Process.StandardInput.BaseStream)
  $task57Process.StandardInput.Close()
  while (-not $task57Process.WaitForExit(1000)) {
   if ($task57Watch.Elapsed.TotalSeconds -gt 660) { throw ('NONTERMINAL process '+$task57Process.Id+' requires read-only custody inspection; no retry') }
  }
  [void]$task57OutCopy.GetAwaiter().GetResult()
  [void]$task57ErrCopy.GetAwaiter().GetResult()
  $task57Output.Flush($true)
  $task57Error.Flush($true)
  [pscustomobject]@{exit_code=$task57Process.ExitCode;transport_ms=$task57Watch.ElapsedMilliseconds;held_input_sha256=$task57InputHash} | ConvertTo-Json -Compress
 } finally { $task57Output.Dispose(); $task57Error.Dispose() }
} finally { $task57Input.Dispose() }
Get-Item -LiteralPath '.pytest_tmp/task58-native-run-588843d-01.stdout', '.pytest_tmp/task58-native-run-588843d-01.stderr' | Select-Object Name,Length | ConvertTo-Json -Compress
Get-FileHash -LiteralPath '.pytest_tmp/task58-native-run-588843d-01.stdout', '.pytest_tmp/task58-native-run-588843d-01.stderr' -Algorithm SHA256 | ConvertTo-Json -Compress
Get-Content -LiteralPath '.pytest_tmp/task58-native-run-588843d-01.stderr'
