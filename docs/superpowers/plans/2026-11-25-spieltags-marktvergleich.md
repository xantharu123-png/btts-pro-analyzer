# Spieltags-Marktvergleich Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans or subagent-driven-development. Treat the checks below as release evidence.

**Goal:** Einen belegten Spieltag festhalten und dieselbe Marktanalyse für weitere abgeschlossene Zürcher Tage wiederholen können.

**Architecture:** Ein optionaler Bericht im bestehenden Read-only-CLI über Archiv und Evidenzdatenbank. Der Nutzerbericht und die produktiven Prozesse bleiben unverändert. Quellen für Live, Scheine und RisikoBet sind im Referenzbericht separat dokumentiert.

**Tech Stack:** Python, bestehender Archivleser, SQLite in `mode=ro`, pytest.

**Spec:** Auftrag vom 25.11. und Tagesaudit im Chat: Haupttipps getrennt vom Katalog und je Wettart; Quotenstatus und nur hypothetische Rendite auf exakt frischen Preisbelegen; keine Gewichte, Frischegrenzen, Jobs oder API-Abrufe ändern.

## Global Constraints

Zürcher Kalendertage; maximal 31 pro Aufruf. Ein einheitlicher `as_of`-Stichtag pro Bericht. Standardansicht und Automatik separat; keine nachträglich ausgewählten besseren Preise. Kein Produktscan, keine neue DB, keine Änderung der bisherigen CLI ohne die neue Option.

## Review Focus

Kein Beleg ist kein Verlust. Frische Preise bei offenen Spielen liefern noch keinen Rendite-Nenner. Vorschau ohne exakte Bindung wird nicht rückwirkend verknüpft. Preis und Prognose behalten Originalzeit und -revision. Verwandte Märkte je Spiel sind keine unabhängigen Beobachtungen.

1. [x] Echte Archiv-Fixtures testen: erster Haupttipp plus Nebenmarkt, offene Entscheidung und frischer versus alter Preis. `--market-review` im vorhandenen CLI ergänzen; pro Tag und gepoolt gleiche Zählweise verwenden. Vorher Rottest, nachher grün. Die neue Projektion verändert keine Archive; alte CLI-Felder bleiben unverändert.
2. [x] Vergleich 21.–24.11. gegen bestehende Produktionsdaten in einem netzwerkisolierten Python-Prozess nachgespielt; abschliessende Prüfung des fertigen Reports reproduziert den 24.11.-Stichtag. Referenz `9d8f945`, beide Abnahmezeiten, Preisbefund und Vorab/Live/Kombi-Unterschiede dokumentiert. Keine Migration und kein neuer Dienst.
