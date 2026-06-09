#!/usr/bin/env python3
"""Fix corrupted names that resulted from correction strings leaking into name field."""

import yaml
import re
from copy import deepcopy

with open('wow_reference.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

fish = data['fish']
zones = data['zones']

# ── Fish fixes ──────────────────────────────────────────────────────────────

# "Firefin Snapper' or 'Nightfin Snapper" came from original "Misty Fin Snapper"
# (a hallucinated fish). Keep it under its original name with a clarifying note.
for e in fish:
    if e.get('name') == "Firefin Snapper' or 'Nightfin Snapper":
        e['name'] = 'Misty Fin Snapper'
        e['notes'] = ("Does not exist in WoW Classic (1.12). "
                      "LLMs sometimes hallucinate this name instead of Firefin Snapper or Nightfin Snapper.")
        print("FIXED: Misty Fin Snapper")
        break

# "Patch of Elemental Water' (the pool name)" — original was "Essence of Water",
# renamed via correction to "Patch of Elemental Water". Strip the parenthetical annotation.
for e in fish:
    if e.get('name') == "Patch of Elemental Water' (the pool name)":
        e['name'] = 'Patch of Elemental Water'
        print("FIXED: Patch of Elemental Water")
        break

# "Longjaw Mud Snapper' (or specific trophy fish like '10 Pound Mud Snapper')"
# came from "Mud Snap". Now that "Raw Longjaw Mud Snapper" already exists, drop this
# duplicate entirely (it represents a non-existent fish; the real article is #22).
fish[:] = [e for e in fish
           if e.get('name') != "Longjaw Mud Snapper' (or specific trophy fish like '10 Pound Mud Snapper')"]
print("REMOVED: Mud Snap / broken Longjaw Mud Snapper duplicate")

# ── Zones fixes ─────────────────────────────────────────────────────────────

# "Auberdine' (the zone is 'Darkshore')" came from "Auberdine Harbor".
# Correct name: "Auberdine Harbor" (keep distinct; merge happens in dedup if needed)
for e in zones:
    if e.get('name') == "Auberdine' (the zone is 'Darkshore')":
        e['name'] = 'Auberdine Harbor'
        print("FIXED: Auberdine Harbor")
        break

# "Fenris Isle' (the primary island in Lordamere Lake)" → "Fenris Isle"
for e in zones:
    if 'Fenris Isle' in str(e.get('name', '')) and "primary island" in str(e.get('name', '')):
        e['name'] = 'Fenris Isle'
        print("FIXED: Fenris Isle")
        break

# "Azshara (Bay of Storms)', as 'Hidden Azshara coast' is" → "Bay of Storms"
# (It's a subzone of Azshara; keep as distinct subzone entry rather than removing)
for e in zones:
    if "Hidden Azshara coast" in str(e.get('name', '')) or \
       ("Azshara" in str(e.get('name', '')) and "Hidden" in str(e.get('name', ''))):
        e['name'] = 'Bay of Storms'
        print("FIXED: Bay of Storms (was Hidden Azshara coast)")
        break
# Also fix if it starts with "Azshara (Bay of Storms)'"
for e in zones:
    if e.get('name', '').startswith("Azshara (Bay of Storms)'"):
        e['name'] = 'Bay of Storms'
        print("FIXED: Bay of Storms (was Azshara (Bay of Storms) broken)")
        break

# ── Items fix ───────────────────────────────────────────────────────────────

items = data['items_and_clarifications']
for e in items:
    name = str(e.get('name', ''))
    # "Basic Campfire' (spell)" → "Basic Campfire (spell)"
    if name == "Basic Campfire' (spell)":
        e['name'] = 'Basic Campfire (spell)'
        print("FIXED: Basic Campfire (spell)")
        break

# ── Save ────────────────────────────────────────────────────────────────────

class CleanDumper(yaml.Dumper):
    pass

def _represent_str(dumper, data):
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    if len(data) > 80 or any(c in data for c in [':', '#', '[', ']', '{', '}']):
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

def _represent_none(dumper, _):
    return dumper.represent_scalar('tag:yaml.org,2002:null', '')

CleanDumper.add_representer(str, _represent_str)
CleanDumper.add_representer(type(None), _represent_none)

with open('wow_reference.yaml', 'w', encoding='utf-8') as f:
    f.write("# wow_reference.yaml - Verified WoW Classic (patch 1.12) fishing facts\n")
    f.write("# Used by the grader as ground truth for fact-checking.\n\n")
    yaml.dump(data, f, Dumper=CleanDumper, default_flow_style=False,
              allow_unicode=True, sort_keys=False, indent=2, width=120)

print("\nSaved. Re-running dedup...")
