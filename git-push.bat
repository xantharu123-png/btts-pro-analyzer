@echo off
chcp 65001 >nul
cd /d "C:\Users\miros\Desktop\BetBoy\betboy-app"

echo ==========================================
echo    BetBoy - Git Auto Push
echo ==========================================
echo.

:: Zeige Status
echo 📋 Aktuelle Änderungen:
echo ------------------------------------------
git status --short
echo.

:: Frage nach Commit-Nachricht
set /p MESSAGE="💬 Commit-Nachricht (oder Enter für 'Update'): "
if "%MESSAGE%"=="" set MESSAGE=Update

:: Git Befehle ausführen
echo.
echo ⏳ Pushe zu GitHub...
echo.

git add -A
git commit -m "%MESSAGE%"
git push origin main

echo.
echo ==========================================
if %ERRORLEVEL% EQU 0 (
    echo ✅ Erfolgreich gepusht!
    echo 🌐 Streamlit deployed in ~2-3 Minuten
) else (
    echo ❌ Fehler beim Push!
)
echo ==========================================
echo.
pause
