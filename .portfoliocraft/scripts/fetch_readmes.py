"""Fetch the current README of each kept repo via the GitHub API.

Decides which repos need a brand-new README written for them. Categorizes
into: missing, stub (under 300 chars or just a title), or substantial.
"""
import json
import subprocess
import base64
from pathlib import Path

PLAN = Path(r"C:\Users\abdul\AppData\Local\Temp\repo_polish_plan.json")
README_STATE = Path(r"C:\Users\abdul\AppData\Local\Temp\readme_state.json")
OWNER = "AbdullahBakir97"

with PLAN.open(encoding="utf-8") as f:
    plan = json.load(f)


def fetch_readme(name: str) -> dict:
    """Returns dict {status, content?, sha?}.
    status in {'missing','stub','substantial','error'}
    """
    res = subprocess.run(
        ["gh", "api", f"/repos/{OWNER}/{name}/readme",
         "-H", "Accept: application/vnd.github+json"],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        if "Not Found" in res.stderr:
            return {"status": "missing", "content": "", "sha": None}
        return {"status": "error", "error": res.stderr.strip()[:300]}
    data = json.loads(res.stdout)
    sha = data.get("sha")
    encoded = data.get("content", "")
    try:
        decoded = base64.b64decode(encoded).decode("utf-8", errors="replace")
    except Exception as e:
        return {"status": "error", "error": str(e), "sha": sha}
    body = decoded.strip()
    n_chars = len(body)
    n_lines = body.count("\n") + 1 if body else 0
    if n_chars < 300 or n_lines < 8:
        return {"status": "stub", "content": body, "sha": sha,
                "n_chars": n_chars, "n_lines": n_lines}
    return {"status": "substantial", "content": body, "sha": sha,
            "n_chars": n_chars, "n_lines": n_lines}


state = []
for p in plan:
    name = p["name"]
    info = fetch_readme(name)
    info["name"] = name
    state.append(info)
    print(f"{name:42} {info['status']:11} "
          f"({info.get('n_chars', 0)} chars, {info.get('n_lines', 0)} lines)")

with README_STATE.open("w", encoding="utf-8") as f:
    json.dump(state, f, indent=2)

print()
counts = {}
for s in state:
    counts[s["status"]] = counts.get(s["status"], 0) + 1
print("Summary:", counts)
print("Saved ->", README_STATE)
