## 8. Exekvering

- Limit-order som standard (marketable limit med prisgräns), IBKR SmartRouting där det går, och adaptiva algoritmer för större order
- Idempotens: varje order har ett unikt klient-ID så att den aldrig skickas två gånger vid omstart
- Tillståndsmaskin för order: `new → submitted → partially_filled → filled | cancelled | rejected | expired`
- Hantering av delfyllnader, avvisade order och order som hänger
- **Avstämning** mot mäklarens positioner, order och kassa varje minut och vid varje omstart. Mäklaren är alltid sanningen. Vid avvikelse: stoppa och larma.
- Mät slippage (förväntat mot verkligt pris) per affär. Datan går tillbaka in i kostnadsmodellen.
- Återhämtning: efter krasch eller omstart läser systemet in läget från mäklaren och fortsätter säkert.
- Tydlig hantering av IB Gateway-utloggning: pausa handeln, skicka push "Godkänn inloggning i IBKR Mobile", och återuppta automatiskt när anslutningen är tillbaka.

---

