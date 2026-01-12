# BTTS Pro Analyzer - Quick Update Script
# Einfach ausführen nach Datei-Updates!

Write-Host "🚀 BTTS Pro Analyzer - Git Push" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Prüfe ob wir im richtigen Ordner sind
if (-not (Test-Path ".git")) {
    Write-Host "❌ FEHLER: Nicht im Git Repository!" -ForegroundColor Red
    Write-Host "Bitte erst ins btts-pro-analyzer Verzeichnis wechseln!" -ForegroundColor Yellow
    Write-Host "cd C:\Projects\btts-pro-analyzer" -ForegroundColor Yellow
    pause
    exit
}

# Zeige was sich geändert hat
Write-Host "📋 Geänderte Dateien:" -ForegroundColor Yellow
git status --short
Write-Host ""

# Frage ob pushen
$confirm = Read-Host "Möchtest du diese Änderungen auf GitHub pushen? (j/n)"

if ($confirm -eq "j" -or $confirm -eq "J" -or $confirm -eq "yes") {
    
    # Commit Message
    $message = Read-Host "Commit Nachricht (oder Enter für Standard)"
    
    if ([string]::IsNullOrWhiteSpace($message)) {
        $message = "Update: $(Get-Date -Format 'dd.MM.yyyy HH:mm')"
    }
    
    Write-Host ""
    Write-Host "⚙️ Füge Änderungen hinzu..." -ForegroundColor Cyan
    git add .
    
    Write-Host "📝 Erstelle Commit..." -ForegroundColor Cyan
    git commit -m "$message"
    
    Write-Host "🚀 Push zu GitHub..." -ForegroundColor Cyan
    git push
    
    Write-Host ""
    Write-Host "✅ ERFOLGREICH! Änderungen sind auf GitHub!" -ForegroundColor Green
    Write-Host "⏰ Streamlit Cloud updated in 1-2 Minuten automatisch!" -ForegroundColor Green
    Write-Host ""
    
} else {
    Write-Host "❌ Abgebrochen. Keine Änderungen gepusht." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "App URL: https://btts-pro-analyzer-7mody6rq28uhbd5vggobof.streamlit.app" -ForegroundColor Cyan
Write-Host ""

pause
