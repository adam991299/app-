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
| A13 | Att IBKR:s papperskonto får samma gratis realtidsdata (Cboe One/IEX) som huvudkontot. | Fas 0.5 |
| A14 | Att Jarvis ryms på 1 OCPU och 6 GB. Adams Oracle-konto tillåter bara det (2026-11-15), inte de rapporterade 2 OCPU/12 GB. Uppskattat behov: ca 4 GB. Mäts när allt kör på servern; Grafana och Prometheus kan stängas av om minnet inte räcker. | Fas 0.5 |
| A15 | Att en andra användare utan uttagsrätt går att skapa på ett privat ISK-konto. | Före riktig handel |
| A12 | IBKR:s tider för daglig omstart och intervallet för ny 2FA-inloggning (specen anger "normalt en gång i veckan"). | Fas 0.5 |

## Verifierat

| Datum | Vad | Källa |
|---|---|---|
| 2026-11-15 | Papperskontot har eget användarnamn och lösenord, som visas och återställs under Settings → Paper Trading Account. | interactivebrokers.com/docs (Finding your paper user credentials) |
| 2026-11-15 | `gnzsnz/ib-gateway` använder `TWS_USERID`, `TWS_PASSWORD` och `TRADING_MODE` (standard paper). Taggen och körning på arm64 är fortfarande oprövade (A2). | hub.docker.com/r/gnzsnz/ib-gateway |
| 2026-11-15 | Claudes IBKR-koppling i byggsessionen kan läsa dagskurser (prövat med AAPL). Den ger data till Claude, inte till Jarvis, och passar bara för små stickprov. | eget anrop |
| 2026-11-15 | IBKR erbjuder gratis realtidsdata (ej konsoliderad) för amerikanska aktier och ETF:er från Cboe One och IEX; fördröjd data släpar 10–20 min. | interactivebrokers.com, sidan Market Data Pricing |
| 2026-11-15 | `gnzsnz/ib-gateway` publiceras för både amd64 och arm64 (krävs för Oracles gratisservrar). | hub.docker.com/r/gnzsnz/ib-gateway/tags |
| 2026-11-14 | `ib_async` underhålls: version 2.1.0 släpptes 2025-12-08. Kontrolleras igen innan broker-koden skrivs, eftersom senaste släpp då är snart ett år gammalt. | pypi.org/pypi/ib_async |
| 2026-11-14 | Next.js 16.4.6 är aktuell version; appen bygger med App Router och TypeScript strict. | registry.npmjs.org, `npm run build` |

## Kända begränsningar
- **Orderhanteringen:** se listan i beslut D17 (insättningar/uttag, en instans, kvittering av
  problem, 7 dagars fyllnadshistorik).
- **Docker-avbilderna är låsta till exakt version men inte till digest.** Digest-låsning och
  automatiska uppdateringar görs i Fas 7 (§10). `ib-gateway` använder taggen `stable` tills
  den verifieras i Fas 0.5 (A2).
- **Prometheus samlar bara in sig själv.** Tjänsterna får mått (`/metrics`) när de får
  innehåll (§11).
- **En känd sårbarhet av nivån "moderate" i ett utvecklingsverktyg** (`minimatch` via
  `eslint-config-next`, GHSA-g3hv-75wg-m249). Den finns bara i lint-verktyget och följer inte
  med i det som körs på servern. Ingen rättad version finns för Next.js 16 ännu. CI stoppar
  på nivån "high" och uppåt.
- **Redis saknar lösenord och containrarna saknar extra härdning** (`cap_drop`,
  `no-new-privileges`, skrivskyddat filsystem). Redis nås bara på det interna nätverket.
  Härdningen görs i Fas 7.
