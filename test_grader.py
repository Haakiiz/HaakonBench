"""
test_grader.py — Valider at graderen evaluerer WoW Classic fishing-fakta
korrekt når den har tilgang til referansedata.

Mål: >= 95% korrekt på alle påstander i test_claims.yaml

Bruk:
    python test_grader.py
    python test_grader.py --model claude-opus-4-7
    python test_grader.py --model claude-opus-4-7 --provider anthropic
    python test_grader.py --verbose
    python test_grader.py --threshold 0.90
"""

import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

import yaml

from llm_client import LLMClient

HERE = Path(__file__).resolve().parent

EVAL_SYSTEM_TEMPLATE = """\
You are a WoW Classic (patch 1.12) fact-checker evaluating whether a claim is true or false.

You have been given authoritative reference data below. Use ONLY this reference data to judge \
whether claims are correct or incorrect. Do NOT rely on your own knowledge — it may be wrong \
for niche game data.

Rules:
- If a claim is covered by the reference data and matches it → TRUE
- If a claim directly contradicts the reference data → FALSE
- If a claim is incomplete but not wrong (e.g. states one buff but omits another) → TRUE
- If a claim cannot be verified from the reference data → TRUE (give benefit of the doubt)
- If a location, recipe, or item is listed under known_fake_locations or common_hallucinations as fake → FALSE

Respond with EXACTLY this format and nothing else:
VERDICT: TRUE
or
VERDICT: FALSE

{reference_data}"""


def format_reference_data(data: dict) -> str:
    lines = ["## Verified WoW Classic Fishing Reference Data", ""]

    if data.get("cooking_recipes"):
        lines.append("### Cooking Recipes")
        for r in data["cooking_recipes"]:
            lines.append(f"- **{r['name']}**")
            lines.append(f"  - Ingredients: {', '.join(r['ingredients'])}")
            lines.append(f"  - Buff: {r['buff']} ({r.get('buff_duration', '?')})")
            lines.append(f"  - Skill required: {r.get('skill_required', '?')}")
            lines.append(f"  - Source: {r.get('recipe_source', '?')}")
            if r.get("notes"):
                lines.append(f"  - Notes: {r['notes']}")
        lines.append("")

    if data.get("fish"):
        lines.append("### Fish")
        for f in data["fish"]:
            lines.append(f"- **{f['name']}**")
            if f.get("time_restriction"):
                lines.append(f"  - Time: {f['time_restriction']}")
            if f.get("zones"):
                lines.append(f"  - Zones: {', '.join(f['zones'])}")
            if f.get("notes"):
                lines.append(f"  - Notes: {f['notes']}")
        lines.append("")

    if data.get("zones"):
        lines.append("### Zones")
        for z in data["zones"]:
            if not isinstance(z, dict):
                continue
            lines.append(f"- **{z['name']}**: {z.get('faction_safety', '')} — PvP risk: {z.get('pvp_risk', 'unknown')}")
            if z.get("notes"):
                lines.append(f"  - {z['notes']}")
        # Fake locations
        for z in data["zones"]:
            if isinstance(z, dict) and z.get("known_fake_locations"):
                lines.append("- **Known fake locations (do not exist in Classic):**")
                for fake in z["known_fake_locations"]:
                    lines.append(f"  - {fake}")
        lines.append("")

    if data.get("vendors"):
        lines.append("### Vendors")
        for v in data["vendors"]:
            sells = ", ".join(v.get("sells", []))
            lines.append(f"- **{v['name']}** ({v['location']}): sells {sells}")
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
        lines.append("### Gold/Hour Estimates (realistic)")
        lines.append(f"- General note: {ge.get('notes', '')}")
        for k, v in ge.items():
            if isinstance(v, dict) and v.get("realistic_range"):
                lines.append(f"- {v['description']}: {v['realistic_range']}")
        lines.append("")

    if data.get("common_hallucinations"):
        lines.append("### Common LLM Hallucinations (these claims are WRONG)")
        for h in data["common_hallucinations"]:
            lines.append(f"- WRONG: \"{h['wrong_claim']}\" → CORRECT: {h['correct']}")
        lines.append("")

    return "\n".join(lines)


def load_reference_data() -> tuple[dict, str]:
    ref_path = HERE / "wow_reference.yaml"
    if not ref_path.exists():
        print("WARNING: wow_reference.yaml not found. Grader will work without reference data.", file=sys.stderr)
        return {}, ""
    raw = yaml.safe_load(ref_path.read_text(encoding="utf-8"))
    return raw, format_reference_data(raw)


def load_claims() -> list[dict]:
    claims_path = HERE / "test_claims.yaml"
    if not claims_path.exists():
        raise SystemExit(f"test_claims.yaml not found at {claims_path}")
    data = yaml.safe_load(claims_path.read_text(encoding="utf-8"))
    return data["claims"]


def parse_verdict(response: str) -> bool | None:
    upper = response.upper()
    if "VERDICT:" in upper:
        after = upper.split("VERDICT:")[-1].strip()
        if after.startswith("TRUE"):
            return True
        if after.startswith("FALSE"):
            return False
    # Fallback: look for standalone TRUE/FALSE
    if upper.strip() == "TRUE":
        return True
    if upper.strip() == "FALSE":
        return False
    return None


async def evaluate_claim(client: LLMClient, system_prompt: str, claim: dict) -> dict:
    response = await client.call(claim["text"], system=system_prompt)
    verdict = parse_verdict(response)
    expected = claim["expected"]
    return {
        "id": claim.get("id", claim["text"][:50]),
        "text": claim["text"],
        "category": claim.get("category", "uncategorized"),
        "expected": expected,
        "actual": verdict,
        "raw_response": response.strip(),
        "correct": verdict == expected,
    }


async def run_all(client: LLMClient, system_prompt: str, claims: list[dict], verbose: bool) -> list[dict]:
    semaphore = asyncio.Semaphore(3)

    async def _limited(claim: dict) -> dict:
        async with semaphore:
            return await evaluate_claim(client, system_prompt, claim)

    tasks = [_limited(c) for c in claims]
    results = []
    for coro in asyncio.as_completed(tasks):
        result = await coro
        results.append(result)
        if verbose:
            status = "PASS" if result["correct"] else "FAIL"
            verdict_str = str(result["actual"]).upper() if result["actual"] is not None else "PARSE_ERROR"
            print(f"  [{status}] [{result['category']}] {result['text'][:70]}")
            if not result["correct"]:
                print(f"         expected={result['expected']}, got={verdict_str}")
                print(f"         raw: {result['raw_response'][:100]}")
    # Sort by category for consistent output
    results.sort(key=lambda r: (r["category"], r["text"]))
    return results


def print_report(results: list[dict], threshold: float) -> bool:
    total = len(results)
    passed = sum(1 for r in results if r["correct"])
    accuracy = passed / total if total > 0 else 0.0

    # Per-category breakdown
    by_category: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_category[r["category"]].append(r)

    print("\n" + "=" * 60)
    print("GRADER ACCURACY TEST RESULTS")
    print("=" * 60)
    print(f"\nOverall: {passed}/{total} correct ({accuracy:.1%})\n")

    print("Per-category breakdown:")
    for cat in sorted(by_category.keys()):
        items = by_category[cat]
        cat_passed = sum(1 for r in items if r["correct"])
        print(f"  {cat:<25} {cat_passed}/{len(items)}")

    failures = [r for r in results if not r["correct"]]
    if failures:
        print(f"\nFailed claims ({len(failures)}):")
        for r in failures:
            verdict_str = str(r["actual"]).upper() if r["actual"] is not None else "PARSE_ERROR"
            print(f"  [{r['category']}] expected={r['expected']}, got={verdict_str}")
            print(f"    Claim: {r['text']}")

    print("\n" + "=" * 60)
    if accuracy >= threshold:
        print(f"PASSED — {accuracy:.1%} >= threshold {threshold:.0%}")
        return True
    else:
        print(f"FAILED — {accuracy:.1%} < threshold {threshold:.0%}")
        return False


async def main():
    parser = argparse.ArgumentParser(
        description="Validate grader accuracy on WoW Classic fishing facts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--model",     default="claude-sonnet-4-6", help="Model to test (default: claude-sonnet-4-6)")
    parser.add_argument("--provider",  default="anthropic",         help="Provider (default: anthropic)")
    parser.add_argument("--threshold", type=float, default=0.95,    help="Minimum accuracy to pass (default: 0.95)")
    parser.add_argument("--verbose",   action="store_true",         help="Print each claim result as it completes")
    args = parser.parse_args()

    print(f"HaakonBench — Grader Accuracy Test")
    print(f"Model   : {args.provider}/{args.model}")
    print(f"Target  : >= {args.threshold:.0%} accuracy")

    _, ref_text = load_reference_data()
    claims = load_claims()
    print(f"Claims  : {len(claims)} loaded from test_claims.yaml\n")

    system_prompt = EVAL_SYSTEM_TEMPLATE.format(reference_data=ref_text)

    client = LLMClient(provider=args.provider, model=args.model)
    client.max_tokens = 20  # Only need "VERDICT: TRUE" or "VERDICT: FALSE"

    results = await run_all(client, system_prompt, claims, args.verbose)
    passed = print_report(results, args.threshold)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
