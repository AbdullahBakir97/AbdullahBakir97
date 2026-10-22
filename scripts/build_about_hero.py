"""Generate assets/about-hero.svg — an editorial-style banner.

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
import random
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"
OUT = ASSETS / "about-hero.svg"
PHOTO = ASSETS / "abdullah.jpg"


def _photo_data_uri() -> str | None:
    if not PHOTO.exists():
        return None
    raw = PHOTO.read_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")

W, H = 1400, 460

# What I'm currently shipping — narrative, recognizable repo names
NOW_SHIPPING = [
    ("PortfolioCraft", "active",  "GitHub-history → portfolio CLI + Action"),
    ("Stock-Manager",  "active",  "desktop inventory · v2.4.x · daily commits"),
    ("PyDev Apps",     "active",  "6 GitHub Apps for PR / issue / release flow"),
    ("Baeckrei",       "active",  "bakery management — Django + Vue 3"),
]

STATS = [
    ("YEARS CODING",   "4+",            "since 2022"),
    ("REPOS SHIPPED",  "60+",           "across stack"),
    ("LANGUAGES",      "EN · DE · AR",  "fluent in 3"),
]


def render() -> str:
    rng = random.Random(20260504)
    parts: list[str] = []

    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="Currently shipping — Abdullah Bakir profile snapshot">'
    )

    # ── Defs ───────────────────────────────────────────────────────────────
    parts.append('<defs>')
    parts.append(
        # Editorial dark gradient
        '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#0a0e1a"/>'
        '<stop offset="55%" stop-color="#0d1117"/>'
        '<stop offset="100%" stop-color="#02030a"/>'
        '</linearGradient>'
        # Nebula tints
        '<radialGradient id="nebA" cx="20%" cy="0%" r="55%">'
        '<stop offset="0%" stop-color="#a855f7" stop-opacity="0.22"/>'
        '<stop offset="100%" stop-color="#a855f7" stop-opacity="0"/>'
        '</radialGradient>'
        '<radialGradient id="nebB" cx="100%" cy="100%" r="60%">'
        '<stop offset="0%" stop-color="#06b6d4" stop-opacity="0.18"/>'
        '<stop offset="100%" stop-color="#06b6d4" stop-opacity="0"/>'
        '</radialGradient>'
        # Aurora ribbon
        '<linearGradient id="aurora" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0%" stop-color="#39d353" stop-opacity="0"/>'
        '<stop offset="35%" stop-color="#39d353" stop-opacity="0.55"/>'
        '<stop offset="65%" stop-color="#a855f7" stop-opacity="0.55"/>'
        '<stop offset="100%" stop-color="#a855f7" stop-opacity="0"/>'
        '</linearGradient>'
        # Avatar ring + fill
        '<linearGradient id="avatarRing" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#F90001"/>'
        '<stop offset="50%" stop-color="#FF652F"/>'
        '<stop offset="100%" stop-color="#a855f7"/>'
        '</linearGradient>'
        '<radialGradient id="avatarFill" cx="50%" cy="50%" r="50%">'
        '<stop offset="0%" stop-color="#1a1f2e"/>'
        '<stop offset="100%" stop-color="#02030a"/>'
        '</radialGradient>'
        # Stat tile background
        '<linearGradient id="statTile" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#1c2129"/>'
        '<stop offset="100%" stop-color="#0d1117"/>'
        '</linearGradient>'
        # Now-shipping row card background
        '<linearGradient id="rowCard" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#161b22"/>'
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
    # Animations
    parts.append(
        '<style><![CDATA['
        '@keyframes twinkle{0%,100%{opacity:.2}50%{opacity:1}}'
        '@keyframes auroraSlide{0%,100%{transform:translateX(0);opacity:.5}'
        '50%{transform:translateX(40px);opacity:.85}}'
        '@keyframes pulseDot{0%,100%{transform:scale(1);opacity:1}'
        '50%{transform:scale(1.35);opacity:.5}}'
        '@keyframes ringBreathe{0%,100%{transform:rotate(0deg)}'
        '50%{transform:rotate(180deg)}}'
        '@keyframes pulseLive{0%,100%{opacity:.85;r:5}50%{opacity:1;r:7}}'
        '.star{animation:twinkle 3.6s ease-in-out infinite}'
        '.star.b{animation-duration:2.4s}'
        '.star.c{animation-duration:5.1s}'
        '.aurora{animation:auroraSlide 14s ease-in-out infinite}'
        '.avail-dot{animation:pulseDot 1.5s ease-in-out infinite;'
        'transform-origin:center;transform-box:fill-box}'
        '.live-dot{animation:pulseLive 2s ease-in-out infinite;'
        'transform-origin:center;transform-box:fill-box}'
        ']]></style>'
    )
    parts.append('</defs>')

    # ── Backdrop ──────────────────────────────────────────────────────────
    parts.append(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')
    parts.append(
        f'<rect width="{W}" height="{H}" fill="url(#nebA)" filter="url(#haze)"/>'
        f'<rect width="{W}" height="{H}" fill="url(#nebB)" filter="url(#haze)"/>'
    )

    # Aurora ribbon
    ay = 50
    aurora_d = (
        f"M0,{ay} "
        f"Q{int(W*0.3)},{ay-25} {int(W*0.55)},{ay+5} "
        f"T{W},{ay-10} "
        f"L{W},{ay+24} "
        f"Q{int(W*0.7)},{ay+5} {int(W*0.45)},{ay+22} "
        f"T0,{ay+12} Z"
    )
    parts.append(
        f'<path class="aurora" d="{aurora_d}" fill="url(#aurora)" '
        f'filter="url(#haze)" opacity="0.7"/>'
    )

    # Starfield
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

    # Top tag strip
    parts.append(
        f'<text x="60" y="42" '
        f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
        f'font-size="13" font-weight="700" fill="#39d353" letter-spacing="3.5">'
        f'// CURRENTLY SHIPPING · v2026.05</text>'
        f'<text x="{W-60}" y="42" text-anchor="end" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="13" font-weight="600" fill="#7d8590" letter-spacing="2">'
        f'github.com/AbdullahBakir97</text>'
    )

    # ── Avatar (right side) — kept as the visual anchor ───────────────────
    av_cx, av_cy, av_r = W - 220, 220, 110
    photo_uri = _photo_data_uri()
    parts.append(
        # Outer dashed rotating ring
        f'<g style="transform-origin:{av_cx}px {av_cy}px;'
        f'animation:ringBreathe 24s linear infinite">'
        f'<circle cx="{av_cx}" cy="{av_cy}" r="{av_r+18}" fill="none" '
        f'stroke="url(#avatarRing)" stroke-width="1.5" stroke-dasharray="3 8" '
        f'opacity="0.55"/>'
        f'</g>'
        # Solid gradient ring
        f'<circle cx="{av_cx}" cy="{av_cy}" r="{av_r+5}" fill="none" '
        f'stroke="url(#avatarRing)" stroke-width="3"/>'
    )

    if photo_uri:
        # Define a clipPath the size of the avatar so the photo crops
        # to a circle. (clipPath is referenced via clip-path="url(#…)".)
        parts.append(
            f'<defs><clipPath id="avatarClip">'
            f'<circle cx="{av_cx}" cy="{av_cy}" r="{av_r}"/>'
            f'</clipPath></defs>'
            # Inner border ring (sits above the photo for a clean edge)
            f'<circle cx="{av_cx}" cy="{av_cy}" r="{av_r}" '
            f'fill="#0d1117"/>'
            # The actual photo, clipped to the circle
            f'<image href="{photo_uri}" '
            f'x="{av_cx-av_r}" y="{av_cy-av_r}" '
            f'width="{av_r*2}" height="{av_r*2}" '
            f'preserveAspectRatio="xMidYMid slice" '
            f'clip-path="url(#avatarClip)"/>'
            # Subtle inner border on top of the photo for depth
            f'<circle cx="{av_cx}" cy="{av_cy}" r="{av_r}" '
            f'fill="none" stroke="#161b22" stroke-width="2"/>'
        )
    else:
        # Fallback to "AB" initials if the photo file is missing
        parts.append(
            f'<circle cx="{av_cx}" cy="{av_cy}" r="{av_r}" '
            f'fill="url(#avatarFill)" stroke="#161b22" stroke-width="2"/>'
            f'<text x="{av_cx}" y="{av_cy+30}" text-anchor="middle" '
            f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
            f'font-size="92" font-weight="900" fill="#e6edf3" letter-spacing="-3">AB</text>'
        )
    # Pulsing availability dot
    dot_x, dot_y = av_cx + 78, av_cy + 78
    parts.append(
        f'<circle cx="{dot_x}" cy="{dot_y}" r="14" fill="#0d1117"/>'
        f'<circle class="avail-dot" cx="{dot_x}" cy="{dot_y}" r="9" '
        f'fill="#39d353" filter="url(#bloom)"/>'
    )

    # ── LEFT panel: "Now shipping" headline + project rows + philosophy ───
    panel_x = 60

    # Headline
    parts.append(
        f'<text x="{panel_x}" y="115" '
        f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
        f'font-size="44" font-weight="900" fill="#ffffff" letter-spacing="-1">'
        f'Now shipping<tspan fill="#39d353"> ·</tspan></text>'
    )
    # Subtitle
    parts.append(
        f'<text x="{panel_x}" y="143" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="14" fill="#7d8590" font-style="italic" letter-spacing="0.3">'
        f'four headline projects with active commits this week</text>'
    )

    # Project rows
    row_y = 168
    row_h = 38
    row_w = 760
    for i, (name, status, blurb) in enumerate(NOW_SHIPPING):
        ry = row_y + i * (row_h + 6)
        # Card
        parts.append(
            f'<rect x="{panel_x}" y="{ry}" width="{row_w}" height="{row_h}" '
            f'rx="6" fill="url(#rowCard)" stroke="#30363d" stroke-width="1"/>'
        )
        # Live dot
        parts.append(
            f'<circle class="live-dot" cx="{panel_x+18}" cy="{ry+row_h//2}" r="5" '
            f'fill="#39d353" filter="url(#bloom)" '
            f'style="animation-delay:-{i*0.4}s"/>'
        )
        # Repo name
        parts.append(
            f'<text x="{panel_x+34}" y="{ry+row_h//2+5}" '
            f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Text,Inter,Segoe UI,sans-serif" '
            f'font-size="15" font-weight="700" fill="#e6edf3">'
            f'{name}</text>'
        )
        # Separator dot
        name_w = len(name) * 8 + 20
        parts.append(
            f'<circle cx="{panel_x+34+name_w}" cy="{ry+row_h//2}" r="2" fill="#7d8590"/>'
        )
        # Blurb
        parts.append(
            f'<text x="{panel_x+34+name_w+10}" y="{ry+row_h//2+5}" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
            f'font-size="13" font-weight="500" fill="#7d8590">'
            f'{blurb}</text>'
        )
        # Status pill (right side)
        parts.append(
            f'<g transform="translate({panel_x+row_w-72}, {ry+8})">'
            f'<rect width="58" height="22" rx="11" fill="#0d2818" '
            f'stroke="#39d353" stroke-width="1"/>'
            f'<text x="29" y="15" text-anchor="middle" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
            f'font-size="10" font-weight="700" fill="#39d353" letter-spacing="1">'
            f'{status.upper()}</text>'
            f'</g>'
        )

    # ── Stats strip (bottom) ──────────────────────────────────────────────
    strip_y = H - 100
    strip_h = 80
    n = len(STATS)
    total_w = W - 120
    tile_w = (total_w - (n - 1) * 16) // n
    for i, (label, value, sub) in enumerate(STATS):
        sx = 60 + i * (tile_w + 16)
        parts.append(
            f'<g>'
            f'<rect x="{sx}" y="{strip_y}" width="{tile_w}" height="{strip_h}" '
            f'rx="12" fill="url(#statTile)" stroke="#30363d" stroke-width="1"/>'
            f'<rect x="{sx}" y="{strip_y}" width="4" height="{strip_h}" '
            f'rx="2" fill="#F90001"/>'
            f'<text x="{sx+24}" y="{strip_y+24}" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
            f'font-size="11" font-weight="700" fill="#7d8590" letter-spacing="2.5">'
            f'{label}</text>'
            f'<text x="{sx+24}" y="{strip_y+58}" '
            f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
            f'font-size="32" font-weight="800" fill="#e6edf3" letter-spacing="-0.5">'
            f'{value}</text>'
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
