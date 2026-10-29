---
status: accepted
---

# Încălzire oportunistă cu temperatură de avarie

O zonă fără măsurare poate folosi mediana temperaturilor reale ale instanței
pentru a calcula deschiderea actuatorului, păstrând indisponibilă temperatura
afișată. Numai zonele măsurate solicită sursa și determină ciclul; zona pe
avarie primește căldură în ferestrele lor de funcționare. Această separare
păstrează utilitatea setpointului fără a trata estimarea drept observație.

Funcția este opțională și exclusiv pentru încălzire. Fallbackul nu participă
la boost sau monitorizarea răspunsului camerei; suspendă învățarea curbei
comune, continuând politica prudentă din ADR 0001–0003. Senzorii reali pot
continua să determine boostul. În lipsa tuturor măsurătorilor nu există
cerere de funcționare. Detaliile sunt în [ghid](../temperature-fallback.md).
