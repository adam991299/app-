## 3. Marknader och instrument

Jarvis ska kunna skanna och handla:

| Tillgångsslag | Instrument | Kommentar |
|---|---|---|
| Svenska/nordiska aktier | Nasdaq Stockholm, Helsingfors, Köpenhamn, Oslo Børs | Large/Mid Cap som standard; Small Cap bara om likviditetsfiltret godkänner |
| USA-aktier | NYSE, Nasdaq | Kontrollera regler för US pre/after-market |
| ETF:er globalt | Brett urval inkl. sektor-, ränte- och landets-ETF:er | **Verifiera vilka ETF:er en EU-privatperson får köpa (PRIIPs/KID).** Många US-ETF:er är spärrade. |
| Råvaror: guld, olja m.m. | ETC/ETP:er, och terminer (futures) i ISK om IBKR tillåter det för kontot | Terminer är **avstängda som standard** och får bara slås på av Adam. Hantera rullning, kontraktsstorlek och marginal korrekt. |
| Krypto | Om IBKR erbjuder krypto för kontot används det, annars krypto-ETP:er på nordiska/europeiska börser | **Verifiera vad som är tillåtet i ISK.** Krypto har egen, lägre exponeringsgräns. |

**Universumfilter (körs varje natt):**
- Minsta genomsnittliga dagsomsättning (ADV) — standard 5 MSEK för Norden, 20 MUSD för USA
- Minsta kurs (inga pennyaktier), max spread i procent
- Uteslut instrument som är handelsstoppade, på observationslista, eller som har pågående bud/avnotering
- Valutahantering: allt räknas om till SEK, och FX-kostnaden ingår i kostnadsmodellen

**Kontotypsregler:** Läs vilka begränsningar ISK har hos IBKR (blankning, belåning, derivat) och gör det till hårda regler i risk-engine. Som standard är Jarvis **long-only och obelånad** tills Adam ändrar det.

---

