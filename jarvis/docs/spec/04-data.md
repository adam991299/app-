## 4. Data

### 4.1 Marknadsdata
- Realtid: kurser, bid/ask, volym och orderdjup där det finns, via IBKR
- **Viktig begränsning:** IBKR ger som standard ett begränsat antal samtidiga realtidsrader (vanligtvis 100, fler med högre courtage/kapital eller köpta "Quote Booster"-paket). Jarvis kan alltså **inte** strömma realtid för alla instrument samtidigt. Designa skanningen i nivåer:
  1. **Hela universumet:** skannas på dagliga och timvisa barer samt IBKR:s marknadsskannrar.
  2. **Bevakningslista** (de ~50–80 mest intressanta just nu): realtid.
  3. **Öppna positioner:** alltid realtid, och har förtur till raderna.
  Kontrollera aktuella gränser och priser för datapaketen, och visa Adam en kostnadsjämförelse innan något beställs.
- Historik: dagliga och intradagsbarer. IBKR har begränsningar på historisk data (pacing). Bygg en köad hämtare som respekterar dem och cachar allt lokalt.
- Föreslå åt Adam en kompletterande betald historikkälla för backtests över många år (ta fram aktuella alternativ och priser). **Justera för splittar och utdelningar** och arbeta mot **survivorship bias** (ta med avnoterade bolag när det går, och dokumentera annars att biasen finns).
- Datakvalitet: upptäck luckor, extremvärden, dubbletter och stale data. Instrument med dålig data handlas inte.

### 4.2 Fundamenta och händelser
- Rapportdatum, utdelningsdatum, splittar
- Grundläggande nyckeltal (P/E, tillväxt, marginaler, skuld) där en källa finns
- **Insynshandel:** Finansinspektionens insynsregister (Sverige) och SEC Form 4 (USA)
- Blankningspositioner (FI:s register för Sverige)

### 4.3 Makro
- Kalender: Riksbanken, Fed, ECB, KPI/CPI, arbetsmarknadsdata, BNP, PMI, OPEC-möten (för olja)
- Räntor, dollarindex, VIX, råvarupriser — används för regimklassificering

---

