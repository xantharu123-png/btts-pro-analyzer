# P4a F1: bekannte Identitätskonflikte vor unbekannten IDs prüfen

Basis dieses isolierten Folgepatches:
`f0b020557fc060e500bdb33fb466646ff1c49ce7`.
Branch: `codex/kontext-team-sports-live-idfix-20260909`.
Der ursprüngliche P4a-Worktree bleibt unverändert eingefroren.

## Bestätigter fremder P2-Befund

Der vollständige unabhängige Bericht und beide Probequellen wurden gelesen
und byteidentisch nach `.pytest_tmp/p4a-independent-20260909` in diese neue
Arbeitskopie übertragen. Vor und nach den Läufen stimmen die SHA256-Werte mit
den Originaldateien überein; kein Reviewfall wurde umgeschrieben.

`_native_binding` kehrte bei einer nicht auflösbaren Team-ID zu früh zurück.
Dadurch verdeckte diese echte Lücke eine andere, bereits bekannte falsche
Event-ID oder Gegner-ID. Die ursprüngliche Modellwahrscheinlichkeit wurde
nicht verändert und es entstand keine B3-/Quellen-/Empirikfreigabe. Dennoch
akzeptierte das Original einen bereits nachweisbaren Identitätswiderspruch.

Eigene Wiederholung der unveränderten Originalproben auf dem alten Source:
**8 fehlgeschlagen, 204 bestanden, 0 Skips**, 8,76 s, Exitcode 1. Damit sind
genau die acht gemeldeten funktionalen REDs bestätigt, nicht lediglich eine
fehlgeschlagene Testcollection.

## Enge Korrektur

Nur `_native_binding` im neuen P4a-Modul wurde geändert:

- Die bestehenden nativen Parser bleiben unverändert. Nicht auflösbare IDs
  werden intern als unbekannt behalten, ohne den Rest der Prüfung abzubrechen.
- Jede unabhängig bekannte Event-/Heimteam-/Auswärtsteam-ID wird zunächst
  gegen das übergebene kanonische Event verglichen.
- Ein belegter Widerspruch löst weiterhin den bestehenden typisierten Fehler
  aus. Erst danach dürfen tatsächlich unbekannte IDs zum bisherigen Ergebnis
  `base=None` samt unveränderter Originalprognose führen.
- Das gilt symmetrisch auch für eine unbekannte Event-ID bei bereits bekannter
  widersprüchlicher Teilnehmer-ID. Es gibt keine neue Aliasauflösung oder
  Ersetzung unbekannter IDs durch Namen, normalisierte Modell-IDs oder Null.

Keine Änderung an Numerik, Fits, Vorwärtsgesetzen, Quotes, Quellenauflösung,
Versionen, B3-Verträgen, Consumer, Transport, D4 oder Cricket. Der frühere
P4a-Audit wurde nicht überschrieben. Keine weitere Sportart angebunden.

## Permanente Regressionen und eigene Läufe

30 neue permanente Fälle verwenden echte Aufnahmen aus dem bestehenden
`predict_prematch`-Callback, nicht frei erfundene Koeffizienten:

- 24 Konfliktfälle: beide Sportarten, unbekannte Event-/Heimteam-/Auswärtsteam-ID,
  jeweils ein unabhängiger bekannter Widerspruch, über Builder und reine
  Originalvalidierung. Der reine Validator erhält ein konsistent neu gehashtes
  Event, damit der Test tatsächlich die native Prüfung erreicht.
- Sechs positive Unknown-Kontrollen: Originalwahrscheinlichkeit und Komplement
  bleiben exakt, kein natives Base-Event wird erfunden; die reine Validierung
  akzeptiert denselben unveränderten Originalbeleg.

Vor dem Sourcepatch: **24 fehlgeschlagen, 6 bestanden**, 137 abgewählt,
2,18 s, Exitcode 1. Nach dem Patch: **242 bestanden, 0 Skips**, 8,84 s,
Exitcode 0, einschließlich der unveränderten fremden Proben.

Finaler begrenzter Rücklauf: **592 bestanden, 0 Skips**, 33,10 s, Exitcode 0.
Er umfasst zusätzlich bestehende Basketball-, Hockey-Numerik- und
Kontextvertragsprüfungen sowie die bereits vorhandene genaue Cricket-Parität.
Alle PowerShell-Läufe übernahmen und prüften ausdrücklich `$LASTEXITCODE`.

```text
python -B -m pytest -q -p no:cacheprovider tests/test_sports_prematch.py tests/test_sports_prematch_original_capture.py tests/test_team_sports_live_original.py tests/test_basketball_context.py tests/test_ice_hockey_context.py tests/test_ice_hockey_numerics.py tests/test_context_contracts.py .pytest_tmp/p4a-independent-20260909/test_independent_original.py .pytest_tmp/p4a-independent-20260909/test_independent_boundaries.py --tb=short -rs --basetemp=.pytest_tmp/p4a-idfix-focus-final-01 --junitxml=.pytest_tmp/p4a-idfix-focus-final-01.xml
```

Keine eigene Vollsuite, kein Provideraufruf, Push, Merge oder VPS-Schritt.
Die tatsächliche B1-Auflösung, produktive P4b-Anbindung und unabhängige
Nachabnahme dieses Folgepatches bleiben separate Aufgaben.

## Eingefrorene Evidenz

SHA256, jeweils nach dem finalen Rücklauf geprüft:

| Datei | SHA256 |
| --- | --- |
| context_models/team_sports_live.py | dcb571b6aaef03a1e18638a8aedfd47841c1317d324f5c0561eab67da8646b8d |
| tests/test_team_sports_live_original.py | fec935a1cb49143b77aaf728a5f0a494692333547b08d082aad5477ad1813ef1 |
| .pytest_tmp/p4a-independent-20260909/REVIEW.md | 988dd9c9775adfc074b83fec18f67e04063e3893f2b0e8004be46c6a458d75cd |
| .pytest_tmp/p4a-independent-20260909/test_independent_original.py | 7bb4d33980e8379b010df6b1202ac5b829c22b97793e33b49d09793445a595ec |
| .pytest_tmp/p4a-independent-20260909/test_independent_boundaries.py | 45b0cd408673b2ac1ffcc684f58883102150065466b1136fcec1f3ed71134753 |
| .pytest_tmp/p4a-idfix-original-red-01.xml | 174e204a68f4e4198505504bf009692caa5d46082e9857b27f6186559b0e909e |
| .pytest_tmp/p4a-idfix-permanent-red-01.xml | 1ee72a9e0bdd5c7546d674e5a138f51b81411bbccc7ee5f3a223aa23ce80ef13 |
| .pytest_tmp/p4a-idfix-green-01.xml | 850c9c21a0f5ea9ce5fce53e0dd08bb3ba1ce43d1b50d580b5150b3d687f5d83 |
| .pytest_tmp/p4a-idfix-focus-final-01.xml | 0e542bd84aebc54d45f3b51fb89ad415ffc78e9d304d621a56bb398909aa6f13 |

Unveränderte ursprüngliche Quellen:

| Datei | SHA256 |
| --- | --- |
| context_models/contracts.py | 7b3c2a909fee790879d446ef2b95bc944d24951af4261c3296c36e6338518fa8 |
| sports_prematch.py | 1d908a32d4decdd508477526af9802f3a81bd9054f93636e4df8c63675b9a07d |
| context_models/team_sports.py | 6d93c2b77ce5f0085cb1861edcc9524d3064b84faa772b501bf8481fedfb7228 |
| context_models/ice_hockey.py | 5b27b2fc84c354e87e7842e5191658f9aea9f0213f4a9e5e2136270c4f1280d4 |
