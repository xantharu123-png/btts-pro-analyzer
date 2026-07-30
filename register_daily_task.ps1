# BetBoy Tennis Daily - registriert die taegliche Pipeline in der
# Windows-Aufgabenplanung (07:17 lokal, nur wenn Benutzer angemeldet).
# Erneutes Ausfuehren ueberschreibt die Aufgabe (-Force).
$root = "C:\Users\miros\Desktop\BetBoy\betboy-app"
$action = New-ScheduledTaskAction `
    -Execute "$root\.codex_test_venv\Scripts\pythonw.exe" `
    -Argument "`"$root\scripts\run_daily_pipeline.py`"" `
    -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At 07:17
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3)
Register-ScheduledTask -TaskName "BetBoy Tennis Daily" `
    -Action $action -Trigger $trigger -Settings $settings `
    -Description "BetBoy Tennis Tages-Pipeline: State-Rebuild, Scan, montags Kalibrierungs-Waechter + Wochenreport" `
    -Force | Select-Object TaskName, State
