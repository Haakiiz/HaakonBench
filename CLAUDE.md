# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Two separate things live here:

1. **HåkonBench** — a Python benchmark that sends the same prompt to multiple LLM providers in parallel, then grades all responses blind with a judge model.
2. **`index.html`** — a static WoW Classic fishing strategy guide (pure HTML + inline CSS, no build step).

---

## Setup

```bash
pip install -r requirements.txt
```

`.env` file in the project root (only the keys you need):
```
ANTHROPIC_API_KEY=...
CHATGPT_API_KEY=...
GOOGLE_API_KEY=...
XAI_API_KEY=...
```

---

## Common commands

```bash
# Full benchmark run — new timestamped folder
python haakonbench.py

# Re-grade existing results with updated grader prompt
python haakonbench.py --regrade

# Retry a failed model (slots into latest run folder, re-grades)
python haakonbench.py --only openai/gpt-5.5

# Use a different grader model
python haakonbench.py --regrade --grader-model anthropic/claude-opus-4-7

# Run models without grading (cheap connectivity check)
python haakonbench.py --no-grade

# List all run folders
python haakonbench.py --list

# Validate grader accuracy against WoW Classic reference data
python test_grader.py

# Same test but with verbose per-claim output
python test_grader.py --verbose

# Test with a different model
python test_grader.py --model claude-opus-4-7
```

---

## Architecture

### Benchmark flow (`haakonbench.py`)

1. **Run phase** — `CONTESTANTS` list drives parallel async API calls via `LLMClient`. Each response is written to `results/{timestamp}/{provider}__{model}.md`.
2. **Grade phase** — all successful responses are loaded, anonymised as letters (A, B, C…), and sent to the judge model in a single call. The judge uses `GRADER_SYSTEM_TEMPLATE` + `GRADER_RUBRIC` to produce a scored markdown table plus hallucination callouts. Results go to `results/{timestamp}/_grades.md` with the letter→model key appended at the end.

### Grader accuracy

The grader is backed by `wow_reference.yaml` — a curated file of verified WoW Classic facts (recipes, ingredients, buff stats, zones, vendors). This file is injected into the grader's system prompt at runtime so it judges accuracy against ground truth rather than its own knowledge. **When the grader flags a factual error, always check `wow_reference.yaml` first before assuming the response is wrong.**

`test_grader.py` + `test_claims.yaml` provide a 48-claim test suite (target: ≥95% accuracy) to validate the grader's fact-checking. Run it after changing the grader prompt or reference data.

### LLM client (`llm_client.py`)

Unified async wrapper for Anthropic, OpenAI (and xAI via OpenAI-compatible endpoint), and Google Gemini. Provider/model are passed at construction time, so `haakonbench.py` can drive many models concurrently. `config.yaml` sets defaults only when `LLMClient` is called directly (not used by the benchmark runner).

### Key constants in `haakonbench.py`

| Name | Purpose |
|------|---------|
| `CONTESTANTS` | List of `(provider, model)` tuples to benchmark |
| `GRADER_PROVIDER` / `GRADER_MODEL` | Default judge (overridable with `--grader-model`) |
| `PROMPT` | The single prompt sent to all contestants |
| `GRADER_SYSTEM_TEMPLATE` | Judge system prompt; `{reference_data}` is filled from `wow_reference.yaml` |
| `GRADER_RUBRIC` | Scoring rubric (5 dimensions: Accuracy, Strategy, Creativity, Structure, Fidelity) |

---

## Extending the benchmark

- **Add a contestant:** append `("provider", "model-name")` to `CONTESTANTS`.
- **Change the prompt:** edit the `PROMPT` constant.
- **Improve grader accuracy:** add entries to `wow_reference.yaml` (the grader reads it on every run) and add corresponding claims to `test_claims.yaml`, then run `python test_grader.py`.
- **Add a new provider:** implement its branch in `LLMClient._init_client()` and `LLMClient.call()`.

---

## HTML guide (`index.html`)

Open directly in a browser, or `python -m http.server 8000` → http://localhost:8000.
CSS variables for the theme (`--gold`, `--alliance-blue`, etc.) are at the top of the `<style>` block.
