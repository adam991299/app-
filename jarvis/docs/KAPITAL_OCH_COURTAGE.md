# Hur mycket kapital behöver Jarvis för att courtaget inte ska äta upp vinsten?

Räknat 2026-11-16 med Jarvis egna regler. En affär tas bara om den förväntade vinsten är
minst **2 gånger** kostnaderna (risk-motorn, `min_edge_to_cost_ratio`).

## Antaganden (inte verifierade mot ditt konto)
- IBKR Pro **Fast**: 0,005 USD per aktie, minst 1 USD per order.
- IBKR Pro **Tiered**: 0,0035 USD per aktie, minst ca 0,35 USD per order plus börs- och
  clearingavgifter (räknat som 0,40 USD). Minimiavgiften står på IBKR:s australiska sida
  men kunde inte bekräftas på den amerikanska. Om Tiered går att välja på ett ISK är inte
  verifierat (A6, A21).
- Spread 2 punkter och växling 2 punkter per affär (Jarvis kostnadsmodell).
- 1 USD ≈ 10,5 kr.
- Daytrading: stoppen ca 1 % från köpet. Trendföljning: ca 6 % (3 × ATR).
- "Förväntad vinst per affär" i enheter av risken (R) är okänd tills valideringen har körts.
  Tabellen visar tre nivåer.

## Minsta kapital (Jarvis budget) per strategi

Balanserad = högst 10 % per aktie, Offensiv = högst 20 %.

| Strategi | Förväntad vinst per affär | Fast, Balanserad | Fast, Offensiv | Tiered, Balanserad | Tiered, Offensiv |
|---|---|---|---|---|---|
| Daytrading | 0,2 R | 1 050 000 kr | 525 000 kr | 420 000 kr | 210 000 kr |
| Daytrading | 0,3 R | 300 000 kr | 150 000 kr | 120 000 kr | 60 000 kr |
| Daytrading | 0,5 R | 124 000 kr | 62 000 kr | 49 000 kr | 25 000 kr |
| Trendföljning | 0,2 R | 40 000 kr | 20 000 kr | 16 000 kr | 8 000 kr |
| Trendföljning | 0,3 R | 26 000 kr | 13 000 kr | 10 000 kr | 5 000 kr |
| Trendföljning | 0,5 R | 15 000 kr | 7 000 kr | 6 000 kr | 3 000 kr |

Under 0,16 R lönar sig daytrading **aldrig**, oavsett kapital: spread och växling äter då
upp hela vinsten.

## Dessutom: en hel aktie
Jarvis köper hela aktier. Många av de 50 aktierna kostar 150–900 USD. Med 10 % per aktie
behövs ungefär 15 000–95 000 kr för att kunna köpa en enda aktie i dem. Med 10 000 kr når
Jarvis bara de billigaste aktierna.

## Slutsats
- Med 10 000–80 000 kr är **trendföljning** realistisk, särskilt med Tiered.
- **Daytrading** kräver en stark strategi (minst ca 0,3–0,5 R per affär) och helst Tiered
  för att löna sig med under 100 000 kr. Valideringen visar om strategin har det; risk-motorn
  stoppar annars affärerna av sig själv.
- Byte till Tiered görs i Client Portal (Inställningar → Kontoinställningar → Provision /
  "Commission"). Jarvis kostnadsmodell behöver då ändras till samma avgifter.
