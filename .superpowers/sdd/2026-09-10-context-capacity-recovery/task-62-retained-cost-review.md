# Task62: eng begrenzte Retained-Kostendiagnose

## Ergebnis

Der vollständige Erfolgsweg verlangt **vier Vollbeobachtungen je Retained-Root**:
zwei im selben Preparation-Prozess und zwei im selben späteren Parent-Prozess.
Beide Prozesse haben jeweils eine kumulative CPU60-Grenze. Es sind nicht60CPU
pro Scan; die Worker240CPU können keinen dieser Parent-Scans finanzieren.
Ein erfolgreicher Einzelroot-Scan beweist deshalb noch keinen ausführbaren
Gesamtweg. Mit der vorliegenden Messung ist dessen CPU60-Passung nicht belegt
und die gleichbleibende-Kosten-Hochrechnung überschreitet sie bereits deutlich.

Zeilen beziehen sich auf die gelesenen aktuellen Parent-/Catalogue-Dateien
(Root meldet HEADbb54ec5) sowie das historische Task61-Preparation-Instrument.
Keine Git-/VPS-/Testaktion oder Implementierung; nur dieser Bericht wurde ergänzt.

## Exakte Aufrufstellen und Prozessgrenzen

| Prozess / Stelle | Vollscans pro Root auf dem Erfolgsweg | CPU-Grenze |
|---|---:|---|
| `evidence/task61-native-catalogue-prepare.py:82-90`: direkte Schleife mit `retained_root` in Zeile83 | 1 | derselbe Preparation-Prozess, `(60,60)` ab Zeile3 |
| Preparation Zeile96 ruft `inventory`; aktueller Catalogue `:1028` ruft `validate_retained(..., observe=True)` | 1 weiterer | weiterhin dasselbe60CPU-Konto, kein Neustart |
| `tests/native_context_receipt_diagnostic.py:376`: vollständige Beobachtung vor Admission/Worker | 1 | Parent `startup():94-112`, CPU60 ab Zeile98 |
| Parent `:472`: vollständige Beobachtung nach Worker-Rückkehr, vor Ergebnisannahme/Close | 1 weiterer | derselbe Parent und dieselbe kumulative60CPU-Grenze |

Die gemeinsame Semantik steht in
`tests/native_context_receipt_diagnostic_catalogue.py:595-625`: `observe` ist
standardmäßigFalse; beiTrue führt die Root-Schleife in Zeile624 tatsächlich
`retained_root(name)` aus und vergleicht den kompletten Befund. Der Linux-Pfad
`:448-536` liest alle regulären Dateien vollständig, statt nur Metadaten oder
gespeicherte Hashes zu übernehmen.

Nicht als zusätzliche Vollscans mitzählen:

- Preparation `:94` prüft die gespeicherte Form mit dem DefaultFalse.
- `validate_manifest` im Catalogue `:962` nutzt ebenfalls DefaultFalse; dies
  betrifft `inventory():1058`, `launcher():1012` und Parent `:365`.
- `selected()` in Preparation `:79,91,99` enumeriert die Auswahlverzeichnisse,
  nicht sämtliche Root-Dateiinhalte.
- Parent `recheck():404-427`, aufgerufen `:452,473`, kontrolliert aktive Inputs
  und neue Job-/Registry-Slots; es ist kein weiterer historischer Vollscan,
  verursacht aber zusätzliche Parent-CPU.
- Journalbeobachtungen in Preparation `:89` und Catalogue `:622,650-679`
  lesen/replayen deklarierte Journale zusätzlich; sie sind keine erneute
  Vollbeobachtung aller Root-Inhalte.

Das Preparation-Instrument ist historisch fest auf den alten Catalogue-Pin
und Commit1632072 gebunden (`:22-33,96`), nicht bereits ein startbereites
Task62/63-Instrument. Seine Aufrufstruktur zeigt die doppelte Beobachtung;
die aktuellen Catalogue-Zeilen belegen, dass `inventory` sie weiterhin enthält.
Kein stilles Umpinnen oder erneuter Preparation-Lauf ist hier autorisiert.

Parent-Details: erster Scan `:376` liegt vor Admission `:393` und Workerstart
`:456`; zweiter Scan `:472` nach Ergebnis-/Logpersistierung `:463-465`, jedoch
vor Ergebnisannahme `:474` und Admission-Close `:476`. Ein CPU-Abbruch dort ist
kein sauberer Abschluss. Der einzelne Worker erhält240CPU ausschließlich im
direkten Kind (`:115-149`, insbesondere `:144`); `launch_once():153-165` prüft
anschließend ausdrücklich die unveränderten60CPU des Parents. Parent-Start,
Vorprüfung, Kopien, Überwachung, Nachprüfung, Ausgabe und Cleanup teilen diese
Grenze. Preparation setzt daneben Alarm300 (`:17`); der Parent bindet seine
3600s-Frist an den ursprünglichen Kernel-Prozessstart (`:107-112,348-355`).

## Messung gegenüber unverbindlicher Hochrechnung

Root übermittelt für Session82187/Terminale86c3d, SSH0, genau einen vollständigen
Scan von `/tmp/betboy-context-qa.9xr68INa`:

- 56895 Dateien,17409 Verzeichnisse,1932 Symlinks;
  7599442782 logische und7748403200 allokierte Bytes.
- Scan-CPU47.558612911s; externe ganze CPU35.88+11.79=47.67s;
  externe Wall59.41s; RSS38328KiB.

Diese native Einzelmessung wurde hier nicht wiederholt oder aus Rohlogs erneut
verifiziert. Sie umfasst weder alle Retained-Roots noch mehrere Durchläufe.

**Nur bei unverändertem Aufwand pro Beobachtung** ergeben zwei Scans allein
dieses einen Roots95.117225822CPU-s in jedem der beiden Prozesse, vier insgesamt
190.234451644CPU-s über beide Prozesse. Nach einem solchen Scan blieben von60CPU
rechnerisch12.441387089s, noch vor anderen Roots und allen übrigen Arbeiten.
Das ist keine gemessene Mehrfachlaufzeit und keine harte zukünftige Untergrenze:
Cache-/I/O-Zustand und Laufvariationen können Kosten verändern. Insbesondere
ist59.41s Wall nicht gleich59.41CPU-s. Ein Speedup-Verhältnis zum alten Walker
ist ohne vergleichbare alte Messung nicht ableitbar.

## Nächste Entscheidungsgrenze

Der Engpass ist nicht mehr allein die Kosten einer einzelnen Traversierung,
sondern deren verpflichtende Wiederholung innerhalb derselben60CPU-Prozesse.
Eine weitere Freigabe benötigt zunächst eine explizite Architektur-/Budget-
Entscheidung oder einen plausibel budgetierbaren, semantikerhaltenden Ansatz.
Die bislang vorliegenden Daten rechtfertigen keinen neuen teuren Vollversuch.

Insbesondere wären eine Aufteilung der Verifikation auf zusätzliche Prozesse
mit jeweils frischem60CPU-Konto, Kostenverlagerung zum Worker, weniger
Beobachtungen oder Wiederverwendung früherer Hashes Änderungen der aktuellen
Prozess-/Prüfverträge und dürfen nicht als transparente Optimierung eingeführt
werden. Keine freie Budgeterhöhung, kein Cache/Teilscan/Überspringen alter
Historie, kein Refund und kein automatischer Wiederholungsversuch werden hier
vorgeschlagen oder umgesetzt. Preparation-Kosten bleiben separat dokumentiert;
sie werden nicht zu einem erfundenen freien Anteil des60+240/300CPU-Tickets.
C/B-/Gesamtfreigaben bleiben offen.
