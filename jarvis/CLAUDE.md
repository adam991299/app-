# Jarvis the Trader — arbetsinstruktioner

Jarvis ligger i mappen `jarvis/` i det här repot. Resten av repot är en annan app
(Närmast, Expo) och rörs inte av Jarvis-arbetet. Rotens `AGENTS.md` (Expo) gäller inte här.

**Ny session:** läs den här filen, `docs/PLAN.md` och `docs/PROGRESS.md`, och fortsätt exakt
där det slutade. Originalet är `JARVIS_SPEC.md` (oförändrat). Vid tveksamhet gäller originalet.

## Visionen
Ett helautomatiskt handelssystem åt Adam (Sverige): skannar marknader, läser nyheter, tar fram
och validerar strategier, handlar via Interactive Brokers och visas i en webbapp med
iOS-känsla. Det unika är att Jarvis **förbättrar sig själv hela tiden** (§5.5) — men "bättre"
ska alltid mätas och bevisas statistiskt. All text i appen på **svenska**; kod, kommentarer
och variabelnamn på engelska.

## Regler som aldrig bryts (§0)
1. **Ärlighet om resultat.** Inga påhittade siffror. Allt i appen kommer från körd kod och
   riktig data. Aldrig löften om vinst.
2. **Kapitalskydd före vinst.** Vid osäkerhet: handla inte.
3. **Ingen riktig handel utan Adams aktiva beslut.** Alltid IBKR Paper från start. Live kräver
   att Adam slår på det i appen med passkey och frasen `JAG FÖRSTÅR RISKEN` (§9.4).
4. **Inga hemligheter i koden.** Bara `.env` (600) eller Docker secrets. Committas aldrig.
5. **Arbeta i faser** enligt §13 med arbetscykeln nedan.
6. **Verifiera aktuella fakta** (API:er, versioner, priser, mäklarregler) i aktuell
   dokumentation. Det som inte gick att verifiera skrivs i `docs/ASSUMPTIONS.md`.
7. **Jarvis måste slå det enkla alternativet** (bred index-ETF) efter alla kostnader och skatt,
   annars säger appen det rakt ut.
8. **Språkmodeller fattar aldrig köp- eller säljbeslut.** Claude tolkar text; beslut tas av
   testade regelbaserade/statistiska modeller och risk-engine.

**Adams grundprincip (D31):** maximera vinsten efter alla kostnader oavsett kontots storlek.
Varje del ska anpassa sig efter kapitalet (rangordning efter nettovinst i kronor, strategier
och aktielista efter vad som lönar sig vid nuvarande budget). Riskgränserna står över detta.

Koden ska gå att förstå för Adam: korta moduler, tydliga namn, och
`docs/HUR_DET_FUNGERAR.md` på enkel svenska (signal → order).

## Arbetscykeln per fas (§00.2) — utan undantag
1. **Läs** fasens specfiler i `docs/spec/` igen.
2. **Planera** delsteg och test av acceptanskraven i `docs/PLAN.md`.
3. **Bygg** i små steg, kör testerna efter varje steg.
4. **Verifiera** varje acceptanskrav (✅ i §13) med riktiga körningar. Gränssnitt:
   skärmdumpar i mobil- och datorstorlek (Playwright) som granskas mot §9.1.
5. **Granska** med en separat agent som inte skrivit koden (fokus `risk/`, `execution/`,
   `broker/`, säkerhet, gränsfall). Åtgärda allt.
6. **Städa:** inga TODO:er, ingen bortkommenterad eller död kod, inga tillfälliga lösningar.
7. **Dokumentera:** `PROGRESS.md`, `PLAN.md`, berörda docs. Commit med tydligt meddelande.
8. **Rapportera** till Adam på enkel svenska: byggt, testat, återstår, behövs av honom.

En fas är klar först när alla punkter är klara.

## Kvalitetskrav (§00.3)
- Varje funktion färdig på riktigt: fungerande, testad, felhanterad, dokumenterad.
- Inga platshållare i det som levereras: inga påhittade data, inga "kommer snart", inga tomma
  vyer utan genomtänkt tomt läge. Stubbar under bygget märks och tas bort innan fasen är klar.
- Noll kända buggar när en fas avslutas. Varje bugg får ett test som hade fångat den.
- **100 % täckning** i `risk/`, `execution/`, `broker/`, `economics/`; minst 85 % i övrig
  backend; Playwright-e2e för viktiga flöden. mypy strict, TypeScript strict, lint utan
  varningar. CI grön.
- Varje anrop utåt har timeout, återförsök med backoff och säkert felbeteende. Aldrig tysta
  krascher.
- Hellre fråga än gissa. Oklarheter och beslut skrivs i `docs/DECISIONS.md`.
- Gör aldrig något enklare i smyg — säg öppet om något inte går att bygga som det står.

## Tempo (§00.4)
Arbeta självständigt; vänta på Adam bara för inloggningar, nycklar, betalningar, 2FA och
beslut som inte kan ångras. Oberoende delar byggs parallellt av underagenter i egna git
worktrees, efter att delade gränssnitt (API-kontrakt, databasschema, design tokens) är
definierade. `risk/`, `execution/`, `broker/`, `economics/` skyndas aldrig.

## Designkänslan (§9.1)
Ett lugnt kontrollrum mitt i natten där en lojal, extremt kompetent agent redan har läget
under kontroll. Mörkt, djupt, lite mystiskt — aldrig rörigt. iOS-precision med helt egen
identitet (ingen likhet med filmer eller andra varumärken). Huvudvyn visar bara det
viktigaste; detaljer ett tryck bort.
- **Orben** är Jarvis ansikte: andas lugnt, pulserar vid analys, bärnsten vid varning, dämpad
  vid paus. Läget ska synas på en sekund.
- **Ton:** lugn, självsäker, kortfattad, lojal, ärlig. "Jag har stängt …". Inga utropstecken,
  inget säljigt. Vågar säga "Jag vet inte".
- **Färger:** bakgrund `#05070B`, yta `#0D1117`, upphöjd `#141A23`, text `#F2F4F8` /
  `#8A93A3`, glöd cyan `#4CE0FF` → violett `#7B5CFF` (sparsamt), vinst `#30D158`,
  förlust `#FF453A`, varning `#FFB340`. Allt via design tokens — inga engångsfärger.
- Systemfontstack, `tabular-nums`, iOS-typskala, frostat glas, 8-punktsgrid, fjäderanimationer,
  `prefers-reduced-motion`, WCAG AA går före stämning, grönt/rött alltid med +/− och pilar.

## Kommandon
| Vad | Var | Kommando |
|---|---|---|
| Backend-kontroller | `backend/` | `uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest && uv run pip-audit --skip-editable` |
| 100 %-kravet | `backend/` | `uv run coverage report --include='src/jarvis/risk/*,src/jarvis/broker/*,src/jarvis/execution/*,src/jarvis/economics/*' --fail-under=100` |
| Webb-kontroller | `web/` | `npm run lint && npm run typecheck && npm run build` |
| Starta allt | `jarvis/` | `scripts/init-env.sh && docker compose up -d --build --wait` |
| Röktest | `jarvis/` | `scripts/smoke.sh` |
| Databastester som root | `backend/` | starta PostgreSQL som användaren `postgres` och sätt `JARVIS_TEST_POSTGRES=host:port` (D13) |

## Struktur
- `backend/src/jarvis/` — Python-paketet, en modul per ansvar: `config/`, `service/`,
  `domain/` (delade typer), `risk/`, `broker/` (`BrokerAdapter`, `SimBroker`), senare
  `execution/`, `economics/` …
- `web/` — Next.js-appen (PWA)
- `config/default.yaml` — standardvärden från specen, validerade vid start
- `deploy/` — Caddy, Prometheus
- `docs/` — plan, logg, antaganden, beslut och specfilerna

## Specifikationen (ordagrant uppdelad i `docs/spec/`)
| Fil | Innehåll |
|---|---|
| `000-inledning.md` | Rubrik och inledning |
| `00-arbetssatt.md` | §00 Hur arbetet ska gå till |
| `00b-roll-och-regler.md` | §0 Roll och regler |
| `01-adams-checklista.md` | §1 Vad Adam behöver ordna |
| `01.5-ekonomi.md` | §1.5 Ekonomin, break-even, ISK, "kan jag leva på det?" |
| `01.6-dygnet-runt.md` | §1.6 Drift dygnet runt, nattläge, 2FA |
| `01.7-utlandsflytt.md` | §1.7 Flytt utomlands |
| `02-arkitektur.md` | §2 Arkitektur och teknikval |
| `03-marknader.md` | §3 Marknader, instrument, universumfilter |
| `04-data.md` | §4 Marknadsdata, fundamenta, makro |
| `05-nyheter.md` | §5 Nyhetsmotorn |
| `05.4-politiker.md` | §5.4 Politikersignaler |
| `05.5-learning-loop.md` | §5.5 Learning Loop (systemets hjärta) |
| `06-strategimotor.md` | §6 Strategier, validering, livscykel, samtidighet |
| `07-risk.md` | §7 Riskmotorn och kapitalkontrollen (§7.1) |
| `08-exekvering.md` | §8 Exekvering |
| `09-app.md` | §9 Appen, chatt/röst, möjlighetsnotiser, byte till live |
| `10-sakerhet.md` | §10 Säkerhet |
| `11-drift.md` | §11 Drift, övervakning, nödplan, dödmansgrepp |
| `12-skatt.md` | §12 Skatt och bokföring |
| `13-byggordning.md` | §13 Faser med acceptanskrav |
| `14-teststrategi.md` | §14 Teststrategi |
| `15-definition-of-done.md` | §15 Definition of Done |
| `15.1-framtida-produkt.md` | §15.1 Om Jarvis blir en produkt |
| `16-stoppregler.md` | §16 Stoppregler för hela projektet |
