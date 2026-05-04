"""Generate assets/about-hero.svg — an editorial-style banner.

Pure SVG (no foreignObject) so it renders inside GitHub's <img> proxy.

Design intent: magazine-cover hero, not a busy dashboard.
- Big bold name typography (display-weight, kerned tight)
- One clear focal point (gradient avatar circle on the right)
- A horizontal tech-stack badge row (readable, not orbiting)
- Three large stat tiles below
- Subtle animated atmospherics — aurora ribbon + twinkling stars
- High contrast text throughout for readability at any render size
"""
import datetime as dt
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "assets" / "about-hero.svg"

W, H = 1400, 460

# Tech stack — shown as a simple horizontal pill row (readable, not orbital)
TECH = [
    ("Python",     "#3776ab"),
    ("Django",     "#0c4b33"),
    ("Vue",        "#42b883"),
    ("Nuxt",       "#00dc82"),
    ("TypeScript", "#3178c6"),
    ("Postgres",   "#336791"),
    ("Redis",      "#dc382d"),
    ("Docker",     "#2496ed"),
    ("AWS",        "#ff9900"),
]

STATS = [
    ("YEARS CODING",   "5+",     "since 2020"),
    ("REPOS SHIPPED",  "60+",    "across stack"),
    ("LANGUAGES",      "EN · DE · AR", "fluent in 3"),
]


def render() -> str:
    rng = random.Random(20260504)
    parts: list[str] = []

    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="Abdullah Bakir — Full-Stack Developer">'
    )

    # ── Defs ───────────────────────────────────────────────────────────────
    parts.append('<defs>')

    # Editorial dark background
    parts.append(
        '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#0a0e1a"/>'
        '<stop offset="55%" stop-color="#0d1117"/>'
        '<stop offset="100%" stop-color="#02030a"/>'
        '</linearGradient>'
    )

    # Subtle nebula tints
    parts.append(
        '<radialGradient id="nebA" cx="20%" cy="0%" r="55%">'
        '<stop offset="0%" stop-color="#a855f7" stop-opacity="0.22"/>'
        '<stop offset="100%" stop-color="#a855f7" stop-opacity="0"/>'
        '</radialGradient>'
        '<radialGradient id="nebB" cx="100%" cy="100%" r="60%">'
        '<stop offset="0%" stop-color="#06b6d4" stop-opacity="0.18"/>'
        '<stop offset="100%" stop-color="#06b6d4" stop-opacity="0"/>'
        '</radialGradient>'
    )

    # Aurora ribbon
    parts.append(
        '<linearGradient id="aurora" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0%" stop-color="#39d353" stop-opacity="0"/>'
        '<stop offset="35%" stop-color="#39d353" stop-opacity="0.55"/>'
        '<stop offset="65%" stop-color="#a855f7" stop-opacity="0.55"/>'
        '<stop offset="100%" stop-color="#a855f7" stop-opacity="0"/>'
        '</linearGradient>'
    )

    # Avatar gradient ring (brand colors)
    parts.append(
        '<linearGradient id="avatarRing" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#F90001"/>'
        '<stop offset="50%" stop-color="#FF652F"/>'
        '<stop offset="100%" stop-color="#a855f7"/>'
        '</linearGradient>'
        '<radialGradient id="avatarFill" cx="50%" cy="50%" r="50%">'
        '<stop offset="0%" stop-color="#1a1f2e"/>'
        '<stop offset="100%" stop-color="#02030a"/>'
        '</radialGradient>'
    )

    # Stat tile background
    parts.append(
        '<linearGradient id="statTile" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#1c2129"/>'
        '<stop offset="100%" stop-color="#0d1117"/>'
        '</linearGradient>'
    )

    # Filters
    parts.append(
        '<filter id="bloom" x="-50%" y="-50%" width="200%" height="200%">'
        '<feGaussianBlur stdDeviation="3" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
        '<filter id="haze" x="-20%" y="-20%" width="140%" height="140%">'
        '<feGaussianBlur stdDeviation="8"/>'
        '</filter>'
    )

    # Animations — minimal, readable, no spinning text
    parts.append(
        '<style><![CDATA['
        '@keyframes twinkle{0%,100%{opacity:.2}50%{opacity:1}}'
        '@keyframes auroraSlide{0%,100%{transform:translateX(0);opacity:.5}'
        '50%{transform:translateX(40px);opacity:.85}}'
        '@keyframes pulseDot{0%,100%{transform:scale(1);opacity:1}'
        '50%{transform:scale(1.35);opacity:.5}}'
        '@keyframes ringBreathe{0%,100%{transform:rotate(0deg)}'
        '50%{transform:rotate(180deg)}}'
        '.star{animation:twinkle 3.6s ease-in-out infinite}'
        '.star.b{animation-duration:2.4s}'
        '.star.c{animation-duration:5.1s}'
        '.aurora{animation:auroraSlide 14s ease-in-out infinite}'
        '.avail-dot{animation:pulseDot 1.5s ease-in-out infinite;'
        'transform-origin:center;transform-box:fill-box}'
        f'.av-ring{{transform-origin:center;transform-box:fill-box;'
        'animation:ringBreathe 24s linear infinite}}'
        ']]></style>'
    )

    parts.append('</defs>')

    # ── Backdrop ──────────────────────────────────────────────────────────
    parts.append(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')
    parts.append(
        f'<rect width="{W}" height="{H}" fill="url(#nebA)" filter="url(#haze)"/>'
        f'<rect width="{W}" height="{H}" fill="url(#nebB)" filter="url(#haze)"/>'
    )

    # Aurora ribbon — top
    ay = 50
    parts.append(
        f'<path class="aurora" d="M0,{ay} '
        f'Q{int(W*0.3)},{ay-25} {int(W*0.55)},{ay+5} '
        f'T{W},{ay-10} '
        f'L{W},{ay+24} '
        f'Q{int(W*0.7)},{ay+5} {int(W*0.45)},{ay+22} '
        f'T0,{ay+12} Z" '
        f'fill="url(#aurora)" filter="url(#haze)" opacity="0.7"/>'
    )

    # Starfield — sparse and elegant
    parts.append('<g fill="#e6edf3">')
    star_classes = ['', 'b', 'c']
    for _ in range(50):
        sx = rng.randint(8, W - 8)
        sy = rng.randint(8, H - 80)
        sr = rng.choice([0.4, 0.6, 0.8])
        cls = "star " + rng.choice(star_classes)
        delay = rng.randint(0, 60) / 10
        parts.append(
            f'<circle class="{cls.strip()}" cx="{sx}" cy="{sy}" r="{sr}" '
            f'style="animation-delay:-{delay}s"/>'
        )
    parts.append('</g>')

    # ── Top tag strip ─────────────────────────────────────────────────────
    parts.append(
        f'<text x="60" y="42" '
        f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
        f'font-size="13" font-weight="700" fill="#39d353" letter-spacing="3.5">'
        f'// THE PROFILE · v2026.05</text>'
        f'<text x="{W-60}" y="42" text-anchor="end" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="13" font-weight="600" fill="#7d8590" letter-spacing="2">'
        f'github.com/AbdullahBakir97</text>'
    )

    # ── Avatar (right side) ───────────────────────────────────────────────
    av_cx, av_cy, av_r = W - 220, 230, 110
    # Outer rotating dashed ring (subtle "alive" cue)
    parts.append(
        f'<g class="av-ring" style="transform-origin:{av_cx}px {av_cy}px">'
        f'<circle cx="{av_cx}" cy="{av_cy}" r="{av_r+18}" fill="none" '
        f'stroke="url(#avatarRing)" stroke-width="1.5" stroke-dasharray="3 8" '
        f'opacity="0.55"/>'
        f'</g>'
    )
    # Solid gradient ring
    parts.append(
        f'<circle cx="{av_cx}" cy="{av_cy}" r="{av_r+5}" fill="none" '
        f'stroke="url(#avatarRing)" stroke-width="3"/>'
    )
    # Inner avatar disc
    parts.append(
        f'<circle cx="{av_cx}" cy="{av_cy}" r="{av_r}" '
        f'fill="url(#avatarFill)" stroke="#161b22" stroke-width="2"/>'
    )
    # Initials — large, high-contrast
    parts.append(
        f'<text x="{av_cx}" y="{av_cy+30}" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
        f'font-size="92" font-weight="900" fill="#e6edf3" '
        f'letter-spacing="-3">AB</text>'
    )
    # Pulsing availability dot — bottom-right of avatar
    dot_x, dot_y = av_cx + 78, av_cy + 78
    parts.append(
        f'<circle cx="{dot_x}" cy="{dot_y}" r="14" fill="#0d1117"/>'
        f'<circle class="avail-dot" cx="{dot_x}" cy="{dot_y}" r="9" '
        f'fill="#39d353" filter="url(#bloom)"/>'
    )

    # ── Main name + role (left side) ──────────────────────────────────────
    name_x = 60
    name_y = 150

    # Name — display weight, very large (no tag above; "Hi, I'm" goes BELOW)
    parts.append(
        f'<text x="{name_x}" y="{name_y}" '
        f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
        f'font-size="76" font-weight="900" fill="#ffffff" '
        f'letter-spacing="-2.5">'
        f'Abdullah Bakir</text>'
    )

    # "Hi, I'm" greeting — placed UNDER the name, not above. Combined with role.
    parts.append(
        f'<text x="{name_x}" y="{name_y + 38}" '
        f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
        f'font-size="14" font-weight="700" fill="#39d353" letter-spacing="3" '
        f'text-transform="uppercase">'
        f'👋 Hi, I\'m a</text>'
    )

    # Role — secondary, large, colored
    parts.append(
        f'<text x="{name_x}" y="{name_y + 80}" '
        f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
        f'font-size="32" font-weight="600" fill="#a855f7" '
        f'letter-spacing="-0.5">'
        f'Full-Stack Developer · Berlin, Germany 🇩🇪</text>'
    )

    # Tagline / philosophy
    parts.append(
        f'<text x="{name_x}" y="{name_y + 122}" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="18" font-weight="400" fill="#c9d1d9" font-style="italic">'
        f'"Ship something useful → learn → ship again."</text>'
    )

    # Available pill
    pill_y = name_y + 150
    parts.append(
        f'<g transform="translate({name_x}, {pill_y})">'
        f'<rect x="0" y="0" width="220" height="32" rx="16" fill="#0d2818" '
        f'stroke="#39d353" stroke-width="1.5"/>'
        f'<circle cx="18" cy="16" r="5" fill="#39d353"/>'
        f'<text x="32" y="21" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="13" font-weight="700" fill="#39d353" letter-spacing="0.5">'
        f'Available for collaboration</text>'
        f'</g>'
    )

    # ── Stats strip (bottom) ──────────────────────────────────────────────
    strip_y = H - 110
    strip_h = 80
    n = len(STATS)
    total_w = W - 120
    tile_w = (total_w - (n - 1) * 16) // n
    for i, (label, value, sub) in enumerate(STATS):
        sx = 60 + i * (tile_w + 16)
        parts.append(
            f'<g>'
            # Tile
            f'<rect x="{sx}" y="{strip_y}" width="{tile_w}" height="{strip_h}" '
            f'rx="12" fill="url(#statTile)" stroke="#30363d" stroke-width="1"/>'
            # Accent stripe
            f'<rect x="{sx}" y="{strip_y}" width="4" height="{strip_h}" '
            f'rx="2" fill="#F90001"/>'
            # Label
            f'<text x="{sx+24}" y="{strip_y+24}" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
            f'font-size="11" font-weight="700" fill="#7d8590" letter-spacing="2.5">'
            f'{label}</text>'
            # Value (large)
            f'<text x="{sx+24}" y="{strip_y+58}" '
            f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
            f'font-size="32" font-weight="800" fill="#e6edf3" letter-spacing="-0.5">'
            f'{value}</text>'
            # Subtitle
            f'<text x="{tile_w + sx - 24}" y="{strip_y+58}" text-anchor="end" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
            f'font-size="13" font-weight="500" fill="#8b949e">'
            f'{sub}</text>'
            f'</g>'
        )

    parts.append('</svg>')
    return "".join(parts)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
