"""Zentrale DB-Pfade plus einmalige Migration btts_data.db -> betboy_data.db.

Die Migration kopiert (nicht verschiebt): die alte Datei bleibt als Backup
bestehen. Alle SQLite-Zugriffe laufen ueber ensure_primary_db(), wenn sie den
Standard- oder Legacy-Namen nutzen - so kann kein Codepfad versehentlich eine
leere neue Datenbank anlegen, solange der alte Bestand existiert.
"""

from pathlib import Path
import shutil

LEGACY_DB_NAME = "btts_data.db"
PRIMARY_DB_NAME = "betboy_data.db"


def ensure_primary_db(base_dir: str | Path = ".") -> str:
    """Stelle sicher, dass betboy_data.db existiert; migriere sonst aus dem Legacy-Bestand.

    Gibt IMMER den relativen Primaer-Namen zurueck (gleiche cwd-Semantik wie bisher).
    """
    base = Path(base_dir)
    primary = base / PRIMARY_DB_NAME
    legacy = base / LEGACY_DB_NAME
    if not primary.exists() and legacy.exists():
        shutil.copy2(legacy, primary)
    return PRIMARY_DB_NAME
