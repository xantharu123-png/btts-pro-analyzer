# BetBoy - Repository Cleanup Script
# Führe dieses Script in PowerShell aus

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  BTTS Pro Analyzer - Repo Cleanup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Wechsle zum Projektordner
Set-Location "C:\Users\miros\Desktop\BetBoy\betboy-app"

Write-Host "📁 Aktueller Ordner: $(Get-Location)" -ForegroundColor Yellow
Write-Host ""

# 1. Lösche __pycache__
Write-Host "🗑️  Lösche __pycache__..." -ForegroundColor Yellow
if (Test-Path "__pycache__") {
    Remove-Item -Recurse -Force "__pycache__"
    Write-Host "   ✅ __pycache__ gelöscht" -ForegroundColor Green
} else {
    Write-Host "   ℹ️  __pycache__ nicht vorhanden" -ForegroundColor Gray
}

# 2. Lösche alte Dokumentationen (optional - auskommentiert)
Write-Host ""
Write-Host "🗑️  Lösche alte Dokumentationen..." -ForegroundColor Yellow
$mdFiles = @(
    "CLOUD_MIGRATION_COMPLETE.md",
    "EMERGENCY_FIX.md",
    "FINAL_DEPLOYMENT_GUIDE.md",
    "FINAL_FIX_GUIDE.md",
    "GOAL_FESTIVAL_EXPANSION.md",
    "IMPLEMENTATION_PLAN_V2.4.md",
    "LIVE_ONLY_FIX.md",
    "LIVE_SCANNER_SETUP.md",
    "MULTI_MARKET_GUIDE.md",
    "NONE_VALUES_FIX.md",
    "QUICK_FIX_V2.4.1.md",
    "TIER_1_2_UPDATE.md",
    "ULTRA_FINAL_FIX.md",
    "ULTRA_V3_UPGRADE_GUIDE.md",
    "UPDATE_V2.2.md",
    "UPDATE_V2.3.md",
    "UPDATE_V2.4_FINAL.md",
    "WHY_NO_DISPLAY.md",
    "XG_INTEGRATION_PLAN.md"
)

foreach ($file in $mdFiles) {
    if (Test-Path $file) {
        Remove-Item $file
        Write-Host "   ✅ $file gelöscht" -ForegroundColor Green
    }
}

# 3. Benenne gitignore um zu .gitignore
Write-Host ""
Write-Host "📝 Korrigiere .gitignore..." -ForegroundColor Yellow
if (Test-Path "gitignore") {
    Remove-Item "gitignore"
    Write-Host "   ✅ Alte 'gitignore' entfernt" -ForegroundColor Green
}

# 4. Lösche alte Scripts die nicht mehr gebraucht werden
Write-Host ""
Write-Host "🗑️  Lösche alte Scripts..." -ForegroundColor Yellow
$oldScripts = @("START_BTTS_ANALYZER.bat", "git-push.ps1")
foreach ($script in $oldScripts) {
    if (Test-Path $script) {
        Remove-Item $script
        Write-Host "   ✅ $script gelöscht" -ForegroundColor Green
    }
}

# 5. Zeige verbleibende Dateien
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Verbleibende Dateien:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Get-ChildItem -Name | ForEach-Object { Write-Host "   $_" -ForegroundColor White }

Write-Host ""
Write-Host "✅ Cleanup abgeschlossen!" -ForegroundColor Green
Write-Host ""
Write-Host "Nächste Schritte:" -ForegroundColor Yellow
Write-Host "1. Kopiere die korrigierten Dateien in den Ordner" -ForegroundColor White
Write-Host "2. Führe 'git add -A' aus" -ForegroundColor White
Write-Host "3. Führe 'git commit -m \"Cleanup and fixes\"' aus" -ForegroundColor White
Write-Host "4. Führe 'git push origin main' aus" -ForegroundColor White
Write-Host ""
