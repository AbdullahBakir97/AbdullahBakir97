"""Generate assets/current-focus.svg — what I'm working on, from real GitHub activity.

Six cards, one per repository with the most of my commits in the last 30 days.
Each card shows the repo name, its description, a status worked out from the
data, and its topics (or language) as tags:

  ACTIVE       commits in the last 7 days
  SHIPPING     a release published in the last 30 days
  MAINTAINING  commits in the last 30 days, nothing newer

Runs from readme.yml with GH_TOKEN. Without network it keeps the last file.
Pure SVG so it renders inside GitHub's <img> proxy.
"""
import datetime as dt
import json
import os
import textwrap
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "current-focus.svg"

GH_USER = os.environ.get("GH_USER", "AbdullahBakir97")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
SKIP = {GH_USER.lower()}

W, H = 1400, 560
COLS, GAP = 3, 22
CARD_W = (W - (COLS - 1) * GAP) // COLS
CARD_H = 258
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'JetBrains Mono',Menlo,Consolas,monospace"
TEXT, MUTED, BORDER, SURFACE = "#e6edf3", "#8b949e", "#30363d", "#161b22"
STATUS = {  # label: (accent, pill fill)
    "ACTIVE": ("#39d353", "#0d2818"),
    "SHIPPING": ("#F90001", "#2a0a0a"),
    "MAINTAINING": ("#58a6ff", "#0c1d33"),
}


def _gh(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": GH_USER})
    if GH_TOKEN:
        req.add_header("Authorization", f"Bearer {GH_TOKEN}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def fetch(limit=6):
    """[(name, description, status, tags, commits_30d)] for the busiest repos, or None offline."""
    now = dt.datetime.now(dt.timezone.utc)
    d7, d30 = now - dt.timedelta(days=7), now - dt.timedelta(days=30)
    repos = _gh(f"https://api.github.com/users/{GH_USER}/repos?type=owner&sort=pushed&per_page=40")
    rows = []
    for r in repos:
        if r.get("fork") or r.get("archived") or r["name"].lower() in SKIP:
            continue
        if dt.datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")) < d30:
            continue
        commits = _gh(f"https://api.github.com/repos/{GH_USER}/{r['name']}/commits"
                      f"?author={GH_USER}&since={d30:%Y-%m-%dT%H:%M:%SZ}&per_page=100")
        if not commits:
            continue
        last = max(dt.datetime.fromisoformat(c["commit"]["author"]["date"].replace("Z", "+00:00")) for c in commits)
        status = "ACTIVE" if last >= d7 else "MAINTAINING"
        if status != "ACTIVE":
            rel = _gh(f"https://api.github.com/repos/{GH_USER}/{r['name']}/releases?per_page=1")
            if rel and dt.datetime.fromisoformat(rel[0]["published_at"].replace("Z", "+00:00")) >= d30:
                status = "SHIPPING"
        tags = (r.get("topics") or [])[:4] or [t for t in [r.get("language")] if t]
        rows.append((len(commits), r["name"], r.get("description") or "", status, tags))
    rows.sort(reverse=True)
    return [(name, desc, status, tags, n) for n, name, desc, status, tags in rows[:limit]] or None


def card(x, y, name, desc, status, tags, commits):
    accent, pill = STATUS[status]
    lines = textwrap.wrap(desc or "No description yet.", 46)[:3]
    if len(textwrap.wrap(desc, 46)) > 3:
        lines[-1] = lines[-1].rstrip(" ,.;—-") + "…"
    out = [f'<g transform="translate({x} {y})">',
           f'<rect width="{CARD_W}" height="{CARD_H}" rx="14" fill="{SURFACE}" stroke="{BORDER}"/>',
           f'<rect width="{CARD_W}" height="4" rx="2" fill="{accent}"/>',
           f'<rect x="26" y="28" width="{len(status) * 9 + 34}" height="26" rx="13" fill="{pill}" stroke="{accent}"/>',
           f'<circle cx="41" cy="41" r="4" fill="{accent}"/>',
           f'<text x="52" y="45.5" font-family="{SANS}" font-size="11.5" font-weight="700" letter-spacing="1.6" fill="{accent}">{status}</text>',
           f'<text x="{CARD_W - 26}" y="46" text-anchor="end" font-family="{SANS}" font-size="13" fill="{MUTED}">'
           f'<tspan fill="{TEXT}" font-weight="700">{commits}</tspan> commits · 30 days</text>',
           f'<text x="26" y="98" font-family="{SANS}" font-size="25" font-weight="800" letter-spacing="-.3" fill="{TEXT}">{escape(name)}</text>']
    for i, ln in enumerate(lines):
        out.append(f'<text x="26" y="{132 + i * 22}" font-family="{SANS}" font-size="15" fill="{MUTED}">{escape(ln)}</text>')
    tx = 26
    for t in tags:
        w = len(t) * 8 + 24
        if tx + w > CARD_W - 20:
            break
        out.append(f'<rect x="{tx}" y="{CARD_H - 50}" width="{w}" height="26" rx="13" fill="none" stroke="{accent}" stroke-opacity=".55"/>'
                   f'<text x="{tx + w / 2}" y="{CARD_H - 32.5}" text-anchor="middle" font-family="{MONO}" font-size="12" fill="{accent}">{escape(t)}</text>')
        tx += w + 8
    out.append("</g>")
    return "".join(out)


def render(items):
    rows = (len(items) + COLS - 1) // COLS
    h = rows * CARD_H + (rows - 1) * GAP + 2
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" role="img" '
         f'aria-label="Current focus: {escape(", ".join(i[0] for i in items))}">']
    for i, it in enumerate(items):
        p.append(card((i % COLS) * (CARD_W + GAP), 1 + (i // COLS) * (CARD_H + GAP), *it))
    p.append("</svg>")
    return "".join(p)


def main():
    try:
        items = fetch()
    except Exception as e:
        print(f"current focus unavailable, keeping the last file: {e}")
        return
    if items:
        OUT.write_text(render(items), encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)} ({len(items)} cards)")


if __name__ == "__main__":
    main()
