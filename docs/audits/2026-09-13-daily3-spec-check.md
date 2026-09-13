# Daily3 — Spezifikationsprüfung und Fortsetzung

Stand: 13.09.2026. Ausschließlich Dokumentationsarbeit; kein Daily3-Produktivcode,
keine Geldbewegung, kein neuer Timer und kein VPS-Deployment.

## Gegenstand

[Produktspezifikation](../superpowers/specs/2026-09-13-daily3-design.md)
für `3 a day keeps the job away`. Gelesener Bestand:
`9ccdf4262c7e69ee73160eb31540e0a4a2851ba7` im bestehenden Branch
`codex/context-capacity-recovery-20260910`.

Übernommen: CHF 50 eigenes Tagesbudget, höchstens drei Einzelwetten,
abgerechnete Gewinne wiederverwendbar, kein Nachschuss, CHF 50 Nettoverlust
gegenüber Tagesstart, Nutzer platziert selbst. Kein garantierter Tagesgewinn.
Cricket bleibt ausgenommen. Keine Freigabeänderung des älteren C/B-Vertrags.

## Nachgerechnet — keine Produkt-Testabdeckung

Eine zustandslose JavaScript-Prüfung verglich die Spezifikationsformeln in
ganzen Rappen. Sie führte keine Datenbank-, Browser- oder Buchmacheraktion aus.

- 11 Zustandsbeispiele einschließlich Reservierung, Platzierung, Verlust,
  vollständigem Void und Wiederverwendung der CHF 120 Gesamtrückzahlung.
- 16 Zulässigkeitsfälle: Betragsgrenze, parallele Belegung, vierter Slot,
  ungültige Geldwerte und negative Verfügbarkeit nach externer Korrektur.
- 3000 Kombinationen aus realisiertem Nettoergebnis, offenen Einsätzen,
  Reservierungen, bereits belegten Slots und neuem Einsatz verglichen.
- 345 Kombinationen zulässig; alle hielten das definierte Netto-Worst-Case-
  Limit ein. Kein Widerspruch zwischen Verfügbarkeits- und Verlustformel.

Verwendete Rasterwerte: `G=[-5000,-2000,0,2000,7000]`,
`O=[0,2000,5000,7000,12000]`, `R=[0,2000,3000,5000,12000]`,
`n=[0,1,2,3]`, `s=[1,1000,2000,5000,7000,12000]`.
Geprüft wurden `A=5000+G-O-R`, `W=G-O-R` sowie die Aufnahme von `s`
bei positiver Ganzzahl, freiem Slot, `s<=A` und `W-s>=-5000`.

Das ist eine Konsistenzprüfung des Entwurfs, keine vollständige Beweisführung
für eine künftige Implementierung und kein Bericht über bestandene App-Tests.
Insbesondere Transaktionsisolation, dauerhafte Idempotenz, Abrechnung,
Rundung/Gebühren, Identität, Restore und reale UI wurden noch nicht umgesetzt
oder dadurch getestet.

## Tatsächlicher Codeabgleich

- Bestehende Navigation hat fünf Hauptbereiche; neue sechste Mobile-Taste
  wurde nicht ungeprüft vorgeschrieben.
- `selection_coherence.py` ist der vorhandene Kohärenzbaustein; vollständigen
  Pool prüfen, bevor Daily3 kürzt.
- Teile von `bet_finder_ui.py` verwenden Preis-/RELEASED-Zustände und liefern
  keinen direkt übernehmbaren preisneutralen Daily3-Sicherheitsrang.
- `challenge_engine.py` und `ChallengeLedger` verfolgen andere 15K-Regeln;
  keine Übernahme ihrer Ziel-/Quoten-/Einsatzgrenzen als Nutzerfreigabe.
- `TipStore` mit REAL-Geldfeldern und binären Abrechnungstypen ist kein
  hinreichendes Daily3-Tagesledger.
- Browser-Scope ist kein verifiziertes globales Personen-/Buchmacherlimit.

## Offen — nicht als bestätigt darstellen

Nachtrag: Die Übernachtregel wurde am 13.09.2026 mit „ja passt und vps pullen“
bestätigt. Sie ist nicht mehr offen. Noch auszuarbeiten bleiben:

1. Entwurf einer manuellen Einsatzbestätigung ohne automatische Einsatzformel.
2. Preisneutrale fachliche Rangfolge mit nachvollziehbarer Vergleichbarkeit;
   keine erfundene Kalibrierung durch diese Spezifikation.
3. Vertrag zur Bestätigung realer Rückzahlungen einschließlich Teilabrechnung,
   Korrekturen, Rundungen und Gebühren vor erneuter Gewinnverwendung.
4. Zugang innerhalb Wettfinder und flache Desktop-/Mobile-Skizze.

Nächster Schritt: die noch offenen fachlichen Details ausarbeiten und
Wireframe/begrenzten Implementierungsplan erstellen. Keine erneute Nachfrage
zu bereits bestätigtem Namen, Währung, CHF-50-Nettoverlustdefinition oder
Übernachtregel. Zum angeforderten VPS-Pull siehe
[frischen Betriebsabgleich](2026-09-13-daily3-vps-preflight.md).
Der ältere C/B-Reparaturstand bleibt separat offen; neue Daily3-Zustimmung
ersetzt keine fehlende CPU-/Prüfarchitekturentscheidung und keinen Releasebeleg.
