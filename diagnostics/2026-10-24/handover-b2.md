# Corecția transferului între zone — 0.1.1b2

## Problema și comportamentul nou

Verificarea de la 16:38 a găsit 13 porniri ale releului sursei de 30–32 s.
La schimbarea sloturilor, închiderea căii vechi preceda confirmarea celei noi,
iar protecția `no_flow` întrerupea sursa. Pornirea sursei fusese deja întârziată
de repausul minim, deci aceasta avea numai aproximativ 30 s de funcționare.

Coordinatorul păstrează acum calea veche validă până când o cale dorită nouă
raportează `on` și trece timpul său `open_s`. Deschiderile sunt comandate
înaintea închiderilor. Replanificarea la limita ciclului lasă această decizie
reconciliatorului, astfel încât nu închide anticipat ultima cale a sursei.

Așteptarea transferului este limitată la maximum `open_s` al înlocuitorilor
plus 30 s pentru confirmare. Dacă nu există un înlocuitor pregătit până atunci,
se solicită oprire controlată cu motivul `handover_timeout`, păstrând calea
veche validă pentru minimumul sursei și postcirculație. Calea veche blocată de
siguranță sau indisponibilă nu este menținută artificial; pierderea ultimei
căi deschise oprește sursa și pompa imediat.

Diagnosticul existent `plant_flow_hold` include atât transferul, cât și oprirea.
Noul atribut `plant_flow_hold_reason` distinge `handover`, `stopping` și `null`.
Confirmarea electrică și `open_s` estimează pregătirea căii; poziția vanei și
debitul nu sunt măsurate direct.

## Verificări înainte de instalare

Reproducerea anterioară a fost reluată înaintea corecției și a eșuat cu aceeași
oprire la 30 s. Cele patru teste noi care disting defectul au eșuat pe codul
anterior: confirmare întârziată, deschidere mecanică, transfer la limita
ciclului și expirarea așteptării. Testul pentru blocaj real verifică păstrarea
protecției, care funcționa deja.

După corecție:

```text
python3 diagnostics/2026-10-24/reproduce_handover.py
PASS: immediate feedback control
PASS: planned handover retains a confirmed path

/tmp/ha-virtual-climate-diag-venv/bin/python -m unittest discover -s tests -v
Ran 53 tests
OK
```

Cele 7 teste adăugate verifică:

- Confirmare întârziată și 60 s deschidere după confirmare.
- Confirmare imediată, cu păstrarea timpului de deschidere mecanică.
- Continuitate la limita ciclului.
- Înlocuitor fără confirmare: expirare, minimum sursă și postcirculație.
- Blocaj de siguranță al căii vechi în timpul transferului.
- Pierderea căii vechi înainte ca noua vană să fie pregătită.
- Două ore simulate cu trei zone, cerere variabilă și confirmări întârziate:
  niciun interval complet ON al sursei sub 300 s și nicio sursă pornită fără
  o cale confirmată și cu timpul de deschidere trecut.

Compilarea Python, sintaxa scriptului de instalare și `git diff --check` au
trecut. Nu au fost adăugate mesaje temporare de instrumentare în producție.

## Instalare și verificare pe homerha

Instalarea efectivă prin `dev/sync.sh` a trecut toate cele 53 de teste,
verificarea SHA-256, importurile în containerul HA real și verificarea
configurației. Core a repornit și scriptul a confirmat noul proces/API:

- Versiune instalată: `0.1.1b2`, anterior `0.1.1b1`.
- SHA-256: `d03d12ba0c3bd42bbc9759de378d05b8537243e804e425f87df760fc81ae7a8e`.
- Backup: `/config/virtual_climate_backups/20261024T135403Z-86622/`.
- Rezultat: `installed`, `restart_confirmed: true`.
- Noul manager pornește la 16:55:35.807, Europe/Bucharest.

Citirile MCP de după restart confirmă intrarea `loaded`, cele 10 zone și
opțiuni identice cu cele de dinaintea instalării. Noah păstrează asocierea
de pardoseală nulă și diagnosticul `no_floor_sensor`. Atributul nou
`plant_flow_hold_reason` este prezent în stările live.

La 16:57:08 există zero neconcordanțe și zero actuatoare indisponibile în
diagnosticul global. Nu apar erori de execuție ale integrării în citirile
de după restart; logul brut include avertizarea generică HA pentru integrare
custom, distinctă de o eroare de funcționare.

Cererea este foarte mică. O cerere de 0,01 în Shared Bathroom începe la
16:56:42, apoi dispare la 16:57:02. Managerul anulează pornirea în timp ce
așteaptă repausul minim; releul sursei rămâne oprit. Zona este păstrată
pentru temporizările normale, cu motivul diagnostic `stopping`.

Nu a avut loc un transfer natural între zone în această fereastră scurtă
de după restart. Transferul și protecțiile sunt confirmate de testele
deterministe pe codul de producție; confirmarea în mai multe cicluri reale
rămâne o verificare ulterioară, nu un rezultat pretins al acestei instalări.
Nicio țintă de temperatură nu a fost modificată pentru a forța un transfer.

Metadatele și captura verificării sunt în directorul ignorat de Git:
`local/deployments/20261024T135403Z-86622-verification.json`.

Revenire la codul salvat înaintea acestei instalări:

```bash
bash dev/sync.sh --host ha --config-root /config --rollback 20261024T135403Z-86622
```

Revenirea codului păstrează configurația HA; nu rescrie `.storage`.
