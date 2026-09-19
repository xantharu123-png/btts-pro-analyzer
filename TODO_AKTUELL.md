# BetBoy – aktuelle To-dos und Account-Übergabe

## Kontextanschluss und Daily3-Spielvergleich – 19.09.2026, laufende Reparatur

- Nicht als vollständig fertig melden: numerische Verletzungs-/Müdigkeits-/
  Wetterwirkung ist weiterhin nicht trainiert und empirisch freigegeben.
  Die vorhandenen Prognosen sind echte Berechnungen, aber ohne diese Wirkung.
- Daily3 v4 vergleicht aktive/Form-Variante mit der Saison-/Heim-Auswärtsbasis
  derselben Begegnung. Favoritenstärke allein reicht nicht. Die zusätzlichen
  zwei Prozentpunkte sind eine Relevanzregel, kein Sicherheits-/Valuebeweis.
  Keine Marktverbote oder Quotenfilter; normale Prognosen bleiben erhalten.
- Kanonischer Fußballworker erhält die vorhandene Originalaufnahme mit
  dauerhaftem Aufnahmebudget: 4 MiB/Sitzung, 8 MiB/UTC-Tag, 128 MiB insgesamt
  an zusätzlicher JSON-Nutzlast. Keine neue Sicherung oder Bereinigung.
- Nicht gesendete Spielerhistorienabfragen wegen API-Budgetreserve lösen
  keine neue 24-Stunden-Wartefrist mehr aus; echte Fehlantworten weiterhin.
- Tatsächliche Lücken: keine Fußball-Originale oder trainierten Effekte im
  geprüften VPS-Bestand; Tennis nur 112 unterschiedliche Ergebnisereignisse.
  Neue Originalaufnahme ersetzt weder native Zuordnung noch Replayfreigabe.
- Prüf-/Releaseabschluss folgt im [Reparaturbericht](docs/audits/2026-09-19-kontextanschluss-und-spielvergleich.md).
  Cricket, Echtgeldregeln, alte Archive und deaktiviertes Tagesbackup erhalten.

## Daily3 19.09.2026 – Auswahlregel und Teil-Refresh repariert

- `0a54313`: keine Sortierung allein nach höchster Rohwahrscheinlichkeit mehr.
  Versions- und spielgebundener Vergleich zur historischen Markthäufigkeit,
  mindestens 70 Prozent in allen drei vorhandenen Modellvarianten. Keine
  pauschalen Wettartenverbote und kein Quotenfilter; normale Prognosen erhalten.
- `533a98f`: echter VPS-Befund behoben – ein nicht modellierbares Spiel verwirft
  nicht mehr die erfolgreichen Berechnungen seiner ganzen Gruppe. Alte Daten
  fehlgeschlagener Spiele werden weder gelöscht noch als frisch umetikettiert;
  ihr Fehler bleibt über weitere Gruppen hinweg sichtbar.
- Beide Commits auf main/GitHub und VPS; 1.090 Tests/111 Untertests jeweils im
  Worktree und main bestanden. App/Healthchecks bestätigt. Normaler Datenlauf
  um 15:26:36 CEST beendet: 51 Spiele neu modelliert, 9 weitere weiterhin
  unmodelliert (deshalb ehrlich Teildaten/Exit1). Gründe dieser neun offen.
  Echter Vorher-/Nachher-Vergleich bestätigt: alte Regel liefert exakt die
  beanstandeten drei Tipps; neue Regel Reykjavík-Gesamtüber2,5, Siriusüber0,5,
  Santosüber0,5. Zwei einfache Märkte bleiben erlaubt, kein Marktverbot.
  Kein zusätzlicher vollständiger 10k-Testlauf.
- Vergleichsproduzent bislang nur Fußball; ohne passenden Vergleich keine
  Daily3-Auswahl anderer Sportarten, deren normale Prognosen bleiben sichtbar.
  Kein empirischer Nachweis besserer Treffer-/Gewinnqualität. Verletzungs- und
  Müdigkeitswirkung bleibt separat offen; Cricket unverändert.
- Nur Streamlit-AppTests: interner Browser scheitert schon beim Start an
  Windows-ACLs. Keinen externen Browser übernehmen. Keine neue visuelle
  Desktop-/Mobile-Abnahme behaupten. Keine weitere Speicherbereinigung oder
  Sicherung; Tagesbackup bleibt aus.
- [Reparaturbericht und ehrliche Grenzen](docs/audits/2026-09-19-daily3-auswahlvergleich.md).

## Spielblöcke 19.09.2026 – gemeinsames Auf-/Zuklappen live

- Funktionscommit `1e918b9` auf main/VPS: automatischer Wettfinder zeigt jedes
  Spiel nur einmal, mit sämtlichen bisher sichtbaren Auswahlen im selben Block.
  Hervorgehobene Spiele zunächst offen, weitere zunächst geschlossen.
- Zustand bleibt innerhalb der Browsersitzung bei Sportfilter-/Seitenwechseln
  erhalten. Seiten enthalten ganze Spiele, keine zerschnittenen Marktgruppen.
- 907 betroffene Tests plus 26 Untertests jeweils in Worktree und main grün.
  Lokal Desktop/Tablet/Mobil und echter VPS-Browser geprüft; Beispiel
  Brommapojkarna–Göteborg mit allen zehn Auswahlen gemeinsam geschlossen.
- Keine Modell-, Quoten-, Geld-, Datenbank- oder Backupänderungen. Bekannte
  fachliche Restarbeiten bleiben offen. Keine erneute Speicherbereinigung.
- [Abschluss und Grenzen](docs/audits/2026-09-19-spielbloecke.md).

## Prognosekarten 19.09.2026 – kompakte Fakten und Ausfalldetails live

- Funktionscommit `763c741` auf main/VPS. Kurze Torprognose und Faktenfelder
  statt langer sichtbarer Absätze, Einzelheiten per Klick/Tastatur; Wettfinder
  und aktuelle Daily3-Karten. Keine Änderung von Wahrscheinlichkeit oder Geld.
- Spielerstatus ehrlich getrennt: alte gemischte Listen nicht als gesicherte
  Ausfälle bezeichnen. Neue Läufe speichern getrennte Namen; kein Zusatzabruf.
  Nicht eingerechnete Ausfallwirkung bleibt direkt sichtbar.
- 713 Tests und 26 Untertests jeweils im Worktree und main bestanden;
  Desktop/Mobil, Tastatur und echte Website geprüft. Health/Timer bestätigt.
- Keine Speicherbereinigung/Migration/Sicherung wiederholen. Tagesbackup aus.
  Vollständige Modellwirkung und empirische Qualität bleiben offen.
- [Abschluss und Grenzen](docs/audits/2026-09-19-kompakte-prognosekarten.md).

## Daily3 19.09.2026 — defensives Modellprofil und kompakte UI live

- Funktionscommit `1985407c176e4cf5ecc4a9d5b2a93636b8634673` auf main/VPS.
  Mindestens 70% Modellschätzung, höhere Modellchance vor Vielfalt, ein Spiel
  pro Slot. Kein Gewinnziel-/Quotenfilter, keine Änderung der normalen Rangfolge.
- 344 betroffene Tests im Worktree und nochmals in main bestanden. Desktop,
  Mobil, leer/gefüllt und die echte Website geprüft. Kein zusätzlicher Gesamttest.
- Hauptansicht gekürzt; allgemeine Regeln optional, konkrete Unsicherheiten
  weiterhin sichtbar. Echtgeld-/Budget-/Abrechnungslogik unverändert.
- VPS-Codewechsel und Healthchecks bestätigt. Keine neue Speicherbereinigung,
  Datenmigration oder Sicherung. Tagesbackup bleibt disabled, Retention unverändert.
- Offen bleiben empirische Qualität, vollständige Verletzungs-/Müdigkeitseffekte
  und die vorher bestehenden Teildaten-/Datenjobfehler. Höhere Roh-Modellchancen
  sind keine nachgewiesene Sicherheit und kein CHF150-Einkommensversprechen.
- Details und ehrliche Abgrenzung der SSH-Nachlaufkante:
  [Releasebericht](docs/audits/2026-09-19-daily3-defensiv.md).

## Speicherreparatur 19.09.2026 — live, ca. 11:29 CEST verifiziert

- **Erledigt:** Funktionscommit `8caf022b562c561c7d23b4b8363791bb0869d9d3`
  gepusht und auf VPS bereitgestellt; nachfolgende Abschlussdokumentation
  aendert keinen Produktcode. Vorherige Produktreparaturen damit ebenfalls
  ausgeliefert. Wartungsauftrag `betboy-storage-repair-20260919-b.service`
  erfolgreich (Exit 0). Keine bereits erledigte Speicherbereinigung wiederholen.
- Produktivdatenbank **3.326.431.232 -> 2.092.552.192 Bytes**, rund 1,23 GB
  weniger. 36 aufgeblähte Snapshots umgepackt; alle 1.041 Analyseidentitäten,
  926.502 Inhalts-/Empfangsbelege und übrige Tabellen-/Schemaidentitäten
  erhalten. SQLite/Fremdschlüssel ok, große Inline-Restfälle 0. Frischer
  normaler Lesetest mit 504.808 Verweisen und unverändertem Hash bestanden.
- App/Caddy aktiv, lokale und öffentliche Healthchecks ok; sechs Rechentimer
  wieder aktiv. Tagesbackup disabled/inactive; Aufbewahrungstimer unverändert.
  Kein neues Tages-/Updatearchiv; alte Archive und Root-Updater nachweislich
  unverändert. Nur eigene temporäre synthetische QA-Daten (~114 MB) entfernt.
- **Nicht daraus ableiten:** vorher fehlgeschlagene/degraded Tennis-/Wettfinder-
  Läufe, vollständige Verletzungs-/Müdigkeitswirkung oder empirische Qualität
  seien erledigt. Normale Beobachtungshistorien dürfen weiter wachsen; behoben
  ist die unbeabsichtigte Vollkopie jeder großen Nachweisliste pro Analyse.

- Konkreter Defekt behoben: ab 500.001 Nachweisverweisen wurden rund 34 MB
  pro Analyse erneut inline gespeichert. Gemeinsame Blockspeicherung und
  Leser funktionieren nun auch oberhalb dieser Grenze; Inhalte/Hashes und
  Prognosen bleiben unverändert. Keine Statistiken oder Wetthistorien löschen.
- 25 gezielte Tests jeweils Windows und VPS-Linux bestanden. Gesamtlauf:
  10.293 bestanden, 96 Skips, 111 Untertests, 16 Windows-Git-Setupfehler;
  die vollständige betroffene Testdatei anschließend mit exakt scoped
  safe.directory: 56 bestanden. Zusammen 10.309 unterschiedliche Tests
  erfolgreich, keine Quell-/Teständerung danach. Nicht als einzelnen grünen
  Gesamtlauf ausgeben. Details: [Speicherbericht](docs/audits/2026-09-19-snapshot-speicherfehler.md).
- Nutzer will keine neuen Tages-/Updatearchive. Tagesbackup auf VPS bereits
  disabled/inactive. Vorhandene Archive und Aufbewahrungspolitik unverändert.
  Alten Updater nicht unverändert starten: er erzwingt Archive und aktiviert
  Tagesbackups erneut. Dieser Release verwendet einen geprüften Code-only-
  Ablauf ohne Root-/Dependency-/Finanzmigration und danach die bestehende
  verlustfreie Inline-Snapshot-Kompaktierung bei stillstehenden Schreibern.
  Dies ist kein Auftrag, den alten Updater oder die Kompaktierung erneut
  auszuführen. Fachliche Modelllücken bleiben separat offen.

## Produktreparatur 19.09.2026 — committed und gepusht, VPS separat

**Veröffentlicht:** Reparaturpaket `2cd0a982a96331996955779a8dfff0466ecfb2fd` ist im Hauptcheckout auf main und auf GitHub-main, nach regulärem Push per `ls-remote` bestätigt. Nachfolgende Änderungen ergänzen nur diese Abschlussdokumentation. Funktions-/Teststand `d0759b1`. Alle unabhängigen Task-/Gesamtreviewbefunde geschlossen. Keine Produktions-/VPS-Änderung oder Speicherbereinigung in dieser Runde.

**Tests abgeschlossen:** Vollsuite auf `d0759b1`:10303 bestanden,96 Skips,111 Untertests,Exit0,1545.58s; neun reine JUnit-Berichtshinweise. Anschließend Hauptcheckout auf `2cd0a98`:625 bestanden,79 Untertests,Exit0,90.16s. Keine Quell-/Teständerung während oder nach diesen Läufen. Logs im Worktree `output/playwright/product-full-suite-20260919-d0759b1.{log,xml}` und im Hauptcheckout `output/playwright/product-main-checkout-20260919-2cd0a98.log`. Vorige Fixture-/Ownershipfehler im Reparaturbericht erklärt; keine Schutzregeln/Pins gelockert. Erledigte Tests nicht erneut als laufend übernehmen.

Dieser Abschnitt ersetzt die darunterstehenden historischen Statusmeldungen. Nutzerauftrag: bestätigte Produktfehler beheben, committen und pushen; Cricket unverändert. Keine weitere Speicherbereinigung und keine automatische Codeauslieferung durch Timer.

- Ausgangsstand des geprüften Produkt-Audits: lokal/GitHub/VPS `c64218b`. Audit [2026-09-18-produktqualitaet.md](docs/audits/2026-09-18-produktqualitaet.md); Reparaturfortschritt [2026-09-18-produktreparatur.md](docs/audits/2026-09-18-produktreparatur.md).
- Arbeit im bereits genehmigten Worktree `.worktrees/context-capacity-recovery-20260910`, Branch `codex/context-capacity-recovery-20260910`; Hauptcheckout per Fast-forward aktualisiert, VPS unverändert. Bestehender Worktree und fremde/ungetrackte Prüfdateien bleiben erhalten. Kein erneutes Worktree/Design/Push-Permission-Pingpong.
- Lokal erledigt und unabhängig geprüft: `f844f05` Preiswarnung/keine erfundene Erholung; `c953d46`+`9467148` gemeinsame widerspruchsfreie Auswahl, belegte Hervorhebung/Analyse, keine pauschalen Marktverbote; `f42e264` gemeinsame konsistente Fußballverteilungen mit eigener Validierungsversion und alter Ticket-/ORIGINAL-Kompatibilität. 709 betroffene Tests plus97 Untertests für den mathematischen Stand; **keine neue Gesamt-Suite** daraus ableiten.
- WTA-Dauererhaltung `534d27d` + `2d92eb9` ist unabhängig nachgeprüft: alle drei Reviewbefunde geschlossen, echte historische Laufzeit-/Trainingsreplays erhalten; 360 betroffene Tests und 92 numerische Tests bestanden, 3 Skips. Keine Müdigkeitswirkung daraus ableiten.
- Basketball-/Eishockey-Brücke `fdd04bf`+`423e888` unabhängig abgeschlossen: dieselbe vorhandene Berechnung wird im normalen Wettfinder konsumiert, Belege unveränderlich übernommen. Daily3 erklärt gemeinsamen Bestand und tatsächliche Anzahl. 468 Tests plus26 Untertests; Fixrunde275 plus26 Untertests. Finanz-Lesevorprüfung `5ff08a9` unabhängig geprüft:217 Tests plus85 Untertests; Geld-/Integritätsregeln unverändert. Browser-Rundungsfehler mit `a322430` behoben: kein gerundetes100% bei Wahrscheinlichkeit kleiner1;160 betroffene Tests bestanden.
- Kausale Fußball-Originalanbindung `f6f62a5` ist implementiert und unabhängig geprüft: 590 Tests, 4 Skips, 32 Untertests. Endliche ausdrückliche Opt-in-Budgets; standardmäßig keine Zusatzspeicherung. Ausführungsfingerabdruck ist **kein** replay-fähiges C1-Codepaket oder eine Effektqualifikation. Originalquelle, Codeidentität und empirischen Stand getrennt berichten. Echte Aktivierung/Tageszuwachs-/Kapazitätsprüfung bleibt offen.
- Desktop-/Mobilrenderer mit klar synthetischen Daten tatsächlich geprüft: konsistente Richtung, unveränderte Prognosen bei Quote1.12, Daily3 mit0/1/3 Events, neutrale Basketball-/Eishockeykarten, kein Überlauf bis320px und frische Konsole ohne Fehler. Bericht `docs/audits/2026-09-18-product-ui-check.md`. Keine Freigabe der vollständigen Produktionsseite oder Vorhersagequalität daraus ableiten.
- Git-Integration, Hauptcheckout-Prüfung und regulärer Push sind erledigt. VPS-Deployment und neue Linux-/Betriebsabnahme separat; Timer liefern keinen Code aus. Eine neue Produktionsfreigabe nicht allein aus Windows-Tests oder GitHub-Hash ableiten.
- **Fachlich weiterhin offen:** tatsächliche angewendete/empirisch belegte Verletzungs-/Müdigkeitseffekte; Aktivierung des kausalen Fußball-Live-/B1-Anschlusses und neuer versionsgleicher Wirkungs-/Trainingspfad; tatsächliche Tennis-Endzeiten/native Zuordnung; ausreichende unbenutzte echte Testevents. Neue Verteilungsregel braucht eigene Qualifikation. 101 gebundene Tennis-Spiele sind keine200 geeigneten Holdout-Events. Keine bessere Wettqualität behaupten.

Konkrete Wiederaufnahme aus den jeweiligen `.superpowers/sdd/2026-09-18-*/progress.md` und tatsächlichem Git; bereits vollständige Tasks nicht neu implementieren. Fremde/ungetrackte Prüfdateien erhalten. Der neue Fußball-Liveanschluss ist technisch unabhängig geprüft, aber nicht aktiviert; sein Code und Speicherbaustein sind kein fachlicher Effektbeleg.

## Historisches Releasepaket 18.09.2026 — neuerer Stand steht oben

- **Funktionsstand `c44684d` ist lokal auf `main` und auf GitHub-main.** Die folgenden Dokumentationsänderungen gehören zum selben Releasepaket. VPS zuletzt weiterhin `f3c2b60`; ein Push ist kein Deployment. Abschließende Serverbelege werden separat in `output/playwright/context-repair-deployment-20260918.md` festgehalten. Falls diese Datei fehlt, keinen erfolgreichen neuen Release annehmen; Git/Health/Jobstatus frisch lesen.
- Vollständige finale Suite: **10.065 bestanden, 96 Skips, 97 Untertests bestanden**, Exit 0, 1608.90 s. Danach im fast-forwardeten Hauptcheckout nochmals **346 bestanden, 12 Skips**, Exit 0. Alle Funktionsreviews, der Gesamtdiffreview und die QA-Korrektur sind ohne offene Befunde. Quellen-/Testdateien blieben während des finalen Gesamtlaufs eingefroren. Logs: `full-suite-final-20260918-39b5c281.log`, `main-checkout-20260918-031b438d.log` unter `output/playwright/`.
- Fertig: kürzere Consumer-Lesesperren, korrigierter Tennis-Saisonpfad, eng begrenzter historischer Tennis-Replay-Übergang, deduplizierte verlustfreie Fußball-Originalspeicherung. Sieben vorbestehende native QA-Fehler sind durch ehrliche Trennung historischer Prüffälle und aktueller Ausführung korrigiert; keine Pins, Ressourcen- oder Modellregeln gelockert. **Aktuelle native Neuqualifikation bleibt separat offen.**
- Die nach erneuter Freigabe zusätzlich übernommenen acht alten QA-/Recovery-Ziele sind nach vollständiger Linux-Wiederherstellung, geschütztem SSH-Export und kompletter lokaler Archivleseprüfung entfernt. Wiederherstellung: `C:/Projekt/BetBoy/.private-vps-backups/20260918-qa-retirement`, Archiv 1.632.517.697 Bytes; SHA256 `44d6f5202513b96156b4b33e0724561b30186a71da0ce32039d89a549d5b9366`. Manifest SHA256 `a025bce3460cfa83bb8148499d56907b77c1e76c9c32471adb13baeea987bc95`. Rund 2.43 GB dauerhaft frei; zusätzliche Server-Transportkopie ebenfalls entfernt. Runner, Wartungszustand und installierter Updater sind hashgleich; Produktionsdatenbanken und reguläre Backups unangetastet. Alte Drei-Kopien-Bereinigung ebenfalls erledigt, keine Bereinigung erneut starten.
- Frischer Reservecheck nach Bereinigung: 22.581.014.528 Bytes frei, 22.399.551.488 Bytes unveränderte Grundreserve nötig. **Codebereitstellung muss zusätzlich passen**; 181 MB Abstand sind keine garantierte Releasefreigabe. Nur den vorhandenen vertrauenswürdigen Updater verwenden; nicht direkt in Produktion pullen, keine Grenze reduzieren. Acht gelöschte Ziele/Prüfbelege stehen im neuen Retirement-Plan und den SDD-Berichten. Keine weitere Datenkopie ist durch diesen konkreten Acht-Ziele-Schritt freigegeben.
- **Fachlich nicht fertig:** Fußballplan Tasks 2/3 (kausaler Live-/B1-Anschluss und Aktivierung), Spieler-/Ersatz-/Belastungsdaten und Kohorten, echte Tenniszeitdaten, durchgängige Spielinkarnationen bei wiederverwendeten Provider-IDs, weitere Sportarten außer Cricket sowie empirische und Nutzerabnahme. 101 unterschiedliche exakt gebundene Tennis-Spiele sind keine 200 geeigneten unangetasteten Testevents. Keine neue Verletzungs-/Müdigkeitswirkung oder bessere Wettqualität freigegeben. Preise und Geldkonten unverändert.

Details: [Reparaturbericht](docs/audits/2026-09-18-context-repair-release.md). Die erneute allgemeine Design-/Worktree-/Pushfreigabe ist nicht erforderlich; erledigte Tasks nicht wieder beginnen. Timer berechnen, sie deployen keinen Code.

## Historischer Arbeitsstand 18.09.2026, 19:43 CEST

- **Nicht alles abgeschlossen.** Lokal `c44684d`, GitHub-main und VPS zuletzt `f3c2b60`. Sechs lokale Reparaturcommits noch nicht gepusht/deployed. Server um 19:36 CEST: App/Caddy aktiv, interner Healthcheck `ok`; letzter Wettfinderlauf 19:07–19:15 CEST erfolgreich. Kein neuer erfolgreicher Tennis-Gesamtlauf behauptet.
- Software fertig: Consumer-Lesetransaktion verkürzt (`185812e`), WTA/ATP-Quellenpfad repariert (`b342b02`), exakte historische Tennis-Replays erhalten (`0b529cf`), verlustfreie deduplizierte Fußball-Originalspeicherung samt inklusiver Grenze (`49ad632`, `0df6707`). Alle Funktionstasks und ihr Gesamtdiff unabhängig ohne Befund geprüft. Zahlen/Belege im [Reparaturbericht](docs/audits/2026-09-18-context-repair-release.md).
- Sieben Gesamtregressionsfehler waren bereits am exakten vorherigen Stand reproduzierbar: historische native Pins wurden mit inzwischen geänderten QA-Eigentümerdateien vermischt. `c44684d` trennt historische Prüffälle von der echten aktuellen Ausführung. 337 betroffene Tests bestanden, 54 Skips; native Pins, Eigentümer und Grenzen unverändert. **Aktuelle native Neuqualifikation bleibt offen**, kein anderer Name für einen zugelassenen aktuellen Lauf.
- Finaler Gesamttest läuft seit 19:40:14 CEST auf eingefrorenen Quellbytes, ohne `maxfail`: Sitzung `65907`, Log `output/playwright/full-suite-final-20260918-39b5c281.log`, isolierter Testpfad `C:/Projekt/BetBoy/.qa-final-20260918-39b5c281`. Gleichzeitig unabhängiger QA-Review unter `.superpowers/sdd/2026-09-18-native-qa-portability/task-1-review.md`. Noch keinen grünen Gesamtabschluss ableiten; keine Source-Änderung während des Laufs.
- Bereits genehmigter Drei-Kopien-Export und deren Bereinigung sind erledigt, nicht wiederholen. **Zusatzfreigabe durch „alles“ am 18.09., etwa 19:48 CEST:** die acht zuvor genau angefragten QA-/Recovery-Ziele geschützt archivieren, vollständig wiederherstellen/prüfen, lokal sichern und erst dann entfernen. Plan `2026-09-18-approved-qa-retirement.md`; privater lokaler Zielordner bereits angelegt, noch kein Transfer/Löschen. Letzter Reservefehlbetrag 2.239 GB vor Codebereitstellung; die acht Ziele garantieren noch keine ausreichende Reserve. Keine produktive Datenbank, reguläre Sicherung oder weitere Kopie entfernen.
- Nach grünem Gesamtlauf und abgeschlossenem Review: nur eigene Quell-/Test-/Plan-/Handoffdateien committen, unverändertes GitHub-main prüfen, `main` fast-forwarden und regulär pushen. Keine erneute allgemeine Push-/Worktree-/Designfreigabe nötig. Neues Deployment erst bei ausreichender echter Reserve über den installierten vertrauenswürdigen Updater. Timer deployen nicht.
- Fachlich offen: Fußballplan Tasks 2/3 (echter Live-/B1-Anschluss und Aktivierungsprüfung), Spieler-/Ersatz-/Belastungsdaten und Kohorten, tatsächliche Tenniszeitdaten, durchgängige Spielinkarnationen bei wiederverwendeten Provider-IDs, weitere Sportarten außer Cricket und empirische/nutzersichtbare Abnahme. Es gibt 101 verschiedene exakt gebundene Tennis-Ergebnisse, keine 200 geeigneten unbenutzten Testevents. **Keine neue Verletzungs-/Müdigkeitswirkung oder bessere Wettqualität nachgewiesen.**

## Historischer Zwischenstand 18.09.2026, 18:41 CEST

- **Nicht alles erledigt; neue Reparaturen noch nicht deployed.** Produktivstand und GitHub-main weiterhin `f3c2b60`; aktive Reparaturkopie `codex/context-capacity-recovery-20260910` ist weiter. App/Caddy und interner Healthcheck zuletzt 18:28 CEST erfolgreich gelesen. Keine Produktionsänderung durch die folgenden lokalen Tasks.
- `185812e`: tatsächlicher Karten-Leser-Konflikt repariert; unveränderliche Leseabbilder verlassen die SQLite-Transaktion vor CPU-Prüfung. 472 betroffene Tests bestanden/5 Skips; unabhängiger Taskreview ohne Befund. Andere lange Inventurleser bleiben separat offen.
- `b342b02`: WTA/ATP-Saisonquelle auf veröffentlichten HTTPS-Pfad korrigiert, 159 betroffene Tests bestanden/3 Skips. Ein echter isolierter WTA-Aufbau mit vorhandenen öffentlichen Daten funktioniert: 1110 Spielerinnen, Ergebnisstand12.09.2026,7025 bestehende Kalibrierungsbeobachtungen,5.95s. Keine Veröffentlichung, kein Wirkungstest; vier offene openpyxl-Hinweise dokumentiert.
- Wichtiger Nachfolgefehler vor Deployment entdeckt: `tennis/data_loader.py` gehört zur gespeicherten Original-Codeidentität. Alte Originale würden allein wegen der URL-Änderung scheitern. Exakte historische ATP/WTA-Fälle reproduziert; eng begrenzter vollständiger Sechsdatei-Versionsübergang gerade in Implementierung, Plan WTA Task2. Keine alte Prognose umschreiben und keine Hashprüfung pauschal lockern.
- `49ad632` plus `0df6707`: verlustfreie deduplizierte Fußball-Originalspeicherung fertig, inklusive korrigierter exakter4MiB-Grenze. Betroffener Erstlauf356passed/4skip, Fixlauf93passed/4skip; unabhängiges Nachreview SPEC/QUALITY PASS. Synthetischer380-Zeilen-Fall:826589Bytes expandiert,230689Bytes einmaliger Nutzinhalt, unveränderte Folgeberechnung271Bytes. Das ist ein Speicherbaustein, **noch keine Live-Scanneranbindung oder aktivierte Verletzungswirkung**. Fußballplan Task1 abgeschlossen,Tasks2/3 offen.
- Frische Tennis-Ergebnisinventur:995 Originalpublikationen,122 unterschiedliche native Paarungsidentitäten,101 verschiedene exakt outcome-gebundene Spiele(2ATP/99WTA). Keine weiteren abgeschlossenen Fälle aus vorhandenen normalisierten Statusdaten sicher nachbindbar. Fehlende Gewinnerbelege und wiederverwendete Provider-IDs bleiben explizit ungeklärt; kein künstliches Hochzählen wiederholter Originale. Weitere elf Identitäten zuletzt geplant/laufend.
- Die bereits genehmigte Drei-Kopien-Bereinigung und der geschützte Export sind abgeschlossen; nicht wiederholen. Acht **zusätzliche** alte QA-/Recovery-Ziele (2.432.557.056 Bytes) wurden zur geschützten Archivierung/Wiederherstellungsprüfung/Entfernung angefragt, noch keine Antwort. Reserve während laufendem Wettfinder: 22.314.248.192 Bytes nötig, 18.987.212.800 frei, 3.327.035.392 fehlend plus Codebereitstellung. Der zusätzliche Verlust ist read-only geklärt: PID560381 im Wettfinder hält fd3 einer bereits entlinkten temporären Datei, 1.182.539.776 Bytes. Kein neuer dauerhafter Bestand; kein Pfad zum Löschen, keinen Prozess für Speicher beenden. Nach natürlichem Abschluss Reserve erneut prüfen. Acht Ziele noch nicht verarbeitet, keine Schutzgrenze verändert.
- Nächster Softwareabschluss: historische Replay-Kompatibilität fertigstellen/reviewen, einmalige volle aktuelle Suite, Gesamtreview, dann gezielter Commit/Push. Serverrelease erst mit ausreichend echter Reserve und vollständiger Freigabe. Nochmalige ursprüngliche Spezifikations-, Worktree- oder allgemeine Push-Freigabe nicht erforderlich.
- Fachlich weiter offen: Fußball-Live-Original/B1-Anschluss, ursprüngliche Spieler-/Ersatz-/Belastungsdaten und Kohorten, tatsächliche Tenniszeit-/Belastungsdaten, durchgängiger Fixture-Inkarnationsvertrag, weitere Sportarten außer Cricket, eigenständige Effektqualifikation und Nutzerabnahme. Mindestens200 unabhängige unangetastete Testevents in drei Zeitblöcken plus getrenntes Training/Tuning bleiben erforderlich;101 Spiele sind kein Qualitätsnachweis. Keine Gesamtfertigmeldung.

Belege lokal: jeweilige `.superpowers/sdd/2026-09-18-*/`-Ledger, `output/playwright/wta-isolated-build-20260918.md`, `tennis-replay-locator-compatibility-20260918.md`, `tennis-outcome-coverage-inventory-20260918.md`, `release-reserve-inventory-20260918.md`. Alte ungetrackte Ausgaben/QA-Verzeichnisse unverändert erhalten.

## Fortsetzung 18.09.2026, 17:50 CEST – hat Vorrang vor alten Angaben

- Release abgeschlossen: Lokal, GitHub-main und VPS auf `f3c2b6083b8bcf78014a26302beb3afd97b8aaf9` (Funktionsstand `afc8a10`). App/Caddy aktiv, interner und öffentlicher Healthcheck geprüft; sieben reguläre App-Timer plus separater Retention-Timer geplant. Frische VPS-Leseprüfung um 17:44 CEST bestätigt Commit und internen Healthcheck. Alte fehlgeschlagene Dienste nicht zurückgesetzt.
- Die drei ausdrücklich freigegebenen verwaisten Prüfkopien wurden nach vollständiger Archiv-/Wiederherstellungsprüfung entfernt. Geschützte lokale Wiederherstellung: `C:/Projekt/BetBoy/.private-vps-backups/20260918-release-recovery`; Archiv und Manifest geprüft. Nur die zusätzliche Server-Transportkopie wurde anschließend entfernt. Produktionsdatenbanken und reguläre Backups blieben erhalten. Diese Bereinigung nicht wieder beginnen.
- Nach dem Release: 489 neue Belege, davon 151 Tennis-Ergebnisbelege für 101 verschiedene Spiele (2 ATP, 99 WTA); 338 Status-/Belastungsbelege separat. 850 frühere Originalpublikationen gebunden, **nicht** 850 unabhängige Testspiele. Probe bleibt fachlich teilweise vollständig; Bindungsprüfung ohne Fehler, kein kompletter Quellen-/Replay-/Qualitätsnachweis.
- Echter Wettfinderlauf 17:08 bis etwa 17:19 CEST erfolgreich, 81 Modellprognosen, 0 vollständig bestätigte Tipps. Keine neue Verletzungs-/Müdigkeitswirkung freigegeben.
- Konkurrierender Ergebnisschreibversuch scheiterte zuvor an `database is locked`; ruhender Wiederholungsversuch erfolgreich. Ursache im echten Karten-Leser reproduziert: CPU-Prüfung/Projektion hält eine Lesetransaktion. Bootstrap allein zu überspringen behebt es nicht. Reparatur läuft im vorhandenen Worktree; Plan `docs/superpowers/plans/2026-09-18-context-consumer-lock.md`. Weitere Langleser und physische Snapshot-Dauer bleiben separat zu prüfen.
- WTA-Ursache frisch geklärt: alter Downloadpfad 404; Upstream veröffentlicht einen neuen HTTPS-Prefix. Aktueller Payload: 2075 Zeilen bis 12.09., bestehende Inhalts-/Regressionsprüfungen bestanden. Noch kein Codefix/Produktivrefresh aus dieser reinen Quellenprüfung. Plan `docs/superpowers/plans/2026-09-18-wta-source-locator.md`.
- Fußball-Live-Original-/Provenienzanschluss wird konkretisiert; noch keine zusätzliche Wirkung aktiv. Tennis Abstract enthält tatsächliche Dauer für eine Teilmenge, der bestehende Loader verwirft sie. Keine tatsächliche Endzeit daraus ableiten. ATP-Turnierdatum bleibt kein Matchdatum.
- WTA `183854` ist als tatsächliche Provider-ID-Wiederverwendung geklärt: zuerst native Teilnehmer `2731/6769`, später `2731/2441`. Kein bloßer Terminwechsel. Die alte Prediction 1409 und ihre Revision blieben korrekt unverändert/offen; kein falsches Endergebnis zugeordnet. Eine durchgängige neue interne Spiel-Inkarnation für die Ersatzpaarung ist noch zu implementieren (Shadow, Refresh, Originale, Outcome, Settlement gemeinsam), nicht die Identitätsprüfung lockern. Diagnose `output/playwright/wta-183854-identity-20260918.md`.
- Consumer-Lock-Fix `185812e` lokal committed, unabhängig ohne Befund geprüft; 472 betroffene Tests bestanden, 5 bestehende Skips. Noch nicht gepusht/deployed. Gesamte aktuelle Testsammlung: 10062 Tests erfolgreich gesammelt; Sammlung ist kein bestandener Testlauf.
- WTA-Locator-Fix `b342b02` ebenfalls lokal committed und unabhängig ohne Befund geprüft; 159 betroffene Tests bestanden, 3 bestehende Skips. Echte isolierte HTTPS-Probe erfolgreich mit 2075 Zeilen bis 12.09.2026. Noch kein Produktivrefresh/Training und kein Deployment daraus ableiten.
- Der nächste sichere Release benötigt beim frischen Reservecheck rund 2,14 GB mehr freien Platz plus Codebereitstellung. Keine erneute alte Bereinigung oder pauschale Backup-Löschung; weitere alte Prüfkopien werden nur inventarisiert. Live-Kontextdatenbank: 1.939.492.864 Bytes. Neuer Fußball-Originalpfad muss feste Inhaltsblöcke wiederverwenden; vollständige Historienkopien pro Berechnung würden erhebliche vermeidbare Datenmengen erzeugen.
- Acht konkrete weitere Prüf-/Recovery-Bestände (2.432.557.056 Bytes) sind inventarisiert; geschützter Export, vollständige Wiederherstellungsprüfung und anschließende genaue Entfernung wurden angefragt, **noch nicht freigegeben oder ausgeführt**. Details `output/playwright/release-reserve-inventory-20260918.md`. Alte drei Ziele und altes Exportarchiv nicht verwechseln. Selbst nach Freigabe Reserve frisch prüfen, nicht trotz zu wenig Platz deployen.
- Fußball-Originalspeicherung wird als verlustfreier fester Inhaltsblock-Speicher implementiert; Plan `docs/superpowers/plans/2026-09-18-football-live-originals.md`, Task 1 im zugehörigen SDD-Ledger. Live-Scanneranbindung und Budget-/Aktivierungsprüfung folgen separat; noch keine neue Original-Publikation auf dem VPS aktiv.
- Weiter offen: vollständige Konkurrenz-/Tageslaufprüfung, WTA-Identitätsfall, Fußball-Live-Integration und verwendbare Spieler-Kohorten, echte Zeit-/Belastungsdaten, weitere Sportarten außer Cricket, empirische und Nutzerfluss-Abnahme. Basisprognosen bleiben unabhängig vom Preis sichtbar. Keine Gesamtfertigmeldung.

Aktuelle Arbeitsbasis: `output/playwright/context-outcome-release-20260916.md`, `output/playwright/context-lock-rootcause-20260918.md`, `output/playwright/tennis-data-coverage-20260918.md`. Ungetrackte Diagnosen erhalten; verbindliche Restliste unten bleibt offen, soweit hier nicht ausdrücklich als erledigt belegt.

## Historische Übernahme 18.09.2026, 16:00 CEST

- **Nicht alles erledigt.** Funktionscommit `afc8a10` lokal und GitHub-main,
  **VPS weiterhin `9659c49`**. Spätere Dokumentationscommits sind kein Deployment.
- Das Update vom 16.09. wurde unterbrochen; App war gestoppt/deaktiviert.
  Nach Prüfung des unveränderten Git-Arbeitsbaums und vollständigen
  Migrationsmarkers wurde der alte Stand wieder gestartet/aktiviert.
  Beide Healthchecks `ok`, sieben reguläre App-Timer gestartet/aktiviert.
  Tennisfehler nicht zurückgesetzt, kein erfolgreicher Gesamtjob behauptet.
- Erneutes entkoppeltes Update brach vor App-Stopp an der unveränderten
  Kapazitätsprüfung ab: 21.264 GB Reserve nötig, 16.313 GB frei;
  rund **4.61 GiB fehlen**. Drei eigene verwaiste Prüfkopien inventarisiert,
  noch nicht gelöscht; genaue Freigabe angefragt. Keine produktive DB oder
  reguläre Sicherung löschen, keine Schutzgrenze lockern.
- `afc8a10`: Tennis-Ergebnisse auch bei belegten Terminrevisionen; ungültige
  Fußball-Spielerprojektion verwirft nicht mehr andere gültige Spiele im Batch.
  **Frisch 162 Tests bestanden**, Exit 0, 34.88 s, DeprecationWarnings als Fehler.
  Ältere 519/193-Läufe nicht addieren; keine neue Vollsuite behaupten.
- Inventur 18.09., 13:50:35 UTC: 986 Tennis-Originalartefakte, fünf Ergebnisbelege
  für nur ein eindeutiges Spiel. Fußball: 272 Spieler-Einsatzbelege / zehn Spiele;
  4.633 Ergebnisbelege / 235 Spiele. Belegzeilen sind keine unabhängigen Testfälle.

### Nächste konkrete Schritte

1. Reserve sicher herstellen, dann nur den installierten vertrauenswürdigen
   Updater nutzen, keinen produktiven Git-Pull. Funktionsziel `afc8a10`;
   bei weiterem Docs-Commit origin/main-Anforderung des Updaters prüfen.
2. Erst danach echte Tennis-Ergebnisprobe speichern und Original-/Event-/
   Terminbindung nachweisen. Entwurf `output/playwright/capture-context-outcomes-20260916.py`
   ist noch nicht ausführungsbereit: `inventory()` fragt fälschlich
   `context_observations.source_schema` ab; Schema liegt im Inhalts-Payload.
   Vor Ausführung korrigieren. Diese Übernahme schrieb keine Kontextdaten.
   Fußball-Probe muss API-Budget und 24h-Backoff respektieren.
3. Fußball-Live-Lücke schließen: `fixture_market_probabilities()` reicht
   `native_provenance` nicht weiter; Originale haben noch
   `unresolved-receipts-not-in-this-capture`. Replay ist bereits verbunden.
   Dieselbe Live-Berechnung mit echten B1-Belegen zum Stichtag verbinden,
   Referenzraten/Kalibrierung/Originale erhalten; danach kompatibler Snapshot-
   Anschluss. Separat kalibrierte Legacy-Marginalen nicht als kohärentes neues
   Torverteilungsmodell umetikettieren. Teilnahme-/Aufstellungsmischung offen.
4. Tennis-Zeitdaten: ESPN-Proben ohne tatsächliche Matchdauer/Endzeit. ATP-CSV
   enthält 8.980 Dauerwerte in 9.736 Zeilen, aber kein Matchdatum. Turnierbeginn
   oder Zeilenfolge sind kein Ersatz. Einzelne offizielle ATP-Seitenprobe war
   mit dem Browserwerkzeug nicht zugänglich; kein Beleg für fehlende Felder
   oder HTTP 403. Quellen-/Zeitsemantik vor versionierter Erweiterung prüfen.
5. Unverändert mindestens 200 eindeutige unangetastete Testevents in drei
   Zeitblöcken zusätzlich zu Training/Tuning. **Keine freigegebene neue Wirkung
   und keine belegte bessere Wettqualität.** WTA, weitere Sportarten und
   Produktabnahme bleiben offen. Cricket bleibt ausgenommen.

Details: [Übernahmebericht](docs/audits/2026-09-18-kontext-fortsetzung.md).

## Historischer Stand 16.09.2026

Stand: **16.09.2026, 01:10 CEST**. Für die Fortsetzung zuerst dieses Dokument
lesen. Es aktualisiert den Arbeitsstatus, ersetzt aber weder die freigegebene
Spezifikation noch ältere Prüfbelege. Bei späterer Übernahme Git/VPS und letzten
Jobabschluss frisch prüfen; die Zahlen unten sind datierte Beobachtungen.

## Auftrag und feste Regeln

- An der App und ihrer fachlichen Qualität weiterarbeiten; die abgeschlossene
  Speicherbereinigung nicht wieder zum Hauptprojekt machen.
- Fußball und Tennis zuerst, danach Basketball, Eishockey und E-Sport.
  **Cricket bleibt ausdrücklich ausgenommen.**
- Verletzungen, Besetzung und Belastung sollen die Modellrechnung nachweisbar
  beeinflussen. Fehlende Daten sind nicht null; keine erfundenen Abschläge.
- Quoten verändern weder Prognose noch Modellreihenfolge und blenden keine
  berechenbare Prognose aus. Keine pauschalen Wettartenverbote; Preis separat.
- Keine gegensätzlichen Haupttipps für dasselbe Spiel. Kurze, belegte Begründung
  sichtbar statt interner Prüfbegriffe; keine erfundenen Vorteile.
- Spezifikation, Umsetzung und isolierter Worktree sind bereits freigegeben.
  Keine erneute Design-/Namens-/Arbeitskopie-Freigabeschleife. Geprüfte Änderungen
  wie beauftragt committen, pushen und kontrolliert deployen.
- Kein Echtgeld automatisch setzen, keine Kontohistorie ändern, keine neue
  kostenpflichtige Quelle ohne gesonderte Zustimmung.

## Erledigt / nicht erneut beginnen

- [x] Speicher-/Backupbereinigung und zugehörige Wartung: Funktionsstand `5069e75`.
  Keine Produktionsdatenbank und kein echtes Backup für weitere Reserve löschen.
- [x] Tennis-Live-Originale an Fallaufbau, Training, Evaluation, Transportprüfung
  und Live-Effektauswahl angebunden: `9d271c1` und `9659c49`.
  Typ: `tennis-live-winner-status-load-antisymmetric-v1`.
- [x] Dieser App-Code committed, auf GitHub-main gepusht und explizit deployed.
  Geprüfter App-Commit: `9659c49b2738d6a4c7b0fcc7442a9e8ecef3b665`.
- [x] Softwareprüfung: 545 Tests im breiteren Zwischenstand; nach zwei letzten
  Korrekturen 144 betroffene Tests unter Windows und dieselben 144 unter Linux,
  jeweils mit DeprecationWarnings als Fehler. **Keine finale Vollsuite behaupten.**
- [x] Nur die eigene temporäre Tennis-QA-Kopie und Transportarchive entfernt;
  Code/Testquellen sind über Git wiederherstellbar. Ältere QA-Bestände erhalten.

## Tatsächlicher Betrieb – nicht mit Modellqualität verwechseln

- VPS-Commit um 01:09 CEST erneut `9659c49…`, App und Caddy aktiv.
  Interner/öffentlicher Healthcheck und acht geplante Timer nach dem Release
  geprüft. Timer berechnen und warten, **sie pullen/deployen keinen Code**.
- Tennis 16.09., 00:35:59–00:50:22 CEST: Gesamtjob **Exit 1 / failed**.
  WTA-Refresh `HTTPError`, letzter Ergebnisstand 26.07.; ATP `retained_fresh`,
  Datenstand 14.09. Die Touren bleiben getrennt.
- Spielscan 850 Sekunden, also diesmal unter 900 Sekunden: 73 gefundene
  noch nicht gestartete Einzelspiele, 40 vorbereitete Abschlussfälle,
  26.283 gespeicherte Spielbeobachtungen, 23 neue Predictions.
  Ein WTA-Event `183854` blieb mit `FixtureIdentityConflict` teilweise offen.
  Kein `reset-failed` und kein weiterer manueller Lauf zur Verschleierung.
- Kontextspeicher nach dem Lauf: **450 Tennis-Originalartefakte, 0 native
  Tennis-Endergebnisbelege**. Artefakte sind nicht gleich unabhängige Testspiele.
  Die separat abgerechneten 39 ESPN-Finals im bisherigen Shadow-Store beweisen
  keine Ergebnisanbindung des neuen Kontexttrainings.
- Peak des Tennisdienstes 2,7 GB RAM; CPU-Zeit 13 min 51,6 s. Kein allgemeiner
  Performance-Erfolg aus einem Lauf knapp unter dem Zeitlimit ableiten.
- Wettfinder 00:07–00:17: 59 Modellprognosen, Gesamtstatus `degraded` wegen
  Cricket. Fußball erfolgreich, Tennis-Refresh ohne operativen Fehler in diesem
  Wettfinderlauf. Cricket bleibt unverändert; kein Alle-Sportarten-Erfolg.

## Offene To-dos – in dieser Reihenfolge

- [ ] **P0 – echte Tennis-Ergebnisbelege nutzbar machen.** Zuerst nachvollziehen,
  warum trotz gespeicherter Originale und Shadow-Finals null passende
  `match_outcome`-Belege vorliegen. Der Erfassungscode existiert bereits; nicht
  blind neu bauen. Nachweisen, dass genau passende, normal beendete native
  Spiele mit tatsächlich vor Spielbeginn gespeicherten Originalen verbunden
  werden. Keine nachträglichen Originale, keine erfundenen Zuordnungen und
  keine Retirement-/Walkover-Labels als normale Siegergebnisse.
- [ ] **P0 – WTA-Datenabruf reparieren.** HTTP-/Inhaltsfehler reproduzieren,
  gültige aktuelle Quelldaten beziehen und Tour-Frische beweisen. ATP darf
  unabhängig weiterlaufen; alten WTA-Stand nicht als frisch ausgeben.
- [ ] **P0 – Spielzuordnung WTA `183854` klären.** Native Revisionen/Teilnehmer
  gegen das unveränderliche Original vergleichen. Nur belegte Korrekturpfade
  zulassen; keine Historie überschreiben und Identitätsprüfung nicht abschalten.
  Danach echten Gesamtjob mit klar ausgewiesenem Ergebnis prüfen.
- [ ] **P1 – Laufzeitreserve belegen.** Die 850/900 Sekunden sind zu knapp.
  Teure Abschluss-/Historienabschnitte messen und gezielt verbessern, ohne
  Datenbelege wegzulassen. Parallelität mit Wettfinder auf SQLite-Locks/OOM
  prüfen; keine bloße Zeitlimit-Erhöhung als Reparatur verkaufen.
- [ ] **P1 – Fußball-Verletzungswirkung fertigstellen.** Vorhandene Erfassung
  für Spieler, Minuten, Rolle, Ersatz, Rotation und Erholung auf echte nutzbare
  Kohorten prüfen; Wirkung auf Tor-/Stärkeverteilung schätzen und alle betroffenen
  Märkte konsistent neu ableiten. Ausfallliste allein ist keine Modellwirkung.
- [ ] **P1 – Tennisbelastung vervollständigen.** Sätze, tatsächliche Dauer und
  Endzeit, Erholung sowie belegte Ausfälle und Umgebungsdaten anbinden, soweit
  die Quelle sie tatsächlich liefert. Der aktuelle ESPN-Kontext belegt keine
  echten Matchminuten/Endzeiten. Beobachtete Erholungs-Untergrenzen nicht als
  gemessene Fünfsatz-Müdigkeit ausgeben. Native historische Namens-/ID-Zuordnung
  bleibt ungeklärt; der neue Live-Pfad ersetzt diesen Nachweis nicht.
- [ ] **P1 – empirische Wirkung nachweisen und erst dann aktivieren.** ATP/WTA
  und Modellfamilien getrennt; mindestens 200 eindeutige Testevents in drei
  Zeitblöcken, unverändert vereinbarte Brier-/HAC-/BH-, Verteilungs- und
  Kalibrierungsprüfungen. Kleine synthetische Tests oder hohe Trefferquoten
  reichen nicht. Bis zum Nachweis bleibt die Basisprognose unverändert.
- [ ] **P1 – Auswahlqualität im echten Nutzerfluss abnehmen.** Wettfinder,
  RisikoBet und Daily3 auf aktualisierte Modelle, Marktvielfalt, keine
  widersprüchlichen Hauptkarten sowie kurze sachliche Pro-/Contra-Begründung
  prüfen. Fehlende/kleine Quoten dürfen den Modellpool nicht verändern.
  Keine Mindestzahl an Tipps erzwingen und keine Profitabilität behaupten.
- [ ] **P2 – Basketball/Eishockey/E-Sport vervollständigen.** Vorhandene Adapter
  und die früheren Teilreviews zuerst inventarisieren; fehlende Aufstellungs-,
  Spieler-/Torhüter-, Belastungs- und Kaderbelege gezielt schließen. Implementierte
  Hüllen nicht als empirisch aktive Sportmodelle abhaken. Cricket nicht anfassen.
- [ ] **P2 – abschließende Regression/Produktabnahme.** Historische Native-/QA-
  Pins und offene Teilplanbefunde gegen den heutigen Code prüfen; keine Pins
  pauschal umschreiben. Für jedes Teilrelease getrennt Software, verwendbare
  Daten, empirischen Status, tatsächliche Aktivierung und Browser/VPS belegen.

Daily3 ist technisch live; Name **„3 a day keeps the job away“**, höchstens
CHF 50 eigenes Geld pro Tag, Gewinne können weiterverwendet werden,
kein Nachschuss über dieses Tagesbudget hinaus.
Die Qualität/Verfügbarkeit der Auswahlen bleibt Teil der offenen Abnahme. Keine
Gewinngarantie oder Behauptung täglich sicherer CHF 150.

## Einstieg für den nächsten Account

1. Git-Root `C:/Projekt/BetBoy/betboy-app`; aktiver Arbeitsstand in
   `.worktrees/context-capacity-recovery-20260910`, Branch
   `codex/context-capacity-recovery-20260910`. Main enthält denselben App-Code.
   Dokumentationsfolgecommits sind kein neuer produktiver Funktionsstand.
2. [Übergabe](PC_WECHSEL_UEBERGABE.md), [freigegebene Spezifikation](docs/superpowers/specs/2026-09-07-kontextmodell-design.md),
   [20-Aufgaben-Plan](docs/superpowers/plans/2026-09-07-kontextmodell-umsetzung.md),
   [Tennis-Vertrag](docs/audits/2026-09-15-tennis-live-training.md) und
   [Datenpfad](docs/audits/2026-09-15-kontext-datenpfad.md) lesen.
3. Konkrete Startdateien: `context_models/tennis_training.py`,
   `tennis/live_context.py`, `context_models/tennis_live.py`,
   `scripts/tennis_daily.py`, `scripts/run_daily_pipeline.py` und zugehörige Tests.
4. Ausführlicher lokaler Abschlussbeleg:
   `output/playwright/tennis-live-training-release-20260916.md` im Worktree.
   Bewusst ungetrackt; die entscheidenden Zahlen stehen deshalb auch hier.
5. Nur VPS `betboy-vps` schreibt/schedult produktiv; App `/opt/betboy/app`.
   Deployment ausschließlich über den vorhandenen vertrauenswürdigen Updater,
   nicht durch direkten produktiven Git-Pull. Bei einem späteren Deployment
   auch `activating`-Worker beachten, nicht nur `is-active`.
6. Vorhandene ungetrackte Audits, `.playwright-cli/`, `output/playwright/` und
   `qa19-*` erhalten. Kein `git add .`, Reset/Clean oder pauschales Löschen.
   Python lokal: `C:/Projekt/BetBoy/betboy-app/.venv/Scripts/python.exe`.
   Tests isoliert, kein pytest in die produktive VPS-venv installieren.

**Nächster konkreter Arbeitsschritt:** read-only den fehlenden Tennis-
Endergebnisübergang vom bestehenden Quellenempfang zum Kontextspeicher
reproduzieren; danach gezielter Regressionstest und kleinster belegter Fix.
