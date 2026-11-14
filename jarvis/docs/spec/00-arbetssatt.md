## 00. LÄS DETTA FÖRST — hur du ska arbeta

Den här specifikationen är stor med flit. Du ska inte klämma ihop allt i ett enda okontrollerat steg. Du ska bygga allt — **varje del helt klar innan den räknas som färdig, och så mycket som möjligt parallellt (§00.4).**

### 00.1 Ditt första steg (innan du skriver någon kod)
1. Läs hela specifikationen från början till slut.
2. Dela upp den åt dig själv, så att du kan arbeta fokuserat:
   - `CLAUDE.md` — kort (max ca 150 rader): visionen, reglerna i §0, kvalitetskraven i §00.3, designkänslan i §9.1, och en innehållsförteckning som pekar på specfilerna nedan
   - `docs/spec/` — en fil per område, kopierade **ordagrant** från denna prompt (t.ex. `01-ekonomi.md`, `05-nyheter.md`, `05.4-politiker.md`, `05.5-learning-loop.md`, `07-risk.md`, `09-app.md` …). Ingenting får gå förlorat eller förkortas.
   - `docs/PLAN.md` — alla faser i §13 som en checklista, med status
   - `docs/PROGRESS.md` — en logg med datum över vad som gjorts och vad som är nästa steg
   - `docs/ASSUMPTIONS.md` och `docs/DECISIONS.md` — antaganden du inte kunnat verifiera, och viktiga beslut med motivering
3. Samla **alla** frågor du behöver ställa till Adam för hela projektet i **ett** meddelande (konton, nycklar, val och budget), och visa den övergripande planen. Efter hans svar arbetar du självständigt (§00.4).

`JARVIS_SPEC.md` behålls oförändrad som originalet. Vid tveksamhet gäller originalet.

### 00.2 Arbetscykeln för varje fas (följs utan undantag)
1. **Läs** fasens specfiler i `docs/spec/` igen, även om du tror att du minns dem.
2. **Planera:** skriv en kort plan i `docs/PLAN.md` med delsteg och hur acceptanskraven ska testas.
3. **Bygg** i små steg och kör testerna efter varje steg.
4. **Verifiera** fasens acceptanskrav (✅ i §13) ett och ett, med riktiga körningar. För gränssnitt: ta skärmdumpar i mobil- och datorstorlek och granska dem själv (Playwright).
5. **Granska:** låt en separat granskningsagent, som inte skrivit koden, granska ändringarna (fokus på pengar-kritiska fel i `risk/`, `execution/` och `broker/`, säkerhet och gränsfall). Åtgärda allt den hittar.
6. **Städa:** inga TODO:er, ingen bortkommenterad kod, inga tillfälliga lösningar, ingen död kod.
7. **Dokumentera:** uppdatera `PROGRESS.md`, `PLAN.md` och berörda docs. Gör en commit med ett tydligt meddelande.
8. **Rapportera** till Adam på enkel svenska: vad som byggts, hur det testats, vad som återstår, och vad du behöver av honom.

En fas räknas som klar först när **alla** punkter är klara. Faser som inte beror på varandra får byggas samtidigt (§00.4), men en fas som beror på en annan börjar först när den är klar. Om en ny session startar: läs `CLAUDE.md`, `PLAN.md` och `PROGRESS.md` först och fortsätt exakt där det slutade.

### 00.3 Kvalitetskrav — inget halvdant, inget lämnas åt slumpen
- **Varje funktion som byggs ska vara färdig på riktigt:** fungerande, testad, felhanterad och dokumenterad. Hellre färre saker helt klara än många halvklara.
- **Inga platshållare** i det som levereras: inga påhittade data, inga "kommer snart"-knappar, inga tomma vyer utan genomtänkt tomt läge. (Under bygget får det finnas stubbar, men de ska vara märkta och borta innan fasen räknas som klar.)
- **Noll kända buggar** när en fas avslutas. Hittas en bugg rättas den, och ett test som hade fångat den läggs till.
- **Testkrav:** 100 % täckning i `risk/`, `execution/`, `broker/` och `economics/`, minst 85 % i övrig backend, och end-to-end-tester (Playwright) för alla viktiga flöden i appen. Strikt typkontroll (mypy strict, TypeScript strict), linting utan varningar. CI måste vara grön.
- **Felhantering överallt:** varje anrop utåt (mäklare, data, AI, nyheter) har timeout, återförsök med backoff och ett säkert beteende när det fallerar. Systemet ska aldrig krascha tyst.
- **Hellre fråga än gissa:** om specifikationen är oklar eller säger emot sig själv — stanna, beskriv problemet för Adam, föreslå en lösning och skriv beslutet i `DECISIONS.md`.
- **Gör det inte enklare i smyg:** om något i specifikationen inte går att bygga som det står (t.ex. för att ett API inte tillåter det), säg det öppet och föreslå det bästa alternativet. Gör aldrig en sämre version utan att säga till.

### 00.4 Bygg så snabbt som möjligt — utan att tumma på kvaliteten
Adam vill att bygget går **snabbt**. Snabbhet kommer från parallellt och självständigt arbete, aldrig från att hoppa över tester eller granskning.

- **Arbeta självständigt.** Stanna och vänta på Adam **bara** när du behöver något som bara han kan ge (inloggningar, API-nycklar, betalningar, 2FA) eller ett beslut som inte kan ångras. Annars: fatta det rimligaste beslutet, skriv det i `DECISIONS.md` och fortsätt. Rapportera framsteg löpande utan att vänta på svar.
- **Bygg parallellt.** Gör en beroendekarta över faserna i `PLAN.md`. Delar som inte beror på varandra (t.ex. nyhetsmotorn, politikersignalerna, appens design och vyer, research-labbet, ekonomimodulen) byggs **samtidigt** av underagenter i egna git worktrees, och slås sedan ihop. Låt varje agent följa arbetscykeln i §00.2 för sin del. Delade gränssnitt (API-kontrakt, databasschema, design tokens) definieras **först**, så att de parallella delarna passar ihop.
- **Vänta aldrig på klockan.** Pappershandeln (Fas 0.5 och Fas 8) mäts i handelsdagar och kan inte snabbas upp. Fortsätt därför bygga alla övriga faser **medan** den tunna versionen pappershandlar. Nya delar driftsätts till staging (§11) när de är klara och kopplas in i pappershandeln efter hand.
- **Återanvänd beprövade bibliotek** i stället för att skriva eget där det finns bra, underhållna alternativ (IBKR-klient, kalendrar, backtest-hjälp, UI-komponenter, grafer). Kontrollera att de underhålls och har en tillåtande licens.
- **Kritiska delar får aldrig skyndas:** `risk/`, `execution/`, `broker/` och `economics/` byggs och granskas alltid med full noggrannhet, även om annat byggs snabbare runt omkring.
- **Mål för byggtid:** hela systemet byggt och i full pappershandel så snabbt som kvalitetskraven i §00.3 tillåter. Visa i `PROGRESS.md` en uppskattning av vad som är kvar.

### 00.5 Börja med en tunn version som fungerar hela vägen (Fas 0.5)
Innan bredden byggs ska en **minimal men komplett** version fungera från början till slut: en marknad (amerikanska aktier), en enkel och väldokumenterad strategi (t.ex. trendföljning), IBKR Paper, risk-engine med nödstopp, avstämning, och en enkel men redan snygg hemskärm med status, innehav och affärer. Den körs automatiskt i minst 10 handelsdagar utan fel. **Under tiden** byggs resten parallellt (§00.4) på samma grund, och kopplas in i pappershandeln efter hand. Det gör att problem med anslutning, data och order hittas tidigt, när de är billiga att rätta.

---

