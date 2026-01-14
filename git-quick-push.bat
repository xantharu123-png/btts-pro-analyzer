@echo off
chcp 65001 >nul
cd /d "C:\Users\miros\Desktop\BetBoy\btts-pro-analyzer"

echo ⏳ Quick Push zu GitHub...

git add -A
git commit -m "Update %date% %time:~0,5%"
git push origin main

if %ERRORLEVEL% EQU 0 (
    echo ✅ Gepusht! Streamlit deployed in ~2-3 Min.
) else (
    echo ❌ Fehler!
)

timeout /t 3
