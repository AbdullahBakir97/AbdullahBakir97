"""Follow repository renames so the README never shows an old name.

GitHub keeps redirecting an old repo name to the new one, and the REST API
answers a request for the old name with the repo under its current name.
`resolve()` uses that; `sync_renames()` rewrites spotlight.json, the README
links and the spotlight SVG file names when a repo was renamed.

Used by .github/scripts/update_readme.py and scripts/build_current_focus.py.
Offline (no token, no network) everything is left as it is.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GH_USER = os.environ.get("GH_USER", "AbdullahBakir97")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
SPOTLIGHT = ROOT / ".github" / "scripts" / "spotlight.json"
README = ROOT / "README.md"
PROJECTS = ROOT / "assets" / "projects"

_cache: dict[str, dict | None] = {}


def _get(path: str):
    req = urllib.request.Request(f"https://api.github.com{path}",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": GH_USER})
    if GH_TOKEN:
        req.add_header("Authorization", f"Bearer {GH_TOKEN}")
    with urllib.request.urlopen(req, timeout=20) as r:  # follows the 301 of a renamed repo
        return json.load(r)


def resolve(name: str) -> dict | None:
    """The repo as GitHub knows it now, or None when it is gone, private or unreachable."""
    key = name.lower()
    if key not in _cache:
        try:
            repo = _get(f"/repos/{GH_USER}/{name}")
            _cache[key] = None if repo.get("private") else repo
        except Exception as e:
            print(f"  resolve {name}: {e}")
            _cache[key] = None
    return _cache[key]


def current_name(name: str) -> str:
    repo = resolve(name)
    return repo["name"] if repo else name


def _replace_in_readme(old: str, new: str) -> int:
    text = README.read_text(encoding="utf-8")
    patterns = [
        (rf"(github\.com/{re.escape(GH_USER)}/){re.escape(old)}(?=[\"/#?)\s])", rf"\g<1>{new}"),
        (rf"spotlight-{re.escape(old)}\.svg", f"spotlight-{new}.svg"),
        (rf"(alt=\"){re.escape(old)}(\s—)", rf"\g<1>{new}\g<2>"),
    ]
    count = 0
    for pat, rep in patterns:
        text, n = re.subn(pat, rep, text)
        count += n
    if count:
        README.write_text(text, encoding="utf-8")
    return count


def sync_renames() -> list[tuple[str, str]]:
    """Rename spotlight entries whose repo was renamed on GitHub. Returns [(old, new)]."""
    try:
        entries = json.loads(SPOTLIGHT.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  spotlight.json unreadable: {e}")
        return []
    renamed = []
    for s in entries:
        old = s["repo"]
        new = current_name(old)
        if new == old:
            continue
        s["repo"] = new
        if s.get("name") == old:
            s["name"] = new
        src, dst = PROJECTS / f"spotlight-{old}.svg", PROJECTS / f"spotlight-{new}.svg"
        if src.exists() and not dst.exists():
            src.rename(dst)
        n = _replace_in_readme(old, new)
        print(f"::warning::{old} was renamed to {new} on GitHub; updated spotlight.json and {n} README references")
        renamed.append((old, new))
    if renamed:
        SPOTLIGHT.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return renamed


if __name__ == "__main__":
    print(sync_renames() or "no renames")
