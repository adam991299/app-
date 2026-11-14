## 5. Nyhetsmotorn ("Jarvis läser allt")

### 5.1 Källor (bygg varje källa som en egen plugin)
- Pressmeddelanden: Nasdaq Nordic bolagsmeddelanden, MFN, Cision/Newsweb, GlobeNewswire
- USA: SEC EDGAR (8-K, 10-Q, 10-K, Form 4) via deras officiella API (följ rate limits och User-Agent-krav)
- Finansnyheter via RSS från källor som tillåter det. **Följ varje källas villkor och robots.txt, och skrapa inte betalväggar.**
- Centralbanker och myndigheter (pressmeddelanden, räntebesked)
- Valfritt: en betald nyhets-API om Adam vill (ta fram alternativ och priser)

### 5.2 Bearbetning
1. Normalisera, ta bort dubbletter (samma nyhet från flera källor) och **tidsstämpla när vi tog emot nyheten**, inte bara publiceringstiden. Det förhindrar lookahead-bias i backtester.
2. Koppla nyheten till instrument (ticker, ISIN, bolagsnamn och alias).
3. Analysera med Claude API. Använd en snabb modell för klassificering av stora volymer och en starkare modell för viktiga händelser. Verifiera aktuella modellnamn i Anthropics dokumentation. Svaret ska alltid vara **strukturerad JSON** som valideras med Pydantic:
   ```json
   {
     "instrument_ids": ["..."],
     "event_type": "earnings|guidance|m_and_a|insider|macro|legal|product|rating|other",
     "sentiment": -1.0,
     "surprise": "none|low|medium|high",
     "relevance": 0.0,
     "time_horizon": "intraday|days|weeks",
     "summary_sv": "En mening på svenska",
     "confidence": 0.0
   }
   ```
4. Nyhetssignaler blir **features** till strategierna. De lagras med full historik så att de kan backtestas. Använd dem aldrig okontrollerat som köpknapp.
5. Kostnadskontroll: ett budgettak för API-anrop per dag som går att ändra i appen, med cache och batchning.

---

