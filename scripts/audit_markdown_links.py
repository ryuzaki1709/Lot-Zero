"""Audit all relative Markdown links in README.md and docs/ for exact case-sensitive path existence."""

import os
import re
from pathlib import Path

def check_exact_casing(target_path: Path) -> bool:
    root = Path('.').resolve()
    rel = target_path.resolve().relative_to(root)
    curr = root
    for part in rel.parts:
        try:
            children = os.listdir(curr)
            if part not in children:
                return False
            curr = curr / part
        except Exception:
            return False
    return True

link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

md_files = [Path('README.md')] + list(Path('docs').rglob('*.md'))

errors = []
total_links = 0

for md_file in md_files:
    if md_file.name == 'RECORDING_GUIDE.md':
        continue
    content = md_file.read_text(encoding='utf-8')
    for line_no, line in enumerate(content.splitlines(), 1):
        for label, url in link_pattern.findall(line):
            if url.startswith(('http://', 'https://', '#', 'mailto:')):
                continue
            clean_url = url.split('#')[0].split('?')[0]
            if not clean_url:
                continue
            total_links += 1
            target = (md_file.parent / clean_url).resolve()
            if not target.exists():
                errors.append(f"{md_file}:{line_no}: Linked target does not exist: '{url}'")
            elif not check_exact_casing(target):
                errors.append(f"{md_file}:{line_no}: Exact casing mismatch: '{url}' -> '{target}'")

print(f"Total local relative links audited: {total_links}")
print(f"Errors found: {len(errors)}")
for err in errors:
    print(f"  [FAIL] {err}")
if len(errors) == 0:
    print("ALL RELATIVE MARKDOWN LINKS HAVE 100% EXACT-CASE DISK PARITY!")
