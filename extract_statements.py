#!/usr/bin/env python3
"""extract_statements.py — mine factual claims out of benchmark responses.

Reads every agent response under results/<timestamp>/*.md, asks a cheap model
(OpenAI gpt-5.4-mini by default) to pull out the WoW Classic fishing/cooking
facts each guide asserts, and merges them into wow_reference.yaml as NEW,
UNVERIFIED entries (verified: false).

Unverified entries are hidden from the grader (see _format_reference_data in
haakonbench.py) and are picked up later by factcheck_reference.py, which checks
each one against the web and flips verified -> true/false. So a noisy extraction
never pollutes the grader — it just gives the fact-checker more to chew on.

Dedup is by normalized name within each section. Existing entries are never
overwritten (especially not verified: true ones).

Usage:
    python extract_statements.py                  # extract from all results, merge
    python extract_statements.py --dry-run        # show what would be added, write nothing
    python extract_statements.py --limit 3        # only the first 3 response files (cheap test)
    python extract_statements.py --model gpt-5.5  # different extractor model
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from tqdm.asyncio import tqdm as tqdm_async

from llm_client import LLMClient
from reference_io import (
    LIST_SECTIONS,
    existing_names,
    load_reference,
    normalize_name,
    parse_json_obj,
    save_reference,
    to_quoted,
)

BODY_SEP = "\n<!-- BEGIN RESPONSE -->\n"

# Field shapes the extractor should follow, mirroring wow_reference.yaml.
SCHEMA_HINT = """\
- cooking_recipes: {name, ingredients: ["Nx Item Name", ...], buff, buff_duration, skill_required, recipe_source, notes?}
- fish: {name, time_restriction?, zones: [...], fishing_skill_required?, notes?}
- vendors: {name, location, sells: ["Recipe: ...", ...], notes?}
- zones: {name, faction_safety, pvp_risk, notable_fish?: [...], notable_spots?: [...], fishing_skill_effective?, access_notes?}
- items_and_clarifications: {name, type, bonus?, duration?, source?, notes?}"""

EXTRACT_SYSTEM = f"""You extract verifiable World of Warcraft Classic (patch 1.12) \
fishing and cooking facts from a guide, for a fact-checking database.

Output ONLY a single JSON object. Keys are any of these sections; each maps to a \
list of entries. Omit sections you have nothing for.

Sections and their fields:
{SCHEMA_HINT}

Rules:
- Extract only concrete, checkable claims the text actually makes (recipe \
ingredients, buff stats, skill requirements, vendor names/locations, fish zones \
and time/season restrictions, item bonuses).
- One entry per distinct named thing. Use the in-game name as `name`.
- Do NOT invent fields you are unsure about — omit them. Do NOT add commentary.
- Skip gold/hour numbers, opinions, and general strategy — only factual entries.
- Return strictly valid JSON, no trailing commas, no markdown outside a single \
```json code block."""



def gather_response_files(results_dir: Path, limit: int | None) -> list[Path]:
    files = sorted(
        p for p in results_dir.glob("*/*.md") if not p.name.startswith("_")
    )
    if limit is not None:
        files = files[:limit]
    return files


def read_body(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    if "**FAILED" in text[:400]:
        return None
    if BODY_SEP in text:
        return text.split(BODY_SEP, 1)[1].strip()
    if "\n---\n\n" in text:  # older format
        return text.split("\n---\n\n", 1)[1].strip()
    return None


async def extract_one(client: LLMClient, sem: asyncio.Semaphore, path: Path, body: str):
    prompt = (
        f"Guide source: {path.parent.name}/{path.name}\n\n"
        f"--- GUIDE TEXT ---\n{body}\n--- END GUIDE TEXT ---"
    )
    async with sem:
        try:
            reply = await client.call(prompt, system=EXTRACT_SYSTEM)
        except Exception as e:  # noqa: BLE001 — one bad file shouldn't kill the run
            return path, None, repr(e)
    return path, parse_json_obj(reply), None


def known_fake_names(data) -> set[str]:
    """Normalized place names from known_fake_locations, so we never re-add a
    hallucinated location the reference file already disowns. Entries look like
    'Lake Shire (Ashenvale) — does not exist' → we key on 'lake shire'."""
    names: set[str] = set()
    for raw in data.get("known_fake_locations") or []:
        head = re.split(r"[(—]|\s-\s", str(raw), 1)[0]
        if head.strip():
            names.add(normalize_name(head))
    return names


def merge_entries(data, extracted: dict, stats: dict, fake_names: set[str]) -> int:
    """Merge one file's extraction into `data`. Returns count of new entries added.

    Cheap guards drop the obvious garbage a small extractor model produces, so the
    fact-checker isn't paid to verify it:
    - locations the reference already lists as fake (known_fake_locations)
    - placeholder/garbage vendor names ('Vendor', 'Recipe: X vendor', ...)
    - cooked dishes mis-filed into items_and_clarifications (they belong in, and
      usually duplicate, cooking_recipes)
    """
    added = 0
    for section in LIST_SECTIONS:
        items = extracted.get(section)
        if not isinstance(items, list):
            continue
        if data.get(section) is None:
            data[section] = []
        seen = existing_names(data, section)
        recipe_names = existing_names(data, "cooking_recipes")
        for entry in items:
            if not isinstance(entry, dict) or not entry.get("name"):
                continue
            key = normalize_name(entry["name"])

            if key in fake_names:
                stats["skipped_fake"] += 1
                continue
            if section == "vendors" and (key in {"vendor", "unspecified", ""}
                                         or key.startswith("recipe:")):
                stats["skipped_junk"] += 1
                continue
            if section == "items_and_clarifications" and (
                "cook" in normalize_name(entry.get("type", "")) or key in recipe_names):
                stats["skipped_food_dupe"] += 1
                continue

            if key in seen:
                stats["duplicates"] += 1
                continue
            new_entry = to_quoted({k: v for k, v in entry.items() if v not in (None, "", [])})
            new_entry["verified"] = False  # pending fact-check; hidden from grader
            data[section].append(new_entry)
            seen.add(key)
            stats.setdefault("by_section", {}).setdefault(section, 0)
            stats["by_section"][section] += 1
            added += 1
    return added


async def main() -> int:
    ap = argparse.ArgumentParser(description="Extract WoW Classic facts from benchmark responses.")
    ap.add_argument("--results-dir", default="results", type=Path)
    ap.add_argument("--limit", type=int, default=None, help="only process the first N response files")
    ap.add_argument("--dry-run", action="store_true", help="print what would be added, write nothing")
    ap.add_argument("--provider", default="openai")
    ap.add_argument("--model", default="gpt-5.4-mini")
    ap.add_argument("--effort", default="low", help="reasoning effort for the extractor")
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()

    load_dotenv()

    files = gather_response_files(args.results_dir, args.limit)
    if not files:
        print(f"No response files found under {args.results_dir}/*/*.md", file=sys.stderr)
        return 1

    pairs = [(p, body) for p in files if (body := read_body(p))]
    print(f"Extracting from {len(pairs)} response file(s) with {args.provider}/{args.model} "
          f"(effort={args.effort})...")

    client = LLMClient(provider=args.provider, model=args.model)
    client.reasoning_effort = args.effort
    sem = asyncio.Semaphore(args.workers)

    tasks = [extract_one(client, sem, p, body) for p, body in pairs]
    results = await tqdm_async.gather(*tasks, desc="Extracting")

    data = load_reference()
    fake_names = known_fake_names(data)
    stats = {"duplicates": 0, "skipped_fake": 0, "skipped_junk": 0,
             "skipped_food_dupe": 0, "by_section": {}}
    failures = []
    for path, extracted, err in results:
        if err or extracted is None:
            failures.append((path, err or "unparseable JSON"))
            continue
        merge_entries(data, extracted, stats, fake_names)

    total_added = sum(stats["by_section"].values())
    print("\n=== Extraction summary ===")
    for section, n in sorted(stats["by_section"].items()):
        print(f"  {section:24s} +{n}")
    print(f"  {'(duplicate names)':24s} {stats['duplicates']}")
    print(f"  {'(known fake locations)':24s} {stats['skipped_fake']}")
    print(f"  {'(junk vendor names)':24s} {stats['skipped_junk']}")
    print(f"  {'(cooked-food dupes)':24s} {stats['skipped_food_dupe']}")
    print(f"  {'TOTAL new entries':24s} {total_added}")
    if failures:
        print(f"\n  {len(failures)} file(s) failed to extract:")
        for path, err in failures:
            print(f"    - {path.parent.name}/{path.name}: {err}")

    if total_added == 0:
        print("\nNothing new to add.")
        return 0
    if args.dry_run:
        print("\n--dry-run: wow_reference.yaml NOT modified.")
        return 0

    save_reference(data)
    print(f"\nWrote {total_added} new (verified: false) entries to wow_reference.yaml.")
    print("Next: run `python factcheck_reference.py` to verify them against the web.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
