"""Shared round-trip helpers for the wow_reference.yaml fact-check pipeline.

Both extract_statements.py (writes new, unverified entries) and
factcheck_reference.py (annotates entries with verification results) read and
write wow_reference.yaml through here.

We use ruamel.yaml in round-trip mode so the hand-curated Norwegian comments and
the file's structure survive read/modify/write cycles — plain pyyaml would strip
every comment and reflow the block scalars.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString as DQ

REFERENCE_PATH = Path("wow_reference.yaml")

# The only top-level sections that are lists of named entries. extract_statements
# writes into these and factcheck_reference iterates over them. The other keys
# (gold_estimates, common_hallucinations, known_fake_locations) have different
# shapes and are intentionally left untouched by the pipeline.
LIST_SECTIONS = ["cooking_recipes", "fish", "vendors", "zones", "items_and_clarifications"]


def _yaml() -> YAML:
    y = YAML()  # round-trip mode (default) — preserves comments
    y.preserve_quotes = True
    y.width = 4096  # never wrap long lines or block scalars
    y.indent(mapping=2, sequence=4, offset=2)  # matches the existing file
    return y


def load_reference(path: Path = REFERENCE_PATH):
    """Load wow_reference.yaml preserving comments/structure."""
    with Path(path).open(encoding="utf-8") as f:
        return _yaml().load(f)


def save_reference(data, path: Path = REFERENCE_PATH) -> None:
    """Write the round-trip document back, comments intact.

    Two post-processing passes on the dumped string fix ruamel spacing issues:
    1. Remove blank lines ruamel inserts *within* an entry when new keys are
       appended after a key that originally had a trailing blank line
       (factcheck_reference symptom: verified: appears after a blank line).
    2. Ensure exactly one blank line before each named list entry so entries
       from extract_statements look like the hand-curated ones.
    """
    buf = io.StringIO()
    _yaml().dump(data, buf)
    text = buf.getvalue()
    # 4-space indent = key inside an entry. Remove blank lines between them.
    # Pattern requires `word:` so it only matches YAML keys, not block-scalar
    # content that might happen to start with a letter at the same indent.
    text = re.sub(r"\n\n(    [a-z]\w*\s*:)", r"\n\1", text)
    # Add a blank line before any `  - name:` that doesn't already have one.
    text = re.sub(r"([^\n])\n(  - name:)", r"\1\n\n\2", text)
    with Path(path).open("w", encoding="utf-8") as f:
        f.write(text)


def to_quoted(entry: dict) -> dict:
    """Wrap string values in DoubleQuotedScalarString so ruamel emits them with
    double quotes, matching the style of the hand-curated entries."""
    out = {}
    for k, v in entry.items():
        if isinstance(v, str):
            out[k] = DQ(v)
        elif isinstance(v, list):
            out[k] = [DQ(i) if isinstance(i, str) else i for i in v]
        else:
            out[k] = v
    return out


def parse_json_obj(text: str) -> dict | None:
    """Tolerant JSON-object extraction from an LLM reply.

    Prefers a fenced code block (```json ... ```) and uses raw_decode so the
    JSON parser determines the object boundary — handles trailing text or extra
    braces after the object without regex back-tracking surprises. Falls back to
    scanning forward through every { if no fence is found.
    """
    if not text:
        return None
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


def normalize_name(name) -> str:
    """Case/whitespace-insensitive key for dedup and lookup."""
    return " ".join(str(name).strip().lower().split())


def existing_names(data, section: str) -> set[str]:
    """Normalized names already present in a list section."""
    names: set[str] = set()
    for entry in data.get(section) or []:
        if isinstance(entry, dict) and entry.get("name") is not None:
            names.add(normalize_name(entry["name"]))
    return names
