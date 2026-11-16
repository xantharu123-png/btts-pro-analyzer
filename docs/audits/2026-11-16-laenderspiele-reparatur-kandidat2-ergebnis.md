# Länderspiel-Modell reparieren: Ergebnis Kandidat 2

Stand 16.11.2026. Die Prüfung folgt der Vorab-Regel in
`docs/audits/2026-11-16-laenderspiele-reparatur-kandidat2-vorab.md` (Commit `a788eed`, gepusht vor der Rechnung).

## Ergebnis

**Nicht erfüllt, Kriterium K0.** Kandidat 2 liefert in Zeitraum A für 0 von 197 Kleinstaaten-Spielen eine Vorhersage
(verlangt sind mindestens 90 %). Nach der Vorab-Regel gibt es keine Umstellung, die Sperre bleibt.

## Warum

Die Engine schliesst Dixon-Coles bei Länderspielen bewusst aus. `challenge_engine._fixture_model`, Zeilen 1332 bis
1344:

- Länderspiele (Nations League oder `challenge_senior_national_team`) laufen über ein eigenes Modell,
  `_senior_national_fixture_model`.
- Jede andere Basis als `legacy` und Formstärke endet sofort mit „keine Vorhersage“. Die Begründung im Code lautet:
  der Vereinsliga-Fit hat keine Grundlage für A-Länderspiele.

Der Teamfilter von Kandidat 2 kam deshalb gar nicht zum Zug. Die Rechnung lief für den Kandidaten in 0 Sekunden
durch. Auch Kandidat 1 scheiterte zuerst an dieser Stelle. Die Mannschaftsgrenze (109 gegen 64) wäre die zweite
Hürde gewesen.

## Was das heisst

- Weder Kandidat 1 noch Kandidat 2 hat Ergebnisdaten erzeugt. Es gibt also keine Auswertung, die einen späteren
  Kandidaten beeinflussen könnte.
- Eine Reparatur muss im Länderspiel-Modell selbst ansetzen (`_senior_national_fixture_model`) oder es bewusst
  ersetzen. Beides ist ein neuer Kandidat mit eigener Vorab-Regel und Owner-Entscheid.
- Die Kleinstaaten-Sperre bleibt live (`fb38329`).
