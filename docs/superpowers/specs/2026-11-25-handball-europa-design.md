# Handball-Pilot: fünf europäische Herrenligen

Der Bundesliga-Pilot wird auf die fünf bestplatzierten Länder der neuesten
[EHF-Klubwertung zur Champions-League-Platzvergabe](https://ehfcl.eurohandball.com/men/2025-26/news/en/202728-men-s-club-competitions-place-distribution-confirmed/)
erweitert: ASOBAL (ES), Bundesliga (DE), Herre Handbold Ligaen (DK), Starligue
(FR), NB I (HU). Das ist ein nachvollziehbares Auswahlkriterium, kein Beleg für
Rendite oder ein direktes Maß für die Tiefe der Landesligen.

Variante 1 wäre, alle europäischen Wettbewerbe samt Pokalen zu laden. Variante 2
erweitert den vorhandenen Pilot nur auf diese fünf Herrenligen. Gewählt wird 2:
je Liga eigene Spielhistorie, eigene Belege und eigener 1X2-Vergleich. Keine
Modelländerung, kein Wettbewerbstransfer, kein neuer Timer, kein öffentlicher Tipp.
Die Champions League ist nicht Teil der Trainingsdaten. Standard bleibt aus.

Die Liga-ID muss zusammen mit Land, Name, Typ und Saison im Anbieterkatalog
eindeutig bestätigt sein. Spiel- und Quotenidentität bleiben strikt an diese
Liga gebunden. Eine nicht verfügbare Liga verhindert die anderen nicht, sofern
der Anbieter insgesamt erreichbar ist. Die bisherigen deutschen Belege bleiben
lesbar; die neuen Ligen erhalten jeweils eigene kleine Saisondateien.

Maximal elf Abrufe je Zürcher Tag: ein Katalog, bis zu fünf Saisonabrufe und ein
1X2-Quotenabruf je Liga mit anstehendem Spiel. 9/min bleibt die Grenze ohne
belegte Tarif-Header; der bestätigte Handball-PRO-Tarif erlaubt den begrenzten
11er-Lauf. Nach einem Abbruch kein zweiter Versuch am selben Tag; bei
anbieterweiter Limit- oder Zugriffssperre stoppen. 75 Sekunden Laufzeitlimit,
kein neuer Timer und kein zusätzlicher Anbieter. `python -m handball_pilot`
liest alle fünf Ligen ohne Abruf.
Historische Endstände erlauben einen Rücktest ohne API-Kauf. Markt- oder ROI-
Nachweis erfordert echte zeitgebundene vollständige 1X2-Preise und exakte
Ergebnisse derselben Spiele; kein Ersatz durch heutige oder unzeitgestempelte
Quoten. Quellenlage, Testergebnis und Kaufentscheidung separat ausweisen.
