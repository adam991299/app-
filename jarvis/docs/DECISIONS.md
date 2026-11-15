# Beslut

Viktiga beslut med motivering. Nyast överst.

## 2026-11-15

### D16. Hemskärmen: ren CSS med design tokens, Tailwind väntar till Fas 6
Specen nämner Tailwind. Hemskärmen är byggd med vanliga CSS-variabler (alla färger, mått och
typsnitt som tokens enligt §9.1), eftersom en enda vy inte behöver mer. Tailwind-temat och
komponentkatalogen (`/design`) byggs i Fas 6 ovanpå samma tokens. Skärmdumparna i
`docs/screenshots/` använder exempeldata som bara finns i testerna; appen själv visar
aldrig påhittade siffror.

### D14. Adam tar bort kraven på tid i pappershandel
Adam: "ta bort dem där kraven på 10 och 60 dagar. Jag vill inte behöva vänta fler månader."
Ändrat efter Adams uttryckliga beslut (avviker från specen §00.5, §6.4 och §13):
- Fas 0.5 kräver inte längre 10 handelsdagar. Den är klar när hela kedjan är verifierad mot
  den simulerade mäklaren och mot IBKR Paper.
- Fas 8 kräver inte längre 60 handelsdagar. Pappershandeln pågår så länge Adam vill, och
  slutrapporten kan tas fram när han vill.
- En strategi behöver ingen minsta tid i papper (`paper_min_trading_days` och
  `slow_strategy_paper_min_months` är 0).

**Oförändrat:** riktig handel startar bara när Adam själv slår på den i appen (§9.4);
risk-motorn, stoppen och kill switch gäller som förut; en strategi behöver fortfarande minst
50 affärer i papper (statistiskt underlag, inte väntetid) och måste klara valideringen i §6.3.
**Risken, som Adam har fått veta:** utan tid i papper bygger beslutet om riktig handel
nästan bara på backtester, som brukar se bättre ut än verkligheten.

### D15. Utgångar sker genom att höja stoppen (tunna versionen)
I Fas 0.5 stänger Jarvis en position bara genom att höja stopporderna hos mäklaren (aldrig
sänka), som i en kanalutgång för trendföljning. Positionen har då alltid ett skydd. Manuell
stängning ("stäng positionen nu") kräver att stoppen tas bort före försäljningen och byggs i
Fas 5 tillsammans med ett reservstopp om försäljningen misslyckas.

### D12. Dag och vecka för förlustgränserna följer svensk tid
Kontot är ett ISK i kronor, så "dagens förlust" räknas från midnatt till midnatt i
Europe/Stockholm, och veckan börjar måndag 00:00 svensk tid. Referensvärdet är kontots sista
värde före dagens (veckans) början, alltså gårdagens (förra veckans) slutvärde. Värdena
räknas fram ur sparade ögonblicksbilder av kontot, så att de är spårbara i efterhand.

### D13. Databas och tester
SQLAlchemy 2 (asynkront, asyncpg) med Alembic-migreringar. Databasens adress är en hemlighet
och läses bara från miljövariabeln `JARVIS_DATABASE_URL`. Testerna körs mot en riktig
PostgreSQL och hoppas aldrig över om den saknas. CI startar en egen server; där testerna
körs som root (som i Claudes byggmiljö) startas servern som användaren `postgres` och pekas
ut med `JARVIS_TEST_POSTGRES=host:port`. Ett test kontrollerar att migreringarna stämmer
exakt med tabellerna i koden.

### D11. Beslut efter granskningen av risk-motorn
- **Dags- och veckostoppet håller resten av dagen respektive veckan.** De jämför dagens och
  veckans *lägsta* kontovärde med startvärdet, inte det nuvarande. Första versionen släppte
  stoppet om kontot återhämtade sig samma dag (hittat av granskaren).
- **En sälj får inte röra aktier som en stopporder hos mäklaren redan skyddar.** Stoppen
  tas bort först, sedan säljs aktierna. Annars kunde en gammal stopp senare sälja aktier som
  köpts efteråt. Mellan de två stegen är positionen kort oskyddad; det sker bara när Jarvis
  ändå säljer.
- **Stängningar räknas inte mot ordertaket per minut och dag.** De kan bara minska risken
  och aldrig sälja mer än innehavet. Färsk kurs och rimligt limitpris krävs fortfarande.
- **"Fler än N fel i rad" (§7):** handeln stoppas vid det 5:e felet i rad (`>= 5`).
- **Kostnaden måste alltid anges** för en order; den har inget standardvärde, så
  vinstkravet (minst 2× kostnaden) inte kan kringgås av misstag.
- **Instrument identifieras med symbol** så länge bara amerikanska aktier via SMART handlas.
  I Fas 1, när flera börser tillkommer, byts nyckeln till IBKR:s kontrakts-ID, så att samma
  symbol på två börser aldrig blandas ihop.
- **SimBroker har en valuta.** Valutaomräkningen testas i risk-motorn för sig.

### D9. Jarvis ska kosta 0 kr i fasta kostnader (Adams krav)
Adam: "Detta ska inte kosta något alls." Specen förutsätter en betald VPS, domän,
marknadsdata och Claude API. Så här blir det gratis, och det här går **inte** att få gratis:

| Behov | Gratis lösning | Vad det kostar i kvalitet |
|---|---|---|
| Server dygnet runt | Oracle Cloud Always Free (Arm, EU-region, t.ex. Stockholm) | Gratisnivån halverades 2026 till ca 2 kärnor/12 GB. Räcker för swing/position, inte för tung daytrading eller lokala AI-modeller. Kräver kort för identitetskontroll (debiteras inte). Ledig kapacitet i populära regioner kan saknas. |
| Domän och HTTPS | Tailscale (gratis för privatpersoner) med adressen `*.ts.net` och eget certifikat | Ingen egen domän. Appen nås bara från Adams egna enheter — vilket specen ändå kräver (§10). |
| Marknadsdata USA | IBKR:s gratis realtidsdata från Cboe One och IEX | Inte konsoliderad (ingen NBBO). Godtagbart för strategier på dagsbarer. |
| Marknadsdata Norden, råvaror | Fördröjd data (10–20 min) gratis | Ingen realtid. Norden handlas bara med strategier som klarar fördröjningen, eller inte alls. |
| Historik för backtest | IBKR:s historik (med pacing-gränser) och fria officiella källor | Kortare historik och survivorship bias. Dokumenteras ärligt i varje rapport. |
| Nyhetsanalys | Regelbaserad analys och öppna modeller som körs på servern | Sämre tolkning än Claude, särskilt på svenska. |
| "Fråga Jarvis" (chatt) | — | **Går inte att få bra gratis.** En språkmodell behövs. Utan API-nyckel stängs chatten av; resten av appen fungerar. |
| Notiser, e-post, övervakning | Web Push, Adams egen e-post via SMTP, gratis upptidstjänst | Inget SMS. |
| CI | GitHub Actions (gratis minuter räcker) | — |

**Kostnader som aldrig blir noll när Jarvis handlar på riktigt:** courtage hos IBKR,
valutaväxling, spread och ISK-skatten. Pappershandel kostar ingenting.

**Beslut:** allt byggs för 0 kr. Funktioner som kräver Claude byggs utbytbara och står
avstängda (budget 0 kr/dag) tills Adam eventuellt lägger in en nyckel. Inget av detta
smyger in en betald tjänst. *Bekräftelse av chatt-frågan ställd till Adam.*

### D10. Värden för ordersäkerhet som specen inte anger (§7)
Valda försiktigt, och justerbara inom intervallen i config:
max 3 % avvikelse mellan limitpris och senaste kurs; max 10 order per minut och 50 per
dag; ingen ny position de första och sista 10 minuterna (specen: 5–10); stoppa handeln
efter 5 fel i rad mot mäklaren; en kurs äldre än 60 sekunder räknas som gammal.

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
