## 11. Drift och övervakning

- **Watchdog** som startar om tjänster, larmar om heartbeat saknas, och stoppar handeln om något kritiskt är nere
- Hälsokontroller per tjänst och en statusvy i appen (grön/gul/röd per tjänst)
- Prometheus-mått: latens, ordrar, fel, datafördröjning, API-kostnad och P&L
- Strukturerade loggar (JSON) som sparas i 90 dagar
- NTP-synkad klocka; vid avvikelse > 1 s stoppas handeln
- Tidszoner och sommartid testas uttryckligen (Stockholm och New York byter vid olika datum)
- Dagliga databasbackuper som testas med en återställning varje månad
- **Två miljöer:** `staging` (körs alltid mot IBKR Paper) och `production`. All ny kod går först till staging och måste köras där utan fel (standard minst 2 handelsdagar för ändringar i handel och risk) innan den får gå till production. Driftsättning sker med ett kommando, med automatisk hälsokontroll efteråt, och kan **rullas tillbaka med ett kommando**. Inga ändringar görs direkt på produktionsservern.
- **Avstämning mot mäklarens egna rapporter:** varje natt jämförs Jarvis databas med IBKR:s officiella rapporter (Flex Queries) — affärer, avgifter, utdelningar och kassa. Alla avvikelser larmas.

### 11.1 Om mäklaren krånglar
- Om IBKR har driftstopp, låser kontot för kontroll eller ändrar regler: Jarvis pausar nya affärer, och stoppordrarna som ligger hos mäklaren skyddar positionerna.
- Adam får en tydlig nödplan i appen och i `docs/NODPLAN.md`: vilka positioner som är öppna, var stoppen ligger, och exakt hur han hanterar dem manuellt i IBKR:s egen app. Listan uppdateras varje kväll och skickas även per e-post, så att den finns även om Jarvis server är nere.
- `BrokerAdapter` (§2) gör det möjligt att lägga till en andra mäklare senare om Adam vill ha en reserv.

### 11.2 Adams eget dödmansgrepp
Om Adam blir sjuk, tappar telefonen eller är utan nät länge ska Jarvis inte fortsätta som om inget hänt.
- Adam ska **checka in** i appen minst var 7:e dag (justerbart). Det räcker att öppna appen och trycka "Jag är här".
- Missad incheckning → påminnelse via push och e-post. Efter 3 dagar till → Jarvis halverar risken och slutar öppna nya daytrades. Efter ytterligare 7 dagar → Jarvis stänger positionerna i lugn takt och placerar kapitalet i index-ETF:en (§1.5).
- Valfritt: en betrodd kontaktperson som får ett e-postmeddelande och en enkel säker länk för att **pausa** (aldrig för att handla eller ta ut pengar).
- Under resor kan Adam ställa in en längre period i förväg.

### 11.3 Pappersresultat är för optimistiska
IBKR:s papperskonto fyller ofta order lättare och till bättre priser än verkligheten. Därför:
- Pappersresultat justeras med en extra kostnadsmarginal (standard: dubbel modellerad slippage) innan de jämförs med kraven i §6.4.
- Fyllnader i papper som verkar orimligt bra (t.ex. fyllt på limit utan att marknaden handlats där) flaggas.
- Från första dagen live mäts skillnaden mellan papper och live per strategi, och den används för att justera kostnadsmodellen.

---

