# D3: optionale unveränderliche Kontextreferenz in beiden Verbraucherverträgen

9. September 2026. Dieses Paket erweitert die vorhandenen Signal-/Snapshot-
Verträge; der echte Tennis-Producer und seine fachliche Kartenprojektion werden
separat angeschlossen. Keine neue empirische oder produktive Freigabe.

`ContextReference` ist ein eingefrorener Datentyp mit zwei unveränderlichen
SHA256-Feldern. Seine JSON-Form bleibt exakt der bestehende vierteilige D3-
Refvertrag. `ModelSignal.context_ref` und `EventModelSnapshot.context_ref` sind
optional. Ohne Ref bleiben bisherige Serialisierung und Snapshot-ID exakt
erhalten; das neue Feld wird nicht als `null` in alte Dokumente eingefügt.

Der normale Worker serialisiert einen tatsächlich vorhandenen Ref; beide
bestehenden Leser für Modellkatalog und getrennte Preisfreigabe erhalten ihn.
RisikoBet bindet den optionalen Ref zusätzlich in die Snapshot-ID. Der Store
und der vorhandene strenge UI-Dokumentleser prüfen dieselbe Identität. Diese
Erweiterung speichert keine neue Wettpreis- oder Freigabeinformation.

Die bestehende SQLite-Eindeutigkeit aus Event, Modellversion und Inputhash
bleibt erhalten. Ein veränderter Kontext muss Teil des echten geänderten
Inputhashs sein; ein Ref allein darf dieselben ursprünglichen Inputs nicht
mit abweichendem Inhalt überschreiben. Der Koexistenztest prüft die Ablehnung
dieses Konflikts und anschließend die neue tatsächlich eigene Inputrevision.
Es gibt weder Schemamigration noch Änderung der alten Geld-/Ticketgeschichte.

## Ausgeführte Regressionen

- 11 neue initiale API-REDs, anschließend zehn grün/ein Testharnessfehler:
  `write_run` war kein vorhandener Storeaufruf. Nur der Testaufruf wurde auf
  das tatsächliche `append_run` korrigiert.
- Die folgende Runde zeigte den bestehenden Event/Modell/Input-Unique-Vertrag.
  Statt ihn zu lockern, dokumentiert der Test jetzt zuerst die erwartete
  Ablehnung und verwendet für neue Eingaben deren eigenen Hash. 295 bestanden,
  26 Untertests, 5,60s; kein Datenbankvertrag wurde geändert.
- Drei zusätzliche echte JSON-Readback-Tests reproduzierten noch den verlorenen
  Ref: 3 ROT/11 GRÜN. Nach dem Anschluss beider vorhandenen Leser: **298 bestanden,
  26 Untertests bestanden, keine Skips, 5,95s**.
- Abgedeckt: Domain/Store/UI-Leser, Wettfinderautomation, Signalquellen und
  Workflowintegrität. Neue Tests prüfen die geschlossene Form, echte bool-/
  Digest-/Zusatzfeldablehnung, unveränderliche Werte, getrennte JSON-Kopien,
  alte/neue persistierte Snapshot-Koexistenz und Preisoverlay-Refgleichheit.

```text
9cef750abca4a210c25725cae07412deb3bbd64a2f8dddddf162048fd49cae1d context_links.py
c9dbdf14317377ea2a65f9255f21f84e897b074a8b37ebb3b66955cf65faf9fd tests/test_context_domain_links.py
f970df164f355db1882da53db52f07d4874994f04f322cac68a9630a470bfafb .pytest_tmp/context-domain-link-broad-20260909-03.xml
```

Vier eigene bearbeitete Verbrauchermodule waren im Checkout durch Git/Edits
gemischt CRLF/LF. Sie wurden ausschließlich mechanisch auf die tatsächlichen
LF-Gitblobs ausgerichtet; dadurch bleibt der Source-Diff auf die realen neuen
Vertragszeilen begrenzt. Kein geschütztes Modellrezept oder Stagehelper wurde
normalisiert. Stagehelper-SHA weiterhin
`1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026`.

Unabhängiges Review und tatsächliche Producer-/Kartenintegration stehen noch
aus. Die parallel auf `d2809fc` laufende Vollsuite enthält dieses Paket noch
nicht. Cricket, Preis-/Rankinglogik, 15K und VPS-Verhalten bleiben unverändert.
