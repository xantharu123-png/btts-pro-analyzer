# Wettfinder: Was traf am 19. November – und was ist nicht belegt?

**12 Treffer und 6 Niederlagen bei 18 entschiedenen Märkten; eine weitere Auswahl war offen.**
Diese 19 unterschiedlichen Auswahlen gehörten zu 13 Spielen. Es sind weder
19 unabhängige Begegnungen noch Kundenwetten. Ein Gewinnbetrag ist daraus nicht ableitbar.

## Welche Tipps wurden gezählt?

- Zürcher Spieltag 19.11.2026, Katalog `wettfinder_default_inventory`,
  Produktion `87f2434`. Nur vor dem für das Spiel belegten Beginn vorhandene
  Veröffentlichungen, kein nachträglich ausgesuchter besserer Preis. Das
  Standardinventar ist **nicht** identisch mit dem sichtbaren 70-%-Filter oder
  einer tatsächlich geöffneten Ansicht.
- Nimmt man aus der ersten Veröffentlichung je Spiel die höchste verfügbare
  Chance, stehen **6 Treffer, 6 Niederlagen, 1 offen** zu Buche; 50,0 % der
  entschiedenen Auswahlen bei durchschnittlich **58,9 %** angekündigter Chance.
  Das nachträgliche Maximum aus dem Tageskatalog lieferte hier dieselben Zählwerte;
  das sind unterschiedliche Fragestellungen. Der komplette Katalog traf 12/18
  (66,7 %), darunter sieben von acht Fussballmärkten. Die Märkte eines Spiels hängen
  zusammen. Aus zwölf entschiedenen Einzelspielen folgt keine belastbare Fehlkalibrierung.
- **Welche Karte stand wirklich oben?** Der Erzeuger bestimmt die führende
  Modellrevision *vor* dem Preisfilter. Das bisherige Archiv speichert den
  verfügbaren Bestand *danach* und die globale Hervorhebung, nicht den
  Ereignis-Hauptrollenbeleg. Eine in diesem Bestand rekonstruierte höchste
  Chance ist deshalb keine exakt nachgewiesene damalige Hauptkarte. Alte
  Belege bleiben unverändert. Die exakte Erstkartenbilanz darf hier keine
  stellvertretenden Treffer zählen.
- Nachprüfbar mit dem neuen internen Bericht (lokal im geprüften Branch):
  `python -B scripts/selection_performance_report.py --db PFAD_FORECAST_DB --history-db PFAD_TIPPARCHIV --matchday 2026-11-19 --as-of 2026-11-20T12:00:00Z`.
  Fehlende Rollen, fehlende Zuordnung, Annullierung und offene Spiele trennen.
  Ein Risikoszenario oder die Einzelwette eines Kombischeins ist kein abgerechnetes Ticket.

**Abnahme am echten Archiv mit dem neuen Reader:** Stand 20.11. 12:00 UTC,
zwei Inventarbelege, null fehlerhafte Ergebnisbindungen. Bei allen 13 Spielen
fehlte die explizite Hauptrolle; `first_main_card` hat deshalb keinen Nenner
und **keine** Trefferquote. Erste Inventar-Rekonstruktion: Fussball 1/2,
Hockey 2/3, Basketball 1/4, E-Sport 2/3 entschieden plus 1 offen.
Auswertung im Arbeitsspeicher mit dem App-Dienstkonto, ohne Änderung der VPS-App.

**Weitere Produkte, separat geprüft, gleicher Stichtag:** Doublebet hatte drei
vollständige leere Inventarbelege (unterschiedliche Flächen), keine datierten
Auswahlen und keine erfasste Platzierung. Bei 15K keine Ticketzeile in den
für den Tag relevanten geprüften App-Ledgern. RisikoBet hatte keinen öffentlichen
Katalogbeleg für diesen Spieltag. Die 43 internen Kandidatenrevisionen sind
keine veröffentlichten Tipps oder Tickets. Keine Nutzer- oder Kontodaten ausgewiesen,
keine Aussage über Wetten beim Buchmacher ausserhalb der App.

## Warum nur drei frische Preise?

| Status bei der ersten Veröffentlichung | Beleg |
|---|---|
| 3 frisch | Zwei Fussballmärkte, ein NHL-Siegermarkt. |
| 5 veraltet | Alle fünf vom selben Fussballspiel (1492458). Letzter Abruf erst 2 min 41 s alt, Anbieterstand aber bereits 10 h 26 min alt. Die Abrufuhr darf die Anbieteruhr nicht ersetzen. |
| 1 fehlend, Fussball | Für Heimteam 2–4 Tore wurde das richtige Spiel abgefragt; aus den erhaltenen Belegen ist nicht zu unterscheiden, ob die Linie fehlte oder nicht zugeordnet werden konnte. |
| 4 fehlend, Basketball | Vor der Veröffentlichung Spielplanabrufe, aber zwischen dem 16.11. und dem Erstbeleg keine protokollierten Quotenabrufe für Basketball. Grund pro Partie unbekannt. |
| 4 fehlend, E-Sport | Letzter Preis-Batch ohne verwertbares Ereignis, zwei Aufschübe aus Kontingentgründen. Kein Nachweis für einen bestimmten Matchpreis. |
| 2 fehlend, NHL | Generische Quotenabrufe dokumentiert, keine erhaltenen Versuchsstempel für diese beiden exakten Spiele. Grund offen. |

Kein nachgewiesener Zuordnungsfehler in diesen 16 Fällen; kein zusätzlicher Anbieter,
keine Wiederholungsabfragen, keine Preis- oder Auswahlregel geändert.

## Was die vier Hockey-Fehler tatsächlich betrafen

Nicht der Spielplan, sondern die **Saisonhistorie 2026**: Schweizer National League (51),
finnische Liiga (16), SHL (47) und DEL (19). Die ersten drei Fehler sind dem
Folgetagslauf um 02:45 UTC zugeordnet, der vierte dem RisikoBet-Modellpfad um 02:47.
HTTP 200 mit anschliessendem `ValueError` in der gemeinsamen Antwortprüfung.
Die ursprünglichen Antwortkörper fehlen; ein Tarifproblem oder eine kaputte
Anbieterlinie lässt sich rückwirkend nicht beweisen.

Die Änderung meldet den konkreten Grund aus der **nächsten normalen** Antwort,
z. B. Anbieter meldet Tarifbeschränkung, ungültiges JSON, falsche Listenstruktur
oder unvollständige Seite. Nur feste Bezeichner, kein Antworttext, kein Schlüssel.
Beobachtung in Verbrauchsprotokoll und Historienabdeckung; Fehler bleiben Fehler.
Die Warteliste ist ein anderes Thema: Modellspiele behalten Vorrang vor reinen
Preiszeilen. Für Malmö–Rögle, Krefeld–Straubing und Lausanne–Zürich gab es
am 19.11. um 09:15 und 12:15 keinen Versuchsstempel. Kein Beleg, dass die
Heimligen dadurch bessere oder schlechtere Prognosen liefern.

## Was als Nächstes entscheidbar ist

- **21./22.11.** Reguläre Wochenendläufe: vollständige Suche für morgen (66 Ligen),
  Zeit bis zum 60-Minuten-Limit, Teilausfälle, konkrete Hockey-Gründe nach Release,
  echte Versuchsstempel, maximal neun Abrufe pro Sport in 60 Sekunden, Hockey 100/Tag.
  Kein eigens gestarteter Scan.
- **Nach 22.11.** Fallenfilter nur zählen. **30.11.** erst ab 150 abgerechneten Fällen
  öffnen, sonst gemäss bestehendem Plan verlängern. Die getrennten Prüfungen für
  Formstärke/Hybrid sowie die 70-%-Liste nicht vermischen.
- **Mitte Dezember:** gegnerbereinigte Nationalteamstärke, zuerst vorhandene Quellen;
  13 etwaige zusätzliche Abrufe brauchen ein separates OK. **Ende Dezember:**
  vorregistrierter Doublebet-Vergleich; keine Übertragung auf 15K.
- **Club-Heimvorteil:** [eigener Prüfvertrag](2026-11-20-club-heimvorteil-pruefvertrag.md).
  Ein fester Rechenkandidat, keine Aktivierung. Aus dem historischen Pilot ist nur
  die Fallzahlplanung verwendbar. Kein neuer Verletzungs-, Wetter- oder Müdigkeitsbonus.

## Technische Abnahme (Arbeitsbranch, keine Freigabe)

- Kombinierter Lauf: 659 bestanden in 18 Dateien (Standard-Testvertrag). Enthält
  die zehn schnellen CI-Dateien, beide Reportreader, Inventar und Publikation,
  Hockey-Scanner und Ratenlimit sowie Offline-Heimvorteil und gemeinsame Torverteilung.
  Separater vollständiger Ruff-Lauf grün. Keine Vollsuite.
- Zusätzliche Preis-Regressionen sind **nicht** durchgehend grün: unter `gate`
  183 bestanden, zwei bekannte Fehler in Team-/Hockey-Preistests; unter `floor`
  143 bestanden, sechs bekannte Fehler in den Team-Preistests (abweichender Dateiumfang).
  Fehlernamen und Preisverträge decken sich mit der Basis, siehe
  [Übergabe §6](../handoffs/2026-11-19-claude-uebergabe-codex.md).
  Kein fachfremdes Ändern der Preisregel oder Entfernen der Tests.
- Gegenprobe: ein nach Preisfilter verbliebener alter Markt belegt nicht automatisch
  die Hauptrolle; ein vom Geschwistermarkt belegter Anpfiff jenseits von Mitternacht
  muss vor Tages- und Kausalitätsprüfung gelten. Beides ist regressionsgetestet.
