# Control termic cu memorie

Implementarea urmărește [planul aprobat](adaptive-control-plan.md), urmărit în
[issue #1](https://github.com/alexelite/ha-virtual-climate/issues/1).
Este o implementare experimentală: nu a fost instalată în HA.
Configurațiile existente rămân `legacy`. Acceptarea completă pentru activare
live rămâne deschisă: sunt necesare calibrarea și acceptarea scenariilor de
menținere, inclusiv sarcina mică.

## Configurare

În opțiunile integrării, „Control termic cu memorie” selectează strategia:

- `legacy`: controlul existent, fără actualizarea modelelor zonelor;
- `observe`: propuneri și învățare din activarea reală, fără comenzi suplimentare;
- `adaptive`: impulsuri cu sold limitat; inițial PI, predicție numai după eligibilitate.

Răcirea folosește strategia existentă în toate cele trei moduri. Pentru fiecare
zonă, editorul opțiunilor permite profilul `underfloor` sau `radiator` și un
obiect de parametri avansați. Importul JSON acceptă aceleași chei; exportul le
păstrează. Lipsa strategiei înseamnă `legacy`; lipsa profilului înseamnă
`underfloor`. Profilul radiatoarelor trebuie ales explicit.

```json
{
  "global": {
    "global_co_mode_entity": "select.system_mode",
    "heating_control_strategy": "observe",
    "thermal_parameters": {"comfort_below": 0.2, "comfort_above": 0.3}
  },
  "zones": [{
    "id": "camera", "name": "Camera",
    "sensor_air": "sensor.camera_temperature", "sensor_rh": "sensor.camera_humidity",
    "switch_actuator": "switch.camera",
    "thermal_profile": "underfloor",
    "thermal_parameters": {"supply_reference": 40}
  }]
}
```

Parametrii zonei suprascriu parametrii avansați ai intrării. Obiectul acceptă:

| Cheie | Pardoseală | Radiatoare | Limite |
| --- | ---: | ---: | --- |
| `delay_minutes` | 45 | 20 | 1–120 |
| `persistence_minutes` | 180 | 45 | 5–360 |
| `trend_minutes` | 60 | 30 | 5–180 |
| `horizon_minutes` | 360 | 180 | 30–720 |
| `integral_minutes` | 360 | 180 | 30–1440 |
| `gain_per_hour` | 0.6 | 0.6 | 0.001–10 |
| `loss_per_hour` | 0.15 | 0.15 | 0–5 |
| `comfort_below` / `comfort_above` | 0.2 / 0.3 | 0.2 / 0.3 | 0–2°C |
| `deficit_weight` | 2 | 2 | 1–10 |
| `variation_cost` / `start_cost` | 0.02 / 0.01 | 0.02 / 0.01 | 0–10 |
| `supply_reference` | null | null | 5–90°C sau null |

Valorile sunt ipoteze inițiale, nu parametri fizici măsurați. Câștigul și
pierderea sunt rate locale în °C/oră. Pierderea este constantă în fereastra
modelului; modelul nu pretinde că estimează energia livrată sau anvelopa clădirii.
Senzorul opțional `supply_control.supply_sensor` trebuie să aparțină circuitului
intrării. Fără tur sau referință validă se utilizează activarea neponderată,
vizibilă în diagnostic. Reglajul local și hardware-ul sunt în afara integrării;
vezi [contractul regulatorului local](local-supply-regulator-contract.md).

## Comportament și învățare

Modelul se actualizează la un minut. Activarea raportată intră într-o coadă
cu întârziere, apoi într-o stare cu persistență exponențială. Cu tur valid,
activarea este ponderată cu diferența pozitivă tur–cameră raportată la
referință–cameră, limitată la 0–2. Atingerea țintei de tur nu este o condiție.

PI folosește proporționalul existent (eroare / 1.5°C) și integrala lentă,
limitată la 0–1, cu anti-windup. Blocajele, senzorii lipsă, intervențiile
manuale și suspiciunile de avarie suspendă acumularea. După schimbarea
setpointului, întreținerea așteaptă fereastra de tendință; dinamica poate
continua să fie observată. O scădere a setpointului șterge integrala și soldul
incompatibile. Acest modul nu scrie ținta de tur.

Impulsul pornește numai după acumularea duratei minime utile, incluzând
actuatorul, întârzierile sursei, funcționarea minimă și postcirculația.
Prelungirile reale se debitează din sold. Dacă durata minimă depășește ciclul
maxim, zona nu pornește și diagnosticul explică motivul. Soldul este limitat
pozitiv și negativ la `t_cycle_max`, fără restanțe nelimitate. Opririle pentru
ferestre, pardoseală și control manual au prioritate.

Identificarea caută întârzieri și persistențe la 0.5/0.75/1/1.5/2 ori valorile
profilului (în limite), apoi ajustează câștigul și pierderea prin regresie cu
constrângeri. Ajustarea folosește primele 70% dintre observațiile cronologice;
restul validează candidatul fără reajustare. Grilele indistincte sau activarea
aproape constantă nu justifică validarea. Sunt necesare cel puțin șapte zile
valide și trei secvențe de încălzire urmate de pauză, fiecare segment cel
puțin cât impulsul minim. Sunt excluse încălzirile inițiale ale filtrului,
golurile, blocajele, intervențiile manuale și avariile suspectate.

Predicția devine eligibilă la o reducere de minimum 15% a erorii pătratice
medii a ratei termice pe setul ulterior. Validarea este repetată cel mult la
șase ore, în executorul HA. Un profil inițial deja exact poate să nu treacă
pragul de îmbunătățire: în acest caz rămâne PI, fără eligibilitate inventată.
Predicția evaluează 0–100% în pași de 5%, simulând impulsurile minime și
aportul deja în coadă. Costul integrează pătratele abaterilor din afara benzii,
penalizează dublu deficitul și include variația și pornirile. La egalitate se
păstrează cererea precedentă.

Modelele și maximum 21 zile de observații se păstrează în stocarea HA,
separat de curba sursei: `virtual_climate.<entry_id>.thermal_zones`. Se salvează
la 15 minute și la unload. Soldul impulsurilor și istoricul activ nu persistă.
După restart, predicția așteaptă întârzierea plus trei constante de persistență;
PI este disponibil între timp. Modificarea senzorului, actuatorului, profilului
sau parametrilor relevanți invalidează experiența zonei.

Atributele `thermal_control` ale entității climate arată cererea de menținere,
corecția, efectul întârziat, tendința, temperatura prezisă, încrederea, parametrii,
soldul, motivul deciziei și validarea. `observe` separă propunerea de activarea
reală. Stările software ale pompei și cererii nu confirmă debitul sau arderea.
Învățarea curbei comune păstrează condițiile din ADR 0001–0003.

## Verificare și limite de acceptare

```sh
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python simulations/thermal_acceptance.py
```

[Raportul de acceptare](thermal-simulation-results.md) și
[rezultatele numerice pe scenarii](thermal-simulation-results.json) provin din instalații
sintetice cu întârzieri de 20–60 minute, persistență de 45–180 minute și patru
zile de control. Simularea compară proporționalul cu un ciclu fix de 12 minute
și durate minime cu noua politică de impulsuri; nu este o reproducere completă
a serviciilor HA sau a hidraulicii. Testele coordinatorului verifică separat
interblocările, mai multe zone și identitatea comenzilor `observe`/`legacy`.

Sunt publicate atât etapa PI inițială, cât și etapa de după nouă zile sintetice
de învățare, cu refacerea istoricului după restaurare. Un rezultat după învățare
include minutele în care predicția a fost efectiv eligibilă. Rezultatele fără
eligibilitate nu sunt prezentate drept control predictiv.

Cazul de sarcină mică este un contraexemplu de calibrare, păstrat în raport.
Nu declarăm îndeplinită acceptarea universală: mai puține porniri nu compensează
un deficit sau o depășire severă mai mare. Nu activați live pe baza acestor
simulări până la îndeplinirea criteriilor pe toate scenariile de menținere.

Ordinea rămâne explicită: observare → verificarea entităților instalației →
refacere observații → adaptive pe pardoseală → minimum șapte zile evaluare →
extindere la radiatoare. Nicio etapă nu a fost activată automat.
