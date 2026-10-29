---
status: accepted
---

# Separarea compensării climatice de reglajul local al turului

Modulul de compensare climatică din Virtual Climate calculează temperatura țintă de tur din condițiile exterioare și interioare și o transmite dispozitivului care realizează reglajul local. Prima etapă acoperă încălzirea; răcirea va fi tratată ulterior. Această decizie extinde strategia cu ținte fixe descrisă în README. Implementarea inițială și profilul configurabil de calibrare sunt descrise în [ghidul de utilizare](../supply-control.md).

Pentru instalațiile radiante cu inerție mare, evaluarea urmărește comportamentul pe o perioadă relevantă, fără a cere urmărirea strictă a țintei în fiecare moment. Oscilațiile în jurul țintei pot fi acceptabile; exemplul discutat este o țintă de 33°C cu valori de aproximativ 32–34°C. Exemplul nu stabilește o toleranță sau o fereastră de timp universală.

Modulul trebuie să poată detecta abateri persistente și să semnaleze posibile avarii în limita senzorilor disponibili, fără să preia reglajul local. Separarea păstrează reglajul dependent de echipament în dispozitiv, iar calculul țintei și supravegherea în integrare. O cerere de funcționare emisă de integrare nu confirmă funcționarea efectivă.

Învățarea și monitorizarea activă a răspunsului sunt condiționate inițial de controlul cererii de încălzire de către Virtual Climate. Perioadele de evaluare folosesc contextul cererilor emise. Calculul curbei este o funcție distinctă; prezența lui nu este suficientă pentru activarea învățării sau monitorizării. Avariile suspectate suspendă învățarea, pentru ca o problemă de funcționare să nu fie încorporată în curba învățată. Criteriile și ferestrele exacte de evaluare rămân de stabilit.

Lipsa răspunsului termic produce inițial diagnostic și notificare, fără oprirea automată a încălzirii. Învățarea bazată pe observațiile suspecte se suspendă, iar escaladarea nejustificată a boostului se oprește. Încălzirea continuă în limitele configurate, cu prioritate pentru protecțiile existente. Notificarea separă observația de cauzele posibile; de exemplu, un răspuns insuficient poate justifica verificarea debitului, dar nu confirmă singur un debit insuficient.

Inițial, o abatere termică suspectă într-o zonă eligibilă suspendă învățarea întregii curbe de tur comune. Corecțiile validate se păstrează, încălzirea continuă și zona rămâne vizibilă în evaluarea confortului și în diagnostic. Regula evită optimizarea curbei doar pentru camerele fără probleme și va fi reevaluată pe baza funcționării reale.

Învățarea se poate relua automat după o perioadă de funcționare cu date valide și răspuns termic acceptabil, nu după o singură măsurătoare bună. Confirmarea notificării nu șterge condiția tehnică. Înghețarea manuală a învățării rămâne disponibilă și nu este anulată de această reluare automată. Durata și criteriile numerice ale perioadei de revenire rămân de calibrat.

## Transmiterea țintei

Indisponibilitatea entității țintă sau eșecul apelului de scriere reprezintă o problemă de comandă, distinctă de lipsa răspunsului termic. Pe durata problemei se suspendă probele și învățarea, se reîncearcă transmiterea la intervale controlate și se semnalează eroarea.

Înaintea unei porniri noi a sursei, integrarea așteaptă transmiterea cu succes a țintei. Dacă instalația funcționează deja, eroarea de transmitere nu provoacă singură oprirea automată; protecțiile existente rămân active. Succesul transmiterii nu confirmă realizarea temperaturii solicitate, care se evaluează separat în timp, numai dacă există senzor de tur.
