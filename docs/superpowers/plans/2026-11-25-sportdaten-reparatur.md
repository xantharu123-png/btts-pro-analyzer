# Sportdaten-Reparatur – Umsetzungsplan

Geprüfte Ursachen und Prioritäten: [Sportarten-Audit](../../audits/2026-11-25-sportarten-ausserhalb-nhl.md).

1. **Hockey-Quoten:** Teamrollen aller Zeilen einer nativen Partie vor
   Wiederverwendung und Abruflimits prüfen. Bei Konflikt weder Cache-Treffer
   noch alte eingebettete Quote zulassen. Warmen Cache vor/nach Sperrfrist
   sowie Wettfinder-/Doublebet-Pfad testen. Kein zusätzlicher Quotenabruf.
2. **E-Sport-Zeit:** Tatsächliche Anbieter-Aktualisierung und unseren Abruf
   getrennt aufbewahren. Fehlende/future Zeit nicht als Anbieterzeit werten.
   OddsPapi-Aggregatorpreise sind kein Ausführungsbeleg. Modellwert,
   Preisanzeige und Wettentscheidung getrennt halten; nichts rückdatieren.
3. **NBA:** Lokalen Zürcher Spieltag über seine tatsächlichen überlappenden
   ESPN-Datumsbereiche lesen, nach Zürich und nativer ID filtern. Ein
   Mitternachtsfall und getrennte NBA-/EuroLeague-Provenienz als Regression.
4. **Europäisches Hockey:** Saison-/Liga-Verfügbarkeit im vorhandenen Archiv
   verifizieren. Nur belegte, rechtzeitige Ergebnisse derselben Liga und
   Quelle in das bestehende Modell übernehmen. Gebuchte API-Abdeckung
   nicht umgehen; ein nicht lösbares Kontolimit explizit dokumentieren.
5. **Release:** Red/green für die vier Teilpfade, gezielt unter `gate`
   und `floor`, unabhängige Diff-Prüfung und CI; eingegrenzten Commit
   veröffentlichen. VPS im freien Timerfenster, Offline-Prüfung,
   Fast-forward und Healthchecks. Kein Backup und kein zusätzlicher
   Sportscan. Keine Änderung der Modellsicherheit, Top-Grenzen oder
   Doublebet-Produktregel ohne separaten Auftrag.
