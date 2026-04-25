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
import os
import re
import sys
import urllib.parse
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
    commits = e["payload"].get("commits") or []
    if not commits:
        return None  # skip empty pushes (branch deletes etc.)
    return f"⬆️ Pushed {len(commits)} commit(s) to {_repo_link(e['repo']['name'])}"


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
      totalRepositoriesWithContributedCommits
    }
  }
}
"""


def fetch_year_stats() -> str:
    start = f"{CURRENT_YEAR}-01-01T00:00:00Z"
    end = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = graphql(STATS_QUERY, {"login": GH_USER, "from": start, "to": end})
    cc = data["user"]["contributionsCollection"]

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
        f'<img src="https://img.shields.io/badge/Active_in-{cc["totalRepositoriesWithContributedCommits"]}_repos-red?style=for-the-badge&logo=github&logoColor=white" alt="Active repos" />'
        "</p>"
    )


# --- SKYLINE / CITY GRIDS -----------------------------------------------------

RAW_BASE = f"https://raw.githubusercontent.com/{GH_USER}/{GH_USER}/metrics-output"


def _years() -> list[int]:
    if CURRENT_YEAR < START_YEAR:
        return [CURRENT_YEAR]
    return list(range(START_YEAR, CURRENT_YEAR + 1))


def _grid(href_for: Callable[[int], str], svg_for: Callable[[int], str], alt_kind: str) -> str:
    years = _years()
    width = 100 // len(years)
    cells = []
    for y in years:
        label = f"{y} <sub>(live)</sub>" if y == CURRENT_YEAR else str(y)
        cells.append(
            f'<td width="{width}%" align="center">'
            f'<a href="{href_for(y)}">'
            f'<img src="{svg_for(y)}" width="100%" alt="{alt_kind} {y}">'
            f"</a>"
            f"<p><b>{label}</b></p>"
            f"</td>"
        )
    return (
        '<table align="center" width="100%"><tr>'
        + "".join(cells)
        + "</tr></table>"
    )


def skyline_grid() -> str:
    return _grid(
        href_for=lambda y: f"https://skyline.github.com/{GH_USER}/{y}",
        svg_for=lambda y: f"{RAW_BASE}/github-metrics-skyline-{y}.svg",
        alt_kind="GitHub Skyline",
    )


def city_grid() -> str:
    return _grid(
        href_for=lambda y: f"https://honzaap.github.io/GithubCity?name={GH_USER}&year={y}",
        svg_for=lambda y: f"{RAW_BASE}/github-metrics-city-{y}.svg",
        alt_kind="GitHub City",
    )


# --- INLINE LINK BARS (STL + GitCity) -----------------------------------------

STL_BASE = f"https://github.com/{GH_USER}/{GH_USER}/blob/metrics-output"


def _link_bar(prefix: str, href_for: Callable[[int], str], label_for: Callable[[int], str]) -> str:
    parts: list[str] = []
    for y in _years():
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


def main() -> int:
    with open(README_PATH, encoding="utf-8") as f:
        text = f.read()
    original = text

    sections: list[tuple[str, Callable[[], str]]] = [
        ("ACTIVITY", fetch_activity),
        ("LATEST_RELEASES", fetch_releases),
        ("PAGESPEED", fetch_pagespeed),
        ("HIGHLIGHTS_STATS", fetch_year_stats),
        ("SKYLINE_GRID", skyline_grid),
        ("STL_LINKS", stl_links),
        ("CITY_GRID", city_grid),
        ("GITCITY_LINKS", gitcity_links),
    ]

    for marker, fn in sections:
        try:
            body = fn()
            text = replace_block(text, marker, body)
            print(f"updated {marker}")
        except Exception as e:
            warn(f"{marker} update failed: {e}")

    if text == original:
        print("no changes")
        return 0
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    print("README updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
