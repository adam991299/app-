## 14. Teststrategi

- Enhetstester för alla risk-, storleks- och kostnadsberäkningar (100 % täckning i `risk/` och `execution/`)
- Egenskapsbaserade tester (Hypothesis) för positionsstorlek och gränser
- Integrationstester mot `SimBroker` och IBKR Paper
- Replay-läge: spela upp en historisk handelsdag i realtidsfart genom hela systemet
- Kaostester (se Fas 5)
- Frontend: Playwright för huvudflöden (inloggning, paus, kill switch, byte till live)

---

