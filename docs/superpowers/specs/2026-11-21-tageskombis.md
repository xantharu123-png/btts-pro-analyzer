# Tageskombis in „Deine Wetten“

**Korrektur des Owners, 23.11.2026:** Eine Partie wird nicht für mehrere öffentliche
Tageskombis verwendet, auch nicht mit anderer Auswahl oder anderer Anbieterkennung
für dasselbe Spiel. Gespeicherte Scheine bleiben unverändert und belegen ihre Spiele
für spätere Veröffentlichungen desselben Tages. Je Marktgruppe sind höchstens
2 Positionen im 3er, 4er und 5er und höchstens 3 im 6er zulässig. Torlinien,
Torbereiche und „Beide treffen“ zählen zusammen; Sieger und Doppelte Chance zählen
zusammen. Ecken, Karten und kombinierte Ergebnis-/Tormärkte sind getrennte Gruppen.
Wenn kein vollständiger Schein passt, bleibt diese Größe frei. Für die öffentlichen
Scheine ersetzt dies die ursprüngliche Überlappungsregel unten. Preisgrenze,
Modellwerte, Auswahl nach Chancenprodukt und die historischen internen Vergleichsarme
bleiben unverändert. Es gibt keinen rückwirkenden Austausch und keinen Zusatzscan.

**Korrektur des Owners, 21.11.2026:** Gefordert sind sichtbare Modellscheine, keine Beobachtungsphase.
Je Tag und Größe höchstens ein unveränderlicher Schein mit sportlich passenden, verschiedenen Spielen.
Ein fehlender gemeinsamer Buchmacherpreis ist kein Anzeigeverbot.
Die öffentliche Preis-Untergrenze bleibt bestehen. Der gemeinsame Preisbeleg und die Prüfung an späteren
Ergebnissen sind davon getrennt. Begonnene Scheine bleiben als solche erkennbar, nicht als neue Empfehlung.
Die gegenteiligen Bedingungen für die Kundenansicht im ursprünglichen Entwurf unten sind aufgehoben.

**Anzeigeentscheidung des Owners, 22.11.2026:** Der einzige öffentliche Balken heißt
„Ø Modellchance je Einzeltipp“. Er zeigt für 3er bis 6er den ungewichteten Durchschnitt
der vor Spielbeginn gespeicherten Einzelchancen, gerundet auf ganze Prozent. Die zuvor
gezeigte Schätzung „alle richtig“ entfällt. Weder die Scheinauswahl noch der intern
gespeicherte Produktwert oder die spätere Ergebnisprüfung ändern sich dadurch.

**Produktauftrag, 21.11.2026:** Rechts im automatischen Wettfinder bleiben Doublebet und die Tennisbox stehen. Dazu kommen höchstens ein 3er, ein 4er, ein 5er und der „Jackpot 6er“ pro Zürcher Spieltag. Kein Einsatz, keine Buchung, keine Änderung am vorhandenen Modell, an den bestehenden Produktregeln oder an der [Produktionsreferenz](https://github.com/xantharu123-png/btts-pro-analyzer/tree/betboy-referenz-2026-11-21). Vorgeschlagene technische Abnahme unten; das ist noch kein Releasebericht.

## Auswahl und Preis

- Das Modell prüft die sportlich qualifizierten Märkte des heutigen Spiels aus dem bereits gespeicherten automatischen Bestand, unabhängig von UI-Filter, Seite, Doublebet-Band und Preis. Kein neuer API-Abruf. Keine morgige Vorschau, gestartete Partie, unklare Zuordnung, Forschungs-Ausnahme eines anderen Produkts oder Auswahl ohne nachvollziehbare sportliche Grundlage.
- Preis ist eine Bedingung für die Zusammenstellung, kein Prognosemerkmal. Für jede Auswahl braucht es einen exakt zu Spiel, Teilnehmern, Markt, Zeitraum, Linie und Seite passenden Preis von **mindestens 1,20 einschließlich** beim **selben** Buchmacher. Zusätzlich gilt der bestehende öffentliche Preisfilter. Keine Mindest-Gesamtquote. Pro Angebot dessen Anbieterzeit (max. 45 Minuten) und Abrufzeit (max. 35 Minuten) am Entscheidungszeitpunkt prüfen; keine Zukunftsdaten. Anzeigezeit oder Cachetreffer ersetzen keine Anbieterzeit. Preisstatus beim späteren Öffnen erneut prüfen, nicht den Schein umschreiben. Ein Produkt beobachteter Einzelquoten ist keine vom Buchmacher bestätigte Scheinquote.
- Stabile Buchmacher-ID mit Herkunft verwenden. Unterschiedliche Anbieterquellen nur über nachgewiesene eindeutige Zuordnung desselben Buchmachers und Angebotsgebiets zusammenführen. Keine Namensähnlichkeit, rohen Zahlen-IDs oder Bestquoten verschiedener Bücher mischen. Hockey, Basketball und E-Sport liefern im jetzigen Pfad Abrufbeobachtungen, keine Anbieteruhr; dafür keine erfundene Ausnahme.
- Eine Partie und ein Teilnehmer je Schein höchstens einmal, auch bei Alias oder Wettbewerbswechsel. Zwischen zwei Scheinen höchstens ein gemeinsames Spiel; pro Spiel über alle vier Scheine maximal zwei Einsätze, immer exakt dieselbe Auswahl. 3er zuerst; 6er kein aufgefüllter 5er. Scheine nur in voller Größe; am dünnen Spieltag sind null Scheine korrekt. Gleiche Daten liefern dasselbe Ergebnis, Preis ist kein Sortierschlüssel. Bei identischer sportlicher Bewertung stabile Identitäten als Gleichstandsentscheidung.

## Chancenbalken und Qualitätsprüfung

Der Einzeltipp-Durchschnitt ist keine Gewinnwahrscheinlichkeit für den Schein. Die interne
Qualitätsprüfung für „alle richtig“ bleibt getrennt: Eine Rückzahlung/Annullierung ist kein
gewonnener Originalschein. Weder 15K-Abschläge noch Fréchet-Untergrenze oder das Produkt
unter Unabhängigkeit sind empirisch bestätigte Scheinwahrscheinlichkeiten. Keine Umdeutung
von 12/14 Einzelgewinnern in erfolgreiche historische Scheine.

Vergleich vorab festlegen: deterministische Referenz „höchste zulässige Einzelwahrscheinlichkeiten“ unter exakt denselben Buchmacher-, Uhrzeit-, Qualitäts- und Überlappungsregeln. Eine Modellvariante darf vergleichbare Auswahlen mit gleichgerichteten historischen Modellfehlern (gleiche Liga/Marktfamilie) zurückstufen. Abhängigkeiten und Kalibrierung aus Trainingsspieltagen schätzen; nur frühere, exakt zugeordnete Ergebnisse. Danach Version und Parameter einfrieren. Ganze, spätere Zürcher Spieltage testen, keine zufällige Aufteilung von Einzelmärkten. Pro Größe Anzahl Scheine, Auslassungen, offen/annulliert, echte Treffer, erwartete Treffer, Kalibrierungsabweichung und Brier-Wert gegenüber der Referenz ausweisen. Bei gleichem Spiel in zwei Scheinen ganze Spieltage gemeinsam auswerten. Kein Prozentwert für nicht geprüfte Größen/Sport-Kombinationen.

## Festschreiben und Anzeige

„Vor dem ersten Anpfiff“ meint den ersten Anpfiff **des jeweiligen Scheins**, nicht den ersten des Tages. Ist ein früheres Spiel schon gestartet, kann ein späterer regulärer Lauf weiterhin einen komplett aus bevorstehenden Spielen bestehenden Abendschein festschreiben. Ein heute noch freier 6er darf keinen fixierten 3er verdrängen.

Für die Auswahl pro Größe zählt die größte modellierte gemeinsame Chance unter allen zulässigen Zusammenstellungen, nicht das größte Einzel-p oder die größte Gesamtquote. Bei Modellen ohne Freigabe sind die internen Referenzscheine nach dem Produkt der p (explizite Unabhängigkeitsreferenz) zu sortieren; Gleichstand deterministisch nach den kanonischen Auswahl-IDs und schließlich der Buchmacher-ID auflösen. Eine begrenzte Suche darf nur dann ein Optimum behaupten, wenn die Schranke es belegt; andernfalls Auslassung intern kennzeichnen.

Ein ursprünglicher Schein ist ein eigenes, unveränderliches Objekt. Er wird bei einer **regulären** Veröffentlichung vor dem ersten Anpfiff einmal pro Tag, Größe und Policy festgeschrieben. Referenz und Modellvariante intern getrennt; genau die dem Nutzer angebotene Version als solche markieren. Bei neuem Quotenlauf nur bisher freie Größen füllen, bestehende Überlappungen beachten. Fehlende, ungültige oder widersprüchliche Belege sperren nur die betroffene neue Kombi; Doublebet, Tennis und der Tageslauf müssen weiter funktionieren. Nur kleine Scheinbelege speichern (IDs, Teilnehmer, Markt, p, Zeit, Version, exakter Buchmacherpreis), keine Quelllisten oder Datenbankkopien. Ergebnisse danach aus bereits verifizierten Original-Prognose-IDs ableiten. Keine nachträgliche Umstellung auf eine besser ausgegangene Auswahl.

Kundenansicht: pro Größe höchstens ein Schein, Spiele nach Beginn, kurze Begründung pro Auswahl, Balken mit lesbarer Prozentzahl. Gemeinsame Auswahl bei Bedarf kurz kennzeichnen. Ein gemeinsamer kurzer Leerzustand genügt, keine vier technischen Fehlermeldungen. Zugang folgt der bestehenden Berechtigung der rechten Pro-Tagesauswahl; keine Tarifänderung. Eine Anlaufphase ohne validierte Scheine darf intern Belege sammeln, ist **kein** fertig validierter Kundenstart.

## Alternativen und Grenzen

Vier verschachtelte Top-Listen vervielfachen dasselbe Risiko; vier vollständig getrennte Scheine verlangen 18 Spiele. Gewählt ist begrenzte Überlappung. Für eine noch nicht validierte Größe kommen nur intern markierte Probescheine infrage, keine als geprüft dargestellten Kundenscheine. Ohne hinreichendes historisches Material sind die technische Auslieferung und die mathematische Freigabe zwei verschiedene Termine.
