# Antaganden — sådant som inte är verifierat ännu

Regel 6 i §0: aktuella fakta ska verifieras mot aktuell dokumentation innan något byggs mot
dem. Här står det som **inte** är verifierat. Varje punkt verifieras i den fas som anges och
flyttas då till "Verifierat" med datum och källa.

## Inte verifierat

| # | Antagande | Verifieras i |
|---|---|---|
| A1 | ISK finns hos IBKR Ireland för svenska privatpersoner, och vilka begränsningar kontot har (blankning, belåning, derivat, terminer, krypto). | Fas 0.5, tillsammans med Adam |
| A2 | Miljövariablerna för `ghcr.io/gnzsnz/ib-gateway` (`TWS_USERID`, `TWS_PASSWORD`, `TRADING_MODE`) och taggen `stable` stämmer med aktuell version. Tjänsten startas inte förrän i Fas 0.5. | Fas 0.5 |
| A3 | IBKR:s gräns för samtidiga realtidsrader (specen anger "vanligtvis 100") och priserna på datapaket. | Fas 1 |
| A4 | IBKR:s regler för historikhämtning (pacing). | Fas 1 |
| A5 | Vilka ETF:er en EU-privatperson får köpa (PRIIPs/KID). | Fas 1 |
| A6 | PDT-regler för amerikanska aktier på Adams kontotyp. | Fas 3 (daytrading-spåret) |
| A7 | Aktuella Claude-modellnamn och priser för nyhetsanalys och chatt. | Fas 4 |
| A8 | Villkor och robots.txt för varje nyhetskälla, samt SEC EDGAR:s rate limits. | Fas 4 |
| A9 | Format och villkor för Senatens eFD och representanthusets Clerk. | Fas 4.2 |
| A10 | Att KBLab:s svenska Whisper-modell finns och hur den presterar. | Fas 6.5 |
| A11 | Årets skattefria grundnivå och schablonsats för ISK. Fälten i `config/default.yaml` är därför tomma, och ekonomimodulen ska vägra räkna skatt tills de är ifyllda från Skatteverket. | Ekonomimodulen |
| A12 | IBKR:s tider för daglig omstart och intervallet för ny 2FA-inloggning (specen anger "normalt en gång i veckan"). | Fas 0.5 |

## Verifierat

| Datum | Vad | Källa |
|---|---|---|
| 2026-11-14 | `ib_async` underhålls: version 2.1.0 släpptes 2025-12-08. Kontrolleras igen innan broker-koden skrivs, eftersom senaste släpp då är snart ett år gammalt. | pypi.org/pypi/ib_async |
| 2026-11-14 | Next.js 16.4.6 är aktuell version; appen bygger med App Router och TypeScript strict. | registry.npmjs.org, `npm run build` |

## Kända begränsningar
- **Docker-avbildernas taggar är inte låsta till digest.** `timescaledb:latest-pg17`,
  `prometheus:latest` och `grafana:latest` låses till exakta versioner i Fas 7 (§10 kräver
  låsta beroenden).
- **Prometheus samlar bara in sig själv.** Tjänsterna får mått (`/metrics`) när de får
  innehåll (§11).
