---
status: accepted
---

# Strategii de tur independente pe mod și cerințe specifice fiecărei funcții

Strategia de tur se selectează separat pentru încălzire și răcire. Temperatura constantă poate fi aleasă inclusiv când există senzori pentru compensare climatică; compensarea climatică necesită temperatura exterioară actuală. Implementarea inițială a compensării acoperă încălzirea, iar răcirea păstrează ținta constantă până la etapa dedicată ei.

Strategia cu temperatură constantă păstrează ținta configurată, fără corecții automate prin învățare sau boost. Monitorizarea poate rămâne activă dacă sunt îndeplinite cerințele ei de date și control.

Senzorul temperaturii efective de tur este opțional pentru compensarea climatică, dar necesar pentru verificarea realizării țintei de tur. Calculul diferenței tur–retur necesită ambii senzori. Estimarea puterii din debit și diferența tur–retur, apoi integrarea energiei, sunt extensii viitoare.

Fiecare funcție are cerințe explicite de date și, unde este necesar, de control. Lipsa datelor necesare împiedică funcția respectivă, fără să impună aceleași cerințe tuturor celorlalte funcții.

| Funcție | Date și condiții necesare | Rolul senzorilor opționali |
| --- | --- | --- |
| Calculul țintei constante | Valoarea configurată pentru modul activ | Nu necesită senzor exterior sau de tur |
| Calculul compensării climatice | Temperatură exterioară validă, curba și limitele turului | Senzorul de tur nu este obligatoriu |
| Transmiterea țintei | Entitate țintă disponibilă și apel de scriere reușit | Măsurarea turului nu confirmă transmiterea comenzii și se evaluează separat |
| Boost după răspunsul zonelor | Compensare climatică activă, fără funcționare pe ținta de rezervă; temperaturi și setpointuri ale zonelor eligibile, istoric suficient pentru tendință, activitatea raportată a actuatoarelor și contextul cererii controlate de integrare | Turul măsurat poate îmbunătăți diagnosticul |
| Învățarea corecțiilor | Datele relevante ale zonelor și activării, exterior valid în intervalul configurat, condiții de probă valide și controlul cererii de către integrare | Turul măsurat nu este obligatoriu; absența lui limitează concluziile despre temperatura efectiv livrată |
| Monitorizarea răspunsului camerelor | Temperaturi, setpointuri, activitate relevantă a actuatoarelor și cerere controlată de integrare | Turul și returul pot ajuta la explicarea abaterii |
| Verificarea realizării țintei de tur | Senzor de tur valid, ținta solicitată și context valid de funcționare controlată | Returul nu este obligatoriu |
| Calculul diferenței tur–retur | Senzori valizi de tur și retur | Interpretarea ca posibilă avarie necesită context de funcționare |
| Estimarea puterii și energiei | Extensie viitoare bazată pe debit și diferența tur–retur | Modelul de calcul și cerințele complete vor fi stabilite în acea etapă |

Validitatea numerică și temporală a datelor și profilul inițial al ferestrelor de observație sunt descrise în [ghidul de utilizare](../supply-control.md). Matricea consemnează dependențele funcțiilor; calibrarea se verifică în timp pe instalație.

La pierderea temperaturii exterioare valide, un mod configurat cu compensare trece temporar la o țintă constantă de rezervă, configurată explicit. Învățarea și boostul sunt suspendate, astfel încât ținta de rezervă rămâne strict constantă. Monitorizarea poate continua dacă are datele și contextul de control necesare. Starea de rezervă este vizibilă și nu este prezentată drept compensare climatică validă. La revenirea datelor valide se reia calculul curbei, iar învățarea așteaptă refacerea observațiilor necesare.
