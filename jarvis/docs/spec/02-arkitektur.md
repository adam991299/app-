## 2. Arkitektur

```
┌──────────────────────────────── VPS (Docker Compose) ───────────────────────────────┐
│                                                                                      │
│  ib-gateway  ◄──►  broker-service ◄──► execution-engine ◄──► risk-engine             │
│  (IBC, auto-                ▲                 ▲                    ▲                  │
│   restart)                  │                 │                    │                  │
│                     market-data-service   strategy-engine ◄── research-lab            │
│                             │                 ▲               (backtest, walk-fwd)    │
│                             ▼                 │                                       │
│                   TimescaleDB (Postgres) ◄── news-service (RSS/API + Claude-analys)   │
│                             ▲                                                         │
│                     Redis (pub/sub, kö, cache)                                        │
│                             ▲                                                         │
│                    api (FastAPI + WebSocket) ◄──► web (Next.js PWA, iOS-design)       │
│                                                                                      │
│  scheduler · watchdog · notifier (Web Push + e-post) · backup · Prometheus/Grafana  │
└──────────────────────────────────────────────────────────────────────────────────────┘
        Åtkomst endast via Cloudflare Access eller Tailscale + passkey-inloggning
```

**Teknikval:**

- **Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, asyncio
- **IBKR:** IB Gateway i Docker (t.ex. `gnzsnz/ib-gateway-docker` med IBC) och `ib_async` som klient. Kontrollera först att biblioteket fortfarande underhålls och välj annars IBKR:s officiella `ibapi` eller Web API.
- **Data:** PostgreSQL + TimescaleDB (tidsserier), Redis
- **Analys:** pandas/polars, numpy, scipy, statsmodels, scikit-learn, vectorbt eller en egen vektoriserad backtester plus en händelsedriven backtester för slutvalidering
- **Kalendrar:** `exchange_calendars` för helgdagar, halvdagar och öppettider per börs. Allt lagras i UTC och visas i Europe/Stockholm.
- **Frontend:** Next.js (App Router) + TypeScript, Tailwind, Framer Motion, TanStack Query, lightweight-charts (TradingView) för grafer, installerbar som PWA
- **Drift:** Docker Compose, Caddy (HTTPS), Prometheus + Grafana, Sentry eller motsvarande, dagliga krypterade backuper

**Learning-service** (§5.5) är en egen tjänst med modellregister (t.ex. MLflow), affärsjournal, skuggkörning och research-agentens sandlåda. Sandlåda är en separat container utan nätverksåtkomst till mäklaren och utan skrivrätt till live-konfigurationen.

Allt mot mäklaren går via ett **broker-interface** (`BrokerAdapter`) så att fler mäklare (t.ex. Avanza) kan läggas till senare utan att resten av systemet ändras. Det ska också finnas en `SimBroker` för tester.

---

