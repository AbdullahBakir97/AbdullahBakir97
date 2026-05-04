"""Regenerate audit.md 'Repositories audited' appendix using LIVE data.

audit.json was a snapshot in time and doesn't know about LICENSE files we
added afterwards. This script:
  1. Loads audit.json findings
  2. For each repo, live-checks LICENSE presence via the GitHub API
  3. Marks license findings as 'resolved' if a LICENSE now exists
  4. Rewrites the appendix accordingly
"""
import json
import re
import datetime as dt
import subprocess
from pathlib import Path

REPO = Path(r"C:\Users\abdul\projects\Abdullah-Readme\src")
AUDIT_MD = REPO / ".portfoliocraft" / "audit.md"
AUDIT_JSON = REPO / ".portfoliocraft" / "audit.json"
REPOS_JSON = Path(r"C:\Users\abdul\AppData\Local\Temp\repos.json")
OWNER = "AbdullahBakir97"

with AUDIT_JSON.open(encoding="utf-8") as f:
    audit = json.load(f)
with REPOS_JSON.open(encoding="utf-8") as f:
    repos = json.load(f)

all_names = sorted([r["name"] for r in repos], key=str.lower)

# Group findings by repo + category
findings_by_repo = {}
for fi in audit["findings"]:
    repo = fi.get("repo")
    if not isinstance(repo, dict):
        continue
    n = repo.get("name")
    if n:
        findings_by_repo.setdefault(n, []).append(fi)

# Live-check LICENSE for repos that had license findings
def has_license(name: str) -> bool:
    res = subprocess.run(
        ["gh", "api", f"repos/{OWNER}/{name}/license"],
        capture_output=True, text=True
    )
    return res.returncode == 0


print("Live-checking LICENSE on repos with prior license findings...")
license_status = {}
for name, findings in findings_by_repo.items():
    if any(f["category"] == "license" for f in findings):
        ok = has_license(name)
        license_status[name] = ok
        print(f"  {name:42} {'has LICENSE' if ok else 'still missing'}")

# Now mark findings as resolved
def is_resolved(finding):
    if finding["category"] == "license":
        return license_status.get(finding["repo"]["name"], False)
    return False


# Stats
total_findings = len(audit["findings"])
resolved_count = sum(1 for f in audit["findings"] if is_resolved(f))

# Rebuild appendix
sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def severity_summary(name):
    findings = findings_by_repo.get(name, [])
    if not findings:
        return "clean"
    # Filter resolved ones
    open_findings = [f for f in findings if not is_resolved(f)]
    if not open_findings:
        return "all resolved ✅"
    counts = {}
    for f in open_findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: sev_order.get(kv[0], 99))
    return ", ".join(f"{c} {s}" for s, c in ordered)


def status_for(name):
    findings = findings_by_repo.get(name, [])
    if not findings:
        return "🟢 clean"
    open_ = [f for f in findings if not is_resolved(f)]
    if not open_:
        return "🟢 resolved"
    return "🟡 flagged"


with AUDIT_MD.open(encoding="utf-8") as f:
    existing = f.read()

# Strip prior appendix
existing = re.split(r"\n---\n\n## Repositories audited", existing, maxsplit=1)[0].rstrip()

today = dt.date(2026, 5, 4)
flagged = sum(1 for n in all_names if findings_by_repo.get(n) and any(not is_resolved(f) for f in findings_by_repo[n]))
clean_or_resolved = len(all_names) - flagged

lines = ["\n\n---\n\n## Repositories audited\n\n"]
lines.append(
    f"_Updated {today.isoformat()}. Coverage of {len(all_names)} owned non-fork repos. "
    f"**🟢 Clean** = no findings · **🟢 Resolved** = all original findings have been "
    f"fixed since the audit was generated · **🟡 Flagged** = open findings remain. "
    f"License presence is verified live against the GitHub API at table-render time._\n\n"
)
lines.append("| Repository | Status | Findings summary |\n")
lines.append("| --- | --- | --- |\n")
for n in all_names:
    lines.append(f"| [`{n}`](https://github.com/{OWNER}/{n}) | {status_for(n)} | {severity_summary(n)} |\n")

# Resolution-tracker section
fully_resolved = [n for n in all_names
                  if findings_by_repo.get(n)
                  and not any(not is_resolved(f) for f in findings_by_repo[n])]
license_resolved = sorted([n for n, ok in license_status.items() if ok])

if license_resolved:
    lines.append(f"\n### Resolved findings since audit was generated\n\n")
    lines.append(f"**License (high severity) — {len(license_resolved)} resolved:** ")
    lines.append(", ".join(f"[`{n}`](https://github.com/{OWNER}/{n})" for n in license_resolved))
    lines.append(" — all received an MIT LICENSE file via portfolio-polish pass.\n")

if fully_resolved:
    lines.append(f"\n**Fully clean now ({len(fully_resolved)}):** ")
    lines.append(", ".join(f"[`{n}`](https://github.com/{OWNER}/{n})" for n in fully_resolved))
    lines.append("\n")

new = existing + "".join(lines) + "\n"
AUDIT_MD.write_text(new, encoding="utf-8")
print(f"\nWrote audit.md appendix")
print(f"  total repos: {len(all_names)}")
print(f"  flagged:     {flagged}")
print(f"  clean+resolved: {clean_or_resolved}")
print(f"  fully resolved repos: {len(fully_resolved)}")
print(f"  license findings resolved: {len(license_resolved)}")
