## 15. Definition of Done

Jarvis the Trader är klar när:
1. Hela systemet körs på VPS:en i papper, automatiskt och dygnet runt, i minst 60 handelsdagar utan manuella ingrepp utöver IBKR:s 2FA, även när Adams dator är avstängd.
2. Varje affär går att spåra från signal och nyheter, genom riskbeslutet, till order och fyllnad, med en svensk förklaring i appen.
3. Alla circuit breakers och kill switch har testats och fungerar.
4. Appen är snabb, vacker, mörk och tydlig enligt §9.1, enkel att förstå på några sekunder, och känns som Adams egen agent.
5. README förklarar på enkel svenska hur Adam startar, pausar, uppdaterar och felsöker systemet, och vad varje inställning betyder.
6. Inga siffror i systemet är påhittade, och alla begränsningar står i `docs/ASSUMPTIONS.md`.
7. Staging och production fungerar, med återställning med ett kommando. Adams incheckning (§11.2) och nödplanen (§11.1) är testade.
8. Adam kan fråga Jarvis om vilken affär som helst, i text eller med rösten, och få en korrekt förklaring baserad på journalen. Han kan också be den skanna och analysera marknader direkt från chatten.
9. Jarvis hanterar många affärer i olika motorer samtidigt, och kan i läget "Fråga mig först" skicka möjlighetsnotiser som Adam godkänner eller avböjer.
10. Learning Loop körs automatiskt varje dag och vecka. Minst en challenger har skuggkörts mot championen hela vägen, och appen visar ärligt vad Jarvis lärt sig och om det har gett en säkerställd förbättring.
11. Varje fas i §13 är avbockad i `docs/PLAN.md` med verifierade acceptanskrav. Noll kända buggar, inga TODO:er och inga platshållare (§00.3).

---

