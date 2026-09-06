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
# Run the benchmark. Lands in the bucket for this config and only calls the
# contestants that don't already have a valid answer there.
python haakonbench.py

# Show what would be reused vs. called (and what it lands in) — calls nothing
python haakonbench.py --dry-run

# Ignore cached answers and re-call every contestant in the bucket
python haakonbench.py --refresh

# Re-grade existing results with updated grader prompt
python haakonbench.py --regrade

# Retry / force-refresh specific models (always calls them, cached or not)
python haakonbench.py --only openai/gpt-5.5

# A second, independent bucket of the same config (e.g. to measure variance)
python haakonbench.py --tag variance-2

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

# List all buckets (config, how many answers, when last graded)
python haakonbench.py --list

# Target an old timestamped folder by name (pre-bucket runs have no manifest)
python haakonbench.py --regrade --run 2026-07-09_214014

# Validate grader accuracy against WoW Classic reference data
python test_grader.py

# Same test but with verbose per-claim output
python test_grader.py --verbose

# Test with a different model
python test_grader.py --model claude-opus-4-7
```

---

## Architecture

### Run buckets — results are keyed on config, not on time

A saved answer is reusable **if and only if** everything that shaped it is identical: the `PROMPT` text, the effort tier (which also fixes `max_tokens`), and whether web search was on. Those three fields *are* the folder name:

```
results/p3f2a1c__high__search-on/
    _run.json          ← authoritative config record (the folder name is just the label)
    _prompt.md         ← the exact prompt these answers were given
    openai__gpt-5.6-sol.md
    anthropic__claude-opus-4-8.md
    _grades.md         ← latest verdict
    _grades/2026-07-24_203355_google__gemini-3.5-flash.md   ← history
```

So re-running a config **lands in the same bucket and only calls what's missing**. Adding an 11th model to `CONTESTANTS` and re-running the same command costs one API call, not eleven. The pieces:

- **`prompt_sha()`** — first 6 hex of `sha256(PROMPT)`. Edit one comma in the prompt and the hash changes, so old answers can never be silently reused against a new prompt. It reads the `PROMPT` global at call time — **do not** turn that back into a default argument, or the hash freezes at import.
- **`plan_contestants()`** — splits `CONTESTANTS` into `(to_call, reused)`. `has_valid_result()` defines "reusable": file exists, isn't `FAILED`, and has a non-empty body. So failed *and* silently-empty responses are always retried.
- **`--only` / `--refresh`** are explicit "call it anyway" instructions and skip the cache. `--dry-run` prints the plan and exits without writing anything (it even removes the empty bucket it just probed).
- **Config guard** — `--run NAME` refuses to proceed if that folder's `_run.json` contradicts your flags (pass `--force` to override). This is what stops an `--effort high` answer from being slotted into a low-effort folder. Legacy timestamped folders have no manifest: they still work, you just get a warning that the config can't be verified.
- **`--tag foo`** appends to the bucket name, for a deliberately separate run of the same config (variance testing).

### Benchmark flow (`haakonbench.py`)

1. **Run phase** — `CONTESTANTS` minus whatever the bucket already answered drives parallel async API calls via `LLMClient`. Each response is written to `results/{bucket}/{provider}__{model}.md`. The file header carries an `<!-- HB_META ... -->` block recording the date, wall-clock time, effort tier, max_tokens, prompt_sha and token usage (input/output/reasoning/total) so it survives `--regrade`. Because a bucket fills up over time, `date` matters: the efficiency table grows an **Answered** column whenever the answers in a bucket aren't all from the same day.
2. **Grade phase** — **always runs over the whole bucket, even when nothing was called.** Grading is comparative and blind (responses are anonymised as letters A, B, C…), so one added contestant reshuffles everyone's letters and can move their scores — and it's a single cheap call next to the answers it ranks. The judge uses `GRADER_SYSTEM_TEMPLATE` + `GRADER_RUBRIC` to produce a scored markdown table plus hallucination callouts. Output goes to `_grades.md` (latest) *and* an archived copy under `_grades/{stamp}_{grader}.md`, so re-grading with a different judge doesn't erase the old verdict. Each verdict is stamped with an `HB_GRADE` header (grader, date, response count, bucket config) — scores depend on the grader and on the exact set compared, not just on the answers. The letter→model key is appended, followed by an **Efficiency — raw data** table joining each model's Total score against its time and token counts (sorted by score). The score column is parsed best-effort from the judge's table; if parsing fails it shows `—` but the token/time columns still populate.

### Effort tiers (`--effort {low,medium,high,max}`)

One abstract CLI knob, **translated per provider** because providers disagree on the level names and ceilings. Every provider that has a knob now uses a **named effort level** (no provider uses a numeric token budget anymore). `TIER_MAX_TOKENS` sets a universal output budget; `PROVIDER_EFFORT` in `haakonbench.py` is the single source of truth, and `resolve_effort()` applies the per-model Anthropic caps. Default is `medium`.

| Tier | max_tokens | Anthropic Opus/Sonnet 5/Fable 5.1 (effort) | OpenAI (reasoning.effort) | Gemini 3.x (thinking_level) | xAI grok-4.3/4.5/4.6 (reasoning_effort) |
|------|-----------|----------------------------------|---------------------------|-----------------------------|--------------------------------------|
| low | 16000 | low | low | low | low |
| medium | 32000 | medium | medium | medium | medium |
| high | 64000 | high | high | high | high |
| max | 128000 | **max** | **max** (Astra, Sol) / xhigh (others) | high | **xhigh** (4.6) / high (4.3, 4.5) |

Key per-provider facts (verified against provider docs):
- **Anthropic** Opus 4.7/4.8, **Opus 5**, **Sonnet 5** and **Fable 5.1** use `output_config: {effort: low/medium/high/xhigh/max}` **plus** `thinking: {type: "adaptive"}` (sent via `extra_body` so older SDKs that don't type `output_config` still forward it). The old numeric `thinking.budget_tokens` / `thinking: {type:"enabled"}` is **removed** and returns 400. Sonnet 5 takes the full range up to `max` (and runs adaptive thinking by default even without the `thinking` param); **Sonnet 4.x** caps at `high`; **Haiku 4.5** supports neither effort nor adaptive thinking (gets no knob). Sonnet 5's model ID is `claude-sonnet-5` — **no date suffix** (dated forms 404). An explicit `timeout` is passed to suppress the SDK's non-streaming guard (which raises for `max_tokens` > ~21k).
- **Fable 5.1** (`claude-fable-5-1`, released 2026-08-28) is Anthropic's top tier at **$10/$50 per MTok** — 5× Opus 5's output price, so it's the most expensive contestant in the field by a wide margin. 1M context, 128K max output, full `low..max` effort range. **Thinking is always on**: `{type: "adaptive"}` (what we send) or omitting the param are the only accepted forms — `{type: "disabled"}` and `budget_tokens` both 400. The raw chain of thought is never returned and `display` defaults to `omitted`, so `reasoning_tokens` reads as 0 in `HB_META` and the thinking spend shows up inside `output_tokens` instead. Web search (`web_search_20260209` with `allowed_callers: ["direct"]`) is supported — verified with a live call. Two Fable-only wrinkles the benchmark never hits: forced `tool_choice` (`any`/`tool`) 400s, and a request can come back with `stop_reason: "refusal"` instead of content (it would be saved as an empty answer and retried on the next run).
- **OpenAI** **GPT-6 Astra** (`gpt-6-astra`, released 2026-09-03) is the new frontier model — $10/$50 per MTok (Anthropic-Fable money, 2× Sol's tier). Effort range is the widest of any contestant: `none/minimal/low/medium/high/xhigh/max`, so it takes `max` like Sol while Terra, Luna and gpt-5.5 stay capped at `xhigh`. It's a reasoning model on the Responses API — Chat Completions rejects `max_tokens` outright — so `llm_client.py`'s reasoning predicate had to grow a `"gpt-6"` prefix; without it the model would have silently fallen through to the Chat Completions branch. `tools: [{type: web_search}]` works, even though the API's own tool-enum error message lists only `web_search_preview` (the enum is stale — verified with live calls on both Astra and Sol). GPT-5.6 family (launched 2026-07-09): `gpt-5.6-sol` (flagship), `gpt-5.6-terra` (balanced), `gpt-5.6-luna` (fast/cheap). There is **no** bare `gpt-5.6` alias and no dated snapshots for the family — the three suffixed IDs are the only forms (verified against `/v1/models` 2026-07-24; bare `gpt-5.6` returns 404 `model_not_found`). All support `low/medium/high/xhigh` (also `minimal`/`none`); **`max` effort is Sol-only** — `resolve_effort()` caps every other OpenAI model at `xhigh` on the `max` tier. gpt-5.5 (previous frontier) supports up to `xhigh`. All `gpt-5.x` IDs route through the Responses-API reasoning branch in `llm_client.py` (shared reasoning+output budget, 20k floor still applies; Sol at `max` effort is token-hungry — the big `max`-tier budget matters).
- **Gemini 3.x** uses a named `thinking_level`, **not** the old numeric `thinking_budget` — passing a budget to a Gemini 3 model is a hard error. Set via `ThinkingConfig(thinking_level=...)` (case-insensitive). 3.1 Pro: `low/medium/high`, default `high` (still `gemini-3.1-pro-preview` — no GA ID yet). 3.5 Flash: `minimal/low/medium/high`, default `medium` (`gemini-3.5-flash` is GA). **3.7 Flash** (GA 2026-08-13, `gemini-3.7-flash`): `low/medium/high` only, default `medium` — **`minimal` is rejected with a validation error**, unlike 3.5 Flash. **3.8 Flash** (`gemini-3.8-flash`, GA): same surface as 3.7 — `low/medium/high`, default `medium`, 1M in / 64K out, Google Search grounding — so it needed no client changes; verified with a live call. From 3.6 onward `temperature`/`top_p`/`top_k` are deprecated; `llm_client.py` already only sends `temperature` for `gemini-1`/`gemini-2` IDs, so no change was needed.
- **xAI** grok-4.3, grok-4.5 and grok-4.6 accept `reasoning_effort`, sent via `extra_body`. (Older grok-4 rejects it.) IDs use a dot: `grok-4.5`, `grok-4.6`. grok-4.3/4.5 take `none/low/medium/high` (4.5 defaults to `high`); **grok-4.6** (released 2026-08-12, 500K context, knowledge cutoff 2026-02-01) adds **`xhigh`** and also defaults to `high`. The `max` tier therefore maps xAI to `xhigh`, and `resolve_effort()` caps every non-4.6 grok back to `high`.

`LLMClient` exposes a single `reasoning_effort` (the named level for every provider; Anthropic also auto-enables adaptive thinking). An unsupported level just makes that one call fail loudly (saved as `FAILED`), never a silent empty. After every `call()`, `client.last_usage` holds the normalized `{input,output,reasoning,total}_tokens` dict (parsed from each provider's usage object).

### Web search (`--web-search`)

**Default OFF** — every contestant answers from base knowledge only (no `tools` are sent). This is usually what you want for a WoW-Classic-facts benchmark: it tests the model's own knowledge against `wow_reference.yaml`, not its ability to look things up. Pass `--web-search` to flip on each provider's **server-side** web search tool. All searching happens on the provider's infra — there is no scraping/fetch code in this repo, `LLMClient` just declares the tool. `LLMClient.web_search` is the single boolean knob; the flag is recorded in `HB_META` (`web_search: true/false`) so a run's search mode survives `--regrade`. The grader **never** uses web search (it judges against the reference file).

| Provider | Tool attached when `--web-search` is on |
|----------|------------------------------------------|
| Anthropic | `tools: [{type: web_search_20260209, name: web_search}]` — GA, no beta header; dynamic filtering auto-activates on Opus 4.8/4.7/4.6 & Sonnet 4.6 |
| OpenAI | Responses API `tools: [{type: web_search}]` (the gpt-5.x contestants already route through the Responses branch) |
| Gemini | `GenerateContentConfig(tools=[Tool(google_search=GoogleSearch())])` — Gemini 3 is billed **per search query** |
| xAI | Responses API `tools: [{type: web_search}]` — Chat Completions endpoint only accepts `"function"` or `"live_search"` and rejects `web_search` |

As with the effort knob, an unsupported tool just makes that one call fail loudly (saved as `FAILED`), never a silent empty.

**Search counts are model-decided, not capped.** We attach only the tool — each provider runs its own server-side search loop and the model chooses how many queries to fire. `LLMClient.last_web_searches` captures how many it *actually* ran, parsed per provider: Anthropic `usage.server_tool_use.web_search_requests`, OpenAI `web_search_call` items in the Responses output, Gemini `grounding_metadata.web_search_queries`. xAI stays `None` — the OpenAI-compatible usage object doesn't expose a clean per-call search count. The count is folded into `HB_META` (`web_searches: N`, omitted when unknown) and surfaces as a **Web searches** column in the efficiency table — but only on `--web-search` runs (normal runs keep the original 6-column table). Provider caps exist if you ever want bounded/comparable runs (Anthropic `max_uses`, xAI `max_turns`) but are not wired up.

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
