---
status: accepted
---

# Control cu memorie și învățare observațională a zonelor

Calculul cererii de încălzire poate folosi istoricul activării raportate a
actuatorului, cu întârziere și persistență explicită. Alegem un model simplu,
identificabil prin grilă și regresie cu constrângeri, în locul escaladării
automate a turului sau a unei dependențe ML. Indicatorul de aport nu este energie.

Învățarea observațională a zonei este distinctă de învățarea curbei sursei:
poate folosi o sursă independentă fără să inventeze confirmarea funcționării
acesteia. Aceasta extinde delimitarea din ADR 0001–0003 numai pentru modelul
zonei; cerințele de control pentru învățarea curbei de tur rămân valabile.

Configurațiile existente rămân `legacy`; `observe` învață exclusiv din
comenzile reale și nu intervine în ele. `adaptive` este explicit. Predicția
necesită șapte zile valide, trei secvențe informative încălzire/pauză și
minimum 15% îmbunătățire pe date ulterioare, excluse din ajustare. Până atunci
se folosește control proporțional cu integrală lentă. Modelul persistă separat
pe intrare și zonă; soldul impulsurilor și istoricul activ se reconstruiesc
la restart. Protecțiile au prioritate față de orice propunere.

Vana pardoselii aparține exclusiv regulatorului ESPHome local. Poziția stabilă
memorată există numai în RAM; după reboot calibrarea precede orice reglaj.
[Specificația aprobată](../adaptive-control-plan.md) și
[ghidul implementării](../adaptive-control.md) descriu parametrii și validarea.
