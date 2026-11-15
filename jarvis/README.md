# Jarvis the Trader

Ett helautomatiskt handelssystem som körs på en egen server, handlar via Interactive Brokers
och visas i en webbapp. Jarvis startar **alltid i pappershandel**. Riktig handel kan bara slås
på av Adam själv i appen.

> **Läget just nu:** Fas 0 (skelettet). Alla tjänster startar och svarar, men ingen handel,
> ingen data och inga vyer finns ännu. Se [`docs/PLAN.md`](docs/PLAN.md) och
> [`docs/PROGRESS.md`](docs/PROGRESS.md).

Jarvis lovar ingen vinst. Varje resultat jämförs med att bara äga en bred indexfond, efter
alla kostnader och skatt, och appen ska säga rakt ut om Jarvis inte slår den.

## Det här behöver Adam ordna

- [ ] **IBKR-konto** (IBKR Ireland) med **ISK**, samt ett **Paper Trading-konto**
- [ ] En **separat IBKR-användare** för boten, med handelsrättigheter men **utan rätt att ta
      ut eller flytta pengar**
- [ ] **Marknadsdata** hos IBKR för de börser som ska handlas (Nasdaq Nordic, USA,
      råvarubörser). En kostnadslista tas fram i Fas 1, innan något beställs.
- [ ] En **API-nyckel till Anthropic** (Claude) för nyhetsanalys
- [ ] En **VPS i EU** (t.ex. Hetzner Helsingfors, 4 vCPU/8 GB RAM räcker att börja med) och
      ett **domännamn**
- [ ] **IBKR Mobile** på telefonen för att godkänna 2FA

**Ärligt om 2FA:** IB Gateway kräver ny inloggning med jämna mellanrum (normalt en gång i
veckan), och då måste du godkänna med 2FA i mobilen. Jarvis kommer att skicka en push-notis
när det behövs. Om du inte svarar skyddas öppna positioner av stoppordrar som ligger hos
mäklaren, och inga nya affärer tas förrän inloggningen är godkänd. Allt annat ska vara
automatiskt.

## Starta

Kräver Docker med Compose.

```bash
cd jarvis
scripts/init-env.sh
docker compose up -d --build --wait
scripts/smoke.sh
```

- `scripts/init-env.sh` skapar filen `.env` med slumpade lösenord. Den körs en gång och skriver
  aldrig över en befintlig fil. `.env` får aldrig committas.
- Appen nås sedan på `https://localhost` (webbläsaren varnar för certifikatet lokalt; på
  servern hämtar Caddy ett riktigt certifikat för domänen i `JARVIS_DOMAIN`).
- `scripts/smoke.sh` kontrollerar att alla tjänster kör och svarar.

## Stoppa, uppdatera, felsöka

| Vad | Kommando (i `jarvis/`) |
|---|---|
| Se status för alla tjänster | `docker compose ps` |
| Läsa loggar för en tjänst | `docker compose logs --tail 100 risk-engine` |
| Stoppa allt (data ligger kvar) | `docker compose down` |
| Uppdatera efter ny kod | `git pull && docker compose up -d --build --wait && scripts/smoke.sh` |

Paus, kill switch, driftsättning till server och återställning med ett kommando byggs i
Fas 0.5 och Fas 7 och beskrivs här när de finns.

**Om en tjänst inte startar:** läs dess logg. Ett vanligt skäl är en ogiltig inställning —
Jarvis vägrar då starta och loggen säger exakt vilket värde som är fel.

## Inställningar

Standardvärdena står i [`config/default.yaml`](config/default.yaml) och kommer från
specifikationen. Ändra inte den filen i drift: lägg dina egna värden i en egen fil och peka ut
den med miljövariabeln `JARVIS_CONFIG_OVERRIDE`. Allt valideras vid start.

| Avsnitt | Betyder |
|---|---|
| `app` | Språk och vilken tidszon appen visar tider i. Börsernas öppettider påverkas inte. |
| `night_mode` | Mellan dessa klockslag gäller strängare gränser och färre notiser. |
| `markets` | Vilka marknader Jarvis får handla. Terminer och pre/after-market är avstängda. |
| `universe` | Lägsta dagsomsättning för att ett instrument ska få handlas. |
| `risk.per_trade` | Högst 0,75 % av kapitalet i risk per affär; högst ¼ Kelly. |
| `risk.portfolio` | Tak per position, sektor, krypto och råvaror; kassareserv på minst 5 %. |
| `risk.circuit_breakers` | Automatiska stopp vid dags-, vecko- och toppförlust. Kan inte stängas av. |
| `risk.turnover` | Skydd mot överhandel: max omsättning och krav på vinst jämfört med kostnad. |
| `risk.gap` | Hur stor förlust en position får ge om kursen gapar förbi stoppen. |
| `risk.technical_max` | Hårda tak som skyddar mot buggar och felklick. |
| `risk.concurrency` | Max antal öppna positioner och samtidiga daytrades. |
| `risk.daytrading` | Egna förlustgränser för daytrading. |
| `validation` | Kraven en strategi måste klara innan den får handla. |
| `lifecycle` | Hur länge en strategi måste gå i papper innan den får riktiga pengar. |
| `opportunities` | Max antal möjlighetsnotiser per dag och när priset måste bekräftas igen. |
| `tax` | Skattemodell (ISK eller vanlig kapitalvinst). Årets ISK-siffror fylls i från Skatteverket. |
| `economics` | När appen varnar för att kostnaderna är för höga; buffert som aldrig handlas. |
| `check_in` | Hur ofta du behöver checka in innan Jarvis drar ner risken. |
| `project_stop_rules` | Stoppreglerna för hela projektet (§16). |

Handelsläge (papper eller live), belåning och blankning finns medvetet **inte** i någon fil.
Jarvis är long-only och obelånad, och sådant som ökar risken ska bara gå att ändra i appen.

## Så är det uppbyggt

```
jarvis/
├── JARVIS_SPEC.md        Originalspecifikationen (ändras aldrig)
├── backend/              Python: alla tjänster delar paketet `jarvis`
├── web/                  Webbappen (Next.js)
├── config/default.yaml   Standardinställningar
├── deploy/               Caddy (HTTPS) och Prometheus
├── scripts/              init-env.sh, smoke.sh
└── docs/                 Plan, logg, antaganden, beslut och specen per område
```

Tjänsterna (se `docker-compose.yml`): `api`, `broker-service`, `execution-engine`,
`risk-engine`, `market-data-service`, `strategy-engine`, `research-lab`, `news-service`,
`learning-service`, `scheduler`, `watchdog`, `notifier`, `backup`, `web`, samt `db`
(TimescaleDB), `redis`, `caddy`, `prometheus` och `grafana`. `ib-gateway` startas separat med
`docker compose --profile broker up -d` när IBKR-inloggningen finns.

Bara Caddy är nåbar utifrån (port 443). Allt annat ligger på ett internt nätverk.

## För utvecklare

```bash
cd jarvis/backend && uv sync && uv run ruff check . && uv run mypy && uv run pytest
cd jarvis/web && npm ci && npm run lint && npm run typecheck && npm run build
```

Arbetssätt och kvalitetskrav står i [`CLAUDE.md`](CLAUDE.md).
