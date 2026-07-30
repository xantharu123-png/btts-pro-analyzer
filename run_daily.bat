@echo off
rem BetBoy Tennis Tages-Pipeline - manueller Start (Doppelklick).
rem Die automatische Ausfuehrung laeuft ueber die Windows-Aufgabenplanung
rem (Aufgabe "BetBoy Tennis Daily", taeglich 07:17).
cd /d "%~dp0"
".codex_test_venv\Scripts\python.exe" "scripts\run_daily_pipeline.py"
echo.
echo Fertig. Log: logs\pipeline_%DATE%.log
pause
