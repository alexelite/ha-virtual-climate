# Contractul regulatorului local de tur

Virtual Climate calculează cererea zonelor, coordonează instalația și stabilește
ținta de tur. Reglajul local al temperaturii de tur, actuatorul vanei,
interblocările hardware și comportamentul sigur la pierderea Home Assistant
aparțin controllerului dispozitivului și nu sunt implementate în acest
repository.

Contractul este exprimat exclusiv prin entități Home Assistant configurate pe
intrarea Virtual Climate. Integrarea nu presupune ESPHome, identificatori din
firmware, pini sau o anumită strategie locală de reglaj.

## Comenzi către instalație

O intrare poate configura următoarele roluri:

- `heating_source_entity`: cerere logică de încălzire;
- `cooling_source_entity`: cerere logică de răcire;
- `circulation_pump_entity`: comandă logică a pompei;
- `changeover_entity`: selectarea modului instalației, când este necesară;
- `target_supply_temperature_entity`: ținta de tur solicitată.

Entitățile de comandă pot fi adaptoare către un controller local. Ele nu trebuie
să fie releele fizice. Controllerul local poate refuza sau opri o comandă pentru
protecție, iar integrarea tratează starea raportată ca stare software observată,
nu drept confirmare de debit, poziție mecanică, flacără sau energie livrată.

În implementarea actuală, Virtual Climate deține secvențierea nominală a
actuatoarelor de zonă, pompei și sursei: întârzierile de pornire, funcționarea
minimă, postcirculația și pauza minimă. Un adapter de dispozitiv nu trebuie să
implementeze independent aceleași temporizări. Protecțiile locale pot opri
hardware-ul oricând.

## Observații din instalație

Senzorii configurați în `supply_control` pot furniza temperatura efectivă de
tur, returul și exteriorul. Aceștia sunt opționali pentru funcțiile care nu îi
necesită. Senzorul de tur trebuie să aparțină circuitului controlat de intrarea
respectivă.

Stările pompei, sursei și actuatoarelor sunt context observațional. Virtual
Climate nu deduce din ele că există debit, ardere sau aport termic fizic. Un
controller local poate expune diagnostic și faulturi suplimentare, dar acestea
nu fac parte din contractul obligatoriu până când integrarea nu oferă câmpuri
de configurare și semantică explicită pentru ele.

## Mai multe instalații

Fiecare intrare configurează explicit entitățile instalației sale. Când mai
multe circuite folosesc aceeași sursă fizică, entitățile configurate trebuie să
ofere un singur proprietar al releului comun sau adaptoare de cerere arbitrate
în controllerul local. Două intrări nu trebuie să comande independent același
releu fizic fără un asemenea arbitru.

Schimbarea proprietarului secvențierii de la Virtual Climate la controllerul
local este o decizie arhitecturală separată. Dacă va fi adoptată, temporizările
și comenzile duplicate se elimină din integrare în aceeași etapă.
