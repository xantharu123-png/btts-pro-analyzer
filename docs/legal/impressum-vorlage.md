# Vorlage: Anbieterinformationen / Impressum (BetBoy)

**Status: Vorlage mit Platzhaltern. Kein Rechtsrat.** Alle Felder in eckigen
Klammern `[PLATZHALTER …]` muss der Owner selbst ausfüllen. Der fertige Text ist
vor der Veröffentlichung von einer Anwältin oder einem Anwalt mit Schweizer
Zulassung zu prüfen. Nichts in dieser Datei ist eine Aussage über die
tatsächliche Betreiberin oder den tatsächlichen Betreiber von BetBoy; im Code und
in der App stehen keine Betreiberdaten.

Die veröffentlichte Seite wird über `BETBOY_LEGAL_URL` (App und Portal) verlinkt.
Solange die Variable fehlt, zeigt die App ehrlich «Anbieterinformationen und
Datenschutz: noch nicht veröffentlicht».

---

## Anbieterinformationen

**Anbieterin / Anbieter dieses Angebots**

[PLATZHALTER Firma oder Name, Rechtsform (z. B. Einzelunternehmen, GmbH, AG)]
[PLATZHALTER Strasse und Nummer]
[PLATZHALTER PLZ Ort]
Schweiz

**Kontakt**

E-Mail: [PLATZHALTER Kontaktadresse, die tatsächlich gelesen wird]
Telefon: [PLATZHALTER, optional]

**Vertretungsberechtigte Person(en)**

[PLATZHALTER Vorname Name, Funktion]

**Handelsregister**

[PLATZHALTER Handelsregisteramt des Kantons, Firmennummer (CHE-…)] – oder:
«Kein Handelsregistereintrag» [PLATZHALTER prüfen, ob eine Eintragungspflicht
besteht]

**Mehrwertsteuer**

[PLATZHALTER UID mit MWST-Zusatz (CHE-…-MWST)] – oder: «Nicht
mehrwertsteuerpflichtig» [PLATZHALTER prüfen]

**Verantwortlich für den Inhalt**

[PLATZHALTER Vorname Name, Adresse wie oben]

## Was BetBoy ist und was nicht

BetBoy ist [PLATZHALTER kurze, zutreffende Beschreibung der Dienstleistung, z. B.
«ein Informations- und Analysewerkzeug für Sportstatistik»]. BetBoy
[PLATZHALTER: nimmt keine Wetten an / vermittelt keine Wetten / betreibt keine
Geldspiele – nur eintragen, was tatsächlich zutrifft und juristisch bestätigt
ist]. Modellwerte sind Schätzungen; es gibt keine Gewinngarantie. Wetten
können zum Verlust des Einsatzes führen. Zugelassen ab 18 Jahren.

## Hilfe bei Spielsucht

- SOS Spielsucht, Beratungstelefon 0800 040 080 (kostenlos, anonym),
  <https://www.sos-spielsucht.ch/>
- Sucht Schweiz, <https://www.suchtschweiz.ch/>

## Haftung und Urheberrecht

[PLATZHALTER Haftungsklausel – juristisch prüfen lassen; keine pauschalen
Haftungsausschlüsse übernehmen, die nach Schweizer Recht unwirksam sind.]

[PLATZHALTER Urheberrechtshinweis zu Texten, Grafiken und Modellen; Quellen der
verwendeten Sportdaten und deren Lizenzbedingungen nennen, sofern die Lizenz
das verlangt.]

## Streitbeilegung

[PLATZHALTER Hinweis auf Gerichtsstand / anwendbares Recht – gehört in der Regel
in die AGB, hier nur falls gewünscht.]

Stand: [PLATZHALTER Datum]

---

## Checkliste für den Owner (vor Veröffentlichung)

Eintragen:

1. Vollständige Identität und ladungsfähige Postadresse der Anbieterin / des
   Anbieters (Art. 3 Abs. 1 lit. s UWG verlangt im elektronischen
   Geschäftsverkehr klare Angaben zur Identität und Kontaktadresse – ob und wie
   das auf BetBoy zutrifft, juristisch prüfen lassen).
2. Rechtsform, Handelsregister- und UID-/MWST-Angaben, sofern vorhanden.
3. Eine Kontaktadresse, die tatsächlich betreut wird.
4. Zutreffende Beschreibung der Leistung (Informationsdienst, kein Wettanbieter –
   nur wenn das stimmt).
5. Datum des Standes.

Juristisch prüfen lassen:

- Ob das Angebot unter das Bundesgesetz über Geldspiele (BGS) oder kantonale
  Vorschriften fällt oder eine Bewilligung bzw. Zusammenarbeit mit einem
  konzessionierten Anbieter voraussetzt; ob Werbe- und Jugendschutzregeln für
  Wett-Werbung gelten.
- Haftungsklausel und Urheberrechtshinweis.
- Ob für Kundinnen und Kunden in der EU oder im übrigen Ausland weitere
  Informationspflichten bestehen (z. B. DSGVO, Verbraucherrecht am Wohnsitz).
- Konsistenz mit den AGB (`BETBOY_TERMS_URL`) und der Datenschutzerklärung
  (`BETBOY_PRIVACY_URL`): dieselbe Anbieterin, dieselbe Adresse, dasselbe
  Datum.

Technisch nach der Veröffentlichung:

- `BETBOY_LEGAL_URL`, `BETBOY_PRIVACY_URL`, `BETBOY_TERMS_URL` in
  `/etc/betboy/betboy.env` (Streamlit-App) und `/etc/betboy/portal.env`
  (Portal, dort zusätzlich `BETBOY_LEGAL_READY=1`) auf die veröffentlichten
  https-Adressen setzen; nur mit allen drei Werten zeigt die App die Links.
