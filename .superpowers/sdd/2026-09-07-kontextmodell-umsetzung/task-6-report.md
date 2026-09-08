# Task 6 / B2 — regularisierte Offset-Schätzung

Datum: 2026-09-08. Implementierender Agent: `/root/b1_observations` (dieser Folgetask ist B2).

## Stand und Grenzen

B2 ist im isolierten Checkout implementiert und selbstgeprüft. Der eingefrorene vollständige lokale Testlauf ist grün. **Unabhängiges Review steht noch aus; keine empirische oder produktive Freigabe.**

- Arbeitskopie: `C:/Projekt/BetBoy/betboy-app/.worktrees/kontext-b2-20260908`.
- Branch: `codex/kontext-b2-20260908`.
- Exakte Quellbasis: `0c50c5ab2a30c1ffd1f35a62be9c4dda863306b3`.
- Gezielter Implementierungscommit: `a71d0955a74884a152c90fddd9bfae2e20602b34` — `feat: learn regularized context offsets against frozen base models` (exakt vier Dateien, 529 Einfügungen / 10 Löschungen).
- Der Agent hat weder gepusht noch gemergt, keine Netzwerk-/Provider-/VPS-Abfragen vorgenommen und keinen Unteragenten gestartet.
- Nur B2 und der vereinbarte gemeinsame Fit-Validator wurden geändert. Keine Datenquelle, Beobachtung, Modellvariante, empirische Auswahl, Preis-/Rankingregel, Cricket-, Konto-, Ticket- oder Abrechnungsfunktion wurde geändert oder aktiviert. B3 und die späteren Sportadapter/Abnahmen bleiben eigenständige Aufgaben.

## Autoritative Grundlagen

Vollständig gelesen: Task-6-Brief, freigegebene Kontextmodell-Spezifikation, `context-contract-decisions.md` einschließlich der numerischen B2-Klarstellungen und die tatsächlichen B1-Verträge. Der Brief fehlte noch im B2-Checkout und wurde ausdrücklich **nur lesend** aus `kontextmodell-20260907/.superpowers/sdd/2026-09-07-kontextmodell-umsetzung/task-6-brief.md` verwendet. Keine fehlenden Unterlagen eigenmächtig kopiert oder Änderungen aus der späteren Controller-Dokumentationsversion in B2 gemergt.

Das alte Superpowers-Paket ist in diesem Konto nicht verfügbar. Der bereits freigegebene TDD-/gezielte-Commit-/unabhängige-Review-Ablauf wurde beibehalten, ohne Installation oder erneute Freigabefrage.

## Exakte Dateigrenze

1. `context_models/offset.py` — neue reine numerische Routinen und typisierter `ContextModelError`.
2. `context_models/contracts.py` — gemeinsamer geschlossener `validate_offset_fit`; vorhandener EffectArtifact-Validator verwendet ihn zusätzlich zu seinen Familien-/Head-/Feature-Reihenfolgeprüfungen.
3. `tests/test_context_offset.py` — synthetische numerische Regressionen.
4. `tests/test_context_contracts.py` — ausschließlich gemeinsame Fit-Vertragsprüfungen.

Dieser Bericht liegt separat in der eigenen SDD-Ablage und wird vom Controller zusammen mit dem unabhängigen Review gesichert. Er ist kein Produktionscode.

## Implementierter Vertrag

- Tatsächlich gelernte, regularisierte Poisson-, Binomial- und Gaussian-Residuen gegen bereits eingefrorene Link-Offsets; exakt die festgelegten gemittelten Verluste und analytischen Gradienten.
- Kein zusätzlicher Intercept, keine Zentrierung, kein Fit einer Basisskala. Training-only-Skalierung `max(std(ddof=0), 1e-8)`; Vorhersagen verwenden nur die gespeicherte Skala und unveränderte Feature-Reihenfolge.
- Festgelegter `L-BFGS-B`-Aufruf mit Nullstart und `jac=True`; kein alternativer Optimierer, keine Bounds/Clipping, kein stiller Null-/Altmodell-Fallback. Alpha wird als numerischer Parameter übergeben; seine Auswahl gehört D1.
- Rein nullwertige Trainingsspalten behalten exakt Nullkoeffizienten. Null-Delta erhält die Basiswerte bitgenau, einschließlich negativer Null im Identity-Link.
- Rate-Inversion im gemeinsamen Lograum erhält repräsentierbare Extremfälle (`1e-300,+800` bzw. `1e300,-800`). Echte Über-/Unterläufe, nichtpositive Raten und numerisch gesättigte Logit-Endpunkte liefern den typisierten Fehler, keine künstliche Reparatur.
- Poisson-/Binomial-Beobachtungen sind ganzzahlwertig; `1.0` ist legal, Bruchteile nicht. Binomial-Trials sind mindestens eins, standardmäßig eins, und Erfolge überschreiten Trials nicht. Identity-Ziele dürfen endliche negative/reelle Werte sein.
- Numerische APIs verlangen tatsächliche numerische NumPy-Arrays, prüfen Dimensionen und Übereinstimmung ohne Broadcasting und weisen Bool/String/Object/Complex/Masked/NaN/Inf vor Float-Konversion zurück. Nicht verlustfrei in Float64 abbildbare Integer-Arraywerte werden nicht still gerundet. Numerische NumPy-Skalare für Alpha werden vor JSON-Ausgabe in echte endliche Python-Zahlen normalisiert.
- Gespeicherte Fits besitzen exakt `link, scale, coef, alpha, n_rows`; echte endliche JSON-Zahlenlisten, gleiche nichtleere Dimensionen, Skala mindestens `1e-8`, Alpha nichtnegativ und tatsächliches ganzzahliges `n_rows >= 2`. Vorhersage und Artefakt verwenden denselben Validator. Gültige große JSON-Ganzzahlen werden innerhalb der numerischen Routine explizit als Float64 eingelesen, nicht als Object-Array und nicht pauschal begrenzt.
- Nichtkonvergenz, Backend-Ausnahmen, nichtendliche Skala/Verluste/Gradienten/Parameter und widersprüchliche Optimiererrückgaben liefern den typisierten Fehler. B3 muss damit die gültige Basis behalten; diese spätere Integration wurde hier nicht vorgetäuscht.

## TDD und Regressionsevidenz

Alle Läufe verwendeten `C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe`, `-B -m pytest`, `-p no:cacheprovider` und jeweils ein neues `.pytest_tmp`-Kind. Ausschließlich synthetische lokale Tests; keine reale kausale Quelle oder empirische Prognoseverbesserung wird dadurch zertifiziert.

| Lauf / Basetemp | Tatsächliches Ergebnis |
| --- | --- |
| `b2-initial-red` | erwarteter Collection-Fehler `ModuleNotFoundError: context_models.offset`; gelernter Effekt noch nicht implementiert |
| `b2-initial-green` | 108 bestanden, 0.76 s |
| `b2-regression-01` | 1 fehlgeschlagen, 256 bestanden, 1.00 s: gültiges `np.float64(.1)` für Alpha fälschlich abgewiesen |
| `b2-large-json-red` | 2 fehlgeschlagen, 140 abgewählt, 0.72 s: gültige JSON-Skala bzw. Koeffizient `10**20` erzeugte untypisierten `np.isfinite`-TypeError |
| `b2-regression-02` | 259 bestanden, 0.76 s; beide Eingabegrenzen korrigiert |
| `b2-final-focus` | 262 bestanden, 0.81 s, mit `-rs`; keine Skips |
| `b2-frozen-full-01` | **2324 bestanden, 15 übersprungen, 97 Untertests bestanden, 73.36 s**; Exitcode 0 |

Finaler fokussierter Aufruf:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest tests/test_context_offset.py tests/test_context_contracts.py -q -rs -p no:cacheprovider --basetemp=.pytest_tmp/b2-final-focus --tb=short
```

Einmaliger vollständiger Lauf auf dem eingefrorenen endgültigen Quell-/Teststand:

```powershell
& 'C:/Projekt/BetBoy/betboy-app/.codex_test_venv/quality/Scripts/python.exe' -B -m pytest -q -rs -p no:cacheprovider --basetemp=.pytest_tmp/b2-frozen-full-01
```

Abgesichert sind alle drei tatsächlich trainierten Links, exakte Zielfunktion und zentrale Finite-Differenzen für die Gradienten mit und ohne Regularisierung, Seitenumkehr/Komplement, nichtzentrierte Referenz, exakte Nullspalten/-Delta, training-only-Skalierung, JSON-Roundtrip, Eingabeunveränderlichkeit, der exakte Optimiereraufruf, Zählwert-/Trials- und Typ-/Dimensionsgrenzen sowie fehlgeschlagene/inkonsistente Optimierungen. Die vom Controller gemeldeten zwei großen JSON-Integer-Fälle wurden **vor der Korrektur reproduziert**, danach als Produktregression bestanden.

## Erwartete Windows-Skips aus `-rs`

Die 15 Skips betreffen unveränderte plattformspezifische Tests, nicht B2. Bei WinError 1314 werden unten nur die dynamischen temporären Quell-/Zielpfade weggelassen; der eigentliche Grund bleibt erhalten.

| Datei / Zeile | Anzahl | Ausgegebener Grund |
| --- | --- | --- |
| `tests/test_backup_stage_archive.py:279` | 1 | `database symlinks are unavailable on this platform: [WinError 1314] Dem Client fehlt ein erforderliches Recht` |
| `tests/test_model_artifacts.py:420` | 1 | `POSIX process umask` |
| `tests/test_model_artifacts.py:593` | 1 | `POSIX permission bits` |
| `tests/test_model_artifacts.py:607` | 1 | `POSIX permission bits` |
| `tests/test_model_artifacts.py:617` | 1 | `POSIX permission bits` |
| `tests/test_server_jobs.py:790` | 1 | `directory symlinks are unavailable` |
| `tests/test_server_jobs.py:1702` | 1 | `file symlinks are unavailable` |
| `tests/test_server_jobs.py:1748` | 1 | `directory symlinks are unavailable` |
| `tests/test_server_jobs.py:2579` | 1 | `directory symlinks are unavailable` |
| `tests/test_server_jobs.py:2596` | 1 | `directory symlinks are unavailable` |
| `tests/test_server_jobs.py:2659` | 1 | `directory symlinks are unavailable` |
| `tests/test_server_jobs.py:2802` | 1 | `file symlinks are unavailable` |
| `tests/test_tennis_training_cache.py:203` | 3 | `symlinks unavailable: [WinError 1314] Dem Client fehlt ein erforderliches Recht` |

## Eingefrorene Rohbytes (SHA-256)

Vor dem vollständigen Lauf ermittelt und nach dem Lauf vor dem Staging unverändert bestätigt. Git kann wegen der bestehenden CRLF-Konfiguration andere normalisierte Blob-Hashes haben; diese Tabelle bezeichnet ausdrücklich die getesteten lokalen Rohbytes.

| Datei | SHA-256 |
| --- | --- |
| `context_models/offset.py` | `907fbcc5dda91f820be32b3144fa76dca8f7cdf7e8af1485d12a956e2838c23c` |
| `context_models/contracts.py` | `e462518584a285c0716ea74f5fad30a8c40980df7f7c322252cfd2d087e722b4` |
| `tests/test_context_offset.py` | `9c5f242d74df2e7d117692854346e8fd1e45e4bf03124cf970fb644ac7104778` |
| `tests/test_context_contracts.py` | `89a006f6374bde75aeec8795057ba70c3f70dd0eb7d0b3b2fd8d1a5646c4cd36` |
| unveränderter `scripts/stage_runtime_databases.py` | `1441158c542e97a19b193fa0cd091b645ec6442d6d8157f1d4fceabbba72b026` |

Die normalisierten Git-Blobs des gezielten Commits sind:

| Datei | Git-Blob |
| --- | --- |
| `context_models/offset.py` | `08652312066156a4a34b12e6f59e2a6585247a8f` |
| `context_models/contracts.py` | `eb36d85b5c05141712301952e85de535c04601f4` |
| `tests/test_context_offset.py` | `019f0912d8fc8179bf0741154acd2c3b54d8b059` |
| `tests/test_context_contracts.py` | `0f751ae7e3e85a8ec2d1bacbea9f651246b35177` |

## Selbstreview und nächster Nachweis

Der Agent hat Brief, gemeinsame Verträge, numerischen Kern und gezielten Diff abgeglichen. `git diff --check` ist grün; lediglich die bestehende Git-Zeilenendenwarnung für zwei geänderte Dateien erschien. Keine fachliche Entscheidung zu Datenquellen oder Empirie wurde aus grünen Mechaniktests abgeleitet. Die vom Controller gefundene Eingabegrenze wurde nicht als ungültige Nutzereingabe umdefiniert.

`git diff --cached --check` und die explizite Vier-Dateien-Stagingprüfung waren vor dem Commit grün. Nach dem Commit ist der einzige ungetrackte Eintrag dieser Bericht; kein fremder WIP wurde gestaged. Quell-/Teständerungen sind beendet. Der Controller soll genau diesen Stand unabhängig prüfen; Integration, Push, empirische Abnahme und VPS-Aktivierung sind weiterhin getrennte, hier **nicht** behauptete Nachweise.
