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

from llm_client import LLMClient

# ── Contestants ────────────────────────────────────────────────────────────
CONTESTANTS: list[tuple[str, str]] = [
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


async def run_contestant(provider: str, model: str) -> tuple[str, str, float, str | None]:
    label = slug(provider, model)
    t0 = time.perf_counter()
    try:
        client = LLMClient(provider=provider, model=model)
        client.max_tokens = MAX_TOKENS_PER_CALL
        response = await client.call(PROMPT)
        return label, response, time.perf_counter() - t0, None
    except Exception as e:
        return label, "", time.perf_counter() - t0, f"{type(e).__name__}: {e}"


def save_result(run_dir: Path, label: str, response: str, secs: float, err: str | None) -> None:
    path = run_dir / f"{label}.md"
    if err:
        path.write_text(
            f"# {label}\n\n**FAILED after {secs:.1f}s**\n\n```\n{err}\n```\n",
            encoding="utf-8",
        )
        print(f"  ✗ {label}  ({secs:.1f}s)  — {err}")
    else:
        path.write_text(
            f"# {label}\n\n_Generated in {secs:.1f}s_\n{BODY_SEP}\n{response}\n",
            encoding="utf-8",
        )
        print(f"  ✓ {label}  ({secs:.1f}s, {len(response):,} chars)")


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


# ── Grading ────────────────────────────────────────────────────────────────

GRADER_SYSTEM = (
    "You are an expert evaluator for LLM benchmarks. You grade responses blind — "
    "the identities of the models are hidden behind letters (A, B, C, ...). Be "
    "rigorous, specific, and honest. Reward accuracy, depth, creativity, structure, "
    "and usefulness. Penalize hallucinations (especially WoW Classic facts that look "
    "made up), generic filler, and prompt-ignoring."
)

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


async def grade_run(run_dir: Path) -> str:
    entries = load_successful_results(run_dir)
    if not entries:
        raise RuntimeError(f"No successful result files in {run_dir} — nothing to grade.")

    letters = [chr(ord("A") + i) for i in range(len(entries))]
    blocks  = [f"## Response {letter}\n\n{body}\n" for letter, (_label, body) in zip(letters, entries)]
    responses_block = "\n---\n\n".join(blocks)

    grader_prompt = GRADER_RUBRIC.format(prompt=PROMPT, responses_block=responses_block)

    print(f"Grading {len(entries)} response(s) with {GRADER_PROVIDER}/{GRADER_MODEL}...")
    grader = LLMClient(provider=GRADER_PROVIDER, model=GRADER_MODEL)
    grader.max_tokens = 8000
    verdict = await grader.call(grader_prompt, system=GRADER_SYSTEM)

    key_lines = ["", "---", "", "## Key (revealed after grading)", ""]
    for letter, (label, _body) in zip(letters, entries):
        key_lines.append(f"- **{letter}** → `{label}`")
    return verdict + "\n" + "\n".join(key_lines)


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
    parser.add_argument("--only",    help="Run only these contestants (comma-separated provider/model).")
    parser.add_argument("--run",     help="Target a specific run folder name (e.g. 2026-05-24_143022). Defaults to latest.")
    parser.add_argument("--regrade", action="store_true", help="Skip API calls. Re-grade what's on disk in the target run folder.")
    parser.add_argument("--no-grade",action="store_true", help="Run models but skip grading.")
    parser.add_argument("--list",    action="store_true", help="List all run folders and exit.")
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
        print(f"HåkonBench — {verb} {run_dir.name}\n")
        for provider, model in to_run:
            print(f"  • {provider:10s} {model}")
        print()

        tasks   = [run_contestant(p, m) for p, m in to_run]
        results = await asyncio.gather(*tasks)
        for label, response, secs, err in results:
            save_result(run_dir, label, response, secs, err)

    if args.no_grade:
        print(f"\n--no-grade set; skipping grading. Results in: {run_dir}")
        return

    verdict    = await grade_run(run_dir)
    grade_path = run_dir / "_grades.md"
    grade_path.write_text(verdict, encoding="utf-8")
    print(f"\nGrades written to {grade_path}")
    print("\n" + "=" * 60)
    print(verdict)


if __name__ == "__main__":
    asyncio.run(main())
