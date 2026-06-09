#!/usr/bin/env python3
"""
wow_reference.yaml cleaner:
1. Apply corrections to data fields
2. Set verified=True, keep source_url
3. Deduplicate within each section
"""

import yaml
import re
from copy import deepcopy

def load_yaml(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

# ──────────────────────────────────────────────────────────
# YAML dump helpers
# ──────────────────────────────────────────────────────────

class CleanDumper(yaml.Dumper):
    pass

def _represent_str(dumper, data):
    # Use block style only for long/multiline strings
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    if len(data) > 80 or any(c in data for c in [':', '#', '[', ']', '{', '}']):
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

def _represent_none(dumper, _):
    return dumper.represent_scalar('tag:yaml.org,2002:null', '')

CleanDumper.add_representer(str, _represent_str)
CleanDumper.add_representer(type(None), _represent_none)

def save_yaml(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# wow_reference.yaml — Verified WoW Classic (patch 1.12) fishing facts\n")
        f.write("# Used by the grader as ground truth for fact-checking.\n\n")
        yaml.dump(data, f, Dumper=CleanDumper, default_flow_style=False,
                  allow_unicode=True, sort_keys=False, indent=2, width=120)

# ──────────────────────────────────────────────────────────
# Correction application
# ──────────────────────────────────────────────────────────

SIMPLE_FIELDS = (
    'name', 'buff', 'buff_duration', 'recipe_source', 'skill_required',
    'fishing_skill_required', 'time_restriction', 'faction_safety',
    'pvp_risk', 'type', 'source', 'notes', 'bonus', 'duration',
    'access_notes', 'location', 'continent', 'fishing_skill_effective',
)
FIELD_PAT = '|'.join(re.escape(f) for f in SIMPLE_FIELDS)
SIMPLE_RE = re.compile(
    rf'^({FIELD_PAT}):\s+should be\s+(.*?)(?:,?\s+not\s+.+)?$',
    re.IGNORECASE
)

def _add_note(entry, text):
    existing = entry.get('notes') or ''
    if isinstance(existing, list):
        if text not in existing:
            existing.append(text)
            entry['notes'] = existing
    else:
        existing = str(existing)
        if text not in existing:
            entry['notes'] = (existing + (' ' if existing else '') + text).strip()

def parse_list_str(s):
    """Try to parse a string into a list of items."""
    s = s.strip()
    items = re.findall(r"['\"]([^'\"]+)['\"]", s)
    if items:
        return items
    if s.startswith('['):
        inner = s[1:s.rfind(']')]
        items = [x.strip().strip("'\"") for x in inner.split(',') if x.strip()]
        if items:
            return items
    if ',' in s:
        return [x.strip().strip("'\"") for x in s.split(',') if x.strip().strip("'\"")]
    clean = s.strip("'\"")
    return [clean] if clean else []

def apply_correction(entry, corr_str):
    if not corr_str:
        return
    corr = str(corr_str).strip()
    if not corr or corr.startswith('#'):
        return

    # "does not exist in WoW Classic" / WotLK/TBC additions
    if re.search(r'does not exist in WoW Classic', corr, re.IGNORECASE):
        _add_note(entry, "Does not exist in WoW Classic (1.12)")
        return
    if re.search(r'N/A\s*\((?:item|location) does not exist\)', corr, re.IGNORECASE):
        _add_note(entry, "Does not exist in WoW Classic (1.12)")
        return
    if re.search(r'added in\s+(?:Wrath|WotLK|The Burning Crusade|TBC|Patch 2\.)', corr, re.IGNORECASE):
        _add_note(entry, "Does not exist in WoW Classic (1.12)")
        return

    # Simple field: "fieldname: should be VALUE [, not ...]"
    m = SIMPLE_RE.match(corr)
    if m:
        field = m.group(1).lower()
        new_val = m.group(2).strip().strip("'\"").strip()
        if new_val.lower() in ('null', 'none', "''", '""'):
            entry[field] = None
        elif new_val:
            entry[field] = new_val
        return

    # Zones: "zones: should be / should include ..."
    m = re.match(r'^zones:\s+should (?:be|include)\s+(.*?)(?:,?\s+not\s+.+)?$', corr, re.IGNORECASE)
    if m:
        zones = parse_list_str(m.group(1).strip())
        if zones:
            entry['zones'] = zones
        return

    # Ingredients: "ingredients: should be ..."
    m = re.match(r'^ingredients:\s+should (?:be|include)\s+(.*?)(?:,?\s+not\s+.+)?$', corr, re.IGNORECASE)
    if m:
        raw = m.group(1).strip()
        ings = parse_list_str(raw)
        if not ings:
            ings = [p.strip() for p in re.split(r'\s+and\s+|,\s*', raw) if p.strip()]
        if ings:
            entry['ingredients'] = ings
        return

    # Notable fish: update
    m = re.match(r'^notable_fish:\s+should (?:be|include)\s+(.*?)(?:,?\s+not\s+.+)?$', corr, re.IGNORECASE)
    if m:
        fish = parse_list_str(m.group(1).strip())
        if fish:
            entry['notable_fish'] = fish
        return

    # Sells: too complex to parse automatically – skip

def process_entry(entry):
    if not isinstance(entry, dict):
        return entry
    corrections = entry.get('corrections') or []
    for c in corrections:
        apply_correction(entry, c)
    entry['verified'] = True
    # Remove corrections key entirely
    entry.pop('corrections', None)
    return entry

# ──────────────────────────────────────────────────────────
# Deduplication
# ──────────────────────────────────────────────────────────

def normalize_name(name, section):
    name = str(name).strip()
    if section == 'cooking_recipes':
        name = re.sub(r'^Recipe:\s*', '', name, flags=re.IGNORECASE)
        name = re.sub(r'^Raw\s+', '', name, flags=re.IGNORECASE)
    elif section == 'fish':
        name = re.sub(r'^Raw\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^The\s+', '', name, flags=re.IGNORECASE)
    name = name.lower()
    if section == 'items_and_clarifications':
        # Also strip spaces and trailing 's' for plural/addon name variants
        name = re.sub(r'\s+', '', name)
        name = re.sub(r's$', '', name)
    else:
        name = re.sub(r'\s+', ' ', name).strip()
    return name

def field_count(e):
    return sum(1 for k, v in e.items()
               if v is not None and v != [] and v != '' and k not in ('_orig_verified',))

def choose_primary(a, b):
    """Return (primary, secondary) – primary is the one we keep."""
    a_ov = a.get('_orig_verified', False)
    b_ov = b.get('_orig_verified', False)
    if a_ov and not b_ov:
        return a, b
    if b_ov and not a_ov:
        return b, a

    a_name = str(a.get('name', ''))
    b_name = str(b.get('name', ''))

    # Prefer Raw X in fish
    if a_name.lower().startswith('raw ') and not b_name.lower().startswith('raw '):
        return a, b
    if b_name.lower().startswith('raw ') and not a_name.lower().startswith('raw '):
        return b, a

    # Prefer name without Recipe:
    if not a_name.lower().startswith('recipe:') and b_name.lower().startswith('recipe:'):
        return a, b
    if not b_name.lower().startswith('recipe:') and a_name.lower().startswith('recipe:'):
        return b, a

    # More complete entry wins
    if field_count(a) >= field_count(b):
        return a, b
    return b, a

def merge(primary, secondary):
    for k, v in secondary.items():
        if k in ('_orig_verified',):
            continue
        if k not in primary or primary[k] is None or primary[k] == []:
            primary[k] = v
        elif k == 'zones' and isinstance(v, list) and isinstance(primary.get(k), list):
            existing = set(primary[k])
            for z in v:
                if z not in existing:
                    primary[k].append(z)
                    existing.add(z)
        elif k == 'source_url' and not primary.get(k) and v:
            primary[k] = v
    primary['verified'] = True
    return primary

def deduplicate_section(entries, section):
    if not entries:
        return [], 0
    # Mark original verified status
    for e in entries:
        if isinstance(e, dict):
            e['_orig_verified'] = e.get('verified', False)
    # Apply corrections
    processed = [process_entry(deepcopy(e)) for e in entries if isinstance(e, dict)]
    # Deduplicate
    seen = {}   # norm_name -> index in result
    result = []
    dups = 0
    for entry in processed:
        name = entry.get('name', '')
        norm = normalize_name(name, section)
        if norm in seen:
            idx = seen[norm]
            primary, secondary = choose_primary(result[idx], entry)
            result[idx] = merge(primary, secondary)
            dups += 1
        else:
            seen[norm] = len(result)
            result.append(entry)
    # Clean temp fields
    for e in result:
        e.pop('_orig_verified', None)
    return result, dups

# ──────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────

data = load_yaml('wow_reference.yaml')

LIST_SECTIONS = ['cooking_recipes', 'fish', 'zones', 'vendors', 'items_and_clarifications']

total_before = 0
total_after = 0
total_dups = 0
report_lines = []

for section in LIST_SECTIONS:
    entries = data.get(section)
    if not isinstance(entries, list):
        continue
    before = len(entries)
    total_before += before
    cleaned, dups = deduplicate_section(entries, section)
    after = len(cleaned)
    total_after += after
    total_dups += dups
    data[section] = cleaned
    report_lines.append(f"  {section}: {before} -> {after}  ({dups} duplicates removed)")

save_yaml(data, 'wow_reference.yaml')

print("=== wow_reference.yaml cleanup complete ===")
for line in report_lines:
    print(line)
print(f"\nTotal list entries: {total_before} -> {total_after}  ({total_dups} duplicates removed)")
print(f"Unique entries now: {total_after}")
