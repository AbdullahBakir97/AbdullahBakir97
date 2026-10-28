"""Generate assets/current-focus.svg — what I'm working on, from real GitHub activity.

Six cards, one per public repository with the most of my commits in the last
30 days, picked fresh on every run. Each card shows the repo name, its
description (my own words from OVERRIDES when I wrote some), a status worked
out from the data, and its topics (or language) as tags:

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
import sys
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
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
    "SHIPPED": ("#bc8cff", ""),
    "IN USE": ("#e3b341", ""),
}


def _gh(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": GH_USER})
    if GH_TOKEN:
        req.add_header("Authorization", f"Bearer {GH_TOKEN}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


# My own words for repos I care about. Everything else on a card is live: which
# repos show up, their order, status, commit count and language. A repo without
# an entry here uses its GitHub description and topics. Keys survive renames:
# a key that is not a current repo name is looked up through GitHub's redirect.
OVERRIDES = {
    "Ragolex": ("Ask your documents a question and get an answer with the sources. Hybrid search, citations and an MCP server.",
                ["fastapi", "pgvector", "rag", "mcp"]),
    "Django--LMS--Learning-Management-System": ("A course platform with payments, a social feed and a job board.",
                                                ["django", "vue", "channels", "celery"]),
    "Baeckrei": ("Bakery management system: production planning, recipe-based inventory, customer accounts and online orders.",
                 ["django", "vue", "postgres"]),
    "DevTrust": ("Tools I made to check code when AI writes part of it: test selection, PR review and LLM tracing.",
                 ["pypi", "github-apps", "testing"]),
    "PortfolioCraft": ("Turns your GitHub history into a portfolio, CV and README, as a CLI or a GitHub Action.",
                       ["cli", "github-action", "portfolio"]),
    "cortex": ("Profile widgets from your GitHub data, including graph-art: drawings found in the contribution calendar.",
               ["python", "svg", "github-action"]),
}


def _when(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def _my_commits(name, since, pages=3):
    """My commits in `name` since `since`: (count, newest date)."""
    count, newest = 0, None
    for page in range(1, pages + 1):
        batch = _gh(f"https://api.github.com/repos/{GH_USER}/{name}/commits"
                    f"?author={GH_USER}&since={since:%Y-%m-%dT%H:%M:%SZ}&per_page=100&page={page}")
        count += len(batch)
        for c in batch:
            d = _when(c["commit"]["author"]["date"])
            newest = d if newest is None or d > newest else newest
        if len(batch) < 100:
            break
    return count, newest


def _overrides(names):
    """OVERRIDES keyed by the repos' current names (lower case)."""
    out = {}
    for key, val in OVERRIDES.items():
        if key.lower() not in names:
            try:
                import repo_names
                key = repo_names.current_name(key)
            except Exception as e:
                print(f"  could not resolve {key}: {e}")
        out[key.lower()] = val
    return out


def fetch(limit=6):
    """The public repos with the most of my commits in the last 30 days.

    [(name, description, status, tags, footer_count, language, footer_text)]
    Forks, archived and private repos are left out. If fewer than `limit` repos
    had commits, the rest are the most recently pushed ones.
    """
    now = dt.datetime.now(dt.timezone.utc)
    d7, d30 = now - dt.timedelta(days=7), now - dt.timedelta(days=30)
    repos = [r for r in _gh(f"https://api.github.com/users/{GH_USER}/repos?type=owner&sort=pushed&per_page=100")
             if not r.get("fork") and not r.get("archived") and not r.get("private") and r["name"].lower() not in SKIP]
    if not repos:
        raise RuntimeError("no repositories returned")
    ranked, rest = [], []
    for r in repos:
        count, newest = 0, None
        if _when(r["pushed_at"]) >= d30:
            try:
                count, newest = _my_commits(r["name"], d30)
            except Exception as e:
                print(f"  {r['name']}: commits unavailable ({e})")
        (ranked if count else rest).append((r, count, newest))
    ranked.sort(key=lambda t: (t[1], t[2]), reverse=True)
    rest.sort(key=lambda t: t[0]["pushed_at"], reverse=True)
    picked = (ranked + rest)[:limit]
    ov = _overrides({r["name"].lower() for r in repos})
    out = []
    for r, count, newest in picked:
        desc, tags = ov.get(r["name"].lower(), (None, None))
        desc = desc or r.get("description") or ""
        tags = tags or (r.get("topics") or [])[:4] or ([r["language"].lower()] if r.get("language") else [])
        if count:
            status, footer = ("ACTIVE" if newest >= d7 else "MAINTAINING"), "commits · 30d"
        else:
            pushed = _when(r["pushed_at"])
            status, footer = "SHIPPED", f"updated {pushed:%b} {pushed.day}"
        try:
            rel = _gh(f"https://api.github.com/repos/{GH_USER}/{r['name']}/releases?per_page=1")
            if rel and rel[0].get("published_at") and _when(rel[0]["published_at"]) >= d30 and status != "ACTIVE":
                status = "SHIPPING"
        except Exception:
            pass
        out.append((r["name"], desc, status, tags, count or None, r.get("language"), footer))
    return out


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


def card(i, x, y, name, desc, status, tags, commits, lang=None, footer="commits · 30d"):
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
        if tx + w > CARD_W - 44 - (60 + len(footer) * 6.6 if commits else len(footer) * 6.9):
            break
        out.append(f'<rect x="{tx}" y="{CARD_H - 44}" width="{w}" height="24" rx="12" fill="#ffffff" fill-opacity=".03" stroke="#ffffff" stroke-opacity=".1"/>'
                   f'<text x="{tx + w / 2}" y="{CARD_H - 27.5}" text-anchor="middle" font-family="{MONO}" font-size="11.5" fill="#c9d1d9">{escape(t)}</text>')
        tx += w + 8
    if commits:
        out.append(f'<text x="{CARD_W - 24}" y="{CARD_H - 27}" text-anchor="end" font-family="{SANS}" font-size="12.5" fill="{MUTED}">'
                   f'<tspan font-family="{MONO}" font-size="15" font-weight="700" fill="{accent}">{commits}</tspan> {escape(footer)}</text>')
    else:
        out.append(f'<text x="{CARD_W - 24}" y="{CARD_H - 27}" text-anchor="end" font-family="{SANS}" font-size="12.5" fill="{accent}">{escape(footer)}</text>')
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
