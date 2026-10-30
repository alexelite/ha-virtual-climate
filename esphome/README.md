# Reglaj local calm pentru vana pardoselii

`packages/mixing-valve.yaml` și `packages/mixing_controller.h` formează pachetul
reutilizabil; `examples/module1.yaml` păstrează numele/id-urile hardware din
configurația locală `module1`. Nu conține secrete și nu a fost instalat pe ESP32.

Pachetul primește ID-urile pompei, modului, comenzii manuale, țintei, cover-ului,
indicatorului de calibrare și proprietarului anti-blocare. Scriptul
`cancel_exercise_id` trebuie să abandoneze exercițiile fără cleanup întârziat
peste o comandă reală. Senzorul NTC brut al nodului se numește `ntc_raw`.
Copia filtrată păstrează `ntc_temperature` / „NTC Temperature”.

ADC-ul din exemplu eșantionează la 5 s. Temperatura publică de control folosește
mediană 3 și EMA de 30 s, fără cuantila veche. Regulatorul reconstruiește separat
același filtru numai din citirile cu circulație: temperatura din pauză nu intră
în media de reglaj de 120 s, nici indirect prin starea EMA/medianei. Valorile brute
se folosesc pentru protecții, independent de medie.

Automatul verifică siguranța la 5 s și deciziile normale la 30 s; o corecție
necesită abatere persistentă la două evaluări și minimum 90 s de la terminarea
mișcării. Adapterul cover-ului notifică terminarea prin `motion_finished`.
Pentru ±2°C nu corectează; peste 2°C corectează 1%, peste 5°C corectează 2%.
O tendință de minimum 0.2°C/min spre bandă amână mișcarea.

Stările vizibile sunt `idle_closed`, `prepositioning`, `settling`, `regulating`,
`manual`, `fault`; `calibrating` delimitează calibrarea de boot. Memoria poziției
rămâne în RAM: minimum cinci minute cu circulație, medie în bandă, minimum două
minute fără corecție. După oprire, vana închide. Poziția poate fi reutilizată la
pauze de cel mult 30 minute, în încălzire și pentru ținte diferite cu cel mult
1°C. Fără poziție validă pornește la 10%, cu revenire de maximum 30 puncte
procentuale/minut. După poziționare așteaptă minimum 120 s; temperatura proaspătă
peste banda superioară întrerupe revenirea.

Limita absolută `ufh_absolute_max` este obligatorie și intenționat nu are o
valoare implicită în exemplu. Limita trebuie verificată din instalație, împreună
cu sensul vanei și durata cursei, înainte de instalare. Depășirea ei închide
imediat aportul cald; ținta+8°C timp de 15 s produce același `fault`. Lipsa
măsurătorilor valide timp de 30 s închide aportul. Reluarea cere 120 s sub
pragul de declanșare minus 2°C. Pompa nu este oprită automat de regulatorul vanei.
Protecțiile au prioritate inclusiv în control manual sau exercițiu.

Releul comun are un singur arbitru OR al cererilor, după publicarea stării
fiecărei cereri template, cu interblocare la răcire. „CT gaz relay active” și
textul de diagnostic descriu starea software, fără feedback al contactelor
sau al arderii. Exercițiile folosesc GPIO-urile interne ale pompelor;
comenzile reale trec prin template-uri și anulează exercițiul chiar dacă pompa
era deja pornită. Reglajul normal nu concurează cu exercițiul vanei.
Protecția la deconectarea HA rămâne la intervalul existent de cinci minute.

Substituțiile `mixing_band`, `mixing_initial_position`, `mixing_return_per_minute`,
`mixing_move_pause`, `mixing_settling`, `mixing_small_step`, `mixing_large_step`,
`mixing_large_error` și `mixing_trend_per_minute` configurează reglajul normal.
Restul temporizărilor sunt câmpuri explicite ale `MixingConfig`, configurabile
în adapter înainte de apelul `tick`; nu există PID sau integrală locală.

## Validare

ESPHome 2026.10.1 validează configurația. Comenzile de mai jos folosesc 50°C
**numai ca valoare de compilare**, fără a afirma că este potrivită instalației:

```sh
.venv/bin/esphome -s ufh_absolute_max 50 config esphome/examples/module1.yaml
.venv/bin/esphome -s ufh_absolute_max 50 compile esphome/examples/module1.yaml
```

Validarea YAML și zece scenarii C++ locale, plus tabela de adevăr a arbitrului
OR, au trecut. Generarea C++ a reușit în prima încercare de compilare ESP32,
dar toolchain-ul ESP-IDF nu a putut fi descărcat în sandbox; cererea de permisiune
pentru continuarea compilării a fost respinsă. Prin urmare **compilarea ESP32
rămâne neverificată**. Testele locale nu înlocuiesc validarea firmware-ului sau
validarea fizică a reglajului. Nu a fost executată comanda `run`/`upload`.

Documentație ESPHome folosită pentru integrare: [pachete](https://esphome.io/components/packages/),
[comutatoare template](https://esphome.io/components/switch/template/),
[triggere de stare ale comutatoarelor](https://esphome.io/components/switch/),
[filtre de senzor](https://esphome.io/components/sensor/) și
[ADC](https://esphome.io/components/sensor/adc/).
