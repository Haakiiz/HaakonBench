# HåkonBench

Send den samme prompten til alle store LLM-leverandører parallelt, og la en dommermodell gradere svarene blindt.

Oppgaven er den samme hver gang: **skriv den beste fiskeguiden en level 60 Human Warrior i WoW Classic noensinne kommer til å lese.** Karakteren har ubegrenset tid, men kan ikke dø og kan ikke sitte og passe på skjermen. Alt må være AFK-trygt. Svarene fakstsjekkes mot `wow_reference.yaml`, en kuratert fil med verifiserte Classic-fakta — så modeller som finner på tall og oppskrifter blir tatt.

---

## 📊 Siste resultater — 14. august 2026

**Oppsett:** 14 modeller · `--effort medium` · nettsøk **på** · dommer `google/gemini-3.5-flash` · bucket `pc96c9b__medium__search-on`

Karaktersetting skjer blindt: dommeren ser svarene som «Response A, B, C…» og vet ikke hvem som skrev hva. Maks 50 poeng, fordelt på Accuracy, Strategy, Creativity, Structure og Fidelity.

| # | Modell | Total | Tid | Tokens | Søk |
|---|---|---|---|---|---|
| 🥇 | `openai/gpt-5.6-sol` | **49** | 288s | 124k | 13 |
| 🥈 | `google/gemini-3.5-flash` | **45** | 91s | 14k | 12 |
| 🥉 | `openai/gpt-5.5` | **44** | 213s | 68k | 8 |
| 4 | `anthropic/claude-opus-4-8` | 41 | 300s | 70k | 9 |
| 4 | `anthropic/claude-opus-5` | 41 | 344s | 42k | 2 |
| 4 | `openai/gpt-5.4-mini` | 41 | 501s | 146k | 24 |
| 7 | `openai/gpt-5.6-terra` | 39 | 102s | 49k | 4 |
| 8 | `openai/gpt-5.6-luna` | 38 | **39s** | 19k | 1 |
| 9 | `google/gemini-3.6-flash` | 37 | 55s | **9k** | 0 |
| 10 | `anthropic/claude-sonnet-5` | 34 | 391s | 263k | 38 |
| 10 | `xai/grok-4.6` 🆕 | 34 | 419s | 109k | 12 |
| 12 | `xai/grok-4.5` | 33 | 270s | 104k | 14 |
| 12 | `google/gemini-3.7-flash` 🆕 | 33 | **39s** | **8k** | 0 |
| 14 | `google/gemini-3.1-pro-preview` | 27 | 51s | 5k | 0 |

### 🥇 Vinneren: GPT-5.6 Sol

Sol vant på et grep ingen andre fant. Alle modellene slet med den samme motsetningen — hvordan kan noe være AFK-trygt på en PvP-server? Sol løste det ved å lese spillets *sonereglar* i stedet for kartet:

> *"In Alliance-controlled territory, you are not automatically PvP-flagged. Do not attack Horde, heal flagged players or arrive with a lingering flag... Best strict-safety money spot on a PvP realm."*

Ved å sende spilleren til Westfall-kysten etter Oily Blackmouth får du både høy verdi og garantert trygghet. Dommeren kalte det «a stroke of genius» og ga full pott på både Accuracy, Strategy og Creativity — det eneste svaret i feltet med 10/10 på tre akser.

### 🥈 Overraskelsen: Gemini 3.5 Flash

Andreplass, på **en tredel av tiden og en niendedel av tokenbudsjettet** til vinneren. Den vant på praktiske detaljer ingen andre tenkte på — som at «AFK-fisking» i praksis er en *lyd*-aktivitet:

> *"Slide Music and Ambience to 0. Slide Sound Effects (SFX) to 100. When you hear the distinct 'SPLASH' sound cue in your headphones, right-click."*

Det er den typen råd som avslører at modellen har forstått hva oppgaven faktisk handler om, ikke bare hva den spør om. (Se forbeholdet nederst — 3.5 Flash var også dommer i dette kjøret.)

### 💀 Bunnen: Gemini 3.1 Pro

27 poeng, og dommerens dom var kort: *«A disaster.»* Den ba spilleren selge Firefin Snapper til vendor som søppel (de er alkymi-reagenser og verdt penger), og fant opp en oppskrift der Loch Frenzy blir til Thistle Tea — en drikk som i virkeligheten lages av Swiftthistle og ikke har noe med fisk å gjøre.

---

## 🆕 Månedens nye modeller: Grok 4.6 og Gemini 3.7 Flash

To ferske modeller slapp denne uka — `grok-4.6` (12. august) og `gemini-3.7-flash` (13. august). Begge ble sluppet rett inn i den eksisterende bucketen, så de svarte på **nøyaktig samme prompt med nøyaktig samme tokenbudsjett** som de 12 andre, og hele feltet ble gradert på nytt samlet. Det er den nærmeste sammenligningen vi kan lage.

Konklusjonen er ubarmhjertig: **ingen av dem er en oppgradering.** Den ene står stille, den andre går bakover.

### Grok 4.6 vs Grok 4.5 — én poeng, på 55 % mer tid

| | Accuracy | Strategy | Creativity | Structure | Fidelity | **Total** | Tid |
|---|---|---|---|---|---|---|---|
| `grok-4.5` | 6 | 7 | 6 | 6 | 8 | **33** | 270s |
| `grok-4.6` 🆕 | **7** | 7 | 6 | 6 | 8 | **34** | **419s** |
| | +1 | – | – | – | – | **+1** | +55 % |

Se på den tabellen en gang til. Fire av fem akser er **identiske**. Hele generasjonsspranget fra 4.5 til 4.6 er ett enkelt poeng på Accuracy — og for det betalte vi 149 ekstra sekunder. 419 sekunder er det tregeste kjøret i hele bucketen, tregere enn Opus 5 (344s) og Sonnet 5 (391s), til tross for at Grok skrev et av de *korteste* svarene i feltet.

Innholdet er ikke dumt. Det contrariane valget er faktisk det beste argumentet Grok leverer, og det er ekte:

> *"Verdantis has stretches where you can sit behind a tree or on a tiny unnamed pond with zero pathing mobs and zero other players... Defend it by actually sitting there for four hours instead of theory-crafting percentages."*

Men dommeren avfeide det som gjenbruk — *«just a copy-paste of Moonglade/Feralas logic seen in other guides»* — og tok den på to faktafeil, begge verifisert mot referansefila:

- **Winter Squid-sesongen:** Grok sa 21. des–18. mars. Fasit: **23. sept–20. mars.** (Grok 4.5 bommet på det samme, bare litt annerledes — arvet feil.)
- **Kjøpmannen Gikkix:** Grok plasserte ham i Gadgetzan. Fasit: **Steamwheedle Port, Tanaris.**

Begge Grok-modellene deler også bunnplasseringen på Structure (6 poeng) sammen med Sonnet 5. Det er ikke tilfeldig at dommeren beskrev begge som repetitive.

### Gemini 3.7 Flash vs 3.6 vs 3.5 — tre generasjoner nedover

Dette er den virkelig oppsiktsvekkende grafen i hele kjøringen. Google har sluppet tre Flash-modeller på under to måneder, og på denne oppgaven blir de **jevnt dårligere for hver eneste versjon**:

| | Accuracy | Strategy | Creativity | Structure | Fidelity | **Total** |
|---|---|---|---|---|---|---|
| `gemini-3.5-flash` (juli) | 9 | 9 | 9 | 9 | 10 | **45** 🥈 |
| `gemini-3.6-flash` (21. juli) | 6 | 7 | 8 | 8 | 8 | **37** |
| `gemini-3.7-flash` 🆕 (13. aug) | 6 | 6 | **5** | 8 | 8 | **33** |
| | −3 | −3 | **−4** | −1 | −2 | **−12** |

Tolv poeng tapt på tre versjoner. Verst er **Creativity: fra 9 til 5** — nest dårligst i hele feltet, bare slått nedover av Gemini 3.1 Pro. Accuracy falt med 3 allerede ved 3.6 og har ikke kommet tilbake.

3.7 Flash fant på en fisk som ikke finnes — **«Glossy Bay Shark»** i Feralas — og rotet med hvilke fisker som blir til hvilke retter (Whitescale Salmon blir Baked Salmon; Redgill blir Filet of Redgill — den blandet dem). Og det den selv utropte til sitt dristige, contrariane valg fikk denne dommen:

> *"This is completely generic, as almost every basic WoW fishing guide points players to Feathermoon as the default Alliance hub."*

Verdt å merke seg: Google markedsfører 3.7 Flash som et **koding- og agent**-løft, ikke et kreativitetsløft. Denne benchmarken måler det stikk motsatte — fritekst, faktakunnskap og originalitet. Så resultatet er ikke nødvendigvis at 3.7 er en dårlig modell; det er at den er optimalisert bort fra akkurat det HåkonBench belønner. Det er en påminnelse om at «nyere» og «bedre» ikke er samme sak, og at det avhenger helt av hva du måler.

### Hvor de står i feltet

Begge de nye havnet i nedre halvdel: **grok-4.6 på delt 10. plass**, **gemini-3.7-flash på delt 12.** av 14.

Det gjør spesielt vondt for 3.7 Flash når man ser på fart-for-pengene. Den er raskest i feltet sammen med `gpt-5.6-luna` — begge på 39 sekunder — men:

| Modell | Total | Tid | Tokens |
|---|---|---|---|
| `gpt-5.6-luna` | **38** | 39s | 19k |
| `gemini-3.6-flash` | **37** | 55s | 9k |
| `gemini-3.7-flash` 🆕 | **33** | 39s | **8k** |

`gpt-5.6-luna` gir deg fem poeng mer på nøyaktig samme tid. Og Googles egen forrige modell, 3.6 Flash, gir deg fire poeng mer for omtrent samme tokenpris. **3.7 Flash er billigst i feltet — og det er hele salgsargumentet dens her.**

En siste ting begge Flash-modellene har til felles: de kjørte **null nettsøk**, selv om søkeverktøyet var påslått. De svarte helt fra egen kunnskap på 39 og 55 sekunder, mens Grok 4.6 fyrte av 12 søk og brukte sju minutter. Antall søk bestemmer modellen selv — vi henger bare på verktøyet. At Gemini konsekvent velger å ikke slå opp, mens Grok graver seg ned i et kvarters research og likevel bommer på vendor-byen, sier noe interessant om to helt ulike temperament.

## 🤔 Hva dette *ikke* beviser

HåkonBench er et morsomt eksperiment, ikke vitenskap. De ærlige forbeholdene:

- **Dommeren rangerte seg selv som nummer to.** `gemini-3.5-flash` var både deltaker og dommer. Den ble gradert blindt, men det er verdt å ta med en klype salt. Uavhengig kontroll finnes: `claude-opus-5` graderte de samme 12 svarene i juli og ga det samme svaret **36 poeng og 6. plass**, ikke 45 og 2. plass.
- **Dommeren avgjør nesten like mye som deltakerne.** Bytt dommermodell, og hele tabellen stokker om. Gamle dommer-verdikt ligger arkivert under `_grades/`, så du kan sammenligne selv.
- **Karakterene er komparative, ikke absolutte.** Dommeren ser alle svarene samtidig og rangerer dem mot hverandre. Legger du til én modell, kan alle andres poeng flytte seg. Tallene her kan altså ikke sammenlignes direkte med tidligere kjøringer.
- **Modellene svarte under ulike forhold.** Nettsøk var påslått for alle, men hvor mange søk hver modell faktisk kjørte bestemmer den selv — fra 0 (begge Flash-modellene, som svarte helt fra egen kunnskap) til 38 (Sonnet 5). Det er ikke likt spillefelt.
- **Én kjøring per modell.** Ingen varians måles. Kjør med `--tag variance-2` om du vil se hvor mye støy det er.
- **Referansefila er kuratert, ikke komplett.** Når dommeren sier «denne fisken finnes ikke», betyr det strengt tatt «den står ikke i `wow_reference.yaml`». Runneren har en automatisk selvmotsigelses-sjekk som flagger slikt nederst i `_grades.md` — den slo faktisk ut på ett punkt i dette kjøret.

Hele verdiktet med alle faktasjekk-kommentarene ligger i [`results/pc96c9b__medium__search-on/_grades.md`](results/pc96c9b__medium__search-on/_grades.md).

---

## Oppsett

```bash
pip install -r requirements.txt
```

Lag en `.env`-fil i prosjektmappa:

```
ANTHROPIC_API_KEY=...
CHATGPT_API_KEY=...
GOOGLE_API_KEY=...
XAI_API_KEY=...
```

Du trenger bare nøklene til de leverandørene du faktisk bruker. Kommenter ut resten i `CONTESTANTS`-lista i `haakonbench.py`.

---

## Kjøre benchmarken

### Fullt kjør – ny datert mappe
```bash
python haakonbench.py
```
Lager `results/2026-05-24_143022/` med én `.md` per modell og en `_grades.md` med karakterene.
Overskriver aldri gamle kjøringer.

---

### Retry én eller flere modeller som feilet
```bash
python haakonbench.py --only openai/gpt-5.5
python haakonbench.py --only openai/gpt-5.5,xai/grok-4.3
```
Kjører bare de oppgitte modellene, lagrer i **siste** kjøringsmappe, og graderer hele poolen på nytt.
Bruk `provider/modellnavn`-format – samme som i `CONTESTANTS`-lista.

---

### Test én ny modell mot et gammelt kjør
Legg til modellen i `CONTESTANTS` i `haakonbench.py`, så kjør:
```bash
python haakonbench.py --only anthropic/claude-haiku-4-5
```
Slotter inn i siste mappe og regraderer alt samlet.

---

### Spesifiser hvilken kjøringsmappe du vil bruke
```bash
python haakonbench.py --only openai/gpt-5.5 --run 2026-05-24_110000
python haakonbench.py --regrade --run 2026-05-24_110000
```
`--run` tar mappenavnet (ikke full path). Uten `--run` brukes alltid siste mappe.

---

### Regrade uten å kjøre noe
```bash
python haakonbench.py --regrade
```
Hopper over alle API-kall. Graderer alt som allerede ligger på disk i siste mappe.
Nyttig hvis du vil justere grader-prompten og sammenligne på nytt.

---

### Kjør modeller uten å gradere
```bash
python haakonbench.py --no-grade
python haakonbench.py --only xai/grok-4.3 --no-grade
```
Lagrer svarene, men kaller ikke graderen. Billig måte å sjekke at modellene svarer.

---

### Slå på nettsøk med `--web-search`
```bash
python haakonbench.py --web-search
python haakonbench.py --web-search --effort low
python haakonbench.py --web-search --only anthropic/claude-opus-4-8
```
Henger på hver leverandørs innebygde nettsøk-verktøy. Default er **av** – da svarer
modellene fra eget kunnskap, noe som gir et renere bilde av hva de kan uten å slå opp.

Hva som skjer per leverandør:

| Leverandør | Implementasjon |
|---|---|
| Anthropic | `tools: [{type: web_search_20260209}]` – GA, ingen beta-header |
| OpenAI | Responses API `tools: [{type: web_search}]` |
| Gemini | `GenerateContentConfig(tools=[Tool(google_search=...)])` – faktureres per søk |
| xAI grok-4.3 | Responses API `tools: [{type: web_search}]` (Chat Completions-endepunktet støtter det ikke) |
| Haiku 4.5 | ⚠ Støtter ikke programmatisk tool calling – feiler alltid med `--web-search` |

Antall søk modellen faktisk kjørte vises i **Web searches**-kolonnen i efficiency-tabellen
i `_grades.md`. xAI eksponerer ikke søketal via usage-objektet og vises som `—`.

Merk: `--web-search` lagres i `HB_META`-blokken i hver modell-fil, så `--regrade` vet
om søk var på i det opprinnelige kjøret.

---

### Se alle kjøringer
```bash
python haakonbench.py --list
```
Viser alle mapper under `results/` med antall filer og om de er gradert.

---

### Skru opp reasoning/tenking med `--effort`
```bash
python haakonbench.py --effort high
python haakonbench.py --effort max --only anthropic/claude-opus-4-8
```
Én bryter (`low | medium | high | max`, default `medium`) som setter et felles
output-token-budsjett **og** oversettes til hver leverandørs navngitte reasoning-nivå.
Leverandørene er uenige om navn og tak, så oversettelsen ligger i `PROVIDER_EFFORT`
i `haakonbench.py`:

| Tier | max_tokens | Anthropic Opus | OpenAI | Gemini 3 | xAI Grok |
|------|-----------|----------------|--------|----------|----------|
| low | 8000 | low | low | low | low |
| medium | 16000 | medium | medium | medium | medium |
| high | 32000 | high | high | high | high |
| max | 64000 | **max** | **max** (Sol) / xhigh | high | **xhigh** (4.6) / high |

Per-modell-tak for Anthropic: `max` er kun Opus (Sonnet 4.6 kappes til `high`), og
Haiku 4.5 får ingen knapp (støtter verken effort eller adaptive thinking). Kjøringen
skriver ut hvilket nivå hver modell faktisk får (`provider model → nivå`).

**Hva ligger inni `max_tokens`?** Avhenger av leverandør:

| Leverandør | Hva `max_tokens` dekker |
|---|---|
| OpenAI (gpt-5.x) | reasoning **+** synlig svar (delt budsjett) |
| Google Gemini | tenking **+** synlig svar (delt budsjett) |
| Anthropic Claude | tenking **+** synlig svar — tenke-tokens teller mot `max_tokens`; dybden styres av `effort` |
| xAI Grok | **kun** synlig svar — reasoning skjer server-side og teller ikke mot budsjettet |

For OpenAI/Gemini gulvsettes budsjettet uansett til minst 20 000 (i `llm_client.py`)
så modellen har rom til å tenke *og* svare.

På høye nivåer (`high`/`max`) kan enkeltmodeller bruke flere minutter. Hvert svar
lagres **i det øyeblikket modellen er ferdig** (`[3/8] ✓ ...`), og en heartbeat hvert
20. sekund viser hvilke som fortsatt kjører — så du ser at den lever, ikke henger.
Delresultater overlever altså om noen modeller feiler eller du avbryter.

```bash
python haakonbench.py --effort max --timeout 600   # marker modeller > 600s som FAILED og gradér resten
```

---

## Resultater

```
results/
  2026-05-24_110000/        ← første kjør
    anthropic__claude-opus-4-7.md
    anthropic__claude-sonnet-4-6.md
    openai__gpt-5.5.md
    ...
    _grades.md              ← karakterer + rangering + vinner
  2026-05-24_143022/        ← andre kjør  (latest)
    ...
```

Hver modell-fil har hele svaret, med en `<!-- HB_META ... -->`-blokk i toppen som
lagrer tid, effort-nivå og token-bruk (input/output/reasoning/total) – så tallene
overlever `--regrade`.

`_grades.md` har en blindtest-tabell (A/B/C…) med poengsummer på Accuracy, Strategy,
Creativity, Structure og Fidelity, en nøkkel som avslører hvilken modell som er hvilken,
og til slutt en **Efficiency — raw data**-tabell som setter hver modells totalscore ved
siden av tid og token-tall (sortert på score). Da ser du f.eks. om to modeller fikk samme
karakter, men den ene brukte halvparten av tokens eller tiden.

---

## Konfigurere deltakere

Rediger `CONTESTANTS`-lista øverst i `haakonbench.py`:

```python
CONTESTANTS = [
    ("anthropic", "claude-opus-4-7"),
    ("openai",    "gpt-5.5"),
    # ("xai",    "grok-4.3"),   # kommenter ut om du ikke har nøkkel
]
```

Dommeren settes med `GRADER_PROVIDER` / `GRADER_MODEL` i toppen av `haakonbench.py`, og kan overstyres per kjøring:

```bash
python haakonbench.py --grader-model google/gemini-3.5-flash
```

---

## Filer

| Fil | Hva den gjør |
|---|---|
| `haakonbench.py` | Benchmark-runner + grader |
| `llm_client.py` | Unified async-klient for alle 4 leverandører |
| `config.yaml` | Standard provider/modell for `LLMClient` (ikke graderen) |
| `requirements.txt` | Python-avhengigheter |

---

## HTML-siden (det originale prosjektet)

Statisk referanseside – åpne `index.html` direkte i nettleseren, eller:

```bash
python -m http.server 8000
```
→ http://localhost:8000
