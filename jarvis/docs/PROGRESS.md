# Framstegslogg

Nyast överst. Varje post: vad som gjorts, hur det verifierats och vad som är nästa steg.

## 2026-11-16 — Ekonomivyn (D27)

- `GET /api/economics` och sidan `/ekonomi` (kort på hemskärmen): Jarvis mot indexfonden i
  kronor med graf (hovring, tabellvy, färger kontrollerade för färgblindhet), ärligt omdöme,
  fasta kostnader och break-even, ISK-skatt (bara med årets siffror), courtage hittills.
- Körslingan sparar indexfondens stängning och växelkurs varje dag (migrering 0007).
- Kvar enligt §1.5: linjen "Jarvis före kostnader" (D27), "Kan jag leva på det?"-kalkylatorn
  i appen (modellen finns i `economics/living.py`).
- 570 backend-tester gröna, 100 % i risk, mäklare, order och ekonomi; Playwright med
  skärmdumpar `docs/screenshots/economics-*`.

## 2026-11-16 — Daytrading-vyn i appen

- `GET /api/daytrading` och sidan `/daytrading` (kort på hemskärmen, detaljer ett tryck
  bort): läge på svenska (aktiv, pausad och varför, avstängd tills validering), öppna av max,
  dagens resultat i kronor, förluster i rad, regler och dagens affärer med köp, försäljning
  och resultat. Tomt läge och fel-läge finns.
- Rättat fel: dagsförlusten för daytrading räknades i dollar men jämfördes med en gräns i
  kronor. Nu räknas den om med aktuell växelkurs, och utan kurs öppnas inga nya daytrades.
- Priser i förklaringarna skrivs med decimalkomma.
- Daytradingens läge sparas i `strategy_state` (migrering 0006).
- 558 backend-tester gröna, 100 % i risk, mäklare, order och ekonomi; Playwright-kontroller
  med skärmdumpar i mobil- och datorstorlek (`docs/screenshots/daytrading-*`).

## 2026-11-16 — Köp bara för likvida pengar (A6)

- `Account.settled_cash` (IBKR:s `SettledCash`) och `spendable`. Risk-motorn avvisar ett köp
  som bara går att betala med pengar från försäljningar som inte är likvida än
  (`UNSETTLED_CASH`), och storleken räknas på de likvida pengarna.
- `SimBroker(settlement_days=1)` beter sig som ett kontantkonto med T+1.
- 549 tester gröna, 100 % i risk, mäklare, order, ekonomi och domän.

## 2026-11-16 — Fler daytrades per dag (D26)

- 50 aktier i stället för 20 (`config/universe_us.yaml`).
- Samma aktie upp till 3 gånger per dag, efter ny dagshögsta (`strategy/orb.setup_for`,
  `research/orb_backtest`, `runner/daytrade`). Backtestet och livehandeln följer samma regel.
- 545 tester gröna, 100 % i risk, mäklare, order och ekonomi.
- Öppet: om ISK hos IBKR är ett kontantkonto med T+1 (A6) och om 50 aktiers 5-minutersdata
  ryms i IBKR:s gränser (A4). Båda provas i papper.

## 2026-11-16 — Daytrading (öppningsintervall, ORB) i körslingan

**Gjort**
- `runner/daytrade.py`: under USA-sessionen letar Jarvis efter utbrott över de första
  minuternas högsta nivå (5-minutersdata från IBKR). Bara om ORB-strategins senaste
  validering är godkänd. Högst 5 daytrades samtidigt, en per aktie och dag, stopp för dagen
  vid 1 % förlust eller 3 förluster i rad, allt säljs 15 minuter före stängning med riktig
  säljorder. Varje ny 5-minutersstapel hämtas en gång (IBKR:s gränser för historikanrop).
  Trendstrategins stopphöjning rör inte daytrades.
- `store.closed_results`: resultat efter avgifter för varje helt stängd affär per strategi.
- `marketdata`: `intraday_bars` (en månad per anrop, paus mellan anropen).
- `python -m jarvis.research.run orb`: validerar daytrading på ett års 5-minutersdata
  (walk-forward, låst holdout, deflaterad Sharpe, jämförelse med index). Tar ungefär en timme.

**Verifierat:** 542 tester gröna, 100 % täckning i risk, mäklare, order och ekonomi; mypy
strict och ruff utan anmärkningar.

**Nästa:** köra båda valideringarna på servern när den finns; Fas 6-vyer.

## 2026-11-15 — Fas 0.5 påbörjad, och "0 kr"-beslutet

**Adams svar:** bor i Sverige (tidszon Europe/Stockholm, redan standard), har ett IBKR-konto,
och Jarvis ska inte kosta något. Beslut D9 beskriver hur det blir 0 kr i fasta kostnader
och vad som inte går att få gratis.

**Gjort**
- `domain/`: delade typer; pengar alltid `Decimal`; sektorer normaliseras.
- `risk/`: positionsstorlek, kontroll före varje order (alla §7-gränser som har data i dag),
  circuit breakers som håller dag/vecka, kill switch, hälsostopp; skäl på svenska.
- `broker/`: `BrokerAdapter` och `SimBroker` (kontantkonto, bracket med stopp hos mäklaren,
  delfyllnader, idempotenta order-ID, felinjektion).
- `markets/`: börskalender med helgdagar, halvdagar och sommartid.
- CI kräver 100 % täckning i `risk/` och `broker/`.

**Verifierat**
- 234 tester godkända; 100 % täckning i `risk/` och `broker/`; mypy strict och ruff utan
  anmärkningar; varningar räknas som fel.
- Egenskapstest: storleken från `size_position` godkänns alltid av risk-motorn, och en aktie
  till avvisas alltid — med ett annat innehav i annan valuta och sektor på kontot.
- Sommartid: testat att USA:s öppning ligger 14:30 svensk tid under veckorna i mars då USA
  bytt till sommartid men inte Sverige, och 15:30 annars.

**Granskning (separat agent)** hittade fyra fel, alla rättade med test (D11): dagsstoppet
släppte när kontot återhämtade sig; en sälj kunde överlappa en stopp hos mäklaren; en gammal
stopp kunde sälja aktier från ett senare köp; den simulerade mäklaren kunde ge negativ kassa.
Dessutom: kurser med framtida tidsstämpel avvisas, gap-scenariot räknar med en stopp som
ligger längre bort än gapet, och kostnaden måste alltid anges.

**Nästa steg:** databasschema och lagring (kill switch, paus, kontovärden, affärsjournal),
`execution/` med avstämning, trendföljningsstrategin och hemskärmen.

## 2026-11-14 — Fas 0: plan och skelett

**Gjort**
- Läst hela specifikationen och delat upp den ordagrant i 25 filer i `docs/spec/`.
  Kontroll: filerna sammanslagna i ordning är identiska med `JARVIS_SPEC.md` byte för byte.
- Skrivit `CLAUDE.md`, `PLAN.md` (med beroendekarta), `ASSUMPTIONS.md`, `DECISIONS.md` och
  `README.md`.
- Config-system med validering: alla standardvärden från specen, hårda tak från §7.1, och
  circuit breakers som inte går att stänga av. Ogiltig config gör att tjänsten vägrar starta.
- Tjänsteskelett: 13 backend-tjänster med hälsokontroll och JSON-loggar, webbskelett med
  design tokens från §9.1, och Docker Compose med databas, Redis, Caddy, Prometheus, Grafana.
- CI med tre jobb: backend, webb och ett röktest som startar hela systemet.

**Verifierat**
- Backend: `ruff format --check`, `ruff check`, `mypy --strict` utan anmärkningar; 75 tester
  godkända, 100 % rad- och grentäckning; `pip-audit` utan fynd.
- Webb: `eslint` utan varningar, `tsc` strict, `next build` godkänd; `npm audit` utan fynd på
  nivån "high" (en "moderate" i ett lint-verktyg, se `ASSUMPTIONS.md`).
- **Acceptanskravet:** CI-körning 2 (commit `3686cac`) är grön i alla tre jobb. Röktestet
  startar hela systemet med `docker compose up -d --build --wait` på en ren maskin och
  kontrollerar att alla 19 tjänster kör och är friska, att appen och API:t svarar över
  HTTPS, att API-schemat inte är nåbart utifrån och att bara Caddy publicerar en port (443).
  https://github.com/adam991299/app-/actions/runs/43656160972
- Lokalt gick Compose inte att köra i byggmiljön (Docker Hub begränsade nedladdningarna), så
  verifieringen av `docker compose up` vilar på CI-körningen.

**Granskning (separat agent)**
Alla standardvärden stämde mot specen, men valideringen hade luckor. Åtgärdat: belåning och
blankning gick att slå på via config-filen (borttaget, se D2b); gränser gick att göra
verkningslösa med extrema värden (golv och tak på allt, se D4b); text och sant/falskt
tolkades som siffror; dubbla nycklar i YAML togs tyst; API-schemat var nåbart utifrån;
avbilder var inte låsta till version; standardvärdena testades för glest (nu jämförs varje
värde mot en handskriven lista från specen). Kvar till Fas 7, dokumenterat i
`ASSUMPTIONS.md`: digest-låsning, Redis-lösenord och containerhärdning.

**Uppskattning av vad som är kvar**
Fas 0 av 14 faser är byggd. Byggarbetet för Fas 0.5–7 är stort (hela handelssystemet, appen,
nyhets- och lärandedelarna). Två delar går inte att snabba upp: Fas 0.5 kräver minst 10
handelsdagar (ca 2 veckor) och Fas 8 minst 60 handelsdagar (ca 3 månader) i pappershandel på
en server som är igång dygnet runt. Klockan för dem börjar gå först när VPS och IBKR
Paper-inloggning finns.

**Nästa steg**
1. Fas 0.5 mot `SimBroker` (kräver inget av Adam): delade gränssnitt, databasschema,
   `BrokerAdapter`, risk-engine med nödstopp, order-tillståndsmaskin, avstämning,
   trendföljningsstrategi, hemskärm.
2. Koppla mot IBKR Paper och driftsätta på VPS när Adam har svarat på frågorna.
