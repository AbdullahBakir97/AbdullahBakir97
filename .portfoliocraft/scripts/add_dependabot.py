"""Add .github/dependabot.yml to every active (non-archived) kept repo.

Detects ecosystems per repo and emits a tailored dependabot config:
  * `pip` if any requirements*.txt or pyproject.toml is found
  * `npm` if package.json is found at root or in frontend/
  * `github-actions` if .github/workflows/ has any *.yml

Skips repos that already have dependabot.yml.
"""
import base64
import json
import subprocess
import time
from pathlib import Path

OWNER = "AbdullahBakir97"

# Active kept repos = our case-study set (excludes the 21 archived)
ACTIVE = [
    # Flagship Django
    "Barber-Salon", "Jobs-Portal", "Django-Store",
    "Django--LMS--Learning-Management-System",
    # Mid-tier
    "Project-Management-Tool", "Py-Desktop-Expense_Tracker",
    "Python-Environment-Management-Tool", "Django-Followers-System",
    "API", "Pilot-Logbook", "Mini-RAG", "API-Client-Generator",
    "Content-Creator-Tool", "Tawil-Media---Advertisement",
    "Django-Reporting-System", "Django-Blog-app", "Trello-Clone-Services",
    "Automtion", "image-cropping", "Email-Sender", "Baeckrei",
    # Small named demos
    "Dj--To-Do", "Weather--App-django-vue.js", "Python-Django-join_with",
    "Py-Tetris-Game", "Space-Shooter", "Repo-Directory-Structure",
    "GitHub-Doc-Generator", "AI-KI", "2050-Bootstrap-Landing-page",
    "GitHub-Issues-Wall",
    # PyDev Apps
    "ai-quality-gate", "commit-craft", "issue-triage-bot",
    "pr-coach", "release-pilot", "repodoc-ai",
    # TS portfolio
    "Portfolio",
    # Profile readme
    "AbdullahBakir97",
]


def gh(args, body=None):
    return subprocess.run(["gh"] + args, input=body, capture_output=True, text=True)


def file_exists(repo, path):
    return gh(["api", f"repos/{OWNER}/{repo}/contents/{path}"]).returncode == 0


def list_dir(repo, path=""):
    res = gh(["api", f"repos/{OWNER}/{repo}/contents/{path}"])
    if res.returncode != 0:
        return []
    try:
        data = json.loads(res.stdout)
        return [item["name"] for item in data] if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def detect_ecosystems(repo):
    """Return list of (ecosystem, directory) tuples to register with dependabot."""
    top = list_dir(repo)
    eco = []

    has_pip = any(f in top for f in (
        "requirements.txt", "requirements-dev.txt", "pyproject.toml", "Pipfile"
    ))
    if has_pip:
        eco.append(("pip", "/"))

    if "package.json" in top:
        eco.append(("npm", "/"))
    elif "frontend" in top:
        sub = list_dir(repo, "frontend")
        if "package.json" in sub:
            eco.append(("npm", "/frontend"))

    if "backend" in top:
        sub = list_dir(repo, "backend")
        if any(f in sub for f in ("requirements.txt", "pyproject.toml")):
            eco.append(("pip", "/backend"))

    workflows = list_dir(repo, ".github/workflows")
    if workflows:
        eco.append(("github-actions", "/"))

    return eco


def render_dependabot_yml(ecosystems):
    if not ecosystems:
        return None
    lines = [
        "# Dependabot keeps dependencies fresh — opens PRs grouped by ecosystem.",
        "# Limits each kind to 5 open PRs at a time so review queues stay sane.",
        "version: 2",
        "updates:",
    ]
    for eco, directory in ecosystems:
        lines.extend([
            f'  - package-ecosystem: "{eco}"',
            f'    directory: "{directory}"',
            f'    schedule:',
            f'      interval: "weekly"',
            f'      day: "monday"',
            f'    open-pull-requests-limit: 5',
            f'    labels: ["dependencies", "{eco}"]',
            f'    commit-message:',
            f'      prefix: "deps({eco})"',
        ])
    return "\n".join(lines) + "\n"


def push_dependabot(repo):
    if file_exists(repo, ".github/dependabot.yml"):
        return {"repo": repo, "status": "skipped (already exists)"}
    eco = detect_ecosystems(repo)
    if not eco:
        return {"repo": repo, "status": "skipped (no detectable ecosystem)"}
    yml = render_dependabot_yml(eco)
    eco_summary = "+".join(f"{e}@{d}" for e, d in eco)
    payload = json.dumps({
        "message": "chore(deps): add Dependabot config for automated dependency updates",
        "content": base64.b64encode(yml.encode("utf-8")).decode("ascii"),
    })
    res = gh(
        ["api", "-X", "PUT",
         f"repos/{OWNER}/{repo}/contents/.github/dependabot.yml",
         "--input", "-"], payload
    )
    if res.returncode == 0:
        return {"repo": repo, "status": "added", "ecosystems": eco_summary}
    return {"repo": repo, "status": "ERROR", "err": res.stderr.strip()[:200]}


print(f"Adding Dependabot to {len(ACTIVE)} active repos...\n")
results = []
for i, repo in enumerate(ACTIVE, 1):
    r = push_dependabot(repo)
    note = r.get("ecosystems") or r.get("err") or ""
    print(f"  [{i:>2}/{len(ACTIVE)}] {repo:42} {r['status']:35} {note}")
    results.append(r)
    time.sleep(0.3)

# Summary
counts = {}
for r in results:
    key = r["status"].split(" (")[0] if "(" in r["status"] else r["status"]
    counts[key] = counts.get(key, 0) + 1
print(f"\nSummary: {counts}")

Path(r"C:\Users\abdul\AppData\Local\Temp\dependabot_results.json").write_text(
    json.dumps(results, indent=2), encoding="utf-8"
)
