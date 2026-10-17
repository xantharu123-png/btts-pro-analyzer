# Fußball-Auswahl und Multigoal – 17.10.2026

## Auftrag und nachgewiesener Fehler

Alle unterstützten Wettarten müssen die mathematische und statistische Prüfung
erreichen. Erst die Auswahl treffen, danach die Anzeige sortieren. Keine
pauschalen Marktverbote, keine erzwungenen Familienquoten und keine Backups.

Der gespeicherte Ilves–SJK-Lauf enthält in derselben echten Modellrevision
RESULT_HOME0,486390, RESULT_AWAY0,251021, DC_1X0,748979 und DC_X2 0,513610.
Der alte Katalog verwarf RESULT_HOME beim Vergleich mit dem viel breiteren
DC_X2-Ereignis. Dadurch fehlte dem nachfolgenden Leser die modale Spielrichtung.
Auch die Oberfläche machte bisher den Markt mit der höchsten marginalen
Trefferchance automatisch zum ersten Vorschlag – unabhängig von dessen
statistischer Modellgüte. Unabhängig reproduziert, nicht aus UI-Text vermutet.

## Begrenzte Korrektur

- Exakte Gegenrichtungen nur innerhalb derselben Wettart/Linie/Teamachse und
  vollständigen Modellrevision nach ihrer Wahrscheinlichkeit vergleichen.
- Unterschiedliche Märkte nach der bestehenden sechsstelligen statistischen
  Rangfolge auswählen: belegte relative Brier-Verbesserung und Evidenz, danach
  Streuung und bestehende vorsichtige Rechnung. Keine neue Schätzformel.
- Gemeinsame logische Verträglichkeit prüfen; die modale Resultatrichtung
  darf nicht durch überlappende Doppelte-Chance-Märkte verschwinden.
- Erst einen statistischen Hauptmarkt je Spiel wählen, dann Spiele nach
  dessen Wahrscheinlichkeit anzeigen. Vereinbare weitere Märkte bleiben
  sekundär sichtbar und werden dort absteigend nach Wahrscheinlichkeit sortiert.
- Vorhandene vollständige Fußball-Kandidaten nur lesend verwenden. Native
  Identitäten, Modell-/Eingangszeiten, Kontextalter und echte exakt passende
  Quoten bleiben gebunden. Keine Neuberechnung aus gerundeten Torerwartungen.
- Manuelle Suche und normale Scan-Ausgaben müssen den vollständigen Pool
  bis zur gemeinsamen Auswahl behalten; 15K-Geldregeln bleiben unverändert.

## Multigoal und historische Verträge

Runtime95 statt90: zusätzlich Gesamttore1–3/1–4/2–4 und Team1/Team2 jeweils1–4.
Bestehende Team1–3/2–4 bleiben erhalten. Inklusive Grenzen, alle Marginalen aus
derselben effektiven gemeinsamen Torverteilung. Eigene zeitlich getrennte
Validierung je exaktem Markt; keine Freigabe einer anderen Linie übernehmen.

Die unveränderte v14-Kalibrierung behält ihre90 Fit-Märkte und ihre40 Torziele.
Owning ORIGINAL-Belege, Replay, alte Tickets und deren Hashes bleiben im alten
Vertrag. Neue Projektionen sind keine nachträglich freigegebenen Kontexteffekte.
Der neue95-Katalog hat eine separate Cache-/Discovery-Identität. Alte90-Metriken
werden nicht als95 umetikettiert; neue strikte Freigaben benötigen95 Hypothesen.

Auch der eigenständige Ticketdefinitionsprüfer kennt die fünf neuen Verträge.
Seine alten90 Definitionen bleiben bytegleich; keine Änderung an HMAC, Geld-
historie, Schlüsselbereitstellung oder Sicherungsverhalten. Es wurde keine
Sicherung ausgeführt.

## Tatsächliche Quotenabdeckung

Genau vier erfolgreiche kontingentgeschützte API-Football-Abfragen: Katalog,
Ilves-Quote und je eine Seite der Gesamt-Torbereichsmärkte186/223 für heute.
Der Katalog führt diese Märkte; beide Tagesproben lieferten **null Angebote**.
Beim geprüften Spiel hatten40/41 nur exakte Torzahlen/offene Enden, keine
echten1–4-Bereichsangebote. Solche Einzelquoten werden niemals addiert.

Sichtbare Tipps brauchen weiterhin eine wirklich exakt passende Quote ab1,20.
Fehlende Bereichsangebote werden nicht durch Über/Unter-Quoten ersetzt. Die
neuen95 Definitionen werden regulär berechnet; bereits gespeicherte alte90
Prognosen werden nicht umgeschrieben. Ein neuer Sportscan wurde nicht beauftragt.

## Prüf- und Veröffentlichungsstand

Der erste vollständige Lauf zeigte58 fehlgeschlagene Testfälle, nicht58
unabhängige Produktfehler. Die ursprünglichen Logs/XMLs
bleiben erhalten. Behoben wurden ein echter fehlender Anschluss der fünf
Definitionen im Standalone-Prüfer sowie Testdatengeneratoren, die historische
90/40-Verträge mit dem aktuellen95/45-Katalog vermischten. Aktuelle strikte
Hypothesentests erwarten95, historische Belege bleiben ausdrücklich90/40.
Keine Markt-/Geld-/Kontextschutzprüfung wurde für einen grünen Test gelockert.

Der neue Numeriktest vergleicht tatsächlichen unveränderlichen Git-Basiscode
und neuen Code im selben Rechenkern: alle90 alten Wahrscheinlichkeitstripel
und die ganze gemeinsame Torverteilung müssen exakt bytegleich bleiben. Ein
gezielter Ein-ULP-Gegentest wird abgelehnt. Ein zuvor hartkodierter Hash hing
von der BLAS-Threadumgebung ab; weder Modellwerte noch historische Pins wurden
an diesen Hash angepasst.

Final gesammelt:15076 Tests, alle14680 ursprünglichen IDs unverändert erhalten,
396 zusätzliche Fälle. Ganze Modulgruppen werden nativ/offline erneut geprüft;
keine Test-Deselektion. Das vollständige203-Fall-Skalierungsmodul läuft separat
mit unverändertem Produktcode und eigenem Quellmanifest. Das Gesamtaggregat
fordert exakt dieselben98 früheren Skip-IDs. Der Abschluss bleibt bis zum
letzten Ergebnis offen.

Die erneute Vollprüfung fand danach noch genau fünf betroffene Testfälle eines
gemeinsamen Anschlussfehlers: der vorhandene Update-Launcher erwartete noch
den alten SHA-256 des jetzt um fünf Definitionen erweiterten Ticketprüfers.
Nach unabhängigem Review wurde nur dieser eine Pin aktualisiert. Der historische
Reparaturinstaller bleibt unangetastet; der eingefrorene Paritätstest rekonstruiert
die exakte alte Pin-Zeile vor allen unveränderten historischen SHA-Prüfungen.
Die vollständigen drei besitzenden Testmodule wurden danach erneut ausgeführt:
572 bestanden,8 unveränderte Skips, Exit0.
Kein Update-/Backup-Ablauf wurde auf dem VPS dafür aufgerufen.

Gezielte RED/GREEN-Belege und zwei unabhängige Reviews liegen außerhalbGit unter
`C:/Projekt/BetBoy/output/market-selection-20261017/`. Das strenge mehrstufige
Endaggregat ist bestanden:14978PASS/98 gleiche Skips; alle15076 gesammelten
IDs exakt einmal in den finalen XML-Belegen, alle14680 früheren IDs erhalten.
806 aktuelle Quell-/Fixture-Hashes, exakt abgegrenzte und unabhängig geprüfte
Besitzer-Nachläufe. Ursprüngliche Fehlbelege bleiben erhalten, kein Ausfiltern
oder Lockern der Assertions. Zusätzlich11 native No-Backup-Deploy-Guardtests
und3 reine Dokumente-Pull-Tests bestanden.

Commit/Push/Deploy sowie der echte gespeicherte Katalog- und Browsernachweis
folgen jetzt; deren konkrete Git-/VPS-Identität wird anschließend ergänzt.
Keine bessere Wett-Rendite aus Softwaretests ableiten.

Unabhängig offen bleiben tatsächliche belastbare Verletzungs-/Wetter-/Müdigkeits-
wirkungen und der vollständige NHL-Personalmodellnachweis. Dieser Auswahlfix
behauptet keine Erledigung dieser anderen Arbeitspakete.
