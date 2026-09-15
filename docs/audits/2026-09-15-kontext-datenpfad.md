# Kontextdaten: Erfassung und Wiederverwendung, 15. September 2026

## Reparierter Umfang

- Der normale VPS-Wettfinder fragt je Lauf höchstens eine Hintergrundcharge
  mit 20 bereits nativ beobachteten abgeschlossenen Fußballspielen ab.
  Die Auswahl hängt nicht von Tipps oder Quoten ab. Es gibt keinen neuen Timer.
- Eine atomar gespeicherte, kurz gesperrte Abrufreservierung verhindert
  Wiederholungen innerhalb von 24 Stunden, auch bei HTTP-/JSON-Fehlern,
  fehlenden Spielern, ungültigen Projektionen, Prozessabbruch und parallelen
  Workern mit unterschiedlich alten Eintrittszeiten. Native Änderungen an
  Spiel, Teams, Termin, Liga, Saison oder Ergebnis erhalten einen neuen Schlüssel.
  Dies sind interne Ablaufdaten, keine erfundenen Providerbelege.
- Zwei tatsächlich empfangene API-Football-Antworten verwendeten für sämtliche
  Spieler `substitute=False`. Zuvor verwarf der Parser beide vollständigen
  Antworten. Die eng begrenzte Ausnahme erfordert eine vollständig gebundene
  Mannschaft, elf ausdrücklich aufgeführte Starter und Bankspieler. Einzelne
  widersprüchliche Flags bleiben Fehler, unbekannte Minuten bleiben unbekannt.
- Tennis speichert normale, eindeutig beendete Siegerergebnisse aus den bereits
  empfangenen ESPN-Antworten zusätzlich zu Status und Belastung. Erforderlich
  ist ein passendes, tatsächlich vor Spielbeginn gespeichertes Original mit
  nativen Teilnehmern, Turnier, Termin und ursprünglicher Modellidentität.
  Es gibt keine neuen Quellenabfragen, nachträglichen Originalprognosen oder
  Änderungen an Abrechnungen. Retirements/Walkovers liefern kein normales Label.
- Fußball-Rezeptpayloads mit explizitem `schema=2` binden ältere kompatible
  Spielerdetails über separate `context_refs`. Die letzte mathematische
  Basisantwort bleibt maßgeblich. Ganze alte Empfangsbelege behalten ihre
  Originalzeit; neue leere Spielerlisten, Identitätsänderungen und gleichzeitige
  widersprüchliche Antworten verhindern Wiederverwendung. Schema 1 bleibt
  unverändert. Fallzusammenstellung und D4 prüfen die zusätzlichen Referenzen.
- Aus einem Fixturetransport werden keine medizinischen Belege verlangt oder
  erzeugt. Ausfallinformationen bleiben eine getrennte Quelle.

## Nachweise

- Lokale Abschlussregression: **585 bestanden**, 341,14 Sekunden, 18 relevante
  Testsuiten einschließlich Wettfinder, Capture, Replay, Fallzusammenstellung
  und D4. Temporäre Daten ausschließlich im isolierten Testverzeichnis.
- Unabhängiger Review: zwei reproduzierte P2-Kanten korrigiert (ältere
  Worker-Eintrittsuhr; D4-Versionsverteiler). Abschluss ohne offene Befunde.
- Echter Quellenempfang vom 15.09.2026, 17:08:18.166869 UTC: native Fixtures
  1494760 und 1575162. Offline-Prüfung auf dem VPS verarbeitet jeweils 40
  Spielerdatensätze einschließlich nicht eingesetzter Bankspieler sowie 22
  Starter. Isolierter Capture speichert 84 Belege ohne Fehler. Keine weitere
  API-Anfrage, keine Produktionsdatenbankänderung und keine Modellaktivierung
  durch diese Prüfung.
- Tests zeigen ausdrücklich unveränderte Basiswahrscheinlichkeiten bei
  ergänztem Kontext und Ablehnung fehlender/verspäteter Zusatzreferenzen.

## Grenzen, nicht als erledigt melden

Die Reparatur schließt Datenpfadfehler. Sie ist **kein Nachweis empirisch
wirksamer Verletzungs- oder Müdigkeitskoeffizienten** und aktiviert kein Modell.
Tennis benötigt weiterhin die separat versionierte Trainingskohorte für echte
Live-Originale sowie ausreichend belegte Belastungs-/Umgebungsdaten. Fehlende
Dauer, tatsächliches Matchende oder native Belagsdaten werden nicht erfunden.
Fußball benötigt vollständige geeignete Kohorten und die unverändert
freigegebene zeitlich getrennte Validierung. Cricket bleibt ausgeschlossen.

Linux-Abnahme, endgültiger Git-Stand, Archivierung der ausdrücklich freigegebenen
sechs alten QA-Verzeichnisse und VPS-Deployment werden im operativen Bericht
`output/playwright/context-data-release-20260915.md` separat nachgewiesen.
