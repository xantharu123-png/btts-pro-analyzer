# Länderspiel-Modell reparieren: Ergebnis Kandidat 1

Stand 16.11.2026. Die Prüfung folgt der Vorab-Regel in `docs/audits/2026-11-16-laenderspiele-reparatur-vorab.md`
(Commit `234c34a`, gepusht vor der Rechnung).

## Ergebnis

**Die Kriterien sind nicht erfüllt.** Der Kandidat `dixon_coles_hl365` liefert für Länderspiele keine einzige
Vorhersage. Nach der Vorab-Regel gibt es deshalb keine Umstellung, und die Kleinstaaten-Sperre bleibt.

## Warum

`football_dixon_coles.fit_dixon_coles` ist für Vereinsligen gebaut:

- **Höchstens 64 Mannschaften** je Fit (`MAX_TEAMS`).
- **Jede Mannschaft braucht mindestens 4 Spiele** im Fenster (`MIN_TEAM_MATCHES`).

Der Länderspiel-Pool erfüllt beides nicht. Das zeigt das letzte Spiel im Pool, Spain gegen England, mit seinem
Fenster von 730 Tagen:

- 651 Spiele
- 109 Mannschaften
- 42 Mannschaften mit weniger als 4 Spielen; das sind meist Gegner aus Freundschaftsspielen ausserhalb Europas

Der Fit endet mit „history exceeds the supported team count“. Die Variante fällt dann geschlossen aus (`return
None`). Die Produktionsbasis lieferte auf denselben Spielen 41 124 Markt-Paare, der Kandidat 0.

## Was das heisst

- Die Prüfung sagt nichts darüber, ob ein multiplikatives Modell die Lücke schliessen würde. Es liess sich in dieser
  Form nur nicht rechnen.
- Ein Kandidat, der für Länderspiele angepasst ist, ist ein **neuer Kandidat**. Er braucht eine neue Vorab-Regel.
  Mögliche Anpassungen sind ein Fit nur über Mannschaften mit genügend Spielen und eine höhere Grenze der
  Mannschaftszahl. Beides wird erst nach Owner-Entscheid festgelegt.
- Die Sperre bleibt live (`fb38329`, seit 16.11.2026 09:15).

## Rechnung

Das Prüfskript lief nur lesend auf dem Server, mit demselben Pool von 1243 A-Länderspielen wie in der
Kleinstaaten-Prüfung. Produktionsbasis und Kandidat liefen kausal, Tag für Tag. Dazu kam eine Einzelprüfung des Fits
für das letzte Spiel im Pool.
