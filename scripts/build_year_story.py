"""Generate assets/year-story.svg — every year of contributions with its story.

Each year gets its own grid, split automatically into stretches (quiet, steady,
busy) worked out from the monthly totals, with the longest streak outlined and
the biggest day circled, plus one caption per stretch written for visitors.
Built from the same assets/heatmap-*.svg files as the commit-name banner, so it
updates whenever they do. Pure SVG so it renders inside GitHub's <img> proxy.
"""
import datetime as dt
import re
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "year-story.svg"

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'JetBrains Mono',Menlo,Consolas,monospace"
BLUE, GREEN, RED, MUTED = "#58a6ff", "#42b883", "#F90001", "#8b949e"
LEVELS = ["#151b26", "#5a2a16", "#8f3b1b", "#cc4f22", "#ff6a2b"]
KIND = {  # label, colour, dashed
    "quiet": ("Quiet stretch", "#8b949e", True),
    "steady": ("Steady stretch", "#58a6ff", True),
    "busy": ("Busy stretch", "#ff652f", False),
}
W, X0, C = 1300, 52, 22


def load_days() -> dict[dt.date, int]:
    days: dict[dt.date, int] = {}
    for f in sorted((ROOT / "assets").glob("heatmap-*.svg")):
        for n, d in re.findall(r"<title>(\d+) on (\d{4}-\d{2}-\d{2})</title>", f.read_text(encoding="utf-8")):
            days[dt.date.fromisoformat(d)] = int(n)
    return days


def level(n: int) -> int:
    return 0 if n == 0 else 1 if n < 5 else 2 if n < 15 else 3 if n < 30 else 4


def mname(m: int) -> str:
    return dt.date(2000, m, 1).strftime("%b")


def phases(months: list[int], last_month: int) -> list[list]:
    """Split months 1..last_month into at most four stretches by how busy they were."""
    peak = max(months[:last_month] + [1])
    def kind(v):
        return "busy" if v >= .45 * peak else "quiet" if v < .12 * peak else "steady"
    runs: list[list] = []
    for m in range(1, last_month + 1):
        k = kind(months[m - 1])
        if runs and runs[-1][0] == k:
            runs[-1][2] = m
        else:
            runs.append([k, m, m])
    rank = {"quiet": 0, "steady": 1, "busy": 2}
    # fold one-month blips into a neighbour, then merge until four stretches remain
    def merge(i, j):
        a, b = runs[min(i, j)], runs[max(i, j)]
        keep = a[0] if (a[2] - a[1]) >= (b[2] - b[1]) else b[0]
        runs[min(i, j)] = [keep, a[1], b[2]]
        del runs[max(i, j)]
    changed = True
    while changed and len(runs) > 1:
        changed = False
        for i, r in enumerate(runs):
            if r[1] == r[2] and len(runs) > 1:
                j = i - 1 if i == len(runs) - 1 else i + 1 if i == 0 else (
                    i - 1 if abs(rank[runs[i - 1][0]] - rank[r[0]]) <= abs(rank[runs[i + 1][0]] - rank[r[0]]) else i + 1)
                merge(i, j)
                changed = True
                break
    while len(runs) > 4:
        i = min(range(len(runs) - 1), key=lambda i: abs(rank[runs[i][0]] - rank[runs[i + 1][0]]))
        merge(i, i + 1)
    # neighbours of the same kind after folding
    i = 0
    while i < len(runs) - 1:
        if runs[i][0] == runs[i + 1][0]:
            runs[i][2] = runs[i + 1][2]
            del runs[i + 1]
        else:
            i += 1
    return runs


def year_svg(year: int, days: dict[dt.date, int], today: dt.date, y0: float) -> tuple[list[str], float]:
    o: list[str] = []
    current = year == today.year
    last = today if current else dt.date(year, 12, 31)
    ds = [d for d in (dt.date(year, 1, 1) + dt.timedelta(i) for i in range((last - dt.date(year, 1, 1)).days + 1))]
    val = {d: days.get(d, 0) for d in ds}
    total = sum(val.values())
    months = [sum(v for d, v in val.items() if d.month == m) for m in range(1, 13)]
    start = dt.date(year, 1, 1) - dt.timedelta(days=(dt.date(year, 1, 1).weekday() + 1) % 7)

    def xy(d):
        i = (d - start).days
        return X0 + (i // 7) * C, y0 + 74 + (i % 7) * C

    o.append(f'<text x="0" y="{y0 + 30}" font-family="{SANS}" font-size="34" font-weight="800" fill="#ffffff">{year}'
             f'<tspan font-size="20" font-weight="700" fill="{BLUE}">  {total:,}</tspan>'
             f'<tspan font-size="18" font-weight="400" fill="{MUTED}"> contributions</tspan>'
             + (f'<tspan font-family="{MONO}" font-size="14" font-weight="700" letter-spacing="2.5" fill="{GREEN}">   · LIVE</tspan>' if current else "")
             + '</text>')
    for k, t in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        o.append(f'<text x="{X0 - 44}" y="{y0 + 74 + k * C + 15}" font-family="{SANS}" font-size="13" fill="{BLUE}">{t}</text>')
    for d in ds:
        x, y = xy(d)
        o.append(f'<rect x="{x}" y="{y}" width="{C - 4}" height="{C - 4}" rx="4" fill="{LEVELS[level(val[d])]}"/>')
        if d.day == 1:
            o.append(f'<text x="{x}" y="{y0 + 64}" font-family="{SANS}" font-size="13" fill="{BLUE}">{d:%b}</text>')

    runs = phases(months, last.month)
    caps = []
    for n, (kind, m0, m1) in enumerate(runs, 1):
        label, col, dashed = KIND[kind]
        a = dt.date(year, m0, 1)
        b = min(last, (dt.date(year + (m1 == 12), m1 % 12 + 1, 1) - dt.timedelta(days=1)))
        xa, _ = xy(a - dt.timedelta(days=(a.weekday() + 1) % 7))
        xb, _ = xy(b - dt.timedelta(days=(b.weekday() + 1) % 7))
        top = y0 + 74
        dash = ' stroke-dasharray="6 6"' if dashed else ""
        o.append(f'<rect x="{xa - 4}" y="{top - 4}" width="{xb - xa + C + 4}" height="{7 * C + 4}" rx="8" fill="{col}" fill-opacity=".05" '
                 f'stroke="{col}" stroke-width="2.2"{dash}/>')
        cx = (xa + xb + C) / 2
        o.append(f'<circle cx="{cx}" cy="{top + 7 * C + 20}" r="12" fill="{col}"/>'
                 f'<text x="{cx}" y="{top + 7 * C + 25}" text-anchor="middle" font-family="{SANS}" font-size="13" font-weight="800" fill="#0d1117">{n}</text>')
        span = [d for d in ds if a <= d <= b]
        sub = sum(val[d] for d in span)
        act = sum(1 for d in span if val[d])
        when = mname(m0) if m0 == m1 else f"{mname(m0)}–{mname(m1)}"
        still = current and b == last
        caps.append((n, col, f"{label}{' · still running' if still else ''}",
                     f"{when}: {sub:,} contributions, active {act} of {len(span)} days"))

    # longest streak (outlined) and biggest day (circled)
    run = best = 0
    rs = bs = be = None
    for d in ds:
        if val[d]:
            run += 1
            rs = d if run == 1 else rs
            if run > best:
                best, bs, be = run, rs, d
        else:
            run = 0
    if best >= 3:
        d = bs
        while d <= be:
            x, y = xy(d)
            o.append(f'<rect x="{x - 1.5}" y="{y - 1.5}" width="{C - 1}" height="{C - 1}" rx="5" fill="none" stroke="{GREEN}" stroke-width="2.2"/>')
            d += dt.timedelta(days=1)
    top_day = max(ds, key=lambda d: val[d])
    if val[top_day]:
        x, y = xy(top_day)
        o.append(f'<circle cx="{x + (C - 4) / 2}" cy="{y + (C - 4) / 2}" r="16" fill="none" stroke="#ffffff" stroke-width="2.4"/>')

    cy = y0 + 74 + 7 * C + 64
    for i, (n, col, title, line) in enumerate(caps):
        x = (i % 2) * 650
        y = cy + (i // 2) * 56
        o.append(f'<circle cx="{x + 12}" cy="{y}" r="12" fill="{col}"/>'
                 f'<text x="{x + 12}" y="{y + 5}" text-anchor="middle" font-family="{SANS}" font-size="13" font-weight="800" fill="#0d1117">{n}</text>'
                 f'<text x="{x + 34}" y="{y + 6}" font-family="{SANS}" font-size="18" font-weight="700" fill="#ffffff">{escape(title)}</text>'
                 f'<text x="{x + 34}" y="{y + 30}" font-family="{SANS}" font-size="15.5" fill="{MUTED}">{escape(line)}</text>')
    y = cy + ((len(caps) + 1) // 2) * 56 + 10
    if best >= 3:
        o.append(f'<rect x="0" y="{y - 13}" width="16" height="16" rx="4" fill="none" stroke="{GREEN}" stroke-width="2.2"/>'
                 f'<text x="26" y="{y}" font-family="{SANS}" font-size="15.5" fill="#c9d1d9">longest streak: {best} days '
                 f'({bs:%b} {bs.day} – {be:%b} {be.day})</text>')
    if val[top_day]:
        o.append(f'<circle cx="658" cy="{y - 5}" r="8" fill="none" stroke="#ffffff" stroke-width="2.2"/>'
                 f'<text x="676" y="{y}" font-family="{SANS}" font-size="15.5" fill="#c9d1d9">biggest day: '
                 f'{top_day:%b} {top_day.day} ({val[top_day]} contributions)</text>')
    return o, y + 34 - y0


def main() -> None:
    days = load_days()
    if not days:
        print("no heatmaps, skipping year story")
        return
    today = min(dt.date.today(), max(days))
    years = sorted({d.year for d in days if days[d] > 0} | {today.year}, reverse=True)
    body: list[str] = []
    y = 10
    for i, yr in enumerate(years):
        if i:
            body.append(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="#21262d" stroke-width="1.5"/>')
            y += 30
        part, h = year_svg(yr, days, today, y)
        body += part
        y += h
    totals = {yr: sum(v for d, v in days.items() if d.year == yr) for yr in years}
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {y:.0f}" width="{W}" height="{y:.0f}" role="img" '
            f'aria-label="Contributions per year with busy and quiet stretches: '
            + ", ".join(f"{yr}: {totals[yr]:,}" for yr in years) + '">')
    OUT.write_text(head + "".join(body) + "</svg>", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(years)} years)")


if __name__ == "__main__":
    main()
