"""Generate professional README content for the 10 repos with missing/stub READMEs."""
import json
from pathlib import Path

PLAN = Path(r"C:\Users\abdul\AppData\Local\Temp\repo_polish_plan.json")
README_STATE = Path(r"C:\Users\abdul\AppData\Local\Temp\readme_state.json")
README_OUT = Path(r"C:\Users\abdul\AppData\Local\Temp\generated_readmes")
OWNER = "AbdullahBakir97"

with PLAN.open(encoding="utf-8") as f:
    plan = {p["name"]: p for p in json.load(f)}
with README_STATE.open(encoding="utf-8") as f:
    state = {s["name"]: s for s in json.load(f)}

README_OUT.mkdir(parents=True, exist_ok=True)


def quick_start_for(lang: str, topics: list[str], name: str) -> str:
    t = set(topics)
    if "django" in t or "Django" in t or (lang == "Python" and ("django-rest-framework" in t or name.lower().startswith("django"))):
        return (
            "```bash\n"
            f"git clone https://github.com/{OWNER}/{name}.git\n"
            f"cd {name}\n"
            "python -m venv .venv\n"
            "source .venv/bin/activate    # Windows: .venv\\Scripts\\activate\n"
            "pip install -r requirements.txt\n"
            "python manage.py migrate\n"
            "python manage.py runserver\n"
            "```"
        )
    if lang == "Python" and ("pygame" in t or "game" in t):
        return (
            "```bash\n"
            f"git clone https://github.com/{OWNER}/{name}.git\n"
            f"cd {name}\n"
            "python -m venv .venv\n"
            "source .venv/bin/activate    # Windows: .venv\\Scripts\\activate\n"
            "pip install -r requirements.txt\n"
            "python main.py\n"
            "```"
        )
    if lang == "Python":
        return (
            "```bash\n"
            f"git clone https://github.com/{OWNER}/{name}.git\n"
            f"cd {name}\n"
            "python -m venv .venv\n"
            "source .venv/bin/activate    # Windows: .venv\\Scripts\\activate\n"
            "pip install -r requirements.txt\n"
            "```"
        )
    if lang in ("TypeScript", "JavaScript"):
        return (
            "```bash\n"
            f"git clone https://github.com/{OWNER}/{name}.git\n"
            f"cd {name}\n"
            "npm install\n"
            "npm run dev\n"
            "```"
        )
    if lang == "Vue":
        return (
            "```bash\n"
            f"git clone https://github.com/{OWNER}/{name}.git\n"
            f"cd {name}\n"
            "npm install\n"
            "npm run serve\n"
            "```"
        )
    return (
        "```bash\n"
        f"git clone https://github.com/{OWNER}/{name}.git\n"
        f"cd {name}\n"
        "```"
    )


def lang_badge(lang: str | None) -> str:
    if not lang:
        return ""
    palette = {
        "Python": "3776AB",
        "JavaScript": "F7DF1E",
        "TypeScript": "3178C6",
        "Vue": "4FC08D",
        "HTML": "E34F26",
        "CSS": "1572B6",
        "Jupyter Notebook": "F37626",
    }
    color = palette.get(lang, "555555")
    safe = lang.replace(" ", "%20")
    logo = lang.lower().replace(" ", "")
    return f"![{lang}](https://img.shields.io/badge/{safe}-{color}?style=flat-square&logo={logo}&logoColor=white)"


def topics_section(topics: list[str]) -> str:
    if not topics:
        return ""
    return "## Topics\n\n" + " · ".join(f"`{t}`" for t in topics) + "\n"


def render(name: str) -> str:
    p = plan[name]
    desc = p["new_desc"]
    topics = p["new_topics"]
    lang = p["lang"]
    stars = p["stars"]
    forks = p["forks"]
    title = name.replace("-", " ").replace("_", " ").strip()

    nice_lang = lang or "Multi-language"
    badges = []
    badges.append(lang_badge(lang))
    badges.append(
        f"![Stars](https://img.shields.io/github/stars/{OWNER}/{name}?style=flat-square&color=FFD700)"
    )
    badges.append(
        f"![Forks](https://img.shields.io/github/forks/{OWNER}/{name}?style=flat-square&color=blue)"
    )
    badges.append(
        f"![Last commit](https://img.shields.io/github/last-commit/{OWNER}/{name}?style=flat-square)"
    )
    badge_row = " ".join(b for b in badges if b)

    qs = quick_start_for(lang or "", topics, name)

    return (
        f"# {title}\n\n"
        f"> {desc}\n\n"
        f"{badge_row}\n\n"
        f"---\n\n"
        f"## Overview\n\n"
        f"{desc}\n\n"
        f"## Tech stack\n\n"
        f"- **Language:** {nice_lang}\n"
        f"- **Tags:** {', '.join(topics) if topics else '—'}\n\n"
        f"## Quick start\n\n"
        f"{qs}\n\n"
        f"{topics_section(topics)}\n"
        f"## Author\n\n"
        f"**Abdullah Bakir** — [@{OWNER}](https://github.com/{OWNER})\n\n"
        f"Full-Stack Developer based in Germany - Python · Django · Vue · Nuxt.\n\n"
        f"## License\n\n"
        f"Part of the [@{OWNER}](https://github.com/{OWNER}) portfolio. License terms to be added; for now treat as **all rights reserved**.\n\n"
        f"---\n\n"
        f"_Last refreshed: 2026-05-04 - This README was generated as part of a portfolio polish pass and will be replaced with project-specific narrative as work resumes on this repository._\n"
    )


# Identify which need new READMEs
need_new = [s["name"] for s in state.values() if s["status"] in ("missing", "stub")]
print(f"Generating new README for {len(need_new)} repos:")

for name in need_new:
    if name not in plan:
        continue
    md = render(name)
    out = README_OUT / f"{name}.md"
    out.write_text(md, encoding="utf-8")
    print(f"  - {name:42} ({len(md)} chars)")

print(f"\nGenerated READMEs saved -> {README_OUT}")
