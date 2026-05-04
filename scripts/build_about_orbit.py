"""Generate assets/about-orbit.svg — the technologies-orbit footer for About Me.

Pure SVG. Three concentric counter-rotating rings of tech badges around a
central glowing core. Companion piece to about-hero.svg — pairs as
banner+footer for the About Me section.
"""
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "assets" / "about-orbit.svg"

W, H = 1400, 540
CX, CY = W // 2, H // 2

# Three rings of tech badges, each a different radius and rotation speed.
ORBIT = [
    # (label, color, ring_index 0..2, angle_deg)
    # Inner ring — primary stack (clockwise, fastest)
    ("Py",   "#3776ab", 0,    0),
    ("Dj",   "#0c4b33", 0,   60),
    ("DRF",  "#a30000", 0,  120),
    ("Vue",  "#42b883", 0,  180),
    ("Nx",   "#00dc82", 0,  240),
    ("TS",   "#3178c6", 0,  300),
    # Middle ring — data + infra (counter-clockwise)
    ("PG",   "#336791", 1,    0),
    ("MySQL","#00758F", 1,   45),
    ("Rd",   "#dc382d", 1,   90),
    ("Dk",   "#2496ed", 1,  135),
    ("Js",   "#f7df1e", 1,  180),
    ("Tw",   "#06b6d4", 1,  225),
    ("Ng",   "#009639", 1,  270),
    ("Cy",   "#37814A", 1,  315),
    # Outer ring — devops + AI (clockwise, slowest)
    ("AWS",  "#ff9900", 2,    0),
    ("Vrcl", "#000000", 2,   60),
    ("CI",   "#ff652f", 2,  120),
    ("AI",   "#a855f7", 2,  180),
    ("RAG",  "#06b6d4", 2,  240),
    ("CLI",  "#7e57c2", 2,  300),
]

RADII = [120, 200, 290]


def render() -> str:
    rng = random.Random(20260504)
    parts: list[str] = []

    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="Tech stack — orbiting technologies">'
    )

    parts.append('<defs>')

    # Background (deep editorial)
    parts.append(
        '<radialGradient id="bg" cx="50%" cy="50%" r="80%">'
        '<stop offset="0%" stop-color="#1a1f2e"/>'
        '<stop offset="55%" stop-color="#0d1117"/>'
        '<stop offset="100%" stop-color="#02030a"/>'
        '</radialGradient>'
        '<radialGradient id="halo" cx="50%" cy="50%" r="50%">'
        '<stop offset="0%" stop-color="#39d353" stop-opacity="0.20"/>'
        '<stop offset="60%" stop-color="#a855f7" stop-opacity="0.08"/>'
        '<stop offset="100%" stop-color="#06b6d4" stop-opacity="0"/>'
        '</radialGradient>'
        '<linearGradient id="coreGrad" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#F90001"/>'
        '<stop offset="50%" stop-color="#FF652F"/>'
        '<stop offset="100%" stop-color="#a855f7"/>'
        '</linearGradient>'
        '<filter id="bloom" x="-50%" y="-50%" width="200%" height="200%">'
        '<feGaussianBlur stdDeviation="4" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
        '</filter>'
    )

    # Animations — concentric rings rotate at different speeds, breathing core
    parts.append(
        '<style><![CDATA['
        '@keyframes twinkle{0%,100%{opacity:.18}50%{opacity:1}}'
        '@keyframes orbitCW{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}'
        '@keyframes orbitCCW{from{transform:rotate(0deg)}to{transform:rotate(-360deg)}}'
        '@keyframes coreBreathe{0%,100%{opacity:.85;transform:scale(1)}'
        '50%{opacity:1;transform:scale(1.06)}}'
        '@keyframes haloPulse{0%,100%{opacity:.55}50%{opacity:.95}}'
        '.star{animation:twinkle 3.4s ease-in-out infinite}'
        '.star.b{animation-duration:2.1s}'
        '.star.c{animation-duration:5.4s}'
        f'.ring-inner{{transform-origin:{CX}px {CY}px;'
        'animation:orbitCW 28s linear infinite}}'
        f'.ring-mid{{transform-origin:{CX}px {CY}px;'
        'animation:orbitCCW 48s linear infinite}}'
        f'.ring-outer{{transform-origin:{CX}px {CY}px;'
        'animation:orbitCW 80s linear infinite}}'
        f'.core{{transform-origin:{CX}px {CY}px;transform-box:fill-box;'
        'animation:coreBreathe 4s ease-in-out infinite}}'
        '.halo-pulse{animation:haloPulse 4s ease-in-out infinite}'
        ']]></style>'
    )

    parts.append('</defs>')

    # Backdrop
    parts.append(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')
    # Halo behind the city
    parts.append(
        f'<g class="halo-pulse">'
        f'<circle cx="{CX}" cy="{CY}" r="320" fill="url(#halo)"/>'
        f'</g>'
    )

    # Starfield — sparse, professional
    parts.append('<g fill="#e6edf3">')
    star_classes = ['', 'b', 'c']
    for _ in range(70):
        sx = rng.randint(8, W - 8)
        sy = rng.randint(8, H - 8)
        # Avoid placing stars inside the orbit area for clarity
        if abs(sx - CX) < RADII[2] + 30 and abs(sy - CY) < RADII[2] + 30:
            if rng.random() < 0.7:
                continue
        sr = rng.choice([0.4, 0.6, 0.9])
        cls = "star " + rng.choice(star_classes)
        delay = rng.randint(0, 60) / 10
        parts.append(
            f'<circle class="{cls.strip()}" cx="{sx}" cy="{sy}" r="{sr}" '
            f'style="animation-delay:-{delay}s"/>'
        )
    parts.append('</g>')

    # Top-left tag
    parts.append(
        f'<text x="60" y="42" '
        f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
        f'font-size="13" font-weight="700" fill="#39d353" letter-spacing="3.5">'
        f'// THE STACK · v2026.05</text>'
        f'<text x="{W-60}" y="42" text-anchor="end" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="13" font-weight="600" fill="#7d8590" letter-spacing="2">'
        f'orbiting technologies · drag to imagine</text>'
    )

    # Subtitle — section caption
    parts.append(
        f'<text x="{CX}" y="{H-30}" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" '
        f'font-size="14" font-weight="500" fill="#7d8590" font-style="italic" '
        f'letter-spacing="0.5">'
        f'Languages · Frameworks · Data · Infra · DevOps · AI</text>'
    )

    # Concentric guide rings (thin, faint)
    for r in RADII:
        parts.append(
            f'<circle cx="{CX}" cy="{CY}" r="{r}" '
            f'fill="none" stroke="#30363d" stroke-width="0.7" '
            f'stroke-dasharray="2 6" opacity="0.55"/>'
        )

    # Group orbit badges by ring
    rings: dict[int, list[tuple]] = {0: [], 1: [], 2: []}
    for label, color, ring, angle in ORBIT:
        rings[ring].append((label, color, angle))

    ring_class = {0: "ring-inner", 1: "ring-mid", 2: "ring-outer"}

    for ring_idx, items in rings.items():
        r = RADII[ring_idx]
        cls = ring_class[ring_idx]
        parts.append(f'<g class="{cls}">')
        for label, color, angle in items:
            theta = math.radians(angle)
            tx = CX + r * math.cos(theta)
            ty = CY + r * math.sin(theta)
            badge_r = 28 if ring_idx == 0 else (24 if ring_idx == 1 else 22)
            font_size = 14 if len(label) <= 2 else (12 if len(label) <= 3 else 10)
            # Halo
            parts.append(
                f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{badge_r+8}" '
                f'fill="{color}" opacity="0.18" filter="url(#bloom)"/>'
            )
            # Badge body
            parts.append(
                f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{badge_r}" '
                f'fill="#0d1117" stroke="{color}" stroke-width="2.5"/>'
            )
            # Inner glow on the rim
            parts.append(
                f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{badge_r-2}" '
                f'fill="none" stroke="{color}" stroke-width="1" opacity="0.35"/>'
            )
            # Label
            parts.append(
                f'<text x="{tx:.1f}" y="{ty+font_size//3+1:.1f}" text-anchor="middle" '
                f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Text,Inter,Segoe UI,sans-serif" '
                f'font-size="{font_size}" font-weight="800" fill="{color}" '
                f'letter-spacing="0.3">{label}</text>'
            )
        parts.append('</g>')

    # Center core — bigger and more polished than the hero version
    core_r = 72
    parts.append(
        f'<g class="core" filter="url(#bloom)">'
        # Outer glow ring
        f'<circle cx="{CX}" cy="{CY}" r="{core_r+12}" fill="url(#coreGrad)" opacity="0.25"/>'
        # Solid colored ring
        f'<circle cx="{CX}" cy="{CY}" r="{core_r+4}" fill="none" '
        f'stroke="url(#coreGrad)" stroke-width="3"/>'
        # Inner disc
        f'<circle cx="{CX}" cy="{CY}" r="{core_r}" '
        f'fill="#0d1117" stroke="#161b22" stroke-width="2"/>'
        # Bolt symbol
        f'<text x="{CX}" y="{CY+18}" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
        f'font-size="56" font-weight="900" fill="#39d353">⚡</text>'
        # Label under bolt — actually overlaying outside
        f'</g>'
    )

    # Big "AB" mark above the core (hover mark)
    parts.append(
        f'<text x="{CX}" y="{CY-90}" text-anchor="middle" '
        f'font-family="-apple-system,BlinkMacSystemFont,SF Pro Display,Inter,Segoe UI,sans-serif" '
        f'font-size="13" font-weight="700" fill="#7d8590" letter-spacing="3" '
        f'text-transform="uppercase">'
        f'@AbdullahBakir97</text>'
    )

    parts.append('</svg>')
    return "".join(parts)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
