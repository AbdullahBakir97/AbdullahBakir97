"""Build the anatomical neon-brain skill atlas SVG.

Pipeline:
  1. Fetch https://upload.wikimedia.org/wikipedia/commons/3/33/Human-brain.SVG
     (Hugh Guiney, CC-BY-SA-3.0 — 200 anatomical paths).
  2. Extract just the <g id="brain"> content.
  3. Recolor every fill/stroke to a neon palette.
  4. Embed inside a hand-crafted wrapper SVG (1400×900) with:
       • Animated multi-stop gradient (color-wave flow + axis rotation)
       • Atmospheric background (dark space + dot grid + stars)
       • Title with letter-spaced caption
       • 6 anatomical labels with thin leader lines pointing to specific lobes
       • Soft drop shadow + glow on the brain itself
  5. Save to assets/brain-anatomical.svg ready for README use.

Usage:
    python scripts/build_anatomical_brain.py
"""
from __future__ import annotations

import os
import re
import sys
import urllib.request

SOURCE_URL = "https://upload.wikimedia.org/wikipedia/commons/3/33/Human-brain.SVG"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.dirname(SCRIPT_DIR)
OUTPUT_FILE = os.path.join(REPO_ROOT, "assets", "brain-anatomical.svg")
DOCS_FILE   = os.path.join(REPO_ROOT, "docs", "brain.svg")
CACHE_FILE  = "/tmp/wiki-brain.svg"

FILL_REPLACEMENTS = {
    "#fff0cd": "url(#brainGrad)",
    "#fdd99b": "url(#brainGrad)",
    "#d9bb7a": "url(#brainGradAlt)",
    "#ffffff": "url(#brainGrad)",
    "#816647": "url(#brainGradAlt)",
}
STROKE_REPLACEMENTS = {
    "#816647": "#EC4899",
    "#000000": "#7C3AED",
}


def fetch_source() -> str:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            return f.read()
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "AbdullahReadme/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read().decode("utf-8")
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    return content


def extract_brain_group(svg: str) -> str:
    """Pull the <g id="brain">...</g> block intact via bracket-balanced search."""
    # Find the opening <g id="brain"> tag
    m = re.search(r'<g\b[^>]*?id="brain"[^>]*?>', svg, re.DOTALL)
    if not m:
        raise RuntimeError("Couldn't find <g id=\"brain\"> in source SVG")
    start = m.start()
    pos = m.end()

    # Walk forward, counting nested <g> opens and </g> closes until balanced.
    depth = 1
    while depth > 0 and pos < len(svg):
        next_open  = svg.find("<g", pos)
        next_close = svg.find("</g>", pos)
        if next_close == -1:
            raise RuntimeError("Unbalanced <g> tags in source SVG")
        # Only count <g followed by space/newline/> (not <gradient or similar).
        if next_open != -1 and next_open < next_close:
            after = svg[next_open + 2:next_open + 3]
            if after in (" ", ">", "\n", "\t", "\r"):
                depth += 1
            pos = next_open + 2
        else:
            depth -= 1
            pos = next_close + 4
    return svg[start:pos]


def recolor_brain_content(content: str) -> str:
    for old, new in FILL_REPLACEMENTS.items():
        for variant in (old, old.upper(), old.lower()):
            content = content.replace(f"fill:{variant}", f"fill:{new}")
    for old, new in STROKE_REPLACEMENTS.items():
        for variant in (old, old.upper(), old.lower()):
            content = content.replace(f"stroke:{variant}", f"stroke:{new}")
    return content


# Wrapper SVG template: brain content goes between {{BRAIN_CONTENT}} markers.
# Brain native viewBox is 1024×732. We translate it to (188,170) and scale to 0.6
# so the brain occupies roughly (188,170) → (802,609) in our 1400×900 canvas.
# That leaves room for labels around the brain.
TEMPLATE = r"""<?xml version="1.0" encoding="UTF-8"?>
<!--
  Neural Skill Atlas — anatomical neon brain (Wikimedia, CC-BY-SA-3.0 by Hugh Guiney)
  recolored + composed by Abdullah Bakir's profile-build pipeline.
  Source: https://commons.wikimedia.org/wiki/File:Human-brain.SVG
-->
<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="900" viewBox="0 0 1400 900" role="img" aria-label="Neural Skill Atlas">
  <defs>
    <!-- ═══ ANIMATED MULTI-STOP GRADIENT ═══
         Each stop cycles through the palette over 12s, offset by one position
         in the rotation so the color wave flows continuously through the brain.
         Combined with gradient-axis rotation for double dynamism. -->
    <linearGradient id="brainGrad" x1="0" y1="0.05" x2="1" y2="0.95" gradientUnits="objectBoundingBox">
      <animateTransform attributeName="gradientTransform" type="rotate"
                        from="0 0.5 0.5" to="360 0.5 0.5" dur="22s" repeatCount="indefinite"/>
      <stop offset="0%"   stop-color="#22D3EE">
        <animate attributeName="stop-color"
                 values="#22D3EE;#7C3AED;#EC4899;#FF652F;#F90001;#22D3EE"
                 dur="12s" repeatCount="indefinite"/>
      </stop>
      <stop offset="25%"  stop-color="#7C3AED">
        <animate attributeName="stop-color"
                 values="#7C3AED;#EC4899;#FF652F;#F90001;#22D3EE;#7C3AED"
                 dur="12s" repeatCount="indefinite"/>
      </stop>
      <stop offset="50%"  stop-color="#EC4899">
        <animate attributeName="stop-color"
                 values="#EC4899;#FF652F;#F90001;#22D3EE;#7C3AED;#EC4899"
                 dur="12s" repeatCount="indefinite"/>
      </stop>
      <stop offset="75%"  stop-color="#FF652F">
        <animate attributeName="stop-color"
                 values="#FF652F;#F90001;#22D3EE;#7C3AED;#EC4899;#FF652F"
                 dur="12s" repeatCount="indefinite"/>
      </stop>
      <stop offset="100%" stop-color="#F90001">
        <animate attributeName="stop-color"
                 values="#F90001;#22D3EE;#7C3AED;#EC4899;#FF652F;#F90001"
                 dur="12s" repeatCount="indefinite"/>
      </stop>
    </linearGradient>

    <linearGradient id="brainGradAlt" x1="0" y1="0" x2="1" y2="1" gradientUnits="objectBoundingBox">
      <animateTransform attributeName="gradientTransform" type="rotate"
                        from="0 0.5 0.5" to="-360 0.5 0.5" dur="28s" repeatCount="indefinite"/>
      <stop offset="0%"   stop-color="#7C3AED">
        <animate attributeName="stop-color"
                 values="#7C3AED;#EC4899;#FF652F;#7C3AED" dur="14s" repeatCount="indefinite"/>
      </stop>
      <stop offset="50%"  stop-color="#EC4899">
        <animate attributeName="stop-color"
                 values="#EC4899;#FF652F;#7C3AED;#EC4899" dur="14s" repeatCount="indefinite"/>
      </stop>
      <stop offset="100%" stop-color="#FF652F">
        <animate attributeName="stop-color"
                 values="#FF652F;#7C3AED;#EC4899;#FF652F" dur="14s" repeatCount="indefinite"/>
      </stop>
    </linearGradient>

    <radialGradient id="bgRadial" cx="50%" cy="50%" r="80%">
      <stop offset="0%"   stop-color="#180826"/>
      <stop offset="60%"  stop-color="#080410"/>
      <stop offset="100%" stop-color="#000000"/>
    </radialGradient>

    <radialGradient id="brainAura" cx="50%" cy="50%" r="55%">
      <stop offset="0%"   stop-color="#EC4899" stop-opacity="0.30"/>
      <stop offset="55%"  stop-color="#7C3AED" stop-opacity="0.10"/>
      <stop offset="100%" stop-color="#7C3AED" stop-opacity="0"/>
    </radialGradient>

    <linearGradient id="cardBg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#1C1428" stop-opacity="0.94"/>
      <stop offset="100%" stop-color="#0A0612" stop-opacity="0.94"/>
    </linearGradient>

    <pattern id="dotGrid" x="0" y="0" width="26" height="26" patternUnits="userSpaceOnUse">
      <circle cx="2" cy="2" r="0.7" fill="#F90001" fill-opacity="0.07"/>
    </pattern>

    <filter id="cardShadow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="5"/>
      <feOffset dx="0" dy="3" result="shadow"/>
      <feFlood flood-color="#000000" flood-opacity="0.7"/>
      <feComposite in2="shadow" operator="in"/>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>

    <filter id="brainGlow" x="-15%" y="-15%" width="130%" height="130%">
      <feGaussianBlur stdDeviation="2" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <style><![CDATA[
      .t-display { font-family: 'Inter','SF Pro Display','Segoe UI',sans-serif; font-weight: 800; font-size: 30px; letter-spacing: -0.01em; fill: #FFFFFF; }
      .t-tag     { font-family: 'Inter','SF Pro Display','Segoe UI',sans-serif; font-weight: 600; font-size: 11px; letter-spacing: 0.30em; text-transform: uppercase; fill: #C4B5FD; }
      .t-cap     { font-family: 'Inter','SF Pro Display','Segoe UI',sans-serif; font-weight: 600; font-size: 9px; letter-spacing: 0.22em; text-transform: uppercase; }
      .t-region  { font-family: 'Inter','SF Pro Display','Segoe UI',sans-serif; font-weight: 700; font-size: 14px; fill: #FFFFFF; }
      .t-skill   { font-family: 'JetBrains Mono','SF Mono',Consolas,monospace; font-weight: 500; font-size: 10px; fill: #D1D5DB; }

      .brain-pulse {
        animation: brainPulse 5s ease-in-out infinite;
        transform-origin: center;
        transform-box: fill-box;
      }
      @keyframes brainPulse {
        0%, 100% { filter: drop-shadow(0 0 16px rgba(236,72,153,0.45)); }
        50%      { filter: drop-shadow(0 0 32px rgba(236,72,153,0.85)); }
      }

      /* 3D Y-axis rotation simulation via scaleX squeeze + skew wobble.
         16s cycle. The brain "turns" subtly as if on a 3D pedestal. */
      .brain-3d {
        animation: brain3d 16s ease-in-out infinite;
        transform-origin: center;
        transform-box: fill-box;
      }
      @keyframes brain3d {
        0%, 100% { transform: perspective(1200px) scaleX(1)    skewY(0deg); }
        25%      { transform: perspective(1200px) scaleX(0.92) skewY(-1.5deg); }
        50%      { transform: perspective(1200px) scaleX(0.82) skewY(0deg); }
        75%      { transform: perspective(1200px) scaleX(0.92) skewY(1.5deg); }
      }

      .leader-flow {
        stroke-dasharray: 4 6;
        animation: leaderFlow 1.6s linear infinite;
      }
      @keyframes leaderFlow { to { stroke-dashoffset: -20; } }

      .target-pulse { animation: targetPulse 1.6s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
      @keyframes targetPulse {
        0%, 100% { transform: scale(1);   opacity: 0.85; }
        50%      { transform: scale(1.5); opacity: 1; }
      }

      .label-fade {
        opacity: 0;
        animation: labelFade 0.8s cubic-bezier(0.22,1,0.36,1) forwards;
      }
      @keyframes labelFade { to { opacity: 1; } }
      .lf1{animation-delay:0.4s} .lf2{animation-delay:0.55s} .lf3{animation-delay:0.7s}
      .lf4{animation-delay:0.85s} .lf5{animation-delay:1.0s} .lf6{animation-delay:1.15s}

      .twinkle { animation: twinkle 2.4s ease-in-out infinite; }
      @keyframes twinkle { 0%,100%{opacity:0.2} 50%{opacity:0.85} }
    ]]></style>
  </defs>

  <!-- ═══ BACKGROUND ═══ -->
  <rect width="1400" height="900" fill="url(#bgRadial)"/>
  <rect width="1400" height="900" fill="url(#dotGrid)"/>

  <!-- Sparse stars -->
  <g fill="#FFFFFF">
    <circle cx="80"   cy="120" r="0.8" class="twinkle" style="animation-delay:0.1s"/>
    <circle cx="220"  cy="80"  r="1.0" class="twinkle" style="animation-delay:0.5s"/>
    <circle cx="380"  cy="50"  r="0.7" class="twinkle" style="animation-delay:1.2s"/>
    <circle cx="540"  cy="40"  r="0.9" class="twinkle" style="animation-delay:0.3s"/>
    <circle cx="780"  cy="60"  r="1.1" class="twinkle" style="animation-delay:0.8s"/>
    <circle cx="940"  cy="40"  r="0.6" class="twinkle" style="animation-delay:2.0s"/>
    <circle cx="1110" cy="90"  r="0.8" class="twinkle" style="animation-delay:1.5s"/>
    <circle cx="1320" cy="140" r="0.9" class="twinkle" style="animation-delay:0.7s"/>
    <circle cx="60"   cy="350" r="0.7" class="twinkle" style="animation-delay:1.4s"/>
    <circle cx="1340" cy="350" r="0.9" class="twinkle" style="animation-delay:0.6s"/>
    <circle cx="100"  cy="700" r="0.8" class="twinkle" style="animation-delay:1.8s"/>
    <circle cx="1300" cy="700" r="0.7" class="twinkle" style="animation-delay:1.0s"/>
    <circle cx="500"  cy="780" r="0.9" class="twinkle" style="animation-delay:0.4s"/>
    <circle cx="900"  cy="780" r="0.8" class="twinkle" style="animation-delay:1.6s"/>
  </g>

  <!-- Brain aura halo -->
  <ellipse cx="700" cy="440" rx="430" ry="320" fill="url(#brainAura)"/>

  <!-- ═══ TITLE ═══ -->
  <text x="700" y="50" class="t-tag" text-anchor="middle">⏵ NEURAL · SKILL · ATLAS · v1.0 ⏴</text>
  <text x="700" y="86" class="t-display" text-anchor="middle">Abdullah's Skill Brain</text>

  <!-- ═══ LEADER LINES (drawn behind brain so they appear to emerge) ═══ -->
  <g fill="none" stroke-width="1.2" stroke-opacity="0.7">
    <!-- Frontal → Backend (top-right) -->
    <path d="M 1170,180 L 1010,250 L 850,310" stroke="#F90001" class="leader-flow"/>
    <!-- Parietal → Architecture (top-center, inside brain top region) -->
    <path d="M 700,150 L 700,200 L 700,260" stroke="#34D399" class="leader-flow"/>
    <!-- Occipital → Frontend (top-left, points to back-of-brain occipital region) -->
    <path d="M 230,180 L 360,250 L 480,300" stroke="#FF652F" class="leader-flow"/>
    <!-- Temporal → Data Layer (mid-right) -->
    <path d="M 1170,500 L 1000,500 L 830,500" stroke="#FFD23F" class="leader-flow"/>
    <!-- Cerebellum → DevOps (bot-left of brain, lower-back lobe) -->
    <path d="M 230,720 L 380,640 L 470,600" stroke="#22D3EE" class="leader-flow"/>
    <!-- Brainstem → AI (bot-right) -->
    <path d="M 1170,720 L 980,680 L 760,620" stroke="#A78BFA" class="leader-flow"/>
  </g>

  <!-- Target dots at brain endpoints (pulsing) -->
  <g>
    <circle cx="850" cy="310" r="4" fill="#F90001" class="target-pulse"/>
    <circle cx="700" cy="260" r="4" fill="#34D399" class="target-pulse" style="animation-delay:0.3s"/>
    <circle cx="480" cy="300" r="4" fill="#FF652F" class="target-pulse" style="animation-delay:0.6s"/>
    <circle cx="830" cy="500" r="4" fill="#FFD23F" class="target-pulse" style="animation-delay:0.9s"/>
    <circle cx="470" cy="600" r="4" fill="#22D3EE" class="target-pulse" style="animation-delay:1.2s"/>
    <circle cx="760" cy="620" r="4" fill="#A78BFA" class="target-pulse" style="animation-delay:1.5s"/>
  </g>

  <!-- ═══ THE BRAIN (Wikimedia anatomical, recolored, properly centered, 3D-rotating) ═══
       Brain native viewBox 1024×732. Native bbox center ≈ (525,425).
       Scale 0.7 → bbox 717×512, center after scale ≈ (368,298).
       To put center at canvas (700,450): translate (700-368, 450-298) = (332,152).

       Layered transforms:
         outer  = SVG positioning (translate + scale) — never animated, pure attribute
         middle = .brain-pulse  — drop-shadow breathing (filter only)
         inner  = .brain-3d     — scaleX/skewY 3D wobble (transform animation)
       Nesting prevents CSS transform from overriding the outer SVG transform. -->
  <g transform="translate(332,152) scale(0.7)">
    <g class="brain-pulse" filter="url(#brainGlow)">
      <g class="brain-3d">
{{BRAIN_CONTENT}}
      </g>
    </g>
  </g>

  <!-- ═══ ANATOMICAL LABELS ═══
       Each label = small card at canvas edge, content describes the lobe + skill domain.
       Leader line connects each label to its target brain region (drawn earlier). -->

  <!-- TOP-RIGHT: Frontal lobe → Backend -->
  <g transform="translate(1180,150)">
    <g class="label-fade lf1">
      <rect x="0" y="0" width="200" height="80" rx="10" fill="url(#cardBg)" stroke="#F90001" stroke-width="1.5" filter="url(#cardShadow)"/>
      <rect x="0" y="0" width="5"   height="80" rx="2" fill="#F90001"/>
      <text x="100" y="20" class="t-cap" text-anchor="middle" fill="#F90001">FRONTAL · LOBE</text>
      <text x="100" y="44" class="t-region" text-anchor="middle">⚙️ Backend</text>
      <text x="100" y="64" class="t-skill" text-anchor="middle">Logic · APIs · Server</text>
    </g>
  </g>

  <!-- TOP-CENTER: Parietal → Architecture -->
  <g transform="translate(600,90)">
    <g class="label-fade lf2">
      <rect x="0" y="0" width="200" height="80" rx="10" fill="url(#cardBg)" stroke="#34D399" stroke-width="1.5" filter="url(#cardShadow)"/>
      <rect x="0" y="0" width="5"   height="80" rx="2" fill="#34D399"/>
      <text x="100" y="20" class="t-cap" text-anchor="middle" fill="#34D399">PARIETAL · LOBE</text>
      <text x="100" y="44" class="t-region" text-anchor="middle">🏗️ Architecture</text>
      <text x="100" y="64" class="t-skill" text-anchor="middle">Integration · Design</text>
    </g>
  </g>

  <!-- TOP-LEFT: Occipital → Frontend -->
  <g transform="translate(20,150)">
    <g class="label-fade lf3">
      <rect x="0" y="0" width="200" height="80" rx="10" fill="url(#cardBg)" stroke="#FF652F" stroke-width="1.5" filter="url(#cardShadow)"/>
      <rect x="0" y="0" width="5"   height="80" rx="2" fill="#FF652F"/>
      <text x="100" y="20" class="t-cap" text-anchor="middle" fill="#FF652F">OCCIPITAL · LOBE</text>
      <text x="100" y="44" class="t-region" text-anchor="middle">🎨 Frontend</text>
      <text x="100" y="64" class="t-skill" text-anchor="middle">Visual · UI · UX</text>
    </g>
  </g>

  <!-- MID-RIGHT: Temporal → Data Layer -->
  <g transform="translate(1180,470)">
    <g class="label-fade lf4">
      <rect x="0" y="0" width="200" height="80" rx="10" fill="url(#cardBg)" stroke="#FFD23F" stroke-width="1.5" filter="url(#cardShadow)"/>
      <rect x="0" y="0" width="5"   height="80" rx="2" fill="#FFD23F"/>
      <text x="100" y="20" class="t-cap" text-anchor="middle" fill="#FFD23F">TEMPORAL · LOBE</text>
      <text x="100" y="44" class="t-region" text-anchor="middle">💾 Data Layer</text>
      <text x="100" y="64" class="t-skill" text-anchor="middle">Memory · State · Cache</text>
    </g>
  </g>

  <!-- BOT-LEFT: Cerebellum → DevOps -->
  <g transform="translate(20,690)">
    <g class="label-fade lf5">
      <rect x="0" y="0" width="200" height="80" rx="10" fill="url(#cardBg)" stroke="#22D3EE" stroke-width="1.5" filter="url(#cardShadow)"/>
      <rect x="0" y="0" width="5"   height="80" rx="2" fill="#22D3EE"/>
      <text x="100" y="20" class="t-cap" text-anchor="middle" fill="#22D3EE">CEREBELLUM</text>
      <text x="100" y="44" class="t-region" text-anchor="middle">🛠️ DevOps</text>
      <text x="100" y="64" class="t-skill" text-anchor="middle">Coordination · CI/CD</text>
    </g>
  </g>

  <!-- BOT-RIGHT: Brainstem → AI -->
  <g transform="translate(1180,690)">
    <g class="label-fade lf6">
      <rect x="0" y="0" width="200" height="80" rx="10" fill="url(#cardBg)" stroke="#A78BFA" stroke-width="1.5" filter="url(#cardShadow)"/>
      <rect x="0" y="0" width="5"   height="80" rx="2" fill="#A78BFA"/>
      <text x="100" y="20" class="t-cap" text-anchor="middle" fill="#A78BFA">BRAINSTEM</text>
      <text x="100" y="44" class="t-region" text-anchor="middle">🤖 AI &amp; Data</text>
      <text x="100" y="64" class="t-skill" text-anchor="middle">Foundation · LLMs · RAG</text>
    </g>
  </g>
</svg>
"""


def main() -> int:
    print(f"[*] Fetching {SOURCE_URL}")
    src = fetch_source()
    print(f"    ({len(src):,} chars, {src.count('<path'):,} paths)")

    print("[*] Extracting brain group...")
    brain_content = extract_brain_group(src)
    # Sanity check: parses balanced
    o = brain_content.count("<g") - brain_content.count("<gradient")  # discount <gradient...
    c = brain_content.count("</g>")
    print(f"    extracted {len(brain_content):,} chars; <g> opens={o}, </g> closes={c}")
    assert o == c, f"unbalanced tags in extracted brain content: {o} opens, {c} closes"

    print("[*] Recoloring with neon palette...")
    brain_content = recolor_brain_content(brain_content)

    print("[*] Composing wrapper SVG with labels and animations...")
    # Insert brain content as-is (with its outer <g id="brain"> intact, since
    # our wrapper group adds a separate translate/scale group around it).
    out = TEMPLATE.replace("{{BRAIN_CONTENT}}", brain_content)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"[OK] Wrote {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE):,} bytes)")

    # Also copy the raw brain (without our wrapper composition) for the
    # Three.js viewer in /docs — that one only wants the brain paths.
    if os.path.exists(os.path.dirname(DOCS_FILE)):
        # For Three.js, ship a simpler version: just the brain group inside <svg>.
        # Three.js SVGLoader extrudes paths so it doesn't need our wrapper UI.
        simple = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'width="1024" height="731" viewBox="0 0 1024 732">\n'
            + brain_content
            + "\n</svg>\n"
        )
        with open(DOCS_FILE, "w", encoding="utf-8") as f:
            f.write(simple)
        print(f"[OK] Wrote {DOCS_FILE} ({os.path.getsize(DOCS_FILE):,} bytes)")

    print()
    print("[ATTRIBUTION REQUIRED]")
    print("  Original: Hugh Guiney, CC-BY-SA-3.0")
    print("  https://commons.wikimedia.org/wiki/File:Human-brain.SVG")
    return 0


if __name__ == "__main__":
    sys.exit(main())
