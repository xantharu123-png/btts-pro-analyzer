# BetBoy: Kontextmodell und Daily3 – Prüfung 22.09.2026

Stand der Prüfung: Der zuvor veröffentlichte Code `c784195` war auf lokalem
`main`, GitHub und VPS identisch. App und Caddy waren aktiv, der lokale
Healthcheck lieferte `ok`; auf dem VPS waren rund 20 GB frei. Die Timer
berechnen, deployen aber keinen Code.

## Tatsächliche Ergebnisse statt Abschlussbehauptung

- Tennis-Tageslauf 07:17–07:31 CEST: 74 Prognosen verarbeitet, 13 neu
  gespeichert, Prozess-Exit 1. Die alte Prognose einer nachträglich geänderten
  WTA-Paarung darf das Ergebnis der Ersatzpaarung nicht erben. Die drei im
  Capture-Bericht genannten `retired_outcome_events` sind nicht die Ursache
  des generischen Fehlers; der aktive Konflikt liegt bei ESPN 183992. Die
  neue Paarung wurde erst nach ihrem vorverlegten Beginn prognostiziert.
- Wettfinder 23:07–23:12 CEST: Fußball selbst `completed`, 0 Betriebsfehler;
  Gesamt-Exit 1 durch `tennis:event_snapshot_ambiguous` in der separaten
  RisikoBet-Abrechnung. 227 fällige Kandidaten, 0 Abschlüsse, 227 offen.
  Der Anbieter verwendete ESPN 183996 für Julia Avdeeva/Yuki Naito und später
  Ayla Aksu/Yuki Naito. Der Ergebnis-Leser/Runner routet nur über die
  gemeinsame Event-ID, nicht über eine gebundene Inkarnation. Alte Prognosen
  und Geldbuchungen dürfen nicht automatisch gewonnen, verloren oder storniert
  werden. 96 weitere Kandidaten haben gleichrangige Revisionsstände; das
  40-Event-Rotationslimit ist eine separate erwartete Abdeckungsgrenze.
- Der enge lokale RisikoBet-Fix erkennt die nachweisliche Wiederverwendung
  der nativen Tennis-ID an unterschiedlichen Prognose-IDs und Paarungen. Er
  isoliert nur dieses Event, lädt dafür kein Ergebnis und lässt beide alten
  und neuen Kandidaten offen; andere Events können weiter abgerechnet werden.
  Die Diagnose ist Admin-Abdeckung statt technischer Gesamtfehler. Der
  Produktionsdatenbestand enthält sieben Snapshots der alten Paarung mit
  Prognose-ID 1585 und zwei der neuen mit 1637. 234 RisikoBet-Tests grün.
  Gleiche Prognose-ID mit widersprüchlichem Namen oder umgekehrt bleibt
  weiterhin ein technischer Fehler. Die v2-Abrechnungsbindung fehlt noch.
- Rein lesende native Tennis-Inventur: 2.697 Originalpublikationen,
  256 unterschiedliche rechtzeitige Originalevents, aber nur 163 eindeutig
  passende finale Events. Das sind **nicht** 2.697 unabhängige Fälle. Schon die
  Untergrenze von 200 unangetasteten Testevents wird vor Training und
  Abstimmung nicht erreicht. Die Inventur ist keine Qualitätsfreigabe.
- Im Fußball-Kontextspeicher lagen 29 ORIGINAL-v2-Bindungen. Vorhandene
  Ausfall-/Aufstellungs-/Spielerbelege sind nicht dasselbe wie ein empirisch
  qualifizierter Verletzungs- oder Müdigkeitseffekt.

## Daily3 und Modellwirkung

- ATP besitzt den gebundenen Same-Match-Belagsvergleich; WTA ist wegen des
  negativen historischen Freigabeurteils weiterhin ausdrücklich ausgenommen.
- Basketball und Eishockey liefern derzeit Research-Prognosen, aber keinen
  zweiten qualifizierten Same-Market-Modellzustand. Ein anderer Markt oder eine
  Preis-/Risiko-Korrektur wäre kein defensiver Modellvergleich.
- E-Sport speichert ebenfalls nur eine sportliche Modellprognose; der
  Risikoabschlag ist keine unabhängige Variante. Ein Effektartefakt und
  ausreichende native Ergebniskohorten fehlen.
- Keine Sportart erhält künstlich drei Daily3-Auswahlen, eine fiktive 50-%-
  Vergleichsbasis oder eine nicht nachgewiesene Wirkung. Cricket bleibt ausgenommen.

## Nächste überprüfbare Schritte

1. Tennis-Capture führt nun lokal ausschließlich den nativ belegten
   Teilnehmerwechsel als nicht auswertbare alte Paarung; beschädigte oder
   widersprüchliche Belege bleiben Betriebsfehler. Der CLI-Test zeigt Exit 0
   mit ausdrücklich `partial` und Event-ID. 300 gemeinsame Tennis-/Fußball-
   Regressionen bestanden. Der vollständige App-Test und die produktive
   Nachprüfung stehen bei diesem Nachtrag noch aus. Ein direkter Replay des
   geänderten Codes gegen die VPS-Datenbank im QA-Prozess wurde durch die
   Zugriffsprüfung abgelehnt und nicht umgangen; die äußeren aktuellen ESPN-
   und Revisionsprädikate wurden mit installiertem Code read-only bestätigt.
2. Für die spätere Abrechnung der isolierten RisikoBet-Paarungen braucht es
   eine versionsgebundene Tennis-Inkarnation aus Event,
   Wettbewerb und nativen Teilnehmern. Nicht nur Request, Ergebnis, Issue und
   Runner, sondern auch neue Kandidaten-ID, Snapshot und terminaler
   Store-Eindeutigkeitsindex müssen diese Inkarnation binden. Vorhandene
   V1-Kandidaten/Terminals dürfen nicht umgeschrieben werden; eine alte Zeile
   kann nur mit reproduzierbarem Original-, Status- und Input-Hash append-only
   zugeordnet werden. Das ESPN-Finale benötigt einen dauerhaft gespeicherten,
   überprüfbaren nativen Beleg einschließlich Teilnehmern, Sieger-Flags,
   Score und Empfangszeit. 1637 darf erst nach eindeutiger Bindung geprüft
   werden; 1585 bleibt offen. Ein bloßer Statuswechsel oder Split des
   Ergebnis-Lesers reicht wegen der bisherigen `candidate_id`-Eindeutigkeit
   nicht aus. Keine Auszahlung oder Stornierung ohne diesen Vertrag.
3. Der neue reine Fußball-ORIGINAL-v2-Vergleich prüft Rohzellen,
   Marktsettlement und effektive Mittelwerte (147 angrenzende Tests grün).
   Er prüft weder Projektionsziele noch einen manifestgebundenen Aufrufer.
   Weiter fehlen vollständiges Replay der Produktionskalibrierung,
   Kontextanwendung, Wirkungstraining und zeitlich getrennte Qualitätsabnahme.
4. Weitere echte unabhängige Ergebnisfälle sammeln. Erst danach die
   vordefinierte Train-/Tune-/Testprüfung und Marktverteilungsmetriken ausführen;
   keine Testbeobachtungen vorzeitig zum Modell-Fit verwenden.

Dieser Bericht ist eine technische Übergabe, keine Wett- oder
Einkommenszusage. Aussagen zu Push/VPS-Freigabe des neuen Codebausteins folgen
erst nach Abschlussreview und separater Veröffentlichung.

## Nachtrag 23.09.2026: technische Veröffentlichung

- Unabhängiges Patchreview ohne neue Befunde. 300 gemeinsame Tennis-/Fußball-
  Regressionen sowie 234 RisikoBet-Tests bestanden.
- `f5c0971c0bc3a09017b70b259f6b875efeeb149a` ist auf GitHub `main` und
  dem VPS identisch. Code-Fast-Forward ohne Datenmigration und ohne neues
  Backup-Archiv; App und Caddy aktiv, Healthcheck `ok`, sieben Rechentimer
  aktiv, täglicher Backup-Timer weiter deaktiviert.
- Die breite Suite lief bis 6.999 bestandenen Tests und traf dann auf einen
  E-Sport-Test, der `EsportsScanner.__new__` ohne die im echten Konstruktor
  angelegte Fehlerliste verwendet. Nach Ergänzung dieser Testinitialisierung
  bestanden das gesamte betroffene Modul und alle noch nicht abgeschlossenen
  Testmodule mit weiteren 4.061 Tests. Damit wurden alle 275 Testmodule in
  zwei Stufen abgedeckt; dies ist kein einzelner ununterbrochener Vollsuite-Lauf.
- Automatischer Wettfinderlauf ab 01:37 CEST auf `f5c0971`: Exit 0,
  `completed`, null technische Fehler. Die wiederverwendete Tennis-Event-ID
  ist nun `native_event_identity_reused` mit operativem Fehlerzähler 0.
  229 fällige RisikoBet-Kandidaten blieben offen, null wurden terminal
  abgerechnet; insbesondere wurde die alte Paarung nicht als Gewinner oder
  Verlierer umgedeutet.
- Der reguläre Tennis-Tagesdienst wurde auf dem neuen Commit einmalig zur
  Abnahme gestartet: 01:44–02:01 CEST, Exit 0, Scan und Gesamtpipeline OK,
  41 neue Prognosen. Capture `partial`, aber `issues=[]`; die alte WTA-
  Paarung ESPN 183992 erscheint ausdrücklich unter
  `native_unavailable_outcome_events`. Kein fremder Sieger übertragen.
- Der Nullwert der RisikoBet-Abrechnung um 01:37 ist kein Beweis eines
  dauerhaften Loaderfehlers: Der Tennis-Scan begann erst 01:44 und lieferte
  danach viele neue Endresultate. Bei 14 heute passenden Belegen liegt der
  Ergebnis-Zeitstempel nach dem Wettfinderlauf; für vier weitere fehlt ein
  separates Schreibdatum. Der Runner hat am 22.09. bereits 54 Tennis-
  Kandidaten abgerechnet. Die automatische Gegenprobe nach dem Scan folgt
  um 02:07 CEST; vor deren Ergebnis keine Schlussfolgerung erzwingen.
- Rein lesende Neuaufnahme um 02:09 CEST nach dem Tennis-Scan:
  2.784 Originalpublikationen, 296 eindeutige rechtzeitige Originalevents,
  davon 222 mit exakt passendem regulärem Finale (+59 gegenüber den zuvor
  gemessenen 163). Die 200er-Untergrenze ist nur für den Gesamtbestand
  erreicht; 200 unangetastete Testevents zusätzlich zu Training/Tuning,
  drei Zeitblöcke und die vorab verlangten Brier-/Logloss-/Kalibrierungs-
  prüfungen fehlen. Kein Effektfit und keine Qualitätsfreigabe.
- Automatischer Wettfinder-Gegenlauf 02:07–02:13 CEST nach dem Tennis-Scan:
  Exit 0, `completed`, null technische Fehler. RisikoBet prüfte wieder 47
  Events und schloss nun 29 andere Kandidaten terminal ab; 200 blieben offen.
  Die neun gespeicherten Snapshots für die wiederverwendete WTA-Event-ID
  (Prognosen 1585/1637) haben weiterhin **null** terminale Einträge. Die
  Abrechnung anderer Events funktioniert, ohne die alte/neue Paarung zu
  vermischen. Dies ist keine Freigabe der v2-Inkarnationsmigration.
