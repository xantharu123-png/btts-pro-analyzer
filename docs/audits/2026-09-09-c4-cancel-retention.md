# C4: Absageruecknahme bleibt ueber andere Fakten erhalten

9. September 2026. Ausgangspunkt: `79763a179b3efdd67c9f6d8ae6bd1c0d2032e3a2`.
Dieser Nachtrag korrigiert den unabhaengig belegten C4-R1b-Fall. Er ersetzt
weder die beiden frueheren Reviews noch behauptet er echte neue Quelldaten,
empirische Wirkung, Root-Integration oder Produktivfreigabe.

## Ursache und enger Eingriff

Der vorherige Fix behielt eine zwischenzeitliche `started`-Ruecknahme,
aber nicht `cancelled`. Eine spaetere abgeschlossene Map oder historische
Aufstellung konnte deshalb den alten, widerrufenen Serienabschluss wieder
gueltig machen. Der unveraenderte unabhaengige Gegenlauf liegt unter
`.pytest_tmp/c4-final-independent-20260909/test_c4_lifecycle_edges.py`.

Der Resolver behandelt beide tatsaechlich empfangenen Statuswerte als
Ruecknahme eines aelteren terminalen Serien-/Aufstellungsfakts. Erst ein
neues eigenes vollstaendiges terminales Faktum nach der Ruecknahme kann
seinen eigenen Abschluss wieder belegen. Der bereits vorhandene Vergleich
mit tatsaechlichen Map-Endzeiten bleibt bestehen. Keine Ende-/Dauerschaetzung.

Auch eine aktuell wirksame Absage behaelt die Ungewissheit beim Widerruf
eines alten numerischen Fakts: Sie ist kein Nachweis gemessener Nullbelastung
und macht ein aelteres Spiel nicht zum sicher letzten abgeschlossenen Spiel.
Die Quelle, ihre Subject-v2-Identitaet und die generische B1-Auswahl bleiben
unveraendert. Es gibt keine Migration oder Neuberechnung alter DB-Zeilen.

## Tatsaechliche Regressionen

Neue Dauertests verwenden echte temporaere B1-SQLite-Dateien und synthetische
native Quellen, nicht tatsaechliche PandaScore-Spielerhistorien:

- map/started, map/cancelled und observed_lineup/cancelled, beide Teams;
- Widerruf bleibt bei abgelaufener Meldung erhalten;
- neuer eigener konsistenter Serienabschluss stellt nur seine Zeit wieder her;
- tatsaechlicher Empfang bei Cutoff minus/equal/plus einer Mikrosekunde;
- kein frei erfundenes `valid_from` im geschlossenen Quellenschema.

Die erste neue Harnessfassung hatte drei unzulaessige Kombinationen
started/observed_lineup sowie zwei zusaetzliche, dort verbotene valid_from-
Felder. Diese fuenf Harnessfehler wurden vor jedem Sourcefix anhand des
bestehenden Quellenschemas korrigiert: zulaessige Paare beziehungsweise
explizite Ablehnung. Keine alte oder unabhaengige Assertion wurde veraendert.

Korrigierter Dauertestlauf auf altem Sourcecode: **8 echte RED / 8 GREEN**,
13,87 s, `.pytest_tmp/c4-retractions-red-20260909-02.xml`. Darunter zwei
zusaetzliche belegte Nullbelastungsfehler bei aktuell empfangener Absage.
Nach dem engen Sourcefix: **176 GREEN**, 94,48 s, inklusive aller 67
urspruenglichen unabhaengigen Repros und der 10 unveraenderten R1b-Gegenfaelle.
Dieser Fokus ersetzt nicht die gesamte C4-Modell- oder Root-Vollsuite.

Die ganze C4-Worktree-Suite ist auf diesen eingefrorenen Bytes abgeschlossen:
**4.205 bestanden, 18 erwartete Plattform-Skips, 97 Untertests**, 257,97 s,
`.pytest_tmp/c4-retractions-full-20260909-01.xml`. Die Skips betreffen
Windows-Symlinkrechte beziehungsweise POSIX-Eigentuemer-/Moduspruefungen,
keinen neuen Kontextfall. Das ist nicht die weiterentwickelte Root-Vollsuite.
Eine unabhaengige Nachpruefung laeuft weiterhin; ihr Resultat ist separat.

## Eingefrorene Bytes

```text
ddd7be0707ded720d546af78cb11c082c03ee0b462705d46c1dbce77a1a47a7c  context_models/esports.py
e5ef10ae444e6947b4841eef832ee8f4109f35c8d765918c4d503b8d96242901  tests/test_esports_context_retractions.py
6719a39df1578e59e5c20197b6f2f6057253eee0fc4063bc1048b4de84beb567  context_sources/esports.py (unveraendert)
```

Unveraendert: Default-Elo, Cricket, Preise/Ranking, Tickets, 15K, Abrechnung,
historische Prognosen und VPS. Ein erfolgreicher Mechaniktest ist weiterhin
kein Beleg einer empirisch gelernten oder produktiv aktivierten Ermuedung.
