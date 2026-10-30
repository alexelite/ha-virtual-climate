# Raport de simulare termică

Sunt păstrate inclusiv rezultatele nefavorabile. Acceptarea completă pentru activare live **nu este îndeplinită**.

Instalație sintetică: câștig 0.6°C/h, pierdere 0.45°C/h (0.15°C/h la sarcină mică), impuls minim 9 minute, pauză minimă 4 minute, ciclu legacy fix de 12 minute. Parametrii au un efect puternic asupra comparației; rezultatele nu sunt universale.

Deficitul este de două ori integrala pătratului abaterii sub setpoint−0.2°C; depășirea severă integrează pătratul abaterii peste setpoint+0.6°C, în °C²·h. Pragul de severitate este o convenție de simulare. Pornirile sunt tranziții ale actuatorului, fără confirmare de ardere.

| Scenariu | Deficit legacy / PI / după învățare | Depășire severă legacy / PI / după învățare | Porniri legacy / PI / după învățare | Acceptare PI |
| --- | --- | --- | --- | --- |
| maintenance_delay_30 | 2.331 / 16.530 / 15.698 | 0.000 / 0.000 / 0.000 | 360 / 89 / 93 | nu |
| maintenance_delay_60 | 20.694 / 29.178 / 24.535 | 0.000 / 0.000 / 0.000 | 360 / 80 / 85 | nu |
| maintenance_independent_no_supply | 9.226 / 21.475 / 19.535 | 0.000 / 0.000 / 0.000 | 360 / 84 / 94 | nu |
| maintenance_modulating_oscillating_supply | 70.186 / 23.340 / 21.576 | 0.000 / 0.000 / 0.000 | 356 / 88 / 82 | da |
| maintenance_radiator | 0.299 / 3.830 / 3.192 | 0.000 / 0.000 / 0.000 | 360 / 104 / 68 | nu |
| low_load_initial_pi | 0.000 / 3.028 / 3.091 | 0.000 / 0.028 / 0.016 | 127 / 92 / 92 | nu |
| recovery | 116.119 / 72.142 / 69.768 | 0.000 / 0.000 / 0.000 | 321 / 81 / 90 | scenariu funcțional |
| setpoint_decrease | 107.757 / 133.164 / 21.689 | 0.000 / 0.796 / 1.422 | 306 / 66 / 83 | scenariu funcțional |
| external_heat | 37.750 / 37.166 / 17.319 | 0.000 / 0.062 / 0.103 | 344 / 83 / 98 | scenariu funcțional |
| sensor_gap_restart_window | 162.865 / 54.785 / 44.431 | 0.000 / 0.000 / 0.000 | 247 / 52 / 57 | scenariu funcțional |

Etapa de după învățare include nouă zile de observații sintetice și refacerea istoricului după restaurare. Eligibilitatea și minutele predictive efective sunt în JSON. Un profil inițial deja exact nu poate demonstra o îmbunătățire de 15% și rămâne pe PI.

Legacy poate avea deficit aproape nul prin prelungirea impulsurilor mici la durata minimă. Reducerea pornirilor nu justifică declararea acceptării când deficitul sau depășirea severă cresc. Cazurile de setpoint și aport extern necesită și ele calibrare.

Protecțiile, contabilizarea limitată, persistența și lipsa comenzilor suplimentare în observe sunt verificate separat prin teste deterministe. Criteriile de confort pentru activare live nu sunt încă demonstrate pe toate cazurile. Penalizările 0.02/0.01 sunt explicite, dar nu sunt considerate calibrate pentru activare live.

Reproducere: `.venv/bin/python simulations/thermal_acceptance.py`. Datele sunt sintetice și nu reprezintă confort obținut în instalație. Compilarea ESP32 rămâne neverificată; firmware-ul nu a fost instalat.
