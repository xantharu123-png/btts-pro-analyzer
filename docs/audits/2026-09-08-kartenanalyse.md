# Verständliche Wettfinder-Karten – Release-Nachweis

Stand: 8. September 2026, 19:14 Uhr Zürich. Quellcode, lokale Darstellung, reguläres VPS-Deployment und die echte Produktionskarte nach dem planmäßigen Datenlauf sind getrennt nachgewiesen.

## Auftrag und Abgrenzung

Der Nutzer beanstandete die Porto–Manchester-City-Karte: „H2H geprüft, kein belastbares Veto · Ausfälle Liste geprüft …“ erklärt die Auswahl nicht. Die freigegebene Änderung ersetzt diese öffentliche Checkliste durch eine unmittelbar sichtbare Kurzbegründung aus gespeicherten Modellfakten plus Gegenrisiko, auf Haupt- und Zusatzkarten. Das bisherige Aufklappen einer bloßen Checkliste entfällt.

Keine Änderung an Wahrscheinlichkeiten, Abschlägen, Reihenfolge, Wettarten, Preisen, Freigaben, Cricket, Konten, Einsätzen, Tickets oder Abrechnungen. Kein neuer Scan oder Anbieterabruf beim Seitenbesuch. Die weiterhin offene numerische Verletzungs-/Belastungsmodellierung ist ein eigener Auftrag und wird hier nicht als erledigt bezeichnet.

Arbeitskopie: `.worktrees/erklaerbare-karten-20260908`, Branch `codex/erklaerbare-karten-20260908`, Basis `8c3df7978bf074cfe6ce3d9a794f6f60139327ea`. Der erste Implementierungscommit ist `e8e057fcef2ad6be860d2bbe7cf4b0808f78b4f5`; dessen P2-Zeitbefund wurde in `f82d7aeea2e42d81affa2c4389cb377f2293af5c` korrigiert und unabhängig nachgeprüft. Die unfertige Tennis-/Kontext-Arbeitskopie wird nicht mit diesem UI-Release ausgerollt.

## Nachgewiesene Darstellung

- Tatsächlich gespeicherte Porto-Zahlen aus dem nur lesend geprüften VPS-Artefakt vom 8. September 15:37:17 UTC: Torerwartungen 1,527 / 1,133; Heimsieg 0,46361; ursprünglicher Modell-/Inputzeitpunkt 7. September 22:11:47 UTC. Das ist ein Nachweis des App-Datenstands, keine unabhängige Bestätigung des Spielplans oder der Modellgüte.
- Die Erklärung nennt die höhere Torprognose für Porto (gerundet 1,53 zu 1,13), aber ebenso 53,6 % für Remis oder Auswärtssieg zusammen. Sie behauptet weder eine Mehrheit für Heimsieg noch empirisch belegte Stärkeübertragung zwischen Ligen.
- Ausfälle werden nur als zeitlich belegte Meldungen beschrieben. Ihre noch nicht eingerechnete Wirkung wird nicht als Vorteil verkauft. Fehlende oder veraltete Angaben sind nicht gleichbedeutend mit einem gesunden Kader.
- Torerwartungen begründen keine Ecken-/Kartenmärkte; diese verwenden ausschließlich ihre separat gespeicherten Modellraten und Einheiten.
- Alte Datensätze ohne exakt zugeordnete Erklärungsdaten zeigen einen ehrlichen Kurztext. Der vorhandene Kontext-Refresh ergänzt die Fakten bei erfolgreicher, regulär fälliger Aktualisierung, unter Erhalt des ursprünglichen Modellzeitpunkts. Kein spekulativer Join und kein Zusatzabruf.

## Softwareprüfung

Erster stabiler Volltest: 1.787 bestanden, 11 übersprungen, 97 Untertests; fokussiert 305 bestanden und 26 Untertests. Ein unabhängiges Review bestätigte den Fokuslauf, fand aber einen P2: zukünftige Modell-/Inputzeitpunkte wurden noch als konkrete Erklärungsgrundlage akzeptiert. Dieser erste Stand wurde nicht veröffentlicht.

Der Fix `f82d7aeea2e42d81affa2c4389cb377f2293af5c` verwendet in beiden echten Lesern und beim Kartenrendern die bereits vorhandene gemeinsame Auswertungsuhr. Vier neue RED-Fälle belegten den Fehler. Danach: fokussiert 313 bestanden und 26 Untertests; vollständige frische Suite 1.795 bestanden, 11 übersprungen, 97 Untertests in 83,92 Sekunden. Gleichheit mit dem Auswertungszeitpunkt bleibt zulässig; bei Zukunftszeitpunkten fällt nur die optionale Erklärung zurück. Code- und Diffprüfung grün.

Das unabhängige Re-Review hat `f82d7aeea2e42d81affa2c4389cb377f2293af5c` ohne verbleibenden Befund im vereinbarten Umfang freigegeben. Sieben eigene Zeitfälle durch beide echten Leser und direktes Kartenrendern bestanden; ein separater Fokuslauf bestätigte 313 Tests und 26 Untertests. Wahrscheinlichkeiten, Abschläge, Preis- und Freigabefelder sowie ursprüngliche Daten blieben unverändert. Vollständiger Bericht: `.superpowers/sdd/2026-09-08-kartenanalyse/independent-review.md`.

## Gerenderte lokale Prüfung

Mit dem Playwright-Skill wurden echte Streamlit-Renderer und Produktions-CSS in einer isolierten, ausdrücklich als Test bezeichneten Vorschau geprüft. Der Controller hat die Screenshots selbst angesehen. Keine Produktionsdatenbank, kein Anbieterabruf, keine gespeicherte Wette.

- Breiten 1440, 761, 390 und 320 Pixel: kein horizontaler Seiten- oder Kartenüberlauf.
- Fünf Karten, fünf unmittelbar sichtbare Analysen, kein „Analyse anzeigen“ und keine alte Veto-Checkliste.
- Hauptkarte, Zusatzkarte, ausgewählte Heim-/Auswärtsseite, Tor- und Eckeneinheiten sowie Altbestand ohne Fakten wurden gerendert geprüft.
- Die optionale eigene Quotenprüfung lässt sich weiterhin öffnen; kein Ticket oder Einsatz wurde gespeichert.
- Lokaler Browser: keine Console-Fehler oder -Warnungen. Die vor dem Release geladene Produktionsseite hatte keine Fehler, aber neun bestehende Browser-/Iframe-Warnungen; diese sind nicht als durch die Kartenänderung behoben zu werten.
- Artefakte liegen uncommitted unter `output/playwright/card-analysis/` der Arbeitskopie. Der lokale Harness ist kein Produktivcode.
- Frischer Reload nach dem Fix-Commit `f82d7ae`: bei 1440 Pixeln erneut fünf Karten und fünf sichtbare Analysen ohne alte Aufklapp-Checkliste oder horizontalen Überlauf. Die beiden geänderten Quelldateien sind zeitliche Evidenzprüfungen, kein erneuter Layoutumbau.

## Betrieb vor dem Release

VPS am 8. September 16:18 UTC sauber auf `b3afc478a07fa0d67509e2bef0a9c05766bdb077`; App/Caddy aktiv, interner Healthcheck `ok`, sieben Timer geplant. Die Timer rechnen Daten und führen keinen Pull/Deploy aus.

Zwei Worker meldeten unabhängig vom UI-Auftrag Fehler: gemeinsamer Tennis-Rebuild nach ATP-Verarbeitung mit HTTPError; Wettfinder wegen mehrdeutiger RisikoBet-Ergebnisrevisionen. Die Fußballanalyse war abgeschlossen. Bestehende Cricket-Teildaten bleiben unverändert. Diese Befunde dürfen nicht durch einen grünen Seiten-Healthcheck oder einen bloßen Neustart als gelöst gelten.

## Ausgeführtes Deployment und echter Datenlauf

- `ce7b98ccf365a5db4303ed04291058acdbe6067b` wurde auf `main` und den UI-Branch gepusht und durch den regulären root-eigenen `/usr/local/sbin/betboy-update` erfolgreich ausgerollt. Main, GitHub und VPS waren anschließend exakt identisch; der Produktionscheckout war sauber. Der fachliche Karten-Quellstand ist weiterhin das unabhängig geprüfte `f82d7ae`.
- Pre-Update-Backup `/var/backups/betboy-update/betboy-preupdate-20260908T163523Z-b3afc478a07f.zip` und reguläres Backup `/var/backups/betboy/betboy-sqlite-20260908T163605Z.zip`: jeweils **87 Datenbanken verifiziert**. Keine Schlüssel oder Ledgerdaten wurden in lokale QA kopiert.
- Der normale Lauf um 18:37 Uhr ergänzte 17 Fußball-Erklärungen. Porto war zu diesem Zeitpunkt nach der unveränderten Frischeregel noch nicht fällig. Erst der normale Lauf um **19:07 Uhr** ergänzte Porto erfolgreich; es wurde kein Zusatzscan gestartet.
- Veröffentlichtes Artefakt: `generated_at=2026-09-08T17:07:12.004286+00:00`; Porto-Kontext `2026-09-08T17:07:04.340066+00:00`. 27 gespeicherte Modellkandidaten, davon 25 mit exakt gebundener numerischer Analyse. Bereits gestartete Spiele werden wie bisher nicht mehr als kommende Auswahlen geführt.
- Porto behielt `probability=0.46361`, Torerwartungen `1.527/1.133` und beide ursprünglichen Modell-/Inputzeiten `2026-09-07T22:11:47.515195+00:00`. Es wurde kein neues Modell simuliert und keine Wahrscheinlichkeit durch Quote oder Kontextbericht geändert.
- Nach einem frischen öffentlichen Reload standen auf Seite 1 **23 gerenderte Karten und 23 direkt sichtbare Analysen**; der gesamte Katalog ist paginiert. Die echte Porto-Hauptkarte zeigt die Torprognose, 46,4 % Heimsieg, 53,6 % Gegenrisiko, den unvalidierten Vergleich verschiedener Ligen und den zeitlich bezeichneten Kaderstand, dessen Wirkung noch nicht eingerechnet ist. Kein „Analyse anzeigen“ und keine alte H2H-/Veto-Checkliste.
- Produktion bei 1440, 390 und 320 Pixeln ohne horizontalen Seiten-/Kartenüberlauf. Der Controller hat die tatsächlichen Desktop- und Mobile-Screenshots selbst angesehen. Belege: `production-porto-1440.png` und `production-porto-390.png` im uncommitteten `output/playwright/card-analysis/` der UI-Arbeitskopie. Die Mobile-Aufnahme enthält die vorhandene feste Navigation; das ist kein versteckter Analyse-Expander.
- Frischer Produktionsbrowser: **0 Console-Fehler, 9 bestehende Feature-Policy-/Iframe-Warnungen**. `betboy-app.service` und Caddy aktiv; interner und öffentlicher Healthcheck `ok`; alle sieben Timer geplant. Die Timer rechnen weiterhin nur Daten und deployen keinen Code.

Der Wettfinder-Worker endete um 19:11:34 trotz erfolgreicher Fußball-Veröffentlichung weiterhin mit Status 1 wegen der bereits bekannten mehrdeutigen Ergebnisrevisionen. Auch der separate gemeinsame Tennis-Rebuild war fehlgeschlagen. Diese Fehler sind **nicht** durch den Karten-Release behoben; keine alten Ergebnisse wurden geraten, überschrieben oder als abgeschlossen umetikettiert. Verletzungs-/Müdigkeitseffekte, empirische Modellgüte und die übrigen Kontextplan-Aufgaben bleiben offen. Ein nachfolgender reiner Dokumentationscommit ändert den hier geprüften fachlichen Quellstand nicht.
