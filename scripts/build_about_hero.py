"""Generate assets/about-hero.svg — a cinematic, animated About-Me banner.

Pure SVG (no foreignObject) so it renders inside GitHub's <img> proxy.
Animation via CSS @keyframes embedded in the SVG.

Layers, back to front:
  1. Sky — radial gradient (deep space → midnight blue at horizon)
  2. Nebula — two soft hue-shifting blobs
  3. Starfield — 80 staggered-twinkle stars
  4. Aurora ribbon — animated translateX wave
  5. Profile card (left) — avatar circle with initials, name, role,
     location with flag, pulsing availability dot, social tags
  6. Tech orbit (right) — three concentric rings (counter-rotating),
     each loaded with tech-logo glyphs at distinct radii
  7. Stats strip (bottom) — years coding · repos shipped · languages
  8. Vignette + foreground particles drifting upward
  9. HUD typography
"""
import datetime as dt
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "assets" / "about-hero.svg"
TODAY = dt.date(2026, 5, 4)

# Stat data — could be wired to live API; keep numeric so they render bold
STATS = [
    ("YEARS CODING",   "5+",       "since 2020"),
    ("REPOS SHIPPED",  "60+",      "across stack"),
    ("LANGUAGES",      "3",        "EN · DE · AR"),
    ("PRIMARY STACK",  "Python",   "Django · Vue · Nuxt"),
]

# Tech orbit — (label, color, ring_index 0..2, angle_deg_at_t0)
ORBIT = [
    # Inner ring (closest, fastest)
    ("Py",      "#3776ab", 0,   0),
    ("Dj",      "#0c4b33", 0,  72),
    ("Vue",     "#42b883", 0, 144),
    ("Nx",      "#00dc82", 0, 216),
    ("TS",      "#3178c6", 0, 288),
    # Middle ring
    ("PG",      "#336791", 1,   0),
    ("Rd",      "#dc382d", 1,  60),
    ("Dk",      "#2496ed", 1, 120),
    ("Js",      "#f7df1e", 1, 180),
    ("Tw",      "#06b6d4", 1, 240),
    ("Ng",      "#009639", 1, 300),
    # Outer ring (slowest, sparser)
    ("AWS",     "#ff9900", 2,   0),
    ("CLI",     "#7e57c2", 2,  90),
    ("CI",      "#ff652f", 2, 180),
    ("AI",      "#a855f7", 2, 270),
]

# Layout
W, H = 1400, 760
CARD_X, CARD_Y = 48, 80
CARD_W, CARD_H = 540, 600
ORBIT_CX = W - 360
ORBIT_CY = H // 2 + 10
RADII = [120, 200, 280]


def rng_for(seed: int) -> random.Random:
    return random.Random(seed)


def render() -> str:
    rng = rng_for(20260504)
    parts: list[str] = []

    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="Abdullah Bakir — Full-Stack Developer">'
    )

    # ── Defs: gradients, filters, animations ───────────────────────────────
    parts.append('<defs>')

    # Sky gradient
    parts.append(
        '<radialGradient id="sky" cx="50%" cy="100%" r="120%">'
        '<stop offset="0%" stop-color="#1a1f3a"/>'
        '<stop offset="35%" stop-color="#0d1230"/>'
        '<stop offset="100%" stop-color="#02030a"/>'
        '</radialGradient>'
    )

    # Nebulae
    parts.append(
        '<radialGradient id="nebA" cx="20%" cy="20%" r="55%">'
        '<stop offset="0%" stop-color="#a855f7" stop-opacity="0.32"/>'
        '<stop offset="100%" stop-color="#a855f7" stop-opacity="0"/>'
        '</radialGradient>'
        '<radialGradient id="nebB" cx="85%" cy="15%" r="50%">'
        '<stop offset="0%" stop-color="#06b6d4" stop-opacity="0.28"/>'
        '<stop offset="100%" stop-color="#06b6d4" stop-opacity="0"/>'
        '</radialGradient>'
        '<radialGradient id="nebC" cx="50%" cy="120%" r="80%">'
        '<stop offset="0%" stop-color="#39d353" stop-opacity="0.20"/>'
        '<stop offset="100%" stop-color="#39d353" stop-opacity="0"/>'
        '</radialGradient>'
    )

    # Aurora ribbon gradient
    parts.append(
        '<linearGradient id="aurora" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0%" stop-color="#39d353" stop-opacity="0"/>'
        '<stop offset="22%" stop-color="#34d399" stop-opacity="0.55"/>'
        '<stop offset="48%" stop-color="#06b6d4" stop-opacity="0.85"/>'
        '<stop offset="72%" stop-color="#a855f7" stop-opacity="0.55"/>'
        '<stop offset="100%" stop-color="#a855f7" stop-opacity="0"/>'
        '</linearGradient>'
    )

    # Profile card glassy background
    parts.append(
        '<linearGradient id="cardGlass" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#161b22" stop-opacity="0.85"/>'
        '<stop offset="100%" stop-color="#0d1117" stop-opacity="0.95"/>'
        '</linearGradient>'
    )

    # Avatar gradient ring
    parts.append(
        '<linearGradient id="avatarRing" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#F90001"/>'
        '<stop offset="50%" stop-color="#FF652F"/>'
        '<stop offset="100%" stop-color="#a855f7"/>'
        '</linearGradient>'
    )

    # Stat-strip card background
    parts.append(
        '<linearGradient id="statCard" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#1c2129" stop-opacity="0.9"/>'
        '<stop offset="100%" stop-color="#0d1117" stop-opacity="0.95"/>'
        '</linearGradient>'
    )

    # Vignette
    parts.append(
        '<radialGradient id="vignette" cx="50%" cy="50%" r="80%">'
        '<stop offset="60%" stop-color="#000" stop-opacity="0"/>'
        '<stop offset="100%" stop-color="#000" stop-opacity="0.55"/>'
        '</radialGradient>'
    )

    # Filters — bloom and soft haze
    parts.append(
        '<filter id="bloom" x="-50%" y="-50%" width="200%" height="200%">'
        '<feGaussianBlur stdDeviation="3" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
        '<filter id="haze" x="-20%" y="-20%" width="140%" height="140%">'
        '<feGaussianBlur stdDeviation="6"/>'
        '</filter>'
    )

    # Animations
    parts.append(
        '<style><![CDATA['
        '@keyframes twinkle{0%,100%{opacity:.18}50%{opacity:1}}'
        '@keyframes auroraWave{0%,100%{transform:translateX(0);opacity:.55}'
        '50%{transform:translateX(28px);opacity:.85}}'
        '@keyframes hueShift{0%,100%{filter:hue-rotate(0deg)}'
        '50%{filter:hue-rotate(35deg)}}'
        '@keyframes pulseDot{0%,100%{transform:scale(1);opacity:1}'
        '50%{transform:scale(1.3);opacity:.55}}'
        '@keyframes pulseRing{0%,100%{opacity:.4;r:7}50%{opacity:.05;r:14}}'
        '@keyframes orbitCW{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}'
        '@keyframes orbitCCW{from{transform:rotate(0deg)}to{transform:rotate(-360deg)}}'
        '@keyframes rise{0%{transform:translateY(20px);opacity:0}'
        '15%{opacity:.85}85%{opacity:.85}'
        f'100%{{transform:translateY(-{H+30}px);opacity:0}}}}'
        '@keyframes fadeIn{from{transform:translateY(8px)}'
        'to{transform:translateY(0)}}'
        '@keyframes typing{0%,40%{width:0}50%,100%{width:100%}}'
        '.star{animation:twinkle 3.4s ease-in-out infinite}'
        '.star.b{animation-duration:2.2s}'
        '.star.c{animation-duration:4.7s}'
        '.star.d{animation-duration:5.6s}'
        '.aurora{animation:auroraWave 11s ease-in-out infinite}'
        '.nebula{animation:hueShift 22s ease-in-out infinite}'
        '.avail-dot{animation:pulseDot 1.6s ease-in-out infinite;'
        'transform-origin:center;transform-box:fill-box}'
        '.avail-ring{animation:pulseRing 1.6s ease-in-out infinite}'
        f'.ring-inner{{transform-origin:{ORBIT_CX}px {ORBIT_CY}px;'
        'animation:orbitCW 28s linear infinite}}'
        f'.ring-mid{{transform-origin:{ORBIT_CX}px {ORBIT_CY}px;'
        'animation:orbitCCW 48s linear infinite}}'
        f'.ring-outer{{transform-origin:{ORBIT_CX}px {ORBIT_CY}px;'
        'animation:orbitCW 80s linear infinite}}'
        '.ember{animation:rise 14s linear infinite}'
        '.ember.b{animation-duration:18s}'
        '.ember.c{animation-duration:11s}'
        '.fade-in{animation:fadeIn 1.4s ease-out both}'
        '.fade-in.d2{animation-delay:0.2s}'
        '.fade-in.d4{animation-delay:0.4s}'
        '.fade-in.d6{animation-delay:0.6s}'
        '.fade-in.d8{animation-delay:0.8s}'
        ']]></style>'
    )

    parts.append('</defs>')

    # ── Backdrop ──────────────────────────────────────────────────────────
    parts.append(f'<rect width="{W}" height="{H}" fill="url(#sky)"/>')

    # Nebulae
    parts.append(
        f'<g class="nebula" filter="url(#haze)">'
        f'<rect width="{W}" height="{H}" fill="url(#nebA)"/>'
        f'<rect width="{W}" height="{H}" fill="url(#nebB)"/>'
        f'<rect width="{W}" height="{H}" fill="url(#nebC)"/>'
        f'</g>'
    )

    # Starfield — 80 staggered stars
    parts.append('<g fill="#e6edf3">')
    classes = ['', 'b', 'c', 'd']
    for _ in range(90):
        sx = rng.randint(8, W - 8)
        sy = rng.randint(8, H - 8)
        sr = rng.choice([0.5, 0.7, 1.0, 1.3])
        cls = "star " + rng.choice(classes)
        delay = rng.randint(0, 60) / 10
        parts.append(
            f'<circle class="{cls.strip()}" cx="{sx}" cy="{sy}" r="{sr}" '
            f'style="animation-delay:-{delay}s"/>'
        )
    parts.append('</g>')

    # Aurora ribbon
    ay = 90
    aurora_d = (
        f"M0,{ay} "
        f"Q{int(W*0.25)},{ay-30} {int(W*0.5)},{ay-8} "
        f"T{W},{ay-22} "
        f"L{W},{ay+34} "
        f"Q{int(W*0.78)},{ay+10} {int(W*0.5)},{ay+30} "
        f"T0,{ay+18} Z"
    )
    parts.append(
        f'<path class="aurora" d="{aurora_d}" fill="url(#aurora)" '
        f'filter="url(#haze)" opacity="0.7"/>'
    )

    # ── Profile card (left) ────────────────────────────────────────────────
    cx, cy, cw, ch = CARD_X, CARD_Y, CARD_W, CARD_H
    parts.append(
        f'<g class="fade-in">'
        f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" '
        f'rx="20" ry="20" fill="url(#cardGlass)" '
        f'stroke="#30363d" stroke-width="1" stroke-opacity="0.9"/>'
        # Inner accent border line
        f'<rect x="{cx+4}" y="{cy+4}" width="{cw-8}" height="{ch-8}" '
        f'rx="16" ry="16" fill="none" '
        f'stroke="#F90001" stroke-width="0.5" stroke-opacity="0.35"/>'
        f'</g>'
    )

    # Avatar circle (initials) — centered horizontally in the card
    av_cx = cx + cw // 2
    av_cy = cy + 120
    av_r = 70
    parts.append(
        f'<g class="fade-in d2">'
        # Outer gradient ring
        f'<circle cx="{av_cx}" cy="{av_cy}" r="{av_r+4}" '
        f'fill="none" stroke="url(#avatarRing)" stroke-width="3"/>'
        # Inner avatar
        f'<circle cx="{av_cx}" cy="{av_cy}" r="{av_r}" '
        f'fill="#0d1117" stroke="#161b22" stroke-width="2"/>'
        # Initials
        f'<text x="{av_cx}" y="{av_cy+18}" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif" '
        f'font-size="56" font-weight="800" fill="#e6edf3">AB</text>'
        f'</g>'
    )

    # Availability indicator (pulsing dot) — placed at bottom-right of avatar
    av_dot_x = av_cx + 52
    av_dot_y = av_cy + 50
    parts.append(
        f'<g class="fade-in d4">'
        # Outer pulse ring
        f'<circle class="avail-ring" cx="{av_dot_x}" cy="{av_dot_y}" r="7" '
        f'fill="none" stroke="#39d353" stroke-width="2"/>'
        # Inner dot
        f'<circle class="avail-dot" cx="{av_dot_x}" cy="{av_dot_y}" r="6" '
        f'fill="#39d353" filter="url(#bloom)"/>'
        # Halo
        f'<circle cx="{av_dot_x}" cy="{av_dot_y}" r="9" '
        f'fill="none" stroke="#0d1117" stroke-width="2"/>'
        f'</g>'
    )

    # Name
    name_y = cy + 230
    parts.append(
        f'<g class="fade-in d2">'
        f'<text x="{cx + cw//2}" y="{name_y}" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Inter,sans-serif" '
        f'font-size="38" font-weight="800" fill="#e6edf3" letter-spacing="0.2">'
        f'Abdullah Bakir</text>'
        # Role tag
        f'<text x="{cx + cw//2}" y="{name_y+30}" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif" '
        f'font-size="14" font-weight="600" fill="#39d353" '
        f'letter-spacing="2.5" text-transform="uppercase">'
        f'Full-Stack Developer</text>'
        f'</g>'
    )

    # Location pill
    loc_y = name_y + 60
    parts.append(
        f'<g class="fade-in d4" transform="translate({cx + cw//2 - 105}, {loc_y})">'
        f'<rect x="0" y="0" width="210" height="32" rx="16" ry="16" '
        f'fill="#161b22" stroke="#30363d" stroke-width="1"/>'
        f'<text x="105" y="22" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif" '
        f'font-size="13" font-weight="500" fill="#c9d1d9">'
        f'🇩🇪 Germany · open to remote</text>'
        f'</g>'
    )

    # Status line
    status_y = loc_y + 56
    parts.append(
        f'<g class="fade-in d4" transform="translate({cx + cw//2 - 90}, {status_y})">'
        f'<circle cx="8" cy="14" r="5" fill="#39d353"/>'
        f'<text x="22" y="19" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif" '
        f'font-size="13" font-weight="600" fill="#39d353">'
        f'Available for collaboration</text>'
        f'</g>'
    )

    # Tagline
    tag_y = status_y + 40
    parts.append(
        f'<g class="fade-in d6">'
        f'<text x="{cx + cw//2}" y="{tag_y}" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif" '
        f'font-size="13" fill="#7d8590" font-style="italic">'
        f'Ship something useful → learn → ship again.</text>'
        f'</g>'
    )

    # Social pills row
    social_y = tag_y + 40
    socials = [
        ("@AbdullahBakir97", "#F90001"),
        ("LinkedIn", "#0a66c2"),
        ("Telegram", "#26a5e4"),
    ]
    pill_w = 145
    pill_gap = 12
    total_w = len(socials) * pill_w + (len(socials) - 1) * pill_gap
    start_x = cx + (cw - total_w) // 2
    for i, (label, color) in enumerate(socials):
        px = start_x + i * (pill_w + pill_gap)
        parts.append(
            f'<g class="fade-in d8" transform="translate({px}, {social_y})">'
            f'<rect width="{pill_w}" height="34" rx="17" ry="17" '
            f'fill="{color}" opacity="0.92"/>'
            f'<text x="{pill_w//2}" y="22" text-anchor="middle" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif" '
            f'font-size="12" font-weight="600" fill="#ffffff" letter-spacing="0.4">'
            f'{label}</text>'
            f'</g>'
        )

    # ── Tech orbit (right) ─────────────────────────────────────────────────

    # Concentric guide rings (subtle)
    for r in RADII:
        parts.append(
            f'<circle cx="{ORBIT_CX}" cy="{ORBIT_CY}" r="{r}" '
            f'fill="none" stroke="#30363d" stroke-width="0.6" opacity="0.45"/>'
        )

    # Center "core" — pulsing logo
    parts.append(
        f'<g class="fade-in d2">'
        f'<circle cx="{ORBIT_CX}" cy="{ORBIT_CY}" r="58" '
        f'fill="#0d1117" stroke="url(#avatarRing)" stroke-width="2.5" '
        f'filter="url(#bloom)"/>'
        f'<text x="{ORBIT_CX}" y="{ORBIT_CY+10}" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="32" font-weight="900" fill="#39d353">⚡</text>'
        f'</g>'
    )

    # Orbiting tech badges — group per ring so the whole ring rotates together
    rings: dict[int, list[tuple]] = {0: [], 1: [], 2: []}
    for label, color, ring, angle in ORBIT:
        rings.setdefault(ring, []).append((label, color, angle))

    ring_class = {0: "ring-inner", 1: "ring-mid", 2: "ring-outer"}
    for ring_idx, items in rings.items():
        r = RADII[ring_idx]
        cls = ring_class[ring_idx]
        parts.append(f'<g class="{cls} fade-in d4">')
        for label, color, angle in items:
            theta = math.radians(angle)
            tx = ORBIT_CX + r * math.cos(theta)
            ty = ORBIT_CY + r * math.sin(theta)
            badge_r = 22 if ring_idx == 0 else 19
            parts.append(
                # Outer halo
                f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{badge_r+5}" '
                f'fill="{color}" opacity="0.18" filter="url(#bloom)"/>'
                # Badge
                f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{badge_r}" '
                f'fill="#0d1117" stroke="{color}" stroke-width="2"/>'
                # Label
                f'<text x="{tx:.1f}" y="{ty+5:.1f}" text-anchor="middle" '
                f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif" '
                f'font-size="{11 if len(label) > 2 else 13}" font-weight="700" '
                f'fill="{color}">{label}</text>'
            )
        parts.append('</g>')

    # ── Stats strip (bottom) ──────────────────────────────────────────────
    stat_h = 90
    stat_y = H - stat_h - 30
    n_stats = len(STATS)
    stat_w_total = W - 96
    stat_card_w = (stat_w_total - (n_stats - 1) * 16) // n_stats
    for i, (label, value, sub) in enumerate(STATS):
        sx = 48 + i * (stat_card_w + 16)
        parts.append(
            f'<g class="fade-in d6">'
            f'<rect x="{sx}" y="{stat_y}" width="{stat_card_w}" height="{stat_h}" '
            f'rx="14" ry="14" fill="url(#statCard)" '
            f'stroke="#30363d" stroke-width="1"/>'
            # Accent line
            f'<rect x="{sx+18}" y="{stat_y+12}" width="3" height="{stat_h-24}" '
            f'rx="1.5" fill="#F90001"/>'
            f'<text x="{sx + stat_card_w//2 + 12}" y="{stat_y+34}" '
            f'text-anchor="middle" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif" '
            f'font-size="10" font-weight="700" fill="#7d8590" letter-spacing="2">'
            f'{label}</text>'
            f'<text x="{sx + stat_card_w//2 + 12}" y="{stat_y+62}" '
            f'text-anchor="middle" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Inter,sans-serif" '
            f'font-size="26" font-weight="800" fill="#e6edf3">'
            f'{value}</text>'
            f'<text x="{sx + stat_card_w//2 + 12}" y="{stat_y+80}" '
            f'text-anchor="middle" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif" '
            f'font-size="10" fill="#7d8590">{sub}</text>'
            f'</g>'
        )

    # ── Foreground particles ──────────────────────────────────────────────
    parts.append('<g class="embers">')
    ember_classes = ['', 'b', 'c']
    for _ in range(18):
        ex = rng.randint(20, W - 20)
        ey = rng.randint(stat_y + 20, H - 20)
        cls = "ember " + rng.choice(ember_classes)
        col = rng.choice(["#7ee787", "#39d353", "#a7f3d0", "#bae6fd"])
        delay = rng.randint(0, 200) / 10
        parts.append(
            f'<circle class="{cls.strip()}" cx="{ex}" cy="{ey}" r="1.4" '
            f'fill="{col}" filter="url(#bloom)" '
            f'style="animation-delay:-{delay}s"/>'
        )
    parts.append('</g>')

    # Vignette overlay
    parts.append(f'<rect width="{W}" height="{H}" fill="url(#vignette)" pointer-events="none"/>')

    # Ghost background "ABDULLAH" wordmark
    parts.append(
        f'<text x="{W - 40}" y="58" text-anchor="end" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Inter,sans-serif" '
        f'font-size="14" font-weight="700" fill="#39d353" '
        f'letter-spacing="3" opacity="0.7">// ABOUT.SVG · v2026.05</text>'
    )

    parts.append('</svg>')
    return "".join(parts)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
