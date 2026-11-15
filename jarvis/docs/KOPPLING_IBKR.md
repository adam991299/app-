# Guide: koppla Jarvis till ditt IBKR-konto

Allt här är gratis. Räkna med ungefär en timme. Skriv aldrig lösenord i chatten med Claude –
de ska bara in i filen `.env` på servern (steg 5).

**Läget just nu:** steg 1–5 kan du göra i dag. Steg 6 (att Jarvis faktiskt loggar in och
handlar i papper) fungerar först när Jarvis IBKR-koppling är byggd och testad. Gatewayn i
steg 5 är inte provkörd på Oracles servertyp ännu.

## Steg 1 – Papperskontot hos IBKR
Papperskontot har ett **eget användarnamn och lösenord**, skilt från ditt vanliga.

1. Logga in i Client Portal på interactivebrokers.ie med ditt vanliga konto.
2. Tryck på gubben uppe till höger → **Settings** → **Paper Trading Account**.
3. Där står papperskontots **användarnamn** och **kontonummer** (börjar med DU). Skriv upp dem.
4. Tryck **Reset Paper Trading Password** och välj ett nytt lösenord. Det påverkar inte ditt
   vanliga lösenord.

Det är papperskontots inloggning Jarvis ska använda. Den kan aldrig röra riktiga pengar.

## Steg 2 – Kontrollera kontot
- Under **Settings → Account Settings**: kontrollera att kontot är ett **ISK** om det är
  tanken. Det avgör skatten och vad Jarvis får handla.
- Under **Settings → Market Data Subscriptions**: beställ ingenting. Gratisdatan för
  amerikanska aktier räcker till den första versionen.

## Steg 3 – Gratis server (Oracle Cloud)
1. Skapa ett konto på oracle.com/cloud/free. Välj hemregion **Sweden Central (Stockholm)** –
   den går inte att byta senare.
2. Oracle vill ha ett kort för att kontrollera vem du är. Det dras inte så länge du bara
   använder "Always Free". Uppgradera inte kontot.
3. Skapa en server: **Compute → Instances → Create instance**.
   - Image: **Ubuntu 24.04**
   - Shape: **Ampere → VM.Standard.A1.Flex**, 2 OCPU och 12 GB minne (gratisgränsen)
   - Ladda ner den privata SSH-nyckeln som Oracle erbjuder och spara den.
4. Får du felet "Out of capacity" finns ingen ledig gratismaskin just då. Försök igen senare.

## Steg 4 – Tailscale (så att bara du når appen)
1. Skapa ett konto på tailscale.com (gratis för privat bruk) och installera appen på din
   telefon och dator.
2. Logga in på servern från datorn (byt ut sökvägen och adressen mot dina):

```bash
ssh -i ~/Downloads/ssh-key.key ubuntu@SERVERNS_IP
```

3. Installera Tailscale på servern och logga in med länken som visas:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

```bash
sudo tailscale up
```

Öppna inga portar i Oracles brandvägg. Appen ska bara nås via Tailscale.

## Steg 5 – Jarvis på servern
1. Installera Docker:

```bash
curl -fsSL https://get.docker.com | sudo sh
```

```bash
sudo usermod -aG docker ubuntu
```

Logga ut och in igen efter det sista kommandot.

2. Hämta koden (repot är privat, så GitHub frågar efter inloggning):

```bash
git clone https://github.com/adam991299/app-.git
```

```bash
cd app-/jarvis && scripts/init-env.sh
```

3. Lägg in papperskontots inloggning i `.env`:

```bash
nano .env
```

Fyll i de två raderna, spara med Ctrl+O och avsluta med Ctrl+X:

```
IBKR_PAPER_USERNAME=ditt-pappersanvändarnamn
IBKR_PAPER_PASSWORD=ditt-papperslösenord
```

4. Starta allt:

```bash
docker compose --profile broker up -d --build --wait
```

```bash
scripts/smoke.sh
```

## Steg 6 – Första inloggningen
När gatewayn startar loggar den in på papperskontot. IBKR kan be dig godkänna i appen
**IBKR Mobile**. Ungefär en gång i veckan behöver du godkänna igen; Jarvis ska då skicka en
notis. Under tiden skyddas öppna positioner av stoppordrarna hos mäklaren.

## Senare – riktig handel
Riktig handel är ett eget beslut som du tar i appen. Inför det skapar du en **andra
användare** för boten på ditt riktiga konto, med rätt att handla men **utan rätt att ta ut
eller flytta pengar** (Client Portal → Settings → Users & Access Rights). Exakt hur det går
till för ett privat ISK-konto är inte verifierat; fråga IBKR:s support om menyn saknas.
