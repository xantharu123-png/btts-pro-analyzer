# Accountübergabe Domainumzug und BetBoy

Stand: 07.10.2026, Europe/Zurich. Aktueller Auftrag: To-do und Übergabe für einen anderen Account sichern. Der Domainumzug ist vorbereitet, aber weder bestellt noch durchgeführt. Die bisherigen App-Aufgaben bleiben offen und separat dokumentiert.

## Sofortiger Einstieg

1. Diese Übergabe und die lokale [Umzugs-To-do-Liste](<C:/Projekt/BetBoy/output/domain-migration-20261006/TODO_AKTUELL.md>) lesen.
2. Im bestehenden **internen Browser** die offene [netcup-Zusammenfassung](https://www.netcup.com/de/checkout/zusammenfassung) lesen. Keine neue Bestellung und keinen zweiten Warenkorb anlegen.
3. Vor Fortsetzung klären, ob der Nutzer inzwischen bestellt hat: Bestellbestätigung und tatsächliche Aktivierung prüfen. Solange diese fehlen, nichts als gekauft behandeln. Eine weitere kostenpflichtige Aktion braucht die konkreten Positionen und Nutzerfreigabe.

Der Nutzer erlaubt getrennte Anbieter, wenn sie deutlich günstiger sind. Bevorzugt vorbereitet: fünf .ch bei Dynadot, zwei .com und drei .online bei Spaceship, Websites und Mail bei netcup. Die jüngsten Fragen waren Kostenvergleiche, keine neue Zahlungsfreigabe. Keine Migration allein aus einem früheren „ja“ ableiten.

## Aktuell geprüfter Warenkorb

- Genau ein **Webhosting 1000 NUE**, Nürnberg; 12 Monate Mindestlaufzeit und Abrechnung.
- Erste Rechnung **EUR 29.32 inklusive 8,1 % Schweizer Steuer**, Einrichtung EUR 0. Der angezeigte Monatspreis EUR 2.44 ist gerundet; nicht EUR 29.28 als Rechnung behaupten.
- Rechnungsadresse wurde bereits vom Nutzer gespeichert. Nicht erneut danach fragen und keine privaten Kontaktdaten in Dokumente oder Git übernehmen.
- Bei der letzten rein lesenden UI-Prüfung waren AGB und Widerrufsbelehrung **beide angehakt**. Ältere Angaben „Häkchen ungesetzt“ sind überholt. Der Agent hat die Kästchen nicht geändert und keinen Kauf ausgeführt.
- Die Oberfläche steht weiterhin auf Zusammenfassung mit „Kostenpflichtig bestellen“; keine Bestellbestätigung, Zahlung oder Hostingaktivierung nachgewiesen.
- Die Domaintransfers und vier zusätzlichen externen Domain-Anbindungen sind **nicht** in EUR 29.32 enthalten. Vertrag verlängert sich ohne fristgerechte Kündigung; Checkout nennt spätestens 31 Tage vor Laufzeitende.

## Geprüfte Kosten und ihre Grenzen

Alle Varianten umfassen zehn Domains, zwei tatsächlich benötigte Websites und zehn unabhängige Postfächer. Bestehender BetBoy-VPS und andere externe Apphostings bleiben unverändert und kosten separat.

| Variante | Reguläre jährliche Kosten ungefähr |
|---|---:|
| Dynadot und Spaceship Domains plus netcup Hosting und Mail | CHF 124.09 |
| Infomaniak Domains plus netcup Hosting und Mail | CHF 199.81 |
| Vollständig Infomaniak, optimierte passende Endkonfiguration | CHF 396.20 |

Die bevorzugte Kombination ist unter den geprüften passenden Angeboten am günstigsten, keine weltweit absolute Billigstpreisgarantie. Gegenvergleich umfasste auch Hetzner, ALL-INKL, Manitu, OVH und weitere aktuelle Hostingtarife; reguläre Folgekosten statt bloßer Einstiegsaktionen vergleichen.

Bevorzugte Kombination:

- Fünf .ch: Dynadot jeweils USD 8.29 jährlich, zusammen USD 41.45. Transfer kostenlos, **ohne** zusätzliches Laufzeitjahr.
- Zwei .com: Spaceship jeweils USD 10.18 einschließlich ICANN, zusammen USD 20.36 jährlich.
- Drei .online: Spaceship jeweils USD 15.28 einschließlich ICANN, zusammen USD 45.84 jährlich. Nicht die USD-0.98-Neuregistrierungsaktion verwenden.
- netcup: EUR 29.32 jährlich. Eine externe Domain inklusive; vier weitere einmalig EUR 4.20 netto je Domain, zusammen rechnerisch **EUR 18.16** mit Schweizer Steuer. Keine laufenden Zusatzgebühren laut Dokumentation; Schweizer Zuschaltpreis im tatsächlichen Prozess prüfen.
- Neue Anbieter im ersten Umzugsjahr rechnerisch **CHF 177.12**: enthalten sind die vier Zuschaltungen und höhere .online-Transfers zu USD 28.66 je Domain. .online/.com-Transfer fügt ein Jahr hinzu; nicht Transfer und Verlängerung für dasselbe Jahr doppelt zählen.

CHF-Beträge sind Kalkulationen: EZB vom 06.10.2026, EUR 1 = CHF 0.9359 und USD 1.1269. Auf die USD-Preise wurde vorsorglich zusätzlich 8,1 % Steuer gerechnet; ihre tatsächliche Schweizer Erhebung ist nicht im Registrar-Checkout bestätigt. Bankgebühren, Wechselkursabweichungen, alte Rechnungen und Vertragsüberschneidungen kommen gegebenenfalls hinzu. Nur der Hostingbetrag EUR 29.32 ist ein konkret gelesener Checkoutbetrag.

Infomaniak optimiert: Domains CHF 172.37, PHP-Webhosting CHF 141.50, zwei separate Premium-Maildienste für BMM.ch/.com zusammen CHF 59.50, eine kSuite Standard mit einem Nutzer für die zwei Songtakt-Postfächer ca. CHF 22.83, kostenlose Starter-Adressen für Reden24 und Punktzukunft. Dafür müssen die Starter-Domains bei Infomaniak registriert sein; gegebenenfalls separate Organisation für Songtakt, da nur eine kSuite je Organisation. Die unabhängigen BMM-Postfächer dürfen nicht als Domainspiegel zusammengelegt werden. CHF 396.20 ist eine mögliche Endkonfiguration, **kein bestätigter Gesamtwarenkorb oder geprüfter sicherer Übergangsweg**. Das frühere CHF-171.25-Teilpaket nicht als vollständigen Umzug bezahlen; CHF 462.62 war die teurere Voll-Premium-Rechnung.

## Bestand der erhalten bleiben muss

Zehn Domains: reden.online, ichbinich.online, reden24.ch, keyhero.ch, songtakt.com, songtakt.online, songtakt.ch, bmmestudios.ch, bmmestudios.com, punktzukunft.ch.

| Maildomain | Getrennte Postfächer | Anzahl |
|---|---|---:|
| bmmestudios.ch | legal, privacy, support | 3 |
| bmmestudios.com | legal, privacy, support | 3 |
| punktzukunft.ch | kontakt | 1 |
| reden24.ch | info | 1 |
| songtakt.com | studio, support | 2 |

Die anderen fünf Domains haben laut geprüfter Verwaltung keine Postfächer. Quellkapazität je Postfach 2 GB, insgesamt maximal 20 GB; tatsächliche Nutzung, Regeln, Weiterleitungen, Kontakte und Kalender noch prüfen. netcup bietet separate 25 GB Web und 25 GB Mail, 100 IMAP-Konten, PHP und SSL. Nur die fünf aktiven Web-/Maildomains dort anbinden, nicht unnötig alle zehn.

Nur **reden24.ch** (ca. 6 MB) und **songtakt.com** (ca. 8,62 MB, statischer Export plus PHP-Endpunkt) sind als echte Quellwebsites bestätigt. Versteckte Dateien und Songtakt-Formular/SMTP müssen erhalten und getestet werden. Für BetBoy/Python/Node.js ist netcup 1000 nicht vorgesehen. KeyHero und Punktzukunft haben externe Appziele; ihre vorhandenen A-Einträge nicht pauschal ersetzen. Leere Standardwebroots sind keine Löschfreigabe.

## Reihenfolge und offene Aufgaben

1. Tatsächliche Zielaktivierung und konkrete Zusatzpreise prüfen; nötige Konten regulär vorbereiten. Nur interner Browser, neue Passwörter und Vertragsannahmen durch Nutzer.
2. Vollständige Dateien einschließlich versteckter Regeln sowie Mailumfang und erlaubten Importweg prüfen. Private Nachrichtenübertragung konkret mit Quelle und Ziel abstimmen; keine Secrets im Chat/Git.
3. Zielwebsites und zehn getrennte Postfächer bereitstellen. Dateien und Nachrichten regulär übernehmen; HTTPS, Formulare, Weiterleitungen, Versand und Empfang vor Umschaltung testen.
4. Unabhängiges DNS **vor** Registrartransfer vorbereiten. Cloudflare Free ist vorgeschlagen, aber noch kein Konto oder Zone angelegt. Kontoanlage und produktive DNS-/DNSSEC-Änderungen konkret autorisieren lassen. netcup hostet keine DNS-Zonen für externe Domains.
5. 117 vorhandene Nicht-SOA-Einträge über zehn Zonen abgleichen. Alte Root-NS/SOA nicht als neue Delegation importieren; providerseitige NS verwenden. Anwendungs-/Mailrecords zuerst erhalten, A/AAAA/CNAME zunächst DNS-only. Quell-Mailrecords später gezielt durch geprüfte Zielwerte ersetzen.
6. Bei keyhero.ch und reden.online echte Parent-DS, DNSKEY und TTL prüfen; gesetzte DNSSEC-Checkboxen reichen nicht. DS-Wechsel kontrolliert planen und Ablauf alter Caches beachten; keine pauschale Abschaltung.
7. Nach getesteter Zielbereitschaft DNS umstellen, Verbreitung prüfen und Mail-Differenz übernehmen. Swizzonic warnt vor Maildatenlöschung nach mindestens sieben Tagen fremdem MX: nicht als garantierten sicheren Parallelbetrieb behandeln.
8. **Erst danach Registrartransfers** durchführen. Swizzonic kann beim Transfer-out DNS und Hosting sofort löschen. Funktionierende unabhängige Nameserver beibehalten.
9. Abschließend Registrare, Laufzeiten, DNSSEC, HTTPS, Formulare und alle Mailkonten bestätigen. Swizzonic-Fristen, offene Rechnungen und abweichende .online-Termine klären; erst nach erfolgreicher Übernahme gezielt kündigen.

## Belege und separate Appaufgaben

Lokale Bestandsdokumente außerhalb des App-Repositories unter `C:\Projekt\BetBoy\output\domain-migration-20261006`: `TODO_AKTUELL.md`, `UMZUG_STATUS.md`, `ANGEBOT_ZUR_FREIGABE.md`, `MAIL_BESTAND.md`, `HOSTING_BESTAND.md`, `DNS_BESTAND.md`. Die Inventur stammt vom 06.10.; Preis- und Warenkorbprüfung vom 07.10. Screenshots `netcup-bestellbetrag-2932-20261007.jpg` und `netcup-warenkorb-20261007.jpg` enthalten nur die Angebotsansicht, keine Anschrift. Diese lokalen Belege werden nicht automatisch durch Git mitgenommen; bei einem Accountwechsel auf demselben PC bleiben sie am genannten Ort.

App-Einstieg: [zentrale To-do-Liste](../../TODO_AKTUELL.md), [PC-Übergabe](../../PC_WECHSEL_UEBERGABE.md), [Claude-Appübergabe](../../CLAUDE_UEBERGABE_2026-10-06.md). App-Gitroot ist `C:\Projekt\BetBoy\betboy-app`; frisch gelesener lokaler Stand vor dieser Dokumentation `c165d50`. Getrackte Dateien waren sauber, vorhandene ungetrackte Audit-/Browserdateien bleiben erhalten. Die älteren Appberichte sind historische Nachweise: aktuelle GitHub-/VPS-Revisionen und Gesundheit in dieser Übergabe **nicht** neu geprüft.

Weiter offen laut App-To-do: Kundenportalservice und Stripe-/SMTP-/Rechts-/Länder-/E2E-Anbindung, belegte Monatsbilanz, native Stores sowie Modell-/Scanner-Restarbeiten. Domainvergleich beweist weder fertigen Verkauf noch bessere Wettqualität. Nicht die freigegebene Landingpage erneut planen oder ungefragt Scans, Backups, Bereinigungen und Deployments starten.

In diesem Übergabeschritt nur Dokumentation. Keine Bestellung, Zahlung, Datenkopie, Domainübertragung, DNS-Änderung, Kündigung, Produktionscodeänderung, neue Sicherung oder explizites VPS-Deployment.

## Primärquellen

- [netcup Paket](https://www.netcup.com/de/hosting/webhosting/webhosting-1000-nue) und [externe Domains](https://www.netcup.com/de/helpcenter/dokumentation/webhosting/externe-domains).
- [Dynadot .ch](https://www.dynadot.com/domain/ch), [Spaceship Preise](https://www.spaceship.com/domains/), [Transferbedingungen](https://www.spaceship.com/domains/transfer/).
- [Infomaniak PHP-Hosting](https://www.infomaniak.com/en/hosting/prices-and-characteristics), [kSuite](https://www.infomaniak.com/en/ksuite/ksuite-pro/prices), [Mailtarife](https://www.infomaniak.com/en/ksuite/service-mail/prices), [Starter](https://www.infomaniak.com/en/support/faq/2002/order-a-starter-product-mail-service-web-hosting), [Domainspiegel](https://www.infomaniak.com/en/support/faq/2097/add-an-additional-domain-name-to-the-mail-service).
- Infomaniak Verlängerungen: [.ch](https://www.infomaniak.com/en/domains/prices/ch), [.com](https://www.infomaniak.com/en/domains/prices/com), [.online](https://www.infomaniak.com/en/domains/prices/online).
- [EZB](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html), [Swizzonic Transfer-out](https://swizzonic.support/transfer-und-interne-uebertragung/).
