# Framstegslogg

Nyast överst. Varje post: vad som gjorts, hur det verifierats och vad som är nästa steg.

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
- Backend: `ruff format --check`, `ruff check`, `mypy --strict` utan anmärkningar; 54 tester
  godkända, 100 % rad- och grentäckning.
- Webb: `eslint` utan varningar, `tsc` strict, `next build` godkänd.
- `docker compose config` godkänner filen.

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
