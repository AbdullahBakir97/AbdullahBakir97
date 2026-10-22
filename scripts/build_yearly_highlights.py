"""Generate assets/yearly-highlights.svg: one card per year.

The story lines are written by hand in YEARS below. The numbers at the bottom of
each card (contributions, active days, busiest month) come from the daily
assets/heatmap-*.svg files, so they stay correct without editing.
"""
import calendar
import datetime as dt
import re
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "yearly-highlights.svg"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'JetBrains Mono',Menlo,Consolas,monospace"

YEARS = {
    2023: ("#bc8cff", "First projects", [
        "My first repo in May: a landing page with Bootstrap 5.",
        "Built Django-Store in September, a shop with Django, DRF and Bootstrap.",
        "Built Django-Blog and Jobs-Portal. Jobs-Portal has 29 stars now."]),
    2024: ("#F90001", "My first real customer", [
        "Built Barber-Salon for a real salon. It runs at kharsa-style.de and has 55 stars.",
        "Started Django LMS in June, and more than 10 other projects that summer.",
        "Started Mini-RAG, and Baeckrei for a bakery customer."]),
    2025: ("#ff652f", "A quieter year", [
        "Fewer public commits this year.",
        "Kept building Baeckrei with Django and Vue 3: recipes, inventory and online orders.",
        "Started Content-Creator-Tool in January and Email-Sender in August."]),
    2026: ("#e3b341", "Tools for developers", [
        "Built 7 GitHub Apps for pull requests, commits, issues and releases.",
        "Published DevTrust: 9 packages on PyPI and 281 tests.",
        "Built Stock-Manager, a desktop inventory app.",
        "Started my training as a Fachinformatiker at GPB in August."]),
}


def wrap(text, n):
    out, cur = [], ""
    for w in text.split():
        if len(cur) + len(w) + 1 > n:
            out.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    return out + [cur] if cur else out


def year_stats():
    days = {}
    for f in ROOT.glob("assets/heatmap-*.svg"):
        for c, d in re.findall(r"<title>(\d+) on (\d{4}-\d{2}-\d{2})</title>", f.read_text(encoding="utf-8")):
            days[d] = int(c)
    st = defaultdict(lambda: {"total": 0, "active": 0, "months": defaultdict(int)})
    for d, c in days.items():
        y = int(d[:4]); st[y]["total"] += c; st[y]["active"] += c > 0; st[y]["months"][int(d[5:7])] += c
    return st


def render():
    st = year_stats()
    years = sorted(YEARS)
    W, gap = 1400, 20
    cw = (W - gap * (len(years) - 1)) / len(years)
    top, ch = 70, 470
    H = top + ch + 4
    now = dt.date.today().year
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Yearly highlights {years[0]} to {years[-1]}">']
    o.append(f'<line x1="{cw/2}" y1="30" x2="{W-cw/2}" y2="30" stroke="#ffffff" stroke-opacity=".12" stroke-width="2" stroke-dasharray="3 6" stroke-linecap="round"/>')
    for i, y in enumerate(years):
        col, title, lines = YEARS[y]
        x = i * (cw + gap); cx = x + cw / 2
        s = st.get(y, {"total": 0, "active": 0, "months": {}})
        best = max(s["months"], key=s["months"].get) if s["months"] else None
        live = y == now
        o.append(f'<line x1="{cx}" y1="44" x2="{cx}" y2="{top}" stroke="{col}" stroke-opacity=".6" stroke-width="1.6"/>'
                 f'<circle cx="{cx}" cy="30" r="14" fill="#0d1117" stroke="{col}" stroke-width="2"/>'
                 f'<circle cx="{cx}" cy="30" r="5" fill="{col}">'
                 + (f'<animate attributeName="r" values="5;7;5" dur="2s" repeatCount="indefinite"/>' if live else "") + '</circle>')
        gid = f"yh{i}"
        o.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{col}" stop-opacity=".14"/>'
                 f'<stop offset=".5" stop-color="{col}" stop-opacity=".02"/><stop offset="1" stop-color="{col}" stop-opacity="0"/></linearGradient>'
                 f'<rect x="{x}" y="{top}" width="{cw}" height="{ch}" rx="16" fill="#0f141b"/>'
                 f'<rect x="{x}" y="{top}" width="{cw}" height="{ch}" rx="16" fill="url(#{gid})" stroke="#ffffff" stroke-opacity=".1" stroke-width="1.2"/>'
                 f'<line x1="{x+24}" y1="{top+.6}" x2="{x+cw-24}" y2="{top+.6}" stroke="{col}" stroke-width="1.6"/>')
        o.append(f'<text x="{x+26}" y="{top+64}" font-family="{SANS}" font-size="44" font-weight="800" letter-spacing="-1.5" fill="{col}">{y}</text>')
        if live:
            o.append(f'<rect x="{x+cw-82}" y="{top+30}" width="58" height="24" rx="12" fill="{col}" fill-opacity=".14" stroke="{col}" stroke-opacity=".6"/>'
                     f'<circle cx="{x+cw-68}" cy="{top+42}" r="3.5" fill="{col}"><animate attributeName="opacity" values="1;.3;1" dur="1.6s" repeatCount="indefinite"/></circle>'
                     f'<text x="{x+cw-60}" y="{top+46.5}" font-family="{MONO}" font-size="11" font-weight="700" fill="{col}">LIVE</text>')
        o.append(f'<text x="{x+26}" y="{top+100}" font-family="{SANS}" font-size="21" font-weight="700" fill="#f0f6fc">{escape(title)}</text>')
        yy = top + 144
        for ln in lines:
            parts = wrap(ln, 36)
            o.append(f'<circle cx="{x+30}" cy="{yy-5}" r="3" fill="{col}"/>')
            for k, p in enumerate(parts):
                o.append(f'<text x="{x+44}" y="{yy + k*21}" font-family="{SANS}" font-size="14.5" fill="#c9d1d9">{escape(p)}</text>')
            yy += len(parts) * 21 + 14
        sy = top + ch - 84
        o.append(f'<line x1="{x+24}" y1="{sy}" x2="{x+cw-24}" y2="{sy}" stroke="#ffffff" stroke-opacity=".07"/>')
        tiles = [(f'{s["total"]:,}', "contributions"), (str(s["active"]), "active days"),
                 (calendar.month_abbr[best] if best else "–", "best month")]
        tw = (cw - 48) / 3
        for k, (v, lab) in enumerate(tiles):
            tx = x + 24 + k * tw
            o.append(f'<text x="{tx}" y="{sy+38}" font-family="{SANS}" font-size="22" font-weight="800" fill="{col if k == 0 else "#f0f6fc"}">{v}</text>'
                     f'<text x="{tx}" y="{sy+60}" font-family="{MONO}" font-size="10" letter-spacing=".6" fill="#8b949e">{lab.upper()}</text>')
    o.append("</svg>")
    return "".join(o)


def main():
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
