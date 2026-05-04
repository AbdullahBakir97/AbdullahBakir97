"""Apply description / topics / README updates to GitHub via the gh CLI."""
import json
import subprocess
import base64
import time
from pathlib import Path

PLAN = Path(r"C:\Users\abdul\AppData\Local\Temp\repo_polish_plan.json")
README_STATE = Path(r"C:\Users\abdul\AppData\Local\Temp\readme_state.json")
README_OUT = Path(r"C:\Users\abdul\AppData\Local\Temp\generated_readmes")
OWNER = "AbdullahBakir97"

with PLAN.open(encoding="utf-8") as f:
    plan = json.load(f)
with README_STATE.open(encoding="utf-8") as f:
    state = {s["name"]: s for s in json.load(f)}


def gh(args, **kw):
    return subprocess.run(["gh"] + args, capture_output=True, text=True, **kw)


def gh_input(args, body: str):
    return subprocess.run(
        ["gh"] + args, input=body, capture_output=True, text=True
    )


results = {"desc_updated": [], "topics_updated": [], "readme_pushed": [],
           "errors": []}

for i, p in enumerate(plan, start=1):
    name = p["name"]
    print(f"[{i:>2}/{len(plan)}] {name}")

    # 1. Description
    if p["desc_changed"]:
        res = gh(["repo", "edit", f"{OWNER}/{name}",
                  "--description", p["new_desc"]])
        if res.returncode == 0:
            print(f"           desc: ok")
            results["desc_updated"].append(name)
        else:
            err = res.stderr.strip()[:200]
            print(f"           desc: ERROR -> {err}")
            results["errors"].append({"name": name, "kind": "desc", "err": err})

    # 2. Topics (replace via PUT /topics)
    if p["topics_changed"] and p["new_topics"]:
        body = json.dumps({"names": p["new_topics"]})
        res = gh_input(
            ["api", "-X", "PUT", f"/repos/{OWNER}/{name}/topics",
             "-H", "Accept: application/vnd.github.mercy-preview+json",
             "--input", "-"],
            body,
        )
        if res.returncode == 0:
            print(f"           topics: ok ({len(p['new_topics'])} tags)")
            results["topics_updated"].append(name)
        else:
            err = res.stderr.strip()[:200]
            print(f"           topics: ERROR -> {err}")
            results["errors"].append({"name": name, "kind": "topics", "err": err})

    # 3. README — only if missing or stub, and we generated content
    s = state.get(name, {})
    if s.get("status") in ("missing", "stub"):
        path = README_OUT / f"{name}.md"
        if not path.exists():
            print(f"           readme: SKIP (no generated file)")
        else:
            content = path.read_text(encoding="utf-8")
            b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
            payload = {
                "message": "docs(readme): initial portfolio-polish pass",
                "content": b64,
            }
            if s.get("sha"):
                payload["sha"] = s["sha"]
            res = gh_input(
                ["api", "-X", "PUT", f"/repos/{OWNER}/{name}/contents/README.md",
                 "--input", "-"],
                json.dumps(payload),
            )
            if res.returncode == 0:
                print(f"           readme: pushed ({len(content)} chars)")
                results["readme_pushed"].append(name)
            else:
                err = res.stderr.strip()[:200]
                print(f"           readme: ERROR -> {err}")
                results["errors"].append({"name": name, "kind": "readme", "err": err})

    # Be polite to the API
    time.sleep(0.4)

print()
print("=" * 60)
print("DONE")
print(f"  descriptions updated: {len(results['desc_updated'])}")
print(f"  topics updated:       {len(results['topics_updated'])}")
print(f"  READMEs pushed:       {len(results['readme_pushed'])}")
print(f"  errors:               {len(results['errors'])}")
if results["errors"]:
    print("\nErrors:")
    for e in results["errors"]:
        print(f"  - {e['name']:36} [{e['kind']:6}] {e['err']}")

# Save outcome log
out = Path(r"C:\Users\abdul\AppData\Local\Temp\polish_results.json")
out.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(f"\nResults log -> {out}")
