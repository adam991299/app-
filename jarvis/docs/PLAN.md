# Plan — Jarvis the Trader

Status: ✅ klar och verifierad · 🔨 pågår · ⏳ väntar på Adam · ⬜ ej påbörjad

Acceptanskraven är ordagrant från `docs/spec/13-byggordning.md`. En fas bockas av först när
hela arbetscykeln (§00.2) är genomförd.

## Beroendekarta

```
Fas 0 ──► Fas 0.5 (tunn version, pappershandlar ≥ 10 handelsdagar) ──────────────┐
  │                                                                               │
  ├─► Delade gränssnitt (definieras först i Fas 0.5): API-kontrakt,               │
  │   databasschema, design tokens, BrokerAdapter                                 │
  │        │                                                                      │
  │        ├─► Fas 1 Data ──► Fas 2 Research-labb ──► Fas 3 Strategier            │
  │        │        │                    │                  │                     │
  │        │        ├─► Fas 4 Nyheter ───┤                  │                     │
  │        │        ├─► Fas 4.2 Politiker┤                  │                     │
  │        │        │                    └─► Fas 4.5 Learning Loop                │
  │        ├─► Fas 5 Risk och exekvering (bygger vidare på 0.5) ──► Fas 6.2       │
  │        ├─► Fas 6 Appen (mot API-kontraktet) ──► Fas 6.2 ──► Fas 6.5           │
  │        ├─► economics/ (§1.5) — oberoende, visas i Fas 6                       │
  │        └─► Fas 7 Drift och säkerhet (VPS krävs redan för Fas 0.5)             │
  │                                                                               ▼
  └──────────────────────────────► Fas 8 Papper ≥ 60 handelsdagar ► Fas 9 Live ► Fas 10
```

**Byggs parallellt** (egna git worktrees, efter att de delade gränssnitten finns):
nyhetsmotorn (4), politikersignaler (4.2), appens design och vyer (6), research-labbet (2),
ekonomimodulen. **Byggs aldrig i hast:** `risk/`, `execution/`, `broker/`, `economics/`.

**Tidskrav:** borttagna av Adam (D14). Pappershandeln kräver fortfarande en server som är
igång dygnet runt och Adams IBKR Paper-inloggning.

## Faser

### ✅ Fas 0 – Plan och skelett
Repo-struktur, Docker Compose, CI (lint, typkontroll, tester), `README.md` på svenska,
`docs/ASSUMPTIONS.md`, och config-system med validering.
**Acceptanskrav:** `docker compose up` startar alla tomma tjänster, och CI är grön.

- [x] Specen uppdelad ordagrant i `docs/spec/` (kontrollerad byte för byte mot originalet)
- [x] `CLAUDE.md`, `PLAN.md`, `PROGRESS.md`, `ASSUMPTIONS.md`, `DECISIONS.md`
- [x] Config-system med validering (`backend/src/jarvis/config/`, `config/default.yaml`)
- [x] Tjänsteskelett med hälsokontroll och JSON-loggar (`backend/src/jarvis/service/`)
- [x] Webbskelett (Next.js, TypeScript strict, design tokens från §9.1)
- [x] Docker Compose med alla tjänster i §2; bara Caddy publicerar en port (443)
- [x] CI: backend (ruff, mypy strict, pytest), webb (eslint, tsc, build), compose-röktest
- [x] README på svenska
- [x] Granskning av separat agent, fynd åtgärdade
- [x] Acceptanskravet verifierat i CI (se `PROGRESS.md`)

### 🔨 Fas 0.5 – Den tunna versionen hela vägen
Amerikanska aktier, en strategi, IBKR Paper, risk-engine med nödstopp, avstämning, test- och
live-miljöer (§11), och en enkel men redan snygg hemskärm enligt §9.1.
**Acceptanskrav (ändrat av Adam, D14):** Körs automatiskt utan fel eller manuella ingrepp
(utöver 2FA) — kravet på minst 10 handelsdagar är borttaget. Varje affär går att följa från
signal till fyllnad. Kill switch testad. Hemskärmen granskad med skärmdumpar.

Delsteg (byggs mot `SimBroker`, kräver inget av Adam):
- [x] Delade typer (`domain/`): instrument, kurs, position, konto — pengar alltid `Decimal`
- [x] `BrokerAdapter` och `SimBroker` (kontantkonto: ingen blankning, ingen belåning,
      bracket med stopp hos mäklaren, delfyllnader, idempotenta order-ID, felinjektion)
- [x] Risk-engine: positionsstorlek, kontroller före varje order, circuit breakers,
      kill switch, hälsostopp (anslutning, fel i rad, klocka, avstämning)
- [x] CI kräver 100 % täckning i `risk/` och `broker/`
- [x] Granskning av risk och broker, fynd åtgärdade (D11)
- [x] Börskalender (`exchange_calendars`): öppettider, helgdagar, halvdagar, sommartid
- [x] API-kontrakt för appen (`contracts/api.schema.json`, test mot avdrift)
- [x] Databasschema och lagring: kill switch, paus, kontovärden, orderjournal, fyllnader,
      riskbeslut, revisionslogg (D12, D13)
- [x] `execution/`: order-tillståndsmaskin, journal före avsändning, idempotens vid omstart,
      återhämtning, avstämning, larm, höjning av stopp (D15); 100 % täckning
- [x] Trendföljningsstrategi på dagsbarer: Donchian-utbrott, ATR-stopp, glidande stopp
      (regler och tester; ännu inte kopplad till data eller validerad, se D18)
- [x] Hemskärm enligt §9.1: orb, status, kontovärde, idag, marknader, innehav, affärer,
      tomma lägen, felläge; skärmdumpar i `docs/screenshots/` (med exempeldata)
- [x] API-tjänsten som ger hemskärmen riktig data (`/status`, `/portfolio`, `/trades`, `/today`),
      migrerar databasen vid start; orderhanteringen sparar läget efter varje avstämning.
      Hela kedjan provkörd: simulerad mäklare → orderhantering → databas → API → app
      (`docs/screenshots/home-live-sim-*.png`)
- [ ] Hemskärmens e2e-kontroll (`npm run e2e`) i CI
- [x] Granskning av `execution/`, fem fel rättade med test (D17)
- [x] IBKR-adapter (`broker/ibkr.py`, `ib_async` 2.1.0): bracket som en enhet, `orderRef` som
      order-ID, idempotens, statusmappning, flytt av stopp, fyllnader först när provisionen är
      känd; prispriser avrundas till tillåtna steg (D20). Testad mot fejkad gateway.
- [ ] Provkörning mot riktig IB Gateway och Adams papperskonto — **kräver servern**
- [x] Körslinga (execution-engine-tjänsten): anslut med återförsök, återhämtning,
      avstämning varje minut, klockkontroll mot NTP, kurser i realtid från IBKR (annars ingen
      kurs), dagsdata klippt vid senaste stängda dag, stopphöjning efter stängning,
      köpsignaler loggas men skickas inte förrän en validerad förväntad vinst finns (D18)
- [x] Larm via e-post (Adams eget Gmail, valfritt) och alltid i loggen; Web Push kommer med appen i Fas 6
- [ ] Driftsättning på gratisserver — **kräver att Adam skapar kontot (D9)**
- [ ] Automatisk pappershandel utan fel (inget minimikrav på tid, D14)

**Skjuts uttryckligen upp** (risk-delar som kräver data eller vyer som inte finns än).
Fram till dess handlar den tunna versionen bara en strategi på amerikanska aktier och
dagsbarer, där dessa delar har minst betydelse:

| Del (§) | Byggs i | Varför då |
|---|---|---|
| Korrelationskontroll (§7) | Fas 5 | Kräver historik för korrelationer (Fas 1) |
| Max affärer per vecka och årlig omsättning (§7) | Fas 5 | Kräver affärsjournalen i databasen |
| Daglig stresstest mot 2008, mars 2020, 2022 och flashkrascher (§7) | Fas 5 | Kräver historik |
| Rapportskydd före rapporter (§7) | Fas 5 | Kräver rapportkalender (§4.2) |
| Handelsstatus och auktioner (§7) | Fas 5 | Kräver IBKR-adaptern |
| Nattläge med mindre positioner (§1.6) | Fas 5 | Specen anger inte hur mycket mindre; beslut tas då |
| Saknad data som stopp för hela systemet (§7) | Fas 0.5, `execution/` | Hälsoövervakningen byggs där |
| Kontroll att marknaden är påslagen i config (§3) | Fas 1 | Kräver marknadsfält per instrument |
| Likviditetsfilter för småbolag (§3) | Fas 1 | Universumfiltret |
| ¼ Kelly (§7) | Fas 3 | Ingen strategi använder Kelly förrän då |
| Jarvis budget och kapitalkontrollen (§7.1) | Fas 6 | Gränserna räknas mot hela kontot tills reglagen finns, vilket är försiktigare så länge budgeten är 100 % |
| Daytrading-gränser (§6.2.1) | Fas 3 | Daytrading-motorn |

### ⬜ Fas 1 – Data
Kalendrar, universum, historik- och realtidsdata från IBKR Paper, datakvalitetskontroller.
**Acceptanskrav:** Historik för minst 200 instrument över alla tillgångsslag sparad och
kvalitetskontrollerad.

### ⬜ Fas 2 – Research-labb
Kostnadsmodell, vektoriserad och händelsedriven backtester, walk-forward, holdout, Deflated
Sharpe, Monte Carlo och lookahead-test.
**Acceptanskrav:** En känd enkel strategi ger samma resultat i båda backtestrarna (inom
tolerans), och lookahead-testet fångar ett avsiktligt inplanterat fel.

### ⬜ Fas 3 – Strategibibliotek och regimer
Alla strategier i §6.1, regimklassificering och livscykel.
**Acceptanskrav:** Rapport på svenska över vilka kandidater som klarar valideringen. Det är
helt okej om ingen klarar den. Då säger rapporten det ärligt och Jarvis handlar inte.

### ⬜ Fas 4 – Nyhetsmotor
Källplugins, avduplicering, Claude-analys med JSON-validering, features och kostnadstak.
**Acceptanskrav:** Nyheter strömmar in, kopplas rätt till instrument (stickprov på 50 st
≥ 90 % rätt) och lagras med mottagningstid.

### ⬜ Fas 4.2 – Politikersignaler (§5.4)
Parsers för Senatens och representanthusets rapporter, utskottsdata, features och backtest
från publiceringsdatum.
**Acceptanskrav:** Historik sedan 2012 inläst och stickprovskontrollerad mot original-PDF:er
(≥ 95 % korrekta). Testet som stoppar användning av affärsdatum som signaldatum finns och
fungerar. En ärlig rapport på svenska visar om signalen tillför något efter kostnader.

### ⬜ Fas 4.5 – Learning Loop (§5.5)
Affärsjournal, efteranalys, märkning av nyhetsutfall, modellregister, champion/challenger med
skuggkörning, driftdetektering, research-agent i sandlåda, och mätvärden.
**Acceptanskrav:** En medvetet sämre challenger ska förlora och aldrig befordras. En medvetet
bättre challenger (på syntetisk data med en inplanterad edge) ska vinna. Återställning till
förra versionen fungerar. Research-agenten kan inte röra risk- eller live-kod (testas).

### ⬜ Fas 5 – Risk och exekvering mot papperskonto
Risk-engine, order-tillståndsmaskin, bracket-order, avstämning och återhämtning.
**Acceptanskrav:** Kaostester: döda tjänster mitt i en order, koppla bort gatewayn, skicka
dubbla signaler. Inga dubbla order, inga positioner utan stop, och läget stämmer alltid mot
mäklaren.

### ⬜ Fas 6 – Appen
Alla vyer i §9 och PWA med notiser.
**Acceptanskrav:** Lighthouse ≥ 95 i Performance, Accessibility och Best Practices på mobil.
Mörkt läge (standard) och ljust läge granskade med skärmdumpar mot §9.1. Fungerar från
iPhone-hemskärmen. Noll kända buggar.

### ⬜ Fas 6.2 – Samtidighet och möjlighetsnotiser (§6.4.1, §9.2.2)
Portföljhanterare, delpositioner, gränser för samtidighet, de tre lägena per motor,
möjlighetskort med nedräkning och priskontroll.
**Acceptanskrav:** Simulering: 5 daytrades, 10 swingpositioner och 2 krypto- och
råvarupositioner hanteras samtidigt utan motstridiga order och utan överskriden budget. En
kraschad strategi påverkar inte de andra. Ett förslag som godkänns efter att priset rört sig
kräver ny bekräftelse. Ett utgånget förslag kan inte godkännas.

### ⬜ Fas 6.5 – "Fråga Jarvis" (§9.2.1)
Chatt med tool use, rika kort, röst in och ut, säkerhetsnivåer, och skydd mot prompt injection.
**Acceptanskrav:** 30 testfrågor (förklaringar, skanningar, analyser och åtgärder) besvaras
korrekt utifrån riktig data. Röstorder på nivå 3 kräver alltid bekräftelse. Försök att via
chatt eller röst slå på live-handel, höja riskgränser eller stänga av kill switch misslyckas
(testas automatiskt). En nyhet med en inplanterad instruktion ("sälj allt") leder inte till
någon åtgärd. Svarstiden i röstläge mäts.

### ⬜ Fas 7 – Drift och säkerhet
Deploy till VPS, Caddy, Cloudflare Access/Tailscale, passkeys, övervakning, backup och watchdog.
**Acceptanskrav:** Säkerhetschecklista genomgången. Återställning från backup testad.

### ⬜ Fas 8 – Pappershandel (kravet på 60 handelsdagar borttaget av Adam, D14)
Jarvis körs helt automatiskt i papper. Veckorapporter. Avvikelser mot backtest och mot index
analyseras.
**Acceptanskrav:** Adam får en slutrapport: vad som fungerade, vad som inte gjorde det, och om
systemet uppfyller kraven för LIVE-LITEN enligt §6.4. Rekommendationen ska vara ärlig även om
svaret är nej.

### ⬜ Fas 9 – Live (bara när Adam aktivt väljer det)
Enligt §9.4.

### ⬜ Fas 10 – Utvärdering efter 6 och 12 månader live
En ärlig rapport om Jarvis jämfört med index efter alla kostnader och skatt, med statistisk
osäkerhet (konfidensintervall), och en tydlig rekommendation. Följer stoppreglerna i §16.
