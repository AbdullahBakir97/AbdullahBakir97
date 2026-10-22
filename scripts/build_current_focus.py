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
import re
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
CARD_H = 236
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'JetBrains Mono',Menlo,Consolas,monospace"
TEXT, MUTED, BORDER, SURFACE = "#e6edf3", "#8b949e", "#30363d", "#161b22"
STATUS = {  # label: (accent, pill fill)
    "ACTIVE": ("#3fb950", ""),
    "SHIPPING": ("#ff652f", ""),
    "MAINTAINING": ("#58a6ff", ""),
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
        rows.append((len(commits), r["name"], r.get("description") or "", status, tags, r.get("language")))
    rows.sort(key=lambda r: r[0], reverse=True)
    return [(name, desc, status, tags, n, lang) for n, name, desc, status, tags, lang in rows[:limit]] or None


LANG_ICON = {"Python": "python", "TypeScript": "typescript", "JavaScript": "javascript", "Vue": "vuejs",
             "HTML": "html5", "CSS": "css3", "Go": "go", "Dockerfile": "docker"}
ICONS = ROOT / "assets" / "icons" / "lang"


def _icon(lang, x, y, s):
    f = ICONS / f"{LANG_ICON.get(lang, '')}-original.svg"
    if not lang or not f.exists():
        return ""
    t = f.read_text(encoding="utf-8")
    inner = re.sub(r"^<svg[^>]*>|</svg>\s*$", "", t.strip())
    vb = re.search(r'viewBox="([^"]+)"', t).group(1)
    return f'<svg x="{x}" y="{y}" width="{s}" height="{s}" viewBox="{vb}">{inner}</svg>'


NAMES = {"Django--LMS--Learning-Management-System": "Django LMS"}


def card(i, x, y, name, desc, status, tags, commits, lang=None):
    accent = STATUS[status][0]
    name = NAMES.get(name, name.replace("--", " ").replace("_", " "))
    lines = textwrap.wrap(desc or "No description yet.", 44)
    if len(lines) > 3:
        lines = lines[:3]
        lines[-1] = lines[-1].rstrip(" ,.;-") + "…"
    gid = f"fg{i}"
    out = [f'<g transform="translate({x} {y})">',
           f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{accent}" stop-opacity=".13"/>'
           f'<stop offset=".55" stop-color="{accent}" stop-opacity=".015"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></linearGradient>',
           f'<rect width="{CARD_W}" height="{CARD_H}" rx="16" fill="#0f141b"/>',
           f'<rect width="{CARD_W}" height="{CARD_H}" rx="16" fill="url(#{gid})" stroke="#ffffff" stroke-opacity=".1" stroke-width="1.2"/>',
           f'<line x1="24" y1=".6" x2="{CARD_W - 24}" y2=".6" stroke="{accent}" stroke-width="1.6"/>',
           f'<rect x="24" y="24" width="44" height="44" rx="12" fill="#ffffff" fill-opacity=".04" stroke="#ffffff" stroke-opacity=".1"/>',
           _icon(lang, 34, 34, 24) or f'<text x="46" y="52" text-anchor="middle" font-family="{MONO}" font-size="16" font-weight="700" fill="{accent}">{escape(name[:1])}</text>',
           f'<text x="82" y="44" font-family="{SANS}" font-size="20" font-weight="700" fill="#f0f6fc">{escape(name if len(name) <= 24 else name[:23] + "…")}</text>',
           f'<circle cx="87" cy="59" r="3.5" fill="{accent}"><animate attributeName="opacity" values="1;.3;1" dur="2s" repeatCount="indefinite"/></circle>',
           f'<text x="97" y="63" font-family="{MONO}" font-size="11.5" font-weight="700" letter-spacing="1.5" fill="{accent}">{status}</text>']
    for k, ln in enumerate(lines):
        out.append(f'<text x="24" y="{106 + k * 22}" font-family="{SANS}" font-size="14.5" fill="{MUTED}">{escape(ln)}</text>')
    out.append(f'<line x1="24" y1="{CARD_H - 62}" x2="{CARD_W - 24}" y2="{CARD_H - 62}" stroke="#ffffff" stroke-opacity=".07"/>')
    tx = 24
    for t in tags:
        w = len(t) * 7.6 + 22
        if tx + w > CARD_W - 150:
            break
        out.append(f'<rect x="{tx}" y="{CARD_H - 44}" width="{w}" height="24" rx="12" fill="#ffffff" fill-opacity=".03" stroke="#ffffff" stroke-opacity=".1"/>'
                   f'<text x="{tx + w / 2}" y="{CARD_H - 27.5}" text-anchor="middle" font-family="{MONO}" font-size="11.5" fill="#c9d1d9">{escape(t)}</text>')
        tx += w + 8
    out.append(f'<text x="{CARD_W - 24}" y="{CARD_H - 27}" text-anchor="end" font-family="{SANS}" font-size="12.5" fill="{MUTED}">'
               f'<tspan font-family="{MONO}" font-size="15" font-weight="700" fill="{accent}">{commits}</tspan> commits · 30d</text>')
    out.append("</g>")
    return "".join(out)


def render(items):
    rows = (len(items) + COLS - 1) // COLS
    h = rows * CARD_H + (rows - 1) * GAP + 2
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" role="img" '
         f'aria-label="Current focus: {escape(", ".join(i[0] for i in items))}">']
    for i, it in enumerate(items):
        p.append(card(i, (i % COLS) * (CARD_W + GAP), 1 + (i // COLS) * (CARD_H + GAP), *it))
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
