# Temperatură de avarie per instanță

Opțiunea **Încălzire cu temperatura de avarie a instanței** se activează din
opțiunile integrării, în **Setări Globale**. Implicit este dezactivată.
În importul/exportul JSON cheia este `global.instance_temperature_fallback`,
cu valoarea booleană `true` sau `false`.

Când un senzor de cameră lipsește, zona poate folosi intern mediana
temperaturilor primare valide ale aceleiași instanțe. Pentru un număr par
de senzori se face media celor două valori centrale. Un senzor partajat de
mai multe zone este numărat o singură dată. Se folosesc numai zone compatibile
cu încălzirea; zonele oprite manual pot furniza în continuare măsurători reale.
Valorile estimate nu reintră în calcul. Observațiile interne mai vechi de
120 de secunde sunt respinse; la fiecare evaluare termică sunt citite din nou
sursele. Dispozitivele trebuie să raporteze indisponibilitatea senzorilor:
o valoare numerică înghețată în sursa HA nu dovedește că senzorul este sănătos.

Temperatura măsurată afișată de card rămâne indisponibilă. Setpointul rămâne
editabil și controlează proporția solicitată de deschidere a actuatorului.
Exemplu: mediana este 21°C; la setpoint 22°C zona cere încălzire, iar la 20°C
nu cere. Aceasta nu confirmă temperatura reală a camerei defecte.

Numai zonele cu temperatură măsurată pot solicita sursa, determina durata
ciclului și raportul agregat de cerere. Zonele pe avarie se alătură după
pornirea sursei și numai în ferestrele active ale zonelor măsurate. Ele nu
deplasează sloturile acestora în modul eșalonat și nu prelungesc cererea
sursei. Protecțiile existente de timp minim, circulație și post-funcționare
se păstrează; o cale deja deschisă poate fi reținută pentru oprirea sigură.
Nu există garanția livrării întregului timp cerut de o zonă pe avarie.

Dacă nu există nicio temperatură validă sau nicio zonă măsurată nu cere
căldură, fallbackul nu pornește instalația. Instanțele sunt independente:
cererea radiatoarelor nu activează fallbackul pardoselii. La revenirea
senzorului primar se reia automat controlul măsurat la următoarea evaluare.
OFF, ferestrele deschise, limitele de pardoseală și indisponibilitatea
actuatorului își păstrează efectele. Fallbackul nu se aplică la răcire.

Zonele pe avarie sunt excluse din boost și din diagnosticul răspunsului
termic al camerelor. Învățarea curbei comune este suspendată cât timp există
fallback activ; corecțiile validate se păstrează, iar o probă se întrerupe.
Boostul poate continua pentru camerele cu măsurători reale.

Atributele fiecărei entități climate includ `temperature_source`
(`measured`, `instance_fallback`, `unavailable`), `control_temperature`,
`fallback_donor_count` și `fallback_limited_by_plant_demand`.
Durata efectivă se verifică în istoricul actuatorului; starea electrică
nu confirmă debitul sau livrarea căldurii.

Această funcție este destinată perioadei până la repararea senzorului.
Mediana celorlalte camere poate supraîncălzi sau subîncălzi camera defectă.

## Salvarea opțiunilor și reîncărcarea

Salvarea opțiunilor reîncarcă instanța. În acest interval integrarea oprește
ieșirile, apoi reia cererea validă, respectând timpul minim de repaus și
întârzierile pompei/sursei. Fallbackul nu elimină aceste temporizări.

Feedbackul ESPHome poate ajunge înainte de încheierea apelului de comandă HA.
Oprirea de urgență `no_flow` aflată în curs trebuie lăsată să se termine;
feedbackul repetat nu trebuie să o anuleze și să o relanseze. O oprire normală
poate fi escaladată o singură dată la `no_flow` dacă se pierde circulația.
Regresia este verificată în testul
`test_startup_recovery_finishes_with_delayed_service_feedback`, care simulează
feedbackul înainte de finalizarea apelurilor și verifică reluarea sursei.
