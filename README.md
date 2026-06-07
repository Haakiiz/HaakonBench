# HåkonBench

Send the same prompt til alle store LLM-leverandører parallelt, og la Claude Sonnet gradere svarene blindt.

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

| Tier | max_tokens | Anthropic Opus | OpenAI | Gemini 3 | xAI grok-4.3 |
|------|-----------|----------------|--------|----------|--------------|
| low | 8000 | low | low | low | low |
| medium | 16000 | medium | medium | medium | medium |
| high | 32000 | high | high | high | high |
| max | 64000 | **max** | **xhigh** | high | high |

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

Graderen er alltid `claude-sonnet-4-6` (Anthropic). Endre i toppen av `haakonbench.py` om ønskelig.

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
