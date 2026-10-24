"""Generate assets/commit-name.svg — my name written in my own commit history.

Original concept and design: Abdullah Bakir (@AbdullahBakir97), 2026.

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

W, H = 1400, 640
PITCH, CELL, RADIUS = 13.4, 10.6, 2.4
GRID_COLS, GRID_ROWS = 97, 28
LINE_TOP = 10          # the name starts under the octopus' head
GX = (W - GRID_COLS * PITCH) / 2
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


YEAR_COLOURS = {2023: ("#22d3ee", "#127a8a"), 2024: ("#F90001", "#8f1414"),
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
    top = LINE_TOP
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


NAME_EATEN = []       # filled by drawings_and_worm: [(food item, (t_eat, total))]
WORM_DT = 0.015       # seconds per square the worm moves
FIG_C = 22            # square size in the drawings section


def cell_rect(f, T):
    """One square: it is typed/drawn in at its build time, eaten when the worm reaches it,
    and reset at the end of the loop."""
    x, y, size, colour, title, group, _, _, _, build, eat = f
    full = ART_OPACITY if group == "art" else 1
    kt = [0, build / T, (build + .3) / T, eat / T, (eat + .06) / T, (T - .5) / T, 1]
    anim = (f'<animate attributeName="opacity" values="0;0;{full};{full};.06;.06;0" '
            f'keyTimes="{";".join(f"{k:.5f}" for k in kt)}" dur="{T:.2f}s" repeatCount="indefinite"/>')
    tip = f"<title>{title}</title>" if title else ""
    return f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{RADIUS}" fill="{colour}" opacity="0">{anim}{tip}</rect>'


# where each drawing sits on the grid, in the space the name leaves free (col, row of its top-left)
SLOTS = {"Dog": (1, 10), "Ghost": (18, 10), "Orange robot": (75, 10), "Lighthouse": (89, 10),
         "Robots": (2, 20), "Skull": (22, 20), "Dog diving": (67, 20), "Diamond axe": (81, 20),
         "Me at my desk": (8, 1)}
ART_OPACITY = .62     # the drawings sit a step behind the name
# when each drawing happened in the graph, so the worm meets them in time order
FIG_DATES = {"Diamond axe": "2023-09-01", "Skull": "2023-09-20", "Lighthouse": "2023-11-05", "Ghost": "2023-11-20",
             "Dog": "2024-02-01", "Robots": "2024-08-15", "Dog diving": "2026-04-10", "Orange robot": "2026-07-10",
             "Me at my desk": "2026-09-20"}
LETTER_STEP, FIG_STEP, SLEEP = .26, .55, 3.0


def drawings():
    """{name: [(dc, row, colour)]} from assets/art-figures.json, each cropped to its own squares."""
    import json
    path = ASSETS / "art-figures.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    figs = [c for c in data["cells"] if c[3] == "fig"]
    out = {}
    for b in range(data["bands"]):
        labels = sorted((cx, name) for bb, cx, name in data["labels"] if bb == b)
        cols = sorted({c[1] for c in figs if c[0] == b})
        groups = [[cols[0]]]
        for x in cols[1:]:
            (groups[-1].append(x) if x - groups[-1][-1] <= 1 else groups.append([x]))
        for g in groups:
            centre = (g[0] + g[-1]) / 2
            name = min(labels, key=lambda lab: abs(lab[0] - centre))[1]
            out.setdefault(name, []).extend(c for c in figs if c[0] == b and g[0] <= c[1] <= g[-1])
    shapes = {}
    for name, cells in out.items():
        c0 = min(c[1] for c in cells)
        shapes[name] = [(c[1] - c0, c[2], c[4]) for c in cells]
    return shapes


OCTO = ["#2c2050", "#382968", "#463383", "#563fa0", "#6b4fc2"]   # purple scale for the octopus days


OCTO_EYES = {}


def octopus_mask(phase=0.0):
    """Squares of a big octopus drawn on the grid: a dome with two eyes and eight curling arms.
    `phase` sways the arms, so two phases make the arms wave."""
    import math
    cx, cells = GRID_COLS / 2, set()
    for c in range(GRID_COLS):
        for r in range(GRID_ROWS):
            if ((c + .5 - cx) / 15) ** 2 + ((r + .5 - 5.4) / 5.6) ** 2 <= 1 and r <= 8:
                cells.add((c, r))
    for ex in (-7, 5):                                   # two eyes: white with a dark pupil
        for dc in (0, 1, 2):
            for dr in (0, 1):
                cells.discard((int(cx) + ex + dc, 3 + dr))
                OCTO_EYES[(int(cx) + ex + dc, 3 + dr)] = "#14102a" if (dc, dr) == (1, 1) else "#e8dcff"
    bases = [-12, -8.5, -5, -1.5, 1.5, 5, 8.5, 12]
    for i, bx in enumerate(bases):
        side = -1 if bx < 0 else 1
        outer = abs(i - 3.5) / 3.5                       # 0 for the middle arms, 1 for the outer ones
        x, y = cx + bx, 8.0
        ang = math.radians(90 - side * (8 + 46 * outer))
        length = 26 + 30 * outer
        curl = side * math.radians(120) * (.45 + .4 * outer)
        n = int(length * 3)
        for j in range(n):
            t = j / n
            a = ang - curl * t ** 2.2 + math.sin(phase + i * .9 + t * 4) * .22 * t
            x += math.cos(a) / 3
            y += math.sin(a) / 3
            w = 1.6 * (1 - t) + .45
            for dc in range(-2, 3):
                for dr in range(-2, 3):
                    if dc * dc + dr * dr <= w * w:
                        cc, rr = int(x + dc), int(y + dr)
                        if 0 <= cc < GRID_COLS and 0 <= rr < GRID_ROWS:
                            cells.add((cc, rr))
    return cells


def worm(food):
    """Type the name, draw the drawings, let the worm sleep, then eat everything in time order."""
    # 1. build times: the name letter by letter, then each drawing in date order
    t = START
    name = [f for f in food if f[5] == "name"]
    letter = None
    for f in name:
        if f[8][1] != letter:
            letter, j = f[8][1], 0
            t = START + letter * LETTER_STEP
        f[9] = t + j * .012
        j += 1
    end = max(f[9] for f in name) + .4 if name else START
    arts = sorted({f[8][1] for f in food if f[5] == "art"}, key=lambda n: FIG_DATES.get(n, "9999"))
    for fi, n in enumerate(arts):
        cells = sorted((f for f in food if f[5] == "art" and f[8][1] == n), key=lambda f: (f[6], f[7]))
        c0 = cells[0][6]
        for f in cells:
            f[9] = end + fi * FIG_STEP + (f[6] - c0) * .03
    build_end = max(f[9] for f in food) + .8

    # 2. the route: every square in date order (drawings at their date, column by column)
    def key(f):
        if f[5] == "name":
            return (f[8][0], 0, 0, 0)
        return (FIG_DATES.get(f[8][1], "9999"), 1, f[6], f[7] if f[6] % 2 == 0 else -f[7])
    route = sorted(food, key=key)
    pts, idx = [], {}
    step = PITCH * .9
    for f in route:
        cx, cy = f[0] + f[2] / 2, f[1] + f[2] / 2
        if pts:
            px, py = pts[-1]
            for tx, ty in ((cx, py), (cx, cy)):
                n = max(1, int((abs(tx - px) + abs(ty - py)) / step))
                pts += [(px + (tx - px) * j / n, py + (ty - py) * j / n) for j in range(1, n + 1)]
                px, py = tx, ty
        else:
            pts.append((cx, cy))
        idx[id(f)] = len(pts) - 1
    cum = [0.0]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        cum.append(cum[-1] + ((bx - ax) ** 2 + (by - ay) ** 2) ** .5)
    move = build_end + SLEEP
    travel = len(pts) * WORM_DT
    T = move + travel + 2.4
    for f in route:
        f[10] = move + cum[idx[id(f)]] / (cum[-1] or 1) * travel

    # drop only the points in the middle of a straight run in the same direction; keep every
    # corner and every turn-back, so the drawn path is exactly as long as the timing assumes
    keep = [pts[0]]
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        u, v = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
        straight = abs(u[0] * v[1] - u[1] * v[0]) < 1e-6 and u[0] * v[0] + u[1] * v[1] > 0
        if not straight:
            keep.append(b)
    keep.append(pts[-1])
    d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in keep)

    out = ['<defs><radialGradient id="wh" cx=".35" cy=".35" r=".8"><stop offset="0" stop-color="#ff8a7a"/>'
           '<stop offset=".45" stop-color="#ff2a1a"/><stop offset="1" stop-color="#b3000a"/></radialGradient>'
           '<filter id="wg" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="3"/></filter>'
           f'<path id="route" d="{d}"/></defs>']
    sx, sy = pts[0]
    show = (f'<animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;{(build_end - .4) / T:.5f};{build_end / T:.5f};'
            f'{(T - .6) / T:.5f};1" dur="{T:.2f}s" repeatCount="indefinite"/>')
    # asleep: a slow breathing glow and a few z's before it wakes up
    out.append(f'<g opacity="0"><animate attributeName="opacity" values="0;0;1;1;0;0" keyTimes="0;{(build_end - .2) / T:.5f};'
               f'{build_end / T:.5f};{(move - .3) / T:.5f};{move / T:.5f};1" dur="{T:.2f}s" repeatCount="indefinite"/>'
               f'<circle cx="{sx}" cy="{sy}" r="11" fill="{RED}" opacity=".35" filter="url(#wg)">'
               f'<animate attributeName="r" values="9;14;9" dur="1.6s" repeatCount="indefinite"/></circle>')
    for i, (dx, dy, fs) in enumerate(((-16, -6, 11), (-27, -14, 13), (-40, -24, 16))):
        out.append(f'<text class="mono" x="{sx + dx}" y="{sy + dy}" font-size="{fs}" font-weight="700" fill="{MUTED}" opacity="0">z'
                   f'<animate attributeName="opacity" values="0;.9;0" dur="1.8s" begin="{i * .45:.2f}s" repeatCount="indefinite"/></text>')
    out.append("</g>")
    out.append(f'<g opacity="0">{show}')
    segs = 10
    for i in range(segs, -1, -1):
        size = CELL * 1.25 * (1.1 if i == 0 else 0.95 - i * 0.045)
        shade = "url(#wh)" if i == 0 else f"#{int(0xF9 - (0xF9 - 0x5c) * i / segs):02x}0{int(1 + 6 * i / segs):x}0{int(1 + 6 * i / segs):x}"
        lag = i * WORM_DT * 1.6
        motion = (f'<animateMotion calcMode="linear" keyPoints="0;0;1;1" keyTimes="0;{(move + lag) / T:.5f};'
                  f'{min((move + travel + lag) / T, .995):.5f};1" dur="{T:.2f}s" repeatCount="indefinite"><mpath href="#route"/></animateMotion>')
        if i == 0:
            out.append(f'<rect x="{-size / 2 - 3:.1f}" y="{-size / 2 - 3:.1f}" width="{size + 6:.1f}" height="{size + 6:.1f}" '
                       f'rx="{size / 2:.1f}" fill="{RED}" opacity=".55" filter="url(#wg)">{motion}</rect>')
        out.append(f'<rect x="{-size / 2:.1f}" y="{-size / 2:.1f}" width="{size:.1f}" height="{size:.1f}" rx="{size / 2.6:.1f}" '
                   f'fill="{shade}">{motion}</rect>')
    out.append("</g>")
    fade = (f".head,.cap,.first{{opacity:0;animation:fade {T:.2f}s linear infinite}}"
            f"@keyframes fade{{0%,{build_end / T * 100:.2f}%{{opacity:0}}{(build_end + .6) / T * 100:.2f}%,"
            f"{(T - .8) / T * 100:.2f}%{{opacity:1}}{(T - .3) / T * 100:.2f}%,100%{{opacity:0}}}}")
    return T, fade, "".join(out)


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
    css.append("%%FADE%%")
    css.append("@media (prefers-reduced-motion:reduce){.pulse{animation:none!important}}")

    p = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} %%H%%" width="{W}" height="%%H%%" role="img" '
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
    p.append(f'<rect width="{W}" height="%%H%%" rx="14" fill="url(#bg)" stroke="{BORDER}"/>')
    p.append(f'<rect width="{W}" height="%%H%%" rx="14" fill="url(#glow)"/>')

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
    tw, th, gap = 168, 74, 8
    x0 = W - GX + 12 - (4 * tw + 3 * gap)
    for i, (label, value, sub) in enumerate(tiles):
        x = x0 + i * (tw + gap)
        p.append(f'<g><rect x="{x}" y="66" width="{tw}" height="{th}" rx="8" fill="{SURFACE}" stroke="{BORDER}"/>'
                 f'<rect x="{x}" y="66" width="3" height="{th}" rx="1.5" fill="{RED}"/>'
                 f'<text class="mono" x="{x + 16}" y="88" font-size="10" font-weight="700" letter-spacing="2" fill="{MUTED}">{label}</text>'
                 f'<text x="{x + 16}" y="120" font-size="26" font-weight="800" fill="{TEXT}">{value}</text>'
                 f'<text x="{x + tw - 12}" y="120" font-size="11" fill="{MUTED}" text-anchor="end">{sub}</text></g>')

    # the calendar: every empty square, with the rest of the real year ghosted in
    # every other square is a real day too: the whole timeline, oldest to newest, column by column
    shapes = drawings()
    art = {}
    for name, cells_ in shapes.items():
        c0, r0 = SLOTS.get(name, (None, None))
        if c0 is None:
            continue
        for dc, r, colour in cells_:
            if 0 <= c0 + dc < GRID_COLS and 0 <= r0 + r < GRID_ROWS and (c0 + dc, r0 + r) not in lit:
                art[(c0 + dc, r0 + r)] = (colour, name)
    free = [(c, r) for c in range(GRID_COLS) for r in range(GRID_ROWS) if (c, r) not in lit and (c, r) not in art]
    frames = []          # a quiet frame and a name for every drawing
    for name in shapes:
        pts_ = [(c, r) for (c, r), (_, n) in art.items() if n == name]
        if not pts_:
            continue
        c0, c1 = min(c for c, _ in pts_), max(c for c, _ in pts_)
        r0, r1 = min(r for _, r in pts_), max(r for _, r in pts_)
        fx, fy_ = GX + c0 * PITCH - 4, GY + r0 * PITCH - 4
        fw, fh = (c1 - c0 + 1) * PITCH + 4.6, (r1 - r0 + 1) * PITCH + 4.6
        frames.append(f'<rect x="{fx}" y="{fy_}" width="{fw}" height="{fh}" rx="6" fill="{BG}" fill-opacity=".55" '
                      f'stroke="#ffffff" stroke-opacity=".12" stroke-dasharray="3 3"/>'
                      f'<text x="{fx + fw / 2}" y="{fy_ + fh + 13}" text-anchor="middle" font-size="10.5" '
                      f'letter-spacing=".4" fill="{MUTED}">{name}</text>')
    # behind everything: an octopus drawn from the same real days, its arms waving between two poses
    oct_a, oct_b = octopus_mask(0.0), octopus_mask(2.4)
    empty = []
    for i, (c, r) in enumerate(free):
        g = days[round(i * (len(days) - 1) / max(1, len(free) - 1))] if days else None
        x, y = GX + c * PITCH, GY + r * PITCH
        lv = LEVELS.index(level_colour(g[1], cuts)) if g and g[1] > 0 else 0
        tip = f"<title>{g[1]} contributions on {g[0]}</title>" if g else ""
        in_a, in_b = (c, r) in oct_a, (c, r) in oct_b
        if (c, r) in OCTO_EYES:
            empty.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{OCTO_EYES[(c, r)]}" opacity=".9">'
                         f'<animate attributeName="height" values="{CELL};{CELL};1;{CELL};{CELL}" keyTimes="0;.9;.93;.96;1" '
                         f'dur="6s" repeatCount="indefinite"/></rect>')
        elif in_a or in_b:
            col = OCTO[lv]
            wave = ""
            if in_a != in_b:                              # an arm square that comes and goes
                v = "1;1;0;0;1" if in_a else "0;0;1;1;0"
                wave = f'<animate attributeName="opacity" values="{v}" keyTimes="0;.4;.5;.9;1" dur="3.6s" repeatCount="indefinite"/>'
            empty.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{col}"'
                         f'{" opacity=\"0\"" if in_b and not in_a else ""}>{wave}{tip}</rect>')
        elif lv:
            empty.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{GHOST[lv]}">{tip}</rect>')
        else:
            empty.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{EMPTY}"/>')
    p.append(f'<g>{"".join(empty)}</g><g>{"".join(frames)}</g>')

    # the name: real active days, oldest to newest, landing letter by letter
    under = []
    food = []       # everything the worm eats: (x, y, size, colour, title, group)
    for (k, c, r), day in zip(cells, picks):
        x, y = GX + c * PITCH, GY + r * PITCH
        colour = year_colour(day[0], day[1] > cuts[0])   # each year has its own colour, busier days brighter
        under.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{EMPTY}"/>')
        food.append([x, y, CELL, colour, f"{day[1]} contributions on {day[0]}", "name", c, r, (day[0], k), 0.0, 0.0])
    for (c, r), (colour, name) in art.items():
        x, y = GX + c * PITCH, GY + r * PITCH
        under.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{EMPTY}"/>')
        food.append([x, y, CELL, colour, f"{name}, drawn on real commit days", "art", c, r, (FIG_DATES.get(name, "9999"), name), 0.0, 0.0])
    p.append(f'<g>{"".join(under)}</g><g filter="url(#lit)">%%NAME%%</g>')

    # analysis drawn on the name itself: the longest streak and the biggest day
    def callout(ax, ay, line1, line2, colour, row):
        gap_y = GY + (LINE_TOP + 7.5 if row >= LINE_TOP + 8 else LINE_TOP - 1.4) * PITCH   # between the lines, or above the name
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
    sx = GX + c * PITCH + CELL / 2
    gy_ = GY + (LINE_TOP + 7.5) * PITCH
    p.append(f'<g class="first"><path d="M{sx} {GY + (LINE_TOP + 6) * PITCH + CELL}V{gy_ - 12}" stroke="{GREEN}" stroke-width="1.4" stroke-dasharray="3 3"/>'
             f'<rect x="{sx - 20}" y="{gy_ - 12}" width="182" height="24" rx="12" fill="{BG}" stroke="{GREEN}"/>'
             f'<text class="mono" x="{sx + 71}" y="{gy_ + 4.5}" font-size="12" font-weight="700" fill="{GREEN}" text-anchor="middle">'
             f'FIRST DAY <tspan fill="{MUTED}" font-weight="400">· {first}</tspan></text></g>')

    # HEAD lands on the last square
    k, c, r = cells[-1]
    hx, hy = GX + c * PITCH + CELL / 2, GY + r * PITCH + CELL / 2
    by_ = GY + GRID_ROWS * PITCH + 14
    p.append(f'<g class="head"><circle class="pulse" cx="{hx}" cy="{hy}" r="9" fill="none" stroke="{PURPLE}" stroke-width="2"/>'
             f'<path d="M{hx} {hy + 8}V{by_ - 12}" stroke="{PURPLE}" stroke-width="1.4" stroke-dasharray="3 3"/>'
             f'<rect x="{hx - 107}" y="{by_ - 12}" width="214" height="24" rx="12" fill="{BG}" stroke="{PURPLE}"/>'
             f'<text class="mono" x="{hx}" y="{by_ + 4.5}" font-size="12" font-weight="700" fill="{PURPLE}" text-anchor="middle">'
             f'HEAD → main <tspan fill="{MUTED}" font-weight="400">· {last}</tspan></text></g>')

    # footer: legend left, the honest caption right
    fy = GY + GRID_ROWS * PITCH + 62
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
    p.append(f'<line x1="{GX}" y1="{fy + 18}" x2="{W - GX + 12}" y2="{fy + 18}" stroke="{BORDER}"/>'
             f'<text class="mono" x="{GX}" y="{fy + 40}" font-size="11.5" letter-spacing="1.5" fill="{MUTED}">'
             f'ORIGINAL CONCEPT &amp; DESIGN · <tspan fill="{TEXT}" font-weight="700">ABDULLAH BAKIR</tspan> · 2026</text>'
             f'<text class="mono" x="{W - GX + 12}" y="{fy + 40}" font-size="11.5" letter-spacing="1.5" fill="{MUTED}" text-anchor="end">'
             f'NAME, DRAWINGS AND WORM DRAWN ONLY FROM REAL COMMIT DAYS</text>')
    height = fy + 58
    T, fade, worm_svg = worm(food)
    p.append(worm_svg)
    p.append("</svg>")
    out = "".join(p).replace("%%NAME%%", "".join(cell_rect(f, T) for f in food)).replace("%%FADE%%", fade)
    return out.replace("%%H%%", f"{height:.0f}")


if __name__ == "__main__":
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")

