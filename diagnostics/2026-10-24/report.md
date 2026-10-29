# Analiza Virtual Climate — 24 octombrie 2026

Toate orele sunt în Europe/Bucharest. Analiză prin MCP `homerha`, istoricul HA și sursa locală, revizia `92d35cc`. Nu am schimbat configurația HA, actuatoarele sau codul integrării. Fișierele din acest director sunt artefacte de diagnostic.

## Concluzie

Există trei defecte confirmate care explică simptomele: temporizatorul de oprire este respins de HA, trecerea între cicluri trimite OFF și ON imediat, iar timpul ultimei opriri resetează artificial cererea zonelor deja repornite. Succesiunea `stop → start → running` descrie ciclul coordonatorului; nu dovedește o oprire și o repornire a sursei de încălzire.

## Evenimentul de la 06:05:52

| Ora | Observație HA |
| --- | --- |
| 06:05:52.806 | Coordonator `stop`; cererea agregată devine 0 |
| 06:05:52.820 | Coordonator `start`; cererea agregată revine la 0,27 |
| 06:05:52.969474 | `switch.ufh_noah_bedroom` devine `off` |
| 06:05:53.407098 | Același switch devine `on`, după **0,437624 s** |
| 06:05:53.806 | Coordonator `running`, cerere 0 și 10 zone blocate |
| 06:09:52.981 | Cererea agregată revine la 0,26, după expirarea blocajului de aproximativ 240 s |

La același moment, `switch.ufh_hallway` și `switch.ufh_master_bathroom` au avut și ele impulsuri OFF/ON de aproximativ 0,44 s. Master Bedroom și Eva au alte exemple similare în aceeași noapte. Noah avea aerul la aproximativ 21,77 °C și ținta la 22 °C: cererea termică nu dispăruse.

Controlerul `Cc-Ufh2`, dispozitivul `205a805936453c930f94a11a4d35c6c4`, a rămas conectat. În fereastra 05:45–06:25 uptime-ul a crescut de la aproximativ 2.651.628 la 2.654.028 s, fără resetare. Evenimentul analizat se corelează cu coordonatorul, fără indicii de restart al ESPHome în acea fereastră.

## 1. Opririle programate ale zonelor eșuează

În `custom_components/virtual_climate/zone_manager.py:738`, `async_call_later` primește un lambda sincron fără `@callback`. HA îl execută în executor; acesta încearcă să apeleze `hass.async_create_task` din alt thread. Logul real conține `RuntimeError` pentru exact acel fișier, linie și apel. Intrarea de avertizare asociată are **262 de apariții**, prima la 00:00:32 și ultima la 07:38:20 în captura citită. Există și avertizări că `ZoneManager._turn_off_zone` nu a fost așteptată.

Efect: oprirea de la finalul duratei individuale poate să nu ajungă la actuator. Pentru Noah, diagnosticul indica o durată programată de **240 s**, însă istoricul switch-ului îl arată `on` de la începutul ferestrei 00:00 până la impulsul de la 06:05:52, apoi din nou până la 07:42:39. Ora 00:00 este o captură a stării de la începutul ferestrei, nu ora reală a pornirii.

`running_zones` se calculează din intervalele programate (`_zone_slot_is_running`), nu din confirmările switch-urilor. De aceea poate raporta 0 în timp ce switch-urile sunt încă `on`. Nici `hvac_action` nu confirmă actuatorul: în `climate.py:131` este dedus din diferența dintre țintă și temperatura aerului.

Comportamentul executorului și cerința `@callback` sunt descrise în [documentația oficială HA](https://contributors.home-assistant.io/core/internals/thread-safety/). Același tipar de lambda există și pentru pornirea întârziată, la linia 707; configurația observată folosește `simultaneous`, astfel încât calea de oprire este cea demonstrată în logurile acestei instalații.

## 2. Trecerea între cicluri produce impulsuri OFF/ON

În `zone_manager.py:194–213`, planul pentru ciclul următor este calculat înaintea opririi ciclului curent. `_stop_cycle()` trimite OFF tuturor zonelor și scrie timpul ultimei opriri pentru fiecare. Apoi `_start_cycle(plan)` folosește planul deja calculat și trimite imediat ON zonelor selectate.

Limita minimă de repaus este verificată în planificare, înainte ca noua oprire să fie înregistrată. Astfel, noua pornire o ocolește. Pentru Noah sunt configurate `zone_min_off_s=180` și `close_s=60`; planificatorul intenționează un interval de 240 s. Intervalul observat de 0,438 s încalcă inclusiv minimumul de 180 s.

Impulsul electric atât de scurt nu dovedește că vana termică a făcut o închidere mecanică completă. Dovedește însă comutarea switch-ului și defectul de secvențiere.

## 3. Cererea agregată este anulată artificial

Sunt două mecanisme directe:

- `_stop_cycle()` publică explicit cerere zero, chiar când există un plan pentru următorul ciclu.
- După repornire, `_plan_cycle()` verifică `last_off + 180 + 60` fără să excludă zonele care sunt deja pornite. Le marchează `zone_min_off` și le setează fracția cerută la zero.

În plus, `_stop_cycle()` actualizează timpul ultimei opriri chiar și pentru zonele care erau deja oprite. Aceasta explică cele **10 zone blocate** imediat după pornirea ciclului, concomitent cu **6 zone raportate în execuție** la 06:05:53.

În fereastra 05:45–06:25, senzorul agregat este zero aproximativ **982 s din 2400 s — 41% din timp**. Aceste zerouri nu pot fi interpretate drept lipsă reală de necesar termic. Senzorul mediază fracțiile zonelor eligibile din plan, iar eligibilitatea este afectată de blocajul descris.

Senzorul `plant_state` a rămas `running`, `plant_mode` a rămas `HEAT`, iar `system_mode` a rămas `HEAT` în fereastra 00:00–07:45. Acestea sunt stări raportate de integrare; nu am verificat separat releul fizic al sursei sau debitul instalației.

## Alte constatări

- Senzorii de temperatură și umiditate pentru Living room și Entry hallway sunt `unavailable` de la 23 octombrie, aproximativ 23:51:44. Aceste zone nu furnizează cerere calculabilă din temperatura aerului.
- Senzorul de pardoseală Noah raportează 19,68 °C și are `last_reported` la 23 octombrie, 23:51:44. Prospețimea acestei măsurători trebuie verificată separat; valoarea constantă singură nu dovedește un senzor defect.
- În sursă, durata ciclului este recalculată la fiecare tick și suprascrie durata ciclului aflat deja în curs. Temporizatoarele rămân cele stabilite la început; aceasta permite nealinieri între durata ciclului și sloturile existente.
- Callback-urile temporizatoarelor nu au mânere de anulare păstrate și nici identificator de generație a ciclului. După corectarea execuției lor trebuie prevenită executarea unui temporizator vechi într-un ciclu nou. Acest ultim risc este constatat în sursă, nu demonstrat ca eveniment separat în istoricul citit.

## Reproducere și corecții recomandate

`python3 diagnostics/2026-10-24/reproduce.py` execută clasa reală `ZoneManager`, cu o singură zonă, intrări constante, ceas controlat și servicii/temporizatoare HA simulate. Nu comunică cu instalația. Rezultat: **3 defecte reproduse**, exit code 1, intenționat pentru versiunea curentă:

```text
FAIL: Scheduled OFF fails: hass.async_create_task called outside the event loop
FAIL: Cycle rollover issues OFF then ON with no minimum off wait
FAIL: Positive unchanged heat demand becomes 0 while the zone is running; reason=['zone_min_off']
```

Ordinea recomandată pentru remediere:

1. Repararea callback-urilor temporizatoarelor, cu anulare și protecție contra callback-urilor din cicluri vechi.
2. Refacerea tranziției între cicluri: continuitate când sloturile se ating legitim; respectarea timpului minim de repaus după orice oprire efectivă. Timpul ultimei opriri trebuie legat de tranziția reală, fără a fi resetat la OFF-uri redundante.
3. Separarea necesarului termic de eligibilitatea la pornire și de sloturile active; aplicarea blocajului de repornire doar zonelor oprite.
4. Păstrarea duratei unui ciclu până la terminarea lui și alinierea diagnosticului cu starea confirmată a actuatoarelor.
5. Verificarea senzorilor indisponibili și a prospețimii măsurătorilor de pardoseală.

Artefactele brute selectate sunt în `evidence.json`. Nu am făcut o comparație integrală prin hash cu sursa de pe HA; concordanța este susținută de același fișier, număr de linie și fragment de cod în erorile live, plus reproducerea simptomelor din istoric.

## Actualizare: ștergerea senzorului de pardoseală din formular

Utilizatorul a confirmat că senzorul Noah nu mai este valabil și că a golit câmpul în configurarea zonei. O citire ulterioară prin MCP arată că `options.zones[id=noah_bedroom].sensor_floor` conține încă `sensor.noah_bedrom_th_123_2`.

Reproducerea locală identifică un defect suplimentar în `config_flow.py:106`: `_optional_entity_field()` folosește `vol.Optional(key, default=default)` când există deja o asociere. Când un selector opțional este golit și cheia lipsește din payload, validarea schemei o reintroduce cu valoarea veche înainte de `async_step_zone_edit()`. Salvarea primește astfel vechiul senzor și îl persistă din nou. Aceeași funcție este folosită pentru `window_switch`.

Comanda de reproducere, într-un mediu temporar cu `voluptuous==0.15.2`:

```text
/tmp/ha-virtual-climate-diag-venv/bin/python diagnostics/2026-10-24/reproduce_optional_clear.py
```

Rezultat pe codul curent, exit 1 intenționat:

```text
CURRENT sensor_floor: submitted=<omitted>, after_schema='sensor.noah_bedrom_th_123_2', after_save_and_reload='sensor.noah_bedrom_th_123_2'
CURRENT window_switch: submitted=<omitted>, after_schema='binary_sensor.noah_window', after_save_and_reload='binary_sensor.noah_window'
CONTROL: save/merge without schema default injection preserves sensor_floor=None
CANDIDATE: suggested_value preserves clear, retain, and replace for both optional entity fields
```

Harness-ul execută funcțiile reale de construire a formularului, salvare și combinare a configurației. Validarea Voluptuous este reală; wrapper-ele HA și validatorii selectorilor sunt simulate. Nu a fost capturat payload-ul sesiunii originale de editare din browser.

Soluție verificată într-o probă exclusiv în memorie: marker opțional fără default injectabil, cu valoarea existentă în `description={"suggested_value": ...}`. Câmpul șters rămâne absent la validare, iar logica existentă de salvare scrie explicit `None`; combinarea cu `entry.data` păstrează această ștergere. Au fost verificate ștergerea, păstrarea și înlocuirea ambelor asocieri opționale.

Corecția de producție trebuie inclusă în remediere, cu un test de regresie prin formular → validare → salvare → reîncărcare și verificare UI după instalare. Asocierea învechită din Noah va fi golită explicit după corectare. Nu am modificat codul integrării sau configurația live în această investigație.

Referință: [HA Core 2026.10.3 — validarea formularului și suggested_value](https://github.com/home-assistant/core/blob/2026.10.3/homeassistant/data_entry_flow.py).

## Implementare locală după aprobarea utilizatorului

Corecțiile sunt implementate în sursa repository-ului. Comutările de zonă sunt reconciliate de tick-ul central de o secundă, fără temporizatoare individuale. Durata ciclului rămâne fixă, tranzițiile confirmate ale switch-urilor controlează repausul minim, iar cererea termică rămâne separată de eligibilitatea la pornire. Intervalele continue trec între cicluri fără OFF/ON administrativ.

Pornirea sursei așteaptă confirmarea actuatorului și timpul de deschidere. Oprirea normală păstrează căile eligibile deja deschise până la sfârșitul minimumului de funcționare și al postcirculației; pierderea ultimei căi valide oprește imediat sursa și pompa. Modurile HEAT/COOL trec prin oprire înaintea schimbării. Ieșirile găsite pornite după restart sunt aduse prin secvența de oprire înaintea unei sesiuni noi. Aceste reguli pot prelungi deschiderea unei zone peste slotul normal în timpul opririi sursei.

Diagnosticele diferențiază intervalul programat, comanda dorită și starea raportată a switch-ului. Starea electrică și timpul de deschidere reprezintă o estimare a disponibilității căii, fără măsurarea poziției vanei sau a debitului.

Câmpurile opționale `sensor_floor` și `window_switch` folosesc valori sugerate, iar ștergerea se persistă explicit ca `None`. Handler-ul serviciului de actualizare a zonelor rulează acum ca funcție async și publică evenimente pe event loop.

Validare: 33 de teste de regresie trecute, inclusiv două ore simulate de cerere variabilă, plus reluarea reproducerilor inițiale fără defectele originale. Testele execută logica de producție cu I/O HA simulat și Voluptuous real. Compilarea Python și verificarea whitespace-ului au trecut.

Codul nou nu a fost încă instalat în HA și configurația live Noah nu a fost schimbată. Activarea necesită sincronizarea fișierelor și restart HA Core, apoi golirea asocierii vechi din opțiunile Noah și verificare live a logurilor și feedback-ului ESPHome. Aceste observații de implementare nu schimbă dovezile istorice din secțiunile anterioare.

## Instalare locală pe homerha — 24 octombrie 2026

Scriptul `dev/sync.sh`, împreună cu `dev/deploy.py`, a fost completat cu împachetare
imutabilă, teste, backup al codului și al configurației acestei integrări,
încărcare separată, verificare SHA-256 și importuri în containerul HA real,
verificarea configurației, restart Core și confirmarea noului proces/API.
La eșec după activare readuce codul anterior; nu rescrie `.storage`.
Cele 46 de teste (33 de control și 13 de instalare/recuperare) au trecut.

Simularea și instalarea efectivă au fost executate prin script, pe aliasul SSH `ha`:

- Versiunea anterioară: `0.1.0`; versiunea instalată: `0.1.1b1`.
- SHA-256 al manifestului de fișiere: `89d1660390c256704376a5e7d93ab5afcebb37e8fa182f2a21c9592010547be5`.
- Backup: `/config/virtual_climate_backups/20261024T060932Z-74273/`.
- Rezultat script: `installed`, `restart_confirmed: true`.
- Primele stări din noul proces: aproximativ 09:11:08, Europe/Bucharest.
- Intrarea `01K6R41QXYWXR97ATA8PGX4EHX` este `loaded`; toate cele 10 zone sunt păstrate.

La 09:13:26, serviciul propriu `virtual_climate.update_zone` a salvat explicit
`sensor_floor: null` pentru `noah_bedroom`, declanșând reîncărcarea integrării.
Citirea după reîncărcare confirmă asocierea nulă, `t_floor: null` și
`floor_limit_state: no_floor_sensor`. Limitele numerice rămân salvate, dar nu
participă la control în absența senzorului. Noah are aproximativ 22,1 °C la o
țintă de 22 °C, cerere zero și actuator oprit — comportament așteptat în aceste
condiții. Nu a fost șters dispozitivul/senzorul ESPHome din registrul HA.

Prima citire a logului `system` filtrată după `virtual_climate`, inclusiv după
reîncărcare, nu conține erori sau avertizări. Diagnosticele actuatoarelor sunt
prezente și raportează zero neconcordanțe și zero actuatoare indisponibile.
Tranzițiile `stopped/startup` și zeroul temporar al cererii la 09:13:26 sunt
asociate reîncărcării deliberate a configurației, nu unei treceri între cicluri.

Pentru revenirea exclusivă a codului:

```bash
bash dev/sync.sh --host ha --config-root /config --rollback 20261024T060932Z-74273
```

Asocierea Noah eliminată prin API este o schimbare de configurație separată;
revenirea codului nu o reintroduce. Backup-ul include configurația anterioară
doar ca referință, fără restaurare automată a stocării interne HA.

### Verificarea primului ciclu complet

Fereastra recorder verificată: 09:13:32–09:22:39, Europe/Bucharest. Primul ciclu
după reîncărcare începe la 09:13:31.748 cu 505 s. Logul confirmă începutul celui
următor la 09:21:57.359, cu noua durată de 498 s. Durata veche nu a fost
modificată în timpul ciclului. În această fereastră:

- Faza rămâne `running` și cererea agregată rămâne în intervalul 0,33–0,38,
  inclusiv la trecerea dintre cicluri; nu există `stop/start` sau zero artificial.
- Bucătăria este `on` de la 09:17:27.021902 până la 09:21:27.458796
  (240,437 s); holul etajului de la 09:17:27.071442 până la 09:21:28.112753
  (241,041 s). Ambele respectă minimumul de 180 s plus 60 s deschidere.
- WC rămâne `on` de la 09:17:27.022240, inclusiv peste limita dintre cicluri;
  sursa și pompa rămân de asemenea pornite. Nu există impulsul OFF/ON observat
  inițial la schimbarea ciclului.
- Pompa pornește la 09:17:28.123930, iar sursa la 09:18:27.412432,
  după aproximativ 60 s de la confirmarea primelor actuatoare.
- Bucătăria și holul oprite sunt în repaus minim, iar cererea lor rămâne
  pozitivă; diagnosticul nu raportează neconcordanțe ale actuatoarelor.
- Noah rămâne oprit, cu senzorul de pardoseală eliminat. Compararea celor
  10 zone înainte și după actualizare arată o singură modificare de
  configurație: `noah_bedroom.sensor_floor`, din vechea entitate în `null`.

Logurile `system` filtrate după integrare nu conțin erori/avertizări.
Fereastra recentă de log brut include înregistrările INFO ale ciclurilor și
secvenței sursei, fără excepțiile vechi de thread/timer.
Captura verificării este salvată local, în directorul ignorat de Git
`local/deployments/20261024T060932Z-74273-verification.json`.

Aceasta verifică un ciclu complet și trecerea lui în următorul, nu performanța
termică pe termen lung. Senzorii de aer Living room și Entry hallway rămân
indisponibili; zonele respective sunt blocate explicit cu
`air_sensor_unavailable`, independent de corecțiile instalate.
