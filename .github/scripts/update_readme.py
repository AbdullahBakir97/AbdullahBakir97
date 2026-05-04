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
from pathlib import Path
from typing import Callable

import requests

GH_USER = os.environ.get("GH_USER", "AbdullahBakir97")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
PSI_API_KEY = os.environ.get("PSI_API_KEY", "")
PSI_URL = os.environ.get("PSI_URL", "http://kharsa-style.de/")
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


def fetch_activity(limit: int = 8) -> str:
    r = requests.get(
        f"https://api.github.com/users/{GH_USER}/events/public?per_page=30",
        headers=GH_HEADERS,
        timeout=20,
    )
    r.raise_for_status()
    lines: list[str] = []
    for event in r.json():
        formatter = EVENT_FORMATTERS.get(event["type"])
        if not formatter:
            continue
        line = formatter(event)
        if line:
            lines.append(f"- {line}")
        if len(lines) >= limit:
            break
    if not lines:
        return "_No recent public activity._"
    return "\n".join(lines)


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
    out = []
    for row in rows[:limit]:
        date = row["at"][:10]
        out.append(
            f"- 📦 [`{row['repo']}` `{row['tag']}`]({row['url']}) — {row['name']} "
            f"<sub>({date})</sub>"
        )
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


def fetch_pagespeed() -> str:
    params = [("url", PSI_URL), ("strategy", "mobile")]
    for cat in PSI_CATEGORIES:
        params.append(("category", cat))
    if PSI_API_KEY:
        params.append(("key", PSI_API_KEY))
    qs = urllib.parse.urlencode(params)
    url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?{qs}"
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=120)
            if r.status_code == 429:
                hint = "" if PSI_API_KEY else " (set PSI_API_KEY secret to lift rate limits)"
                raise RuntimeError(f"PSI rate-limited{hint}")
            r.raise_for_status()
            break
        except Exception as e:
            last_exc = e
            if attempt < 2:
                import time
                time.sleep(5 * (attempt + 1))
    else:
        raise last_exc  # type: ignore[misc]
    categories = r.json().get("lighthouseResult", {}).get("categories", {})
    scores: dict[str, int] = {}
    for cat in PSI_CATEGORIES:
        key = cat.lower().replace("_", "-")
        node = categories.get(key)
        if node and node.get("score") is not None:
            scores[cat] = round(node["score"] * 100)
    if not scores:
        return "_PageSpeed scores unavailable._"

    badges: list[str] = []
    rows: list[str] = []
    for cat in PSI_CATEGORIES:
        if cat not in scores:
            continue
        pct = scores[cat]
        label = PSI_LABELS[cat]
        color = score_color(pct)
        badges.append(
            f'<img src="https://img.shields.io/badge/{label}-{pct}%25-{color}'
            f'?style=for-the-badge&logo=google&logoColor=white" alt="{label}: {pct}%" />'
        )
        rows.append(f"<tr><td>{label.replace('_', ' ')}</td><td>{pct}/100</td></tr>")

    today = dt.date.today().isoformat()
    return (
        '<p align="center">' + "\n  ".join(badges) + "</p>\n\n"
        '<table align="center"><tr><th>Metric</th><th>Score</th></tr>\n'
        + "\n".join(rows)
        + "\n</table>\n\n"
        f'<p align="center"><em>Last updated {today} (mobile strategy).</em></p>'
    )


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
        f'<img src="https://img.shields.io/badge/Commits-{cc["totalCommitContributions"]}-red?style=for-the-badge&logo=git&logoColor=white" alt="Commits" /> '
        f'<img src="https://img.shields.io/badge/PRs-{cc["totalPullRequestContributions"]}-red?style=for-the-badge&logo=github&logoColor=white" alt="PRs" /> '
        f'<img src="https://img.shields.io/badge/New_Repos-{new_repos_count}-red?style=for-the-badge&logo=github&logoColor=white" alt="New repos" /> '
        f'<img src="https://img.shields.io/badge/Active_in-{active_repos}_repos-red?style=for-the-badge&logo=github&logoColor=white" alt="Active repos" />'
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

    lines = ["```mermaid", "gitGraph", '   commit id: "main"']
    for repo, count in pushes:
        # Sanitize branch name for Mermaid (no special chars)
        branch = re.sub(r"[^a-zA-Z0-9_-]", "-", repo)[:30] or "branch"
        lines.append(f"   branch {branch}")
        lines.append(f"   checkout {branch}")
        for i in range(min(count, 4)):  # cap at 4 commits per branch for readability
            lines.append(f'   commit id: "c{i + 1}"')
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

def _category_for(repo: dict) -> str:
    name = repo["name"]
    topics = set(repo.get("topics") or [])
    if name in {"PortfolioCraft", "GitHub-Doc-Generator", "Repo-Directory-Structure",
                "Python-Environment-Management-Tool", "API-Client-Generator",
                "commit-craft", "pr-coach", "repodoc-ai", "ai-quality-gate",
                "issue-triage-bot", "release-pilot"}:
        return "🛠️ Tooling"
    if topics & {"ai", "ml", "machine-learning", "rag", "llm"} or name in {"AI-KI", "Mini-RAG", "cortex"}:
        return "🧠 AI / Data"
    if topics & {"game", "pygame"} or name in {"Py-Tetris-Game", "Space-Shooter"}:
        return "🎮 Game"
    if (repo.get("language") or "") in ("Vue", "TypeScript", "JavaScript", "HTML", "CSS"):
        return "🎨 Frontend"
    return "🌐 Backend / API"


def _score_repo(repo: dict, recent_commits: int) -> float:
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    pushed = dt.datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
    days_since = max(0, (dt.datetime.now(dt.timezone.utc) - pushed).days)
    recency = max(0.0, 1.0 - days_since / 365.0)
    return 0.4 * stars + 0.4 * recent_commits + 0.2 * (recency * 50)


PIN_CARD_TITLE_COLOR = "#c6c6c2"
PIN_CARD_ICON_COLOR = "#ffde01"
PIN_CARD_TEXT_COLOR = "#da644d"

# Language → color (mirrors github-readme-stats / GitHub Linguist)
LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#F1E05A", "TypeScript": "#3178C6",
    "Vue": "#41B883", "HTML": "#E34F26", "CSS": "#563D7C", "SCSS": "#C6538C",
    "Jupyter Notebook": "#DA5B0B", "Shell": "#89E051", "Dockerfile": "#384D54",
    "Java": "#B07219", "Go": "#00ADD8", "Rust": "#DEA584", "C": "#555555",
    "C++": "#F34B7D", "C#": "#178600", "PHP": "#4F5D95", "Ruby": "#701516",
    "Inno Setup": "#264B99", "MDX": "#1B6E5E",
}

PIN_W, PIN_H = 460, 200


def _truncate(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def _wrap_lines_pin(s: str, line_chars: int, max_lines: int) -> list[str]:
    s = (s or "").strip()
    out: list[str] = []
    while s and len(out) < max_lines:
        if len(s) <= line_chars:
            out.append(s)
            break
        cut = s.rfind(" ", 0, line_chars + 1)
        if cut <= 0:
            cut = line_chars
        out.append(s[:cut].rstrip())
        s = s[cut:].lstrip()
    if s and len(out) == max_lines:
        last = out[-1]
        room = line_chars - 1
        out[-1] = (last[: room].rstrip() + "…") if len(last) > room else last
    return out


def render_pin_svg(repo: dict, dest: Path) -> None:
    """Render a Pinned repo card — 460x200, distinctly styled vs the
    larger Featured cards. Editorial layout: repo icon + name header,
    2-line description, topic chips, lang dot + star/fork stats, last
    commit timestamp. No third-party dependency."""
    name = repo["name"]
    desc = (repo.get("description") or "_No description._").strip()
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    lang = repo.get("language") or "—"
    lang_color = LANG_COLORS.get(lang, "#6e7681")
    topics = (repo.get("topics") or [])[:5]
    pushed = (repo.get("pushed_at") or "")[:10]

    desc_lines = _wrap_lines_pin(desc, 52, 2)
    title = _truncate(name, 30)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{PIN_W}" height="{PIN_H}" '
        f'viewBox="0 0 {PIN_W} {PIN_H}" role="img" aria-label="{name}">',
        '<defs>'
        # Background — subtle inverse gradient (pin uses dark-to-mid, featured uses mid-to-dark)
        '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#161b22"/>'
        '<stop offset="100%" stop-color="#0a0e14"/>'
        '</linearGradient>'
        # Pin accent stripe gradient (yellow→red, distinct from featured's red→purple)
        '<linearGradient id="pinAccent" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#ffde01"/>'
        '<stop offset="100%" stop-color="#F90001"/>'
        '</linearGradient>'
        '</defs>',
        # Card body
        f'<rect width="{PIN_W-2}" height="{PIN_H-2}" x="1" y="1" rx="10" '
        f'fill="url(#bg)" stroke="#30363d" stroke-width="1"/>',
        # Left vertical accent stripe (yellow→red, full height — visual fingerprint of "pin")
        f'<rect x="0" y="0" width="4" height="{PIN_H}" fill="url(#pinAccent)" rx="2"/>',
    ]

    # Header — pin icon + repo name
    parts.append(
        # Stylized pin emoji (rendered as text — works in pure SVG)
        f'<text x="20" y="36" font-family="-apple-system,Segoe UI Emoji,sans-serif" '
        f'font-size="18" fill="#F90001">📌</text>'
        # Repo name
        f'<text x="46" y="36" '
        f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
        f'font-size="17" font-weight="800" fill="#e6edf3" letter-spacing="-0.2">'
        f'{title}</text>'
    )
    # "PINNED" tag on the right
    parts.append(
        f'<g transform="translate({PIN_W-72}, 18)">'
        f'<rect width="58" height="22" rx="11" fill="#0d1117" '
        f'stroke="#ffde01" stroke-width="1"/>'
        f'<text x="29" y="15" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="9.5" font-weight="700" fill="#ffde01" letter-spacing="1.5">'
        f'PINNED</text>'
        f'</g>'
    )

    # Description (2 lines)
    desc_y = 64
    for i, line in enumerate(desc_lines):
        parts.append(
            f'<text x="20" y="{desc_y + i*18}" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
            f'font-size="12.5" font-weight="400" fill="#c9d1d9" opacity="0.9">'
            f'{line}</text>'
        )

    # Topic chips
    chip_y = 116
    chip_x = 20
    for i, t in enumerate(topics):
        bg, fg = TOPIC_PALETTE[i % len(TOPIC_PALETTE)]
        chip_w = max(48, len(t) * 6.5 + 14)
        if chip_x + chip_w > PIN_W - 16:
            break
        parts.append(
            f'<g transform="translate({chip_x}, {chip_y})">'
            f'<rect width="{chip_w}" height="20" rx="10" fill="#0d1117" '
            f'stroke="{bg}" stroke-width="1"/>'
            f'<text x="{chip_w//2}" y="14" text-anchor="middle" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
            f'font-size="10" font-weight="600" fill="{fg}" letter-spacing="0.2">'
            f'{t}</text>'
            f'</g>'
        )
        chip_x += chip_w + 5

    # Footer — language + stars + forks + last commit
    foot_y = PIN_H - 22
    # Language dot + name
    parts.append(
        f'<circle cx="28" cy="{foot_y-4}" r="6" fill="{lang_color}"/>'
        f'<text x="40" y="{foot_y}" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="12" font-weight="600" fill="#c9d1d9">'
        f'{lang}</text>'
    )
    # Stars
    star_x = 130
    parts.append(
        f'<g transform="translate({star_x}, {foot_y-12})">'
        f'<path d="M8 0l2.39 4.84L16 5.6l-4 3.9.94 5.5L8 12.4 3.06 15l.94-5.5-4-3.9 5.61-.76L8 0z" '
        f'fill="#ffde01"/>'
        f'</g>'
        f'<text x="{star_x+22}" y="{foot_y}" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="12" font-weight="700" fill="#c9d1d9">'
        f'{stars}</text>'
    )
    # Forks
    fork_x = star_x + 60
    parts.append(
        f'<g transform="translate({fork_x}, {foot_y-12})" stroke="#7d8590" stroke-width="1.5" fill="none">'
        f'<circle cx="3" cy="3" r="2"/>'
        f'<circle cx="13" cy="3" r="2"/>'
        f'<circle cx="8" cy="14" r="2"/>'
        f'<path d="M3 5v3a2 2 0 002 2h6a2 2 0 002-2V5"/>'
        f'<line x1="8" y1="10" x2="8" y2="12"/>'
        f'</g>'
        f'<text x="{fork_x+22}" y="{foot_y}" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="12" font-weight="700" fill="#c9d1d9">'
        f'{forks}</text>'
    )
    # Last commit (right aligned)
    parts.append(
        f'<text x="{PIN_W-20}" y="{foot_y}" text-anchor="end" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="11" font-weight="500" fill="#7d8590">'
        f'updated {pushed}</text>'
    )

    parts.append('</svg>')

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(parts), encoding="utf-8")


def regenerate_pin_svgs(repos: list[dict]) -> None:
    pins_dir = Path(ASSETS_DIR) / "pins"
    pins_dir.mkdir(parents=True, exist_ok=True)
    for r in repos:
        try:
            render_pin_svg(r, pins_dir / f"{r['name']}.svg")
        except Exception as e:
            warn(f"pin render failed for {r['name']}: {e}")


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


def render_main_stats_svg(dest: Path) -> None:
    """Emulate github-readme-stats main card with codeSTACKr-style theme.
    Pulls live numbers via GraphQL — independent of the 503'd service."""
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

    # Title
    name = user.get("name") or GH_USER
    title = f"{name}'s GitHub Stats"

    W, H = 495, 195
    rows = [
        ("Total Stars Earned",         _fmt(total_stars),       "⭐"),
        ("Total Commits ({year})".format(year=now.year), _fmt(total_commits_yr), "🕒"),
        ("Total PRs",                  _fmt(total_prs),          "🔀"),
        ("Total Issues",               _fmt(total_issues),       "❗"),
        ("Contributed to (last year)", _fmt(contributed_to),     "🤝"),
    ]

    # Compute simple "rank" (A+ if all metrics over thresholds, scale down)
    score = (
        (1 if total_stars >= 100 else 0) +
        (1 if total_commits_yr >= 1000 else 0) +
        (1 if total_prs >= 50 else 0) +
        (1 if total_issues >= 50 else 0) +
        (1 if contributed_to >= 10 else 0)
    )
    rank_label = ["B", "B+", "A-", "A", "A+", "S"][min(score, 5)]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-label="{title}">',
        '<defs>'
        '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#1a1f29"/>'
        '<stop offset="100%" stop-color="#0d1117"/>'
        '</linearGradient>'
        '<linearGradient id="rankRing" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#F90001"/>'
        '<stop offset="100%" stop-color="#FF652F"/>'
        '</linearGradient>'
        '</defs>',
        f'<rect width="{W-2}" height="{H-2}" x="1" y="1" rx="6" '
        f'fill="url(#bg)" stroke="#30363d" stroke-width="1"/>',
        # Title
        f'<text x="20" y="32" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="16" font-weight="700" fill="#c6c6c2">'
        f'{title}</text>',
        # Underline accent
        f'<line x1="20" y1="40" x2="{W-130}" y2="40" stroke="#30363d" stroke-width="1"/>',
    ]

    # Rows
    row_y = 65
    for i, (label, value, icon) in enumerate(rows):
        y = row_y + i * 22
        parts.append(
            f'<text x="20" y="{y}" font-family="Segoe UI Emoji,Apple Color Emoji,sans-serif" '
            f'font-size="14" fill="#ffde01">{icon}</text>'
            f'<text x="44" y="{y}" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
            f'font-size="13" fill="#da644d">{label}:</text>'
            f'<text x="{W-130}" y="{y}" text-anchor="end" '
            f'font-family="-apple-system,BlinkMacSystemFont,SF Mono,Monaco,monospace" '
            f'font-size="14" font-weight="700" fill="#c6c6c2">{value}</text>'
        )

    # Rank badge (right side)
    rank_cx, rank_cy = W - 75, H // 2
    rank_r = 50
    parts.append(
        # Outer gradient ring
        f'<circle cx="{rank_cx}" cy="{rank_cy}" r="{rank_r}" fill="none" '
        f'stroke="#30363d" stroke-width="6"/>'
        f'<circle cx="{rank_cx}" cy="{rank_cy}" r="{rank_r}" fill="none" '
        f'stroke="url(#rankRing)" stroke-width="6" '
        f'stroke-dasharray="{(score+1)*52} 314" '
        f'transform="rotate(-90 {rank_cx} {rank_cy})"/>'
        # Center
        f'<text x="{rank_cx}" y="{rank_cy+12}" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,sans-serif" '
        f'font-size="32" font-weight="900" fill="#c6c6c2">{rank_label}</text>'
    )

    parts.append('</svg>')

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(parts), encoding="utf-8")


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

    W, H = 495, 195
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-label="Top Languages">',
        '<defs>'
        '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#1a1f29"/>'
        '<stop offset="100%" stop-color="#0d1117"/>'
        '</linearGradient>'
        '</defs>',
        f'<rect width="{W-2}" height="{H-2}" x="1" y="1" rx="6" '
        f'fill="url(#bg)" stroke="#30363d" stroke-width="1"/>',
        # Title
        f'<text x="20" y="32" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="16" font-weight="700" fill="#ff6f00">'
        f'Most Used Languages</text>',
        f'<line x1="20" y1="40" x2="{W-20}" y2="40" stroke="#30363d" stroke-width="1"/>',
    ]

    # Stacked bar
    bar_x, bar_y, bar_w, bar_h = 20, 56, W - 40, 14
    cur_x = bar_x
    for name, size in sorted_items:
        pct = size / grand_total
        seg = max(2, int(bar_w * pct))
        parts.append(
            f'<rect x="{cur_x}" y="{bar_y}" width="{seg}" height="{bar_h}" '
            f'fill="{colors[name]}" '
            + ('rx="7"' if cur_x == bar_x else '')
            + '/>'
        )
        cur_x += seg
    # Round the right edge of the last segment by overlaying a rounded rect
    parts.append(
        f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" '
        f'rx="7" fill="none" stroke="#30363d" stroke-width="0.5"/>'
    )

    # Two-column legend
    leg_y = bar_y + bar_h + 24
    col_w = (W - 40) // 2
    for i, (name, size) in enumerate(sorted_items):
        col = i % 2
        row = i // 2
        x = bar_x + col * col_w
        y = leg_y + row * 22
        pct = (size / grand_total) * 100
        parts.append(
            f'<circle cx="{x+8}" cy="{y-3}" r="6" fill="{colors[name]}"/>'
            f'<text x="{x+22}" y="{y}" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
            f'font-size="12" font-weight="600" fill="#c6c6c2">{name}</text>'
            f'<text x="{x+col_w-6}" y="{y}" text-anchor="end" '
            f'font-family="-apple-system,BlinkMacSystemFont,SF Mono,Monaco,monospace" '
            f'font-size="11" fill="#7d8590">{pct:.1f}%</text>'
        )

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
        '<stop offset="0%" stop-color="#ffd700"/>'
        '<stop offset="100%" stop-color="#d60606"/>'
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
                f'font-size="40" font-weight="800" fill="#ffd700">'
                f'{value}</text>'
            )
        else:
            parts.append(
                f'<text x="{cx}" y="73" text-anchor="middle" '
                f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
                f'font-size="40" font-weight="800" fill="#c6c6c2">'
                f'{value}</text>'
            )

        # Label
        parts.append(
            f'<text x="{cx}" y="115" text-anchor="middle" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
            f'font-size="13" font-weight="700" fill="#da644d" letter-spacing="0.3">'
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


def regenerate_stats_cards() -> None:
    stats_dir = Path(ASSETS_DIR) / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)
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


# --- RICH FEATURED-PROJECT CARD ---------------------------------------------
# Distinct visual style from the small pin card: 720x240, three-line
# description, topic chips, fuller metrics, trending indicator on the right.

FEATURED_W, FEATURED_H = 720, 240

# Topic chip palette — cycle so chips of different topics look visually distinct
TOPIC_PALETTE = [
    ("#1f6feb", "#388bfd"),   # blue
    ("#bf4b8a", "#db61a2"),   # pink
    ("#3fb950", "#56d364"),   # green
    ("#d29922", "#e3b341"),   # gold
    ("#a371f7", "#bc8cff"),   # purple
    ("#f78166", "#ffa28b"),   # orange
    ("#39c5cf", "#76e3ea"),   # teal
]


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


def _wrap_lines(s: str, line_chars: int, max_lines: int) -> list[str]:
    s = (s or "").strip()
    out: list[str] = []
    while s and len(out) < max_lines:
        if len(s) <= line_chars:
            out.append(s)
            break
        cut = s.rfind(" ", 0, line_chars + 1)
        if cut <= 0:
            cut = line_chars
        out.append(s[:cut].rstrip())
        s = s[cut:].lstrip()
    if s and len(out) == max_lines:
        # ellipsize the last line
        last = out[-1]
        room = line_chars - 1
        if len(last) > room:
            last = last[: room - 1].rstrip() + "…"
        else:
            last = last[: room].rstrip() + "…"
        out[-1] = last
    return out


def render_featured_card_svg(repo: dict, recent_commits: int, dest: Path) -> None:
    """Render a rich Featured Project card — 720x240, distinct from pin cards.

    Layout:
      - Header strip (top, 50px): category icon + repo name + trending badge
      - Description block (3 lines, 60px)
      - Topics chip row (40px, up to 5 chips)
      - Footer stats row (40px): lang dot + name | ⭐ N | 🍴 N | created · updated
    """
    name = repo["name"]
    desc = (repo.get("description") or "").strip() or "_No description._"
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    watchers = repo.get("watchers_count", stars)
    lang = repo.get("language") or "—"
    lang_color = LANG_COLORS.get(lang, "#6e7681")
    topics = (repo.get("topics") or [])[:6]
    pushed = (repo.get("pushed_at") or "")[:10]
    created = (repo.get("created_at") or "")[:10]
    pushed_human = _humanize_date(repo.get("pushed_at") or "")

    # Category emoji
    category = _category_for(repo)
    cat_emoji = category.split(" ")[0]
    cat_text = " ".join(category.split(" ")[1:])

    # Trending badge — show if many recent commits
    if recent_commits >= 30:
        trend_label, trend_color = f"🔥 {recent_commits}/30d", "#F90001"
    elif recent_commits >= 10:
        trend_label, trend_color = f"⚡ {recent_commits}/30d", "#FF652F"
    elif recent_commits >= 1:
        trend_label, trend_color = f"📈 {recent_commits}/30d", "#39d353"
    else:
        trend_label, trend_color = "💤 quiet", "#7d8590"

    desc_lines = _wrap_lines(desc, 60, 3)

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{FEATURED_W}" '
        f'height="{FEATURED_H}" viewBox="0 0 {FEATURED_W} {FEATURED_H}" '
        f'role="img" aria-label="{name} — featured project card">'
    )

    # Defs
    parts.append(
        '<defs>'
        '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#1f242c"/>'
        '<stop offset="100%" stop-color="#0d1117"/>'
        '</linearGradient>'
        '<linearGradient id="accentGrad" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0%" stop-color="#F90001"/>'
        '<stop offset="50%" stop-color="#FF652F"/>'
        '<stop offset="100%" stop-color="#a855f7"/>'
        '</linearGradient>'
        '<filter id="bloom" x="-50%" y="-50%" width="200%" height="200%">'
        '<feGaussianBlur stdDeviation="2.4" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
        '</defs>'
    )

    # Card background
    parts.append(
        f'<rect width="{FEATURED_W-2}" height="{FEATURED_H-2}" x="1" y="1" '
        f'rx="10" fill="url(#bg)" stroke="#30363d" stroke-width="1"/>'
    )
    # Top accent strip
    parts.append(
        f'<rect width="{FEATURED_W-20}" height="3" x="10" y="0" '
        f'fill="url(#accentGrad)" rx="1.5"/>'
    )

    # ── Header row: category badge + repo name + trending pill ───────────
    # Category pill (left)
    parts.append(
        f'<g transform="translate(20, 22)">'
        f'<rect width="148" height="26" rx="13" fill="#161b22" stroke="#30363d" stroke-width="1"/>'
        f'<text x="74" y="18" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="12" font-weight="700" fill="#c9d1d9" letter-spacing="0.5">'
        f'{cat_emoji} {cat_text[:14]}</text>'
        f'</g>'
    )
    # Repo name (centered, large)
    parts.append(
        f'<text x="20" y="78" '
        f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
        f'font-size="22" font-weight="800" fill="#e6edf3" letter-spacing="-0.3">'
        f'{name}</text>'
    )
    # Trending pill (right) — anchored to the right edge
    parts.append(
        f'<g transform="translate({FEATURED_W-148}, 22)">'
        f'<rect width="128" height="26" rx="13" fill="#0d1117" '
        f'stroke="{trend_color}" stroke-width="1.5"/>'
        f'<text x="64" y="18" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="12" font-weight="700" fill="{trend_color}" letter-spacing="0.5">'
        f'{trend_label}</text>'
        f'</g>'
    )

    # ── Description (up to 3 lines) ──────────────────────────────────────
    desc_y = 105
    for i, line in enumerate(desc_lines):
        parts.append(
            f'<text x="20" y="{desc_y + i*20}" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
            f'font-size="13" font-weight="400" fill="#c9d1d9" opacity="0.9">'
            f'{line}</text>'
        )

    # ── Topic chips ──────────────────────────────────────────────────────
    chip_y = 175
    chip_x = 20
    for i, t in enumerate(topics):
        bg, fg = TOPIC_PALETTE[i % len(TOPIC_PALETTE)]
        chip_w = max(48, len(t) * 7 + 16)
        if chip_x + chip_w > FEATURED_W - 20:
            break  # ran out of room
        parts.append(
            f'<g transform="translate({chip_x}, {chip_y})">'
            f'<rect width="{chip_w}" height="22" rx="11" fill="#0d1117" '
            f'stroke="{bg}" stroke-width="1"/>'
            f'<text x="{chip_w//2}" y="15" text-anchor="middle" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
            f'font-size="10.5" font-weight="600" fill="{fg}" letter-spacing="0.2">'
            f'{t}</text>'
            f'</g>'
        )
        chip_x += chip_w + 6

    # ── Footer stats row ─────────────────────────────────────────────────
    foot_y = FEATURED_H - 20
    # Language
    parts.append(
        f'<circle cx="28" cy="{foot_y-4}" r="6" fill="{lang_color}"/>'
        f'<text x="40" y="{foot_y}" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="12" font-weight="600" fill="#c9d1d9">'
        f'{lang}</text>'
    )
    # Stars
    star_x = 130
    parts.append(
        f'<g transform="translate({star_x}, {foot_y-12})">'
        f'<path d="M8 0l2.39 4.84L16 5.6l-4 3.9.94 5.5L8 12.4 3.06 15l.94-5.5-4-3.9 5.61-.76L8 0z" '
        f'fill="#ffde01"/>'
        f'</g>'
        f'<text x="{star_x+22}" y="{foot_y}" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="12" font-weight="700" fill="#c9d1d9">'
        f'{stars}</text>'
    )
    # Forks
    fork_x = star_x + 70
    parts.append(
        f'<g transform="translate({fork_x}, {foot_y-12})" stroke="#7d8590" stroke-width="1.5" fill="none">'
        f'<circle cx="3" cy="3" r="2"/>'
        f'<circle cx="13" cy="3" r="2"/>'
        f'<circle cx="8" cy="14" r="2"/>'
        f'<path d="M3 5v3a2 2 0 002 2h6a2 2 0 002-2V5"/>'
        f'<line x1="8" y1="10" x2="8" y2="12"/>'
        f'</g>'
        f'<text x="{fork_x+22}" y="{foot_y}" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="12" font-weight="700" fill="#c9d1d9">'
        f'{forks}</text>'
    )
    # Watchers (eye)
    eye_x = fork_x + 70
    parts.append(
        f'<g transform="translate({eye_x}, {foot_y-12})" stroke="#7d8590" stroke-width="1.4" fill="none">'
        f'<path d="M0 8 C 4 2, 12 2, 16 8 C 12 14, 4 14, 0 8 Z"/>'
        f'<circle cx="8" cy="8" r="2.2" fill="#7d8590"/>'
        f'</g>'
        f'<text x="{eye_x+22}" y="{foot_y}" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="12" font-weight="700" fill="#c9d1d9">'
        f'{watchers}</text>'
    )
    # Created · updated (right-aligned)
    parts.append(
        f'<text x="{FEATURED_W-20}" y="{foot_y}" text-anchor="end" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="11" font-weight="500" fill="#7d8590">'
        f'created {created}  ·  updated {pushed_human}</text>'
    )

    parts.append('</svg>')

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(parts), encoding="utf-8")


def _pin_card_url(name: str, lines: int = 2) -> str:
    """Reference the locally-rendered pin card. Independent of the flaky
    github-readme-stats.vercel.app service (which 503s frequently)."""
    return f"./{ASSETS_DIR}/pins/{name}.svg"


def _render_pin_grid(repos: list[dict]) -> str:
    """Render a 2-col grid of github-readme-stats pin cards."""
    if not repos:
        return ""
    rows = []
    for i in range(0, len(repos), 2):
        rows.append('<div align="center">')
        for j in range(2):
            if i + j >= len(repos):
                continue
            r = repos[i + j]
            name = r["name"]
            url = _pin_card_url(name)
            rows.append(
                f'  <a href="https://github.com/{GH_USER}/{name}">'
                f'<img src="{url}" width="49%" alt="{name}" /></a>'
            )
        rows.append('</div>')
    return "\n".join(rows)


def fetch_featured_projects(limit: int = 10) -> str:
    """Top N most-active owned non-fork non-archived repos, rendered as
    github-readme-stats pin cards (consistent visual with Pinned Repos)."""
    r = requests.get(
        f"https://api.github.com/users/{GH_USER}/repos?per_page=100&type=owner",
        headers=GH_HEADERS, timeout=20,
    )
    r.raise_for_status()
    repos = [
        x for x in r.json()
        if not x.get("fork") and not x.get("archived")
        and x["name"] != GH_USER  # exclude profile readme repo
    ]
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).isoformat()
    scored = []
    for repo in repos:
        commits = 0
        try:
            cr = requests.get(
                f"https://api.github.com/repos/{GH_USER}/{repo['name']}/commits",
                headers=GH_HEADERS, params={"since": since, "per_page": 100}, timeout=10,
            )
            if cr.ok:
                commits = len(cr.json())
        except Exception:
            pass
        scored.append((_score_repo(repo, commits), repo, commits))
    scored.sort(key=lambda t: -t[0])
    top = [r for _, r, _ in scored[:limit]]

    if not top:
        return "_No featured projects yet._"

    # Side effect: render rich Featured-card SVGs for each entry.
    feat_dir = Path(ASSETS_DIR) / "featured"
    feat_dir.mkdir(parents=True, exist_ok=True)
    # commit-count map needed for trending labels
    commits_by_name = {r["name"]: c for _, r, c in scored}
    for r in top:
        try:
            render_featured_card_svg(r, commits_by_name.get(r["name"], 0),
                                     feat_dir / f"{r['name']}.svg")
        except Exception as e:
            warn(f"featured render failed for {r['name']}: {e}")

    # Render as 2-col grid of <a><img></a> referencing the new cards
    rows = []
    for i in range(0, len(top), 2):
        rows.append('<div align="center">')
        for j in range(2):
            if i + j >= len(top):
                continue
            n = top[i + j]["name"]
            rows.append(
                f'  <a href="https://github.com/{GH_USER}/{n}">'
                f'<img src="./{ASSETS_DIR}/featured/{n}.svg" '
                f'width="49%" alt="{n} — featured project card" /></a>'
            )
        rows.append('</div>')

    today = dt.date.today().isoformat()
    return (
        f'<p align="center"><sub>🔥 Top {len(top)} most-active repos · '
        f'rich cards with topics, last-updated, watchers · ranked by recent '
        f'commits + stars. Last updated {today}.</sub></p>\n\n'
        + "\n".join(rows)
    )


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
    if name in {"AI-KI", "Mini-RAG", "cortex"}:
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


def fetch_pinned_repos() -> str:
    """Render an exhaustive showcase grid: pinned repos at the top, then
    every active (non-archived) repo grouped by category, all using the
    consistent github-readme-stats pin-card visual style."""
    r = requests.get(
        f"https://api.github.com/users/{GH_USER}/repos?per_page=100&type=owner",
        headers=GH_HEADERS, timeout=20,
    )
    r.raise_for_status()
    all_repos = [
        x for x in r.json()
        if not x.get("fork") and not x.get("archived")
    ]

    # Pinned via GraphQL (authoritative for pin order)
    PINNED_Q = """
    query($login: String!) {
      user(login: $login) {
        pinnedItems(first: 6, types: REPOSITORY) {
          nodes { ... on Repository { name } }
        }
      }
    }
    """
    pinned_names = []
    try:
        data = graphql(PINNED_Q, {"login": GH_USER})
        pinned_names = [n["name"] for n in data["user"]["pinnedItems"]["nodes"]]
    except Exception as e:
        warn(f"pinnedItems query failed: {e}")

    by_name = {r["name"]: r for r in all_repos}
    pinned_set = set(pinned_names)

    pinned_repos = [by_name[n] for n in pinned_names if n in by_name]
    rest = [r for r in all_repos if r["name"] not in pinned_set]
    rest.sort(key=lambda r: -r.get("stargazers_count", 0))

    # Category buckets (rest)
    buckets: dict[str, list[dict]] = {
        "most_starred": [], "tools": [], "backend": [],
        "frontend": [], "ai": [], "game": [],
    }
    for r in rest:
        if r.get("stargazers_count", 0) >= 10:
            buckets["most_starred"].append(r)
        else:
            buckets[_categorize_repo(r)].append(r)

    # Side effect: render pin SVG for every repo we'll show, so all <img src>
    # references in the markdown resolve to local files (independent of
    # third-party stats services).
    showcase_set = list(pinned_repos)
    seen = {r["name"] for r in showcase_set}
    for r in all_repos:
        if r["name"] not in seen:
            showcase_set.append(r)
            seen.add(r["name"])
    regenerate_pin_svgs(showcase_set)

    sections: list[str] = []

    if pinned_repos:
        sections.append('<h4 align="center">📌 Pinned by the author</h4>')
        sections.append(_render_pin_grid(pinned_repos))

    label_map = {
        "most_starred": ("⭐ Most-Starred Showcases", "Repos with notable community traction"),
        "tools":        ("🛠️ Developer Tools",        "GitHub Apps, CLIs, and dev-experience tooling"),
        "backend":      ("🌐 Backend / API",          "Django / DRF systems and reference APIs"),
        "frontend":     ("🎨 Frontend / UI",          "Vue, Nuxt, and design-forward web apps"),
        "ai":           ("🧠 AI · Data · Notebooks",  "RAG, agents, ML experiments"),
        "game":         ("🎮 Game",                   "Pygame & arcade clones"),
    }
    for key in ("most_starred", "tools", "backend", "frontend", "ai", "game"):
        items = buckets[key]
        if not items:
            continue
        title, sub = label_map[key]
        sections.append(f'<h4 align="center">{title} <sub>· {len(items)}</sub></h4>')
        sections.append(f'<p align="center"><sub><i>{sub}</i></sub></p>')
        sections.append(_render_pin_grid(items))

    today = dt.date.today().isoformat()
    sections.insert(
        0,
        f'<p align="center"><sub>🔄 Auto-refreshed daily · '
        f'<b>{len(all_repos)}</b> active repos shown across '
        f'<b>{sum(1 for k,v in buckets.items() if v) + (1 if pinned_repos else 0)}</b> categories. '
        f'Last updated {today}.</sub></p>'
    )

    return "\n\n".join(sections)


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
        # 3-hourly fast path — only activity + cache-buster + featured-trending.
        sections: list[tuple[str, Callable[[], str]]] = [
            ("ACTIVITY", fetch_activity),
        ]
    else:
        # Full daily refresh.
        sections = [
            ("ACTIVITY", fetch_activity),
            ("LATEST_RELEASES", fetch_releases),
            ("PAGESPEED", fetch_pagespeed),
            ("HIGHLIGHTS_STATS", fetch_year_stats),
            ("SNAKE_GRID", snake_grid),
            ("SKYLINE_GRID", skyline_grid),
            ("STL_LINKS", stl_links),
            ("CITY_GRID", city_grid),
            ("GITCITY_LINKS", gitcity_links),
            ("QUOTE", quote_of_the_day),
            ("GITGRAPH", gitgraph_from_activity),
            ("PINNED_REPOS", fetch_pinned_repos),
        ]
        # Featured Projects only refreshes if it's a Monday (or via dispatch flag),
        # but include it on every full run too — score is fast and idempotent.
        if "--include-featured" in sys.argv or dt.date.today().weekday() == 0:
            sections.append(("FEATURED_PROJECTS", fetch_featured_projects))

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
