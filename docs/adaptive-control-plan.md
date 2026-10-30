# Control termic adaptat instalațiilor lente și reglaj local ESPHome

## 1. Obiectiv și introducere

Implementăm un control care urmărește menținerea confortului prin aport termic distribuit în timp, ținând cont de întârzierea răspunsului și de încălzirea deja trimisă către instalație. Reglajul local urmărește apropierea temperaturii medii de tur de țintă în perioade cu circulație, acceptând oscilații moderate.

Decizii confirmate:

- Vana de amestec și `sensor.ntc_temperature` aparțin exclusiv pardoselii.
- Prima versiune schimbă încălzirea; răcirea păstrează strategia existentă.
- Obiectiv inițial configurabil de confort: −0,2/+0,3°C; deficitul persistent primește o penalizare mai mare.
- Sunt suficienți senzorii existenți. Turul este opțional și trebuie asociat circuitului corect.
- ESPHome închide vana la oprirea pompei și revine controlat la ultima poziție stabilă validă.
- Livrabil ESPHome: pachet reutilizabil în repository și exemplu pentru `module1`, fără instalare automată pe dispozitiv.

Introducem trei moduri pe fiecare intrare Virtual Climate: `legacy`, `observe`, `adaptive`. Configurațiile existente rămân `legacy`. În `observe`, algoritmul nou calculează propuneri și învață din comenzile reale, fără să le modifice. Trecerea în `adaptive` este explicită; revenirea la `legacy` este disponibilă.

## 2. Virtual Climate: model, control și învățare

### Modelul termic al zonei

Adăugăm un modul de calcul independent de Home Assistant, actualizat la 60 s. Primește temperatura și setpointul camerei, activarea raportată a actuatorului, temporizările instalației și, opțional, turul circuitului.

Fiecare zonă are profil `underfloor` sau `radiator`, cu parametri inițiali configurabili:

| Parametru | Pardoseală | Radiatoare |
|---|---:|---:|
| Întârziere inițială până la efect | 45 min | 20 min |
| Constanta inițială a persistenței efectului | 180 min | 45 min |
| Fereastră pentru tendința camerei | 60 min | 30 min |
| Orizont de predicție | 6 h | 3 h |
| Timp integral pentru controlul inițial | 6 h | 3 h |

Aceste valori sunt ipoteze inițiale pentru simulare și calibrare, vizibile în diagnostic.

Modelul reprezintă explicit efectul întârziat:

- Istoricul activării intră într-o coadă cu întârziere.
- După întârziere, alimentează o stare cu descreștere exponențială, care reprezintă persistența încălzirii.
- Variația temperaturii camerei este estimată din această stare și din pierderea termică locală.
- Starea reprezintă un indicator de aport cu efect întârziat, fără unități de energie.

Cu tur valid, activarea este ponderată cu diferența pozitivă tur–cameră, normalizată la condițiile de referință ale zonei și plafonată la 0–2. Referința se configurează; implicit se folosește ținta de tur a circuitului, dacă există. Fără referință sau fără tur valid se folosește activarea neponderată, cu încredere redusă. Temperatura sub ținta de tur poate contribui; atingerea țintei nu este condiție de pornire a contabilizării.

Pentru sursă comandată, contextul include pompa și cererea, fără a le interpreta drept confirmare de debit sau ardere. Pentru sursă independentă, se folosesc actuatorul și observațiile disponibile; nu se inventează o stare „sursă în funcțiune”.

### Calculul cererii și al impulsurilor

Până la validarea modelului, controlul adaptiv folosește cererea proporțională existentă, completată cu o integrală lentă pentru menținere:

- Integrală limitată la 0–1, actualizată numai cu temperatură proprie validă.
- Acumularea se suspendă la blocaje, lipsă de disponibilitate termică demonstrată sau saturare în sensul erorii.
- O eroare pozitivă nu produce automat escaladarea temperaturii de tur.
- Coborârea setpointului elimină cererea acumulată incompatibilă cu noua țintă.

După validarea modelului, se evaluează cereri între 0 și 100%, în pași de 5%, prin predicție pe orizontul profilului. Costul include:

- abaterea în afara benzii −0,2/+0,3°C;
- penalizare dublă pentru deficit față de depășire;
- variația cererii și numărul de porniri;
- aportul întârziat deja estimat.

Costurile termice folosesc abaterea pătratică integrată în timp. Penalizările pentru comutare și variație sunt parametri expliciți, calibrați în simulările de acceptare înainte de activarea live. La costuri egale se preferă păstrarea comenzii existente.

Cererea se transformă în impulsuri prin acumulare de timp solicitat:

- Cererile sub durata minimă se acumulează până justifică un impuls util.
- Se scade durata reală de activare, inclusiv prelungirile pentru funcționarea minimă și postcirculație.
- Soldul este limitat la durata maximă configurată a unui ciclu; nu se acumulează restanțe nelimitate.
- Blocajele, oprirea manuală și schimbarea setpointului invalidează soldul necorespunzător.
- Predicția se reevaluează la fiecare minut și înainte de un nou impuls. Nu se prelungesc automat comenzile până la atingerea țintei de tur.
- Limitele de pardoseală, ferestrele deschise și protecțiile existente au prioritate.

Planificatorul include durata minimă a sursei și postcirculația în evaluarea impulsului înainte de pornire. Evităm solicitările mici care ar deveni inevitabil un aport mult mai mare prin aceste prelungiri.

### Învățare

Învățăm întârzierea, persistența efectului, câștigul termic și pierderea locală din ferestre valide, păstrând parametrii pozitivi și limitele profilului.

Prima implementare folosește căutare pe o grilă de întârzieri și constante de timp, urmată de ajustarea câștigului și pierderii prin regresie cu constrângeri. Nu adăugăm o dependență de învățare automată.

Un model devine eligibil pentru control după minimum șapte zile valide, minimum trei secvențe informative de încălzire/pauză și îmbunătățirea erorii de predicție cu cel puțin 15% față de profilul inițial pe o perioadă ulterioară, exclusă din ajustare. Dacă datele nu disting suficient parametrii, păstrăm profilul inițial.

Excludem intervențiile manuale, senzorii invalizi, avariile suspectate și schimbările de configurație relevante. Perioadele după schimbarea setpointului pot alimenta modelul dinamic, dar nu învățarea necesarului obișnuit de menținere.

Învățarea zonelor rămâne distinctă de corecțiile curbei de tur. Sursele independente pot beneficia de modelul observațional al zonelor; învățarea curbei sursei păstrează cerințele existente.

## 3. Specificația pachetului ESPHome

Pachetul primește identificatorii pompei, modului, controlului manual, țintei și actuatorului. Exemplul `module1` păstrează identificatorii entităților existente.

### Măsurare și reglaj calm

- ADC cu interval explicit de 5 s.
- Temperatură brută disponibilă pentru diagnostic; temperatură de control cu mediană pe trei valori și EMA cu constantă de 30 s.
- Eliminarea cuantilei actuale din calea de control.
- Evaluarea regulatorului la 30 s; corecții normale numai după minimum 90 s de la ultima mișcare terminată.
- Decizia folosește media temperaturii din ultimele 120 s de circulație și tendința din aceeași fereastră.
- Bandă inițială ±2°C. Corecție de un punct procentual pentru abatere persistentă peste 2°C și două puncte peste 5°C.
- Se amână deschiderea dacă temperatura urcă deja spre bandă cu minimum 0,2°C/min; regulă simetrică pentru închidere.
- Parametrii sunt configurabili. Nu se introduce integrală sau PID în prima versiune.

Temperaturile din pauza pompei nu intră în media utilizată pentru reglaj.

### Secvența vanei

Stări explicite: `idle_closed`, `prepositioning`, `settling`, `regulating`, `manual`, `fault`; calibrarea la pornirea dispozitivului rămâne distinctă.

O poziție devine memorabilă după minimum cinci minute cu circulație, temperatură medie în banda țintei și fără corecții în ultimele două minute. Memorăm poziția, ținta și momentul.

La oprirea pompei se închide vana. La repornire:

- Poziția memorată se reutilizează numai în același mod, după o pauză de maximum 30 min și pentru o țintă diferită cu maximum 1°C.
- Revenirea are limita inițială de 30 puncte procentuale/minut.
- Fără poziție validă, pornirea folosește 10%, configurabil.
- Corecțiile normale încep după încheierea poziționării și minimum 120 s de măsurători cu circulație.
- Orice temperatură proaspătă peste limita superioară întrerupe revenirea.

La o temperatură peste țintă cu 8°C timp de 15 s, vana închide aportul cald, fără să oprească automat pompa. Limita absolută a circuitului este un parametru obligatoriu, stabilit din instalație înainte de instalare. Reluarea necesită temperatură validă sub pragul de declanșare cu cel puțin 2°C timp de 120 s.

Lipsa unei temperaturi valide timp de 30 s închide aportul cald și intră în `fault`. Intrarea în răcire, control manual sau calibrare invalidează reutilizarea poziției de încălzire.

### Coordonarea comenzilor

- Sincronizarea releului comun se execută după publicarea noilor stări ale cererilor, printr-un singur arbitru OR cu interblocarea răcirii.
- Diagnosticul numește explicit starea software a releului.
- Exercițiul anti-blocare și reglajul normal au acces exclusiv la actuator; exercițiul se abandonează la cerere reală.
- Protecția existentă la pierderea conexiunii HA se păstrează.
- Poziția memorată pentru pauze rămâne în RAM; după reboot se calibrează și se pornește conservator.

## 4. Configurare, persistență și diagnostic

Adăugăm configurarea strategiei pe intrare, profilul pe zonă și un bloc avansat de parametri. Importul/exportul păstrează configurațiile vechi; lipsa blocului nou înseamnă `legacy`.

Modelul validat și experiența se salvează separat pe intrare și zonă. La restart se restaurează parametrii, dar soldul impulsurilor se resetează; predicția activă așteaptă refacerea istoricului pe durata întârzierii plus trei constante de timp. Controlul inițial funcționează în acest interval.

Diagnosticul expune cererea de menținere, corecția de confort, aportul întârziat estimat, predicția, încrederea, soldul impulsurilor și motivul deciziei. În `observe`, arată separat propunerea și comanda reală. Nu prezintă rezultate contrafactuale drept confort obținut.

Actualizăm glosarul și ADR-urile pentru controlul cu memorie și învățarea observațională a zonelor. Specificația ESPHome se documentează împreună cu pachetul și cu exemplul de integrare.

## 5. Validare și activare

Testele deterministe și simulările folosesc instalații cu efect vizibil după 30–60 min, persistență îndelungată și sursă modulantă sau independentă.

Scenarii obligatorii:

- menținere, recuperare după deficit, modificarea setpointului și aporturi externe de căldură;
- sursă lentă, temperatură de tur oscilantă și lipsa senzorului de tur;
- impulsuri mici, durate minime, postcirculație și mai multe zone;
- goluri de date, restart, comandă manuală, blocaje și revenire la `legacy`;
- vană cu poziție memorată validă/expirată, schimbare de mod, depășire de tur și senzor invalid;
- oprirea ambelor cereri de gaz și exclusivitatea exercițiilor anti-blocare.

Acceptarea cere respectarea protecțiilor, lipsa acumulărilor nelimitate și lipsa comenzilor suplimentare în `observe`. Pe simulările de menținere, noul control trebuie să reducă deficitul ponderat fără să crească depășirile severe sau pornirile față de strategia existentă; se publică rezultatele pe fiecare scenariu.

Pachetul ESPHome trebuie validat și compilat pentru configurația `module1`. Testele software verifică temporizările, fără a pretinde validarea fizică a reglajului.

Ordinea de activare: observare → verificarea releului și instalarea controlată a ESPHome → reconstruirea observațiilor → activare adaptivă pe pardoseală → evaluare minimum șapte zile → extindere la radiatoare. Trecerea între etape este explicită. Limita absolută de tur și parametrii fizici ai actuatorului se verifică înainte de instalarea firmware-ului.
