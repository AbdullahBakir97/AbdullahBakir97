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

W, H = 1400, 560
PITCH, CELL, RADIUS = 18, 14, 3
GRID_COLS, GRID_ROWS = 71, 19
GX = (W - GRID_COLS * PITCH) / 2 + 12          # room on the left for Mon / Wed / Fri
GY = 166

BG, SURFACE, EMPTY, BORDER = "#0d1117", "#161b22", "#161b22", "#30363d"
TEXT, MUTED = "#e6edf3", "#7d8590"
RED, GREEN = "#F90001", "#39d353"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]

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
    if len(active) >= n:
        picks = [active[round(i * (len(active) - 1) / max(1, n - 1))] for i in range(n)]
    else:
        picks = [active[i % len(active)] for i in range(n)]

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

    # header, in the style of the other banners
    p.append(f'<text class="mono" x="{GX}" y="44" font-size="13" font-weight="700" letter-spacing="3.2" fill="{GREEN}">'
             f'// WRITTEN IN COMMITS · {first[:4]} — {last[:4]}</text>')
    p.append(f'<text class="mono" x="{W - GX + 12}" y="44" font-size="13" letter-spacing="1.5" fill="{MUTED}" text-anchor="end">{HANDLE}</text>')
    p.append(f'<text x="{GX}" y="88" font-size="32" font-weight="800" letter-spacing="-.5" fill="{TEXT}">'
             f'Written in my commits<tspan fill="{GREEN}" font-size="16" dy="-6"> ●</tspan></text>')
    p.append(f'<text x="{GX}" y="118" font-size="15" font-style="italic" fill="{MUTED}">'
             f'Every bright square is a real day I pushed code to GitHub. Read the name left to right and you walk my history, oldest day first.</text>')
    p.append(f'<text class="mono" x="{W - GX + 12}" y="88" font-size="12" letter-spacing="1.5" fill="{MUTED}" text-anchor="end">'
             f'<tspan fill="{GREEN}">●</tspan> REAL DATA · AUTO-UPDATED DAILY</text>')
    p.append(f'<text class="mono" x="{W - GX + 12}" y="110" font-size="12" letter-spacing="1.5" fill="{MUTED}" text-anchor="end">'
             f'last refresh {dt.date.today().isoformat()}</text>')

    # month labels and weekday labels, like the real graph
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for i, m in enumerate(months):
        x = GX + round(i * GRID_COLS / 12) * PITCH
        p.append(f'<text x="{x}" y="{GY - 10}" font-size="11" fill="{MUTED}">{m}</text>')
    for r, d in ((2, "Mon"), (6, "Wed"), (10, "Fri"), (14, "Mon"), (18, "Wed")):
        p.append(f'<text x="{GX - 10}" y="{GY + r * PITCH + CELL - 3}" font-size="11" fill="{MUTED}" text-anchor="end">{d}</text>')

    # the calendar: every empty square, with the rest of the real year ghosted in
    ghost = [d for d in days]
    gi = 0
    empty = []
    for c in range(GRID_COLS):
        for r in range(GRID_ROWS):
            if (c, r) in lit:
                continue
            col = EMPTY
            if ghost:
                g = ghost[gi % len(ghost)]
                gi += 1
                col = level_colour(g[1], cuts) if g[1] > 0 else EMPTY
            x, y = GX + c * PITCH, GY + r * PITCH
            op = "" if col == EMPTY else ' opacity=".12"'
            empty.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{col}"{op}/>')
    p.append(f'<g>{"".join(empty)}</g>')

    # the name: real active days, oldest to newest, landing letter by letter
    lit_rects = []
    under = []
    for i, ((k, c, r), day) in enumerate(zip(cells, picks)):
        x, y = GX + c * PITCH, GY + r * PITCH
        colour = LEVELS[4] if day[1] > cuts[1] else LEVELS[3]   # letters use the two brightest levels so they read
        in_letter = sum(1 for kk, _, _ in cells[:i] if kk == k)
        delay = in_letter * .012
        under.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{EMPTY}"/>')
        lit_rects.append(
            f'<rect class="sq" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" '
            f'style="--c:{colour};animation:L{k} {LOOP}s linear {delay:.3f}s infinite both" fill="{colour}">'
            f'<title>{day[1]} contributions on {day[0]}</title></rect>')
    p.append(f'<g>{"".join(under)}</g><g filter="url(#lit)">{"".join(lit_rects)}</g>')

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
    p.append(f'<g class="head"><circle class="pulse" cx="{hx}" cy="{hy}" r="9" fill="none" stroke="{RED}" stroke-width="2"/>'
             f'<rect x="{hx + 18}" y="{hy - 13}" width="214" height="26" rx="13" fill="{BG}" stroke="{RED}"/>'
             f'<text class="mono" x="{hx + 125}" y="{hy + 4.5}" font-size="12.5" font-weight="700" fill="{RED}" text-anchor="middle">'
             f'HEAD → main <tspan fill="{MUTED}" font-weight="400">· {last}</tspan></text></g>')

    # footer: legend left, the honest caption right
    fy = GY + GRID_ROWS * PITCH + 30
    p.append(f'<text x="{GX}" y="{fy}" font-size="12" fill="{MUTED}">Less</text>')
    for i, col in enumerate(LEVELS):
        p.append(f'<rect x="{GX + 34 + i * 17}" y="{fy - 11}" width="{CELL - 1}" height="{CELL - 1}" rx="{RADIUS}" fill="{col}"/>')
    p.append(f'<text x="{GX + 34 + 5 * 17 + 6}" y="{fy}" font-size="12" fill="{MUTED}">More</text>')
    p.append(f'<text class="cap" x="{W - GX + 12}" y="{fy}" font-size="13" fill="{MUTED}" text-anchor="end">'
             f'<tspan fill="{TEXT}" font-weight="600">{len(cells)}</tspan> real commit days drawn · '
             f'<tspan fill="{TEXT}" font-weight="600">{total:,}</tspan> contributions from '
             f'<tspan fill="{TEXT}">{first}</tspan> to <tspan fill="{TEXT}">{last}</tspan></text>')
    p.append("</svg>")
    return "".join(p)


if __name__ == "__main__":
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
