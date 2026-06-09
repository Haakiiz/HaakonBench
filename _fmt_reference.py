#!/usr/bin/env python3
"""Add a blank line between every list entry in wow_reference.yaml."""

with open('wow_reference.yaml', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
result = []
for line in lines:
    # Insert blank line before each list-entry start (  - name:), but not
    # if the line above is already blank or is a section key (e.g. "fish:").
    if line.lstrip().startswith('- name:') or line.lstrip().startswith('- name '):
        if result and result[-1].strip() != '':
            result.append('')
    result.append(line)

with open('wow_reference.yaml', 'w', encoding='utf-8') as f:
    f.write('\n'.join(result))

print("Done.")
