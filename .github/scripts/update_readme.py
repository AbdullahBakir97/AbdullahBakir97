"""Refresh README.md marker blocks from live data.

Markers handled:
  ACTIVITY                - recent public GitHub events
  LATEST_RELEASES         - newest releases across user's repos
  PAGESPEED               - Google PageSpeed Insights scores
  HIGHLIGHTS_STATS        - current-year commits/PRs/new-repos
  SKYLINE_LINK            - skyline.github.com link with current year
  CITY_LINK               - GithubCity link with current year

Each section is independent: a failure logs a warning and leaves the existing
block intact instead of crashing the whole run.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import random
import re
import sys
import urllib.parse
from html import escape as html_escape
from pathlib import Path
from typing import Callable

import requests

GH_USER = os.environ.get("GH_USER", "AbdullahBakir97")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
PSI_API_KEY = os.environ.get("PSI_API_KEY", "")
PSI_URL = os.environ.get("PSI_URL", "https://kharsa-style.de/")
README_PATH = os.environ.get("README_PATH", "README.md")
START_YEAR = int(os.environ.get("START_YEAR", "2024"))

GH_HEADERS = {"Accept": "application/vnd.github+json"}
if GH_TOKEN:
    GH_HEADERS["Authorization"] = f"Bearer {GH_TOKEN}"

CURRENT_YEAR = dt.datetime.now(dt.timezone.utc).year


def warn(msg: str) -> None:
    print(f"::warning::{msg}", file=sys.stderr)


def replace_block(text: str, marker: str, new_body: str) -> str:
    pattern = re.compile(
        rf"(<!--\s*{re.escape(marker)}:START\s*-->)(.*?)(<!--\s*{re.escape(marker)}:END\s*-->)",
        flags=re.DOTALL,
    )
    if not pattern.search(text):
        warn(f"marker {marker} not found in README — skipping")
        return text
    replacement = rf"\1\n{new_body}\n\3"
    return pattern.sub(replacement, text, count=1)


# --- ACTIVITY -----------------------------------------------------------------

def _repo_link(name: str) -> str:
    return f"[`{name}`](https://github.com/{name})"


def _push_event(e: dict) -> str | None:
    """GitHub's PushEvent payload has been getting trimmed — many entries now
    return only {before, head, push_id, ref, repository_id} with no `size`,
    `distinct_size`, or `commits`. Trust whatever count we can find; if all we
    have is a `head` SHA, treat it as ≥1 commit so the feed isn't silently empty."""
    payload = e["payload"]
    commits = payload.get("commits") or []
    n = payload.get("size") or payload.get("distinct_size") or len(commits)
    if n == 0 and payload.get("head"):
        n = 1  # stripped payload — still a real push
    if n == 0:
        return None  # branch create/delete with no head — truly nothing
    plural = "" if n == 1 else "s"
    return f"⬆️ Pushed {n} commit{plural} to {_repo_link(e['repo']['name'])}"


def _pr_event(e: dict) -> str:
    pr = e["payload"]["pull_request"]
    repo = e["repo"]["name"]
    url = pr.get("html_url") or f"https://github.com/{repo}/pull/{pr['number']}"
    return (
        f"🔀 {e['payload']['action'].title()} PR "
        f"[#{pr['number']}]({url}) in {_repo_link(repo)}"
    )


def _issue_event(e: dict) -> str:
    issue = e["payload"]["issue"]
    repo = e["repo"]["name"]
    url = issue.get("html_url") or f"https://github.com/{repo}/issues/{issue['number']}"
    return (
        f"❗ {e['payload']['action'].title()} issue "
        f"[#{issue['number']}]({url}) in {_repo_link(repo)}"
    )


def _release_event(e: dict) -> str:
    rel = e["payload"]["release"]
    repo = e["repo"]["name"]
    url = rel.get("html_url") or f"https://github.com/{repo}/releases/tag/{rel.get('tag_name', '')}"
    return f"📦 Released [`{rel.get('tag_name', '?')}`]({url}) of {_repo_link(repo)}"


def _create_event(e: dict) -> str | None:
    ref_type = e["payload"].get("ref_type")
    if ref_type not in ("repository", "tag"):
        return None
    return f"✨ Created {ref_type} {_repo_link(e['repo']['name'])}"


def _fork_event(e: dict) -> str:
    return f"🍴 Forked {_repo_link(e['repo']['name'])}"


EVENT_FORMATTERS: dict[str, Callable[[dict], str | None]] = {
    "PushEvent": _push_event,
    "PullRequestEvent": _pr_event,
    "IssuesEvent": _issue_event,
    "ReleaseEvent": _release_event,
    "CreateEvent": _create_event,
    "ForkEvent": _fork_event,
}


def fetch_activity(limit: int = 6) -> str:
    """Recent public activity grouped by repository: a table instead of one line per push."""
    r = requests.get(
        f"https://api.github.com/users/{GH_USER}/events/public?per_page=100",
        headers=GH_HEADERS,
        timeout=20,
    )
    r.raise_for_status()
    repos: dict[str, dict] = {}
    for event in r.json():
        name = event["repo"]["name"].split("/")[-1]
        if name.lower() == GH_USER.lower():
            continue  # the profile repo itself is README plumbing
        row = repos.setdefault(name, {"commits": 0, "prs": 0, "other": 0, "last": event["created_at"]})
        kind = event["type"]
        if kind == "PushEvent":
            p = event["payload"]
            row["commits"] += p.get("size") or p.get("distinct_size") or len(p.get("commits") or []) or 1
        elif kind == "PullRequestEvent":
            row["prs"] += 1
        else:
            row["other"] += 1
        row["last"] = max(row["last"], event["created_at"])
    if not repos:
        return "_No recent public activity._"
    top = sorted(repos.items(), key=lambda kv: kv[1]["last"], reverse=True)[:limit]
    out = ["| Repository | Commits | Pull requests | Last activity |", "| :-- | --: | --: | :-- |"]
    for name, row in top:
        out.append(f"| [{name}](https://github.com/{GH_USER}/{name}) | {row['commits']} | {row['prs']} | "
                   f"{_humanize_date(row['last'])} |")
    return "\n".join(out)


# --- LATEST RELEASES ----------------------------------------------------------

RELEASES_QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(first: 100, ownerAffiliations: OWNER, orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        name
        url
        releases(first: 1, orderBy: {field: CREATED_AT, direction: DESC}) {
          nodes { name tagName publishedAt url }
        }
      }
    }
  }
}
"""


def graphql(query: str, variables: dict) -> dict:
    if not GH_TOKEN:
        raise RuntimeError("GH_TOKEN required for GraphQL")
    r = requests.post(
        "https://api.github.com/graphql",
        headers={**GH_HEADERS, "Content-Type": "application/json"},
        json={"query": query, "variables": variables},
        timeout=30,
    )
    r.raise_for_status()
    payload = r.json()
    if "errors" in payload:
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    return payload["data"]


def fetch_releases(limit: int = 5) -> str:
    data = graphql(RELEASES_QUERY, {"login": GH_USER})
    rows = []
    for repo in data["user"]["repositories"]["nodes"]:
        for rel in repo["releases"]["nodes"]:
            rows.append(
                {
                    "repo": repo["name"],
                    "tag": rel["tagName"],
                    "name": rel["name"] or rel["tagName"],
                    "url": rel["url"],
                    "at": rel["publishedAt"],
                }
            )
    rows.sort(key=lambda r: r["at"], reverse=True)
    if not rows:
        return "_No releases yet._"
    out = ["| Project | Version | Released | Notes |", "| :-- | :-- | :-- | :-- |"]
    for row in rows[:limit]:
        notes = row["name"]
        if notes.startswith(row["tag"]):
            notes = notes[len(row["tag"]):].lstrip(" —-:") or "—"
        out.append(f"| **{row['repo']}** | [`{row['tag']}`]({row['url']}) | {row['at'][:10]} | {notes} |")
    return "\n".join(out)


# --- PAGESPEED ----------------------------------------------------------------

PSI_CATEGORIES = ["PERFORMANCE", "ACCESSIBILITY", "BEST_PRACTICES", "SEO"]
PSI_LABELS = {
    "PERFORMANCE": "Performance",
    "ACCESSIBILITY": "Accessibility",
    "BEST_PRACTICES": "Best_Practices",
    "SEO": "SEO",
}


def score_color(pct: int) -> str:
    if pct >= 90:
        return "success"
    if pct >= 50:
        return "yellow"
    return "red"


PSI_AUDITS = [("largest-contentful-paint", "LCP"), ("cumulative-layout-shift", "CLS"),
              ("total-blocking-time", "TBT"), ("first-contentful-paint", "FCP")]
PAGESPEED_SVG = "pagespeed.svg"


def _psi_run(strategy: str) -> dict:
    params = [("url", PSI_URL), ("strategy", strategy)] + [("category", c) for c in PSI_CATEGORIES]
    if PSI_API_KEY:
        params.append(("key", PSI_API_KEY))
    url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?" + urllib.parse.urlencode(params)
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 429:
                hint = "" if PSI_API_KEY else " (set the PSI_API_KEY secret to lift the shared quota)"
                raise RuntimeError(f"PSI rate-limited{hint}")
            r.raise_for_status()
            lh = r.json().get("lighthouseResult", {})
            cats = lh.get("categories", {})
            scores = {c: round(cats[c.lower().replace("_", "-")]["score"] * 100)
                      for c in PSI_CATEGORIES if cats.get(c.lower().replace("_", "-"), {}).get("score") is not None}
            audits = lh.get("audits", {})
            vitals = [(label, audits[k].get("displayValue", "—"), audits[k].get("score"))
                      for k, label in PSI_AUDITS if k in audits]
            return {"scores": scores, "vitals": vitals}
        except Exception as e:
            last_exc = e
            if attempt < 2:
                import time
                time.sleep(5 * (attempt + 1))
    raise last_exc  # type: ignore[misc]


def _psi_color(v: float) -> tuple[str, str]:
    if v >= 90:
        return "#0cce6b", "#0b2a1a"
    if v >= 50:
        return "#ffa400", "#2e2208"
    return "#ff4e42", "#2e0f0e"


def pagespeed_svg(mobile: dict, desktop: dict | None, site: str, host: str, updated: str) -> str:
    W, H = 1400, 760
    B, G = SEC_BLUE, SEC_GREEN
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
         f'aria-label="Lighthouse scores for {html_escape(host)}: '
         + ", ".join(f"{PSI_LABELS[c].replace('_', ' ')} {v}" for c, v in mobile["scores"].items()) + '">']
    s.append(f'<text x="6" y="40" font-family="{SEC_SANS}" font-size="30" font-weight="700" fill="#ffffff">{html_escape(site)}'
             f'<tspan fill="#8b949e" font-weight="400"> · {html_escape(host)}</tspan></text>'
             f'<text x="6" y="76" font-family="{SEC_SANS}" font-size="20" fill="#8b949e">Live salon website built on my '
             f'<tspan fill="{B}" font-weight="700">Barber-Salon</tspan> platform</text>'
             f'<text x="{W - 6}" y="76" text-anchor="end" font-family="{SEC_SANS}" font-size="18" fill="#8b949e">updated {updated}</text>')
    # mobile tab + rings
    s.append(f'<path d="M6 150 V118 a10 10 0 0 1 10-10 H146 a10 10 0 0 1 10 10 V150" fill="#161b22" stroke="#30363d" stroke-width="1.5"/>'
             f'<text x="81" y="137" text-anchor="middle" font-family="{SEC_MONO}" font-size="16" font-weight="700" letter-spacing="2.5" fill="#ffffff">MOBILE</text>'
             f'<line x1="0" y1="150" x2="{W}" y2="150" stroke="#30363d" stroke-width="1.5"/><line x1="0" y1="430" x2="{W}" y2="430" stroke="#30363d" stroke-width="1.5"/>')
    cats = [c for c in PSI_CATEGORIES if c in mobile["scores"]]
    for i, c in enumerate(cats):
        v = mobile["scores"][c]
        col, bg = _psi_color(v)
        cx, cy, r = W / len(cats) * (i + .5), 268, 82
        circ = 2 * math.pi * r
        s.append(f'<circle cx="{cx:.0f}" cy="{cy}" r="{r}" fill="{bg}" stroke="{bg}" stroke-width="14"/>'
                 f'<circle cx="{cx:.0f}" cy="{cy}" r="{r}" fill="none" stroke="{col}" stroke-width="14" stroke-linecap="round" '
                 f'stroke-dasharray="{circ * v / 100:.1f} {circ:.1f}" transform="rotate(-90 {cx:.0f} {cy})"/>'
                 f'<text x="{cx:.0f}" y="{cy + 20}" text-anchor="middle" font-family="{SEC_SANS}" font-size="56" font-weight="800" fill="{col}">{v}</text>'
                 f'<text x="{cx:.0f}" y="{cy + 134}" text-anchor="middle" font-family="{SEC_SANS}" font-size="22" fill="#ffffff">{PSI_LABELS[c].replace("_", " ")}</text>')
    y = 488
    if desktop and desktop.get("scores"):
        parts, x = [], 190
        s.append(f'<text x="6" y="{y}" font-family="{SEC_MONO}" font-size="16" font-weight="700" letter-spacing="3" fill="#8b949e">DESKTOP</text>')
        for c in cats:
            if c not in desktop["scores"]:
                continue
            v = desktop["scores"][c]
            label = PSI_LABELS[c].replace("_", " ")
            s.append(f'<text x="{x}" y="{y}" font-family="{SEC_SANS}" font-size="20" fill="#ffffff">{label} '
                     f'<tspan font-size="26" font-weight="800" fill="{_psi_color(v)[0]}">{v}</tspan></text>')
            x += len(label) * 11 + 92
    if mobile.get("vitals"):
        s.append(f'<text x="6" y="{y + 66}" font-family="{SEC_MONO}" font-size="16" font-weight="700" letter-spacing="3.5" fill="{G}">// CORE WEB VITALS · MOBILE</text>')
        t0, t1 = y + 88, H - 50
        s.append(f'<line x1="0" y1="{t0}" x2="{W}" y2="{t0}" stroke="#30363d" stroke-width="1.5"/><line x1="0" y1="{t1}" x2="{W}" y2="{t1}" stroke="#30363d" stroke-width="1.5"/>')
        tw = W / len(mobile["vitals"])
        for i, (label, value, score) in enumerate(mobile["vitals"]):
            x = i * tw
            if i:
                s.append(f'<line x1="{x}" y1="{t0}" x2="{x}" y2="{t1}" stroke="#30363d" stroke-width="1.5"/>')
            sc = 0 if score is None else score * 100
            state, col = ("good", "#0cce6b") if sc >= 90 else ("needs work", "#ffa400") if sc >= 50 else ("poor", "#ff4e42")
            s.append(f'<text x="{x + 26}" y="{t0 + 34}" font-family="{SEC_MONO}" font-size="15" font-weight="700" letter-spacing="2.5" fill="#8b949e">{label}</text>'
                     f'<text x="{x + 24}" y="{t0 + 84}" font-family="{SEC_SANS}" font-size="44" font-weight="800" fill="{B}">{html_escape(value)}</text>'
                     f'<circle cx="{x + 32}" cy="{t0 + 111}" r="6" fill="{col}"/><text x="{x + 46}" y="{t0 + 117}" font-family="{SEC_SANS}" font-size="18" font-weight="600" fill="{col}">{state}</text>')
    lg = [("#0cce6b", "90–100 good"), ("#ffa400", "50–89 needs work"), ("#ff4e42", "0–49 poor")]
    x = 6
    for col, txt in lg:
        s.append(f'<circle cx="{x + 7}" cy="{H - 16}" r="7" fill="{col}"/><text x="{x + 22}" y="{H - 10}" font-family="{SEC_SANS}" font-size="17" fill="#8b949e">{txt}</text>')
        x += len(txt) * 9 + 54
    s.append(f'<text x="{W - 6}" y="{H - 10}" text-anchor="end" font-family="{SEC_SANS}" font-size="16" fill="#6e7681">'
             'not affiliated with Google · PageSpeed Insights is a trademark of Google LLC</text></svg>')
    return "".join(s)


def fetch_pagespeed() -> str:
    """Render assets/stats/pagespeed.svg. When Lighthouse can't be reached the previous
    image stays; with no image at all the section stays empty instead of showing a placeholder."""
    dest = Path(ASSETS_DIR) / "stats" / PAGESPEED_SVG
    host = urllib.parse.urlparse(PSI_URL).netloc or PSI_URL
    try:
        mobile = _psi_run("mobile")
        if not mobile["scores"]:
            raise RuntimeError("no scores in the PSI response")
        try:
            desktop = _psi_run("desktop")
        except Exception as e:
            warn(f"desktop PSI run failed, showing mobile only: {e}")
            desktop = None
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(pagespeed_svg(mobile, desktop, "Kharsa Style", host,
                                      dt.date.today().strftime("%b %-d, %Y") if os.name != "nt" else dt.date.today().isoformat()),
                        encoding="utf-8")
    except Exception as e:
        warn(f"PageSpeed unavailable, keeping the last image: {e}")
    if not dest.exists():
        return ""
    return ('<p align="center"><img src="./assets/sections/pagespeed.svg" width="100%" alt="09 · Live Performance"/></p>\n\n'
            f'<p align="center"><a href="https://pagespeed.web.dev/analysis?url={urllib.parse.quote(PSI_URL, safe="")}">'
            f'<img src="./{ASSETS_DIR}/stats/{PAGESPEED_SVG}" width="100%" alt="Lighthouse scores for {host}"/></a></p>\n\n'
            '<p align="center"><img src="./assets/sections/splitter.svg" width="100%" alt=""/></p>')


# --- HIGHLIGHTS_STATS ---------------------------------------------------------

STATS_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      commitContributionsByRepository(maxRepositories: 100) {
        repository { name }
      }
    }
  }
}
"""


def fetch_year_stats() -> str:
    start = f"{CURRENT_YEAR}-01-01T00:00:00Z"
    end = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = graphql(STATS_QUERY, {"login": GH_USER, "from": start, "to": end})
    cc = data["user"]["contributionsCollection"]
    # `totalRepositoriesWithContributedCommits` was removed from the GraphQL
    # schema; derive it from commitContributionsByRepository instead.
    active_repos = len({
        n["repository"]["name"]
        for n in cc.get("commitContributionsByRepository", [])
    })

    new_repos_q = (
        f"https://api.github.com/search/repositories?q="
        f"user:{GH_USER}+created:>={CURRENT_YEAR}-01-01"
    )
    new_repos_count = 0
    try:
        rr = requests.get(new_repos_q, headers=GH_HEADERS, timeout=20)
        rr.raise_for_status()
        new_repos_count = rr.json().get("total_count", 0)
    except Exception as e:
        warn(f"new-repos count failed: {e}")

    return (
        '<p align="center">'
        f'<img src="https://img.shields.io/badge/Commits-{cc["totalCommitContributions"]}-30363d?style=for-the-badge&logo=git&logoColor=white" alt="Commits" /> '
        f'<img src="https://img.shields.io/badge/PRs-{cc["totalPullRequestContributions"]}-30363d?style=for-the-badge&logo=github&logoColor=white" alt="PRs" /> '
        f'<img src="https://img.shields.io/badge/New_Repos-{new_repos_count}-30363d?style=for-the-badge&logo=github&logoColor=white" alt="New repos" /> '
        f'<img src="https://img.shields.io/badge/Active_in-{active_repos}_repos-30363d?style=for-the-badge&logo=github&logoColor=white" alt="Active repos" />'
        "</p>"
    )


# --- PER-YEAR CONTRIBUTION ASSETS ---------------------------------------------
# GitHub's GraphQL contributionCalendar is the only authoritative per-year source.
# Render two visualizations from the same data:
#   * heatmap-{year}.svg   — classic 53×7 grid (used by the snake section's small row)
#   * skyline-{year}.svg   — isometric weekly bars (used by the Skyline section)
# Files write into ./assets/ and are committed by readme.yml alongside README.md.

ASSETS_DIR = os.environ.get("ASSETS_DIR", "assets")

CONTRIB_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount color weekday }
        }
      }
    }
  }
}
"""


def fetch_contribution_calendar(year: int) -> dict:
    start = f"{year}-01-01T00:00:00Z"
    end = (
        dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if year == CURRENT_YEAR
        else f"{year}-12-31T23:59:59Z"
    )
    data = graphql(CONTRIB_QUERY, {"login": GH_USER, "from": start, "to": end})
    return data["user"]["contributionsCollection"]["contributionCalendar"]


def _heatmap_color(count: int, fallback: str) -> str:
    # GitHub dark-theme palette — the GraphQL `color` field is theme-dependent
    # and sometimes empty for zero days, so we map by count for consistency.
    if count <= 0:
        return "#161b22"
    if count < 4:
        return "#0e4429"
    if count < 8:
        return "#006d32"
    if count < 12:
        return "#26a641"
    return fallback or "#39d353"


def render_heatmap_svg(year: int, calendar: dict, dest: str) -> None:
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]
    cell, gap = 11, 2
    pad_x, pad_top = 8, 24
    width = pad_x * 2 + len(weeks) * (cell + gap)
    height = pad_top + 7 * (cell + gap) + 8

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{GH_USER} contributions in {year}">',
        '<rect width="100%" height="100%" fill="#0d1117"/>',
        '<style>text{font-family:-apple-system,Segoe UI,sans-serif;font-size:11px;'
        'fill:#8b949e}</style>',
        f'<text x="{pad_x}" y="16">'
        f'<tspan font-weight="600" fill="#c9d1d9">{total:,}</tspan> '
        f'contributions in {year}</text>',
    ]

    for wi, week in enumerate(weeks):
        x = pad_x + wi * (cell + gap)
        for day in week["contributionDays"]:
            di = day["weekday"]
            y = pad_top + di * (cell + gap)
            color = _heatmap_color(day["contributionCount"], day.get("color") or "")
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'rx="2" ry="2" fill="{color}"><title>{day["contributionCount"]} '
                f'on {day["date"]}</title></rect>'
            )

    parts.append("</svg>")
    with open(dest, "w", encoding="utf-8") as f:
        f.write("".join(parts))


_ISO_COS = math.cos(math.radians(30))   # ≈ 0.8660
_ISO_SIN = math.sin(math.radians(30))   # = 0.5


def _iso(x: float, y: float, z: float = 0.0) -> tuple[float, float]:
    """30° isometric projection — viewer at (+X, +Y, +Z) infinity.
    Visible faces of any cuboid: top (+Z), right (+X), left (+Y)."""
    return ((x - y) * _ISO_COS, (x + y) * _ISO_SIN - z)


# GitHub-style intensity palette: (top, right, left) — top brightest, left in shadow.
# 5 buckets matching the official contribution-graph levels.
_SKYLINE_PALETTE: list[tuple[str, str, str]] = [
    ("#1f242c", "#161b22", "#0d1117"),   # 0 contributions  — flat ground tile
    ("#2ea043", "#1f7a35", "#155724"),   # 1–3
    ("#39d353", "#2ea043", "#1a8c30"),   # 4–7
    ("#56d364", "#3fb950", "#238636"),   # 8–11
    ("#7ee787", "#56d364", "#26a641"),   # 12+
]


def _palette_for(count: int) -> tuple[str, str, str]:
    if count <= 0:
        return _SKYLINE_PALETTE[0]
    if count < 4:
        return _SKYLINE_PALETTE[1]
    if count < 8:
        return _SKYLINE_PALETTE[2]
    if count < 12:
        return _SKYLINE_PALETTE[3]
    return _SKYLINE_PALETTE[4]


def _interp(p1: tuple[float, float], p2: tuple[float, float], t: float) -> tuple[float, float]:
    return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))


def render_skyline_svg(year: int, calendar: dict, dest: str) -> None:
    """Render contributions as an animated cinematic isometric 'modern city'.

    Stack of 12 perceptual depth layers:
       1  Deep-space radial sky
       2  Two soft nebula blobs (violet + cyan), animated hue-rotate
       3  Animated starfield (~80 stars, 5 staggered twinkle classes)
       4  Distant moon with crater stipple + bloom filter
       5  Aurora ribbon path with wave-translation animation
       6  Subtle horizon glow line
       7  Ground platform + iso grid lines (depth cues)
       8  366 buildings, depth-sorted painter's-algorithm rendering,
          three lit faces per cuboid + a top-edge rim highlight on tall ones
       9  Animated window lights (flicker classes) on count≥6 days
      10  Antennas + pulse halos on count≥12 'landmark' buildings
      11  Floating embers rising, varied speeds & delays
      12  Vignette + HUD typography (ghost-year, username, totals, footer)

    All randomness seeded on `year` so renders are reproducible run-to-run
    (no daily commit churn from animation noise).
    """
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]
    n_weeks = len(weeks)

    cell_w = 14.0
    cell_d = 14.0
    max_h = 140.0

    max_count = 1
    avg_count = 0.0
    nonzero_days = 0
    for week in weeks:
        for day in week["contributionDays"]:
            c = day["contributionCount"]
            if c > max_count:
                max_count = c
            if c > 0:
                avg_count += c
                nonzero_days += 1
    avg_count = avg_count / nonzero_days if nonzero_days else 0.0

    extents_x = n_weeks * cell_w
    extents_y = 7 * cell_d

    bbox_pts = [
        _iso(0, 0, 0), _iso(extents_x, 0, 0),
        _iso(extents_x, extents_y, 0), _iso(0, extents_y, 0),
        _iso(0, 0, max_h), _iso(extents_x, 0, max_h),
        _iso(extents_x, extents_y, max_h), _iso(0, extents_y, max_h),
    ]
    min_x = min(p[0] for p in bbox_pts)
    max_x = max(p[0] for p in bbox_pts)
    min_y = min(p[1] for p in bbox_pts)
    max_y = max(p[1] for p in bbox_pts)

    pad_x = 56
    pad_top = 90
    pad_bottom = 56

    width = int(math.ceil(max_x - min_x)) + pad_x * 2
    height = int(math.ceil(max_y - min_y)) + pad_top + pad_bottom

    ox = pad_x - min_x
    oy = pad_top - min_y

    def fmt_pts(*corners: tuple[float, float]) -> str:
        return " ".join(f"{c[0] + ox:.2f},{c[1] + oy:.2f}" for c in corners)

    rng = random.Random(year * 9973 + 17)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{GH_USER} {year} contribution skyline — animated modern city">',
        # ---- DEFS: gradients, filters, animations ----
        '<defs>',
        # Sky — deep-space radial focused at horizon
        '<radialGradient id="sky" cx="50%" cy="100%" r="115%">'
        '<stop offset="0%" stop-color="#1b2447"/>'
        '<stop offset="35%" stop-color="#0d1430"/>'
        '<stop offset="100%" stop-color="#02030a"/>'
        '</radialGradient>',
        # Nebula blobs
        '<radialGradient id="nebulaA" cx="22%" cy="28%" r="55%">'
        '<stop offset="0%" stop-color="#7c3aed" stop-opacity="0.32"/>'
        '<stop offset="60%" stop-color="#7c3aed" stop-opacity="0.06"/>'
        '<stop offset="100%" stop-color="#7c3aed" stop-opacity="0"/>'
        '</radialGradient>',
        '<radialGradient id="nebulaB" cx="78%" cy="18%" r="48%">'
        '<stop offset="0%" stop-color="#06b6d4" stop-opacity="0.28"/>'
        '<stop offset="60%" stop-color="#06b6d4" stop-opacity="0.05"/>'
        '<stop offset="100%" stop-color="#06b6d4" stop-opacity="0"/>'
        '</radialGradient>',
        # Aurora ribbon — multi-stop horizontal sweep
        '<linearGradient id="aurora" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0%" stop-color="#39d353" stop-opacity="0"/>'
        '<stop offset="22%" stop-color="#34d399" stop-opacity="0.55"/>'
        '<stop offset="48%" stop-color="#06b6d4" stop-opacity="0.85"/>'
        '<stop offset="72%" stop-color="#a855f7" stop-opacity="0.55"/>'
        '<stop offset="100%" stop-color="#a855f7" stop-opacity="0"/>'
        '</linearGradient>',
        # Moon
        '<radialGradient id="moon" cx="38%" cy="38%" r="62%">'
        '<stop offset="0%" stop-color="#fffbeb"/>'
        '<stop offset="55%" stop-color="#fde68a"/>'
        '<stop offset="100%" stop-color="#fbbf24" stop-opacity="0.55"/>'
        '</radialGradient>',
        # Ground platform (deep with slight cyan-bias toward horizon)
        '<linearGradient id="ground" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#1f2a3d"/>'
        '<stop offset="55%" stop-color="#0d1117"/>'
        '<stop offset="100%" stop-color="#02030a"/>'
        '</linearGradient>',
        # Halo (used behind landmark buildings)
        '<radialGradient id="halo" cx="50%" cy="50%" r="50%">'
        '<stop offset="0%" stop-color="#7ee787" stop-opacity="0.55"/>'
        '<stop offset="60%" stop-color="#39d353" stop-opacity="0.18"/>'
        '<stop offset="100%" stop-color="#39d353" stop-opacity="0"/>'
        '</radialGradient>',
        # Vignette
        '<radialGradient id="vignette" cx="50%" cy="55%" r="78%">'
        '<stop offset="60%" stop-color="#000" stop-opacity="0"/>'
        '<stop offset="100%" stop-color="#000" stop-opacity="0.55"/>'
        '</radialGradient>',
        # Soft bloom for moon + landmark windows
        '<filter id="bloom" x="-50%" y="-50%" width="200%" height="200%">'
        '<feGaussianBlur stdDeviation="2.4" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>',
        # Larger blur for aurora + nebula
        '<filter id="haze" x="-20%" y="-20%" width="140%" height="140%">'
        '<feGaussianBlur stdDeviation="6"/>'
        '</filter>',
        # ---- CSS animations (named classes — portable across renderers) ----
        '<style><![CDATA[',
        '@keyframes twinkle{0%,100%{opacity:.18}50%{opacity:1}}',
        '@keyframes pulseHalo{0%,100%{opacity:.25;transform:scale(.92)}50%{opacity:.75;transform:scale(1.08)}}',
        '@keyframes flicker{0%,100%{opacity:.95}9%{opacity:.35}19%{opacity:1}33%{opacity:.55}48%{opacity:1}71%{opacity:.4}82%{opacity:1}}',
        '@keyframes auroraWave{0%,100%{transform:translateX(0);opacity:.55}50%{transform:translateX(28px);opacity:.85}}',
        '@keyframes hueShift{0%,100%{filter:hue-rotate(0deg)}50%{filter:hue-rotate(28deg)}}',
        '@keyframes rise{0%{transform:translateY(36px);opacity:0}10%{opacity:.85}90%{opacity:.85}100%{transform:translateY(-220px);opacity:0}}',
        '@keyframes beam{0%,100%{opacity:.18}50%{opacity:.42}}',
        '.star{animation:twinkle 3.4s ease-in-out infinite}',
        '.star.b{animation-duration:2.1s}',
        '.star.c{animation-duration:4.7s}',
        '.star.d{animation-duration:5.6s}',
        '.star.e{animation-duration:1.8s}',
        '.halo-anim{animation:pulseHalo 4.2s ease-in-out infinite;transform-origin:center;transform-box:fill-box}',
        '.halo-anim.b{animation-duration:5.1s}',
        '.halo-anim.c{animation-duration:6.0s}',
        '.flicker{animation:flicker 4.5s steps(7,end) infinite}',
        '.flicker.b{animation-duration:3.0s}',
        '.flicker.c{animation-duration:5.5s}',
        '.flicker.d{animation-duration:6.8s}',
        '.aurora{animation:auroraWave 11s ease-in-out infinite}',
        '.nebula{animation:hueShift 22s ease-in-out infinite}',
        '.ember{animation:rise 12s linear infinite}',
        '.ember.b{animation-duration:9s}',
        '.ember.c{animation-duration:15s}',
        '.ember.d{animation-duration:18s}',
        '.beam{animation:beam 6s ease-in-out infinite}',
        ']]></style>',
        '</defs>',
    ]

    # --- Layer 1: sky ---
    parts.append(f'<rect width="{width}" height="{height}" fill="url(#sky)"/>')

    # --- Layer 2: nebula (animated hue) ---
    parts.append(
        '<g class="nebula" filter="url(#haze)">'
        f'<rect width="{width}" height="{pad_top + 30}" fill="url(#nebulaA)"/>'
        f'<rect width="{width}" height="{pad_top + 40}" fill="url(#nebulaB)"/>'
        '</g>'
    )

    # --- Layer 3: starfield ---
    parts.append('<g fill="#e6edf3">')
    star_classes = ["", "b", "c", "d", "e"]
    for _ in range(80):
        sx = rng.randint(6, width - 6)
        sy = rng.randint(4, pad_top + 18)
        sr = rng.choice([0.4, 0.6, 0.8, 1.0, 1.3])
        cls = "star " + rng.choice(star_classes) if rng.random() < 0.85 else "star"
        delay = rng.randint(0, 60) / 10
        parts.append(
            f'<circle class="{cls.strip()}" cx="{sx}" cy="{sy}" r="{sr}" '
            f'style="animation-delay:-{delay}s"/>'
        )
    # A handful of warm-colored stars for variety
    for _ in range(8):
        sx = rng.randint(6, width - 6)
        sy = rng.randint(4, pad_top - 4)
        c = rng.choice(["#fde68a", "#f9a8d4", "#bae6fd"])
        parts.append(
            f'<circle class="star c" cx="{sx}" cy="{sy}" r="1.1" fill="{c}"'
            f' style="animation-delay:-{rng.randint(0, 60)/10}s"/>'
        )
    parts.append('</g>')

    # --- Layer 4: moon ---
    moon_x = width - pad_x - 30
    moon_y = pad_top - 20
    parts.append(
        f'<g filter="url(#bloom)">'
        f'<circle cx="{moon_x}" cy="{moon_y}" r="22" fill="url(#moon)"/>'
        f'<circle cx="{moon_x - 5}" cy="{moon_y - 4}" r="3" fill="#000" opacity="0.07"/>'
        f'<circle cx="{moon_x + 4}" cy="{moon_y + 5}" r="2.2" fill="#000" opacity="0.06"/>'
        f'<circle cx="{moon_x - 3}" cy="{moon_y + 7}" r="1.4" fill="#000" opacity="0.05"/>'
        f'</g>'
    )

    # --- Layer 5: aurora ribbon (animated wave) ---
    ay = pad_top + 14
    aurora_d = (
        f"M0,{ay} "
        f"Q{width*0.22:.0f},{ay - 28} {width*0.5:.0f},{ay - 6} "
        f"T{width},{ay - 18} "
        f"L{width},{ay + 32} "
        f"Q{width*0.78:.0f},{ay + 8} {width*0.5:.0f},{ay + 28} "
        f"T0,{ay + 16} Z"
    )
    parts.append(
        f'<path class="aurora" d="{aurora_d}" fill="url(#aurora)" '
        f'filter="url(#haze)" opacity="0.7"/>'
    )

    # --- Layer 6: thin horizon glow line ---
    horizon_y = pad_top + (max_y - min_y) * 0.55
    parts.append(
        f'<line class="beam" x1="0" y1="{horizon_y:.0f}" x2="{width}" y2="{horizon_y:.0f}" '
        'stroke="#39d353" stroke-width="0.6" opacity="0.25"/>'
    )

    # --- Layer 7: ground platform + iso grid lines ---
    base_pad = 8
    g_corners = [
        _iso(-base_pad, -base_pad, 0),
        _iso(extents_x + base_pad, -base_pad, 0),
        _iso(extents_x + base_pad, extents_y + base_pad, 0),
        _iso(-base_pad, extents_y + base_pad, 0),
    ]
    parts.append(
        f'<polygon points="{fmt_pts(*g_corners)}" fill="url(#ground)" '
        'stroke="#39d353" stroke-width="0.5" stroke-opacity="0.25"/>'
    )
    for i in range(0, n_weeks + 1, 4):
        p1 = _iso(i * cell_w, 0, 0)
        p2 = _iso(i * cell_w, extents_y, 0)
        parts.append(
            f'<line x1="{p1[0]+ox:.2f}" y1="{p1[1]+oy:.2f}" '
            f'x2="{p2[0]+ox:.2f}" y2="{p2[1]+oy:.2f}" '
            'stroke="#39d353" stroke-width="0.3" opacity="0.18"/>'
        )
    for j in range(0, 8):
        p1 = _iso(0, j * cell_d, 0)
        p2 = _iso(extents_x, j * cell_d, 0)
        parts.append(
            f'<line x1="{p1[0]+ox:.2f}" y1="{p1[1]+oy:.2f}" '
            f'x2="{p2[0]+ox:.2f}" y2="{p2[1]+oy:.2f}" '
            'stroke="#39d353" stroke-width="0.3" opacity="0.13"/>'
        )

    # --- Layer 8 + 9 + 10: buildings (with windows, antennas, halos) ---
    cells: list[tuple[int, int, int, str]] = []
    for wi, week in enumerate(weeks):
        for day in week["contributionDays"]:
            cells.append((wi, day["weekday"], day["contributionCount"], day.get("date", "")))
    cells.sort(key=lambda c: (c[0] + c[1], c[0]))

    # Pre-pass: emit halos behind landmark buildings (drawn before city group so
    # they sit underneath everything in their footprint but above the ground).
    parts.append('<g class="halos">')
    halo_classes = ["", "b", "c"]
    landmark_threshold = max(12, int(avg_count * 2.2))
    for wi, di, count, _date in cells:
        if count < landmark_threshold:
            continue
        x = wi * cell_w + cell_w / 2
        y = di * cell_d + cell_d / 2
        ratio = count / max_count
        h = (ratio ** 0.5) * max_h + 4.0
        cx_, cy_ = _iso(x, y, h * 0.7)
        r = 14 + count * 0.45
        cls = "halo-anim " + rng.choice(halo_classes)
        parts.append(
            f'<circle class="{cls.strip()}" cx="{cx_+ox:.1f}" cy="{cy_+oy:.1f}" '
            f'r="{r:.0f}" fill="url(#halo)" '
            f'style="animation-delay:-{rng.randint(0, 50)/10}s"/>'
        )
    parts.append('</g>')

    parts.append('<g class="city">')
    flicker_classes = ["", "b", "c", "d"]
    window_palette = ["#fde68a", "#fcd34d", "#a7f3d0", "#bae6fd", "#fbcfe8"]
    for wi, di, count, date in cells:
        x = wi * cell_w
        y = di * cell_d

        if count > 0:
            ratio = count / max_count
            h = (ratio ** 0.55) * max_h + 4.0
        else:
            h = 1.5

        top_c, right_c, left_c = _palette_for(count)

        c100 = _iso(x + cell_w, y,            0)
        c110 = _iso(x + cell_w, y + cell_d,   0)
        c010 = _iso(x,          y + cell_d,   0)
        c001 = _iso(x,          y,            h)
        c101 = _iso(x + cell_w, y,            h)
        c111 = _iso(x + cell_w, y + cell_d,   h)
        c011 = _iso(x,          y + cell_d,   h)

        # Right face (+X side, sunlit)
        parts.append(f'<polygon points="{fmt_pts(c100, c110, c111, c101)}" fill="{right_c}"/>')
        # Left face (+Y side, shadow)
        parts.append(f'<polygon points="{fmt_pts(c010, c110, c111, c011)}" fill="{left_c}"/>')
        # Top face (+Z, brightest)
        parts.append(
            f'<polygon points="{fmt_pts(c001, c101, c111, c011)}" fill="{top_c}">'
            f'<title>{count} on {date}</title></polygon>'
        )

        # Top-edge rim highlight on tall buildings: a thin lighter polygon
        if count >= 8 and h > 30:
            rim = _interp(c001, c011, 0.0)
            rim2 = _interp(c101, c111, 0.0)
            # Tiny ridge along the front edge of the top face
            ridge = [
                c001,
                c101,
                _interp(c001, c011, 0.18),
                _interp(c101, c111, 0.18),
            ]
            # Just two pts forming a thin trapezoid
            ridge_pts = [
                c001, c101,
                _interp(c101, c111, 0.12),
                _interp(c001, c011, 0.12),
            ]
            parts.append(
                f'<polygon points="{fmt_pts(*ridge_pts)}" fill="#a7f3d0" opacity="0.55"/>'
            )

        # Window lights — only for count>=6, only on the right face (sunlit
        # side), arranged in a 2-column grid scaled with building height.
        if count >= 6 and h > 18:
            n_rows = min(int(h / 14), 5)
            for col_t in (0.32, 0.68):
                for row in range(n_rows):
                    row_t = (row + 0.5) / n_rows
                    bot = _interp(c100, c110, col_t)
                    top = _interp(c101, c111, col_t)
                    pos = _interp(bot, top, row_t)
                    flick = "flicker " + rng.choice(flicker_classes) if rng.random() < 0.4 else ""
                    color = rng.choice(window_palette)
                    delay = rng.randint(0, 60) / 10
                    extra = (
                        f' style="animation-delay:-{delay}s"' if flick else ""
                    )
                    parts.append(
                        f'<rect class="{flick.strip()}" x="{pos[0]+ox-0.7:.2f}" '
                        f'y="{pos[1]+oy-0.9:.2f}" width="1.4" height="1.8" '
                        f'fill="{color}"{extra}/>'
                    )

        # Antenna + beacon for landmark buildings
        if count >= landmark_threshold:
            top_mid = _interp(c001, c111, 0.5)
            beacon_x = top_mid[0] + ox
            beacon_y = top_mid[1] + oy
            parts.append(
                f'<line x1="{beacon_x:.1f}" y1="{beacon_y:.1f}" '
                f'x2="{beacon_x:.1f}" y2="{beacon_y - 9:.1f}" '
                f'stroke="#a7f3d0" stroke-width="0.7" opacity="0.85"/>'
                f'<circle class="flicker b" cx="{beacon_x:.1f}" cy="{beacon_y - 10:.1f}" '
                f'r="1.3" fill="#fef3c7" filter="url(#bloom)" '
                f'style="animation-delay:-{rng.randint(0, 50)/10}s"/>'
            )

    parts.append('</g>')

    # --- Layer 11: floating embers ---
    parts.append('<g class="embers">')
    ember_classes = ["", "b", "c", "d"]
    for _ in range(28):
        ex = rng.randint(20, width - 20)
        ey = rng.randint(pad_top + 30, height - pad_bottom)
        sz = rng.choice([0.7, 1.0, 1.3, 1.6])
        cls = "ember " + rng.choice(ember_classes)
        col = rng.choice(["#7ee787", "#39d353", "#a7f3d0", "#86efac"])
        delay = rng.randint(0, 180) / 10
        parts.append(
            f'<circle class="{cls.strip()}" cx="{ex}" cy="{ey}" r="{sz}" '
            f'fill="{col}" filter="url(#bloom)" '
            f'style="animation-delay:-{delay}s"/>'
        )
    parts.append('</g>')

    # --- Layer 12: vignette + HUD typography ---
    parts.append(
        f'<rect width="{width}" height="{height}" fill="url(#vignette)" pointer-events="none"/>'
    )

    parts.append(
        '<style><![CDATA['
        'text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,sans-serif}'
        '.t-user{font-size:28px;font-weight:800;fill:#e6edf3;letter-spacing:0.2px}'
        '.t-meta{font-size:13px;font-weight:500;fill:#8b949e}'
        '.t-meta .num{fill:#7ee787;font-weight:700}'
        '.t-year{font-size:96px;font-weight:900;fill:#7ee787;opacity:.07;letter-spacing:-4px}'
        '.t-tag{font-size:10px;font-weight:600;fill:#7ee787;letter-spacing:2px;text-transform:uppercase}'
        '.t-foot{font-size:11px;fill:#6e7681}'
        '.t-stat{font-size:12px;font-weight:600;fill:#c9d1d9}'
        '.t-stat-label{font-size:9px;fill:#6e7681;letter-spacing:1.5px;text-transform:uppercase}'
        ']]></style>'
        # Giant ghost year
        f'<text x="{width - pad_x}" y="{pad_top - 14}" class="t-year" text-anchor="end">{year}</text>'
        # Top-left tag
        f'<text x="{pad_x}" y="22" class="t-tag">// CONTRIBUTION SKYLINE</text>'
        # Username
        f'<text x="{pad_x}" y="50" class="t-user">{GH_USER}</text>'
        # Meta line
        f'<text x="{pad_x}" y="70" class="t-meta">'
        f'<tspan class="num">{total:,}</tspan> contributions · '
        f'<tspan class="num">{max_count}</tspan> peak · '
        f'<tspan class="num">{nonzero_days}</tspan> active days</text>'
        # Bottom-left mini stats panel
        f'<g transform="translate({pad_x},{height - 38})">'
        f'<text class="t-stat-label">DAILY AVG</text>'
        f'<text class="t-stat" y="14">{avg_count:.1f}</text>'
        f'</g>'
        f'<g transform="translate({pad_x + 90},{height - 38})">'
        f'<text class="t-stat-label">PEAK DAY</text>'
        f'<text class="t-stat" y="14">{max_count}</text>'
        f'</g>'
        f'<g transform="translate({pad_x + 180},{height - 38})">'
        f'<text class="t-stat-label">ACTIVE</text>'
        f'<text class="t-stat" y="14">{nonzero_days} / {sum(len(w["contributionDays"]) for w in weeks)}</text>'
        f'</g>'
        # Footer
        f'<text x="{width - pad_x}" y="{height - 18}" class="t-foot" text-anchor="end">'
        f'github.com/{GH_USER}</text>'
    )

    parts.append("</svg>")
    with open(dest, "w", encoding="utf-8") as f:
        f.write("".join(parts))


def regenerate_yearly_assets() -> None:
    """Refresh heatmap-{year}.svg and skyline-{year}.svg for the hero+small
    window. The 3D Animated Profile section uses the action-generated
    profile-3d-contrib/* SVGs from yoshi389111/github-profile-3d-contrib
    (refreshed by .github/workflows/3d-contrib.yml), so we no longer
    render per-year 3d-rainbow SVGs here."""
    big_year, small_years = _hero_years()
    os.makedirs(ASSETS_DIR, exist_ok=True)
    for y in [big_year, *small_years]:
        try:
            cal = fetch_contribution_calendar(y)
        except Exception as e:
            warn(f"contribution calendar fetch failed for {y}: {e}")
            continue
        try:
            render_heatmap_svg(y, cal, os.path.join(ASSETS_DIR, f"heatmap-{y}.svg"))
            render_skyline_svg(y, cal, os.path.join(ASSETS_DIR, f"skyline-{y}.svg"))
            print(f"refreshed assets for {y} (total={cal['totalContributions']})")
        except Exception as e:
            warn(f"asset render failed for {y}: {e}")


# --- 3D RAINBOW PROFILE (per-year, custom — yoshi389111's YEAR env is broken) ---
# Same iso projection as render_skyline_svg, but with a rainbow palette
# rolling across weeks for a vibrant "3D night rainbow" aesthetic. Renders
# real per-year data so the four tiles in the 3D Animated Profile section
# actually differ year to year.

def _rainbow_face_colors(week_idx: int, count: int) -> tuple[str, str, str]:
    """Cycle through a vibrant rainbow palette by week index. Returns
    (top, right, left) — top is the brightest, right is medium-lit,
    left is shadowed. Empty days fall back to a dim ground tile palette."""
    if count <= 0:
        return ("#1c2129", "#161b22", "#0d1117")
    # Eight rainbow stops, hue rolls across the year
    palette = [
        ("#FF6B6B", "#E84A4A", "#A82F2F"),  # red
        ("#FFA94D", "#E78A2F", "#A85B1F"),  # orange
        ("#FFE066", "#E6C24A", "#9F8B2A"),  # yellow
        ("#9CFF85", "#5AD650", "#36873B"),  # green
        ("#5EEAD4", "#06B6D4", "#0891B2"),  # cyan
        ("#67C7FF", "#2C8DE8", "#1B5FA8"),  # blue
        ("#A78BFA", "#7C3AED", "#5B21B6"),  # violet
        ("#F0ABFC", "#C026D3", "#86198F"),  # magenta
    ]
    return palette[week_idx % len(palette)]


def render_3d_rainbow_svg(year: int, calendar: dict, dest: str) -> None:
    """Render a per-year 3D rainbow contribution city — vibrant alternative
    to the green skyline. Same iso projection, but a rainbow palette rolls
    across weeks. Real per-year data (from contributionCalendar)."""
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]
    n_weeks = len(weeks)

    cell_w = 14.0
    cell_d = 14.0
    max_h = 130.0

    max_count = 1
    for w in weeks:
        for d in w["contributionDays"]:
            if d["contributionCount"] > max_count:
                max_count = d["contributionCount"]

    extents_x = n_weeks * cell_w
    extents_y = 7 * cell_d

    bbox = [
        _iso(0, 0, 0), _iso(extents_x, 0, 0),
        _iso(extents_x, extents_y, 0), _iso(0, extents_y, 0),
        _iso(0, 0, max_h), _iso(extents_x, 0, max_h),
        _iso(extents_x, extents_y, max_h), _iso(0, extents_y, max_h),
    ]
    min_x, max_x = min(p[0] for p in bbox), max(p[0] for p in bbox)
    min_y, max_y = min(p[1] for p in bbox), max(p[1] for p in bbox)

    pad_x, pad_top, pad_bottom = 40, 60, 36
    width = int(math.ceil(max_x - min_x)) + pad_x * 2
    height = int(math.ceil(max_y - min_y)) + pad_top + pad_bottom

    ox = pad_x - min_x
    oy = pad_top - min_y

    def fmt_pts(*corners: tuple[float, float]) -> str:
        return " ".join(f"{c[0] + ox:.2f},{c[1] + oy:.2f}" for c in corners)

    rng = random.Random(year * 1729 + 3)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{GH_USER} {year} 3D rainbow contribution profile">',
        # Backdrop — deep space with violet glow
        '<defs>'
        '<radialGradient id="rainbowSky" cx="50%" cy="100%" r="120%">'
        '<stop offset="0%" stop-color="#241039"/>'
        '<stop offset="40%" stop-color="#0d0820"/>'
        '<stop offset="100%" stop-color="#02030a"/>'
        '</radialGradient>'
        '<linearGradient id="ground" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#1a1330"/>'
        '<stop offset="100%" stop-color="#02030a"/>'
        '</linearGradient>'
        '<filter id="bloom" x="-50%" y="-50%" width="200%" height="200%">'
        '<feGaussianBlur stdDeviation="2" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
        '</defs>',
        f'<rect width="{width}" height="{height}" fill="url(#rainbowSky)"/>',
    ]

    # Stars — sparse rainbow
    parts.append('<g>')
    for _ in range(40):
        sx = rng.randint(8, width - 8)
        sy = rng.randint(8, pad_top - 4)
        sr = rng.choice([0.4, 0.6, 0.9])
        col = rng.choice(["#fde68a", "#f0abfc", "#a78bfa", "#67c7ff", "#5eead4", "#9cff85"])
        parts.append(f'<circle cx="{sx}" cy="{sy}" r="{sr}" fill="{col}" opacity="0.85"/>')
    parts.append('</g>')

    # Ground platform
    base_pad = 6
    g_corners = [
        _iso(-base_pad, -base_pad, 0),
        _iso(extents_x + base_pad, -base_pad, 0),
        _iso(extents_x + base_pad, extents_y + base_pad, 0),
        _iso(-base_pad, extents_y + base_pad, 0),
    ]
    parts.append(
        f'<polygon points="{fmt_pts(*g_corners)}" fill="url(#ground)" '
        f'stroke="#a78bfa" stroke-width="0.5" stroke-opacity="0.4"/>'
    )

    # Cells — depth-sorted painter's algorithm
    cells = []
    for wi, week in enumerate(weeks):
        for d in week["contributionDays"]:
            cells.append((wi, d["weekday"], d["contributionCount"], d.get("date", "")))
    cells.sort(key=lambda c: (c[0] + c[1], c[0]))

    for wi, di, count, date in cells:
        x = wi * cell_w
        y = di * cell_d

        if count > 0:
            ratio = count / max_count
            h = (ratio ** 0.55) * max_h + 4.0
        else:
            h = 1.5

        top_c, right_c, left_c = _rainbow_face_colors(wi, count)

        c100 = _iso(x + cell_w, y,            0)
        c110 = _iso(x + cell_w, y + cell_d,   0)
        c010 = _iso(x,          y + cell_d,   0)
        c001 = _iso(x,          y,            h)
        c101 = _iso(x + cell_w, y,            h)
        c111 = _iso(x + cell_w, y + cell_d,   h)
        c011 = _iso(x,          y + cell_d,   h)

        parts.append(f'<polygon points="{fmt_pts(c100, c110, c111, c101)}" fill="{right_c}"/>')
        parts.append(f'<polygon points="{fmt_pts(c010, c110, c111, c011)}" fill="{left_c}"/>')
        parts.append(
            f'<polygon points="{fmt_pts(c001, c101, c111, c011)}" fill="{top_c}">'
            f'<title>{count} on {date}</title></polygon>'
        )

    # HUD
    parts.append(
        '<style>text{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif}</style>'
        f'<text x="{pad_x}" y="32" font-size="22" font-weight="800" fill="#e6edf3">'
        f'{GH_USER}</text>'
        f'<text x="{pad_x}" y="52" font-size="13" font-weight="500" fill="#a78bfa">'
        f'<tspan font-weight="700" fill="#FFE066">{total:,}</tspan> '
        f'contributions in {year} · 3D Rainbow</text>'
        f'<text x="{width - pad_x}" y="32" text-anchor="end" '
        f'font-size="64" font-weight="900" fill="#FF6B6B" opacity="0.10" '
        f'letter-spacing="-2">{year}</text>'
    )

    parts.append("</svg>")
    with open(dest, "w", encoding="utf-8") as f:
        f.write("".join(parts))


# --- SKYLINE / CITY GRIDS -----------------------------------------------------

RAW_BASE = f"https://raw.githubusercontent.com/{GH_USER}/{GH_USER}/metrics-output"


def _years() -> list[int]:
    """All renderable years from START_YEAR..CURRENT_YEAR (used for STL/city link bars)."""
    if CURRENT_YEAR < START_YEAR:
        return [CURRENT_YEAR]
    return list(range(START_YEAR, CURRENT_YEAR + 1))


def _hero_years() -> tuple[int, list[int]]:
    """Current year (hero) + the three preceding years (small row underneath)."""
    small = [CURRENT_YEAR - 3, CURRENT_YEAR - 2, CURRENT_YEAR - 1]
    return CURRENT_YEAR, small


def _grid(href_for: Callable[[int], str], svg_for: Callable[[int], str], alt_kind: str) -> str:
    """Hero + 3-up layout: current year rendered large on top, three preceding years as a small row below."""
    big_year, small_years = _hero_years()

    hero_cell = (
        f'<td colspan="3" align="center">'
        f'<a href="{href_for(big_year)}">'
        f'<img src="{svg_for(big_year)}" width="100%" alt="{alt_kind} {big_year}">'
        f"</a>"
        f'<p><b>{big_year} <sub>(live)</sub></b></p>'
        f"</td>"
    )

    small_cells = "".join(
        f'<td width="33%" align="center">'
        f'<a href="{href_for(y)}">'
        f'<img src="{svg_for(y)}" width="100%" alt="{alt_kind} {y}">'
        f"</a>"
        f"<p><b>{y}</b></p>"
        f"</td>"
        for y in small_years
    )

    return (
        '<table align="center" width="100%">'
        f"<tr>{hero_cell}</tr>"
        f"<tr>{small_cells}</tr>"
        "</table>"
    )


def skyline_grid() -> str:
    # skyline.github.com was retired in late 2024 and the public Deno
    # contributions API ignores its ?year= parameter (returns the same
    # rolling-year SVG no matter what). We render real per-year skyline
    # SVGs ourselves from GitHub's GraphQL contributionCalendar — see
    # render_skyline_svg() above. Tile clicks open the gh-skyline-CLI
    # STL on metrics-output (rendered by GitHub's built-in 3D viewer).
    return _grid(
        href_for=lambda y: f"https://github.com/{GH_USER}/{GH_USER}/blob/metrics-output/skyline-{y}.stl",
        svg_for=lambda y: f"./{ASSETS_DIR}/skyline-{y}.svg",
        alt_kind=f"{GH_USER} contribution skyline",
    )


def city_grid() -> str:
    return _grid(
        href_for=lambda y: f"https://honzaap.github.io/GithubCity?name={GH_USER}&year={y}",
        svg_for=lambda y: f"{RAW_BASE}/github-metrics-city-{y}.svg",
        alt_kind="GitHub City",
    )


def snake_grid() -> str:
    """Hero (rolling-365 snake) + 3 small per-year contribution heatmaps."""
    big_year, small_years = _hero_years()

    snake_dark = f"https://raw.githubusercontent.com/{GH_USER}/{GH_USER}/output/github-contribution-grid-snake-dark.svg"
    snake_light = f"https://raw.githubusercontent.com/{GH_USER}/{GH_USER}/output/github-contribution-grid-snake.svg"
    hero_cell = (
        f'<td colspan="3" align="center">'
        f'<picture>'
        f'<source media="(prefers-color-scheme: dark)" srcset="{snake_dark}">'
        f'<source media="(prefers-color-scheme: light)" srcset="{snake_light}">'
        f'<img alt="GitHub contribution grid snake animation" src="{snake_dark}" width="100%">'
        f'</picture>'
        f'<p><b>{big_year} <sub>(live · rolling 365 days)</sub></b></p>'
        f"</td>"
    )

    def heatmap_cell(y: int) -> str:
        return (
            f'<td width="33%" align="center">'
            f'<a href="https://github.com/{GH_USER}?tab=overview&from={y}-01-01&to={y}-12-31">'
            f'<img src="./{ASSETS_DIR}/heatmap-{y}.svg" '
            f'width="100%" alt="{GH_USER} — {y} contribution heatmap">'
            f"</a>"
            f"<p><b>{y}</b></p>"
            f"</td>"
        )

    small_cells = "".join(heatmap_cell(y) for y in small_years)
    return (
        '<table align="center" width="100%">'
        f"<tr>{hero_cell}</tr>"
        f"<tr>{small_cells}</tr>"
        "</table>"
    )


# --- QUOTE OF THE DAY ---------------------------------------------------------

QUOTES = [
    ("First, solve the problem. Then, write the code.", "John Johnson"),
    ("Programs must be written for people to read, and only incidentally for machines to execute.", "Harold Abelson"),
    ("Premature optimization is the root of all evil.", "Donald Knuth"),
    ("Simplicity is prerequisite for reliability.", "Edsger W. Dijkstra"),
    ("The best error message is the one that never shows up.", "Thomas Fuchs"),
    ("Make it work, make it right, make it fast.", "Kent Beck"),
    ("Walking on water and developing software from a specification are easy if both are frozen.", "Edward V. Berard"),
    ("Code is like humor. When you have to explain it, it's bad.", "Cory House"),
    ("There are only two kinds of languages: the ones people complain about and the ones nobody uses.", "Bjarne Stroustrup"),
    ("Any fool can write code that a computer can understand. Good programmers write code that humans can understand.", "Martin Fowler"),
    ("Talk is cheap. Show me the code.", "Linus Torvalds"),
    ("If debugging is the process of removing software bugs, then programming must be the process of putting them in.", "Edsger W. Dijkstra"),
    ("Truth can only be found in one place: the code.", "Robert C. Martin"),
    ("Programming isn't about what you know; it's about what you can figure out.", "Chris Pine"),
    ("It's not a bug — it's an undocumented feature.", "Anonymous"),
    ("The most damaging phrase in the language is: 'We've always done it this way!'", "Grace Hopper"),
    ("Software is a great combination of artistry and engineering.", "Bill Gates"),
    ("Java is to JavaScript what car is to carpet.", "Chris Heilmann"),
    ("Good code is its own best documentation.", "Steve McConnell"),
    ("In order to be irreplaceable, one must always be different.", "Coco Chanel"),
    ("Don't comment bad code — rewrite it.", "Brian Kernighan"),
    ("Programs are meant to be read by humans and only incidentally for computers to execute.", "Donald Knuth"),
    ("The function of good software is to make the complex appear to be simple.", "Grady Booch"),
    ("Code never lies, comments sometimes do.", "Ron Jeffries"),
    ("Quality is more important than quantity. One home run is much better than two doubles.", "Steve Jobs"),
    ("Software undergoes beta testing shortly before it's released. Beta is Latin for 'still doesn't work'.", "Anonymous"),
    ("Real programmers count from 0.", "Anonymous"),
    ("Programming is the art of telling another human being what one wants the computer to do.", "Donald Knuth"),
    ("If you don't fail at least 90% of the time, you're not aiming high enough.", "Alan Kay"),
    ("The only way to learn a new programming language is by writing programs in it.", "Dennis Ritchie"),
    ("Computers are good at following instructions, but not at reading your mind.", "Donald Knuth"),
]


def quote_of_the_day() -> str:
    """Pick a quote indexed by day-of-year so it rotates daily and is stable for the whole day."""
    day_of_year = dt.datetime.now(dt.timezone.utc).timetuple().tm_yday
    quote, author = QUOTES[day_of_year % len(QUOTES)]
    return (
        f'<p align="center">\n'
        f'  <i>"{quote}"</i><br/>\n'
        f'  <sub>— <b>{author}</b></sub>\n'
        f"</p>"
    )


# --- MERMAID GITGRAPH FROM RECENT PUSH EVENTS ---------------------------------


def gitgraph_from_activity(limit: int = 8) -> str:
    """Render a small Mermaid gitGraph from recent PushEvents — visualizes commit cadence per repo."""
    r = requests.get(
        f"https://api.github.com/users/{GH_USER}/events/public?per_page=50",
        headers=GH_HEADERS,
        timeout=20,
    )
    r.raise_for_status()
    pushes: list[tuple[str, int]] = []  # (repo_short, commit_count)
    seen_repos: set[str] = set()
    for event in r.json():
        if event["type"] != "PushEvent":
            continue
        payload = event["payload"]
        commits = payload.get("commits") or []
        # See _push_event for why payloads have been getting stripped lately.
        n = payload.get("size") or payload.get("distinct_size") or len(commits)
        if n == 0 and payload.get("head"):
            n = 1
        if n == 0:
            continue
        repo_full = event["repo"]["name"]
        repo_short = repo_full.split("/")[-1]
        if repo_short in seen_repos:
            continue
        seen_repos.add(repo_short)
        pushes.append((repo_short, n))
        if len(pushes) >= limit:
            break

    if not pushes:
        return "_No recent push events to visualize._"

    lines = ["```mermaid",
             "%%{init: {'theme': 'dark', 'gitGraph': {'showCommitLabel': false, 'mainBranchName': 'main'}}}%%",
             "gitGraph", "   commit"]
    for repo, count in pushes:
        # Mermaid branch names: letters, digits, dash, underscore; keep the full name
        branch = re.sub(r"[^a-zA-Z0-9_-]", "-", repo).strip("-") or "branch"
        lines.append(f"   branch {branch}")
        lines.append(f"   checkout {branch}")
        for _ in range(min(count, 4)):  # cap at 4 commits per branch for readability
            lines.append("   commit")
        lines.append("   checkout main")
        lines.append("   merge " + branch)
    lines.append("```")
    return "\n".join(lines)


# --- INLINE LINK BARS (STL + GitCity) -----------------------------------------

STL_BASE = f"https://github.com/{GH_USER}/{GH_USER}/blob/metrics-output"


def _link_bar(prefix: str, href_for: Callable[[int], str], label_for: Callable[[int], str]) -> str:
    """Inline link bar — mirrors the hero-grid year window (3 preceding years + current)."""
    big_year, small_years = _hero_years()
    parts: list[str] = []
    for y in [*small_years, big_year]:
        suffix = " <sub>(live)</sub>" if y == CURRENT_YEAR else ""
        parts.append(f'<a href="{href_for(y)}">{label_for(y)}{suffix}</a>')
    return f'<p align="center"><b>{prefix}</b> ' + " · ".join(parts) + "</p>"


def contrib_links() -> str:
    """One line of links to the same data in 3D: the 3D profile, skyline models and GitHub cities."""
    years = list(range(2023, dt.date.today().year + 1))
    def yl(href):
        return " · ".join(f'<a href="{href(y)}">{y}</a>' for y in years)
    return ('<p align="center"><b>The same data in 3D:</b> '
            f'<a href="./profile-3d-contrib/profile-night-rainbow.svg">3D profile</a> · '
            f'skyline models {yl(lambda y: f"{STL_BASE}/skyline-{y}.stl")} · '
            f'cities {yl(lambda y: f"https://honzaap.github.io/GithubCity?name={GH_USER}&year={y}")}</p>')


def stl_links() -> str:
    return _link_bar(
        prefix="📐 Spin a 3D model:",
        href_for=lambda y: f"{STL_BASE}/skyline-{y}.stl",
        label_for=lambda y: f"{y} STL",
    )


def gitcity_links() -> str:
    return _link_bar(
        prefix="🚗 Drive through:",
        href_for=lambda y: f"https://honzaap.github.io/GithubCity?name={GH_USER}&year={y}",
        label_for=lambda y: f"{y} city",
    )


# --- MAIN ---------------------------------------------------------------------


# --- FEATURED PROJECTS (weekly auto-update) ----------------------------------
# Scores all owned non-fork non-archived repos by recent activity + stars,
# renders the top 6 as narrative cards.

def _score_repo(repo: dict, recent_commits: int) -> float:
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    pushed = dt.datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
    days_since = max(0, (dt.datetime.now(dt.timezone.utc) - pushed).days)
    recency = max(0.0, 1.0 - days_since / 365.0)
    return 0.4 * stars + 0.4 * recent_commits + 0.2 * (recency * 50)


LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#F1E05A", "TypeScript": "#3178C6",
    "Vue": "#41B883", "HTML": "#E34F26", "CSS": "#563D7C", "SCSS": "#C6538C",
    "Jupyter Notebook": "#DA5B0B", "Shell": "#89E051", "Dockerfile": "#384D54",
    "Java": "#B07219", "Go": "#00ADD8", "Rust": "#DEA584", "C": "#555555",
    "C++": "#F34B7D", "C#": "#178600", "PHP": "#4F5D95", "Ruby": "#701516",
    "Inno Setup": "#264B99", "MDX": "#1B6E5E",
}

# --- SELF-HOSTED GITHUB-STATS CARDS ------------------------------------------
# github-readme-stats.vercel.app has been returning 503 globally for hours,
# breaking the main stats card and top-languages card. Render them ourselves
# from real GraphQL/REST data so the README stays alive when the third-party
# service is down.

MAIN_STATS_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    name
    repositoriesContributedTo(first: 1, contributionTypes: [COMMIT]) { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes { stargazerCount }
    }
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
    }
  }
}
"""


def _fmt(n: int) -> str:
    if n >= 10_000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


STATS_ACCENT = "#58a6ff"   # icons and numbers on the stats cards; labels keep the codeSTACKr orange

_GITHUB_MARK = ("M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 "
                "0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 "
                "0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 "
                "1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55"
                "-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 "
                "1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z")


def _stat_icon(kind: str, x: float, y: float, color: str) -> str:
    """Small line icons in the spirit of the octicons on github-readme-stats (16px box at x, y)."""
    s = f'fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"'
    g = f'<g transform="translate({x} {y})">'
    if kind == "star":
        return g + f'<path {s} d="M8 1.5l1.9 3.9 4.3.6-3.1 3 .7 4.3L8 11.3l-3.8 2 .7-4.3-3.1-3 4.3-.6z"/></g>'
    if kind == "commits":
        return g + f'<circle {s} cx="8" cy="8" r="6.2"/><path {s} d="M8 4.5V8l2.4 1.6"/></g>'
    if kind == "pr":
        return (g + f'<circle {s} cx="4" cy="3.5" r="1.8"/><circle {s} cx="4" cy="12.5" r="1.8"/>'
                f'<circle {s} cx="12" cy="12.5" r="1.8"/><path {s} d="M4 5.3v5.4M12 10.7V6.5a2 2 0 0 0-2-2H7.5"/></g>')
    if kind == "issue":
        return g + f'<circle {s} cx="8" cy="8" r="6.2"/><circle cx="8" cy="8" r="1.4" fill="{color}"/></g>'
    return (g + f'<path {s} d="M3 2.5h8.5a1 1 0 0 1 1 1v10H4.5A1.5 1.5 0 0 1 3 12z"/>'
            f'<path {s} d="M3 12a1.5 1.5 0 0 1 1.5-1.5h8"/></g>')


_PROFILE_ICONS = {
    "contrib": "M8 0c4.42 0 8 3.58 8 8a8 8 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38v-2.2c0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82a7.6 7.6 0 0 0-4 0C4.48 3.09 3.8 3.3 3.8 3.3c-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94v1.49c0 .21-.15.45-.55.38A8 8 0 0 1 0 8c0-4.42 3.58-8 8-8Z",
}


def _profile_icon(kind: str, x: float, y: float, color: str) -> str:
    s = f'fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"'
    g = f'<g transform="translate({x} {y}) scale(1.25)">'
    if kind == "contrib":
        return g + f'<path fill="{color}" d="{_PROFILE_ICONS["contrib"]}"/></g>'
    if kind == "repos":
        return (g + f'<path {s} d="M3 2.5h8.5a1 1 0 0 1 1 1v10H4.5A1.5 1.5 0 0 1 3 12z"/>'
                f'<path {s} d="M3 12a1.5 1.5 0 0 1 1.5-1.5h8"/></g>')
    if kind == "joined":
        return g + f'<circle {s} cx="8" cy="8" r="6.2"/><path {s} d="M8 4.5V8l2.4 1.6"/></g>'
    return g + f'<rect {s} x="1.5" y="3.5" width="13" height="9.5" rx="1.2"/><path {s} d="M2 4.5l6 4.5 6-4.5"/></g>'


def profile_details_svg(title: str, rows, months, accent: str = STATS_ACCENT) -> str:
    """profile-details card in the codeSTACKr look: facts on the left, monthly contributions on the right."""
    W, H = 700, 200
    sans = "'Segoe UI',Ubuntu,'Helvetica Neue',Sans-Serif"
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{title}">',
         f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="5" fill="#09131B"/>',
         f'<text x="30" y="40" font-family="{sans}" font-size="22" fill="#ff652f">{title}</text>']
    for i, (kind, text) in enumerate(rows):
        y = 70 + i * 28
        p.append(_profile_icon(kind, 30, y - 14, accent))
        p.append(f'<text x="58" y="{y + 1}" font-family="{sans}" font-size="16" fill="#ffffff">{text}</text>')
    # contributions per month, last 12 months
    x0, x1, y0, y1 = 360, 640, 165, 60
    peak = max([c for _, c in months] + [1])
    step = 10 ** max(0, len(str(peak)) - 1)
    top = ((peak + step - 1) // step) * step
    pts = [(x0 + i * (x1 - x0) / max(1, len(months) - 1), y0 - (c / top) * (y0 - y1)) for i, (_, c) in enumerate(months)]
    d = f"M{pts[0][0]:.1f} {y0}" + "".join(
        f" C{(a[0] + b[0]) / 2:.1f} {a[1]:.1f} {(a[0] + b[0]) / 2:.1f} {b[1]:.1f} {b[0]:.1f} {b[1]:.1f}" if i else f" L{a[0]:.1f} {a[1]:.1f}"
        for i, (a, b) in enumerate(zip([pts[0]] + pts[:-1], pts)))
    p.append(f'<path d="{d} L{pts[-1][0]:.1f} {y0} Z" fill="#ff652f"/>')
    p.append(f'<text x="{x1}" y="40" text-anchor="end" font-family="{sans}" font-size="12" fill="#ffffff">contributions in the last year</text>')
    p.append(f'<line x1="{x1}" y1="{y1}" x2="{x1}" y2="{y0}" stroke="#42b883" stroke-width=".8"/>'
             f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" stroke="#42b883" stroke-width=".8"/>')
    for k in range(0, 5):
        v = top * k / 4
        yy = y0 - (v / top) * (y0 - y1)
        p.append(f'<text x="{x1 + 6}" y="{yy + 3}" font-family="{sans}" font-size="9" fill="{accent}">{int(v):,}</text>')
    for i, (label, _) in enumerate(months):
        if i % 2 == 0 or i == len(months) - 1:
            p.append(f'<text x="{pts[i][0]:.1f}" y="{y0 + 14}" text-anchor="middle" font-family="{sans}" font-size="9" fill="{accent}">{label}</text>')
    p.append("</svg>")
    return "".join(p)


def render_profile_details_svg(dest: Path) -> None:
    r = requests.get(f"https://api.github.com/users/{GH_USER}", headers=GH_HEADERS, timeout=20)
    r.raise_for_status()
    u = r.json()
    # daily counts come from the same heatmaps as the commit-name banner, so the numbers agree
    days: dict[str, int] = {}
    for f in sorted(Path(ASSETS_DIR).glob("heatmap-*.svg")):
        for count, date in re.findall(r"<title>(\d+) on (\d{4}-\d{2}-\d{2})</title>", f.read_text(encoding="utf-8")):
            days[date] = int(count)
    total = sum(days.values())
    today = dt.date.today()
    months = []
    for back in range(12, -1, -1):
        y, m = today.year, today.month - back
        while m <= 0:
            y, m = y - 1, m + 12
        key = f"{y}-{m:02d}"
        months.append((f"{y % 100:02d}/{m:02d}", sum(c for d, c in days.items() if d.startswith(key))))
    years = max(1, today.year - int(u["created_at"][:4]))
    name = (u.get("name") or "").strip()
    title = f"{GH_USER} ({name})" if name else GH_USER
    rows = [("contrib", f"{total / 1000:.2f}k Contributions on GitHub" if total >= 1000 else f"{total} Contributions on GitHub"),
            ("repos", f"{u.get('public_repos', 0)} Public Repos"),
            ("joined", f"Joined GitHub {years} year{'s' if years != 1 else ''} ago")]
    if u.get("email"):
        rows.append(("email", u["email"]))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(profile_details_svg(title, rows, months), encoding="utf-8")


def render_main_stats_svg(dest: Path) -> None:
    """The github-readme-stats main card in its codeSTACKr look, self-hosted so the numbers and icons
    can carry their own colour (the hosted card can only colour labels and numbers together)."""
    now = dt.datetime.now(dt.timezone.utc)
    year_start = dt.datetime(now.year, 1, 1, tzinfo=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    data = graphql(MAIN_STATS_QUERY, {"login": GH_USER, "from": year_start, "to": now_iso})
    user = data["user"]
    total_stars = sum(r["stargazerCount"] for r in user["repositories"]["nodes"])
    total_commits_yr = user["contributionsCollection"]["totalCommitContributions"]
    total_prs = user["pullRequests"]["totalCount"]
    total_issues = user["issues"]["totalCount"]
    contributed_to = user["repositoriesContributedTo"]["totalCount"]
    name = (user.get("name") or GH_USER).strip()  # the profile name has a trailing space
    rows = [
        ("Total Stars Earned", _fmt(total_stars), "star"),
        (f"Total Commits ({now.year})", _fmt(total_commits_yr), "commits"),
        ("Total PRs", _fmt(total_prs), "pr"),
        ("Total Issues", _fmt(total_issues), "issue"),
        ("Contributed to (last year)", _fmt(contributed_to), "repo"),
    ]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(stats_card_svg(f"{name}'s GitHub Stats", rows), encoding="utf-8")


def stats_card_svg(title: str, rows, accent: str = STATS_ACCENT) -> str:
    W, H = 467, 195
    sans = "'Segoe UI',Ubuntu,'Helvetica Neue',Sans-Serif"
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{title}">',
         f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="4.5" fill="#09131B"/>',
         f'<text x="25" y="35" font-family="{sans}" font-size="18" font-weight="600" fill="#ff652f">{title}</text>']
    for i, (label, value, icon) in enumerate(rows):
        y = 55 + i * 25
        p.append(_stat_icon(icon, 25, y + 1, accent))
        p.append(f'<text x="50" y="{y + 12.5}" font-family="{sans}" font-size="14" font-weight="600" fill="#ffffff">{label}:</text>')
        p.append(f'<text x="245" y="{y + 12.5}" font-family="{sans}" font-size="14" font-weight="700" fill="{accent}">{value}</text>')
    # Same rank ring as github-readme-stats (rank_icon=github): faint rim, progress arc, salmon GitHub mark
    cx, cy, r = 380.5, 110.5, 40
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#830203" stroke-opacity=".2" stroke-width="6"/>'
             f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#830203" stroke-opacity=".8" stroke-width="6" stroke-linecap="round" '
             f'stroke-dasharray="{2 * 3.1416 * r * .78:.1f} 999" transform="rotate(-90 {cx} {cy})"/>'
             f'<svg x="{cx - 33}" y="{cy - 33}" width="66" height="66" viewBox="0 0 16 16"><path fill="#da644d" d="{_GITHUB_MARK}"/></svg>')
    p.append("</svg>")
    return "".join(p)


LANGS_QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node { name color }
          }
        }
      }
    }
  }
}
"""


def render_top_langs_svg(dest: Path, top_n: int = 8) -> None:
    """Emulate github-readme-stats top-langs compact card. Aggregates language
    byte counts across all owned non-fork repos."""
    data = graphql(LANGS_QUERY, {"login": GH_USER})
    repos = data["user"]["repositories"]["nodes"]
    totals: dict[str, int] = {}
    colors: dict[str, str] = {}
    for r in repos:
        for edge in r["languages"]["edges"]:
            n = edge["node"]["name"]
            totals[n] = totals.get(n, 0) + edge["size"]
            colors[n] = edge["node"].get("color") or LANG_COLORS.get(n, "#6e7681")
    if not totals:
        warn("no language data — skipping top-langs render")
        return
    sorted_items = sorted(totals.items(), key=lambda x: -x[1])[:top_n]
    grand_total = sum(totals.values())

    # Same layout as the github-readme-stats compact card (codeSTACKr), with the title
    # in the regular orange used by the "Top Languages by Repo" card next to it.
    items = sorted_items[:6]
    shown = sum(sz for _, sz in items)
    W, H = 300, 165
    sans = "'Segoe UI',Ubuntu,Sans-Serif"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Most Used Languages">',
        f'<rect x=".5" y=".5" rx="4.5" width="{W - 1}" height="{H - 1}" fill="#09131B"/>',
        f'<text x="25" y="38" font-family="{sans}" font-size="19.4" font-weight="400" fill="#ff652f">Most Used Languages</text>',
        '<defs><clipPath id="bar"><rect x="25" y="55" width="250" height="8" rx="5"/></clipPath></defs><g clip-path="url(#bar)">',
    ]
    x = 25.0
    for name, size in items:
        w = 250 * size / shown
        parts.append(f'<rect x="{x:.2f}" y="55" width="{w + .5:.2f}" height="8" fill="{colors[name]}"/>')
        x += w
    parts.append('</g>')
    for i, (name, size) in enumerate(items):
        lx, ly = 25 + (i // 3) * 150, 80 + (i % 3) * 25
        parts.append(f'<circle cx="{lx + 5}" cy="{ly + 6}" r="5" fill="{colors[name]}"/>'
                     f'<text x="{lx + 15}" y="{ly + 10}" font-family="{sans}" font-size="11" fill="#ffffff">'
                     f'{name} {100 * size / shown:.2f}%</text>')
    parts.append('</svg>')

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(parts), encoding="utf-8")


def render_streak_svg(dest: Path) -> None:
    """Self-hosted GitHub streak card. Matches github-readme-streak-stats
    visual style + codeSTACKr theme. Computes streak from the live
    contributionCalendar so it's accurate the moment commits register
    (no upstream caching). Three columns: Total Contributions ·
    Current Streak · Longest Streak."""
    # GraphQL contributionsCollection caps at 1-year windows. Stitch multiple
    # one-year fetches so streaks crossing year boundaries compute correctly.
    now = dt.datetime.now(dt.timezone.utc)
    today = now.date()

    days: list[tuple[dt.date, int]] = []
    for years_back in (2, 1, 0):
        end_year = now.year - years_back
        from_dt = dt.datetime(end_year, 1, 1, tzinfo=dt.timezone.utc)
        to_dt = (
            now
            if years_back == 0
            else dt.datetime(end_year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc)
        )
        try:
            data = graphql(CONTRIB_QUERY, {
                "login": GH_USER,
                "from": from_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to":   to_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
            weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
            for w in weeks:
                for d in w["contributionDays"]:
                    try:
                        date = dt.date.fromisoformat(d["date"])
                        days.append((date, d["contributionCount"]))
                    except Exception:
                        continue
        except Exception as e:
            warn(f"streak window {end_year} fetch failed: {e}")

    # Dedupe (each year may overlap a few days at boundaries) and sort
    seen: dict[dt.date, int] = {}
    for d, c in days:
        seen[d] = max(seen.get(d, 0), c)
    days = sorted(seen.items())
    days = [d for d in days if d[0] <= today]

    total = sum(c for _, c in days)
    first_contrib = next((d for d, c in days if c > 0), None)

    # Current streak — walk backwards from today; allow today to be 0 if
    # there's still time left in the day, but stop once we hit yesterday=0.
    current = 0
    cs_start = None
    for date, count in reversed(days):
        if count > 0:
            current += 1
            cs_start = date
        else:
            if date == today:
                # Today has no contributions yet — don't break the streak
                # as long as yesterday counts.
                continue
            break
    # `%-d` (no zero padding) is POSIX-only, breaks on Windows. Build manually.
    def fmt_date(d):
        if d is None: return "—"
        return d.strftime("%b ") + str(d.day) + d.strftime(", %Y")
    cs_range = f"{fmt_date(cs_start)} - Present" if cs_start else "—"

    # Longest streak
    longest = 0
    longest_start = longest_end = None
    run = 0
    run_start = None
    for date, count in days:
        if count > 0:
            if run == 0:
                run_start = date
            run += 1
            if run > longest:
                longest = run
                longest_start = run_start
                longest_end = date
        else:
            run = 0
            run_start = None
    ls_range = (
        f"{fmt_date(longest_start)} - {fmt_date(longest_end)}"
        if longest_start else "—"
    )

    # Total date range
    last_contrib = next((d for d, c in reversed(days) if c > 0), today)
    total_range = (
        f"{fmt_date(first_contrib)} - {'Present' if last_contrib >= today - dt.timedelta(days=1) else fmt_date(last_contrib)}"
        if first_contrib else "—"
    )

    W, H = 495, 195
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-label="GitHub Streak">',
        '<defs>'
        '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#1a1f29"/>'
        '<stop offset="100%" stop-color="#0d1117"/>'
        '</linearGradient>'
        # Flame gradient for the current-streak ring
        '<linearGradient id="flame" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#FF5C5C"/>'
        '<stop offset="100%" stop-color="#F90001"/>'
        '</linearGradient>'
        '</defs>',
        f'<rect width="{W-2}" height="{H-2}" x="1" y="1" rx="6" '
        f'fill="url(#bg)" stroke="#30363d" stroke-width="1"/>',
    ]

    # Three vertical columns
    col_w = W // 3
    columns = [
        ("Total Contributions", _fmt(total),       total_range),
        ("Current Streak",      str(current),      cs_range),
        ("Longest Streak",      str(longest),      ls_range),
    ]

    for i, (label, value, sub) in enumerate(columns):
        cx = i * col_w + col_w // 2

        # Big value at center
        is_streak = i == 1
        if is_streak:
            # Highlighted with flame ring
            parts.append(
                f'<circle cx="{cx}" cy="60" r="32" fill="none" '
                f'stroke="url(#flame)" stroke-width="3"/>'
                f'<text x="{cx}" y="73" text-anchor="middle" '
                f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
                f'font-size="40" font-weight="800" fill="#F90001">'
                f'{value}</text>'
            )
        else:
            parts.append(
                f'<text x="{cx}" y="73" text-anchor="middle" '
                f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
                f'font-size="40" font-weight="800" fill="#e6edf3">'
                f'{value}</text>'
            )

        # Label
        parts.append(
            f'<text x="{cx}" y="115" text-anchor="middle" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
            f'font-size="13" font-weight="700" fill="#8b949e" letter-spacing="0.3">'
            f'{label}</text>'
        )

        # Date range / subtitle
        parts.append(
            f'<text x="{cx}" y="138" text-anchor="middle" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
            f'font-size="11" font-weight="500" fill="#7d8590">'
            f'{sub}</text>'
        )

        # Flame icon for the streak column (just under the value circle)
        if is_streak:
            parts.append(
                f'<g transform="translate({cx-7}, 152)">'
                f'<path d="M7 0 C 4 4, 0 7, 0 11 C 0 15, 3 18, 7 18 C 11 18, 14 15, 14 11 '
                f'C 14 8, 12 5, 10 4 C 11 6, 10 8, 9 8 C 9 6, 8 3, 7 0 Z" '
                f'fill="url(#flame)"/>'
                f'</g>'
            )

        # Vertical separator (between columns)
        if i > 0:
            sx = i * col_w
            parts.append(
                f'<line x1="{sx}" y1="40" x2="{sx}" y2="{H-30}" '
                f'stroke="#30363d" stroke-width="1"/>'
            )

    parts.append('</svg>')
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(parts), encoding="utf-8")


# --- GITHUB STATS SECTION -----------------------------------------------------
# One editorial SVG for README section 05: profile + yearly chart, five big
# numbers, a flame streak ring and the languages. Contribution totals, the
# chart and the streaks all come from the same heatmaps as the commit-name
# banner, so every number on the page agrees.

SEC_BLUE, SEC_GREEN, SEC_ORANGE, SEC_RED = "#58a6ff", "#42b883", "#ff652f", "#F90001"
SEC_SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Helvetica,Arial,sans-serif"
SEC_MONO = "ui-monospace,SFMono-Regular,'JetBrains Mono',Menlo,Consolas,monospace"
LANG_ICON_FILES = {
    "Python": "python", "HTML": "html5", "Vue": "vuejs", "TypeScript": "typescript", "Jupyter Notebook": "jupyter",
    "JavaScript": "javascript", "CSS": "css3", "Go": "go", "Java": "java", "C": "c", "C++": "cplusplus",
    "C#": "csharp", "PHP": "php", "Ruby": "ruby", "Rust": "rust", "Shell": "bash", "Dockerfile": "docker",
    "Kotlin": "kotlin", "Swift": "swift", "Dart": "dart",
}

SECTION_LANGS_QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      nodes {
        primaryLanguage { name color }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } }
      }
    }
  }
}
"""


def _heatmap_days() -> dict[dt.date, int]:
    days: dict[dt.date, int] = {}
    for f in sorted(Path(ASSETS_DIR).glob("heatmap-*.svg")):
        for count, date in re.findall(r"<title>(\d+) on (\d{4}-\d{2}-\d{2})</title>", f.read_text(encoding="utf-8")):
            days[dt.date.fromisoformat(date)] = int(count)
    return days


def _streaks(days: dict[dt.date, int], today: dt.date):
    """(current, current_start, longest, longest_start, longest_end, first_day)"""
    active = sorted(d for d, c in days.items() if c > 0 and d <= today)
    if not active:
        return 0, None, 0, None, None, None
    longest, ls, le, run, rs = 0, None, None, 0, None
    prev = None
    for d in active:
        run = run + 1 if prev and (d - prev).days == 1 else 1
        rs = rs if run > 1 else d
        if run > longest:
            longest, ls, le = run, rs, d
        prev = d
    current, cs = 0, None
    d = min(today, max(days))  # the newest day we have data for
    if days.get(d, 0) == 0:
        d -= dt.timedelta(days=1)  # that day may still be in progress
    while days.get(d, 0) > 0:
        current, cs = current + 1, d
        d -= dt.timedelta(days=1)
    return current, cs, longest, ls, le, active[0]


def _short(d: dt.date | None, year: bool = False) -> str:
    if d is None:
        return "—"
    return d.strftime("%b ") + str(d.day) + (d.strftime(", %Y") if year else "")


def _lang_icon(name: str, x: float, y: float, size: float, color: str) -> str:
    f = Path(ASSETS_DIR) / "icons" / "lang" / f"{LANG_ICON_FILES.get(name, '')}-original.svg"
    if name in LANG_ICON_FILES and f.exists():
        inner = re.sub(r"^<svg[^>]*>|</svg>\s*$", "", f.read_text(encoding="utf-8").strip())
        return f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 128 128">{inner}</svg>'
    initials = "".join(w[0] for w in name.split()[:2]).upper()
    return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="8" fill="{color}"/>'
            f'<text x="{x + size / 2}" y="{y + size / 2 + 6}" text-anchor="middle" font-family="{SEC_SANS}" '
            f'font-size="17" font-weight="800" fill="#0d1117">{html_escape(initials)}</text>')


def _smooth(pts) -> str:
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        mx = (ax + bx) / 2
        d += f" C{mx:.1f} {ay:.1f} {mx:.1f} {by:.1f} {bx:.1f} {by:.1f}"
    return d


def _sec_rule(y: float, x0: float, x1: float, eyebrow: str, title: str | None = None) -> str:
    out = (f'<text x="{x0 + 6}" y="{y + 40}" font-family="{SEC_MONO}" font-size="16" font-weight="700" '
           f'letter-spacing="3.5" fill="{SEC_GREEN}">// {eyebrow}</text>')
    if title:
        out += (f'<text x="{x0 + 6}" y="{y + 92}" font-family="{SEC_SANS}" font-size="40" font-weight="800" '
                f'letter-spacing="-1" fill="#ffffff">{title}<tspan fill="{SEC_RED}">.</tspan></text>')
    return out


def _kv_row(x0, x1, y, icon, label, value, sub=""):
    sub_svg = (f'<tspan fill="#8b949e" font-weight="400" font-size="19"> {html_escape(sub)}</tspan>' if sub else "")
    return (f'{icon}<text x="{x0 + 52}" y="{y + 9}" font-family="{SEC_SANS}" font-size="24" fill="#ffffff">{html_escape(label)}</text>'
            f'<text x="{x1}" y="{y + 9}" text-anchor="end" font-family="{SEC_SANS}" font-size="24" font-weight="700" '
            f'fill="{SEC_BLUE}">{html_escape(value)}{sub_svg}</text>'
            f'<line x1="{x0}" y1="{y + 31}" x2="{x1}" y2="{y + 31}" stroke="#21262d" stroke-width="1.5"/>')


def stats_section_svg(p: dict) -> str:
    W, H = 1400, 1385
    B, G, O, Rd = SEC_BLUE, SEC_GREEN, SEC_ORANGE, SEC_RED
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
         f'aria-label="GitHub stats for {html_escape(p["login"])}: {p["total"]:,} contributions, {p["stars"]} stars, '
         f'{p["commits"]} commits in {p["year"]}, current streak {p["current"]} days">',
         '<defs>'
         f'<linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{O}" stop-opacity=".5"/><stop offset="1" stop-color="{O}" stop-opacity="0"/></linearGradient>'
         '<linearGradient id="ring" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#5c0007"/><stop offset=".55" stop-color="#c3000c"/><stop offset="1" stop-color="#ff2a1a"/></linearGradient>'
         '<linearGradient id="flame" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#8a0008"/><stop offset=".45" stop-color="#F90001"/><stop offset=".8" stop-color="#ff5a1f"/><stop offset="1" stop-color="#ffb347"/></linearGradient>'
         '<linearGradient id="core" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#ff3b1f"/><stop offset="1" stop-color="#ffd27a"/></linearGradient>'
         '<radialGradient id="halo" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#F90001" stop-opacity=".35"/><stop offset="1" stop-color="#F90001" stop-opacity="0"/></radialGradient>'
         '<filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="5"/></filter>'
         '</defs>']

    # ---- profile (left) ------------------------------------------------------
    s.append(_sec_rule(0, 0, W, "PROFILE"))
    rx, ry = 64, 132
    s.append(f'<circle cx="{rx}" cy="{ry}" r="56" fill="none" stroke="#830203" stroke-opacity=".2" stroke-width="9"/>'
             f'<circle cx="{rx}" cy="{ry}" r="56" fill="none" stroke="#830203" stroke-opacity=".85" stroke-width="9" '
             f'stroke-linecap="round" stroke-dasharray="{2 * math.pi * 56 * .78:.1f} 999" transform="rotate(-90 {rx} {ry})"/>'
             f'<svg x="{rx - 46}" y="{ry - 46}" width="92" height="92" viewBox="0 0 16 16"><path fill="#da644d" d="{_GITHUB_MARK}"/></svg>')
    s.append(f'<text x="150" y="128" font-family="{SEC_SANS}" font-size="50" font-weight="800" letter-spacing="-1" fill="{O}">{html_escape(p["login"])}</text>')
    if p["name"]:
        s.append(f'<text x="152" y="170" font-family="{SEC_SANS}" font-size="30" fill="#ffffff">{html_escape(p["name"])}</text>')
    rows = [("contrib", "Contributions on GitHub", p["total_short"]), ("repos", "Public repos", str(p["public_repos"])),
            ("joined", "Joined GitHub", p["joined"])]
    if p["email"]:
        rows.append(("email", "Email", p["email"]))
    y = 236
    for kind, label, value in rows:
        icon = f'<g transform="translate(2 {y - 13}) scale(1.4)">{_profile_icon(kind, 0, 0, B)}</g>'
        s.append(_kv_row(0, 660, y, icon, label, value))
        y += 66
    base = y - 66 + 31  # the last row's divider: the chart's baseline sits on it

    # ---- chart (right) -------------------------------------------------------
    months = p["months"]
    vals = [v for _, _, v in months]
    peak = max(vals + [1])
    step = 10 ** (len(str(peak)) - 1)
    top = -(-peak // step) * step
    cx0, cx1, cyt = 740, 1330, 120
    xs = [cx0 + i * (cx1 - cx0) / (len(vals) - 1) for i in range(len(vals))]
    ys = [base - v / top * (base - cyt) for v in vals]
    line = _smooth(list(zip(xs, ys)))
    s.append(f'<text x="{cx1}" y="86" text-anchor="end" font-family="{SEC_SANS}" font-size="19" fill="#ffffff">contributions in the last year</text>')
    for k in range(5):
        gy = base - k * (base - cyt) / 4
        s.append(f'<line x1="{cx0}" y1="{gy:.1f}" x2="{cx1}" y2="{gy:.1f}" stroke="#21262d" stroke-width="1.2"/>'
                 f'<text x="{cx1 + 12}" y="{gy + 6:.1f}" font-family="{SEC_SANS}" font-size="17" fill="{B}">{int(top * k / 4):,}</text>')
    s.append(f'<path d="{line} L{cx1} {base} L{cx0} {base}Z" fill="url(#area)"/><path d="{line}" fill="none" stroke="{O}" stroke-width="3.5"/>'
             f'<line x1="{cx0}" y1="{base}" x2="{cx1}" y2="{base}" stroke="{G}" stroke-width="2"/>'
             f'<line x1="{cx1}" y1="{cyt}" x2="{cx1}" y2="{base}" stroke="{G}" stroke-width="2"/>')
    for i in range(0, len(months), 2):
        s.append(f'<text x="{xs[i]:.1f}" y="{base + 34}" text-anchor="middle" font-family="{SEC_SANS}" font-size="17" fill="{B}">{months[i][0]}</text>')
    pi = vals.index(peak)
    for i, anchor in ((pi, "middle"), (len(vals) - 1, "end")):
        if i == pi and anchor == "end" and pi == len(vals) - 1:
            continue
        tx = xs[i] - (12 if anchor == "end" else 0)
        s.append(f'<circle cx="{xs[i]:.1f}" cy="{ys[i]:.1f}" r="8" fill="{O}" stroke="#0d1117" stroke-width="3.5"/>'
                 f'<text x="{tx:.1f}" y="{ys[i] - 18:.1f}" text-anchor="{anchor}" font-family="{SEC_SANS}" font-size="19" '
                 f'font-weight="700" fill="{B}">{vals[i]:,} · {months[i][0]}</text>')

    # ---- the numbers ----------------------------------------------------------
    y0 = 560
    s.append(_sec_rule(y0, 0, W, "AT A GLANCE", "The numbers"))
    gy0, gy1 = y0 + 128, y0 + 300
    s.append(f'<line x1="0" y1="{gy0}" x2="{W}" y2="{gy0}" stroke="#30363d" stroke-width="1.5"/>'
             f'<line x1="0" y1="{gy1}" x2="{W}" y2="{gy1}" stroke="#30363d" stroke-width="1.5"/>')
    tiles = [(p["stars"], "Stars earned", "across my repos"), (p["commits"], "Commits", f"in {p['year']}"),
             (p["prs"], "Pull requests", "all time"), (p["issues"], "Issues", "opened"),
             (p["contributed"], "Contributed to", "repos, last year")]
    tw = W / len(tiles)
    for i, (num, label, sub) in enumerate(tiles):
        x = i * tw
        if i:
            s.append(f'<line x1="{x}" y1="{gy0}" x2="{x}" y2="{gy1}" stroke="#30363d" stroke-width="1.5"/>')
        s.append(f'<text x="{x + 26}" y="{gy0 + 86}" font-family="{SEC_SANS}" font-size="64" font-weight="800" letter-spacing="-2" fill="{B}">{num:,}</text>'
                 f'<text x="{x + 28}" y="{gy0 + 124}" font-family="{SEC_SANS}" font-size="22" fill="#ffffff">{label}</text>'
                 f'<text x="{x + 28}" y="{gy0 + 152}" font-family="{SEC_SANS}" font-size="18" fill="#8b949e">{sub}</text>')

    # ---- streak (left) --------------------------------------------------------
    y0 = 920
    s.append(_sec_rule(y0, 0, 660, "STREAK", "Every day counts"))
    fx, fy = 92, y0 + 220
    s.append(f'<circle cx="{fx}" cy="{fy}" r="98" fill="url(#halo)"/>'
             f'<circle cx="{fx}" cy="{fy}" r="76" fill="none" stroke="#2a0a0c" stroke-width="13"/>'
             f'<circle cx="{fx}" cy="{fy}" r="76" fill="none" stroke="url(#ring)" stroke-width="13" stroke-linecap="round" '
             f'stroke-dasharray="430 600" transform="rotate(-62 {fx} {fy})" filter="url(#soft)" opacity=".6"/>'
             f'<circle cx="{fx}" cy="{fy}" r="76" fill="none" stroke="url(#ring)" stroke-width="13" stroke-linecap="round" '
             f'stroke-dasharray="430 600" transform="rotate(-62 {fx} {fy})"/>'
             f'<circle cx="{fx}" cy="{fy - 76}" r="25" fill="#0d1117"/>')
    flame = "M0-39c4.5 13.5 19.5 21 19.5 40.5a19.5 19.5 0 0 1-39 0c0-9 4.5-15 9-19.5 0 7.5 3 12 7.5 13.5-1.5-12 0-22.5 3-34.5z"
    core = "M0-12c3 7.5 9 10.5 9 18a9 9 0 0 1-18 0c0-4.5 3-7.5 4.5-9 0 3 1.5 4.5 3 6 0-6 0-10.5 1.5-15z"
    s.append(f'<g transform="translate({fx} {fy - 78})"><path d="{flame}" fill="url(#flame)" filter="url(#soft)" opacity=".7"/>'
             f'<path d="{flame}" fill="url(#flame)"/><path d="{core}" fill="url(#core)"/></g>'
             f'<text x="{fx}" y="{fy + 18}" text-anchor="middle" font-family="{SEC_SANS}" font-size="62" font-weight="800" fill="{B}">{p["current"]}</text>'
             f'<text x="{fx}" y="{fy + 46}" text-anchor="middle" font-family="{SEC_SANS}" font-size="15" font-weight="700" letter-spacing="2.5" fill="#ff5a4a">DAYS</text>')
    st = f'fill="none" stroke="{B}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"'
    icons = {
        "sum": f'<path {st} d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
        "flame": f'<path {st} d="M12 3c1 3 4 5 4 9a4 4 0 0 1-8 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3-1-5 0-8z"/>',
        "trophy": f'<path {st} d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v4M8 20h8M9 17h6"/>',
    }
    srows = [("sum", "Total", f"{p['total']:,}", f"since {_short(p['first'], True)}"),
             ("flame", "Current", f"{p['current']} day{'s' if p['current'] != 1 else ''}",
              f"{_short(p['cs'])} – {_short(p['today'])}" if p["current"] else ""),
             ("trophy", "Longest", f"{p['longest']} days",
              f"{p['ls'].strftime('%b')} – {p['le'].strftime('%b %Y')}" if p["ls"] else "")]
    y = y0 + 168
    for kind, label, value, sub in srows:
        icon = f'<svg x="232" y="{y - 15}" width="28" height="28" viewBox="0 0 24 24">{icons[kind]}</svg>'
        s.append(_kv_row(230, 660, y, icon, label, value, sub))
        y += 66

    # ---- languages (right) ----------------------------------------------------
    lx0, lx1 = 740, W
    s.append(_sec_rule(y0, lx0, lx1, "LANGUAGES", "What I write"))
    langs = p["langs"][:6]
    shown = sum(v for _, v, _ in langs) or 1
    bx, by, bw = lx0 + 6, y0 + 134, lx1 - lx0 - 6
    s.append(f'<defs><clipPath id="bar"><rect x="{bx}" y="{by}" width="{bw}" height="13" rx="6.5"/></clipPath></defs><g clip-path="url(#bar)">')
    x = bx
    for name, v, col in langs:
        w = bw * v / shown
        s.append(f'<rect x="{x:.1f}" y="{by}" width="{w + .6:.1f}" height="13" fill="{col}"/>')
        x += w
    s.append('</g>')
    for i, (name, v, col) in enumerate(langs):
        lx, ly = bx + (i % 2) * (bw / 2), by + 52 + (i // 2) * 40
        s.append(f'<circle cx="{lx + 8}" cy="{ly - 7}" r="8" fill="{col}"/>'
                 f'<text x="{lx + 26}" y="{ly}" font-family="{SEC_SANS}" font-size="22" fill="#ffffff">{html_escape(name)} '
                 f'<tspan fill="{B}" font-weight="700">{100 * v / shown:.2f}%</tspan></text>')
    # repos by primary language: donut + icons
    dy = by + 52 + 3 * 40 + 34
    dcx, dcy, dr = bx + 52, dy + 48, 40
    repo_langs = p["repo_langs"][:5]
    tot = sum(c for _, c, _ in repo_langs) or 1
    circ, acc = 2 * math.pi * dr, 0.0
    s.append(f'<circle cx="{dcx}" cy="{dcy}" r="{dr}" fill="none" stroke="#21262d" stroke-width="18"/>')
    for name, c, col in repo_langs:
        seg = circ * c / tot
        s.append(f'<circle cx="{dcx}" cy="{dcy}" r="{dr}" fill="none" stroke="{col}" stroke-width="18" '
                 f'stroke-dasharray="{max(seg - 1.5, .5):.1f} {circ:.1f}" stroke-dashoffset="{-acc:.1f}" transform="rotate(-90 {dcx} {dcy})"/>')
        acc += seg
    s.append(f'<text x="{bx + 130}" y="{dy + 18}" font-family="{SEC_MONO}" font-size="15" font-weight="700" letter-spacing="3" fill="{G}">BY REPOS</text>')
    for i, (name, c, col) in enumerate(repo_langs):
        ix = bx + 130 + i * 72
        s.append(_lang_icon(name, ix, dy + 36, 48, col)
                 + f'<rect x="{ix + 6}" y="{dy + 94}" width="36" height="4" rx="2" fill="{col}"/>')
    s.append("</svg>")
    return "".join(s)


def render_stats_section_svg(dest: Path) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    today = now.date()
    r = requests.get(f"https://api.github.com/users/{GH_USER}", headers=GH_HEADERS, timeout=20)
    r.raise_for_status()
    u = r.json()
    year_start = dt.datetime(now.year, 1, 1, tzinfo=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    main = graphql(MAIN_STATS_QUERY, {"login": GH_USER, "from": year_start, "to": now.strftime("%Y-%m-%dT%H:%M:%SZ")})["user"]
    repos = graphql(SECTION_LANGS_QUERY, {"login": GH_USER})["user"]["repositories"]["nodes"]
    bytes_by, colors, count_by = {}, {}, {}
    for repo in repos:
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            bytes_by[n] = bytes_by.get(n, 0) + e["size"]
            colors[n] = e["node"].get("color") or LANG_COLORS.get(n, "#6e7681")
        pl = repo.get("primaryLanguage")
        if pl:
            count_by[pl["name"]] = count_by.get(pl["name"], 0) + 1
            colors.setdefault(pl["name"], pl.get("color") or "#6e7681")
    days = _heatmap_days()
    try:  # the heatmaps can lag a day; the live calendar keeps the streak exact
        live = graphql(CONTRIB_QUERY, {"login": GH_USER, "from": year_start, "to": now.strftime("%Y-%m-%dT%H:%M:%SZ")})
        for w in live["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[dt.date.fromisoformat(d["date"])] = d["contributionCount"]
    except Exception as e:
        warn(f"live calendar unavailable, using heatmaps only: {e}")
    total = sum(days.values())
    current, cs, longest, ls, le, first = _streaks(days, today)
    months = []
    for back in range(12, -1, -1):
        y, m = today.year, today.month - back
        while m <= 0:
            y, m = y - 1, m + 12
        months.append((dt.date(y, m, 1).strftime("%b"), f"{y}-{m:02d}",
                       sum(c for d, c in days.items() if d.year == y and d.month == m)))
    years = max(1, today.year - int(u["created_at"][:4]))
    p = dict(
        login=GH_USER, name=(u.get("name") or "").strip(), email=u.get("email") or "",
        public_repos=u.get("public_repos", 0), joined=f"{years} year{'s' if years != 1 else ''} ago",
        total=total, total_short=f"{total / 1000:.2f}k" if total >= 1000 else str(total), months=months,
        stars=sum(n["stargazerCount"] for n in main["repositories"]["nodes"]),
        commits=main["contributionsCollection"]["totalCommitContributions"], year=now.year,
        prs=main["pullRequests"]["totalCount"], issues=main["issues"]["totalCount"],
        contributed=main["repositoriesContributedTo"]["totalCount"],
        current=current, cs=cs, longest=longest, ls=ls, le=le, first=first, today=today,
        langs=[(n, v, colors[n]) for n, v in sorted(bytes_by.items(), key=lambda x: -x[1])],
        repo_langs=[(n, c, colors[n]) for n, c in sorted(count_by.items(), key=lambda x: -x[1])],
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(stats_section_svg(p), encoding="utf-8")


# --- RECENT ACTIVITY + LATEST RELEASES SECTIONS -------------------------------
# Same editorial look as the stats section. Both are pure render functions fed
# by small fetchers, so a failed API call just keeps yesterday's SVG.

ACT_PALETTE = ["#58a6ff", "#42b883", "#bc8cff", "#e3b341", "#79c0ff", "#f778ba"]
BUMP_STYLE = {  # dot, text, pill fill, pill stroke
    "major": ("#F90001", "#ff6b6b", "#2a0b0e", "#F90001"),
    "minor": ("#58a6ff", "#79c0ff", "#0c1d33", "#388bfd"),
    "patch": ("#8b949e", "#c9d1d9", "#161b22", "#6e7681"),
}


def _gh_rest(path: str, params: dict | None = None):
    r = requests.get(f"https://api.github.com{path}", headers=GH_HEADERS, params=params or {}, timeout=20)
    r.raise_for_status()
    return r.json()


def _ago(when: dt.datetime, now: dt.datetime) -> str:
    secs = (now - when).total_seconds()
    if secs < 3600:
        return "just now" if secs < 120 else f"{int(secs // 60)} minutes ago"
    if when.date() == now.date():
        h = int(secs // 3600)
        return f"{h} hour{'s' if h != 1 else ''} ago"
    days = (now.date() - when.date()).days
    return "yesterday" if days == 1 else f"{days} days ago"


def _clip(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip(" ,.;:-") + "…"


def activity_svg(d: dict) -> str:
    W = 1400
    B, G = SEC_BLUE, SEC_GREEN
    repos = d["repos"][:6]
    top = 588
    H = top + max(1, len(repos)) * 86 + 12
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
         f'aria-label="Last 7 days: {d["kpis"][0][0]} commits across {d["kpis"][1][0]} repositories">']
    # KPI tiles
    s.append(f'<line x1="0" y1="10" x2="{W}" y2="10" stroke="#30363d" stroke-width="1.5"/>'
             f'<line x1="0" y1="176" x2="{W}" y2="176" stroke="#30363d" stroke-width="1.5"/>')
    tw = W / len(d["kpis"])
    for i, (val, suffix, label, delta, unit) in enumerate(d["kpis"]):
        x = i * tw
        if i:
            s.append(f'<line x1="{x}" y1="10" x2="{x}" y2="176" stroke="#30363d" stroke-width="1.5"/>')
        suf = f'<tspan fill="#8b949e" font-size="30" font-weight="700">{suffix}</tspan>' if suffix else ""
        s.append(f'<text x="{x + 26}" y="88" font-family="{SEC_SANS}" font-size="60" font-weight="800" letter-spacing="-2" fill="{B}">{val}{suf}</text>'
                 f'<text x="{x + 28}" y="124" font-family="{SEC_SANS}" font-size="22" fill="#ffffff">{label}</text>')
        if delta is None:
            pass
        elif delta == 0:
            s.append(f'<text x="{x + 28}" y="156" font-family="{SEC_SANS}" font-size="17" fill="#8b949e">= same as last week</text>')
        else:
            up = delta > 0
            s.append(f'<text x="{x + 28}" y="156" font-family="{SEC_SANS}" font-size="17" font-weight="600" fill="{"#3fb950" if up else "#f85149"}">'
                     f'{"▲" if up else "▼"} {abs(delta)}{unit} vs last week</text>')
    # stacked 7-day chart
    color = {r["name"]: r["color"] for r in d["repos"]}
    totals = [sum(v for v in day.values()) for _, day in d["days"]]
    peak = max(totals + [1])
    base, maxh, gap = 430, 190, 24
    cw = (W - gap * 6) / 7
    for i, (label, day) in enumerate(d["days"]):
        x = i * (cw + gap)
        if not totals[i]:
            s.append(f'<rect x="{x:.1f}" y="{base - 5}" width="{cw:.1f}" height="5" rx="2.5" fill="#21262d"/>')
        y = base
        for name, n in sorted(day.items(), key=lambda kv: list(color).index(kv[0]) if kv[0] in color else 99):
            h = max(6, maxh * n / peak)
            y -= h
            s.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cw:.1f}" height="{h - 3:.1f}" rx="5" fill="{color.get(name, "#6e7681")}"/>')
        style = 'font-weight="700" fill="#ffffff"' if i == len(d["days"]) - 1 else f'fill="{B}"'
        s.append(f'<text x="{x + cw / 2:.1f}" y="{base + 34}" text-anchor="middle" font-family="{SEC_SANS}" font-size="19" {style}>{label}</text>')
    s.append(f'<line x1="0" y1="{base + 1}" x2="{W}" y2="{base + 1}" stroke="{G}" stroke-width="2"/>')
    lx = 0
    for r in d["repos"][:6]:
        s.append(f'<rect x="{lx}" y="{base + 62}" width="15" height="15" rx="4" fill="{r["color"]}"/>'
                 f'<text x="{lx + 24}" y="{base + 76}" font-family="{SEC_SANS}" font-size="19" fill="#ffffff">{html_escape(r["short"])}</text>')
        lx += 60 + len(r["short"]) * 10.5
    # table
    s.append(f'<text x="64" y="{top - 22}" font-family="{SEC_SANS}" font-size="15" letter-spacing="2" fill="#8b949e">REPOSITORY · LATEST COMMIT</text>'
             f'<text x="1180" y="{top - 22}" text-anchor="end" font-family="{SEC_SANS}" font-size="15" letter-spacing="2" fill="#8b949e">COMMITS</text>'
             f'<text x="{W}" y="{top - 22}" text-anchor="end" font-family="{SEC_SANS}" font-size="15" letter-spacing="2" fill="#8b949e">LAST PUSH</text>'
             f'<line x1="0" y1="{top}" x2="{W}" y2="{top}" stroke="#21262d" stroke-width="1.5"/>')
    for i, r in enumerate(repos):
        y = top + i * 86
        s.append(_lang_icon(r["lang"] or "", 6, y + 22, 40, r["color"]) if r["lang"] else
                 f'<rect x="6" y="{y + 22}" width="40" height="40" rx="8" fill="#161b22" stroke="#30363d"/>')
        s.append(f'<rect x="64" y="{y + 25}" width="13" height="13" rx="3" fill="{r["color"]}"/>'
                 f'<text x="88" y="{y + 38}" font-family="{SEC_SANS}" font-size="24" fill="#ffffff">{html_escape(_clip(r["name"], 52))}</text>'
                 f'<text x="64" y="{y + 70}" font-family="{SEC_MONO}" font-size="18" fill="#8b949e">{html_escape(_clip(r["msg"], 64))}</text>'
                 f'<text x="1180" y="{y + 52}" text-anchor="end" font-family="{SEC_SANS}" font-size="28" font-weight="700" fill="{B}">{r["commits"]}</text>'
                 f'<text x="{W}" y="{y + 52}" text-anchor="end" font-family="{SEC_SANS}" font-size="22" fill="#8b949e">{r["ago"]}</text>'
                 f'<line x1="0" y1="{y + 86}" x2="{W}" y2="{y + 86}" stroke="#21262d" stroke-width="1.5"/>')
    if not repos:
        s.append(f'<text x="64" y="{top + 52}" font-family="{SEC_SANS}" font-size="22" fill="#8b949e">No pushes in the last 7 days.</text>')
    s.append("</svg>")
    return "".join(s)


def render_activity_svg(dest: Path) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    today = now.date()
    since = now - dt.timedelta(days=14)
    repos = _gh_rest(f"/users/{GH_USER}/repos", {"type": "owner", "sort": "pushed", "per_page": 40})
    rows, per_day, prev_days = [], {}, set()
    week_start = today - dt.timedelta(days=6)
    commits_now = commits_prev = 0
    repos_prev = set()
    for r in repos:
        if r.get("fork") or r.get("archived") or r["name"].lower() == GH_USER.lower():
            continue
        if dt.datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")) < since:
            continue
        cs = _gh_rest(f"/repos/{GH_USER}/{r['name']}/commits",
                      {"author": GH_USER, "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"), "per_page": 100})
        this_week = []
        for c in cs:
            when = dt.datetime.fromisoformat(c["commit"]["author"]["date"].replace("Z", "+00:00"))
            if when.date() >= week_start:
                this_week.append((when, c["commit"]["message"].splitlines()[0]))
                per_day.setdefault(when.date(), {}).setdefault(r["name"], 0)
                per_day[when.date()][r["name"]] += 1
            else:
                commits_prev += 1
                repos_prev.add(r["name"])
                prev_days.add(when.date())
        if this_week:
            this_week.sort(reverse=True)
            commits_now += len(this_week)
            rows.append(dict(name=r["name"], lang=r.get("language"), commits=len(this_week),
                             msg=this_week[0][1], ago=_ago(this_week[0][0], now)))
    rows.sort(key=lambda x: -x["commits"])
    for i, row in enumerate(rows):
        row["color"] = ACT_PALETTE[i % len(ACT_PALETTE)]
        parts = re.split(r"[-_]+", row["name"])
        row["short"] = row["name"] if len(row["name"]) <= 18 else "-".join(p for p in parts[:2] if p)
    try:
        q = f"type:pr author:{GH_USER} created:>={(today - dt.timedelta(days=13)).isoformat()}"
        items = _gh_rest("/search/issues", {"q": q, "per_page": 100})["items"]
        prs_now = sum(1 for it in items if it["created_at"][:10] >= week_start.isoformat())
        prs_prev = len(items) - prs_now
    except Exception as e:
        warn(f"PR count unavailable: {e}")
        prs_now = prs_prev = None
    days = [(("Today" if i == 6 else (week_start + dt.timedelta(days=i)).strftime("%a")),
             per_day.get(week_start + dt.timedelta(days=i), {})) for i in range(7)]
    active = sum(1 for _, day in days if day)
    kpis = [(commits_now, "", "commits", commits_now - commits_prev, ""),
            (len(rows), "", "repos touched", len(rows) - len(repos_prev), ""),
            (prs_now if prs_now is not None else "—", "", "pull requests",
             (prs_now - prs_prev) if prs_now is not None else None, ""),
            (active, "/7", "active days", active - len(prev_days), "")]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(activity_svg(dict(kpis=kpis, days=days, repos=rows)), encoding="utf-8")


def _semver(tag: str):
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", tag or "")
    return tuple(int(x or 0) for x in m.groups()) if m else None


def _bump(tag: str) -> str:
    v = _semver(tag)
    if not v:
        return "patch"
    if v[1] == 0 and v[2] == 0:
        return "major"
    return "minor" if v[2] == 0 else "patch"


def _release_lines(body: str, title: str, n: int = 3) -> list[str]:
    out = []
    for line in (body or "").splitlines():
        t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
        t = re.sub(r"[`*_>#]+", "", t).strip().lstrip("-•+ ").strip()
        if not t or t.lower() == (title or "").lower() or t.lower().startswith(("full changelog", "what's changed", "**full")):
            continue
        out.append(_clip(t, 92))
        if len(out) == n:
            break
    return out


_TAG_RE = re.compile(r"^(?P<pkg>.*?)[-_/@]?(?P<ver>v?\d+(?:\.\d+){1,2}(?:[-+.][\w.]+)?)$")


def _release_entry(repo: str, tag: str, when: dt.datetime, title: str, body: str, url: str, kind: str = "release") -> dict:
    """One row for the releases card. Monorepo tags like `devtrust-whychanged-v0.1.0`
    show as `v0.1.0` with the package next to the repo name."""
    m = _TAG_RE.match(tag)
    label, short = repo, tag
    if m and m.group("pkg"):
        pkg = re.sub(rf"^{re.escape(repo.lower())}[-_/]?", "", m.group("pkg").lower()).strip("-_/")
        short = m.group("ver")
        label = f"{repo} · {pkg}" if pkg else repo
    return dict(repo=label, tag=short, raw_tag=tag, bump=_bump(short), when=when, date=when.date(),
                title=title, notes=_release_lines(body, title), url=url, kind=kind)


def _tag_entries(repo: str, known: set[str], newer_than: dt.datetime | None, look_at: int = 3) -> list[dict]:
    """Version tags that have no GitHub Release, newer than the latest release.
    Notes come from the annotated tag message, or the tagged commit's message."""
    tags = [t for t in _gh_rest(f"/repos/{GH_USER}/{repo}/tags", {"per_page": 30})
            if t["name"] not in known and _TAG_RE.match(t["name"])]
    tags.sort(key=lambda t: _semver(_TAG_RE.match(t["name"]).group("ver")) or (0, 0, 0), reverse=True)
    out = []
    for t in tags[:look_at]:
        ref = _gh_rest(f"/repos/{GH_USER}/{repo}/git/ref/tags/{urllib.parse.quote(t['name'], safe='')}")["object"]
        if ref["type"] == "tag":  # annotated: has its own date and message
            obj = _gh_rest(f"/repos/{GH_USER}/{repo}/git/tags/{ref['sha']}")
            when_s, message = obj["tagger"]["date"], obj.get("message") or ""
        else:
            obj = _gh_rest(f"/repos/{GH_USER}/{repo}/git/commits/{ref['sha']}")
            when_s, message = obj["committer"]["date"], obj.get("message") or ""
        when = dt.datetime.fromisoformat(when_s.replace("Z", "+00:00"))
        if newer_than and when <= newer_than:
            continue
        lines = [ln for ln in message.strip().splitlines() if not ln.startswith("-----BEGIN")]
        title = (lines[0].strip() if lines else "") or t["name"]
        out.append(_release_entry(repo, t["name"], when, title, "\n".join(lines[1:]),
                                  f"https://github.com/{GH_USER}/{repo}/releases/tag/{urllib.parse.quote(t['name'])}", "tag"))
    return out


def releases_svg(d: dict) -> str:
    W = 1400
    B = SEC_BLUE
    L = d["latest"]
    notes = L["notes"]
    s_ = []
    s_.append(f'<text x="0" y="40" font-family="{SEC_SANS}" font-size="24" fill="#ffffff">'
              f'<tspan fill="{B}" font-size="34" font-weight="800">{d["year_count"]}</tspan> release{"s" if d["year_count"] != 1 else ""} this year'
              f'<tspan fill="#8b949e">  ·  </tspan>latest <tspan fill="{B}" font-weight="700">{d["days_since"]} day{"s" if d["days_since"] != 1 else ""}</tspan> ago</text>')
    cy = 80
    title_y = cy + 152
    ny = title_y + 46
    link_y = ny + len(notes) * 36 + (14 if notes else 0)
    ch = link_y + 34 - cy
    dot, txt, pf, ps = BUMP_STYLE[L["bump"]]
    name_w = len(L["repo"]) * 17
    tag_w = len(L["tag"]) * 11 + 32
    s_.append(f'<rect x="1" y="{cy}" width="{W - 2}" height="{ch}" rx="14" fill="url(#card)" stroke="#30363d" stroke-width="1.5"/>'
              f'<text x="36" y="{cy + 50}" font-family="{SEC_MONO}" font-size="16" font-weight="700" letter-spacing="3.5" fill="{SEC_GREEN}">// LATEST</text>'
              f'<text x="{W - 36}" y="{cy + 50}" text-anchor="end" font-family="{SEC_SANS}" font-size="19" fill="#8b949e">{L["date"].strftime("%b ")}{L["date"].day}{L["date"].strftime(", %Y")}</text>'
              f'<text x="36" y="{cy + 110}" font-family="{SEC_SANS}" font-size="36" font-weight="800" letter-spacing="-.6" fill="#ffffff">{html_escape(L["repo"])}</text>'
              f'<rect x="{36 + name_w + 16:.0f}" y="{cy + 82}" width="{tag_w}" height="36" rx="18" fill="{pf}" stroke="{ps}" stroke-width="1.5"/>'
              f'<text x="{36 + name_w + 16 + tag_w / 2:.0f}" y="{cy + 106}" text-anchor="middle" font-family="{SEC_MONO}" font-size="17" font-weight="700" fill="{txt}">{html_escape(L["tag"])}</text>'
              f'<text x="36" y="{title_y}" font-family="{SEC_SANS}" font-size="23" fill="#c9d1d9">{html_escape(_clip(L["title"], 90))}</text>')
    for i, line in enumerate(notes):
        y = ny + i * 36
        s_.append(f'<circle cx="62" cy="{y - 7}" r="3.5" fill="#8b949e"/>'
                  f'<text x="80" y="{y}" font-family="{SEC_SANS}" font-size="20" fill="#c9d1d9">{html_escape(line)}</text>')
    s_.append(f'<text x="36" y="{link_y}" font-family="{SEC_SANS}" font-size="20" font-weight="700" fill="{B}">{"Read the release notes" if L.get("kind", "release") == "release" else "View the tag"} →</text>')
    # timeline
    tl = d["timeline"]
    ty = cy + ch + 96
    n = len(tl)
    span = min(W - 160, max(1, n - 1) * 300)
    x0, x1 = (W - span) / 2, (W + span) / 2
    s_.append(f'<rect x="{x0 - 40}" y="{ty - 1.5}" width="{x1 - x0 + 80}" height="3" rx="1.5" fill="url(#tl)"/>')
    for i, r in enumerate(tl):
        x = (x0 + x1) / 2 if n == 1 else x0 + i * (x1 - x0) / (n - 1)
        dot, txt, _, _ = BUMP_STYLE[r["bump"]]
        s_.append(f'<circle cx="{x:.1f}" cy="{ty}" r="13" fill="{dot}" stroke="#0d1117" stroke-width="4"/>'
                  f'<text x="{x:.1f}" y="{ty + 48}" text-anchor="middle" font-family="{SEC_MONO}" font-size="18" font-weight="700" fill="{txt}">{html_escape(r["tag"])}</text>'
                  f'<text x="{x:.1f}" y="{ty + 76}" text-anchor="middle" font-family="{SEC_SANS}" font-size="20" fill="#ffffff">{html_escape(_clip(r["repo"], 24))}</text>'
                  f'<text x="{x:.1f}" y="{ty + 100}" text-anchor="middle" font-family="{SEC_SANS}" font-size="16" fill="#8b949e">{r["date"].strftime("%b ")}{r["date"].day}</text>')
    ly = ty + 150
    lx = 0
    for kind in ("major", "minor", "patch"):
        s_.append(f'<circle cx="{lx + 8}" cy="{ly - 6}" r="8" fill="{BUMP_STYLE[kind][0]}"/>'
                  f'<text x="{lx + 24}" y="{ly}" font-family="{SEC_SANS}" font-size="18" fill="#8b949e">{kind}</text>')
        lx += 110
    H = ly + 14
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="Latest release: {html_escape(L["repo"])} {html_escape(L["tag"])}">'
            '<defs><linearGradient id="card" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#121821"/><stop offset="1" stop-color="#0d1117"/></linearGradient>'
            '<linearGradient id="tl" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#30363d"/><stop offset="1" stop-color="#42b883"/></linearGradient></defs>')
    return head + "".join(s_) + "</svg>"


def render_releases_svg(dest: Path) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=730)
    repos = _gh_rest(f"/users/{GH_USER}/repos", {"type": "owner", "sort": "pushed", "per_page": 100})
    rels = []
    for r in repos:
        if r.get("fork") or dt.datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")) < cutoff:
            continue
        repo_rels = []
        for rel in _gh_rest(f"/repos/{GH_USER}/{r['name']}/releases", {"per_page": 5}):
            if rel.get("draft") or not rel.get("published_at"):
                continue
            when = dt.datetime.fromisoformat(rel["published_at"].replace("Z", "+00:00"))
            title = (rel.get("name") or rel["tag_name"]).strip()
            title = re.sub(rf"^{re.escape(rel['tag_name'])}\s*[—–-]\s*", "", title) or title
            repo_rels.append(_release_entry(r["name"], rel["tag_name"], when, title, rel.get("body") or "", rel["html_url"]))
        # Tags pushed after the newest release (or with no release at all) count too.
        try:
            repo_rels += _tag_entries(r["name"], {x["raw_tag"] for x in repo_rels},
                                      max((x["when"] for x in repo_rels), default=None))
        except Exception as e:
            warn(f"tags for {r['name']} unavailable: {e}")
        rels += [x for x in repo_rels if x["when"] >= cutoff]
    if not rels:
        warn("no releases found — keeping the previous releases.svg")
        return
    rels.sort(key=lambda x: x["date"], reverse=True)
    d = dict(year_count=sum(1 for x in rels if x["date"].year == now.year),
             days_since=(now.date() - rels[0]["date"]).days, latest=rels[0], timeline=list(reversed(rels[:6])))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(releases_svg(d), encoding="utf-8")


def regenerate_activity_cards() -> None:
    stats_dir = Path(ASSETS_DIR) / "stats"
    for name, fn in (("activity", render_activity_svg), ("releases", render_releases_svg)):
        try:
            fn(stats_dir / f"{name}.svg")
            print(f"rendered {name}.svg")
        except Exception as e:
            warn(f"{name} render failed, keeping the previous file: {e}")


def regenerate_stats_cards() -> None:
    stats_dir = Path(ASSETS_DIR) / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)
    try:
        render_stats_section_svg(stats_dir / "section.svg")
        print("rendered section.svg")
    except Exception as e:
        warn(f"stats section render failed: {e}")
    regenerate_activity_cards()
    try:
        render_profile_details_svg(stats_dir / "profile-details.svg")
        print("rendered profile-details.svg")
    except Exception as e:
        warn(f"profile-details render failed: {e}")
    try:
        render_main_stats_svg(stats_dir / "main-stats.svg")
        print("rendered main-stats.svg")
    except Exception as e:
        warn(f"main-stats render failed: {e}")
    try:
        render_top_langs_svg(stats_dir / "top-langs.svg")
        print("rendered top-langs.svg")
    except Exception as e:
        warn(f"top-langs render failed: {e}")
    try:
        render_streak_svg(stats_dir / "streak.svg")
        print("rendered streak.svg")
    except Exception as e:
        warn(f"streak render failed: {e}")


# --- PROJECTS: shared helpers ------------------------------------------------

def _humanize_date(iso: str) -> str:
    """Turn an ISO date into 'today' / 'yesterday' / 'N days ago' / '~M months ago'."""
    if not iso:
        return "—"
    try:
        d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return iso[:10]
    days = (dt.datetime.now(dt.timezone.utc) - d).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    if days < 365:
        return f"~{days // 30} months ago"
    return f"~{days // 365} years ago"


# --- PINNED REPOS (daily auto-update) ----------------------------------------

def _categorize_repo(repo: dict) -> str:
    """Bucket a repo into a coarse showcase category."""
    name = repo["name"]
    topics = set(repo.get("topics") or [])
    lang = repo.get("language") or ""
    if name in {"PortfolioCraft", "GitHub-Doc-Generator", "Repo-Directory-Structure",
                "Python-Environment-Management-Tool", "API-Client-Generator",
                "commit-craft", "pr-coach", "repodoc-ai", "ai-quality-gate",
                "issue-triage-bot", "release-pilot"}:
        return "tools"
    if topics & {"ai", "ml", "machine-learning", "rag", "llm", "embeddings"}:
        return "ai"
    if name in {"AI-KI", "Ragolex", "cortex"}:
        return "ai"
    if topics & {"game", "pygame", "arcade"}:
        return "game"
    if topics & {"vue", "react", "nuxt", "frontend", "tailwindcss"} or lang in {"Vue", "TypeScript"}:
        return "frontend"
    if name in {"AbdullahBakir97"}:
        return "tools"
    if lang == "HTML" or lang == "CSS":
        return "frontend"
    return "backend"


# --- PROJECTS: spotlight, featured cards, project index ----------------------
# Same editorial system as the stats section: dark cards, green mono eyebrows,
# blue numbers, white text, no emoji. Spotlight copy is curated in
# spotlight.json; every number on it is fetched live.

SPOTLIGHT_FILE = Path(__file__).resolve().parent / "spotlight.json"
PROJECTS_DIR_NAME = "projects"
CATEGORY_LABELS = {"tools": "DEVELOPER TOOLS", "ai": "AI · DATA", "game": "GAMES",
                   "frontend": "FRONTEND", "backend": "BACKEND / API"}
LIGHT_TILE_ICONS = {"django"}  # dark glyphs that need a light tile
_FEATURED_NAMES: list[str] = []


def _load_spotlight() -> list[dict]:
    try:
        return json.loads(SPOTLIGHT_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        warn(f"spotlight.json unreadable: {e}")
        return []


def _spotlight_names() -> set[str]:
    return {s["repo"] for s in _load_spotlight()}


def _wrap_px(text: str, width_px: float, font_px: float) -> list[str]:
    """Greedy word wrap using an average glyph width of ~0.52em."""
    per_line = max(10, int(width_px / (font_px * 0.52)))
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        nxt = f"{cur} {w}".strip()
        if len(nxt) > per_line and cur:
            lines.append(cur)
            cur = w
        else:
            cur = nxt
    if cur:
        lines.append(cur)
    return lines


def _icon_tile(name: str, x: float, y: float, size: float = 64) -> str:
    fill = "#e6edf3" if name in LIGHT_TILE_ICONS else "#1c2330"
    pad = size * 0.2
    return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="14" fill="{fill}" stroke="#30363d" stroke-width="1.5"/>'
            + _lang_icon_file(name, x + pad, y + pad, size - 2 * pad))


def _lang_icon_file(icon: str, x: float, y: float, size: float) -> str:
    f = Path(ASSETS_DIR) / "icons" / "lang" / f"{icon}-original.svg"
    if not f.exists():
        return ""
    inner = re.sub(r"^<svg[^>]*>|</svg>\s*$", "", f.read_text(encoding="utf-8").strip())
    return f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 128 128">{inner}</svg>'


def spotlight_svg(s: dict, live: dict) -> str:
    W, PAD = 1400, 48
    B, G = SEC_BLUE, SEC_GREEN
    lx0, lx1 = PAD, 820
    rx0, rx1 = 880, W - PAD
    label_w = 150
    body_font = 21
    rows = [(k, _wrap_px(v, lx1 - lx0 - label_w, body_font)) for k, v in s["rows"]]
    one = _wrap_px(s["one_liner"], lx1 - lx0, 25)
    y = PAD + 30
    left = [f'<text x="{lx0}" y="{y}" font-family="{SEC_MONO}" font-size="16" font-weight="700" letter-spacing="3.5" fill="{G}">// {html_escape(s["eyebrow"])}</text>']
    y += 62
    left.append(f'<text x="{lx0}" y="{y}" font-family="{SEC_SANS}" font-size="52" font-weight="800" letter-spacing="-1.5" fill="#ffffff">'
                f'{html_escape(s["name"])}<tspan fill="{SEC_RED}">.</tspan></text>')
    y += 44
    for ln in one:
        left.append(f'<text x="{lx0}" y="{y}" font-family="{SEC_SANS}" font-size="25" fill="#c9d1d9">{html_escape(ln)}</text>')
        y += 34
    y += 14
    for label, lines in rows:
        left.append(f'<text x="{lx0}" y="{y + 4}" font-family="{SEC_MONO}" font-size="15" font-weight="700" letter-spacing="2.5" fill="{B}">{label}</text>')
        for i, ln in enumerate(lines):
            left.append(f'<text x="{lx0 + label_w}" y="{y + 6 + i * 29}" font-family="{SEC_SANS}" font-size="{body_font}" fill="#c9d1d9">{html_escape(ln)}</text>')
        y += 6 + len(lines) * 29 + 14
        left.append(f'<line x1="{lx0}" y1="{y - 6}" x2="{lx1}" y2="{y - 6}" stroke="#21262d" stroke-width="1.5"/>')
        y += 18
    left_h = y

    # right column
    ry = PAD + 74
    right = [f'<line x1="{rx0}" y1="{ry}" x2="{rx1}" y2="{ry}" stroke="#30363d" stroke-width="1.5"/>']
    stats = []
    for val, label in s["stats"]:
        if str(val).startswith("live:"):
            v = live.get(val[5:])
            if v is None:
                continue
            val = f"{v:,}"
        stats.append((val, label))
    cw = (rx1 - rx0) / max(1, len(stats))
    for i, (val, label) in enumerate(stats):
        x = rx0 + i * cw + 6
        right.append(f'<text x="{x}" y="{ry + 62}" font-family="{SEC_SANS}" font-size="44" font-weight="800" letter-spacing="-1" fill="{B}">{html_escape(str(val))}</text>'
                     f'<text x="{x}" y="{ry + 94}" font-family="{SEC_SANS}" font-size="19" fill="#ffffff">{html_escape(label)}</text>')
    ry += 122
    right.append(f'<line x1="{rx0}" y1="{ry}" x2="{rx1}" y2="{ry}" stroke="#30363d" stroke-width="1.5"/>')
    ry += 46
    right.append(f'<text x="{rx0}" y="{ry}" font-family="{SEC_MONO}" font-size="16" font-weight="700" letter-spacing="3.5" fill="{G}">// STACK</text>')
    ry += 22
    for i, ic in enumerate(s["stack_icons"]):
        right.append(_icon_tile(ic, rx0 + i * 78, ry))
    ry += 64 + 34
    for ln in _wrap_px(s["stack_text"], rx1 - rx0, 18):
        right.append(f'<text x="{rx0}" y="{ry}" font-family="{SEC_SANS}" font-size="18" fill="#8b949e">{html_escape(ln)}</text>')
        ry += 26
    ry += 22
    right.append(f'<text x="{rx0}" y="{ry}" font-family="{SEC_SANS}" font-size="21" font-weight="700" fill="{B}">View the repository →</text>')
    H = max(left_h, ry + 20) + PAD - 18
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="{html_escape(s["name"])}: {html_escape(s["one_liner"])}">'
            f'<defs><radialGradient id="sg" cx="1" cy="0" r="1.3"><stop offset="0" stop-color="#161b24"/><stop offset=".55" stop-color="#0d1117"/></radialGradient></defs>'
            f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="24" fill="url(#sg)" stroke="#30363d" stroke-width="2"/>'
            + "".join(left) + "".join(right) + "</svg>")


SPOTLIGHT_QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    stargazerCount
    forkCount
    defaultBranchRef { target { ... on Commit { history { totalCount } } } }
  }
}
"""


def render_spotlight_svgs() -> None:
    out = Path(ASSETS_DIR) / PROJECTS_DIR_NAME
    out.mkdir(parents=True, exist_ok=True)
    for s in _load_spotlight():
        try:
            r = graphql(SPOTLIGHT_QUERY, {"owner": GH_USER, "name": s["repo"]})["repository"]
            live = {"stars": r["stargazerCount"], "forks": r["forkCount"],
                    "commits": ((r.get("defaultBranchRef") or {}).get("target") or {}).get("history", {}).get("totalCount")}
            (out / f"spotlight-{s['repo']}.svg").write_text(spotlight_svg(s, live), encoding="utf-8")
            print(f"rendered spotlight-{s['repo']}.svg")
        except Exception as e:
            warn(f"spotlight {s['repo']} failed, keeping the previous file: {e}")


def featured_card_svg(c: dict) -> str:
    """One Featured card. c: name, category, desc, tags, language, stars, status, status_kind, updated."""
    W, H, P = 700, 340, 34
    B, G = SEC_BLUE, SEC_GREEN
    status_fill = {"live": "#ff6b6b", "active": "#3fb950", "quiet": "#6e7681"}[c["status_kind"]]
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
         f'aria-label="{html_escape(c["name"])} — {html_escape(c["desc"])}">'
         f'<defs><linearGradient id="fc" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#121821"/><stop offset="1" stop-color="#0d1117"/></linearGradient></defs>'
         f'<rect x="1.5" y="1.5" width="{W - 3}" height="{H - 3}" rx="20" fill="url(#fc)" stroke="#30363d" stroke-width="2"/>'
         f'<text x="{P}" y="{P + 18}" font-family="{SEC_MONO}" font-size="16" font-weight="700" letter-spacing="3.5" fill="{G}">{html_escape(c["category"])}</text>'
         f'<text x="{W - P}" y="{P + 18}" text-anchor="end" font-family="{SEC_SANS}" font-size="18" font-weight="600" fill="{status_fill}">● {html_escape(c["status"])}</text>']
    name = c["name"] if len(c["name"]) <= 30 else c["name"][:29] + "…"
    s.append(f'<text x="{P}" y="{P + 70}" font-family="{SEC_SANS}" font-size="31" font-weight="800" letter-spacing="-.5" fill="#ffffff">{html_escape(name)}</text>')
    lines = _wrap_px(c["desc"], W - 2 * P, 19.5)
    if len(lines) > 3:
        lines = lines[:3]
        lines[-1] = lines[-1].rstrip(" ,.;—-") + "…"
    for i, ln in enumerate(lines):
        s.append(f'<text x="{P}" y="{P + 110 + i * 28}" font-family="{SEC_SANS}" font-size="19.5" fill="#9da7b3">{html_escape(ln)}</text>')
    tx, ty = P, H - 112
    for t in c["tags"][:3]:
        w = len(t) * 10.4 + 30
        s.append(f'<rect x="{tx}" y="{ty}" width="{w:.0f}" height="34" rx="17" fill="none" stroke="#30363d" stroke-width="1.6"/>'
                 f'<text x="{tx + w / 2:.0f}" y="{ty + 23}" text-anchor="middle" font-family="{SEC_MONO}" font-size="16.5" fill="#c9d1d9">{html_escape(t)}</text>')
        tx += w + 10
    fy = H - 44
    s.append(f'<line x1="{P}" y1="{fy - 24}" x2="{W - P}" y2="{fy - 24}" stroke="#21262d" stroke-width="1.5"/>')
    lang = c.get("language") or ""
    x = P
    if lang:
        s.append(_lang_icon(lang, x, fy - 9, 26, LANG_COLORS.get(lang, "#6e7681")))
        s.append(f'<text x="{x + 36}" y="{fy + 11}" font-family="{SEC_SANS}" font-size="19" fill="#ffffff">{html_escape(lang)}</text>')
        x += 36 + len(lang) * 10.5 + 28
    s.append(f'<text x="{x}" y="{fy + 11}" font-family="{SEC_SANS}" font-size="19" font-weight="700" fill="{B}">★ {c["stars"]}</text>'
             f'<text x="{W - P}" y="{fy + 11}" text-anchor="end" font-family="{SEC_SANS}" font-size="18" fill="#8b949e">updated {html_escape(c["updated"])}</text>')
    s.append("</svg>")
    return "".join(s)


def _featured_card_data(repo: dict, recent_commits: int) -> dict:
    home = (repo.get("homepage") or "").strip()
    host = urllib.parse.urlparse(home if "://" in home else f"https://{home}").netloc.removeprefix("www.") if home else ""
    if host and not host.endswith(("github.com", "github.io")):
        status, kind = f"LIVE · {host}", "live"
    elif recent_commits >= 5:
        status, kind = f"{recent_commits} commits · 30d", "active"
    else:
        status, kind = "quiet", "quiet"
    generic = {"python", "python3", "html", "css", "javascript", "html5"}
    tags = [t for t in (repo.get("topics") or []) if t not in generic][:3]
    return dict(name=repo["name"], category=CATEGORY_LABELS.get(_categorize_repo(repo), "PROJECT"),
                desc=(repo.get("description") or "No description yet.").strip(), tags=tags,
                language=repo.get("language") or "", stars=repo.get("stargazers_count", 0),
                status=status, status_kind=kind,
                updated=_humanize_date(repo.get("pushed_at") or "").lstrip("~"))


def fetch_featured_projects(limit: int = 6) -> str:
    """The most active owned repos (score: recent commits, stars, recency), minus the
    profile repo and the spotlight projects. Rendered as editorial SVG cards."""
    global _FEATURED_NAMES
    r = requests.get(f"https://api.github.com/users/{GH_USER}/repos?per_page=100&type=owner",
                     headers=GH_HEADERS, timeout=20)
    r.raise_for_status()
    skip = _spotlight_names() | {GH_USER}
    repos = [x for x in r.json() if not x.get("fork") and not x.get("archived") and x["name"] not in skip]
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).isoformat()
    scored = []
    for repo in repos:
        commits = 0
        try:
            cr = requests.get(f"https://api.github.com/repos/{GH_USER}/{repo['name']}/commits",
                              headers=GH_HEADERS, params={"since": since, "per_page": 100}, timeout=10)
            if cr.ok:
                commits = len(cr.json())
        except Exception:
            pass
        scored.append((_score_repo(repo, commits), repo, commits))
    scored.sort(key=lambda t: -t[0])
    top = scored[:limit]
    if not top:
        return "_No featured projects yet._"
    feat_dir = Path(ASSETS_DIR) / "featured"
    feat_dir.mkdir(parents=True, exist_ok=True)
    for _, repo, commits in top:
        try:
            (feat_dir / f"{repo['name']}.svg").write_text(featured_card_svg(_featured_card_data(repo, commits)), encoding="utf-8")
        except Exception as e:
            warn(f"featured render failed for {repo['name']}: {e}")
    _FEATURED_NAMES = [repo["name"] for _, repo, _ in top]
    # Drop cards for repos that left the grid (or were renamed), so assets/ stays honest.
    for old in feat_dir.glob("*.svg"):
        if old.stem not in _FEATURED_NAMES:
            old.unlink()
    return _featured_grid(_FEATURED_NAMES)


def _featured_grid(names: list[str]) -> str:
    rows = []
    for i in range(0, len(names), 2):
        rows.append('<p align="center">')
        for n in names[i:i + 2]:
            rows.append(f'  <a href="https://github.com/{GH_USER}/{n}"><img src="./{ASSETS_DIR}/featured/{n}.svg" '
                        f'width="49%" alt="{n} — featured project"/></a>')
        rows.append('</p>')
    return "\n".join(rows)


def _featured_names_in_readme() -> list[str]:
    try:
        text = Path(README_PATH).read_text(encoding="utf-8")
        m = re.search(r"<!--\s*FEATURED_PROJECTS:START\s*-->(.*?)<!--\s*FEATURED_PROJECTS:END\s*-->", text, re.S)
        return re.findall(r"assets/featured/([^\"/]+)\.svg", m.group(1)) if m else []
    except Exception:
        return []


def _short_desc(desc: str, n: int = 64) -> str:
    desc = " ".join((desc or "").split())
    first = re.split(r" — | - |\. ", desc)[0].rstrip(".")
    return _clip(first or desc, n) if first else "—"


def fetch_pinned_repos() -> str:
    """Compact project index: every active repo not already in the spotlight or the
    featured grid, grouped by category, as a two-column HTML table."""
    r = requests.get(f"https://api.github.com/users/{GH_USER}/repos?per_page=100&type=owner",
                     headers=GH_HEADERS, timeout=20)
    r.raise_for_status()
    shown = _spotlight_names() | set(_FEATURED_NAMES or _featured_names_in_readme()) | {GH_USER}
    repos = [x for x in r.json() if not x.get("fork") and not x.get("archived") and x["name"] not in shown]
    order = ["tools", "ai", "backend", "frontend", "game"]
    titles = {"tools": "Developer tools", "ai": "AI · Data", "backend": "Backend / API",
              "frontend": "Frontend", "game": "Games"}
    buckets: dict[str, list[dict]] = {k: [] for k in order}
    for repo in repos:
        buckets[_categorize_repo(repo)].append(repo)
    rows = []
    for k in order:
        items = sorted(buckets[k], key=lambda x: (-x.get("stargazers_count", 0), x["name"].lower()))
        if not items:
            continue
        rows.append(f'<tr><th align="left" colspan="2">{titles[k]} <sub>· {len(items)}</sub></th></tr>')
        rows += [f'<tr><td><a href="https://github.com/{GH_USER}/{x["name"]}"><b>{html_escape(x["name"])}</b></a></td>'
                 f'<td>{html_escape(_short_desc(x.get("description") or ""))}</td></tr>' for x in items]
    if not rows:
        return "_Nothing else to list yet._"
    return '<table width="100%">\n' + "\n".join(rows) + "\n</table>"


# --- STATS CACHE BUSTER ------------------------------------------------------
# GitHub's camo image proxy caches the live-rendered stats services for hours.
# Append a daily-rotating ?v= or &v= to force a fresh fetch.

_STATS_HOSTS = (
    "github-readme-stats.vercel.app",
    "github-readme-streak-stats.herokuapp.com",
    "github-profile-summary-cards.vercel.app",
    "github-profile-trophy.vercel.app",
    "github-readme-activity-graph.vercel.app",
    "komarev.com",
    "img.shields.io",
)


def bust_stats_cache(text: str) -> str:
    """Rotate the ?v= / &v= query param on every stats-card URL to today's date."""
    today = dt.date.today().strftime("%Y%m%d")

    def _bust(match: re.Match) -> str:
        url = match.group(0)
        # Strip an existing v= we previously injected
        url = re.sub(r"([?&])v=\d{8}(?=[&\"]|$)", r"\1", url)
        url = re.sub(r"\?\&", "?", url).rstrip("?&")
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}v={today}"

    pattern = re.compile(
        r'https://(?:' + "|".join(re.escape(h) for h in _STATS_HOSTS) + r')[^\s"\'<>]+'
    )
    return pattern.sub(_bust, text)


# --- MAIN --------------------------------------------------------------------


def main() -> int:
    activity_only = "--activity-only" in sys.argv

    if not activity_only:
        # Follow repo renames first, so every section below uses the current names.
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
            import repo_names
            repo_names.sync_renames()
        except Exception as e:
            warn(f"rename sync failed (continuing with the names on file): {e}")

        # Regenerate per-year contribution heatmap + skyline SVGs first so the
        # snake/skyline marker bodies reference fresh files in this same commit.
        try:
            regenerate_yearly_assets()
        except Exception as e:
            warn(f"yearly asset regeneration failed (continuing with existing files): {e}")

        # Self-hosted GitHub Stats cards — independent of the flaky
        # github-readme-stats.vercel.app service.
        try:
            regenerate_stats_cards()
        except Exception as e:
            warn(f"stats cards regeneration failed: {e}")

        try:
            render_spotlight_svgs()
        except Exception as e:
            warn(f"spotlight regeneration failed: {e}")

        # Regenerate the About-Me hero SVG too (idempotent — same byte output
        # given same date, so no spurious commits).
        try:
            from pathlib import Path as _P
            import importlib.util as _ilu
            scripts_dir = _P(__file__).resolve().parents[2] / "scripts"
            spec = _ilu.spec_from_file_location("about_hero", scripts_dir / "build_about_hero.py")
            if spec and spec.loader:
                mod = _ilu.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.main()
        except Exception as e:
            warn(f"about-hero rebuild failed: {e}")

    with open(README_PATH, encoding="utf-8") as f:
        text = f.read()
    original = text

    if activity_only:
        # 3-hourly fast path — redraw the activity + releases SVGs, then the cache-buster.
        regenerate_activity_cards()
        sections: list[tuple[str, Callable[[], str]]] = []
    else:
        # Full daily refresh.
        sections = [
            ("PAGESPEED", fetch_pagespeed),
            ("CONTRIB_LINKS", contrib_links),
            ("QUOTE", quote_of_the_day),
        ]
        # Featured cards re-rank on every full run; the index runs after them so it
        # can leave out whatever the cards show.
        sections.append(("FEATURED_PROJECTS", fetch_featured_projects))
        sections.append(("PINNED_REPOS", fetch_pinned_repos))

    for marker, fn in sections:
        try:
            body = fn()
            text = replace_block(text, marker, body)
            print(f"updated {marker}")
        except Exception as e:
            warn(f"{marker} update failed: {e}")

    # Cache-buster always runs — daily-rotating ?v= on every stats URL.
    text = bust_stats_cache(text)

    if text == original:
        print("no changes")
        return 0
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    print("README updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
