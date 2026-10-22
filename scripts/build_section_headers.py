"""Generate assets/sections/*.svg — one consistent header per README section,
plus the end-of-section splitter.

Two looks are available (STYLE below):
  editorial  — numbered eyebrow, big title, one-line descriptor, red→green rule
  tab        — an editor tab bar: traffic lights, file tab, breadcrumb path

Pure SVG so it renders inside GitHub's <img> proxy.
"""
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "sections"

W = 1400
BG, SURFACE, BORDER = "#0d1117", "#161b22", "#30363d"
TEXT, MUTED = "#e6edf3", "#7d8590"
RED, GREEN = "#F90001", "#39d353"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'JetBrains Mono',Menlo,Consolas,monospace"

# (slug, eyebrow, title, descriptor, file name for the tab look)
SECTIONS = [
    ("about",         "WHO I AM",              "About Me",            "the person behind the commits",                    "about.py"),
    ("skills",        "SKILLS · EXPERTISE",    "Tech Stack",          "what I use and where it fits", "stack.yml"),
    ("focus",         "NOW · WORKING ON",      "Current Focus",       "what I'm working on now",               "focus.md"),
    ("highlights",    "CAREER · TIMELINE",     "Yearly Highlights",   "what I did each year",                             "CHANGELOG.md"),
    ("stats",         "BY THE NUMBERS",        "GitHub Stats",        "live from the GitHub API",                         "stats.json"),
    ("activity",      "LAST 7 DAYS",           "Recent Activity",     "commits, repos and pull requests",                      "git.log"),
    ("releases",      "SHIPPED",               "Latest Releases",     "tagged and published",                             "releases.md"),
    ("projects",      "SELECTED WORK",         "Featured Projects",   "ranked weekly by activity and stars",              "projects/"),
    ("pagespeed",     "IN PRODUCTION",         "Live Performance",    "audited daily with Google Lighthouse",             "lighthouse.json"),
    ("contributions", "EVERY DAY COUNTS",      "Contribution Graph",  "the same data, four ways",                         "graph.svg"),
    ("connect",       "SAY HELLO",             "Connect With Me",     "LinkedIn or email is the fastest",               "contact.vcf"),
    ("guestbook",     "LEAVE A NOTE",          "Guestbook",           "say hi, it opens a pre-filled issue",              "guestbook.md"),
]


def editorial(i, slug, eyebrow, title, desc, _file):
    h = 120
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" role="img" aria-label="{escape(title)}">'
        f'<defs><linearGradient id="r" x1="0" x2="1"><stop offset="0" stop-color="{RED}"/>'
        f'<stop offset=".55" stop-color="{RED}" stop-opacity=".35"/><stop offset="1" stop-color="{GREEN}" stop-opacity="0"/></linearGradient></defs>'
        f'<text x="0" y="30" font-family="{MONO}" font-size="14" font-weight="700" letter-spacing="3.5" fill="{GREEN}">'
        f'// {i:02d} · {escape(eyebrow)}</text>'
        f'<text x="0" y="80" font-family="{SANS}" font-size="46" font-weight="800" letter-spacing="-1" fill="{TEXT}">'
        f'{escape(title)}<tspan fill="{RED}">.</tspan></text>'
        f'<text x="{W}" y="80" text-anchor="end" font-family="{SANS}" font-size="17" font-style="italic" fill="{MUTED}">{escape(desc)}</text>'
        f'<rect x="0" y="104" width="{W}" height="2" fill="url(#r)"/>'
        f'<rect x="0" y="102" width="56" height="6" rx="3" fill="{RED}"/>'
        f'</svg>')


def tab(i, slug, eyebrow, title, desc, file):
    h = 112
    tw = 34 + len(file) * 11 + 40
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" role="img" aria-label="{escape(title)}">'
        f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>'
        f'<path d="M.5 12.5a12 12 0 0 1 12-12h{W - 25}a12 12 0 0 1 12 12V44H.5z" fill="{SURFACE}"/>'
        f'<line x1="0" y1="44" x2="{W}" y2="44" stroke="{BORDER}"/>'
        f'<circle cx="26" cy="22" r="6.5" fill="#ff5f57"/><circle cx="48" cy="22" r="6.5" fill="#febc2e"/><circle cx="70" cy="22" r="6.5" fill="#28c840"/>'
        f'<rect x="100" y="8" width="{tw}" height="37" rx="8" fill="{BG}" stroke="{BORDER}"/>'
        f'<rect x="100" y="40" width="{tw}" height="6" fill="{BG}"/>'
        f'<rect x="100" y="8" width="{tw}" height="2.5" rx="1" fill="{RED}"/>'
        f'<text x="118" y="32" font-family="{MONO}" font-size="14" fill="{TEXT}">{escape(file)}</text>'
        f'<text x="{W - 24}" y="30" text-anchor="end" font-family="{MONO}" font-size="13" fill="{MUTED}">~/abdullah/{slug}</text>'
        f'<text x="28" y="88" font-family="{SANS}" font-size="34" font-weight="800" letter-spacing="-.5" fill="{TEXT}">{escape(title)}</text>'
        f'<text x="{W - 28}" y="86" text-anchor="end" font-family="{MONO}" font-size="13" letter-spacing="2.5" fill="{GREEN}">'
        f'{i:02d} · {escape(eyebrow)}</text>'
        f'</svg>')


def index_header():
    """Header for the table of contents, same look as the section headers but unnumbered."""
    return editorial(0, "index", "INDEX", "Contents", "jump to any section", "").replace("// 00 · ", "// ")


def toc_pill(i, title):
    """One clickable contents entry (the README wraps it in a link to the section)."""
    w, h = 300, 54
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{i:02d} {escape(title)}">'
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="10" fill="{SURFACE}" stroke="{BORDER}"/>'
        f'<rect x=".5" y="12" width="3" height="{h - 24}" rx="1.5" fill="{RED}"/>'
        f'<text x="22" y="34" font-family="{MONO}" font-size="14" font-weight="700" fill="{RED}">{i:02d}</text>'
        f'<text x="58" y="34" font-family="{SANS}" font-size="17" font-weight="700" fill="{TEXT}">{escape(title)}</text>'
        f'<text x="{w - 22}" y="34" text-anchor="end" font-family="{SANS}" font-size="17" fill="{MUTED}">&#8594;</text>'
        f'</svg>')


def splitter():
    h = 40
    nodes = "".join(f'<circle cx="{W / 2 + dx}" cy="20" r="{r}" fill="{c}"/>'
                    for dx, r, c in ((-28, 4, BORDER), (0, 6, RED), (28, 4, BORDER)))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" role="presentation">'
        f'<defs><linearGradient id="l" x1="0" x2="1"><stop offset="0" stop-color="{BORDER}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{BORDER}"/><stop offset="1" stop-color="{BORDER}" stop-opacity="0"/></linearGradient></defs>'
        f'<rect x="0" y="19" width="{W}" height="2" fill="url(#l)"/>{nodes}</svg>')


def main(style="editorial"):
    OUT.mkdir(parents=True, exist_ok=True)
    make = editorial if style == "editorial" else tab
    for i, sec in enumerate(SECTIONS, 1):
        (OUT / f"{sec[0]}.svg").write_text(make(i, *sec), encoding="utf-8")
    (OUT / "splitter.svg").write_text(splitter(), encoding="utf-8")
    (OUT / "index.svg").write_text(index_header(), encoding="utf-8")
    for i, sec in enumerate(SECTIONS, 1):
        (OUT / f"toc-{sec[0]}.svg").write_text(toc_pill(i, sec[2]), encoding="utf-8")
    print(f"wrote {len(SECTIONS)} headers + splitter to {OUT.relative_to(ROOT)} ({style})")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "editorial")
