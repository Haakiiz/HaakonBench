#!/usr/bin/env python3
"""factcheck_reference.py — verify wow_reference.yaml entries against the web.

For every entry that is not yet `verified: true`, ask Gemini (gemini-3.1-flash-lite
by default) WITH Google Search grounding to check each field against WoW Classic
sources (Wowhead Classic preferred). The verdict is written back into the same
entry, non-destructively:

    verified: true|false
    verified_date: "YYYY-MM-DD"
    source_url: "https://..."      # from the grounding metadata
    corrections: null | [ "...", ... ]

Original fields are never overwritten — only these four are added/updated. Entries
already marked `verified: true` are skipped, so the script is idempotent and can be
re-run as new unverified entries accumulate.

Design notes:
- Gemini's google_search tool is incompatible with structured-output (response
  schema), so we ask for a fenced JSON block in free text and parse it tolerantly.
- Verification runs with bounded concurrency + a progress bar; the document is
  saved after each entry so a crash never loses progress.
- When the model contradicts a previously-trusted (hand-curated) entry, we print a
  loud REVIEW line — a small flash model shouldn't silently bury a known-good fact.

Usage:
    python factcheck_reference.py                 # verify all pending entries
    python factcheck_reference.py --dry-run       # verify, print verdicts, write nothing
    python factcheck_reference.py --limit 5       # only the first 5 pending entries
    python factcheck_reference.py --include-verified   # re-check even verified: true
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import re
import sys

from dotenv import load_dotenv
from tqdm.asyncio import tqdm as tqdm_async

from reference_io import LIST_SECTIONS, load_reference, save_reference

META_KEYS = {"verified", "verified_date", "source_url", "corrections"}
MODEL_CANDIDATES = ["gemini-3.1-flash-lite", "gemini-3.1-flash-lite-preview"]

VERIFY_SYSTEM = """You are a meticulous World of Warcraft Classic (patch 1.12 / \
Era) fact-checker. Use Google Search to verify claims against reliable WoW Classic \
sources — prefer Wowhead Classic (wowhead.com), then Wowpedia/official sources. \
Modern Retail or non-Classic data does not count.

You will be given one database entry. Check every field for factual accuracy for \
WoW Classic specifically. Then respond with a short explanation followed by a \
single fenced JSON block:

```json
{"verified": true or false,
 "corrections": null or ["<field>: should be X, not Y", ...],
 "confidence": "high" | "medium" | "low"}
```

- verified=true only if every checkable field is correct for WoW Classic.
- If anything is wrong, set verified=false and list each problem in corrections.
- If you genuinely cannot find a source, set verified=false, confidence="low", and \
say so in corrections. Do not guess."""


def parse_json_obj(text: str) -> dict | None:
    if not text:
        return None
    # 1. Prefer a fenced code block: find the { right after the opening fence
    #    and use raw_decode so the JSON parser determines the object boundary
    #    (avoids regex back-tracking surprises with nested/trailing braces).
    m = re.search(r"```(?:json)?\s*", text, re.IGNORECASE)
    if m:
        j = text.find("{", m.end())
        if j != -1:
            try:
                obj, _ = json.JSONDecoder().raw_decode(text, j)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
    # 2. Fallback: scan forward through every { and return the first valid dict.
    pos = 0
    while True:
        idx = text.find("{", pos)
        if idx == -1:
            return None
        try:
            obj, _ = json.JSONDecoder().raw_decode(text, idx)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        pos = idx + 1


def entry_to_prompt(section: str, entry: dict) -> str:
    fields = {k: v for k, v in entry.items() if k not in META_KEYS}
    body = json.dumps(fields, ensure_ascii=False, indent=2)
    return f"Database section: {section}\nEntry to verify:\n{body}"


def first_source_url(response) -> str | None:
    """Pull the first grounding source URL out of a Gemini response.
    Note: these are vertexaisearch redirect URLs, not raw wowhead links."""
    try:
        cand = response.candidates[0]
        gm = getattr(cand, "grounding_metadata", None)
        for chunk in getattr(gm, "grounding_chunks", None) or []:
            web = getattr(chunk, "web", None)
            uri = getattr(web, "uri", None)
            if uri:
                return uri
    except (AttributeError, IndexError, TypeError):
        pass
    return None


def response_text(response) -> str:
    try:
        return response.text or ""
    except (AttributeError, ValueError):
        # blocked / no candidate
        parts = []
        for cand in getattr(response, "candidates", None) or []:
            for part in getattr(getattr(cand, "content", None), "parts", None) or []:
                if getattr(part, "text", None):
                    parts.append(part.text)
        return "".join(parts)


async def resolve_model(client, tools_config) -> str:
    """Return the first candidate model id that the API accepts."""
    for model in MODEL_CANDIDATES:
        try:
            await client.aio.models.generate_content(model=model, contents="ping")
            return model
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            if "not found" in msg or "404" in msg or "does not exist" in msg or "unsupported" in msg:
                continue
            # Some other error (auth, quota) — surface it rather than masking.
            raise
    raise RuntimeError(f"None of the candidate models are available: {MODEL_CANDIDATES}")


async def verify_one(client, model, types_mod, sem, ref):
    """ref = (section, entry, was_trusted). Returns (ref, verdict, source_url, error)."""
    section, entry, _ = ref
    tool = types_mod.Tool(google_search=types_mod.GoogleSearch())
    config = types_mod.GenerateContentConfig(
        tools=[tool],
        temperature=0.0,
        system_instruction=VERIFY_SYSTEM,
    )
    async with sem:
        try:
            resp = await client.aio.models.generate_content(
                model=model,
                contents=entry_to_prompt(section, entry),
                config=config,
            )
        except Exception as e:  # noqa: BLE001
            return ref, None, None, repr(e)
    verdict = parse_json_obj(response_text(resp))
    return ref, verdict, first_source_url(resp), None


def collect_targets(data, include_verified: bool) -> list[tuple[str, dict, bool]]:
    targets = []
    for section in LIST_SECTIONS:
        for entry in data.get(section) or []:
            if not isinstance(entry, dict) or not entry.get("name"):
                continue
            already = entry.get("verified") is True
            if already and not include_verified:
                continue
            was_trusted = "verified" not in entry  # hand-curated, no prior verdict
            targets.append((section, entry, was_trusted))
    return targets


def apply_verdict(entry: dict, verdict: dict | None, source_url: str | None,
                  error: str | None, today: str) -> tuple[bool, list[str] | None]:
    """Mutate entry in place. Returns (verified_bool, corrections)."""
    if error is not None or verdict is None:
        verified = False
        corrections = [error or "could not parse verifier response"]
    else:
        verified = bool(verdict.get("verified"))
        corr = verdict.get("corrections")
        corrections = corr if (corr and corr != "null") else None
    entry["verified"] = verified
    entry["verified_date"] = today
    if source_url:
        entry["source_url"] = source_url
    entry["corrections"] = corrections
    return verified, corrections


async def main() -> int:
    ap = argparse.ArgumentParser(description="Fact-check wow_reference.yaml against the web via Gemini + Google Search.")
    ap.add_argument("--limit", type=int, default=None, help="only verify the first N pending entries")
    ap.add_argument("--dry-run", action="store_true", help="verify and print verdicts, write nothing")
    ap.add_argument("--include-verified", action="store_true", help="re-check entries already verified: true")
    ap.add_argument("--model", default=None, help="override the Gemini model id")
    ap.add_argument("--concurrency", type=int, default=5)
    args = ap.parse_args()

    load_dotenv()
    if not os.environ.get("GOOGLE_API_KEY"):
        print("GOOGLE_API_KEY not set (.env).", file=sys.stderr)
        return 1

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("google-genai not installed. Run: pip install -r requirements.txt", file=sys.stderr)
        return 1

    data = load_reference()
    targets = collect_targets(data, args.include_verified)
    if args.limit:
        targets = targets[: args.limit]
    if not targets:
        print("No pending entries to verify. (All entries are already verified: true.)")
        return 0

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    model = args.model or await resolve_model(client, types)
    print(f"Verifying {len(targets)} entry(ies) with {model} + Google Search "
          f"(concurrency={args.concurrency})...")

    sem = asyncio.Semaphore(args.concurrency)
    tasks = [asyncio.create_task(verify_one(client, model, types, sem, ref)) for ref in targets]

    today = dt.date.today().isoformat()
    counts = {"verified": 0, "failed": 0, "errors": 0, "review": 0}
    for coro in tqdm_async.as_completed(tasks, total=len(tasks), desc="Fact-checking"):
        ref, verdict, source_url, error = await coro
        section, entry, was_trusted = ref
        verified, corrections = apply_verdict(entry, verdict, source_url, error, today)
        if error is not None or verdict is None:
            counts["errors"] += 1
        elif verified:
            counts["verified"] += 1
        else:
            counts["failed"] += 1
        if was_trusted and not verified:
            counts["review"] += 1
            tqdm_async.write(
                f"  REVIEW: previously-trusted '{entry['name']}' ({section}) now "
                f"verified=false → it will be HIDDEN from the grader. "
                f"corrections={corrections}"
            )
        if not args.dry_run:
            save_reference(data)  # incremental, crash-safe

    print("\n=== Fact-check summary ===")
    print(f"  verified true : {counts['verified']}")
    print(f"  verified false: {counts['failed']}")
    print(f"  errors        : {counts['errors']}")
    print(f"  needs review  : {counts['review']} (was trusted, now false)")
    if args.dry_run:
        print("\n--dry-run: wow_reference.yaml NOT modified.")
    else:
        print("\nwow_reference.yaml updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
