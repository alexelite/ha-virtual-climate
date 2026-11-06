# Circuite gestionate extern și migrarea Homer

Virtual Climate păstrează planificarea zonelor, impulsurile, durata minimă a
cererii și pauza minimă. CC-HC poziționează vana, comandă pompa și solicită sursa.
Comanda `demand` exprimă necesarul; nu confirmă funcționarea arzătorului.

## Capabilități și responsabilități

Profilul se alege explicit în Setări Globale (`circuit_control`). Intrările vechi
folosesc `direct`, cu aceleași entități și temporizări, inclusiv răcirea existentă.
O pompă neconfigurată în profilul direct înseamnă circulație gestionată independent.
Nu există descoperire sau schimbare automată a profilului.

| Funcție | Cerințe |
| --- | --- |
| Comandă circuit extern | `external` și `circuit_demand_entity` |
| Comandă directă pompă | `direct` și `circulation_pump_entity` |
| Comandă directă sursă | `direct` și entitatea sursei modului respectiv |
| Răcire | Numai profil direct, conform configurației existente |
| Transmiterea țintei | `target_supply_temperature_entity`, disponibilă la scriere |
| Compensare climatică | Exterior valid, curbă și limite conform [ghidului de tur](supply-control.md) |
| Verificarea turului | Tur valid și context de funcționare; realizarea țintei HA necesită o țintă transmisă |
| Stare raportată circuit | `circuit_state_entity`, opțională |
| Menținerea zonelor | `external_post_run_seconds`, independent de starea raportată |

Matricea este expusă în diagnosticul global `capabilities`. Configurarea și
validarea folosesc aceleași chei explicite pentru responsabilități. În profilul
extern, validarea respinge orice entitate directă de pompă, sursă sau changeover.
Entitățile configurate care devin indisponibile produc diagnostic; nu activează
ieșiri alternative. Lipsa țintei nu blochează demand extern: controllerul poate
folosi ținta sa locală. Calculul curbei rămâne independent; probele asupra țintei
necesită transmiterea sa. Profilul direct păstrează verificarea existentă care
cere ieșire de țintă înainte de pornire cu compensare climatică.

În profilul extern, HA așteaptă maximul dintre întârzierea suplimentară configurată
și deschiderea confirmată/temporizată a zonelor, scrie ținta dacă există și
reverifică necesarul înainte de demand. Întârzierile directe ale pompei și sursei
nu participă la secvență. Durata minimă începe la activarea demand; după oprire,
pauza minimă se măsoară de la retragerea demand, nu de la închiderea zonelor.

La oprire HA retrage demand și păstrează căile valide de circulație pe durata HA.
Protecțiile zonelor au prioritate; o cale blocată nu este ținută deschisă. O cerere
nouă anulează închiderea programată și trece prin regulile normale, inclusiv pauza
minimă. Căile vechi rămân deschise până la expirarea menținerii cât timp sunt valide.
La descărcarea integrării se retrage demand și se așteaptă menținerea înainte de
închiderea zonelor; acest lucru poate prelungi descărcarea cu durata configurată.
O oprire bruscă a procesului HA nu poate executa această secvență.

## Parametrii inițiali Homer

Păstrați restul configurației exportate, zonele, planificarea ciclurilor, limitele,
filtrarea și pașii regulatorului. Modificați numai aceste chei din `global`:

```json
{
  "circuit_control": "external",
  "circuit_demand_entity": "switch.<entitatea_ufh_demand>",
  "circuit_state_entity": "sensor.<entitatea_ufh_circuit_state>",
  "circulation_pump_entity": null,
  "heating_source_entity": null,
  "cooling_source_entity": null,
  "changeover_entity": null,
  "external_start_delay_seconds": 0,
  "external_post_run_seconds": 120
}
```

Folosiți ID-urile reale din registrul HA după instalarea separată; nu presupuneți
slugurile generate. Ieșirea existentă de țintă se păstrează dacă este utilizată.
Temporizările CC-HC inițiale sunt: pregătire locală 30 s, pompă–sursă 0 s,
postcirculație 120 s. Pregătirea vanei și temporizarea de 30 s rulează în paralel;
pompa așteaptă ambele condiții, calibrarea și protecțiile. Reglajul începe după
30 s de circulație și reconstrucția ferestrei de măsurare valide.

**Sincronizarea este manuală:** menținerea HA trebuie să fie cel puțin egală cu
postcirculația CC-HC. Creșteți întâi menținerea HA dacă măriți postcirculația locală.
Starea `postrun`/`off` raportată nu scurtează temporizatorul HA.

## Trecerea efectivă, executată separat

1. Exportați configurația HA și păstrați firmware-ul anterior pentru revenire.
2. Opriți circuitul, așteptați încheierea circulației și confirmați lipsa cererii.
3. Eliminați comanda directă a pompei și sursei din Virtual Climate și din alte
   automatizări HA, menținând circuitul oprit.
4. Instalați separat firmware-ul Homer validat cu ESP-IDF. Demand pornește OFF.
   Confirmați calibrarea, timpii locali și entitățile raportate.
5. Configurați profilul extern, ID-ul demand și opțional starea/ținta. Verificați
   menținerea HA de 120 s înainte de activarea încălzirii.
6. Observați câteva cicluri. Sursa trebuie cerută după poziționare și pornirea
   pompei. Memoria poziției nu trebuie să crească în postcirculație. Înregistrați
   timpul până la banda temperaturii și timpul în bandă înainte de schimbarea
   duratelor de 7,5 minute cerere / 3 minute pauză.

La revenire, opriți mai întâi demand și așteptați postcirculația. Restabiliți
firmware-ul/configurația directă numai cu circuitul oprit și un singur responsabil
pentru fiecare ieșire. Module1 nu necesită modificări.

## Pierderea legăturii

Nu introducem expirare sau watchdog pentru demand. La pierderea API-ului,
controllerul păstrează ultima valoare demand și continuă secvența locală cu
protecțiile existente. După restart, demand este OFF. Dacă HA dispare în timp ce
demand era ON, cererea locală poate continua; autonomia manuală și o politică nouă
la deconectare rămân etape separate. Această modificare nu instalează firmware și
nu modifică configurația HA live.

Homer păstrează și `api.reboot_timeout` implicit din ESPHome: 15 minute fără
clienți API pot provoca un restart, după care demand și releele pornesc OFF.
O conexiune API rămasă activă poate împiedica acest restart; acesta nu este un
watchdog pentru prezența HA sau expirarea cererii. Nu modificăm acest parametru.
