# HA Noot Leerlingenvervoer

> **Versie 2026.11.12.01** — Zie [CHANGELOG](CHANGELOG.md)

Een Home Assistant custom integratie die het ritschema en de live tracking van
[Noot Vervoer](https://portal.noot.nl) uitleest en omzet in sensoren, binaire
sensoren en een device tracker. Alles draait via een config entry — geen YAML,
geen losse scripts, geen template helpers meer nodig.

> **Unofficial.** Dit project is niet gelieerd aan, goedgekeurd door of
> ondersteund door Noot Vervoer.
>
> De integratie scraapt hetzelfde webportaal als een browser, omdat het portaal
> geen publieke API heeft. Het portaal kan op elk moment wijzigen, wat deze
> integratie kan breken. Gebruik het alleen voor je eigen account en controleer
> de gebruiksvoorwaarden van het portaal voordat je erop vertrouwt.
>
> Deze integratie is (deels) gegenereerd met AI, maar de werking is door de
> maker persoonlijk getest en wordt dagelijks gebruikt in een echte
> Home Assistant-installatie.

## Waarom deze integratie?

Ik heb deze integratie gemaakt omdat ik wilde weten wanneer mijn kind in de
(bus)taxi stapt, hoe lang het erin zit, en waar de bus is. Ook als het schema
onverwacht verandert (bijv. een andere ophaaltijd omdat de schooltijden wijzigen),
wil ik automatisch een melding krijgen zodat we op tijd klaar staan.

### Wat kun je ermee doen?

- **"Ingestapt"** — een automatisering stuurt een melding
  (Telegram, spraak, etc.) zodra de middagrit begint, met de chauffeur en
  verwachte uitstaptijd.
- **"Taxi komt eraan"** — een spraakmelding in huis (`noot_taxi_busje_komt_thuis_spraak`)
  waarschuwt wanneer de bus binnen de ingestelde afstand van huis is.
- **"Ochtendtaxi over 10 minuten"** — een melding op de wall-tablet als de bus
  er bijna is, zodat het kind zich klaarmaakt.
- **"Waar is de bus?"** — een device tracker toont de positie op de kaart,
  ook als het portaal even geen GPS-coördinaten geeft (valt dan terug op
  school of thuis).
- **"Hoeveel ritten vandaag?"** — een sensor telt het aantal ritten en toont
  de chauffeur, ophaaltijd, afzettijd en het adres per rit.

## Sensoren

*Alle entity-ID's gebruiken `ha_noot_leerlingenvervoer` als domein. In de
Home Assistant UI worden ze weergegeven met een voorvoegsel voor de area
(bijv. `familie_ha_noot_leerlingenvervoer_*`).*

| Sensor | Wat zie je? | Voorbeeldwaarde |
| --- | --- | --- |
| `rit_status_nu` | Status van de rit die vandaag al gestart is | `Aanwezig` |
| `volgende_ochtendrit` | Ophaaltijd volgende ochtendrit | `08:88` |
| `volgende_middagrit` | Ophaaltijd volgende middagrit | `14:30` |
| `eerstvolgende_rit` | De rit die het eerst start (ochtend óf middag) | `14:30` |
| `ritten_vandaag` | Aantal ritten vandaag | `2` |
| `chauffeur` | Chauffeur van de eerstvolgende rit | `J. de Vries` |
| `afzettijd` | Verwachtte uitstapmoment | `15:00` |
| `datum` | Datum van de eerstvolgende rit | `01-01-26` |
| `dag` | Dag van de week | `VRIJDAG` |
| `status` | Status van de eerstvolgende rit | `Aanwezig` |
| `minuten_tot_rit` | Minuten tot de eerstvolgende ophaaltijd | `114` |
| `live_tracking` | Live status van de actieve tracking | `Gepland` / `Onderweg` |
| `eta` | ETA zoals het portaal die berekent | `14:30` |
| `<dag>_<ochtend/middag>` | Per dagdeel: ophaaltijd | `08:00` / `14:30` |

**Attributen** op de ritsensoren: `datum`, `dag`, `ophaaladres`, `school`,
`chauffeur`, `ritnummer`, `status`, `afzettijd`, `minuten_tot_rit`.

### Binaire sensoren

| Sensor | Wat zie je? |
| --- | --- |
| `in_bus_middagrit` | `Aan` zolang de middagrit onderweg is |
| `ochtendrit_binnenkort` | `Aan` in het venster van 10 min voor ophalen tot 5 min erna |
| `bijna_thuis` | `Aan` als de bus binnen de ingestelde afstand van huis is (standaard 1,2 km) |
| `aanwezig_gemeld` | `Aan` als het kind als aanwezig is gemarkeerd in het portaal |

### Device tracker

| Tracker | Wat zie je? |
| --- | --- |
| `locatie` | GPS-positie van de bus op de kaart. Valt terug naar school of thuis als het portaal geen GPS geeft. |

## Installatie

### Via Marketplace (aanbevolen)

Klik op onderstaande knop om de integratie direct aan je Home Assistant toe te voegen:

[![Open je Home Assistant en voeg de repository toe aan de Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=djremco&repository=ha-noot-leerlingenvervoer&category=integration)

*Werkt de knop niet? Voeg handmatig `djremco/ha-noot-leerlingenvervoer` toe via **Marketplace → Custom repository** met categorie **Integration**.*

### Handmatig

1. Download de map `custom_components/ha_noot_leerlingenvervoer` naar
   `config/custom_components/ha_noot_leerlingenvervoer`.
2. Herstart Home Assistant.

## Configuratie

1. Ga naar **Instellingen → Apparaten & services → Integratie toevoegen**.
2. Zoek naar **HA Noot Leerlingenvervoer**.
3. Vul je **e-mailadres** en **wachtwoord** in (dezelfde als op `portal.noot.nl`).
4. Laat het **klantnummer** leeg — het wordt automatisch herkend.
5. Pas op het volgende scherm de intervallen en optionele locaties naar wens aan.

### Opties (later aanpasbaar via Configureren)

| Optie | Standaard | Wat doet het? |
| --- | --- | --- |
| Verversingsinterval schema | 3600 s | Hoe vaak het ritschema wordt opgehaald |
| Verversingsinterval live tracking | 60 s | Hoe vaak de live positie wordt opgehaald |
| Afstand voor 'bijna thuis' | 1,2 km | Straal voor de *Bijna Thuis* sensor |
| Thuisbreedtegraad / -lengtegraad | `zone.home` | Voor afstandsberekening en kaartfallback |
| Schoolbreedtegraad / -lengtegraad | leeg | Kaartfallback als het portaal geen GPS geeft |

Het portaal werkt het schema maar een paar keer per uur bij; een korter interval
geeft niet per se nieuwere data en kan een rate limit triggeren.

## Hoe het werkt

Twee scrapers draaien binnen de integratie:

- **Schema** (`taxsys`): logt in, leest de rit-tabel en bepaalt de volgende
  ochtendrit, de volgende middagrit en de volledige lijst.
- **Tracking** (`gvpapp`): logt in, bepaalt welke rit nu relevant is en leest
  de live gegevens uit (chauffeur, GPS, status, in-/uitstaptijden).

Alle tijden zijn in de tijdzone van Home Assistant.

## Privacy

Deze repository bevat geen persoonlijke gegevens. Inloggegevens, adressen,
klantnummers en coördinaten worden tijdens de installatie ingevuld of tijdens
gebruik uit het portaal gelezen. Houd er rekening mee dat sensor-attributen
wel de ophaal- en afzetadressen bevatten; wees voorzichtig met screenshots.

## Versiebeheer

Zie [CHANGELOG](CHANGELOG.md) voor alle wijzigingen per versie.

Versies volgen het formaat `YYYY-MM-DD-NN`.

## Donatie

Vind je deze integratie nuttig? Een kopje koffie wordt gewaardeerd:

[![Donate with PayPal](https://www.paypalobjects.com/en_US/i/btn/btn_donate_SM.gif)](https://www.paypal.com/donate/?business=tszaandam@gmail.com&no_recurring=0&item_name=HA+Noot+Leerlingenvervoer&currency_code=EUR)

## Troubleshooting

| Fout | Oorzaak & oplossing |
| --- | --- |
| `cannot_connect` tijdens installatie | Portaal niet bereikbaar. Check je internet en probeer opnieuw. |
| `invalid_auth` tijdens installatie | Verkeerd e-mailadres of wachtwoord. Test ze eerst in een browser. |
| Entiteiten worden `unavailable` | De coordinator kon geen data ophalen; de volgende poll herstelt het. |
| `Geen rit` bij sensoren | Normaal in het weekend en tijdens schoolvakanties. |

## Licentie

MIT. Zie [LICENSE](LICENSE).

---

*Gemaakt met 🤖 en ☕, getest in de praktijk.*
