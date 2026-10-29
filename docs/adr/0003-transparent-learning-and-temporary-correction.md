---
status: accepted
---

# Învățare transparentă, distinctă de corecțiile temporare

Compensarea climatică combină o curbă de bază dependentă de exterior, o corecție lentă învățată din răspunsul interior și un boost temporar asociat unui deficit mare față de setpoint. Cauze precum revenirea din vacanță sau o avarie nu definesc mecanisme distincte de recuperare; diagnosticul trebuie să poată distinge situațiile în care o creștere a țintei este justificată de cele care indică o problemă.

Boostul și învățarea sunt mecanisme separate. Boostul nu modifică punctele curbei și nu se transferă automat în corecția învățată, nici prin simpla persistență, nici prin repetare. Învățarea își justifică modificările prin propriile criterii de evaluare. În implementarea inițială, boostul activ suspendă actualizarea învățării; tendințele camerelor rămân disponibile pentru recuperare și monitorizare.

Boostul ține cont de deficitul față de setpoint și de ritmul recuperării în perioade relevante de activare a actuatorului. Suplimentul temporar este plafonat, poate crește când recuperarea este insuficientă și se retrage gradual pe măsură ce deficitul scade. Lipsa răspunsului așteptat la supliment conduce la evaluarea unei posibile avarii, nu la creșteri repetate fără justificare. Pragurile, ferestrele de evaluare și ratele de modificare rămân de stabilit.

Învățarea poate corecta ținta atât în jos, cât și în sus, deoarece curba inițială poate fi nepotrivită. Vizualizarea trebuie să distingă ținta indicată de curba de bază de ținta rezultată după învățare și de contribuțiile temporare, pentru ca utilizatorul să poată înțelege diferențe precum 35°C din curbă față de 32°C solicitate după o perioadă de funcționare. Exemplele exprimă transparența cerută, nu parametri prestabiliți.

Învățarea urmărește optimizarea și corectarea setărilor nepotrivite. Pentru încălzire, obiectivul este cea mai mică temperatură de tur care poate menține confortul cerut, evaluată în contextul funcționării. Corecția trebuie să poată diferi între condiții exterioare diferite: o pantă prea lină sau prea abruptă nu poate fi reparată întotdeauna prin aceeași deplasare a întregii curbe.

Învățarea poate face mici reduceri de probă ale turului când camerele își mențin confortul. Probele sunt reversibile, se fac în condiții suficient de stabile, fără recuperare activă sau suspiciune de avarie, și lasă timp pentru observarea răspunsului. Reducerea se păstrează dacă rezultatul este acceptabil; la deteriorarea persistentă a confortului se revine la valoarea anterioară înainte de o nouă probă. Pașii, timpii și criteriile numerice rămân de stabilit.

Pentru corectarea unei curbe prea joase, învățarea poate face și mici creșteri de probă ale punctului relevant, în prezența unui deficit persistent, a unei activări suficiente a actuatorului și a condițiilor potrivite evaluării. Modificarea se păstrează dacă observațiile susțin îmbunătățirea confortului; în caz contrar se revine și se reevaluează cauza. Acesta este un mecanism propriu al învățării, distinct de boost, iar recuperarea prin boost își păstrează prioritatea.

Dacă în timpul unei probe apare necesitatea recuperării prin boost, proba se întrerupe și se revine la corecția validată anterior. Recuperarea are prioritate. O probă întreruptă nu este considerată reușită; schimbarea setpointului sau a condițiilor nu reprezintă automat dovada că reducerea turului a fost greșită.

Evaluarea urmărește fiecare zonă eligibilă; o medie bună nu trebuie să ascundă deficitul persistent al unei camere. Acest deficit contează pentru reglarea țintei, dar nu justifică singur creșteri repetate: trebuie evaluat și răspunsul camerei. O notificare poate orienta utilizatorul către verificări fizice, inclusiv reglarea manuală a debitului. Deficitul nu confirmă singur un debit insuficient.

Necesarul de boost se calculează separat pentru fiecare zonă eligibilă, iar turul comun folosește cea mai mare nevoie validă, plafonată. Diagnosticul identifică zona care determină ținta și explică motivul. O deteriorare persistentă a confortului într-o singură zonă eligibilă poate respinge o reducere de probă a turului. O zonă cu răspuns suspect declanșează regulile de diagnostic și suspendare stabilite, fără escaladarea repetată și nejustificată a țintei.

Învățarea folosește contextul cererii controlate de integrare, conform ADR 0001. Evaluarea include activitatea raportată a actuatoarelor împreună cu deficitul și tendința temperaturii camerelor. O zonă fără activare relevantă nu justifică prin simplul ei deficit o corecție a curbei. Starea electrică a actuatorului nu confirmă debitul; delimitarea perioadelor relevante și tratarea răspunsului întârziat după închidere rămân de stabilit.

Utilizatorul poate folosi numai curba de bază, activa învățarea și aplicarea corecțiilor, îngheța învățarea păstrând corecțiile sau reseta explicit corecțiile fără a pierde curba de bază. Corecțiile și experiența acumulată se păstrează la repornirea Home Assistant.

La repornire se restaurează corecțiile validate și experiența acumulată. O probă aflată în desfășurare este marcată întreruptă și se revine la ultima corecție validată; o probă nouă așteaptă observații noi. Intervalul în care integrarea nu a funcționat nu este tratat ca observație validă.

Aceste politici sunt reguli inițiale, de reevaluat pe baza funcționării reale. Evaluarea trebuie să poată folosi rezultatele și motivele întreruperii probelor, motivele și durata suspendărilor învățării, evoluția corecțiilor și confortul fiecărei zone. Acceptarea proiectării nu echivalează cu validarea comportamentului în instalație; pragurile și temporizările necesită calibrare și verificare în timp.

## Modelul punctelor

Numărul punctelor este configurabil de utilizator, cu minimum două și implicit cinci. Punctele se distribuie uniform între capetele intervalului exterior configurat. Numărul punctelor determină și rezoluția învățării; nu se modifică automat. Fiecare punct păstrează valoarea de bază, corecția învățată și experiența acumulată.

Observațiile sunt atribuite punctului cel mai apropiat, folosind intervalele delimitate de mijloacele distanțelor către vecini. Ținta se obține prin interpolare liniară între valorile corectate ale punctelor vecine. Astfel, atribuirea observațiilor este locală, iar influența corecției asupra țintei se întinde până la punctele vecine, fără salt la mijlocul intervalului.

Pentru încălzire, curba de bază împreună cu corecțiile învățate nu poate cere un tur mai mic atunci când exteriorul devine mai rece; segmentele plate sunt permise. Corecțiile locale care ar încălca această proprietate se limitează, cu motivul limitării vizibil în diagnostic. Boostul este separat de această constrângere asupra formei curbei. Limitele minime și maxime configurate ale turului se aplică țintei finale, inclusiv contribuției boostului.

Modificarea manuală a valorii de bază a unui punct resetează corecția și experiența acelui punct. Schimbarea numărului de puncte sau a intervalului exterior resetează învățarea întregii curbe. Efectul resetării este explicat înainte de salvarea configurației.

În afara intervalului exterior configurat, curba continuă prin extrapolarea liniară a segmentului de capăt, folosind valorile corectate ale punctelor, până la limitele minime și maxime ale turului. Limitele se aplică și țintei finale, după boost. Învățarea se suspendă în afara intervalului; boostul și monitorizarea rămân disponibile dacă sunt îndeplinite cerințele lor. Diagnosticul indică depășirea intervalului și posibilitatea extinderii lui dacă asemenea condiții sunt frecvente. La mijlocul exact al unui interval, observația este atribuită punctului cu temperatura exterioară mai rece.

Modele existente consultate: [Danfoss ECL, aplicația A266, secțiunea 5.2](https://assets.danfoss.com/documents/latest/186033/AQ156586461753en-010601.pdf) permite șase coordonate ale curbei la temperaturi exterioare predefinite; [NIBE S1155, meniurile 1.30.7–1.30.8](https://installer.nibe.eu/download/18.7a0d4d117d0b32b7fde0a/1637152120208/S1155%20Installer%20Manual.pdf) permite o curbă proprie și o corecție locală în jurul unui punct exterior, pe ±5°C. Aceste exemple susțin folosirea punctelor și corecțiilor locale, fără să stabilească algoritmul de învățare al proiectului.

Algoritmul inițial și profilul numeric configurabil sunt descrise în [ghidul de utilizare](../supply-control.md). Ferestrele, pragurile și ratele rămân supuse calibrării pe instalația reală. Separarea corecției învățate de cea temporară permite explicarea rezultatului fără a confunda recuperarea unui deficit cu necesarul obișnuit al clădirii.
