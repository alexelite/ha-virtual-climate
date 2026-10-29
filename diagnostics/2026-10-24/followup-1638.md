# Verificare la 7 ore și 25 de minute după instalare

Fereastra completă analizată: **24 octombrie 2026, 09:13:32–16:38:20,
Europe/Bucharest**, 26.688 s. Citiri exclusiv de verificare prin MCP și SSH;
codul de producție și configurația homerha nu au fost schimbate în această
verificare. Istoricele au fost citite integral în această fereastră, fără
pagini rămase. Prima stare este o captură la începutul ferestrei, nu o
tranziție; intervalele inițiale incomplete sunt excluse din minime.

## Rezultat

Remedierea actuatoarelor și eliminarea asocierii Noah se confirmă. Există însă
un defect rămas în tranziția dintre căile de circulație, care provoacă opriri
scurte ale sursei. Funcționarea nu poate fi declarată complet corectată.

### Actuatoare și configurație

- Integrarea este `loaded`, cu cele 10 zone păstrate.
- 130 de impulsuri ON complete; niciun impuls sub 240 s și nicio pauză
  completă sub 240 s. Minimele sunt aproximativ 240,133 s ON și 240,138 s OFF.
- `noah_bedroom.sensor_floor` rămâne `null`, `t_floor: null`,
  `floor_limit_state: no_floor_sensor`. Noah nu a pornit în această fereastră.
- Nu există perioade de actuatoare indisponibile în diagnosticul înregistrat.
  Cele 90 de episoade de neconcordanță comandă/feedback durează cel mult
  2,001 s, compatibil cu confirmarea asincronă; nu există episoade peste 5 s.
- Living room și Entry hallway sunt încă blocate explicit de senzorii de aer
  indisponibili; utilizatorul a identificat bateriile descărcate.

### Cerere și cicluri

Logurile conțin 43 de începuturi noi de ciclu în fereastră, suplimentar celui
deja activ la început. Istoricul fazei conține numai `running` și `idle`, fără
vechile secvențe administrative `stop/start`.

Sunt patru intervale de cerere zero, însumând 1.199,748 s (4,50% din fereastră).
Primul începe la 16:17:41.968, imediat după schimbarea țintei WC din 23,5 °C
în 22 °C, la o temperatură de aproximativ 22,19 °C. Capturile tuturor celor
8 zone cu senzori de aer disponibili confirmă `requested_fraction: 0` și
`no_demand` la fiecare dintre cele patru începuturi. Aceste zerouri au o
explicație termică/configurațională și nu reproduc vechiul defect al ciclului.
Verificarea nu atribuie unei persoane sau automatizări schimbarea țintei WC.

### Defect rămas: transferul între zone întrerupe sursa

Releul sursei are **30 de impulsuri ON complete**, dintre care **13 durează
30,108–31,943 s**, față de minimumul configurat de 300 s. Celelalte 17 sunt de
aproximativ 300 s sau mai lungi. Repausul sursei este respectat: minimum
210,126 s observat, față de 180 s configurat.

Toate cele 13 opriri scurte corespund unui `Plant STOP ... reason=no_flow` în
logul integrării, nu unei excepții Python. Exemplul verificat la nivel de
atribute și confirmări ESPHome:

1. La 09:42:00 pornesc Kitchen și Upstairs hallway; WC așteaptă repausul minim.
2. Sursa așteaptă 180 s repaus, apoi 30 s întârziere și pornește electric la
   09:45:30.383838.
3. La 09:46:00.389–.393, Kitchen și Upstairs hallway încă raportează `on`, dar
   primesc comandă `off`; WC primește `on`, dar raportează încă `off`.
   Zonele nu au blocaje de siguranță; WC are cerere pozitivă de 0,7133.
4. Sursa este oprită pentru `no_flow` la 09:46:00.792863, după 30,409 s.
   Confirmarea WC `on` apare la 09:46:00.492046; diagnosticul tick-ului
   anterior nu o avea încă disponibilă. Kitchen/hol confirmă oprirea în același
   interval. Pe următorul tick se solicită din nou pornirea sursei, cu încă
   180 s repaus.

`_reconcile_zones()` închide vechile zone și comandă noua zonă în aceeași
trecere. `_flow_zones()` ia în calcul doar zonele dorite, deja confirmate `on`.
Fereastra fără confirmare declanșează protecția, care oprește sursa și pompa
imediat, fără minimum de funcționare/postcirculație. Oprirea imediată la o
pierdere reală a căii rămâne necesară; problema este crearea evitabilă a
acestei situații la un transfer normal între zone.

## Reproducere locală deterministă

`python3 diagnostics/2026-10-24/reproduce_handover.py` execută clasa de producție
cu două zone, aceiași timpi și I/O HA simulat. Nu comunică cu instalația.

```text
immediate feedback: source_interrupted=False, old_path_closed=True, new_path_confirmed=True
delayed feedback: source_interrupted=True, source_run_s=30.0, old_path_closed=True, new_path_confirmed=False
PASS: immediate feedback control
FAIL: planned handover loses its confirmed path and stops the source after 30 seconds
```

Exit code 1 este intenționat pe codul instalat. Proba de control schimbă numai
confirmarea imediată/întârziată; confirmarea electrică imediată nu dovedește
deschiderea mecanică a vanei. Reproducerea este păstrată explicit în directorul
de diagnostic, separat de testele de regresie care trec.

## Remediere recomandată

Transferul trebuie realizat cu suprapunere: comanda de deschidere a următoarei
zone, confirmarea ei și așteptarea timpului `open_s`, apoi închiderea căii
vechi. Calea veche trebuie să rămână eligibilă din punct de vedere al
siguranței. Dacă sursa încă trebuie să respecte minimumul de funcționare sau
postcirculația, trebuie păstrată o cale validă pe acea durată.

La blocarea reală a ultimei căi rămâne obligatorie oprirea de protecție; nu
se recomandă eliminarea `no_flow` sau forțarea celor 300 s fără o cale validă.
Testele trebuie să acopere confirmarea ESPHome întârziată, timpul de deschidere
la transfer, pornirea sursei întârziată de repaus și pierderea reală a căii.

## Loguri și limite

Nu au reapărut în logurile citite erorile vechi de thread/timer. Există o
avertizare izolată la 16:08:55: actualizarea stării `climate.living_room` a
durat 1,162 s. Nu este explicația celor 13 opriri scurte, care au evenimente
`no_flow` și o reproducere separată. Aceasta este o verificare de secvențiere
și stare electrică; nu măsoară debitul, poziția vanelor sau consumul termic.

Dovezile și calculele sunt păstrate în fișierul ignorat de Git
`local/deployments/20261024T133820Z-followup.json`.
