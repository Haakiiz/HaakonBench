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

Hver modell-fil har hele svaret. `_grades.md` har en blindtest-tabell (A/B/C…) med
poengsummer på Accuracy, Strategy, Creativity, Structure og Fidelity – og en nøkkel
på slutten som avslører hvilken modell som er hvilken.

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
