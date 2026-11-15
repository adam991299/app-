# Hur Jarvis fungerar — från signal till order

Det här dokumentet förklarar på enkel svenska vad som händer när Jarvis vill göra en
affär. Det byggs på i takt med att delarna blir klara. Delar som inte finns än står inte här.

## 1. Risk-motorn har sista ordet

Varje order, oavsett varifrån den kommer, passerar risk-motorn (`backend/src/jarvis/risk/`).
Den kan bara säga ja eller nej, och vid minsta osäkerhet säger den nej. Varje nej loggas med
ett skäl på svenska, till exempel "Kursen är för gammal."

### Först: får Jarvis handla alls just nu?

Risk-motorn räknar ut ett **läge** utifrån kontots värde, systemets hälsa och dina reglage.
Det strängaste läget gäller:

| Läge | När | Nya köp | Stänga positioner |
|---|---|---|---|
| **Stoppad** | Ingen anslutning till mäklaren, 5 fel i rad, klockan fel med mer än 1 s, eller positionerna stämmer inte mot mäklaren | Nej | Nej |
| **Kill switch** | Kontot har fallit 10 % från toppen, eller kill switch är redan aktiv | Nej | Ja |
| **Pausad** | Du har tryckt på Paus | Nej | Ja |
| **Bara stängningar** | Veckans förlust är 4 % eller mer | Nej | Ja |
| **Inga nya affärer** | Dagens förlust är 2 % eller mer | Nej | Ja |
| **Handlar** | Allt är i ordning | Ja | Ja |

Kill switch släpper inte av sig själv när kontot återhämtar sig. Du måste starta handeln
igen i appen. Stoppordrarna ligger hela tiden kvar hos mäklaren, så positionerna är skyddade
även när Jarvis inte handlar.

### Sedan: är just den här ordern rimlig?

Ett köp godkänns bara om **allt** detta stämmer:
- Ordern har en stop-loss under köppriset.
- Om stoppen slår förlorar du högst **0,75 %** av kapitalet.
- Positionen blir högst **10 %** av kapitalet (5 % för krypto och småbolag).
- Om kursen rasar förbi stoppen (räknat som −25 % för en aktie, −40 % för krypto) förlorar du
  högst **3 %** av kapitalet.
- En sektor får högst 25 %, krypto högst 15 % och råvaror högst 20 % av kapitalet.
- Allt investerat blir högst 100 % av kapitalet (ingen belåning) och minst 5 % ligger kvar
  som kontanter.
- Den förväntade vinsten är minst dubbelt så stor som kostnaderna.
- Kursen är högst 60 sekunder gammal och limitpriset avviker högst 3 % från den.
- Marknaden är öppen, och det är inte de första eller sista 10 minuterna av dagen.
- Högst 10 order den senaste minuten och 50 i dag, och högst 25 öppna positioner.

Order som redan ligger hos mäklaren räknas som om de vore fyllda. Två likadana signaler kan
därför aldrig tillsammans ta Jarvis förbi en gräns.

Att **sälja** det Jarvis äger är tillåtet i alla lägen utom "Stoppad". Jarvis kan aldrig
sälja mer än den äger — det skulle vara blankning, och det är inte tillåtet.

### Hur stor blir affären?

Jarvis räknar ut den största storlek som klarar alla gränser ovan och tar den minsta av dem
(`risk/sizing.py`). Ett datortest provar hundratals slumpade fall och kontrollerar att
storleken aldrig bryter någon gräns.

## 2. Mäklaren

Allt som går till mäklaren passerar ett gemensamt gränssnitt (`broker/adapter.py`). Det gör
att Jarvis kan testas mot en simulerad mäklare och senare kopplas till IBKR utan att resten
ändras.

- Varje köp skickas med sin **stop-loss hos mäklaren** (en så kallad bracket-order). Stoppen
  gäller alltså även om Jarvis server går ner.
- Varje order har ett eget ID som Jarvis väljer. Skickas samma order två gånger, till
  exempel efter en omstart, blir det ändå bara en order.
- Om bara en del av ett köp fylls skyddar stoppen exakt den del som köpts.
- Den simulerade mäklaren beter sig som ett ISK: köp utan täckning och blankning avvisas, och
  ett kursras förbi stoppen säljs till raspriset, inte till stoppriset.
