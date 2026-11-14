## 6. Strategimotorn ("Jarvis hittar sin egen strategi")

Adam vill att Jarvis testar och väljer handelsstil själv. Det gör du så här:

### 6.1 Strategibibliotek (alla parametriserade)
- **Trendföljning / tidsseriemomentum** (glidande medelvärden, Donchian-breakout, ATR-baserade exits) — fungerar för aktier, ETF:er, råvaror och krypto
- **Tvärsnittsmomentum** (rankning av universum, månatlig/veckovis rebalansering)
- **Mean reversion** på kort sikt (t.ex. RSI(2), Bollinger, överreaktion efter gap)
- **Breakout med volymbekräftelse**
- **Post-earnings drift** och **nyhetsdrivna händelsestrategier** (byggda på features från §5)
- **Insyns-signal** (kluster av insynsköp)
- **Parhandel / statistisk arbitrage** (endast om kontot tillåter blankning — annars avstängd)
- **Säsongs- och kalendereffekter** (t.ex. månadsskifte) — bara som filter
- **Regimfilter:** klassificera marknaden (trend upp/ned, sidledes, hög/låg volatilitet, risk-on/off) och slå på eller av strategier beroende på regim

### 6.2 Tidshorisonter som testas
Intradag (minutbarer), swing (dagar–veckor) och position (veckor–månader). Kostnaderna avgör ofta: om courtage, spread och slippage äter upp förväntad vinst ska Jarvis välja bort horisonten.

### 6.2.1 Daytrading-spåret (en egen motor)
Adam vill att Jarvis ska kunna daytrada. Bygg det som en egen motor, med samma valideringskrav som allt annat men med extra regler:
- **Strategikandidater:** opening range breakout, VWAP-återgång, momentum i kursen direkt efter nyheter och pressmeddelanden (där en snabb nyhetsmotor kan ge ett verkligt försprång), gap fill/gap and go, och relativ styrka mot index under dagen
- **Data:** realtid med låg fördröjning för bevakningslistan och sekund- eller minutbarer. Mät latensen från nyhet till order, och visa den i appen.
- **Kostnader är avgörande:** daytrading har flest affärer och därför högst kostnader. Kostnadsmodellen ska vara extra noggrann (minimicourtage, spread under dagen, mindre likviditet runt öppning och stängning).
- **Alla positioner stängs före börsens stängning** (om inte strategin är godkänd för att behålla positioner över natten)
- **Egna gränser:** max dagsförlust för daytrading-motorn separat (standard 1 % av kapitalet), max antal affärer per dag, och paus efter 3 förluster i rad
- **Regler:** kontrollera aktuella regler för mönsterdaytrading (PDT) på amerikanska aktier för kontotypen, och vad som gäller i ISK
- **Rakt besked:** om daytrading inte klarar valideringen efter kostnader stängs motorn av, och swing/position får kapitalet. Det är så Jarvis skyddar Adams pengar.

### 6.3 Validering — det här skiljer proffs från amatörer
Varje strategikandidat måste klara **alla** stegen nedan. Gränsvärdena ska gå att ändra i config, men standard är:

1. **Realistisk kostnadsmodell:** IBKR:s verkliga courtage per börs, spread, slippage (som beror på volatilitet och ordervolym i förhållande till ADV), valutaväxlingsavgift och ränta på eventuell kassa.
2. **Ingen lookahead:** signaler beräknas på stängda barer och utförs tidigast vid nästa bar. Testa detta med ett automatiskt test som förskjuter data och kontrollerar att resultatet inte förändras orimligt.
3. **Walk-forward-analys** med rullande in-sample/out-of-sample-fönster. Bara out-of-sample-resultat räknas.
4. **Ett låst holdout-set** (senaste 20 % av historiken) som bara används en gång per kandidat, vid slutvalideringen.
5. **Korrigering för multipla tester:** räkna hur många varianter som provats och använd Deflated Sharpe Ratio eller motsvarande. Ju fler varianter som testats, desto högre krav.
6. **Robusthet:** parameterstabilitet (närliggande parametrar ska också fungera — inga spetsiga optimum), Monte Carlo på affärsordningen, test under olika regimer och över olika marknader.
7. **Minimikrav (standard):** ≥ 100 affärer out-of-sample, Deflated Sharpe > 0,95-sannolikhet, max drawdown ≤ 20 %, profit factor ≥ 1,3 efter kostnader, och positivt resultat i minst 60 % av walk-forward-fönstren.
8. **Jämförelsekrav:** strategin (och hela portföljen av strategier) måste ha bättre riskjusterad avkastning än den valda index-ETF:en efter alla kostnader, eller tillföra tydlig diversifiering (låg korrelation och lägre drawdown).
9. **Försöksregister:** varje backtest som körs sparas med parametrar och resultat (`research_trials`-tabellen), även de misslyckade. Antalet försök används i korrigeringen i punkt 5. Ju mer en strategi har finjusterats, desto hårdare ska den bedömas.
10. **Enkelhetskrav:** max 4–5 fria parametrar per strategi. Föredra strategier med en ekonomisk förklaring (varför edgen borde finnas och vem som är på andra sidan av affären). Strategier som bara "råkar fungera" i datan rankas ned.
11. **Kapacitet:** kontrollera att strategin fortfarande fungerar när ordrarna växer i takt med kapitalet (marknadspåverkan på mindre bolag). Räkna fram en maxkapacitet i SEK per strategi.

### 6.4 Livscykel för en strategi
```
Kandidat → Backtestad → Validerad → PAPPER (≥ 60 handelsdagar och ≥ 50 affärer;
           för långsamma swing-/positionsstrategier i stället ≥ 3 månader)
        → LIVE-LITEN (låg vikt inom Jarvis budget) → LIVE-FULL → (Degraderad → Pausad → Arkiverad)
```
- Uppflyttning sker automatiskt **bara** om resultatet i papper eller live ligger inom ett statistiskt rimligt intervall jämfört med backtesten.
- **Automatisk nedgradering** om live-resultatet avviker signifikant (t.ex. utanför 95 %-intervallet från Monte Carlo), om drawdown överskrider strategins gräns, eller om fyllnadspriserna systematiskt är sämre än modellen.
- Kapital fördelas mellan godkända strategier med riskparitet eller volatilitetsviktning, med en maxvikt per strategi.
- Allt loggas så att Adam ser **varför** en strategi är på, av eller har bytt status.

### 6.4.1 ⭐ Många affärer samtidigt — Jarvis är en multitaskande trader

Jarvis ska **aldrig** arbeta med en affär i taget. Den ska kunna ha till exempel 3 daytrades igång i USA, 6 swingpositioner som hålls i en vecka, en kryptoposition över natten och en guldposition, **samtidigt**, och dessutom skanna efter nya möjligheter hela tiden.

**Arkitektur för samtidighet**
- Händelsedrivet och asynkront (asyncio plus kö via Redis). Varje **motor** (daytrading, swing, position, politikersignaler, krypto, råvaror) och varje **strategi** körs som en egen oberoende enhet med eget tillstånd. En långsam eller kraschad strategi får aldrig blockera de andra.
- Skanningen körs parallellt med handeln. Nya signaler köas och prioriteras (förväntad nettovinst, säkerhet och hur bråttom det är) medan befintliga positioner förvaltas.
- **Portföljhanteraren** (en central komponent, före risk-engine) ser alla förslag från alla strategier på en gång och bestämmer vad som får plats i budgeten just nu. Den tar hänsyn till total risk, korrelation och vilka motorer som har budget kvar (§7.1).
- **Ägarskap:** varje position ägs av exakt en strategi, som ansvarar för dess exit. Om två strategier vill handla samma instrument: samma riktning → slå ihop inom gränsen per instrument, med ägarskapet uppdelat i *delpositioner*. Motsatt riktning → portföljhanteraren nettar eller väljer den signal som är starkast, och loggar varför. Inga motstridiga order skickas till mäklaren samtidigt.
- **Gränser för samtidighet** (ändras i §7.1/Avancerat): max antal öppna positioner totalt (standard 25), max per motor, max samtidiga daytrades (standard 5), och max antal nya order per minut
- **Prestanda:** systemet ska klara minst 50 öppna positioner och hundratals bevakade instrument utan att fördröjningen per beslut ökar märkbart. Lasttesta detta.

**I appen:** Hem-vyn visar en levande lista "Pågår nu" med varje öppen affär som ett litet kort (motor, tid kvar/innehavstid, P&L och stopp). Fliken Innehav kan grupperas per motor.

### 6.5 Research-labbet kör av sig självt
Varje natt och varje helg: uppdatera data, kör om valideringen för aktiva strategier, testa nya parametervarianter inom en tidsbudget och skriv en kort rapport på svenska. Nya strategier går alltid in som **Kandidat** — aldrig direkt live.

---

