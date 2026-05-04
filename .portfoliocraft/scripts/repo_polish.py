"""Generate description / topics / README update plan for kept repos.

This step ONLY plans the changes — applies them in a separate step after review.
"""
import json
from pathlib import Path

KEPT = Path(r"C:\Users\abdul\AppData\Local\Temp\kept_repos.json")
PLAN = Path(r"C:\Users\abdul\AppData\Local\Temp\repo_polish_plan.json")

with KEPT.open(encoding="utf-8") as f:
    repos = json.load(f)

# Curated, hand-written descriptions for the well-known projects
DESCRIPTIONS = {
    "AbdullahBakir97": "GitHub profile README — animated headers, 3D contribution skyline, per-year stats, full project showcase. Auto-refreshed daily by GitHub Actions.",
    "PortfolioCraft": "Generate a verifiable professional portfolio from your GitHub history — README block, JSON Resume, PDF CV, and stat cards. GitHub Action + CLI.",
    "Stock-Manager": "Professional desktop inventory management for Windows — local-first SQLite store, barcode-aware, multi-user with role separation.",
    "Barber-Salon": "Salon management platform — appointments, staff profiles, customer reviews, gallery, products, multi-language. Django + DRF + Vue.",
    "Django-Store": "Amazon-style e-commerce platform — products, brands, reviews, orders, payments, charts, multi-language. Django + DRF + Bootstrap.",
    "Jobs-Portal": "Jobs portal for seekers and employers — listings, applications, employer dashboards, REST API. Django + DRF.",
    "Django--LMS--Learning-Management-System": "Learning management system — courses, certifications, messaging, networking, groups. Django + Channels.",
    "2050-Bootstrap-Landing-page": "Marketing landing page demo built with Bootstrap 5 — responsive sections, hero, features, CTA.",
    "Django-Blog-app": "Django blog application — posts, categories, comments, search, SEO-friendly slugs.",
    "Automtion": "Browser-automation playground — Selenium-driven scrapers and form fillers for repeatable workflows.",
    "Project-Management-Tool": "Project management tool — boards, tasks, members, comments, activity feed. Django + DRF + Vue.",
    "Python-Django-join_with": "Django QuerySet join examples — annotated, nested, and aggregated query patterns with real models.",
    "Weather--App-django-vue.js": "Weather lookup app — Django backend with Vue.js frontend, geolocation and forecast widgets.",
    "API": "Django REST Framework reference API — auth, pagination, throttling, filtering, OpenAPI/Swagger docs.",
    "image-cropping": "Server-side image cropping utility — Pillow-based resize, smart-crop, and aspect-ratio presets.",
    "Pilot-Logbook": "Pilot logbook — track flight hours, aircraft, routes, and certifications. Django + DRF.",
    "Trello-Clone-Services": "Trello-style kanban backend — boards, lists, cards, drag-and-drop ordering, members. Django services layer.",
    "AI-KI": "Notebook-driven AI experiments — model exploration, training, and evaluation in Jupyter.",
    "API-Client-Generator": "Generate typed Python API clients from OpenAPI specs — handles auth, pagination, and retries.",
    "Mini-RAG": "Minimal retrieval-augmented generation pipeline — embeddings, vector store, prompt assembly.",
    "Py-Tetris-Game": "Tetris implementation in Python with pygame — classic mechanics, scoring, level progression.",
    "Content-Creator-Tool": "Content creation utility — generate posts, captions, and assets for social media workflows.",
    "GitHub-Doc-Generator": "Auto-generate documentation pages from a GitHub repository — README parsing and Markdown output.",
    "Space-Shooter": "Space shooter mini-game — pygame-based arcade clone with enemies, power-ups, scoring.",
    "Tawil-Media---Advertisement": "Marketing site for Tawil Media — hero, services, portfolio, contact form. Django + Tailwind.",
    "Baeckrei": "Bakery management system — production scheduling, recipe-driven inventory deduction, customer accounts, online orders. Django + Vue 3.",
    "Email-Sender": "Bulk email sender — templating, attachments, delivery logs. Python.",
    "Portfolio": "Personal portfolio site — projects, blog, contact. TypeScript.",
    "cortex": "Memory-augmented agent kernel — context windows, retrieval, and structured output for LLM workflows.",
    "Repo-Directory-Structure": "Generate a tree-style snapshot of any repository's directory structure — Markdown export.",
    "Py-Desktop-Expense_Tracker": "Desktop expense tracker — categories, charts, monthly reports. Tkinter + SQLite.",
    "Python-Environment-Management-Tool": "CLI to manage Python virtualenvs and project dependencies — bootstrap, freeze, sync.",
    "Django-Followers-System": "Reusable followers/following app for Django — relationships, feeds, signals.",
    "Django-Reporting-System": "Reporting dashboard for Django apps — chart cards, exports, scheduled emails.",
    "Dj--To-Do": "Django to-do app — CRUD, status filters, due dates, owner-scoped queries.",
    "GitHub-Issues-Wall": "Browser wall of GitHub issues — fetched via API, sortable and filterable cards.",
    "commit-craft": "GitHub App that auto-formats pull-request commits to conventional-commits style.",
    "pr-coach": "GitHub App that coaches authors during pull-request review — title, description, scope feedback.",
    "repodoc-ai": "GitHub App that auto-generates and refreshes README sections from real repo signals.",
    "ai-quality-gate": "GitHub App that runs an AI-driven quality gate on every PR — readability, scope, and risk scoring.",
    "issue-triage-bot": "GitHub App that auto-labels and routes new issues based on title, body, and historical patterns.",
    "release-pilot": "GitHub App that drafts release notes and version bumps from merged pull-request history.",
}

PYDEV_TOPICS = ["github-app", "github-action", "developer-tools", "automation", "ci-cd", "python"]
TOPIC_SEEDS = {
    "AbdullahBakir97": ["profile-readme", "github-actions", "auto-update", "dynamic-readme", "svg", "animation"],
    "Automtion": ["python", "automation", "selenium", "web-scraping", "browser-automation"],
    "image-cropping": ["python", "pillow", "image-processing", "thumbnails", "image-cropping"],
    "Pilot-Logbook": ["python", "django", "logbook", "aviation", "pilot"],
    "Trello-Clone-Services": ["python", "django", "kanban", "trello-clone", "services"],
    "AI-KI": ["python", "jupyter", "machine-learning", "ai", "experiments"],
    "API-Client-Generator": ["python", "cli", "api-client", "openapi", "codegen"],
    "Mini-RAG": ["python", "rag", "llm", "embeddings", "vector-store"],
    "Py-Tetris-Game": ["python", "pygame", "game", "tetris"],
    "Content-Creator-Tool": ["python", "content-generation", "social-media", "automation"],
    "GitHub-Doc-Generator": ["python", "cli", "github-api", "documentation", "markdown"],
    "Space-Shooter": ["python", "pygame", "game", "arcade"],
    "Tawil-Media---Advertisement": ["django", "python", "marketing-site", "tailwindcss", "business"],
    "Baeckrei": ["python", "django", "vue3", "bakery", "inventory-management", "pos"],
    "Email-Sender": ["python", "email", "smtp", "bulk-email"],
    "Portfolio": ["typescript", "portfolio", "nextjs", "personal-site"],
    "release-pilot": PYDEV_TOPICS + ["release-notes", "changelog", "semver"],
    "commit-craft": PYDEV_TOPICS + ["conventional-commits", "pre-commit"],
    "pr-coach": PYDEV_TOPICS + ["pull-request", "code-review", "ai"],
    "repodoc-ai": PYDEV_TOPICS + ["readme", "documentation", "ai"],
    "ai-quality-gate": PYDEV_TOPICS + ["code-quality", "ai", "pr-review"],
    "issue-triage-bot": PYDEV_TOPICS + ["issue-tracker", "triage", "auto-label", "ai"],
}


def normalize_topic(t: str) -> str:
    t = t.strip().lower()
    t = t.replace("_", "-").replace(" ", "-")
    return t


plan = []
for r in repos:
    name = r["name"]
    cur_desc = (r.get("description") or "").strip()
    cur_topics = sorted(r.get("topics") or [])

    new_desc = DESCRIPTIONS.get(name, cur_desc).strip() if DESCRIPTIONS.get(name) else cur_desc
    if not new_desc:
        nice = name.replace("-", " ").replace("_", " ").strip()
        lang = r.get("lang") or "Multi-language"
        new_desc = f"{nice} — {lang} repository in the @AbdullahBakir97 portfolio."

    seeds = [normalize_topic(t) for t in TOPIC_SEEDS.get(name, [])]
    merged = sorted({normalize_topic(t) for t in cur_topics} | set(seeds))[:18]

    plan.append({
        "name": name,
        "url": r["url"],
        "lang": r.get("lang"),
        "stars": r["stars"],
        "forks": r["forks"],
        "cur_desc": cur_desc,
        "new_desc": new_desc[:350],
        "desc_changed": cur_desc != new_desc[:350],
        "cur_topics": cur_topics,
        "new_topics": merged,
        "topics_changed": sorted(merged) != sorted(cur_topics),
    })

with PLAN.open("w", encoding="utf-8") as f:
    json.dump(plan, f, indent=2)

desc_ch = sum(1 for p in plan if p["desc_changed"])
top_ch = sum(1 for p in plan if p["topics_changed"])
print(f"Plan written -> {PLAN}")
print(f"  total kept repos: {len(plan)}")
print(f"  description updates planned: {desc_ch}")
print(f"  topic updates planned:       {top_ch}")

print()
print("Sample of description changes:")
for p in [p for p in plan if p["desc_changed"]][:6]:
    print(f"  - {p['name']}")
    print(f"    cur: {(p['cur_desc'] or '(empty)')[:110]}")
    print(f"    new: {p['new_desc'][:110]}")
