## 13. Byggordning (faser med acceptanskrav)

**Fas 0 – Plan och skelett**
Repo-struktur, Docker Compose, CI (lint, typkontroll, tester), `README.md` på svenska, `docs/ASSUMPTIONS.md`, och config-system med validering.
✅ `docker compose up` startar alla tomma tjänster, och CI är grön.

**Fas 0.5 – Den tunna versionen hela vägen (§00.5)**
Amerikanska aktier, en strategi, IBKR Paper, risk-engine med nödstopp, avstämning, test- och live-miljöer (§11), och en enkel men redan snygg hemskärm enligt §9.1.
✅ Körs automatiskt i minst 10 handelsdagar utan fel eller manuella ingrepp (utöver 2FA). Varje affär går att följa från signal till fyllnad. Kill switch testad. Hemskärmen granskad med skärmdumpar.

**Fas 1 – Data**
Kalendrar, universum, historik- och realtidsdata från IBKR Paper, datakvalitetskontroller.
✅ Historik för minst 200 instrument över alla tillgångsslag sparad och kvalitetskontrollerad.

**Fas 2 – Research-labb**
Kostnadsmodell, vektoriserad och händelsedriven backtester, walk-forward, holdout, Deflated Sharpe, Monte Carlo och lookahead-test.
✅ En känd enkel strategi ger samma resultat i båda backtestrarna (inom tolerans), och lookahead-testet fångar ett avsiktligt inplanterat fel.

**Fas 3 – Strategibibliotek och regimer**
Alla strategier i §6.1, regimklassificering och livscykel.
✅ Rapport på svenska över vilka kandidater som klarar valideringen. Det är **helt okej om ingen klarar den**. Då säger rapporten det ärligt och Jarvis handlar inte.

**Fas 4 – Nyhetsmotor**
Källplugins, avduplicering, Claude-analys med JSON-validering, features och kostnadstak.
✅ Nyheter strömmar in, kopplas rätt till instrument (stickprov på 50 st ≥ 90 % rätt) och lagras med mottagningstid.

**Fas 4.2 – Politikersignaler (§5.4)**
Parsers för Senatens och representanthusets rapporter, utskottsdata, features och backtest från publiceringsdatum.
✅ Historik sedan 2012 inläst och stickprovskontrollerad mot original-PDF:er (≥ 95 % korrekta). Testet som stoppar användning av affärsdatum som signaldatum finns och fungerar. En ärlig rapport på svenska visar om signalen tillför något efter kostnader.

**Fas 4.5 – Learning Loop (§5.5)**
Affärsjournal, efteranalys, märkning av nyhetsutfall, modellregister, champion/challenger med skuggkörning, driftdetektering, research-agent i sandlåda, och mätvärden.
✅ En medvetet sämre challenger ska förlora och aldrig befordras. En medvetet bättre challenger (på syntetisk data med en inplanterad edge) ska vinna. Återställning till förra versionen fungerar. Research-agenten kan inte röra risk- eller live-kod (testas).

**Fas 5 – Risk och exekvering mot papperskonto**
Risk-engine, order-tillståndsmaskin, bracket-order, avstämning och återhämtning.
✅ Kaostester: döda tjänster mitt i en order, koppla bort gatewayn, skicka dubbla signaler. Inga dubbla order, inga positioner utan stop, och läget stämmer alltid mot mäklaren.

**Fas 6 – Appen**
Alla vyer i §9 och PWA med notiser.
✅ Lighthouse ≥ 95 i Performance, Accessibility och Best Practices på mobil. Mörkt läge (standard) och ljust läge granskade med skärmdumpar mot §9.1. Fungerar från iPhone-hemskärmen. Noll kända buggar.

**Fas 6.2 – Samtidighet och möjlighetsnotiser (§6.4.1, §9.2.2)**
Portföljhanterare, delpositioner, gränser för samtidighet, de tre lägena per motor, möjlighetskort med nedräkning och priskontroll.
✅ Simulering: 5 daytrades, 10 swingpositioner och 2 krypto- och råvarupositioner hanteras samtidigt utan motstridiga order och utan överskriden budget. En kraschad strategi påverkar inte de andra. Ett förslag som godkänns efter att priset rört sig kräver ny bekräftelse. Ett utgånget förslag kan inte godkännas.

**Fas 6.5 – "Fråga Jarvis" (§9.2.1)**
Chatt med tool use, rika kort, röst in och ut, säkerhetsnivåer, och skydd mot prompt injection.
✅ 30 testfrågor (förklaringar, skanningar, analyser och åtgärder) besvaras korrekt utifrån riktig data. Röstorder på nivå 3 kräver alltid bekräftelse. Försök att via chatt eller röst slå på live-handel, höja riskgränser eller stänga av kill switch misslyckas (testas automatiskt). En nyhet med en inplanterad instruktion ("sälj allt") leder inte till någon åtgärd. Svarstiden i röstläge mäts.

**Fas 7 – Drift och säkerhet**
Deploy till VPS, Caddy, Cloudflare Access/Tailscale, passkeys, övervakning, backup och watchdog.
✅ Säkerhetschecklista genomgången. Återställning från backup testad.

**Fas 8 – Pappershandel i minst 60 handelsdagar**
Jarvis körs helt automatiskt i papper. Veckorapporter. Avvikelser mot backtest och mot index analyseras.
✅ Adam får en slutrapport: vad som fungerade, vad som inte gjorde det, och om systemet uppfyller kraven för LIVE-LITEN enligt §6.4. Rekommendationen ska vara ärlig även om svaret är nej.

**Fas 9 – Live (bara när Adam aktivt väljer det)**
Enligt §9.4.

**Fas 10 – Utvärdering efter 6 och 12 månader live**
En ärlig rapport om Jarvis jämfört med index efter alla kostnader och skatt, med statistisk osäkerhet (konfidensintervall), och en tydlig rekommendation: skala upp, fortsätt som idag, minska eller stäng av och gå över till indexfonden. Utvärderingen följer stoppreglerna för hela projektet i §16.

---

