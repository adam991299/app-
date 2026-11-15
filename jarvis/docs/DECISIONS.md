# Beslut

Viktiga beslut med motivering. Nyast överst.

## 2026-11-14

### D1. Jarvis ligger i mappen `jarvis/` i det befintliga repot
Specen säger "en tom projektmapp", men sessionen startades i repot `app-`, som redan
innehåller appen Närmast (Expo). Jag har bara åtkomst till det repot. Jarvis ligger därför i
en egen mapp `jarvis/` med egen `CLAUDE.md`, egna beroenden och egen CI som bara körs när
`jarvis/` ändras. Enda ändringen utanför mappen: `jarvis/**` är undantaget i rotens
`tsconfig.json`, så att Närmasts typkontroll inte läser Jarvis-koden.
**Kan ändras:** om Adam hellre vill ha ett eget repo flyttas mappen dit med historiken kvar.
*Fråga ställd till Adam.*

### D2. Handelsläget (papper/live) finns inte i config-filen
Regel 3 i §0: live slås bara på av Adam i appen med passkey och bekräftelsefras. Om läget låg
i en fil skulle en felaktig redigering kunna slå på riktig handel. Läget kommer därför att
ligga i databasen med audit-logg (byggs i Fas 0.5 och Fas 6), och config-systemet avvisar
okända fält.

### D2b. Belåning och blankning finns inte heller i config-filen
Av samma skäl som D2. §3 och §7.1: Jarvis är long-only och obelånad tills Adam ändrar det i
Avancerat, där också ISK-reglerna ska kontrolleras. Config-filen har därför inget fält för
belåning eller blankning, och bruttoexponeringen kan inte sättas över 100 %. Möjligheten
byggs i appen (med passkey och kontroll mot kontotypen) om och när Adam vill ha den.
*Hittades av granskningsagenten: första versionen hade ett fält `leverage_allowed`.*

### D3. Bara värden som specen anger finns i config
Specen lämnar flera standardvärden öppna (t.ex. max antal affärer per vecka, max order per
minut, "N fel i rad" mot mäklaren, hur mycket nattläget sänker positionsstorleken). De
läggs till när modulen som använder dem byggs, med ett eget beslut här — inte påhittade i
förväg.

### D4. Intervall för circuit breakers
§7.1: nivåerna får justeras "inom rimliga intervall" men aldrig stängas av. Valda intervall:
dagsförlust 0,5–5 %, veckoförlust 1–10 %, kill switch 2–20 %, och alltid
dag < vecka < kill switch ≤ projektets stoppgräns (§16, 20 %). Värden utanför gör att
Jarvis vägrar starta.

### D4b. Alla gränser har ett golv och ett tak
En gräns ska inte gå att göra verkningslös med ett extremt värde. Exempel: gap-scenariot
kan inte sättas under 10 % (aktier) eller 20 % (krypto), kassareserven inte under 5 %,
max öppna positioner inte över 100, incheckningsintervallet inte över 90 dagar, och risk per
affär aldrig över dagsgränsen. Oändliga tal, text och sant/falskt i stället för siffror
avvisas, liksom dubbla nycklar i filen. Intervallen är mina val där specen inte anger något
och kan justeras av Adam.

### D5. Marknader slås på när deras fas är klar
Standard i config: bara amerikanska aktier påslagna (Fas 0.5). Norden, ETF:er, råvaror och
krypto slås på när deras data och regler är verifierade. Terminer och pre/after-market är
avstängda tills Adam väljer annat (§3, §1.6).

### D6. IB Gateway startas med en egen profil
`docker compose up` startar allt utom `ib-gateway`, som kräver Adams IBKR-inloggning och
startas med `--profile broker`. Gatewayns port publiceras aldrig utanför det interna
nätverket (§10).

### D7. Inga funktioner för andra användare (§15.1)
Jarvis byggs för Adams egna pengar. Att sälja Jarvis eller signaler, eller förvalta andras
pengar, kräver i regel tillstånd från Finansinspektionen och dyrare (professionell)
marknadsdata. Arkitekturen hålls ren så att det går att utöka senare, men inga
fleranvändarfunktioner byggs nu.

### D8. Verktyg
Python-paket hanteras med `uv` (låsfil `uv.lock`), webben med `npm` (låsfil
`package-lock.json`). Backend-tjänsterna delar en Docker-avbild och startas med
`python -m jarvis.service --name <tjänst>`. Containrar körs som icke-root.
