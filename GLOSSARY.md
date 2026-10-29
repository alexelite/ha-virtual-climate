# Virtual Climate

Controlul încălzirii și răcirii radiante pe zone, cu o temperatură de tur comună.

## Language

**Temperatură de avarie**:
Referință termică estimată din camerele măsurate ale aceleiași instalații,
folosită temporar pentru o zonă fără măsurare proprie.

**Încălzire oportunistă**:
Încălzirea unei zone numai în perioadele solicitate de alte zone, fără ca
zona respectivă să emită propria cerere de funcționare a sursei.

**Compensare climatică**:
Ajustarea temperaturii țintă de tur în funcție de necesarul termic, ținând cont atât de temperatura exterioară, cât și de starea termică interioară.

**Temperatură țintă de tur**:
Temperatura dorită a agentului termic trimis spre circuitele radiante. Este distinctă de temperatura efectivă de tur și de temperatura dorită în încăpere.

**Temperatură efectivă de tur**:
Temperatura măsurată a agentului termic trimis spre circuitele radiante.

**Setpoint de cameră**:
Temperatura dorită a aerului într-o zonă.

**Boost de recuperare**:
Creșterea temporară a temperaturii țintă de tur ca răspuns la un deficit mare față de setpointul de cameră, indiferent de cauza deficitului; este distinctă de corecția învățată. Existența deficitului nu stabilește singură dacă este necesar un boost sau dacă există o avarie.

**Curbă climatică de bază**:
Relația de referință dintre temperatura exterioară și temperatura țintă de tur, înaintea corecțiilor învățate și temporare.

**Corecție învățată**:
Ajustarea dedusă din comportamentul termic observat în timp, prin care ținta de tur poate fi mai mică sau mai mare decât cea indicată de curba de bază. Corecția poate diferi în funcție de temperatura exterioară.

**Punct al curbei**:
Pereche formată dintr-o temperatură exterioară de referință și temperatura de tur corespunzătoare. Valoarea de bază și corecția învățată a punctului sunt distincte.

**Interval de învățare al punctului**:
Intervalul de temperatură exterioară delimitat de mijloacele distanțelor către punctele vecine, folosit pentru atribuirea observațiilor punctului apropiat. Acesta nu delimitează influența punctului asupra țintei interpolate.

**Strategie de tur**:
Modul de stabilire a temperaturii țintă de tur: temperatură constantă sau compensare climatică. Strategia este aleasă distinct pentru încălzire și răcire.

**Țintă constantă de rezervă**:
Temperatura de tur configurată explicit pentru perioadele în care compensarea climatică selectată nu are o temperatură exterioară validă.

**Cerere de funcționare**:
Comanda prin care integrarea solicită funcționarea instalației. Emiterea cererii nu confirmă funcționarea efectivă sau livrarea căldurii.

**Reglaj local al turului**:
Reglajul efectuat de dispozitivul instalației pentru a aduce temperatura efectivă de tur în jurul țintei primite.
