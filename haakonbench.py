"""
haakonbench.py — Run the same prompt across multiple providers/models,
then have a grader model score the responses blind.

Full run  →  creates a NEW timestamped folder so nothing is ever overwritten:
    python haakonbench.py
    # → results/2026-05-24_143022/

Retry / add a model  →  targets the LATEST run folder by default:
    python haakonbench.py --only openai/gpt-5.5
    python haakonbench.py --only anthropic/claude-opus-4-7,xai/grok-4.3

Target a specific past run:
    python haakonbench.py --only openai/gpt-5.5 --run 2026-05-24_143022
    python haakonbench.py --regrade --run 2026-05-24_110000

Other flags:
    --regrade   skip API calls, re-grade everything on disk in the target run folder
    --no-grade  run models but skip grading
    --list      show all existing run folders and exit
"""

import argparse
import asyncio
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from llm_client import LLMClient

# ── Contestants ────────────────────────────────────────────────────────────
CONTESTANTS: list[tuple[str, str]] = [
    ("anthropic", "claude-opus-4-8"),
    ("anthropic", "claude-opus-4-7"),
    ("anthropic", "claude-sonnet-4-6"),
    ("anthropic", "claude-haiku-4-5"),
    ("openai",    "gpt-5.5"),
    ("openai",    "gpt-5.4-mini"),
    ("google",    "gemini-3.1-pro-preview"),
    ("google",    "gemini-3.5-flash"),
    ("xai",       "grok-4.3"),
]

# ── Grader ─────────────────────────────────────────────────────────────────
GRADER_PROVIDER = "anthropic"
GRADER_MODEL    = "claude-sonnet-4-6"

# ── The prompt ─────────────────────────────────────────────────────────────
PROMPT = """I want you to create me a fishing strategy, as a level 60 human warrior on World of Warcraft Classic servers. I must be able to fish for an extended period of time where i am not killed and do not have to move. That is alliance zones, or maybe very hidden areas in contested zones. I have level 300 fishing and level 300 cooking, so please utilize both for maximum gold/hour. Tell me where to fish, when, what, etc. Give an estimated gold / hour for the different zones and areas and fish.

Be creative in giving me a great guide, you can add 'features'/chapters/stuff as youd like, if you think that would improve the end result. You are not hard limited by this prompt, but catch the essence of it and work on it. Your overarching goal is to impress me"""

MAX_TOKENS_PER_CALL = 8000
BASE_RESULTS_DIR    = Path("results")
BODY_SEP            = "\n<!-- BEGIN RESPONSE -->\n"
META_RE             = re.compile(r"<!-- HB_META\n(.*?)\n-->", re.DOTALL)

# ── Effort tiers ───────────────────────────────────────────────────────────
# One user-facing knob (--effort low|medium|high|max). Each tier sets a
# universal output-token budget, then is TRANSLATED per provider. Every provider
# that exposes a knob now uses a NAMED effort level — but the names and ceilings
# differ, and some are Opus-only:
#
#   anthropic → output_config.effort + adaptive thinking
#               (low/medium/high/xhigh/max; 'max' is Opus-only; Haiku 4.5
#                supports neither effort nor adaptive thinking → no knob)
#   openai    → reasoning.effort          (low/medium/high/xhigh)
#   google    → thinking_level            (low/medium/high; Gemini 3 rejects
#                                           the old numeric thinking_budget)
#   xai       → reasoning_effort          (low/medium/high; grok-4.3 supports it)
#
# PROVIDER_EFFORT is the SINGLE place to edit when a provider adds or renames a
# level; resolve_effort() applies the per-model Anthropic caps. None = leave the
# provider default. An unsupported value just makes that one call fail loudly
# (saved as FAILED), never a silent empty.
TIERS = ["low", "medium", "high", "max"]
DEFAULT_EFFORT = "medium"

TIER_MAX_TOKENS = {"low": 8000, "medium": 16000, "high": 32000, "max": 64000}

PROVIDER_EFFORT: dict[str, dict[str, object]] = {
    "anthropic": {"low": "low", "medium": "medium", "high": "high", "max": "max"},   # output_config.effort
    "openai":    {"low": "low", "medium": "medium", "high": "high", "max": "xhigh"}, # reasoning.effort
    "google":    {"low": "low", "medium": "medium", "high": "high", "max": "high"},  # thinking_level
    "xai":       {"low": "low", "medium": "medium", "high": "high", "max": "high"},  # reasoning_effort
}


# ── Folder helpers ─────────────────────────────────────────────────────────

def new_run_dir() -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path  = BASE_RESULTS_DIR / stamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def latest_run_dir() -> Path:
    """Return the most recently created run folder, or raise if none exist."""
    BASE_RESULTS_DIR.mkdir(exist_ok=True)
    folders = sorted(
        (p for p in BASE_RESULTS_DIR.iterdir() if p.is_dir()),
        key=lambda p: p.name,  # ISO timestamp names sort chronologically
    )
    if not folders:
        raise SystemExit(
            "No existing run folders found in ./results/.\n"
            "Run 'python haakonbench.py' first to create one."
        )
    return folders[-1]


def resolve_run_dir(run_name: str | None, *, creating_new: bool) -> Path:
    if creating_new:
        return new_run_dir()
    if run_name:
        path = BASE_RESULTS_DIR / run_name
        if not path.is_dir():
            raise SystemExit(f"Run folder not found: {path}")
        return path
    return latest_run_dir()


def list_runs() -> None:
    BASE_RESULTS_DIR.mkdir(exist_ok=True)
    folders = sorted(p for p in BASE_RESULTS_DIR.iterdir() if p.is_dir())
    if not folders:
        print("No run folders yet.")
        return
    print(f"{'Run folder':<30}  Files  Grades?")
    print("-" * 50)
    for p in folders:
        md_files = [f for f in p.glob("*.md") if not f.name.startswith("_")]
        has_grades = (p / "_grades.md").exists()
        marker = "latest ←" if p == folders[-1] else ""
        print(f"  {p.name:<28}  {len(md_files):>3}    {'✓' if has_grades else '—'}  {marker}")


# ── Running ────────────────────────────────────────────────────────────────

def slug(provider: str, model: str) -> str:
    return f"{provider}__{re.sub(r'[^A-Za-z0-9._-]+', '-', model)}"


def resolve_effort(provider: str, model: str, effort: str) -> tuple[int, object]:
    """Translate an abstract tier into (max_tokens, provider-specific effort level).
    Returns a named level string, or None to leave the provider default. Applies
    the per-model Anthropic caps (Haiku has no knob; max/xhigh are Opus-only)."""
    knob = PROVIDER_EFFORT.get(provider, {}).get(effort)
    if provider == "anthropic":
        m = model.lower()
        if "haiku" in m:
            knob = None                       # Haiku 4.5: no effort, no adaptive thinking
        elif "sonnet" in m and knob in ("xhigh", "max"):
            knob = "high"                     # 'max'/'xhigh' are Opus-tier only
    return TIER_MAX_TOKENS[effort], knob


async def run_contestant(
    provider: str, model: str, effort: str, timeout: float | None = None,
) -> tuple[str, str, float, str | None, dict | None]:
    label = slug(provider, model)
    t0 = time.perf_counter()
    try:
        max_tokens, knob = resolve_effort(provider, model, effort)
        client = LLMClient(provider=provider, model=model)
        client.max_tokens = max_tokens
        client.reasoning_effort = knob        # named level (or None for provider default)
        if timeout:
            response = await asyncio.wait_for(client.call(PROMPT), timeout=timeout)
        else:
            response = await client.call(PROMPT)
        return label, response, time.perf_counter() - t0, None, client.last_usage
    except asyncio.TimeoutError:
        return label, "", time.perf_counter() - t0, f"TimeoutError: no response within {timeout:.0f}s", None
    except Exception as e:
        return label, "", time.perf_counter() - t0, f"{type(e).__name__}: {e}", None


def _meta_block(secs: float, effort: str, usage: dict | None) -> str:
    """A machine-parseable comment so --regrade can recover tokens/time later."""
    usage = usage or {}
    lines = [
        "<!-- HB_META",
        f"seconds: {secs:.1f}",
        f"effort: {effort}",
        f"input_tokens: {usage.get('input_tokens', 0)}",
        f"output_tokens: {usage.get('output_tokens', 0)}",
        f"reasoning_tokens: {usage.get('reasoning_tokens', 0)}",
        f"total_tokens: {usage.get('total_tokens', 0)}",
        "-->",
    ]
    return "\n".join(lines)


def save_result(
    run_dir: Path, label: str, response: str, secs: float,
    err: str | None, usage: dict | None = None, effort: str = DEFAULT_EFFORT,
) -> str:
    """Write the result file and return a one-line status string for the caller
    to print (so the run loop can stream feedback as each model finishes)."""
    path = run_dir / f"{label}.md"
    if err:
        path.write_text(
            f"# {label}\n\n**FAILED after {secs:.1f}s**\n\n```\n{err}\n```\n",
            encoding="utf-8",
        )
        return f"  ✗ {label}  ({secs:.1f}s)  — {err}"
    meta = _meta_block(secs, effort, usage)
    path.write_text(
        f"# {label}\n\n_Generated in {secs:.1f}s_\n\n{meta}\n{BODY_SEP}\n{response}\n",
        encoding="utf-8",
    )
    tok = usage.get("total_tokens", 0) if usage else 0
    return f"  ✓ {label}  ({secs:.1f}s, {len(response):,} chars, {tok:,} tok)"


# ── Loading from disk ──────────────────────────────────────────────────────

def load_successful_results(run_dir: Path) -> list[tuple[str, str]]:
    """Read every successful result file from run_dir.
    Returns [(label, body)] sorted by label for stable letter assignment."""
    out = []
    for path in sorted(run_dir.glob("*.md")):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        if "**FAILED" in text[:400]:
            print(f"  (skipping {path.name} — failed run)", file=sys.stderr)
            continue
        # Support both new (BODY_SEP) and old ("\n---\n\n") formats.
        if BODY_SEP in text:
            body = text.split(BODY_SEP, 1)[1].strip()
        elif "\n---\n\n" in text:
            body = text.split("\n---\n\n", 1)[1].strip()
        else:
            print(f"  (skipping {path.name} — unrecognized format)", file=sys.stderr)
            continue
        out.append((path.stem, body))
    return out


def load_result_meta(run_dir: Path, label: str) -> dict:
    """Recover the HB_META block (tokens/time/effort) for a result file.
    Returns {} if the file is missing or has no metadata (e.g. older runs)."""
    path = run_dir / f"{label}.md"
    if not path.exists():
        return {}
    m = META_RE.search(path.read_text(encoding="utf-8"))
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


# ── Grading ────────────────────────────────────────────────────────────────

GRADER_SYSTEM_TEMPLATE = (
    "You are an expert evaluator for LLM benchmarks. You grade responses blind — "
    "the identities of the models are hidden behind letters (A, B, C, ...). Be "
    "rigorous, specific, and honest. Reward accuracy, depth, creativity, structure, "
    "and usefulness. Penalize hallucinations (especially WoW Classic facts that look "
    "made up), generic filler, and prompt-ignoring.\n\n"
    "CRITICAL RULE FOR ACCURACY SCORING: When checking WoW Classic facts, use ONLY "
    "the Verified Reference Data section below as your source of truth. Do NOT rely "
    "on your own knowledge for recipes, buff stats, ingredients, or vendor locations — "
    "it may be wrong. If a claim cannot be verified against the reference data, mark "
    "it as 'unverifiable' rather than calling it incorrect. Pay special attention to "
    "the 'Common LLM Hallucinations' list — these are known errors that look plausible "
    "but are wrong.\n\n"
    "{reference_data}"
)


def _format_reference_data(data: dict) -> str:
    lines = ["## Verified WoW Classic Fishing Reference Data (ground truth)", ""]

    if data.get("cooking_recipes"):
        lines.append("### Cooking Recipes")
        for r in data["cooking_recipes"]:
            lines.append(f"- **{r['name']}**: ingredients: {', '.join(r['ingredients'])} | "
                         f"buff: {r['buff']} ({r.get('buff_duration', '?')}) | "
                         f"source: {r.get('recipe_source', '?')}")
            if r.get("notes"):
                lines.append(f"  - Note: {r['notes']}")
        lines.append("")

    if data.get("fish"):
        lines.append("### Fish")
        for f in data["fish"]:
            parts = [f"**{f['name']}**"]
            if f.get("time_restriction"):
                parts.append(f"time: {f['time_restriction']}")
            if f.get("notes"):
                parts.append(f"note: {f['notes']}")
            lines.append("- " + " | ".join(parts))
        lines.append("")

    if data.get("zones"):
        lines.append("### Zones")
        for z in data["zones"]:
            if not isinstance(z, dict):
                continue
            lines.append(f"- **{z['name']}**: {z.get('faction_safety', '')} | PvP: {z.get('pvp_risk', '?')}")
            if z.get("notes"):
                lines.append(f"  - {z['notes']}")
        lines.append("")

    if data.get("known_fake_locations"):
        lines.append("### Known Fake Locations (do NOT exist in WoW Classic)")
        for fake in data["known_fake_locations"]:
            lines.append(f"- {fake}")
        lines.append("")

    if data.get("vendors"):
        lines.append("### Vendors")
        for v in data["vendors"]:
            sells = ", ".join(v.get("sells", []))
            lines.append(f"- **{v['name']}** ({v['location']}): {sells}")
        lines.append("")

    if data.get("items_and_clarifications"):
        lines.append("### Item Clarifications")
        for item in data["items_and_clarifications"]:
            lines.append(f"- **{item['name']}** ({item.get('type', '')}): {item.get('notes', '')}")
            if item.get("bonus"):
                lines.append(f"  - Bonus: {item['bonus']} for {item.get('duration', '?')}")
        lines.append("")

    if data.get("gold_estimates"):
        ge = data["gold_estimates"]
        lines.append("### Realistic Gold/Hour Estimates")
        if ge.get("notes"):
            lines.append(f"- {ge['notes']}")
        for k, v in ge.items():
            if isinstance(v, dict) and v.get("realistic_range"):
                lines.append(f"- {v.get('description', k)}: {v['realistic_range']}")
        lines.append("")

    if data.get("common_hallucinations"):
        lines.append("### Common LLM Hallucinations — These Claims Are WRONG")
        for h in data["common_hallucinations"]:
            lines.append(f"- WRONG: \"{h['wrong_claim']}\" → CORRECT: {h['correct']}")
        lines.append("")

    return "\n".join(lines)


def load_reference_data() -> str:
    """Load wow_reference.yaml and format it for the grader system prompt.
    Returns empty string (gracefully degraded) if file is missing."""
    ref_path = Path("wow_reference.yaml")
    if not ref_path.exists():
        print("  WARNING: wow_reference.yaml not found — grader will use its own knowledge.",
              file=sys.stderr)
        return ""
    data = yaml.safe_load(ref_path.read_text(encoding="utf-8"))
    return _format_reference_data(data)

GRADER_RUBRIC = """You will judge multiple LLM responses to the SAME user prompt.

# The original user prompt
{prompt}

# The responses (anonymized)
{responses_block}

# Your task
For EACH response, score it on these dimensions (1-10 each):
- Accuracy        — Is the WoW Classic info plausible and correct? (zone safety, fish types, cooking recipes, vendor prices)
- Strategy depth  — Does it actually maximize gold/hour with concrete numbers and reasoning?
- Creativity      — Did it add interesting structure / 'features' beyond the literal ask?
- Structure       — Is it well-organized, scannable, useful as a reference?
- Prompt fidelity — Did it respect the constraints (lvl 60 Alliance warrior, AFK-safe, 300/300)?

Then:
1. Produce a markdown table with one row per response: | Letter | Accuracy | Strategy | Creativity | Structure | Fidelity | Total | One-line verdict |
2. Rank the responses from best to worst.
3. Declare a winner and explain in 3-5 sentences WHY that one beat the others.
4. Call out any specific hallucinations or factual errors you spotted, by letter.

Be opinionated. No participation trophies."""


def parse_grade_totals(verdict: str) -> dict[str, float]:
    """Best-effort extraction of the per-letter Total score from the judge's
    markdown table. Returns {letter: total}. Degrades to {} if it can't parse."""
    totals: dict[str, float] = {}
    total_idx: int | None = None
    for line in verdict.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if total_idx is None:
            lower = [c.lower() for c in cells]
            if "total" in lower:
                total_idx = lower.index("total")
            continue
        if cells and re.fullmatch(r"[A-Z]", cells[0]) and total_idx < len(cells):
            m = re.search(r"\d+(?:\.\d+)?", cells[total_idx])
            if m:
                totals[cells[0]] = float(m.group())
    return totals


def build_efficiency_table(
    run_dir: Path,
    letters: list[str],
    entries: list[tuple[str, str]],
    totals: dict[str, float],
) -> str:
    """Raw-data table: score alongside time and token counts, no ratios."""
    rows = []
    for letter, (label, _body) in zip(letters, entries):
        meta = load_result_meta(run_dir, label)
        score = totals.get(letter)
        rows.append({
            "label": label,
            "score": score,
            "seconds": meta.get("seconds"),
            "output": meta.get("output_tokens"),
            "reasoning": meta.get("reasoning_tokens"),
            "total": meta.get("total_tokens"),
        })

    # Sort by score (desc) when we have it, otherwise keep label order.
    rows.sort(key=lambda r: (r["score"] is not None, r["score"] or 0), reverse=True)

    def cell(v) -> str:
        if v is None:
            return "—"
        if isinstance(v, float):
            return f"{v:g}"
        return f"{v:,}" if isinstance(v, int) else str(v)

    lines = [
        "",
        "---",
        "",
        "## Efficiency — raw data",
        "",
        "_Same score with fewer tokens or less time = more efficient. "
        "Reasoning tokens are internal thinking; '—' means the provider didn't report it._",
        "",
        "| Model | Total score | Time (s) | Output tok | Reasoning tok | Total tok |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['label']}` | {cell(r['score'])} | {cell(r['seconds'])} | "
            f"{cell(r['output'])} | {cell(r['reasoning'])} | {cell(r['total'])} |"
        )
    return "\n".join(lines)


async def grade_run(run_dir: Path, grader_provider: str = GRADER_PROVIDER, grader_model: str = GRADER_MODEL) -> str:
    entries = load_successful_results(run_dir)
    if not entries:
        raise RuntimeError(f"No successful result files in {run_dir} — nothing to grade.")

    letters = [chr(ord("A") + i) for i in range(len(entries))]
    blocks  = [f"## Response {letter}\n\n{body}\n" for letter, (_label, body) in zip(letters, entries)]
    responses_block = "\n---\n\n".join(blocks)

    grader_prompt = GRADER_RUBRIC.format(prompt=PROMPT, responses_block=responses_block)

    ref_data = load_reference_data()
    grader_system = GRADER_SYSTEM_TEMPLATE.format(reference_data=ref_data)

    print(f"Grading {len(entries)} response(s) with {grader_provider}/{grader_model}...")
    grader = LLMClient(provider=grader_provider, model=grader_model)
    grader.max_tokens = 8000
    verdict = await grader.call(grader_prompt, system=grader_system)

    key_lines = ["", "---", "", "## Key (revealed after grading)", ""]
    for letter, (label, _body) in zip(letters, entries):
        key_lines.append(f"- **{letter}** → `{label}`")

    totals = parse_grade_totals(verdict)
    efficiency = build_efficiency_table(run_dir, letters, entries, totals)
    return verdict + "\n" + "\n".join(key_lines) + "\n" + efficiency


# ── CLI ────────────────────────────────────────────────────────────────────

def parse_only(spec: str) -> list[tuple[str, str]]:
    pairs = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "/" not in chunk:
            raise SystemExit(f"--only expects provider/model, got '{chunk}'")
        provider, model = chunk.split("/", 1)
        pairs.append((provider.strip(), model.strip()))
    return pairs


async def main():
    parser = argparse.ArgumentParser(
        description="HåkonBench — multi-model prompt benchmark + blind grader.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--only",         help="Run only these contestants (comma-separated provider/model).")
    parser.add_argument("--run",          help="Target a specific run folder name (e.g. 2026-05-24_143022). Defaults to latest.")
    parser.add_argument("--regrade",      action="store_true", help="Skip API calls. Re-grade what's on disk in the target run folder.")
    parser.add_argument("--no-grade",     action="store_true", help="Run models but skip grading.")
    parser.add_argument("--list",         action="store_true", help="List all run folders and exit.")
    parser.add_argument("--grader-model", default=None,
                        help="Override grader model as provider/model (e.g. anthropic/claude-opus-4-7). "
                             f"Default: {GRADER_PROVIDER}/{GRADER_MODEL}")
    parser.add_argument("--effort", choices=TIERS, default=DEFAULT_EFFORT,
                        help="Reasoning/thinking + token budget tier, translated to each provider's "
                             "named effort level (Claude output_config.effort + adaptive thinking, "
                             "OpenAI reasoning.effort, Gemini thinking_level, Grok reasoning_effort). "
                             f"See PROVIDER_EFFORT. Default: {DEFAULT_EFFORT}.")
    parser.add_argument("--timeout", type=float, default=None, metavar="SECONDS",
                        help="Per-model wall-clock limit. A model that doesn't answer in time is "
                             "marked FAILED and the run continues + grades the rest. Default: no limit.")
    args = parser.parse_args()

    if args.list:
        list_runs()
        return

    BASE_RESULTS_DIR.mkdir(exist_ok=True)

    # A full run (no --only, no --regrade) → new dated folder.
    # --only / --regrade → use latest (or --run) so results slot in.
    creating_new = not args.only and not args.regrade
    run_dir = resolve_run_dir(args.run, creating_new=creating_new)

    if args.regrade:
        if args.only:
            print("Note: --only is ignored when --regrade is set.", file=sys.stderr)
        print(f"Re-grading run: {run_dir.name}\n")
    else:
        to_run = parse_only(args.only) if args.only else CONTESTANTS
        verb   = "Adding to" if args.only else "Starting new run in"
        print(f"HåkonBench — {verb} {run_dir.name}  (effort: {args.effort})\n")
        for provider, model in to_run:
            _, knob = resolve_effort(provider, model, args.effort)
            print(f"  • {provider:10s} {model:32s} → {knob}")
        if args.timeout:
            print(f"  (per-model timeout: {args.timeout:.0f}s)")
        print(f"\nRunning {len(to_run)} model(s) in parallel — saving each as it finishes:\n")

        # Stream results: save + print the moment each model returns, so partial
        # results survive a failure/Ctrl-C, and a heartbeat shows what's still
        # running (so a long --effort max run is visibly alive, not hung).
        tasks = {
            asyncio.create_task(run_contestant(p, m, args.effort, args.timeout)): slug(p, m)
            for p, m in to_run
        }
        t0 = time.perf_counter()
        heartbeat = 20.0
        done_count = 0
        pending = set(tasks)
        while pending:
            done, pending = await asyncio.wait(
                pending, timeout=heartbeat, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                label, response, secs, err, usage = task.result()
                msg = save_result(run_dir, label, response, secs, err, usage, effort=args.effort)
                done_count += 1
                print(f"[{done_count}/{len(tasks)}]{msg}")
            if pending and not done:
                still = ", ".join(sorted(tasks[t] for t in pending))
                print(f"  … {len(pending)} still running after {time.perf_counter() - t0:.0f}s: {still}")

    if args.no_grade:
        print(f"\n--no-grade set; skipping grading. Results in: {run_dir}")
        return

    g_provider, g_model = GRADER_PROVIDER, GRADER_MODEL
    if args.grader_model:
        if "/" not in args.grader_model:
            raise SystemExit(f"--grader-model expects provider/model, got '{args.grader_model}'")
        g_provider, g_model = args.grader_model.split("/", 1)

    verdict    = await grade_run(run_dir, grader_provider=g_provider, grader_model=g_model)
    grade_path = run_dir / "_grades.md"
    grade_path.write_text(verdict, encoding="utf-8")
    print(f"\nGrades written to {grade_path}")
    print("\n" + "=" * 60)
    print(verdict)


if __name__ == "__main__":
    asyncio.run(main())
