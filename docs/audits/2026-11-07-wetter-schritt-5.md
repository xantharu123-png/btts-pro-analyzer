# Plan „bessere Prognosen“, Schritt 5: Wetter als Zahl geprüft und widerlegt

Stand 07.11.2026. Owner-Entscheid vom selben Tag: Die Wetter-Historie von Open-Meteo darf genutzt werden, weil die App
derzeit nur privat läuft. Für eine kommerzielle Nutzung bräuchte Open-Meteo einen bezahlten Plan.

Skripte, Hypothese und Ausgaben liegen unter `output/wetter-20261107/`. Am Code der App ändert sich nichts.

## Daten

- **Spiele:** Liga-Historien, die die App in `.shadow_cache` speichert (62 Ligen, 15.02.2025 bis 06.11.2026). Der
  Auszug wurde nur gelesen (`export_histories.py`). Es gab keine Abrufe bei API-Football.
- **Wetter:**
  - Geokodierung über Open-Meteo: 925 von 1059 Spielorten gefunden.
  - Stündliches ERA5-Archiv (Temperatur, Niederschlag, Wind in 10 m) für 741 Orte.
  - Nach den 741 Orten war das Gratis-Kontingent des Tages erschöpft, weil Open-Meteo lange Zeiträume als mehrere
    Abrufe zählt. Der Abruf wurde dort beendet.
- **Umfang:** 22 335 Ligaspiele, davon 10 654 mit Wetter zur Anstossstunde.

## Vorab festgelegt

`output/wetter-20261107/HYPOTHESE.md`, vor dem ersten Wetterabruf geschrieben.
- **Merkmale:**
  - Wind über 20 km/h je 10 km/h,
  - Niederschlag bis 5 mm/h,
  - Kälte unter 5 °C,
  - Hitze über 28 °C.
- **Modell:** Beide Torerwartungen werden mit exp(b·Merkmale) multipliziert, auf die Produktionsbasis Formstärke.
- **Hypothese:** bWind < 0 und bRegen < 0.
- **Abbruchregel:** Ist einer der beiden auf den Lerndaten (Spiele vor dem 01.07.2026) nicht negativ, gilt die
  Hypothese ohne weitere Prüfung als widerlegt.

## Ergebnis

4968 Lernspiele mit Wetter und Torerwartung (Poisson, Live-Rate als Offset):

| Merkmal | Koeffizient (SE) | Spiele mit Merkmal |
|---|---|---:|
| Wind | +0,008 (0,044) | 462 |
| Regen | +0,008 (0,018) | 972 |
| Kälte | −0,065 (0,058) | 581 |
| Hitze | +0,018 (0,109) | 166 |

- Wind und Regen zeigen keinen Effekt. Beide liegen nahe null und sind nicht negativ.
- **Die Hypothese ist widerlegt.** Wetter bleibt Hinweis und wird nicht als Zahl eingerechnet.
- Kälte zeigt eine leichte Tendenz zu weniger Toren, ist aber nicht belegt (SE 0,058). Für Kälte war vorab keine
  Richtung festgelegt, sie wird nicht nachträglich zur Hypothese gemacht.

## Grenzen

- Für 30 % der Orte fehlt das Wetter: keine Geokodierung oder das erschöpfte Tageskontingent.
- ERA5 ist ein Reanalyse-Raster von rund 30 km und keine Stadionmessung.
- Wenige Spiele haben starken Wind (462) oder Hitze (166).
