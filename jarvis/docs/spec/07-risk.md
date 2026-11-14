## 7. Riskmotorn (har vetorätt över allt)

Varje order passerar risk-engine. Om en kontroll fallerar stoppas ordern och händelsen loggas.

**Per affär**
- Positionsstorlek via volatilitetsmål (ATR eller realiserad volatilitet). Max **0,75 % av kapitalet i risk** per affär (avståndet till stop × antal).
- Om Kelly används: högst **¼ Kelly**, och aldrig över ovanstående tak.
- Varje position har en stop-loss och ett exit-villkor från start. Stoppen läggs **hos mäklaren** (bracket/OCA-order) så att den gäller även om servern går ner.

**Per portfölj**
- Max 10 % av kapitalet i en enskild position (5 % för krypto, 5 % för Small Cap)
- Max 25 % per sektor, max 15 % totalt i krypto, max 20 % totalt i råvaror
- Korrelationskontroll: korrelerade positioner räknas samman som en risk
- Bruttoexponering ≤ 100 % (ingen belåning som standard)
- Kassareserv på minst 5 %

**Stoppregler (circuit breakers)**
- Dagsförlust ≥ 2 % → inga nya affärer resten av dagen
- Veckoförlust ≥ 4 % → bara stängningar tills nästa vecka
- Drawdown från toppen ≥ 10 % → **Kill switch**: alla nya affärer stoppas och Adam måste aktivt starta igen i appen
- Fler än N fel i rad mot mäklaren, saknad eller gammal data, klockavvikelse, eller att positionerna inte stämmer mot mäklaren → stoppa handeln och larma

**Omsättningsbudget (mot överhandel)**
- Max antal affärer per vecka och max årlig omsättning (som standard 10× kapitalet), justerbart per strategi
- Varje affär måste ha en förväntad nettovinst som klart överstiger de beräknade kostnaderna (standard ≥ 2× kostnaden), annars skippas den.

**Gap- och extremrisk**
- En stop-loss garanterar inte priset. Vid gap (t.ex. över natten eller efter rapport) kan förlusten bli större. Positionsstorlek räknas därför även på ett "gap-scenario" (t.ex. −25 % för enskild aktie, −40 % för krypto), och ingen enskild position får kunna ge mer än 3 % förlust av kapitalet i det scenariot.
- Stresstesta portföljen dagligen mot historiska krascher (2008, mars 2020, 2022 och flashkrascher) och visa resultatet i Risk-vyn.

**Ordersäkerhet**
- "Fat finger"-skydd: max ordervärde, max avvikelse från senaste kurs, max antal order per minut och dag
- Handla inte de första och sista 5–10 minuterna av handelsdagen (justerbart), och inte i auktioner om inte strategin uttryckligen kräver det
- Valfritt rapportskydd: ingen ny position X dagar före rapport om inte strategin bygger på rapporter
- Kontrollera handelsstatus (stoppad, auktion) innan en order skickas

Alla gränser ovan är **standardvärden**. Adam styr dem själv via kapitalkontrollen i §7.1.

### 7.1 ⭐ Kapitalkontrollen — Adam bestämmer hur mycket Jarvis får använda

Adam ska kunna ändra hur mycket kapital Jarvis använder, både totalt och per affär, smidigt och snyggt. Systemet ska hjälpa honom att förstå vad valet betyder i **kronor**, inte stoppa honom.

**Tre reglage (på Hem-skärmen via ett tryck på "Jarvis budget", och i Inställningar)**

1. **Jarvis budget** — hur mycket av kontot Jarvis får förvalta
   - Ett stort, mjukt reglage i iOS-stil med värdet både i **kr och %**. Det snäpper fast vid 10 / 25 / 50 / 75 / 100 % med en lätt "klick"-animation, och man kan skriva in exakt belopp.
   - Det som inte är Jarvis budget ligger kvar i index-ETF:en eller som kontanter (Adam väljer i §1.5).
2. **Insats per affär**
   - Fyra lägen som stora knappar: **Liten · Normal · Stor · Egen**. Varje läge visar direkt: "Max per affär: ca 8 000 kr" och "Om stoppen slår förlorar du ca 600 kr".
   - "Egen" öppnar finjustering: max positionsstorlek (% eller kr) och risk per affär (%).
3. **Fördelning mellan motorer** (valfritt, för den som vill)
   - En stapel med dragbara fält som delar budgeten mellan Swing, Daytrading, Politikersignaler (§5.4), Krypto och Råvaror. Dra för att ändra, och totalen blir alltid 100 %.

**Förhandsvisning medan Adam drar i reglagen (det viktiga)**
Ett kort under reglagen som uppdateras i realtid, beräknat från riskmodellen och stresstesterna:
- "En vanlig dålig dag (1 av 20): **−2 300 kr**"
- "En dålig månad (1 av 20): **−9 800 kr**"
- "Om mars 2020 hände igen: **−24 000 kr**"
- "Förväntat spann på ett år (90 %): från **−15 %** till **+X %**", baserat på backtest och live-resultat, med en tydlig osäkerhetsmarkering när live-historiken är kort
- **Jarvis rekommendation:** "Utifrån 47 dagars live-resultat rekommenderar jag max 25 % just nu." Det visas som ett diskret märke på reglaget. Adam kan välja högre, men ser då en gul markering och en kort förklaring.

**Regler för ändringar (smidigt, men säkert)**
- **Sänka** gäller **direkt** och kräver inget extra. Jarvis minskar positionerna i lugn takt, eller direkt om Adam väljer "Minska nu".
- **Höja** kräver Face ID/passkey och ett bekräftelsekort som visar förhandsvisningen ovan. Höjningen börjar gälla från nästa handelsdag. Mer än en fördubbling på en gång ger 24 timmars betänketid som standard (kan stängas av i Avancerat).
- Varje ändring loggas med datum, gammalt och nytt värde, så att Adam kan se hur hans val har påverkat resultatet.
- I chatten (§9.2.1) kan Adam säga "visa min budget" eller "jag vill ändra insatsen", och Jarvis öppnar då reglagen. Själva höjningen bekräftas alltid i reglaget med Face ID.

**Tekniska maxgränser** (finns kvar för att skydda mot buggar och felklick, och är tydligt markerade som sådana i appen)
- En enskild aktie: max 25 % av Jarvis budget. Krypto totalt: max 40 %. Ingen belåning om Adam inte slår på det i Avancerat (där också ISK-reglerna gäller).
- Circuit breakers och kill switch i §7 kan inte stängas av, men deras procentnivåer kan justeras inom rimliga intervall.

---

