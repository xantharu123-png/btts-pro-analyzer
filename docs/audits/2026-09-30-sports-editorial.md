# Sports Editorial – Abnahme vom 30.09.2026

## Umfang

Freigegeben: Design 2 im Web; Design 2 + 5 auf Mobil. Implementiert als
responsive Oberfläche der bestehenden Streamlit-App, nicht als native App.
Warmweiß, Waldgrün, lokale Sporttypografie, neutrale Teaminitialen und ein
gemeinsamer Spielblock. Alle fünf bestehenden Hauptbereiche bleiben erreichbar.
Desktop ergänzt eine Daily3-Spalte aus demselben gespeicherten Prognosepool;
die bestehenden Abo-Rechte gelten auch für diese Vorschau.

Ergebnisfelder zeigen echte 5-/10-Spiele-Fakten mit sportgerechten Resultaten,
Gegnern, Datum und vorhandener Wettbewerbs-/Ranginformation. Kurze Historien
bleiben kurz; E-Sport-Serien ohne Einzelbelege erhalten keine erfundenen Gegner,
Spielstände oder Zeitordnung. Gleichartige Formdaten erscheinen pro Spiel nur
einmal, ohne einen Wettmarkt zu entfernen. Tatsächlich unterschiedliche
Modellgrundlagen bleiben separat. RisikoBet-Zusammenfassungen werden nicht
als neue Einzelresultate interpretiert.

## Regression

Finaler gezielter Lauf: **526 bestanden in 14,68 Sekunden**.

```powershell
.\.codex_test_venv\Scripts\python.exe -m pytest tests/test_sports_editorial.py tests/test_forecast_compact.py tests/test_daily3_selection.py tests/test_daily3_comparison.py tests/test_daily3_store.py tests/test_daily3_ui.py tests/test_wettfinder_surface.py tests/test_workflow_integrity.py tests/test_publication_odds_floor.py tests/test_riskobet_ui.py tests/test_riskobet_surface.py tests/test_riskobet_football_recent_results.py tests/test_football_recent_results.py tests/test_tennis_customer_facts.py tests/test_team_customer_facts.py tests/test_tennis_tab.py tests/test_forecast_analysis.py tests/test_customer_access.py -q --disable-warnings --maxfail=2
```

Geprüft sind gebundene Originalfakten, keine Veränderung der Modellwerte,
bekannte exakt passende Quoten unter 1,20, vorhandene Daily3-Geldregeln,
Navigation und Aborechte. Keine erneute vollständige 11.000er-Suite behauptet.

## Gerenderte Prüfung

Isolierte App `tests/fixtures/sports_editorial_preview.py` mit klar markierten
synthetischen Beispielen; keine Produktionsdatenbank oder externen Sportabfragen.

- 29 Layout-/Randfallkombinationen: normal bei 1440, 1024, 760, 390 und 320 px;
  lange Namen, kurze Historie, leere Auswahl, RisikoBet, drei Daily3-Karten
  und die Abo-Hinweisseite
  jeweils bei 1440, 760, 390 und 320 px.
- Kein horizontaler Seitenüberlauf oder Streamlit-Fehleroverlay, keine
  Page-/Console-Fehler während des finalen QA-Laufs.
- 5/10-Schalter beim ersten Klick, Wechsel per Pfeiltaste, Ergebnisdetails,
  Gegnerliste sowie ganzer Spielblock per Maus/Enter geöffnet und geschlossen.
- Mobile Touch-Emulation bei 390 px: 10 Spiele, Ergebnisdetails und Wechsel zu
  RisikoBet per Tap; fünf untere Navigationsziele mit 58 px Höhe.
- Browserbilder gegen beide freigegebenen Referenzen verglichen.
- Drei direkte Desktop→RisikoBet→Mobil→Wettfinder-Rückwege jeweils mit dem
  ersten Klick bestanden, einschließlich der tatsächlichen Routenzustände.
- RisikoBet-Statuszeile mit explizit gemessener dunkler Schrift auf hellem
  Hintergrund; Mobilnavigation bleibt auch bei einem Seitenabbruch durch den
  unveränderten Abo-Guard sichtbar. Reproduzierter Regressionstest erst rot,
  nach Platzierung der Navigation vor dem Guard grün.

Der Browserlauf fand einen echten Rücksetzfehler: ein HTML-`checked`-Attribut
wurde durch React als kontrollierter Zustand behandelt und stellte nach dem
Klick die Fünferauswahl wieder her. Native unkontrollierte Radios und die
initiale CSS-Fünferansicht beheben den Fehler; der erste Klick wurde erneut
erfolgreich geprüft. Die Navigationsicons sind rein dekorative lokale SVG-Masken,
damit sie die zugänglichen Namen der echten Buttons nicht verändern.

Die erste Produktionsprüfung reproduzierte einen weiteren Rücksetzfall beim
Wechsel von Desktop- auf Mobilnavigation. Die alte versteckte Sidebar war noch
ein drittes navigierendes Widget. Jetzt ist `workspace` gewöhnlicher Appzustand;
ein gemeinsamer Callback synchronisiert beide sichtbaren Widgets vor dem
nächsten Rendern. Der Regressionstest zeigte zunächst die auseinanderlaufenden
Widgetwerte und ist nach der Korrektur grün. Die isolierte Vorschau nutzt jetzt
ebenfalls die echte Initialisierung/Sidebar-Pollfunktion statt diese zu umgehen.

Lokale Nachweise (nicht im Git-Release, vorhandenes Output-Verzeichnis erhalten):
`output/playwright/editorial-browser-qa.js`, `editorial-touch-qa.js`,
`editorial-1440.png`, `editorial-mobile-form.png`, `editorial-case-Daily3.png`
und `editorial-touch.png`.

## Veröffentlichung

UI-Code geprüft; GitHub-/VPS-Veröffentlichung wird nach Commit per Hashvergleich,
internem/öffentlichem Healthcheck und frischem Produktionsbrowser bestätigt.
Kein neuer Backup- oder Sportscan. Der reguläre Tennisdienst startete am
30.09. um 00:05 CEST; er wird für den UI-Deploy nicht unterbrochen.

## Grenzen

Kein Nachweis auf physischem iOS-/Android-Gerät, keine native Store-App.
Keine Aktivierung von Stripe, Konten oder Verkäufen. Verletzungs-, Wetter- und
Müdigkeitseffekte sowie eine bessere Wettqualität werden durch diesen UI-Patch
nicht bewiesen. Modellhistorie, Auswahlen und Geldbuchungen bleiben unverändert.
