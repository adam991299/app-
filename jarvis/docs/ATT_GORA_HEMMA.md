# Att göra hemma (i den här ordningen)

Varje steg tar några minuter. Skriv till mig i chatten när du är vid ett steg, så guidar
jag dig. Lösenord och koder skriver du **aldrig** i chatten.

1. **IBKR Paper-lösenordet.** Client Portal → Inställningar → Paper Trading Account →
   "Reset Paper Trading Password". Fick du fel igen: kontakta IBKR:s support i chatten där.
2. **Byt till Tiered** (billigare små affärer). Client Portal → Inställningar →
   Kontoinställningar → Provision/Commission → IBKR Pro Tiered. Säg till mig, så ändrar jag
   `commission_plan` till `tiered`.
3. **Kontrollera att kontot är ett ISK** och om Tiered gick att välja där.
4. **Oracle-servern.** Kolla om stacken till slut lyckades (Resource Manager → Stacks →
   Jobs). Annars kör vi skriptet som försöker igen automatiskt.
5. **Tailscale.** Admin console → DNS: slå på **MagicDNS** och **HTTPS Certificates**.
   Installera Tailscale på servern när den finns.
6. **Jarvis på servern.** Följ steg 5 i `docs/KOPPLING_IBKR.md` (klona, `scripts/init-env.sh`,
   fyll i `.env` med `nano`, `docker compose --profile broker up -d`).
7. **Passkey.** Steg 7 i `docs/KOPPLING_IBKR.md`: engångskoden från `.env`, skapa passkey
   under Inställningar i appen, ta sedan bort kodraden.
8. **Validering på servern.** Jag ger dig två kommandon (trendföljning och daytrading). Den
   för daytrading tar ungefär två timmar. Först när en strategi är godkänd börjar Jarvis
   handla med den, på papper.
