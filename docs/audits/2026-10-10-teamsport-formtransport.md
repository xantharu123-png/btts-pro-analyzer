# Teamsport-Formtransport – 10.10.2026

## Umfang und Boston-Ursache

Fortsetzung des BOS/PHI-Preis-/Kurzcheck-Fixes, Ausgangscommit
`2ad2ba6b9a36fbe5e35db318e0e85b29e91a2b91`.

Der gespeicherte Tageslauf 04:12 CEST war vor der Wiederanbindung des
Eishockey-Preisproducers entstanden. Sein Preisstatus lautete
`disabled_for_model_only_tips`; ein späterer Code-Deploy erneuerte diesen
gespeicherten Lauf nicht. Zusätzlich lieferte die Karte nur die interne
Torzeile 3,09/2,60, ohne ausgewählte Seite und Gegner verständlich zu verbinden.
Beides war im vorherigen Release repariert und in Produktion geprüft:
Boston 57,7 %, Philadelphia 42,3 %, gespeicherter echter Boston-Preis 1,75.
Das ist keine Aussage über eine inzwischen noch erhältliche Buchmacherquote.

Die ergänzende Formlücke war separat: `OriginalPrematch` enthielt tatsächlich
normalisierte, bereits verbrauchte Spiele. `team_recent_facts` erzeugte daraus
strukturierte Ergebnisse, der RisikoBet-Adapter speicherte aber nur zwei
Textzusammenfassungen. `sports_form.team_forms` benötigte die verlorenen Zeilen.
Ein realer Adapter-/SQLite-/JSON-/Kartenlauf reproduzierte null Formkacheln
für Basketball und Eishockey. Der alte UI-Test hatte diesen Producerweg durch
manuell eingesetzte Formdaten umgangen.

## Begrenzte Reparatur

- Optionaler `team-recent-results-v2`-Anhang im bestehenden Snapshot, maximal
  zehn verbrauchte Spiele je Seite. Keine zusätzliche Datenbank/Tabelle,
  Migration, Abfrage, Prognoseberechnung oder Modellfamilie.
- Bindung an Sport, Quelle, Wettbewerb, Ereignis, native Teilnehmer, Modell-
  Eingabehash, Startzeit und Berechnungs-/Datenschnittzeit. Ergebnisbeobachtung
  strikt nach Spielbeginn und vor dem Datenschnitt. Nur bereits vom Modell
  akzeptierte Revisionen; keine Wiederbelebung korrigierter/gelöschter Ergebnisse.
- Endstände und Gegnerdetails nur aus exakt passenden Rohzeilen: Quelle,
  Wettbewerb, Variante, Teilnehmer, Ereignis und Zeiten. Eishockey verwendet
  den tatsächlichen Endstand inklusive Verlängerung/Penaltyschießen, nicht die
  für das Tormodell bereinigte reguläre Torzahl. Fehlende Details bleiben leer.
- Verschachtelte Werte unveränderlich und bei JSON-Export vollständig gelöst.
  Neue Anzeigeanhänge erzeugen ausdrücklich neue Revisionen; bestehende
  Prognose-/Snapshotzeilen werden nicht ergänzt oder überschrieben.
- Abwesender Anhang wird wie zuvor nicht serialisiert. Fest geprüfte alte
  Snapshot-IDs und bestehende gespeicherte Payloadbytes bleiben unverändert.
- Beide JSON-Lader und beide Speicherprüfpfade berücksichtigen den Anhang.
  Der unabhängige Review fand eine ausgelassene Wettbewerbs-/Schnittbindung im
  Speicherprüfer. Zwei neue rote Regressionen reproduzierten sie; danach wurde
  die Bindung auf beiden Pfaden ergänzt und der Gegentest bestanden.
- Formkacheln nutzen die vorhandene Darstellung: fünf/zehn echte Ergebnisse,
  Sieg/Niederlage, Endstand, Datum und Gegner. NHL-Vollnamen nur nach exakter
  geprüfter Quelle-/Liga-/ID-/Aliasbindung, ohne die Modellidentität umzubenennen.

## Prüfung

Code eingefroren als `702beca820b3aa6359dfa9522976e84b5f791071`.

- Nach allen Korrekturen: **266 gezielte Tests und vier Untertests bestanden**.
- Separater vorgesehener Django-Lauf: **47 Portaltests bestanden**; vorhandene
  `.portal-venv` verwendet, keine Installation. Bare pytest über das gesamte
  Repository ist nicht der korrekte gemeinsame Runner für Sportsuite und Django.
- Unabhängiger Abschlussreview: keine verbleibenden konkreten Findings im
  begrenzten Diff. Acht Transporttests im separaten Gegentest bestanden.
- Interner Browser mit ausdrücklich markierten isolierten Testdaten: fünf auf
  zehn Spiele und zurück per sichtbarer Bedienung; Gegnerliste geöffnet;
  390 und 320 Pixel ohne horizontalen Seitenüberlauf, keine Browserwarnungen
  oder -fehler. Desktopansicht und tatsächliche Endstände separat geprüft.
- Vollständige Sportsuite sammelte 13.015 Tests auf unverändertem Code, starb
  bei etwa 22 % jedoch mit Windows-Python-Exit `0xC0000005`, während ein
  60-Sekunden-Faulthandler-Dump lief. Kein normaler Assertionfehler war zuvor
  ausgegeben; der Teilstart ist ausdrücklich kein PASS. Derselbe Einzeltest
  (`test_actual_stored_evaluation_replays_without_writing_or_approving`)
  reproduzierte den nativen Crash beim Dump auch ohne Streamlit-Watcher.
  Identischer Einzelvergleich ohne den rein diagnostischen Dump-Timer
  vollständig bestanden (79,41 s Setup + 22,77 s Test, insgesamt 103,31 s).
  Ein allgemeiner CPython-/JSON-Bug ist damit nicht bewiesen. Ausgehende
  Test-Netzverbindungen blieben gesperrt.
  Ein älterer Teilstart wurde wegen des Review-Fixes kontrolliert beendet und
  ebenfalls nicht als PASS gezählt.
- Vollständige Wiederholung ohne periodischen Diagnose-Dump, ohne ausgeschlossene
  Tests und auf demselben Produktionscode: **12.909 bestanden, neun fehlgeschlagen,
  97 übersprungen, 115 Untertests bestanden**, 3.133,11 s, Exit 1. Alle neun Fehler
  lagen in derselben parametrisierten Veröffentlichungsfixture: Sie änderte
  Quelle/Wettbewerb, behielt aber den an die ursprüngliche Quelle gebundenen
  Formanhang. Der neue Domain-Guard lehnte diesen widersprüchlichen Aufbau
  berechtigt vor der älteren Veröffentlichungsprüfung ab.
- Nur dieser absichtlich fremde Testaufbau entfernt jetzt seinen unpassenden
  Anhang. Der ursprüngliche Veröffentlichungsguard und seine Assertion bleiben
  bestehen; neun zusätzliche Fälle prüfen explizit die frühere Ablehnung mit
  behaltenem Anhang. **Keine Produktionscodeänderung nach dem Volltestlauf.**
  Frische Wiederholung der gesamten geänderten Testdatei sowie der betroffenen
  Domain-/Producer-/SQLite-/JSON-/Karten-/Quoten-/Identitätspfade:
  **586 bestanden, Exit 0, 20,04 s**. Unabhängiger tatsächlicher Diffreview:
  kein weiterer Befund. Alle neun ursprünglichen Fehlerfälle sind darunter.
  Das sind getrennte reale Läufe, kein behaupteter einteiliger Vollsuite-PASS.

Prüfdateien außerhalb Git: `C:/Projekt/BetBoy/output/team-form-20261010/`.
Volltest- und Wiederholungslogs/JUnit liegen getrennt vor (`full-sports-no-dump.*`
und `publication-repaired.*`). Veröffentlichung und Produktionsabnahme sind noch
offen; am 11.10. um 00:08 CEST lief der reguläre Tennisjob seit 00:05. Er wird
nicht für das Deployment unterbrochen. App und beide Healthchecks waren gesund.

Separater Produktionsstatus, kein Formtransportfehler: Shadowlauf 00:02:02–
00:02:31 CEST auf altem HEAD `2ad2ba6` mit Exit 1 / `partial`, weil für Ereignis
1550985 keine frische Bet365-Quote mit Providerzeit vorlag. Ein Kandidat wurde
zur Wiederholung verschoben; keine Prognose/Schlussquote geloggt. Kein Crash.
Dieser Preisnachweis wird nicht erfunden und die Teilmeldung nicht kaschiert.

## Grenzen

Alte BOS/PHI-Snapshots erhalten keine nachträglich erfundene Formhistorie.
Neue strukturierte Formdaten entstehen im nächsten regulären Modelllauf.
Ein alter Textbeleg wird nicht zurückgeparst. Eine sichere alte Rekonstruktion
würde den ursprünglichen Zielspiel-Datensatz samt Variante und exakt identischen
Modell-Eingabehash benötigen; das ist nicht nachgewiesen und wurde nicht getan.

Keine neue Produktionssicherung, Bereinigung, Sport-/API-Abfrage oder
Kontobewegung. Chancen, Marktregeln, Rangfolge und Vorhersagezeiten unverändert.
Software-/Darstellungsprüfung beweist keine bessere Wettqualität und keine
numerisch validierte Verletzungs-/Wetter-/Müdigkeitswirkung. Globale Sortierung
und zusätzliche Eishockeyligen sind getrennte offene Anfragen, kein Teil dieses
begrenzten Formtransport-Fixes.
