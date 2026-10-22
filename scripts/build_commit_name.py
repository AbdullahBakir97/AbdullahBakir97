"""Generate assets/commit-name.svg — my name written in my own commit history.

A contribution-calendar grid (same 7-day column rhythm and green scale as
GitHub's graph) where the name is drawn in pixel letters. Every lit square is a
real day I committed, taken from assets/heatmap-*.svg in chronological order,
so reading the name left to right walks from my first commits to the latest.
The letters build one at a time, each square landing in brand red and cooling
to its real contribution level. FIRST DAY pins the oldest square, HEAD the newest.
The readme workflow re-runs this daily, so the newest square is always recent.

Pure SVG + CSS animation, so it renders inside GitHub's <img> proxy.
Re-run after the heatmaps refresh (the readme workflow already updates them).
"""
import datetime as dt
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
OUT = ASSETS / "commit-name.svg"

NAME_LINES = ["ABDULLAH", "BAKIR"]
HANDLE = "github.com/AbdullahBakir97"

W, H = 1400, 596
PITCH, CELL, RADIUS = 18, 14, 3
GRID_COLS, GRID_ROWS = 71, 19
GX = (W - GRID_COLS * PITCH) / 2 + 12          # room on the left for Mon / Wed / Fri
GY = 202

BG, SURFACE, EMPTY, BORDER = "#0d1117", "#161b22", "#161b22", "#30363d"
TEXT, MUTED = "#e6edf3", "#7d8590"
RED, GREEN, PURPLE = "#F90001", "#39d353", "#bc8cff"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
GHOST = ["#161b22", "#1a2029", "#1d242e", "#212833", "#252d38"]   # the unused days, quiet grey

LOOP = 16.0
START, STEP = 0.7, 0.42          # first letter at START s, then one letter every STEP s
LAND = 0.45                      # how long a square takes to pop in
HOLD = 14.8                      # everything fades from here to the loop end

FONT = {  # 5 x 7 pixel font
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".####", "#....", "#....", "#....", "#....", "#....", ".####"],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "#.#.#", ".#.#."],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
}


def read_days():
    """All (date, count, colour) from the heatmap SVGs, oldest first."""
    days = []
    for f in sorted(ASSETS.glob("heatmap-*.svg")):
        for fill, count, date in re.findall(
                r'fill="(#[0-9a-fA-F]{6})"><title>(\d+) on (\d{4}-\d{2}-\d{2})</title>', f.read_text()):
            days.append((date, int(count), fill.lower()))
    days.sort()
    return days


def level_colour(count, cuts):
    if count <= 0:
        return LEVELS[0]
    for i, c in enumerate(cuts):
        if count <= c:
            return LEVELS[i + 1]
    return LEVELS[4]


YEAR_COLOURS = {2023: ("#bc8cff", "#6e4fa6"), 2024: ("#F90001", "#8f1414"),
                2025: ("#ff652f", "#99401f"), 2026: ("#e3b341", "#8a6d29")}
FALLBACK = ("#39d353", "#26a641")


def year_colour(date, bright=True):
    pair = YEAR_COLOURS.get(int(date[:4]), FALLBACK)
    return pair[0] if bright else pair[1]


def longest_streak(active):
    """(start, end, length) of the longest run of consecutive active days."""
    best = (None, None, 0)
    prev, run, run_start = None, 0, None
    for d, _, _ in active:
        day = dt.date.fromisoformat(d)
        if prev and (day - prev).days == 1:
            run += 1
        else:
            run, run_start = 1, day
        if run > best[2]:
            best = (run_start, day, run)
        prev = day
    return best


def choose_days(active, n, keep):
    """n days spread evenly over all active days, always including the dates in keep."""
    if len(active) <= n:
        return [active[i % len(active)] for i in range(n)]
    must = [d for d in active if d[0] in keep][:n]
    rest = [d for d in active if d[0] not in keep]
    k = n - len(must)
    picked = [rest[round(i * (len(rest) - 1) / max(1, k - 1))] for i in range(k)] if k > 0 else []
    return sorted(must + picked)


def letter_cells():
    """[(letter_index, col, row)] in drawing order: letter by letter, column by column."""
    cells, k = [], 0
    top = 2
    for li, line in enumerate(NAME_LINES):
        width = len(line) * 6 - 1
        x0 = (GRID_COLS - width) // 2
        y0 = top + li * 9
        for ci, ch in enumerate(line):
            glyph = FONT.get(ch.upper())
            if not glyph:
                continue
            for gx in range(5):
                for gy in range(7):
                    if glyph[gy][gx] == "#":
                        cells.append((k, x0 + ci * 6 + gx, y0 + gy))
            k += 1
    return cells, k


def pct(t):
    return f"{max(0.0, min(100.0, t / LOOP * 100)):.2f}%"


def stats(days):
    """Totals for the header stat tiles."""
    today = dt.date.today()
    year = today.year
    by_date = {d: c for d, c, _ in days}
    total = sum(by_date.values())
    year_days = sum(1 for d, c in by_date.items() if d.startswith(str(year)) and c > 0)
    year_elapsed = (today - dt.date(year, 1, 1)).days + 1
    longest = run = 0                                  # longest run of consecutive commit days
    prev = None
    for d in sorted(k for k, c in by_date.items() if c > 0):
        day = dt.date.fromisoformat(d)
        run = run + 1 if prev and (day - prev).days == 1 else 1
        longest, prev = max(longest, run), day
    return {"total": total, "year": year, "year_days": year_days, "year_elapsed": year_elapsed, "longest": longest}


def render():
    days = read_days()
    active = [d for d in days if d[1] > 0] or [("", 1, LEVELS[3])]
    counts = sorted(d[1] for d in active)
    cuts = [counts[int(len(counts) * q)] for q in (.25, .5, .75)]
    total = sum(d[1] for d in days)
    first, last = (active[0][0], active[-1][0]) if active[0][0] else ("", "")

    cells, n_letters = letter_cells()
    lit = {(c, r) for _, c, r in cells}
    # spread the real active days over the lit squares, oldest first
    n = len(cells)
    s_from, s_to, s_len = longest_streak(active)
    top = max(active, key=lambda d: d[1])
    streak_dates = set()
    if s_from:
        d = s_from
        while d <= s_to:
            streak_dates.add(d.isoformat())
            d += dt.timedelta(days=1)
    picks = choose_days(active, n, streak_dates | {top[0]})

    css = [
        f"text{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,sans-serif}}",
        ".mono{font-family:ui-monospace,SFMono-Regular,'JetBrains Mono',Menlo,Consolas,monospace}",
        ".sq{transform-box:fill-box;transform-origin:center}",
        f".head{{opacity:0;animation:head {LOOP}s linear infinite}}",
        f"@keyframes head{{0%,{pct(START + n_letters * STEP + .2)}{{opacity:0;transform:translateY(6px)}}"
        f"{pct(START + n_letters * STEP + .6)},{pct(HOLD)}{{opacity:1;transform:none}}{pct(HOLD + .6)},100%{{opacity:0}}}}",
        ".pulse{transform-box:fill-box;transform-origin:center;animation:pulse 1.6s ease-out infinite}",
        "@keyframes pulse{0%{transform:scale(1);opacity:.9}100%{transform:scale(2.6);opacity:0}}",
        f".cap{{opacity:0;animation:cap {LOOP}s linear infinite}}",
        f".first{{opacity:0;animation:first {LOOP}s linear infinite}}",
        f"@keyframes first{{0%,{pct(START + .2)}{{opacity:0;transform:translateX(-6px)}}"
        f"{pct(START + .7)},{pct(HOLD)}{{opacity:1;transform:none}}{pct(HOLD + .6)},100%{{opacity:0}}}}",
        f"@keyframes cap{{0%,{pct(START + n_letters * STEP + .5)}{{opacity:0}}{pct(START + n_letters * STEP + 1.1)},{pct(HOLD)}{{opacity:1}}{pct(HOLD + .6)},100%{{opacity:0}}}}",
    ]
    for k in range(n_letters):
        s = START + k * STEP
        css.append(
            f"@keyframes L{k}{{0%,{pct(s)}{{opacity:0;transform:scale(.2);fill:{RED}}}"
            f"{pct(s + LAND * .6)}{{opacity:1;transform:scale(1.3);fill:{RED}}}"
            f"{pct(s + LAND)}{{transform:scale(1);fill:{RED}}}"
            f"{pct(s + LAND + .9)},{pct(HOLD)}{{opacity:1;transform:scale(1);fill:var(--c)}}"
            f"{pct(HOLD + .6)},100%{{opacity:0;transform:scale(1);fill:var(--c)}}}}")
    css.append("@media (prefers-reduced-motion:reduce){.sq,.head,.cap,.pulse{animation:none!important;opacity:1!important}"
               ".sq{fill:var(--c)!important}}")

    p = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
             f'aria-label="Abdullah Bakir, written in real commit history">')
    p.append("<title>Abdullah Bakir, written in commits</title>")
    p.append(f"<style>{''.join(css)}</style>")
    p.append('<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{SURFACE}"/><stop offset="1" stop-color="{BG}"/></linearGradient>'
             '<radialGradient id="glow" cx="50%" cy="45%" r="55%"><stop offset="0" stop-color="#39d353" stop-opacity=".07"/>'
             '<stop offset="1" stop-color="#39d353" stop-opacity="0"/></radialGradient>'
             '<filter id="lit" x="-5%" y="-10%" width="110%" height="120%"><feGaussianBlur stdDeviation="3.5" result="b"/>'
             '<feColorMatrix in="b" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 .55 0" result="g"/>'
             '<feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>')
    p.append(f'<rect width="{W}" height="{H}" rx="14" fill="url(#bg)" stroke="{BORDER}"/>')
    p.append(f'<rect width="{W}" height="{H}" rx="14" fill="url(#glow)"/>')

    # header: story on the left, three live stat tiles on the right (same style as about-hero)
    st = stats(days)
    p.append(f'<text class="mono" x="{GX}" y="44" font-size="13" font-weight="700" letter-spacing="3.2" fill="{GREEN}">'
             f'// WRITTEN IN COMMITS · {first[:4]} — {last[:4]}</text>')
    p.append(f'<text class="mono" x="{W - GX + 12}" y="44" font-size="12" letter-spacing="1.5" fill="{MUTED}" text-anchor="end">'
             f'<tspan fill="{GREEN}">●</tspan> REAL DATA · UPDATED {dt.date.today().isoformat()}</text>')
    p.append(f'<text x="{GX}" y="90" font-size="32" font-weight="800" letter-spacing="-.5" fill="{TEXT}">'
             f'Written in my commits<tspan fill="{GREEN}" font-size="16" dy="-6"> ●</tspan></text>')
    p.append(f'<text x="{GX}" y="118" font-size="14.5" font-style="italic" fill="{MUTED}">'
             f'Every bright square is a real day I pushed code to GitHub.</text>')
    p.append(f'<text x="{GX}" y="138" font-size="14.5" font-style="italic" fill="{MUTED}">'
             f'Read the name left to right: oldest day first. Each year has its own colour.</text>')
    act_days = len([d for d in days if d[1] > 0])
    per_year = {}
    for d, c, _ in days:
        per_year[d[:4]] = per_year.get(d[:4], 0) + c
    best_year = max(per_year, key=per_year.get)
    tiles = [("CONTRIBUTIONS", f"{st['total']:,}", f"since {first[:4]}"),
             ("ACTIVE DAYS", f"{act_days}", f"in {len(per_year)} years"),
             ("LONGEST STREAK", f"{s_len}", "days in a row"),
             ("BEST YEAR", best_year, f"{per_year[best_year]:,}")]
    tw, th, gap = 162, 74, 10
    x0 = W - GX + 12 - (4 * tw + 3 * gap)
    for i, (label, value, sub) in enumerate(tiles):
        x = x0 + i * (tw + gap)
        p.append(f'<g><rect x="{x}" y="66" width="{tw}" height="{th}" rx="8" fill="{SURFACE}" stroke="{BORDER}"/>'
                 f'<rect x="{x}" y="66" width="3" height="{th}" rx="1.5" fill="{RED}"/>'
                 f'<text class="mono" x="{x + 16}" y="88" font-size="10" font-weight="700" letter-spacing="2" fill="{MUTED}">{label}</text>'
                 f'<text x="{x + 16}" y="120" font-size="26" font-weight="800" fill="{TEXT}">{value}</text>'
                 f'<text x="{x + tw - 12}" y="120" font-size="11" fill="{MUTED}" text-anchor="end">{sub}</text></g>')

    # the calendar: every empty square, with the rest of the real year ghosted in
    # every other square is a real day too: the whole timeline, oldest to newest, column by column,
    # tinted with its year's colour so the four years read as four zones behind the name
    free = [(c, r) for c in range(GRID_COLS) for r in range(GRID_ROWS) if (c, r) not in lit]
    empty = []
    for i, (c, r) in enumerate(free):
        g = days[round(i * (len(days) - 1) / max(1, len(free) - 1))] if days else None
        x, y = GX + c * PITCH, GY + r * PITCH
        if g and g[1] > 0:
            op = (.07, .1, .13, .17)[LEVELS.index(level_colour(g[1], cuts)) - 1]
            empty.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{year_colour(g[0])}" '
                         f'opacity="{op}"><title>{g[1]} contributions on {g[0]}</title></rect>')
        else:
            empty.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{EMPTY}"/>')
    p.append(f'<g>{"".join(empty)}</g>')

    # the name: real active days, oldest to newest, landing letter by letter
    lit_rects = []
    under = []
    for i, ((k, c, r), day) in enumerate(zip(cells, picks)):
        x, y = GX + c * PITCH, GY + r * PITCH
        colour = year_colour(day[0], day[1] > cuts[0])   # each year has its own colour, busier days brighter
        in_letter = sum(1 for kk, _, _ in cells[:i] if kk == k)
        delay = in_letter * .012
        under.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{EMPTY}"/>')
        lit_rects.append(
            f'<rect class="sq" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" '
            f'style="--c:{colour};animation:L{k} {LOOP}s linear {delay:.3f}s infinite both" fill="{colour}">'
            f'<title>{day[1]} contributions on {day[0]}</title></rect>')
    p.append(f'<g>{"".join(under)}</g><g filter="url(#lit)">{"".join(lit_rects)}</g>')

    # analysis drawn on the name itself: the longest streak and the biggest day
    def callout(ax, ay, line1, line2, colour, row):
        gap_y = GY + (9.5 if row >= 9 else -1.6) * PITCH       # between the two lines, or above the grid
        w = (len(line1) + len(line2) + 3) * 7.25 + 30
        bx = min(max(ax - w / 2, GX), W - GX + 12 - w)
        return (f'<g class="cap"><path d="M{ax} {ay}V{gap_y + 13}" stroke="{colour}" stroke-width="1.4" stroke-dasharray="3 3"/>'
                f'<rect x="{bx}" y="{gap_y - 13}" width="{w}" height="26" rx="13" fill="{BG}" stroke="{colour}"/>'
                f'<text class="mono" x="{bx + w / 2}" y="{gap_y + 4.5}" font-size="12" font-weight="700" fill="{colour}" '
                f'text-anchor="middle">{line1} <tspan fill="{MUTED}" font-weight="400">· {line2}</tspan></text></g>')

    pos = {day[0]: (c, r) for (k, c, r), day in zip(cells, picks)}
    streak_cells = [pos[d] for d in sorted(streak_dates) if d in pos]
    if streak_cells:
        outl = "".join(f'<rect x="{GX + c * PITCH - 2}" y="{GY + r * PITCH - 2}" width="{CELL + 4}" height="{CELL + 4}" '
                       f'rx="{RADIUS + 1}" fill="none" stroke="#000000" stroke-width="2.2"/>' for c, r in streak_cells)
        p.append(f'<g class="cap">{outl}</g>')
        c0, r0 = min(streak_cells, key=lambda cr: (cr[1], cr[0]))
        p.append(callout(GX + c0 * PITCH + CELL / 2, GY + r0 * PITCH - 2, f"LONGEST STREAK {s_len} DAYS",
                         f"{s_from:%b %d} – {s_to:%b %d %Y}", RED, r0))
    if top[0] in pos:
        c, r = pos[top[0]]
        bx, by = GX + c * PITCH + CELL / 2, GY + r * PITCH + CELL / 2
        tday = dt.date.fromisoformat(top[0])
        p.append(f'<g class="cap"><circle cx="{bx}" cy="{by}" r="12" fill="none" stroke="{year_colour(top[0])}" stroke-width="2"/>'
                 f'<circle class="pulse" cx="{bx}" cy="{by}" r="12" fill="none" stroke="{year_colour(top[0])}" stroke-width="1.5"/></g>')
        p.append(callout(bx, by - 13, f"BIGGEST DAY {top[1]}", f"{tday:%b %d %Y}", year_colour(top[0]), r))

    # the first square gets a pin: this is where the story starts
    k, c, r = cells[0]
    sx, sy = GX + c * PITCH, GY + r * PITCH + CELL / 2
    p.append(f'<g class="first"><rect x="{sx - 196}" y="{sy - 13}" width="182" height="26" rx="13" fill="{BG}" stroke="{GREEN}"/>'
             f'<text class="mono" x="{sx - 105}" y="{sy + 4.5}" font-size="12.5" font-weight="700" fill="{GREEN}" text-anchor="middle">'
             f'FIRST DAY <tspan fill="{MUTED}" font-weight="400">· {first}</tspan></text>'
             f'<path d="M{sx - 14} {sy}h10" stroke="{GREEN}" stroke-width="1.5"/></g>')

    # HEAD lands on the last square
    k, c, r = cells[-1]
    hx, hy = GX + c * PITCH + CELL / 2, GY + r * PITCH + CELL / 2
    p.append(f'<g class="head"><circle class="pulse" cx="{hx}" cy="{hy}" r="9" fill="none" stroke="{PURPLE}" stroke-width="2"/>'
             f'<rect x="{hx + 18}" y="{hy - 13}" width="214" height="26" rx="13" fill="{BG}" stroke="{PURPLE}"/>'
             f'<text class="mono" x="{hx + 125}" y="{hy + 4.5}" font-size="12.5" font-weight="700" fill="{PURPLE}" text-anchor="middle">'
             f'HEAD → main <tspan fill="{MUTED}" font-weight="400">· {last}</tspan></text></g>')

    # footer: legend left, the honest caption right
    fy = GY + GRID_ROWS * PITCH + 30
    lx = GX
    for y in sorted(per_year):
        col = YEAR_COLOURS.get(int(y), FALLBACK)[0]
        label = f"{y} · {per_year[y]:,}"
        p.append(f'<rect x="{lx}" y="{fy - 11}" width="{CELL - 1}" height="{CELL - 1}" rx="{RADIUS}" fill="{col}"/>'
                 f'<text x="{lx + 20}" y="{fy}" font-size="12.5" fill="{TEXT}">{y} <tspan fill="{MUTED}">· {per_year[y]:,}</tspan></text>')
        lx += 20 + len(label) * 7.2 + 18
    p.append(f'<text class="cap" x="{W - GX + 12}" y="{fy}" font-size="13" fill="{MUTED}" text-anchor="end">'
             f'<tspan fill="{TEXT}" font-weight="600">{len(cells)}</tspan> of my real commit days, oldest to newest, from '
             f'<tspan fill="{TEXT}">{first}</tspan> to <tspan fill="{TEXT}">{last}</tspan> · {HANDLE}</text>')
    p.append("</svg>")
    return "".join(p)


if __name__ == "__main__":
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")

