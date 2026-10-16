"""Checks the plugin manifests parse and agree, and the skill's frontmatter has a name and description."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors = []

plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
if plugin.get("name") not in [p.get("name") for p in market.get("plugins", [])]:
    errors.append("marketplace.json does not list the plugin named in plugin.json")

for skill in (ROOT / "skills").glob("*/SKILL.md"):
    m = re.match(r"^---\n(.*?)\n---\n", skill.read_text(encoding="utf-8"), re.S)
    if not m:
        errors.append(f"{skill}: no frontmatter")
        continue
    fm = dict(re.findall(r"^(\w+):\s*(.+)$", m.group(1), re.M))
    if fm.get("name") != skill.parent.name:
        errors.append(f"{skill}: name must be {skill.parent.name}")
    if not 50 <= len(fm.get("description", "")) <= 1024:
        errors.append(f"{skill}: description must be 50 to 1024 characters")

print("\n".join(errors) or "manifests ok")
sys.exit(1 if errors else 0)
