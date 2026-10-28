"""Generate assets/about-hero.svg (identity card, stats, now shipping) and
assets/about-code.svg (about.py editor card with a rotating motto).

Pure SVG (no foreignObject) so it renders inside GitHub's <img> proxy.

The capsule-render banner at the very top of the README already carries
the user's name, role, and locations — so this hero focuses on what's
NEXT: what I'm actively shipping, my philosophy, and live stats. The
right-hand avatar block stays as the visual anchor.

The avatar embeds assets/abdullah.jpg as base64 data URI so the SVG is
fully self-contained (no relative-path resolution gotchas inside
GitHub's camo image proxy).
"""
import base64
import datetime as dt
import json
import os
import random
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape
from xml.sax.saxutils import escape as X

ASSETS = Path(__file__).resolve().parents[1] / "assets"
OUT = ASSETS / "about-hero.svg"
CODE_OUT = ASSETS / "about-code.svg"
PHOTO = ASSETS / "abdullah.jpg"


def _photo_data_uri() -> str | None:
    if not PHOTO.exists():
        return None
    raw = PHOTO.read_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")

W, H = 1400, 560

# What I'm currently shipping — narrative, recognizable repo names
NOW_SHIPPING = [
    ("PortfolioCraft", "active",  "GitHub-history → portfolio CLI + Action"),
    ("Stock-Manager",  "active",  "desktop inventory · v2.4.x · daily commits"),
    ("Ragolex",        "active",  "RAG service — hybrid search, citations, MCP"),
    ("Baeckrei",       "active",  "bakery management — Django + Vue 3"),
]

STATS = [
    ("YEARS CODING",   "4+",            "since 2022"),
    ("REPOS SHIPPED",  "60+",           "across stack"),
    ("LANGUAGES",      "EN · DE · AR",  "fluent in 3"),
]

GH_USER = os.environ.get("GH_USER", "AbdullahBakir97")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
SKIP_REPOS = {GH_USER.lower()}          # the profile repo itself is README plumbing, not a project
CODING_SINCE = 2022


def _gh(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": GH_USER})
    if GH_TOKEN:
        req.add_header("Authorization", f"Bearer {GH_TOKEN}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def live_now_shipping(limit: int = 4):
    """The repos with the most of my commits in the last 7 days, from the GitHub API.

    Returns [(name, status, blurb)] or None when the API is unreachable, so the
    static NOW_SHIPPING list stays as the offline fallback.
    """
    try:
        since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)
        repos = _gh(f"https://api.github.com/users/{GH_USER}/repos?type=owner&sort=pushed&per_page=30")
        rows = []
        for repo in repos:
            if repo.get("fork") or repo.get("archived") or repo["name"].lower() in SKIP_REPOS:
                continue
            pushed = dt.datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
            if pushed < since:
                continue
            commits = _gh(f"https://api.github.com/repos/{GH_USER}/{repo['name']}/commits"
                          f"?author={GH_USER}&since={since:%Y-%m-%dT%H:%M:%SZ}&per_page=100")
            if commits:
                rows.append((len(commits), pushed, repo))
        rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
        out = []
        for n, _, repo in rows[:limit]:
            what = repo.get("description") or repo.get("language") or "work in progress"
            out.append((repo["name"], "active", f"{n} commit{'s' if n != 1 else ''} this week · {what}"))
        return out or None
    except Exception as e:  # network, rate limit, schema drift: keep the last known list
        print(f"  live projects unavailable, using fallback: {e}")
        return None


def live_stats():
    """Same tiles as STATS, with the repo count taken from the API."""
    years = dt.date.today().year - CODING_SINCE
    stats = [("YEARS CODING", f"{years}+", f"since {CODING_SINCE}"), STATS[1], STATS[2]]
    try:
        repos = _gh(f"https://api.github.com/users/{GH_USER}/repos?type=owner&per_page=100")
        own = [r for r in repos if not r.get("fork")]
        stats[1] = ("PUBLIC REPOS", str(len(own)), "on GitHub")
    except Exception as e:
        print(f"  repo count unavailable, using fallback: {e}")
    return stats


def _fit(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[: max(0, max_chars - 1)].rstrip(" ·,—-") + "…"


SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'JetBrains Mono',Menlo,Consolas,monospace"

def panel(x,y,w,h,col,gid,op=.12):
    return (f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{col}" stop-opacity="{op}"/><stop offset=".55" stop-color="{col}" stop-opacity=".015"/><stop offset="1" stop-color="{col}" stop-opacity="0"/></linearGradient>'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="#0f141b"/><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="url(#{gid})" stroke="#ffffff" stroke-opacity=".1" stroke-width="1.2"/>'
            f'<line x1="{x+24}" y1="{y+.6}" x2="{x+w-24}" y2="{y+.6}" stroke="{col}" stroke-width="1.6"/>')

def render(shipping=None, stats=None) -> str:
    shipping = [(n, b) for n, _, b in (shipping or NOW_SHIPPING)]
    base = stats or live_stats_offline()
    stats = [(base[0][0], base[0][1], base[0][2], '#ff652f'), (base[1][0], base[1][1], base[1][2], '#58a6ff'),
             ('PYPI PACKAGES', '9', 'DevTrust suite', '#e3b341'), (base[2][0], base[2][1], base[2][2], '#3fb950')]
    photo_uri = _photo_data_uri() or ""
    o=[f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
     '<defs><linearGradient id="ring" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F90001"/><stop offset=".5" stop-color="#ff652f"/><stop offset="1" stop-color="#e3b341"/></linearGradient>'
     '<clipPath id="av"><circle cx="0" cy="0" r="96"/></clipPath>'
     '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="14"/></filter></defs>']
    # --- left identity card
    lx, ly, lw, lh = 0, 0, 400, H
    o.append(panel(lx+1,ly+1,lw-2,lh-2,"#F90001","pl",.16))
    cx, cy = lx+lw/2, 168
    o.append(f'<circle cx="{cx}" cy="{cy}" r="112" fill="#F90001" opacity=".25" filter="url(#glow)"/>'
             f'<circle cx="{cx}" cy="{cy}" r="106" fill="none" stroke="url(#ring)" stroke-width="4"/>'
             f'<circle cx="{cx}" cy="{cy}" r="116" fill="none" stroke="#ff652f" stroke-opacity=".5" stroke-width="1.5" stroke-dasharray="2 9" stroke-linecap="round">'
             f'<animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" to="360 {cx} {cy}" dur="40s" repeatCount="indefinite"/></circle>'
             f'<g transform="translate({cx} {cy})"><image href="{photo_uri}" x="-96" y="-96" width="192" height="192" clip-path="url(#av)" preserveAspectRatio="xMidYMid slice"/></g>'
             f'<circle cx="{cx+72}" cy="{cy+72}" r="13" fill="#0f141b"/><circle cx="{cx+72}" cy="{cy+72}" r="8" fill="#3fb950"><animate attributeName="opacity" values="1;.4;1" dur="2s" repeatCount="indefinite"/></circle>')
    o.append(f'<text x="{cx}" y="334" text-anchor="middle" font-family="{SANS}" font-size="30" font-weight="800" letter-spacing="-.5" fill="#f0f6fc">Abdullah Bakir</text>'
             f'<text x="{cx}" y="364" text-anchor="middle" font-family="{SANS}" font-size="16" fill="#c9d1d9">Full-stack developer</text>'
             f'<text x="{cx}" y="390" text-anchor="middle" font-family="{MONO}" font-size="13.5" fill="#8b949e">Python · Django · Vue 3 · Nuxt</text>')
    o.append(f'<line x1="{lx+40}" y1="418" x2="{lx+lw-40}" y2="418" stroke="#ffffff" stroke-opacity=".08"/>')
    rows=[("📍","Berlin, Germany","#e6edf3"),("🌐","open to remote","#e6edf3")]
    o.append(f'<path d="M{lx+52} 446c0-6 4.5-10 10-10s10 4 10 10c0 7-10 16-10 16s-10-9-10-16z" fill="none" stroke="#ff652f" stroke-width="2"/><circle cx="{lx+62}" cy="446" r="3" fill="#ff652f"/>'
             f'<text x="{lx+84}" y="452" font-family="{SANS}" font-size="15" fill="#e6edf3">Berlin, Germany <tspan fill="#8b949e">· open to remote</tspan></text>')
    o.append(f'<rect x="{lx+40}" y="478" width="{lw-80}" height="44" rx="22" fill="#3fb950" fill-opacity=".1" stroke="#3fb950" stroke-opacity=".55"/>'
             f'<circle cx="{lx+66}" cy="500" r="5" fill="#3fb950"><animate attributeName="r" values="5;7;5" dur="2s" repeatCount="indefinite"/></circle>'
             f'<text x="{lx+lw/2+10}" y="505.5" text-anchor="middle" font-family="{SANS}" font-size="15" font-weight="700" fill="#3fb950">Open to freelance &amp; collaboration</text>')
    # --- right column
    rx = 424; rw = W - rx
    o.append(panel(rx,1,rw-1,262,"#ff652f","pr",.12))
    o.append(f'<text x="{rx+34}" y="48" font-family="{MONO}" font-size="13.5" font-weight="700" letter-spacing="3" fill="#ff652f">// HELLO THERE</text>'
             f'<text x="{rx+34}" y="96" font-family="{SANS}" font-size="31" font-weight="800" letter-spacing="-.6" fill="#f0f6fc">I’m Abdullah, a full-stack developer</text>'
             f'<text x="{rx+34}" y="134" font-family="{SANS}" font-size="31" font-weight="800" letter-spacing="-.6" fill="#f0f6fc">in Berlin<tspan fill="#F90001">.</tspan></text>'
             f'<text x="{rx+34}" y="174" font-family="{SANS}" font-size="15.5" fill="#8b949e">I build web apps with Python, Django and Vue 3, from the database to the UI.</text>'
             )
    px_ = rx + 34
    for tag, col in [("Backend","#ff652f"),("Frontend","#42b883"),("DevOps","#e3b341"),("Data","#58a6ff"),("AI tooling","#F90001")]:
        tw_ = len(tag)*8.2 + 34
        o.append(f'<rect x="{px_}" y="196" width="{tw_}" height="28" rx="14" fill="{col}" fill-opacity=".1" stroke="{col}" stroke-opacity=".5"/>'
                 f'<circle cx="{px_+14}" cy="210" r="3.5" fill="{col}"/><text x="{px_+24}" y="215" font-family="{SANS}" font-size="13" font-weight="600" fill="#e6edf3">{tag}</text>')
        px_ += tw_ + 10
    # stat tiles
    ty = 280; tw = (rw - 3*16) / 4
    for i,(lab,val,sub,col) in enumerate(stats):
        x = rx + i*(tw+16)
        o.append(panel(x,ty,tw,104,col,f"st{i}",.14))
        o.append(f'<text x="{x+20}" y="{ty+32}" font-family="{MONO}" font-size="12" font-weight="700" letter-spacing="2" fill="#8b949e">{lab}</text>'
                 f'<text x="{x+20}" y="{ty+68}" font-family="{SANS}" font-size="{30 if len(val)<6 else 26}" font-weight="800" fill="{col}">{val}</text>'
                 f'<text x="{x+20}" y="{ty+92}" font-family="{SANS}" font-size="12.5" fill="#8b949e">{sub}</text>')
    # now shipping
    sy = 400; sh = H - sy - 1
    o.append(panel(rx,sy,rw-1,sh,"#3fb950","ps",.12))
    o.append(f'<circle cx="{rx+30}" cy="{sy+30}" r="5" fill="#3fb950"><animate attributeName="opacity" values="1;.3;1" dur="1.6s" repeatCount="indefinite"/></circle>'
             f'<text x="{rx+44}" y="{sy+35}" font-family="{SANS}" font-size="16" font-weight="700" fill="#f0f6fc">Now shipping</text>'
             f'<text x="{rx+158}" y="{sy+35}" font-family="{SANS}" font-size="12.5" fill="#8b949e">repos with the most of my commits in the last 7 days · updated daily</text>')
    cwid = (rw - 1 - 48 - 16) / 2
    for j,(nm,bl) in enumerate(shipping):
        x = rx + 24 + (j%2)*(cwid+16); y = sy + 54 + (j//2)*48
        o.append(f'<rect x="{x}" y="{y}" width="{cwid}" height="40" rx="10" fill="#ffffff" fill-opacity=".03" stroke="#ffffff" stroke-opacity=".08"/>'
                 f'<text x="{x+16}" y="{y+25}" font-family="{SANS}" font-size="14" font-weight="700" fill="#e6edf3">{X(nm)}</text>'
                 f'<text x="{x+150}" y="{y+25}" font-family="{SANS}" font-size="12.5" fill="#8b949e">{X(bl if len(bl)<=44 else bl[:43].rstrip(' ,·—')+'…')}</text>'
                 f'<circle cx="{x+cwid-18}" cy="{y+20}" r="4" fill="#3fb950"><animate attributeName="opacity" values="1;.3;1" dur="2s" begin="{j*.4}s" repeatCount="indefinite"/></circle>')
    o.append('</svg>')


    return ''.join(o)


def render_code() -> str:
    K,S,F,C,N,P,A = "#ff7b72","#a5d6ff","#d2a8ff","#8b949e","#79c0ff","#e6edf3","#ffa657"
    def kv(k, v): return [(P,"    "),(N,f"{k:<16}"),(K,"= "),*v]
    def lst(*xs):
        out=[(P,"[")]
        for i,x in enumerate(xs):
            out.append((S,f'"{x}"'));
            if i<len(xs)-1: out.append((P,", "))
        return out+[(P,"]")]
    L = [
     [(K,"import "),(P,"random")],
     [],
     [(K,"class "),(A,"AbdullahBakir"),(P,":")],
     [(P,"    "),(S,'"""Full-stack developer from Berlin. I build web apps and ship them."""')],
     [],
     kv("location",[(S,'"Berlin, Germany (open to remote)"')]),
     kv("languages",lst("Python","TypeScript","JavaScript")),
     kv("backend",lst("Django","DRF","FastAPI","Celery")),
     kv("frontend",lst("Vue 3","Nuxt","Tailwind")),
     kv("databases",lst("PostgreSQL","pgvector","Redis")),
     kv("infrastructure",lst("Docker","Kubernetes","GitHub Actions")),
     kv("currently_into",lst("AI dev tooling","RAG","GitHub Apps")),
     kv("available_for",lst("Freelance","Open source","Long-term collaboration")),
     kv("speaks",lst("English","Deutsch","العربية")),
     [],
     [(P,"    "),(K,"def "),(F,"philosophy"),(P,"(self) -> "),(N,"str"),(P,":")],
     [(P,"        "),(K,"return "),(S,'"Ship something useful → learn → ship again."')],
     [],
     [(P,"    "),(K,"def "),(F,"motto"),(P,"(self) -> "),(N,"str"),(P,":")],
     [(P,"        "),(K,"return "),(P,"random."),(F,"choice"),(P,"("),(N,"MOTTOS"),(P,")"),(C,"  # a new one every few seconds")],
     [],
     [(P,"me = "),(A,"AbdullahBakir"),(P,"()")],
     [(F,"print"),(P,"(me.philosophy())")],
     [(F,"print"),(P,"(me.motto())")],
    ]
    MOTTOS = ["Curious about how systems break","Code should be useful before it's clever","Boring architecture is usually the right one",
     "Tests are letters from past me to future me","A good name is half the documentation","Make it work, make it right, make it fast",
     "Never trust user input","Measure twice, merge once","Done is better than perfect","First, do no harm to production",
     "The best code is code you don't have to write","Read the code, not the comments","I write Python the way I'd explain it to a friend",
     "Build it once for yourself, then share it","Three languages, one keyboard","Every commit is a small gift to my future team"]
    W2 = 1400; lh = 30; top = 92; H2 = top + len(L)*lh + 168
    o=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W2} {H2}" width="{W2}" height="{H2}">',
     '<style>.ln{opacity:0;animation:a 14s infinite both}@keyframes a{0%{opacity:0}2%{opacity:1}95%{opacity:1}99%{opacity:0}}.cur{animation:b 1s steps(1) infinite}@keyframes b{50%{opacity:0}}</style>',
     '<defs><linearGradient id="ed" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3776ab" stop-opacity=".12"/><stop offset=".3" stop-color="#3776ab" stop-opacity=".01"/><stop offset="1" stop-color="#3776ab" stop-opacity="0"/></linearGradient></defs>',
     f'<rect x="1" y="1" width="{W2-2}" height="{H2-2}" rx="16" fill="#0d1117"/><rect x="1" y="1" width="{W2-2}" height="{H2-2}" rx="16" fill="url(#ed)" stroke="#ffffff" stroke-opacity=".1" stroke-width="1.2"/>',
     f'<path d="M1 17a16 16 0 0 1 16-16h{W2-34}a16 16 0 0 1 16 16v35H1z" fill="#ffffff" fill-opacity=".03"/><line x1="1" y1="52" x2="{W2-1}" y2="52" stroke="#ffffff" stroke-opacity=".08"/>',
     '<circle cx="30" cy="27" r="6.5" fill="#ff5f57"/><circle cx="52" cy="27" r="6.5" fill="#febc2e"/><circle cx="74" cy="27" r="6.5" fill="#28c840"/>',
     f'<rect x="104" y="10" width="150" height="43" rx="8" fill="#0d1117" stroke="#ffffff" stroke-opacity=".08"/><rect x="104" y="48" width="150" height="6" fill="#0d1117"/><line x1="112" y1="11" x2="246" y2="11" stroke="#ffd43b" stroke-width="2"/>'
     f'<g transform="translate(118 21) scale(.16)"><path fill="#3776ab" d="M63.4 1.7C31.2 1.7 33.2 15.7 33.2 15.7l.1 14.5H64v4.3H21.1S.5 32.2.5 64.8c0 32.6 18 31.5 18 31.5h10.7V81.1s-.6-18 17.7-18h30.5s17.2.3 17.2-16.6V18.6S97.2 1.7 63.4 1.7zM46.4 11.5c3.1 0 5.5 2.5 5.5 5.5s-2.5 5.5-5.5 5.5-5.5-2.5-5.5-5.5 2.4-5.5 5.5-5.5z"/><path fill="#ffd43b" d="M64.3 126.3c32.2 0 30.2-14 30.2-14l-.1-14.5H63.7v-4.3h42.9s20.6 2.3 20.6-30.3c0-32.6-18-31.5-18-31.5H98.5v15.1s.6 18-17.7 18H50.3s-17.2-.3-17.2 16.6v28S30.5 126.3 64.3 126.3zm17-9.7c-3.1 0-5.5-2.5-5.5-5.5s2.5-5.5 5.5-5.5 5.5 2.5 5.5 5.5-2.4 5.5-5.5 5.5z"/></g>'
     f'<text x="146" y="37" font-family="{MONO}" font-size="14" fill="#e6edf3">about.py</text>',
     f'<text x="{W2-28}" y="33" text-anchor="end" font-family="{MONO}" font-size="12.5" fill="#6e7681">Python 3.12 · UTF-8</text>']
    for i, toks in enumerate(L):
        y = top + i*lh + 4; d = 0.15 + i*0.18
        t = "".join(f'<tspan fill="{c}">{X(s)}</tspan>' for c,s in toks)
        o.append(f'<g class="ln" style="animation-delay:{d:.2f}s"><text x="62" y="{y}" text-anchor="end" font-family="{MONO}" font-size="14" fill="#484f58">{i+1}</text>'
                 f'<text x="86" y="{y}" font-family="{MONO}" font-size="16.5" xml:space="preserve">{t}</text></g>')
    yb = H2 - 114; d = 0.15 + len(L)*0.18 + .3
    o.append(f'<line x1="1" y1="{yb-34}" x2="{W2-1}" y2="{yb-34}" stroke="#ffffff" stroke-opacity=".08"/>'
             f'<text x="{W2-28}" y="{yb}" text-anchor="end" font-family="{MONO}" font-size="12.5" fill="#6e7681">OUTPUT</text>'
             f'<g class="ln" style="animation-delay:{d:.2f}s"><text x="30" y="{yb}" font-family="{MONO}" font-size="15.5" xml:space="preserve"><tspan fill="#42b883">$</tspan><tspan fill="#e6edf3"> python about.py</tspan></text>'
             f'<text x="30" y="{yb+30}" font-family="{MONO}" font-size="15.5" fill="#3fb950">Ship something useful → learn → ship again.</text></g>')
    N = len(MOTTOS); Tm = 4.5; tot = N*Tm; my = yb + 60
    o.append(f'<g class="ln" style="animation-delay:{d+.4:.2f}s">')
    MC = ["#FF652F","#22D3EE","#FFD700","#34D399","#A78BFA","#F90001","#EC4899","#00C853"]
    for i, m in enumerate(MOTTOS):
        a = i/N; b = a + .3/N; c = a + .85/N; e = a + .97/N
        w = (len(m)+3)*9.6 + 14
        kt = "0;" + ";".join(f"{v:.4f}" for v in [a, b, c, e]) + ";1"
        o.append(f'<clipPath id="mc{i}"><rect x="28" y="{my-18}" height="26" width="0">'
                 f'<animate attributeName="width" values="0;0;{w:.0f};{w:.0f};0;0" keyTimes="{kt}" dur="{tot}s" repeatCount="indefinite"/></rect></clipPath>'
                 f'<text x="30" y="{my}" font-family="{MONO}" font-size="15.5" fill="{MC[i % len(MC)]}" clip-path="url(#mc{i})">// {X(m)}</text>')
    o.append('</g>')
    o.append(f'<text x="30" y="{my+34}" font-family="{MONO}" font-size="15.5" fill="#42b883">$</text><rect class="cur" x="46" y="{my+20}" width="9" height="18" fill="#42b883"/>')
    o.append('</svg>')

    return ''.join(o)


def live_stats_offline():
    years = dt.date.today().year - CODING_SINCE
    return [("YEARS CODING", f"{years}+", f"since {CODING_SINCE}"), STATS[1], STATS[2]]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(live_now_shipping(), live_stats()), encoding="utf-8")
    CODE_OUT.write_text(render_code(), encoding="utf-8")
    print(f"wrote {OUT.name} and {CODE_OUT.name}")


if __name__ == "__main__":
    main()
