"""Shared round-trip helpers for the wow_reference.yaml fact-check pipeline.

Both extract_statements.py (writes new, unverified entries) and
factcheck_reference.py (annotates entries with verification results) read and
write wow_reference.yaml through here.

We use ruamel.yaml in round-trip mode so the hand-curated Norwegian comments and
the file's structure survive read/modify/write cycles — plain pyyaml would strip
every comment and reflow the block scalars.
"""
from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

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
    """Write the round-trip document back, comments intact."""
    with Path(path).open("w", encoding="utf-8") as f:
        _yaml().dump(data, f)


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
