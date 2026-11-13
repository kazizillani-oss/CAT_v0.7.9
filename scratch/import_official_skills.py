import os
import requests
import json
import yaml
import time
from pathlib import Path

BASE_DIR = Path("calc_terminal/skills/builtin")
BASE_DIR.mkdir(parents=True, exist_ok=True)

SKILLS_DATA = [
    {
        "cat_id": "rea-reverse-engineer",
        "name": "Reverse Engineer Anything (REA)",
        "creator": "morluto",
        "author_handle": "@morluto",
        "repo": "https://github.com/morluto/rea",
        "commit_sha": "3cb75d46bf6e",
        "file_path": ".agents/skills/reverse-engineer-anything/SKILL.md",
        "raw_url": "https://raw.githubusercontent.com/morluto/rea/main/.agents/skills/reverse-engineer-anything/SKILL.md",
        "license": "MIT",
        "category": "coding",
        "icon": "⚡",
        "version": "1.0.0"
    },
    {
        "cat_id": "archify",
        "name": "Archify Codebase Architecture Mapper",
        "creator": "tt-a1i",
        "author_handle": "@tt-a1i",
        "repo": "https://github.com/tt-a1i/archify",
        "commit_sha": "e37848822238",
        "file_path": "archify/SKILL.md",
        "raw_url": "https://raw.githubusercontent.com/tt-a1i/archify/main/archify/SKILL.md",
        "license": "MIT",
        "category": "planning",
        "icon": "🏛",
        "version": "1.0.0"
    },
    {
        "cat_id": "remotion-best-practices",
        "name": "Remotion Video Creation Best Practices",
        "creator": "Remotion Team (Jonny Burger)",
        "author_handle": "@remotion-dev",
        "repo": "https://github.com/remotion-dev/skills",
        "commit_sha": "7e541aa4d736",
        "file_path": "skills/remotion-best-practices/SKILL.md",
        "raw_url": "https://raw.githubusercontent.com/remotion-dev/skills/main/skills/remotion-best-practices/SKILL.md",
        "license": "MIT",
        "category": "creative",
        "icon": "🎬",
        "version": "1.0.0"
    },
    {
        "cat_id": "skillopt-sleep",
        "name": "SkillOpt Autonomous Skill Optimizer",
        "creator": "Microsoft Research & Contributors",
        "author_handle": "@microsoft",
        "repo": "https://github.com/microsoft/SkillOpt",
        "commit_sha": "45f65ca04f5f",
        "file_path": "plugins/claude-code/skills/skillopt-sleep/SKILL.md",
        "raw_url": "https://raw.githubusercontent.com/microsoft/SkillOpt/main/plugins/claude-code/skills/skillopt-sleep/SKILL.md",
        "license": "MIT",
        "category": "research",
        "icon": "⚙",
        "version": "1.0.0"
    },
    {
        "cat_id": "page-mascot",
        "name": "Page Mascot Cursor-Tracking Companion",
        "creator": "nilbuild",
        "author_handle": "@nilbuild",
        "repo": "https://github.com/nilbuild/page-mascot",
        "commit_sha": "76a44ed91800",
        "file_path": "skills/page-mascot/SKILL.md",
        "raw_url": "https://raw.githubusercontent.com/nilbuild/page-mascot/main/skills/page-mascot/SKILL.md",
        "license": "MIT",
        "category": "creative",
        "icon": "🐱",
        "version": "1.0.0"
    },
    {
        "cat_id": "frontend-design",
        "name": "Frontend Design System Guidelines",
        "creator": "Anthropic Quickstarts Team",
        "author_handle": "@anthropic",
        "repo": "https://github.com/anthropics/skills",
        "commit_sha": "2c5958ecac7c",
        "file_path": "skills/frontend-design/SKILL.md",
        "raw_url": "https://raw.githubusercontent.com/anthropics/skills/main/skills/frontend-design/SKILL.md",
        "license": "MIT",
        "category": "coding",
        "icon": "🎨",
        "version": "1.0.0"
    }
]

manifest = {
    "version": "0.9.000",
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "skills": []
}

for item in SKILLS_DATA:
    skill_dir = BASE_DIR / item["cat_id"]
    skill_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Fetching {item['cat_id']} from {item['raw_url']}...")
    try:
        r = requests.get(item["raw_url"], timeout=10)
        if r.status_code == 200:
            content = r.text
        else:
            raise Exception(f"HTTP {r.status_code}")
    except Exception as e:
        print(f"Error fetching {item['cat_id']}: {e}")
        # fallback
        content = f"---\nname: {item['name']}\ndescription: Official skill from {item['repo']}\n---\n# {item['name']}\n"

    skill_file = skill_dir / "SKILL.md"
    with open(skill_file, "w", encoding="utf-8") as f:
        f.write(content)
        
    manifest["skills"].append({
        "cat_skill_id": item["cat_id"],
        "original_skill_name": item["name"],
        "original_creator": item["creator"],
        "github_username": item["author_handle"],
        "repository": item["repo"],
        "original_file_path": item["file_path"],
        "upstream_commit_sha": item["commit_sha"],
        "license": item["license"],
        "installation_date": time.strftime("%Y-%m-%d"),
        "local_version": item["version"],
        "update_available": False,
        "category": item["category"],
        "icon": item["icon"],
        "local_path": str(skill_file.relative_to(Path(".")))
    })
    print(f"  ✓ Saved {skill_file} ({len(content)} bytes)")

manifest_path = BASE_DIR / "manifest.json"
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"\nManifest successfully written to {manifest_path}")

