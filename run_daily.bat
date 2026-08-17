@echo off
setlocal
rem BetBoy Tennis Tages-Pipeline - ausschliesslich manueller Diagnoselauf.
rem Nicht in der Windows-Aufgabenplanung aktivieren: Der VPS ist der einzige
rem kanonische Scheduler und Writer.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo FEHLER: .venv\Scripts\python.exe fehlt.
  echo Bitte zuerst die im PC-Wechsel-Runbook dokumentierte .venv erstellen.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "scripts\run_daily_pipeline.py"
set "BETBOY_PIPELINE_RC=%ERRORLEVEL%"
echo.
echo Fertig. Logs: runtime_state\logs\pipeline_YYYY-MM-DD.log
if not "%BETBOY_PIPELINE_RC%"=="0" echo FEHLER: Pipeline rc=%BETBOY_PIPELINE_RC%
pause
exit /b %BETBOY_PIPELINE_RC%
