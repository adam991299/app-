## 10. Säkerhet

- Inloggning med **passkeys (WebAuthn)**, ingen gemensam lösenordsinloggning. Bara Adams konto.
- Appen ligger bakom Cloudflare Access eller Tailscale. Inga öppna portar utöver 443.
- IB Gateway-porten exponeras **aldrig** mot internet.
- Secrets hanteras med Docker secrets eller `.env` med rättigheterna 600. Krypterade backuper.
- Separat IBKR-användare utan uttagsrätt (se §1)
- Audit-logg över alla inställningsändringar, inloggningar och manuella åtgärder
- Beroenden låsta (lockfiles), automatisk sårbarhetsskanning, och regelbundna uppdateringar av OS och containrar
- Rate limiting och CSRF-skydd på API:t

---

