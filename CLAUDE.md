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

# Crank reasoning/thinking + token budget to the high or max tier
python haakonbench.py --effort high
python haakonbench.py --effort max --only anthropic/claude-opus-4-8

# Turn ON each provider's server-side web search (default OFF — base knowledge only)
python haakonbench.py --web-search
python haakonbench.py --web-search --only anthropic/claude-opus-4-8

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

1. **Run phase** — `CONTESTANTS` list drives parallel async API calls via `LLMClient`. Each response is written to `results/{timestamp}/{provider}__{model}.md`. The file header carries an `<!-- HB_META ... -->` block recording wall-clock time, the effort tier, and token usage (input/output/reasoning/total) so it survives `--regrade`.
2. **Grade phase** — all successful responses are loaded, anonymised as letters (A, B, C…), and sent to the judge model in a single call. The judge uses `GRADER_SYSTEM_TEMPLATE` + `GRADER_RUBRIC` to produce a scored markdown table plus hallucination callouts. Results go to `results/{timestamp}/_grades.md` with the letter→model key appended, followed by an **Efficiency — raw data** table joining each model's Total score against its time and token counts (sorted by score). The score column is parsed best-effort from the judge's table; if parsing fails it shows `—` but the token/time columns still populate.

### Effort tiers (`--effort {low,medium,high,max}`)

One abstract CLI knob, **translated per provider** because providers disagree on the level names and ceilings. Every provider that has a knob now uses a **named effort level** (no provider uses a numeric token budget anymore). `TIER_MAX_TOKENS` sets a universal output budget; `PROVIDER_EFFORT` in `haakonbench.py` is the single source of truth, and `resolve_effort()` applies the per-model Anthropic caps. Default is `medium`.

| Tier | max_tokens | Anthropic Opus (effort) | OpenAI (reasoning.effort) | Gemini 3 (thinking_level) | xAI grok-4.3 (reasoning_effort) |
|------|-----------|-------------------------|---------------------------|---------------------------|---------------------------------|
| low | 8000 | low | low | low | low |
| medium | 16000 | medium | medium | medium | medium |
| high | 32000 | high | high | high | high |
| max | 64000 | **max** | **xhigh** | high | high |

Key per-provider facts (verified against provider docs):
- **Anthropic** Opus 4.7/4.8 use `output_config: {effort: low/medium/high/xhigh/max}` **plus** `thinking: {type: "adaptive"}` (sent via `extra_body` so older SDKs that don't type `output_config` still forward it). The old numeric `thinking.budget_tokens` / `thinking: {type:"enabled"}` is **removed** and returns 400. `max` is Opus-tier only; **Sonnet 4.6** caps at `high`; **Haiku 4.5** supports neither effort nor adaptive thinking (gets no knob). An explicit `timeout` is passed to suppress the SDK's non-streaming guard (which raises for `max_tokens` > ~21k; the `max` tier is 64k).
- **OpenAI** gpt-5.5 supports `low/medium/high/xhigh` (also `minimal`/`none`); `max` tier uses `xhigh`.
- **Gemini 3** uses a named `thinking_level` (low/medium/high), **not** the old numeric `thinking_budget` — passing a budget to a Gemini 3 model is a hard error. Set via `ThinkingConfig(thinking_level=...)` (case-insensitive).
- **xAI** grok-4.3 **does** accept `reasoning_effort` (none/low/medium/high), sent via `extra_body`. (Older grok-4 rejects it.)

`LLMClient` exposes a single `reasoning_effort` (the named level for every provider; Anthropic also auto-enables adaptive thinking). An unsupported level just makes that one call fail loudly (saved as `FAILED`), never a silent empty. After every `call()`, `client.last_usage` holds the normalized `{input,output,reasoning,total}_tokens` dict (parsed from each provider's usage object).

### Web search (`--web-search`)

**Default OFF** — every contestant answers from base knowledge only (no `tools` are sent). This is usually what you want for a WoW-Classic-facts benchmark: it tests the model's own knowledge against `wow_reference.yaml`, not its ability to look things up. Pass `--web-search` to flip on each provider's **server-side** web search tool. All searching happens on the provider's infra — there is no scraping/fetch code in this repo, `LLMClient` just declares the tool. `LLMClient.web_search` is the single boolean knob; the flag is recorded in `HB_META` (`web_search: true/false`) so a run's search mode survives `--regrade`. The grader **never** uses web search (it judges against the reference file).

| Provider | Tool attached when `--web-search` is on |
|----------|------------------------------------------|
| Anthropic | `tools: [{type: web_search_20260209, name: web_search}]` — GA, no beta header; dynamic filtering auto-activates on Opus 4.8/4.7/4.6 & Sonnet 4.6 |
| OpenAI | Responses API `tools: [{type: web_search}]` (the gpt-5.x contestants already route through the Responses branch) |
| Gemini | `GenerateContentConfig(tools=[Tool(google_search=GoogleSearch())])` — Gemini 3 is billed **per search query** |
| xAI | agent-tools `tools: [{type: web_search}]` — ⚠️ the old `search_parameters` Live Search was **retired 2026-01-12** (410s); agent-tools `web_search` is the replacement |

As with the effort knob, an unsupported tool just makes that one call fail loudly (saved as `FAILED`), never a silent empty.

### Grader accuracy

The grader is backed by `wow_reference.yaml` — a curated file of verified WoW Classic facts (recipes, ingredients, buff stats, zones, vendors). This file is injected into the grader's system prompt at runtime so it judges accuracy against ground truth rather than its own knowledge. **When the grader flags a factual error, always check `wow_reference.yaml` first before assuming the response is wrong.**

`test_grader.py` + `test_claims.yaml` provide a 48-claim test suite (target: ≥95% accuracy) to validate the grader's fact-checking. Run it after changing the grader prompt or reference data.

### LLM client (`llm_client.py`)

Unified async wrapper for Anthropic, OpenAI (and xAI via OpenAI-compatible endpoint), and Google Gemini. Provider/model are passed at construction time, so `haakonbench.py` can drive many models concurrently. `config.yaml` sets defaults only when `LLMClient` is called directly (not used by the benchmark runner).

### Reasoning models and token budgets

Different providers count reasoning/thinking tokens differently. If you set `max_tokens=8000` naively, reasoning models can burn the whole budget internally and return an empty visible response. gpt-5.5 hit exactly this — the file ended up empty.

| Provider | What `max_tokens` covers | Reasoning behavior |
|---|---|---|
| Anthropic (Claude) | **Thinking + visible output (shared)** — thinking tokens count toward `max_tokens` | Depth is the named `output_config.effort` level + `thinking: {type: "adaptive"}` (Opus 4.7/4.8, Sonnet 4.6). Numeric `budget_tokens` is **removed** (400s). Set via `LLMClient.reasoning_effort`. The client passes an explicit `timeout` so the non-streaming guard doesn't reject the 64k `max` tier. |
| OpenAI (gpt-5.x, o1/o3/o4) | **Reasoning + output (shared)** via Responses API `max_output_tokens` | Always on. Effort defaults to `medium`, can consume 5–15k tokens before any visible output. |
| xAI (grok-4.x) | Visible output only | Reasoning happens server-side, not counted against `max_tokens`. grok-4.3 accepts `reasoning_effort` (sent via `extra_body`); older grok-4 rejects it. |
| Google (Gemini 2.5+/3.x) | **Thinking + output (shared)** via `max_output_tokens` | Thinking on by default. Gemini 3 controls depth with named `thinking_level` (low/medium/high), not numeric `thinking_budget`. |

**Rule for shared-budget providers (OpenAI Responses API, Gemini 2.5+):** floor the budget at **20 000 tokens** so the model has room to reason *and* produce a meaningful answer (~8k visible after ~8–12k reasoning). Enforced in `llm_client.py` via `total_token_budget = max(self.max_tokens, 20000)` in both the OpenAI reasoning branch and the Google branch. Also detect `response.status == "incomplete"` (OpenAI) so silent empties surface as real errors.

**When adding a new reasoning model:** check the provider's docs — does the output-token cap include reasoning tokens? If yes, route through the shared-budget pattern above. If no (like Claude/Grok), normal `max_tokens` is fine.

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
