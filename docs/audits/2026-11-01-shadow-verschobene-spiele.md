# Shadow: Tipps auf verschobene oder abgesagte Spiele sind ungültig

Datum: 01.11.2026. Owner-Entscheid im Chat („Ja, Regel bauen“) nach der Prüfung der ersten v12-Tipps.

## Befund (nur lesend, `output/release-20261101-1/open_priced.sh`, `open_priced2.sh`)

- Zwei v12-Tipps mit Quote lagen auf Spielen der ukrainischen Premier League:
  - Zorya Luhansk – Epitsentr Dunayivtsi, Quote 1,40
  - Karpaty – Kudrivka, Quote 1,62

  Beide waren für den 31.10. um 16:00 UTC erfasst, die Quoten wurden etwa eine Stunde vorher geholt. Laut
  `shadow_fixtures` wurden die Spiele auf den 2.11. verlegt (11:00 bzw. 16:00 UTC). Ohne Regel wären beide am 3.11.
  zur Quote vom 31.10. abgerechnet worden.
- Der v9-Tipp Shakhtar Donetsk – Obolon'-Brovar vom 30.10. hat zwei Tage nach dem Anpfiff keinen Endstand. Tipp und
  App-Eintrag (`shadow_published`) blieben offen, weil nur `FT` abgerechnet wird (`FT_STATUSES`).
- Für verschobene, abgesagte oder abgebrochene Spiele gab es keine Regel.

## Regel

- Vor der täglichen Abrechnung prüft `step_void` den Anbieterstand für alle offenen Tipps, deren erfasster Anpfiff mehr
  als zwei Stunden zurückliegt. Das gilt für alle drei Bücher: Ledger mit Quote, `shadow_unpriced` und
  `shadow_published` (nur Tormärkte).
- Ein Tipp ist ungültig, wenn eine der beiden Bedingungen zutrifft:
  - Der Status ist `PST`, `CANC`, `ABD`, `AWD` oder `WO`: verschoben, abgesagt, abgebrochen, am grünen Tisch
    entschieden oder kampflos (`VOID_STATUSES`).
  - Der Anpfiff des Anbieters weicht mehr als zwölf Stunden vom erfassten Anpfiff ab (`VOID_KICKOFF_SHIFT`).

  Eine Verlegung um wenige Stunden am selben Tag zählt nicht. Die Zwölf-Stunden-Grenze ist eine Setzung dieser
  Umsetzung.
- Ungültige Tipps stehen in `shadow_void` mit Buch, Zeile, Grund, Anbieterstatus und beiden Anpfiffzeiten. Die Zeilen
  selbst bleiben unabgerechnet. Sie zählen nicht in Gewinn/Verlust, Rendite, Trefferquote oder der
  1000er-Prüfstufe. Ausgewiesen werden sie in `results.voided`, `unpriced_results.voided` und `actions.tips_voided`.
- Wird ein Spiel nach der Ungültigkeit doch gespielt, ändert das den Tipp nicht mehr. Auf dasselbe Spiel entsteht kein
  neuer Tipp, weil es einen Tipp je Spiel, Kohorte und Policy gibt.
- Die Auswahlregel ist unverändert, die Policy bleibt `shadow-model-first-v12`. Die Regel gilt rückwirkend für alle
  offenen Tipps, auch solche älterer Policies.
- Unterbrochene Spiele (`SUSP`, `INT`) bleiben offen, bis sie beendet oder abgebrochen sind. Spiele mit Verlängerung
  (`AET`, `PEN`) bleiben wie bisher offen; sie sind nicht Teil dieser Regel.
