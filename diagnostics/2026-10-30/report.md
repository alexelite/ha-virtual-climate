# Date pentru analiza reglajului vanei de amestec

Captură read-only din `ha_zamfir`, 30 octombrie 2026, fus orar
`Europe/Bucharest`. Nu au fost modificate codul ESPHome, integrarea Virtual
Climate, configurația Home Assistant sau stările entităților.

Acest document este un handoff pentru o analiză ulterioară. Separă observațiile
de ipoteze și nu propune încă o remediere.

## Surse

- Configurația ESPHome atașată de utilizator:
  `/Users/alex/.codex/attachments/2319db0f-a98c-4718-8ec8-b84be1173ff9/Pasted text.txt`
- Istoric Home Assistant citit prin MCP `ha_zamfir`.
- Configurația live a intrării `virtual_climate` cu ID
  `01KWSN1WYYJ9GDZYNX9J92BN4Q`.
- ADR-urile 0001–0003 și `GLOSSARY.md` din repository.

## Lanțul de semnale necesar

| Rol | Entitate | Observație |
| --- | --- | --- |
| Temperatură efectivă după vana de amestec | `sensor.ntc_temperature` | ESPHome, NTC 10 kΩ |
| Poziție estimată vană | `sensor.valve_1_position` | procent derivat din cover-ul time-based; nu apare în entity registry |
| Actuator vană | `cover.mix_valve_1` | cursă completă declarată 120 s, poziție presupusă |
| Țintă locală tur | `number.setpoint_temperature` | 16–45°C, pas 0,5°C |
| Pompa circuitului IP | `switch.pompa_ip` | condiționează complet bucla de reglaj a vanei |
| Pompa radiatoarelor | `switch.pompa_radiatoare` | circuit distinct în codul ESPHome |
| Cerere gaz IP | `switch.camera_tehnica_module1_ct_gaz_ufh` | cerere logică optimistă |
| Cerere gaz radiatoare | `switch.camera_tehnica_module1_ct_gaz_radiatoare` | cerere logică optimistă |
| Releu fizic sursă | `binary_sensor.camera_tehnica_module1_ct_gaz_relay_active` | feedback din starea releului ESPHome |
| Diagnostic cerere comună | `sensor.camera_tehnica_module1_ct_gaz_debug` | text diagnostic; nu este feedback fizic |
| Mod global | `select.camera_tehnica_module1_system_mode` | `Heat` în ferestrele analizate |
| Cameră observată | `climate.mansarda`, `sensor.mansarda_temperature` | setpoint și temperatură cameră |
| Actuator radiator Mansarda | `input_boolean.trv_mansarda` | comandă electrică; nu confirmă debitul |

## Comportamentul implementat în ESPHome

- Bucla rulează la fiecare **30 s**, numai dacă `switch.pompa_ip` este ON și
  controlul manual este OFF.
- În încălzire:
  - eroare mai mare de 5°C: vana se deschide cu 5%;
  - eroare între 2 și 5°C: se deschide cu 2%;
  - exces între 2 și 5°C: se închide cu 2%;
  - exces peste 5°C: se închide cu 5%;
  - în banda ±2°C nu se comandă nicio corecție.
- La oprirea pompei IP, vana primește comandă de închidere completă.
- La o eroare mare, viteza maximă de comandă este 5% la 30 s, adică
  aproximativ 10%/minut. De la 0 la 80% sunt necesare aproximativ 8 minute.
- Cover-ul este `time_based`, cu 120 s pentru cursa completă; poziția este o
  estimare, fără feedback mecanic de poziție.
- `sensor.ntc_temperature` are filtru `quantile`, fereastră 7, `send_every: 4`,
  cuantila 0,9. În istoricul HA rezultă o cadență de aproximativ 4 minute.
  Valoarea nu este o medie și este intenționat orientată către eșantioanele
  ridicate din fereastră.
- Releul comun de gaz este OR-ul cererilor UFH și radiatoare, cu interblocare
  la răcire.

## Fereastra principală: 16:30–18:24

Ținta locală a fost constantă la **42°C**. S-au înregistrat:

- 25 de eșantioane NTC;
- 761 de schimbări ale poziției raportate a vanei;
- 171 de tranziții de stare ale cover-ului;
- 22 de stări ale pompei IP.

NTC a variat între **30,04°C** și **48,76°C**. Maximul observat depășește
ținta cu **6,76°C**.

Releul fizic al sursei a fost ON continuu de la începutul ferestrei până la
18:21:28. Pompa IP a pulsat în intervale de aproximativ 7,5–8,5 minute ON,
urmate în general de aproximativ 3 minute OFF. Cererea logică UFH începe de
regulă la circa 30 s după pompă și se termină cu circa 120 s înaintea pompei.

Acest interval este esențial pentru întrebarea „ce s-ar întâmpla fără controlul
sursei”: disponibilitatea continuă a sursei nu a eliminat creșterea lentă a
temperaturii după vană. Totuși, nu este încă stabilit dacă releul ON înseamnă
ardere continuă a centralei; nu există feedback de flacără/modulație/debit.

### Cicluri reprezentative

NTC este raportat la aproximativ 4 minute, astfel că timpul de atingere a
țintei are o incertitudine de ordinul unui interval de eșantionare.

| Pompa IP ON | Durată | Vârf poziție | Eșantioane NTC în puls | Maxim până la 4 min după puls |
| --- | ---: | ---: | --- | ---: |
| 16:34:29–16:42:58 | 509 s | 80% | 30,59; 32,77 | 43,91°C |
| 16:47:01–16:55:11 | 490 s | n/a | 43,48 | 43,48°C |
| 16:58:54–17:06:54 | 480 s | 80% | 33,01 | 44,38°C |
| 17:10:13–17:18:07 | 474 s | n/a | 43,59 | 43,59°C |
| 17:21:07–17:28:58 | 471 s | 75% | 30,41; 33,69 | 45,33°C |
| 17:31:58–17:39:28 | 450 s | n/a | 43,59; 33,39 | 43,59°C |
| 17:42:28–17:49:58 | 450 s | 60% | 31,54; 39,91 | 42,32°C |
| 17:52:58–18:00:28 | 450 s | 10% | 34,05 | 34,05°C |
| 18:03:28–18:10:58 | 450 s | 75% | 36,07 | 48,76°C |
| 18:13:58–18:21:28 | 450 s | n/a | 47,53 | 47,53°C |

În ciclurile unde primul eșantion peste 42°C a fost surprins în timpul
pulsului, întârzierile observate au fost aproximativ 209, 266, 314 și 329 s.
În alte cicluri primul eșantion peste țintă apare abia după oprirea pompei.

`n/a` la poziție nu înseamnă senzor indisponibil. În acele intervale istoricul
nu conține mișcare a vanei, de regulă deoarece temperatura ridicată nu a cerut
deschidere nouă.

## Fereastra Mansarda: 29 octombrie 21:40 – 30 octombrie 08:35

- Temperatura filtrată a camerei pornește de la 17,30°C.
- La activare ținta a fost inițial 22°C și a devenit 21°C la 21:47:33.
- Temperatura filtrată traversează 21°C la 00:32:10.
- Maximul ulterior este 21,233°C la 07:24:10, adică overshoot observat
  aproximativ **0,23°C**.
- La 08:30 temperatura era 21,081°C.
- Pompa IP a fost ON continuu în fereastra 21:40–08:29:46.
- Pompa și cererea radiatoarelor au pulsat; vana Mansarda a continuat să aibă
  impulsuri după prima atingere a țintei.
- Ținta locală ESPHome a fost în principal 37°C. NTC a variat între 29,47 și
  42,39°C, adică un exces maxim observat de aproximativ 5,39°C față de ținta
  locală de 37°C.

Această corelație nu dovedește că vana de amestec alimentează radiatoarele.
Codul ESPHome leagă explicit reglajul vanei de pompa IP, iar radiatoarele au
pompa lor. Topologia hidraulică trebuie confirmată înainte de a atribui
overshoot-ul Mansardei direct vanei de amestec.

## Configurația live Virtual Climate relevantă

- `heating_source_entity`:
  `switch.camera_tehnica_module1_ct_gaz_radiatoare`
- `circulation_pump_entity`: `switch.pompa_radiatoare`
- `heating_source_start_delay_seconds`: 30 s
- `minimum_off_time_seconds`: 180 s
- `minimum_run_time_seconds`: 300 s
- `pump_post_run_seconds`: 120 s
- `heating_supply_target`: 32°C
- `target_supply_temperature_entity`: `null`

Prin urmare, în configurația live Virtual Climate nu transmite ținta sa către
`number.setpoint_temperature`. Valoarea ESPHome de 42°C este independentă de
ținta de tur de 32°C din Virtual Climate.

## Limitări care trebuie păstrate în analiza următoare

1. NTC are cadență rară și filtru de cuantila 0,9; nu permite măsurarea exactă
   a întârzierii la nivel de secunde și poate favoriza vârfurile.
2. Poziția vanei este estimată time-based, nu măsurată mecanic.
3. Releul activ nu dovedește flacără, putere, temperatură primară sau debit.
4. Lipsesc temperatura înaintea vanei, temperatura returului și debitul.
5. Trebuie confirmată topologia: NTC/vana par legate de circuitul IP, nu de
   circuitul radiatoarelor.
6. În fereastra 16:30–18:24 releul fizic rămâne ON, deși cererea logică UFH
   pulsează. Această diferență trebuie explicată separat; nu trebuie presupus
   automat că este intenționată sau că reprezintă ardere continuă.

## Întrebări pentru modelul de reasoning

1. Cum se separă întârzierea sursei, întârzierea vanei, transportul hidraulic
   și filtrarea NTC folosind datele disponibile?
2. Ar trebui controlul local ESPHome să fie predictiv/PID sau este suficientă
   o reglare în trepte cu parametri diferiți?
3. Trebuie păstrată vana parțial deschisă între pulsurile apropiate ale pompei,
   în loc să fie închisă complet și redeschisă de la zero?
4. Ce parte aparține reglajului local și ce parte trebuie doar observată și
   interpretată de Virtual Climate, conform ADR 0001–0003?
5. Ce instrumentare minimă suplimentară este necesară pentru o concluzie
   cauzală: temperatură primară, retur, debit, feedback flacără/modulație sau
   poziție mecanică reală?
