# Controlul temperaturii de tur

Implementarea inițială acoperă încălzirea. Configurațiile existente păstrează temperatura constantă până la alegerea explicită a compensării climatice. Răcirea folosește în continuare o temperatură constantă, configurată separat. Dispozitivul instalației realizează reglajul local.

## Configurare

Țintele constante de încălzire și răcire și entitatea care primește ținta se
editează în **Controlul temperaturii de tur**, atât la configurarea inițială,
cât și în opțiunile integrării. **Setări Globale** păstrează modul instalației,
sursele, pompa, temporizările și coordonarea zonelor. Ținta constantă de
încălzire este și rezerva compensării climatice când exteriorul nu este valid.
Mutarea câmpurilor în interfață păstrează valorile existente și cheile JSON
`global.heating_supply_target`, `global.cooling_supply_target` și
`global.target_supply_temperature_entity`; nu este necesară o migrare.

În opțiunile integrării există pasul **Controlul temperaturii de tur**. Același pas este disponibil în configurarea manuală inițială. Strategia, senzorii, limitele, învățarea și boostul au câmpuri dedicate. Obiectul `curve` conține intervalul exterior și lista temperaturilor de tur; numărul valorilor din listă stabilește numărul punctelor echidistante, între 2 și 50. Obiectul `tuning` expune parametrii de observație și ajustare.

Modificarea unui punct de bază resetează corecția și experiența acelui punct. Schimbarea numărului de puncte sau a intervalului exterior resetează toată învățarea. Formularul explică acest efect înainte de salvare.

Importul/exportul JSON include blocul `global.supply_control`. Exemplul de mai jos este un fragment de configurare globală; pentru importul complet se păstrează și celelalte setări globale și lista `zones`:

```json
{
  "target_supply_temperature_entity": "number.mixing_supply_target",
  "heating_supply_target": 32,
  "cooling_supply_target": 18,
  "supply_control": {
    "heating_strategy": "weather_compensated",
    "cooling_strategy": "constant",
    "outdoor_sensor": "sensor.outdoor_temperature",
    "supply_sensor": "sensor.supply_temperature",
    "return_sensor": "sensor.return_temperature",
    "outdoor_min": -15,
    "outdoor_max": 15,
    "supply_points": [40, 36, 32, 28, 24],
    "heating_min": 20,
    "heating_max": 45,
    "cooling_min": 5,
    "cooling_max": 30,
    "learning_mode": "off",
    "boost_enabled": true
  }
}
```

Senzorul exterior este obligatoriu la alegerea compensării. Turul și returul sunt opționale. Calculul curbei poate fi inspectat fără sursă comandată de integrare; învățarea, boostul și monitorizarea activă necesită contextul cererii controlate de Virtual Climate. Transmiterea necesită o entitate `number` sau `input_number` disponibilă. Unitățile temperaturilor exterioare, turului și returului sunt convertite din °F sau K în °C; pentru entitatea țintă se acceptă °C și °F. Toți parametrii din configurație sunt în °C, iar ratele sunt în °C/oră.

`heating_supply_target` este și ținta de rezervă la pierderea exteriorului. Rezerva este constantă, cu învățarea și boostul suspendate. Limitele configurate se aplică țintei finale în toate strategiile. Intrările vechi fără blocul `supply_control` își păstrează țintele fixe existente.

## Curba și corecțiile

Ținta rezultă din curba interpolată între puncte, corecția învățată și boost, apoi este limitată între minim și maxim. În afara intervalului exterior se continuă panta segmentului de capăt până la limite; învățarea se suspendă. Observațiile se atribuie punctului apropiat; la egalitate exactă se alege punctul cu temperatura exterioară mai rece. Curba corectată păstrează relația monotonă cu exteriorul; probele care ar inversa-o sunt limitate sau împiedicate.

Modurile de învățare:

- `off`: folosește curba de bază, fără aplicarea sau actualizarea corecțiilor păstrate;
- `learn`: aplică corecțiile și poate face probe reversibile;
- `frozen`: aplică numai corecțiile validate, fără probe noi.

Boostul are activare independentă și nu este încorporat automat în corecțiile învățate. Folosește deficitul și tendința temperaturii fiecărei camere împreună cu activarea electrică raportată a actuatorului. Cea mai mare nevoie validă determină suplimentul comun, plafonat. O pauză normală a sursei între sloturi păstrează boostul dacă deficitul există în continuare; el se retrage când confortul se recuperează. Activarea electrică nu confirmă debitul.

Probele folosesc timp de observație valid acumulat între cicluri; pauzele normale nu șterg experiența și nu sunt numărate ca încălzire. La recuperare prin boost, schimbarea setpointului, schimbarea intervalului exterior, pierderea datelor sau eroarea de comandă, proba se întrerupe și se revine la corecția validată. În această primă versiune, învățarea nu modifică curba în timpul boostului activ.

Corecțiile și experiența sunt salvate separat pentru fiecare intrare, prin mecanismul de stocare Home Assistant. Configurația exportată nu conține istoricul învățării. La repornire se restaurează valorile validate; o probă neterminată nu se reia. Se așteaptă observații noi. Serviciul `virtual_climate.reset_supply_learning`, cu `entry_id`, resetează învățarea fără a schimba curba configurată.

## Profilul inițial de calibrare

Aceste valori sunt puncte de pornire pentru teste și calibrare. Simulările de regresie verifică logica și temporizarea, fără a valida inerția unei instalații reale.

| Parametru | Implicit | Utilizare |
| --- | --- | --- |
| `sample_seconds` | 60 s | Eșantionarea observațiilor; efectiv minimum 60 s în integrare |
| `max_gap_seconds` | 120 s | Peste acest gol se abandonează observațiile/proba în curs |
| `sensor_max_age_seconds` | 0 | Expirarea după ultima raportare; 0 dezactivează limita de vârstă |
| `trend_seconds` | 3600 s | Tendință prin regresie liniară, cu minimum 90% acoperire temporală |
| `minimum_active_fraction` | 0.2 | Activare minimă raportată în fereastra de observație |
| `learning_seconds` | 86400 s | Timp valid acumulat înainte de o probă; poate necesita mai multe zile calendaristice |
| `probe_seconds` | 86400 s | Timp valid acumulat pentru evaluarea unei probe |
| `learning_step` | 0.5°C | Pasul maxim al unei probe la punctul relevant |
| `correction_limit` | ±5°C | Limita corecției unui punct față de baza sa |
| `comfort_tolerance` | 0.3°C | Toleranța deficitului pentru evaluarea confortului |
| `comfort_persistence_seconds` | 1800 s | Persistența deteriorării confortului înainte de respingerea anticipată a reducerii |
| `minimum_learning_improvement` | 0.05°C | Îmbunătățirea medie minimă pentru validarea unei creșteri de probă |
| `probe_outdoor_tolerance` | 2°C | Abaterea exteriorului față de începutul probei care o întrerupe |
| `boost_deficit` | 1°C | Deficitul de la care este evaluat suplimentul de recuperare |
| `boost_gain` | 2 | Supliment per grad de deficit, diminuat când camera se recuperează deja |
| `boost_max` | 5°C | Plafon suplimentar, subordonat limitei finale a turului |
| `boost_rate_per_hour` | 1°C/oră | Viteza maximă de creștere/retragere a suplimentului |
| `minimum_recovery_rate` | 0.1°C/oră | Rata de recuperare de referință |
| `fault_seconds` | 21600 s | Fereastra pentru răspuns termic insuficient persistent |
| `recovery_seconds` | 7200 s | Perioada de răspuns acceptabil înaintea reluării automate |
| `supply_tolerance` | 5°C | Abaterea medie persistentă a turului față de ținta transmisă |
| `delta_t_alert` | 15°C | Diferență tur–retur medie persistentă care justifică o verificare |
| `write_interval_seconds` | 60 s | Interval minim între actualizări/reîncercări în funcționare |
| `write_delta` | 0.2°C | Schimbarea minimă pentru o actualizare normală |
| `write_refresh_seconds` | 900 s | Retransmiterea periodică a unei ținte neschimbate |

La vârstă maximă activată se folosește ultima raportare disponibilă (`last_reported`, apoi `last_updated`), nu ultima schimbare a valorii. O temperatură neschimbată poate fi validă. La revenirea unui senzor valid se reia calculul curbei, dar observațiile trebuie reconstruite înainte de învățare. Datele lipsă, `unknown`, `unavailable`, NaN și infinit nu sunt folosite ca temperaturi.

Zonele sunt evaluate împreună la 60 de secunde. Temperatura de cameră și deficitul provin din aceeași citire folosită de climate și de cererea zonei. Cu `temperature_filter_enabled: true` (implicit), această temperatură trece printr-un EMA cu o constantă de timp de 180 de secunde. Activarea/dezactivarea se face în opțiunile fiecărei zone; nu modifică senzorul dedicat. Sursa măsurătorii este verificată în continuare pentru disponibilitate și vechime; o valoare filtrată nu menține eligibilă o sursă indisponibilă. O observație a zonei mai veche decât `max_gap_seconds` nu este folosită.

Configurațiile vechi cu `sample_seconds: 30` folosesc efectiv 60 de secunde. Ferestrele de observație și golul maxim se extind la cel puțin două intervale efective dacă era configurată o valoare mai scurtă. Executarea sloturilor actuatoarelor și întârzierile sursei/pompei folosesc temporizări proprii, distincte de evaluarea termică.

## Diagnostic și istoric

Integrarea expune senzori pentru ținta curbei, corecția învățată validată, ajustarea temporară a unei probe, boost, ținta finală, temperatura exterioară, turul efectiv, retur, diferența tur–retur, strategie, starea învățării și zona care determină ținta. O probă în curs nu este prezentată ca o corecție deja validată. Senzorul stării învățării include în atribute punctele, experiența, proba, tendințele zonelor, ultimele evenimente și eventualele erori de comandă.

În istoricul Home Assistant pot fi afișate împreună ținta curbei, ținta finală și turul efectiv. Astfel se vede, de exemplu, o curbă de bază de 35°C, corecție de −3°C, boost zero și țintă de 32°C. Atributele punctelor explică de unde provine corecția.

Un răspuns insuficient persistent, o abatere medie a turului sau o diferență tur–retur mare produc diagnostic și o notificare persistentă identificată separat pentru fiecare intrare. Nu constituie singure o comandă de oprire. Învățarea întregii curbe comune se suspendă; corecțiile validate se păstrează. Confirmarea notificării nu șterge condiția tehnică. Reluarea automată necesită răspuns acceptabil pe perioada configurată și nu anulează modul `frozen`.

Comenzile de tur sunt așteptate până la terminarea apelului de serviciu, cu timeout de 10 secunde. Înaintea unei porniri noi, transmiterea trebuie să reușească. În funcționare, eșecul produce reîncercări și notificare, fără oprirea automată a sursei doar pentru acea eroare. Limitele și unitatea entității țintă sunt verificate; o comandă în afara limitelor dispozitivului este refuzată. Succesul apelului nu confirmă realizarea temperaturii fizice.

Implementarea poate fi verificată prin `python -m unittest discover -s tests -v`. Testele includ un model termic simplificat pe patru zile, cicluri pornit/oprit, corecții în ambele direcții, restaurare, pierderea senzorilor, comenzi eșuate și compatibilitatea configurațiilor vechi. Încărcarea completă în Home Assistant și răspunsul dispozitivelor necesită verificare pe instalația reală înainte de calibrarea parametrilor.
