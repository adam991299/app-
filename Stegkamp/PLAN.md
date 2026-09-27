# Stegkamp – plan

Social stegtävlingsapp för iPhone: vänner tävlar om flest steg, med live-leaderboards,
inbjudningslänkar och valfria prispotter som deltagarna gör upp direkt med varandra i Swish.

> Arbetsnamn: **Stegkamp**. Namnet styrs från ett ställe (`Config/Base.xcconfig` →
> `APP_DISPLAY_NAME`), så ett byte senare är enkelt.

---

## 1. Namnförslag

| Namn | Varför | Att tänka på |
|---|---|---|
| **Kliv** | Kort, lätt att säga, funkar som verb ("kliv förbi Anna"). Bra app-ikon-ord. | Kolla varumärket; kort namn = svårare att få på App Store. Använd t.ex. "Kliv – stegtävling". |
| **Stegligan** | Låter som ett gäng – det sociala står i centrum. | Tydligt svenskt, svårare internationellt. |
| **Stegduell** | Säger exakt vad appen gör. Bra för App Store-sök. | Duell låter 1-mot-1, men tävlingar har många deltagare. |
| **Trampa** | Lekfullt, energiskt, enkelt. | Lite vardagligt. |
| **Steppa** | Svengelska, internationellt gångbart, uppmanande. | Kan förväxlas med dans (step). |

Min rekommendation: **Kliv** (med underrubriken "Stegtävling med vänner"). Kontrollera i App Store
Connect att namnet är ledigt innan vi bestämmer oss – ett app-namn kan bara reserveras av en app åt gången.

---

## 2. Viktiga regel- och risk-flaggor (läs detta)

1. **Prispotten och App Store Review 5.3 (Gaming, Gambling, Lotteries).** Apple kräver licens för
   "real money gaming". Att vänner satsar pengar på vem som går mest kan av en granskare tolkas som
   vadslagning, även om appen aldrig rör pengarna. Svensk spellag (2018:1138) undantar i regel privat
   spel i mindre omfattning mellan vänner, men **jag är inte jurist – stäm av med en jurist innan
   lansering**. Så här minskar vi risken:
   - Appen tar aldrig emot, håller eller betalar ut pengar och tar ingen provision (redan i specen).
   - 18-årsgräns och tydligt samtycke per tävling.
   - Potten är **avstängningsbar på distans** via en flagga i Firestore (`config/features`), så att vi
     kan skicka in appen, svara Apple och slå av/på funktionen utan ny version.
   - Reservplan om Apple säger nej: "Symbolisk insats" – potten blir en fritext-överenskommelse
     ("förloraren bjuder på fika") utan belopp och utan Swish-knapp.
   - Pengar nämns inte i skärmbilder eller marknadsföring.
2. **Swish-länkar.** Swish har ett officiellt, dokumenterat API för *företag* (Swish Handel, kräver
   avtal med bank). För *privatpersoner* finns bara det förifyllda formatet som används i Swish QR-koder,
   `swish://payment?data=<url-kodad JSON>`. Det fungerar i praktiken men är inte ett garanterat API.
   Vi verifierar formatet mot Swish aktuella dokumentation i fas 5 och har alltid reserven "kopiera
   nummer och belopp".
3. **Radera konto + Sign in with Apple.** Apple kräver att vi även *återkallar* Apple-token vid
   kontoradering (REST-anropet `auth/revoke`). Det kräver en Sign in with Apple-nyckel (.p8) som
   lagras som hemlighet i Cloud Functions – aldrig i appen.
4. **HealthKit.** Stegdata får aldrig gå till annonsnätverk (5.1.3) och får inte lagras i iCloud.
   Vi sparar bara dagliga/timvisa stegsummor i Firestore för att räkna tävlingar – detta beskrivs
   i integritetspolicyn och i App Privacy-formuläret.
5. **Annonser + ATT.** Samtycke först via Google UMP, sedan ATT. Nej = icke-personaliserade annonser.
6. **Molnmiljön kan inte bygga iOS.** Jag (Claude) kör i en Linux-miljö utan Xcode. Swift-koden
   byggs och testas därför på din Mac (`xcodebuild`, se nedan). Cloud Functions och webbsidan kan
   jag bygga och testa här. Efter varje fas får du ett kommando att köra som bygger och kör alla tester.

---

## 3. Arkitektur

```
┌──────────────────────── iPhone ────────────────────────┐
│  SwiftUI-vyer  ──►  @Observable ViewModels            │
│                        │                               │
│                        ▼                               │
│  Services (protokoll + riktig + mock-implementation)   │
│   HealthService  AuthService  Repository  PushService   │
│   PurchaseService  AdsService  ShareService             │
│                        │                               │
│  StegkampKit (ren Swift, delas med widgets & tester)    │
│   modeller · pottfördelning · minsta antal betalningar  │
│   leaderboard-sortering · datum/tidszon · formatering   │
└──────────┬─────────────────────────────┬────────────────┘
           │ Firestore / Auth / FCM      │ HealthKit
           ▼                             ▼
┌──────────────── Firebase ────────────────┐
│ Firestore  ◄── Cloud Functions (TS)      │
│  users, days, competitions, members,     │
│  settlements, inviteCodes, config        │
│ Hosting: /j/<kod>, AASA, policy, villkor │
└──────────────────────────────────────────┘
```

### Principer
- **MVVM med `@Observable`**, async/await och Swift 6 strikt concurrency.
- **Beroenden via protokoll** i en `AppEnvironment` som läggs i SwiftUI-miljön. Previews och UI-tester
  körs mot mock-tjänster (startargument `-ui-testing`), så de fungerar utan nätverk och utan HealthKit.
- **Appen startar utan Firebase-konfiguration**: saknas `GoogleService-Info.plist` körs appen i demoläge.
  Då kan du prova allt på din iPhone innan backend är uppsatt.
- **Servern är sanningen** för leaderboards, avslut och uppgörelser. Klienten laddar bara upp sina steg.
- **Pengar i öre** (heltal) överallt, aldrig flyttal.

### Kodstruktur
```
Stegkamp/
├── project.yml                 XcodeGen – genererar Stegkamp.xcodeproj
├── Config/                     xcconfig (bundle-id, team, domän, annons-ID:n)
├── Stegkamp/                   App-target
│   ├── App/                    @main, AppDelegate, AppEnvironment, RootView
│   ├── DesignSystem/           Färger, typsnitt, spacing, komponenter
│   ├── Features/               Today, Onboarding, Competitions, Settlement, Profile, Paywall
│   ├── Services/               HealthKit, Firebase, push, köp, annonser
│   └── Resources/              Assets, String Catalogs, PrivacyInfo, entitlements
├── StegkampWidgets/            WidgetKit-extension (fas 6)
├── StegkampTests/              Enhetstester (Swift Testing)
├── StegkampUITests/            UI-tester + skärmbildsautomatik
├── Packages/StegkampKit/       Ren domänlogik, testbar med `swift test`
└── firebase/                   firebase.json, rules, functions (TS), hosting (webb)
```

### Datamodell (Firestore)
| Sökväg | Innehåll | Läs | Skriv |
|---|---|---|---|
| `users/{uid}` | namn, avatar, stegmål, tidszon, statistik, notisinställningar | inloggade (publik profil) | ägaren (ej statistik) |
| `users/{uid}/private/profile` | Swish-nummer, FCM-tokens | ägaren | ägaren |
| `users/{uid}/days/{yyyy-MM-dd}` | 24 timvärden (UTC-dygn) + distans | ägaren | ägaren |
| `competitions/{id}` | namn, emoji, period, skaparens tidszon, max deltagare, pott, status, kod | medlemmar | Functions |
| `competitions/{id}/members/{uid}` | visningsnamn, avatar, steg, placering, avstånd, flagga | medlemmar | Functions |
| `competitions/{id}/payInfo/{uid}` | Swish-nummer kopierat vid anslutning | medlemmar | Functions |
| `competitions/{id}/settlements/{id}` | från, till, belopp (öre), status | medlemmar | betalare/mottagare (bara status) |
| `inviteCodes/{kod}` | tävlings-id | Functions | Functions |
| `config/features` | fjärrflaggor (t.ex. pott på/av) | alla | ingen (konsolen) |

**Tidszoner:** steg laddas upp som *timvisa* värden per UTC-dygn. Då kan servern räkna exakt
steg för varje tävlingsdygn i **skaparens** tidszon, oavsett var deltagarna befinner sig.
Appen visar tydligt "Dagarna räknas i svensk tid (Europe/Stockholm)".

### Cloud Functions (TypeScript, 2nd gen)
- `createCompetition`, `joinCompetition`, `rematch` (callable) – validering, unika 6-teckenskoder, max antal, 18+/pott-samtycke.
- `onDayWritten` – räknar om leaderboards för användarens aktiva tävlingar, rimlighetskontroll, "gick om dig"-notiser.
- `competitionTicker` (schemalagd var 5:e min) – start/slut, slutresultat, pottfördelning, uppgörelse.
- `nudges` (schemalagd) – "3 timmar kvar", påminnelse om obetalda skulder efter 24 h.
- `invitePreview` (HTTP) – data till inbjudningssidan och Open Graph-bild.
- `deleteAccount` (callable) – raderar all användardata och återkallar Apple-token.

---

## 4. Designsystem

**Känsla:** energisk men exklusiv. Mycket luft, systemets bakgrunder, en varm glödande accent.

| Token | Ljust | Mörkt | Användning |
|---|---|---|---|
| `Glöd` (accent) | `#C8341A` | `#FF6B47` | knappar, länkar, markeringar (kontrast ≥ 4.5:1) |
| `Glöd → Magenta` (gradient) | `#FF5A36 → #FF2D87` | samma | stegringen, hjältekort, ikon, delningskort |
| `Mynta` (framgång) | `#087A58` | `#34D6A4` | uppnått mål, "Mottaget", du får pengar |
| `Guld` | `#8A5F00` | `#FFC23D` | 1:a plats, vinster, badges |
| `Silver` / `Brons` | `#8A94A3` / `#A15C2E` | `#C9D1DC` / `#D98E5A` | pallen |
| `Midnatt` | `#0E1330` | `#0E1330` | delningskort, ikonbakgrund |

- **Typografi:** SF Pro via Dynamic Type-stilar. Alla siffror i **SF Pro Rounded** med
  `monospacedDigit()` så att de inte hoppar när de rullar upp.
- **Spacing:** 4-punktsskala (4, 8, 12, 16, 24, 32, 48). Hörnradie 22 för kort, 16 för knappar.
- **Komponenter:** `StepRing`, `RollingNumber`, `Card`, `PrimaryButtonStyle`, `SecondaryButtonStyle`,
  `AvatarView`, `EmptyStateView`, `.skeleton()`, `StatTile`, `Pill`, `Haptics`.
- **Rörelse:** spring-animationer, `matchedGeometryEffect`, `contentTransition(.numericText())`.
  Allt respekterar *Reduce Motion* (då används toning i stället för rörelse).

**App-ikon (koncept):** glöd→magenta-gradient med en vit, tjock ring som nästan är sluten (som en
stegring på väg mot målet) och två stiliserade fotavtryck som kliver ut ur öppningen. Enkel silhuett
som syns även i 60 px. En första version finns i `Stegkamp/Resources/Assets.xcassets/AppIcon.appiconset`.

---

## 5. Faser

| Fas | Innehåll | Status |
|---|---|---|
| 0 | Plan, namn, designsystem, XcodeGen, SPM, Firebase-koppling | 🟡 kod klar – väntar på första bygget på din Mac |
| 1 | HealthKit och Idag-skärmen | ⏳ |
| 2 | Onboarding, Sign in with Apple, profil i Firestore | ⏳ |
| 3 | Tävlingar och live-leaderboard | ⏳ |
| 4 | Inbjudningslänkar, webbsida, universal links | ⏳ |
| 5 | Prispott, uppgörelse och Swish | ⏳ |
| 6 | Push-notiser, widgets, delningskort | ⏳ |
| 7 | Annonser, samtycke, köpet "Ta bort annonser" | ⏳ |
| 8 | Finputs: design, animationer, tillgänglighet, tester | ⏳ |
| 9 | App Store-förberedelse och README | ⏳ |

Efter varje fas: bygg, kör tester, rätta fel och varningar, sammanfatta och lista manuella steg.

---

## 6. Så bygger du på din Mac (fas 0)

Engångsinstallation (Terminal):
```bash
# 1. Homebrew (om du inte har det) – se https://brew.sh
# 2. XcodeGen
brew install xcodegen
```

Varje gång (från mappen `Stegkamp/`):
```bash
./scripts/bootstrap.sh     # skapar Config/Local.xcconfig första gången + genererar Xcode-projektet
open Stegkamp.xcodeproj
```

Bygg och kör alla tester från Terminal:
```bash
./scripts/test.sh
```
