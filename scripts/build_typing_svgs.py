"""Generate the cycling-line typing SVGs.

For each SVG, takes a list of (text, color) lines and produces an SVG where each
line types in / holds / erases / waits, then hands off to the next.

Cycle math (uniform per line):
  total cycle  = N lines × seconds_per_line
  per-line phase distribution:
    type   12% of window
    hold   62% of window
    erase  10% of window
    off    16% of window  (so a brief gap between lines)

Outputs:
  assets/about-typing.svg   (30 terminal commands)
  assets/motto-typing.svg   (30 philosophy mottos)
"""
from __future__ import annotations

import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.dirname(SCRIPT_DIR)


# ── ABOUT (terminal commands) — 30 lines, 60s cycle, 2s per line ─────────────
ABOUT_LINES = [
    ("$ whoami",                                       "#00C853"),  # green: terminal prompt
    ("$ pwd",                                          "#22D3EE"),  # cyan: location
    ("$ cat about.py",                                 "#FF652F"),  # orange: file path
    ("$ ls projects/",                                 "#EC4899"),  # magenta: listing
    ("$ git status",                                   "#F90001"),  # red: state check
    ("$ history | head",                               "#A78BFA"),  # purple: past commands
    ("$ uptime",                                       "#34D399"),  # green: system info
    ("$ cat skills.json",                              "#FFD700"),  # gold: skills metadata
    ("$ python --version",                             "#00C853"),  # green: tool version
    ("$ tree -L 1",                                    "#22D3EE"),  # cyan: structure
    ("$ docker ps",                                    "#FF652F"),  # orange: containers
    ("$ git log --oneline | head -3",                  "#EC4899"),  # magenta: recent commits
    ("$ stack list",                                   "#F90001"),  # red: tech stack
    ("$ npm list -g --depth=0",                        "#A78BFA"),  # purple: globals
    ("$ which python",                                 "#34D399"),  # green: locate
    ("$ ls -la ~/code",                                "#FFD700"),  # gold: workspace
    ("$ pytest -q",                                    "#00C853"),  # green: test
    ("$ make build",                                   "#22D3EE"),  # cyan: build
    ("$ curl api.github.com/users/AbdullahBakir97",    "#FF652F"),  # orange: api call
    ("$ docker compose up -d",                         "#EC4899"),  # magenta: orchestrate
    ("$ tmux attach",                                  "#F90001"),  # red: session
    ("$ vim ~/.config/me",                             "#A78BFA"),  # purple: edit
    ("$ echo $LANG",                                   "#34D399"),  # green: env
    ("$ ssh prod -t htop",                             "#FFD700"),  # gold: monitor
    ("$ ps aux | grep python",                         "#00C853"),  # green: processes
    ("$ git push origin main",                         "#22D3EE"),  # cyan: deploy
    ("$ tail -f /var/log/app.log",                     "#FF652F"),  # orange: logs
    ("$ man developer",                                "#EC4899"),  # magenta: meta
    ("$ exit 0",                                       "#A78BFA"),  # purple: clean exit
    ("# open to collab",                               "#FFD700"),  # gold: comment
    # ─── 20 personal lines: actual projects, daily commands, Abdullah's work ─
    ("$ cd ~/projects/baeckrei && make dev",           "#34D399"),  # bakery dev mode
    ("$ python -m pydev create my-app",                "#F90001"),  # PyDev platform
    ("$ stock-manager --inventory --low-stock",        "#FFD700"),  # Stock-Manager
    ("$ python -m issue_triage_bot run",               "#A78BFA"),  # GitHub App
    ("$ python -m pr_coach review",                    "#22D3EE"),  # GitHub App
    ("$ python -m commit_craft check HEAD",            "#FF652F"),  # GitHub App
    ("$ python -m repodoc_ai generate",                "#EC4899"),  # GitHub App
    ("$ python -m ai_quality_gate scan",               "#00C853"),  # GitHub App
    ("$ docker compose -f baeckrei.yml up -d",         "#FFD700"),  # bakery prod
    ("$ deploy.sh barber-salon-prod",                  "#F90001"),  # client deploy
    ("$ tail -f /var/log/baeckrei.log",                "#34D399"),  # monitoring
    ("$ npx nuxt build && npx nuxt start",             "#22D3EE"),  # Vue/Nuxt
    ("$ python manage.py migrate baeckrei",            "#A78BFA"),  # Django migration
    ("$ rabbitmq-plugins enable rabbitmq_management",  "#FF652F"),  # RabbitMQ
    ("$ ssh tawil-media-prod",                         "#EC4899"),  # client server
    ("$ git checkout -b feature/recipe-scheduler",     "#00C853"),  # branch
    ("$ pytest baeckrei/tests/test_orders.py -v",      "#FFD700"),  # test
    ("$ gh extension install AbdullahBakir97/pydev",   "#F90001"),  # PyDev install
    ("$ python -c 'import abdullah; help(abdullah)'",  "#A78BFA"),  # meta
    ("# made in Germany, for small shops worldwide",   "#22D3EE"),  # signature
]

# ── MOTTO (dev philosophy quotes) — 30 lines, 90s cycle, 3s per line ─────────
MOTTO_LINES = [
    ("// Curious about how systems break",                          "#FF652F"),
    ("// Stubborn about how they're rebuilt",                       "#F90001"),
    ("// Code should be useful before it's clever",                 "#FFD700"),
    ("// Boring architecture is usually the right one",             "#34D399"),
    ("// Tests are letters from past me to future me",              "#A78BFA"),
    ("// A good name is half the documentation",                    "#22D3EE"),
    ("// Ship -> measure -> learn -> ship again",                   "#EC4899"),
    ("// The simplest thing that could possibly work",              "#00C853"),
    ("// Read the code, not the comments",                          "#FF652F"),
    ("// Premature optimization is the root of all evil",           "#F90001"),
    ("// Make it work, make it right, make it fast",                "#FFD700"),
    ("// Never trust user input",                                   "#34D399"),
    ("// Naming things is the second-hardest problem",              "#A78BFA"),
    ("// Off-by-one errors are inevitable -- design for them",      "#22D3EE"),
    ("// Documentation is a love letter to your future self",       "#EC4899"),
    ("// Refactor mercilessly once you understand more",            "#00C853"),
    ("// Bugs are features waiting to be understood",               "#FF652F"),
    ("// Empathy for the on-call engineer at 3am",                  "#F90001"),
    ("// YAGNI -- you aren't gonna need it",                        "#FFD700"),
    ("// The code is the source of truth -- comments lie",          "#34D399"),
    ("// Done is better than perfect",                              "#A78BFA"),
    ("// First, do no harm to production",                          "#22D3EE"),
    ("// Question every assumption, including this one",            "#EC4899"),
    ("// Patience is a feature, latency is a bug",                  "#00C853"),
    ("// Write code as if the next maintainer is psychotic",        "#FF652F"),
    ("// Cache invalidation is one of two hard problems",           "#F90001"),
    ("// The best code is code you don't have to write",            "#FFD700"),
    ("// Build with care, deploy with confidence",                  "#34D399"),
    ("// Stay hungry, stay foolish -- keep shipping",               "#A78BFA"),
    ("// Done > Perfect > Started",                                 "#22D3EE"),
    # ─── 20 personal mottos: Abdullah's work philosophy & roots ─────────────
    ("// I build for small businesses, not hyperscalers",           "#FFD700"),
    ("// Three languages, one keyboard, one ambition",              "#FF652F"),
    ("// Code I write today runs at the bakery tomorrow",           "#34D399"),
    ("// Started in HTML, ended up in production",                  "#F90001"),
    ("// Berlin coffee, Damascus passion, daily commits",           "#A78BFA"),
    ("// Built Baeckrei to make small bakeries thrive",             "#22D3EE"),
    ("// PyDev: pip install developer, but make it real",           "#EC4899"),
    ("// 5 GitHub Apps, 1 vision: respect maintainer time",         "#00C853"),
    ("// Production beats demo, every single Friday",               "#FF652F"),
    ("// I write Python the way I'd explain it to a friend",        "#FFD700"),
    ("// Vue 3 because composition beats inheritance",              "#34D399"),
    ("// The bakery never sleeps, the code shouldn't crash",        "#F90001"),
    ("// Open-source what you wish others had shared with you",     "#A78BFA"),
    ("// Every commit is a small gift to my future team",           "#22D3EE"),
    ("// From learning loop to long-running production",            "#EC4899"),
    ("// Build it once for yourself, then share it widely",         "#00C853"),
    ("// Microservices for problems, monoliths for solutions",      "#FFD700"),
    ("// 4+ years in, still excited to type 'git init'",            "#FF652F"),
    ("// English, Deutsch, Arabic -- code is the fourth tongue",    "#34D399"),
    ("// Made in Germany, for the world's small shops",             "#A78BFA"),
]


def round3(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".")


def build_clip_path(line_idx: int, n_lines: int, reveal_width: int, height: int) -> str:
    """Generate a <clipPath> whose rect width animates type→hold→erase→off
    aligned to line `line_idx` of `n_lines`."""
    window = 1.0 / n_lines
    start = line_idx * window  # 0..1 fraction of total cycle when this line starts

    # Phase ratios within the window (sum to 1)
    type_pct  = 0.12
    hold_pct  = 0.62
    erase_pct = 0.10
    # off_pct  = 0.16  (implicit remainder)

    type_end  = start + window * type_pct
    hold_end  = start + window * (type_pct + hold_pct)
    erase_end = start + window * (type_pct + hold_pct + erase_pct)

    if line_idx == 0:
        # First line is on at t=0, no initial off-phase keyframe needed
        values   = f"0;{reveal_width};{reveal_width};0;0"
        keyTimes = f"0;{round3(type_end)};{round3(hold_end)};{round3(erase_end)};1"
    elif line_idx == n_lines - 1:
        # Last line ends right at the cycle boundary
        values   = f"0;0;{reveal_width};{reveal_width};0"
        keyTimes = f"0;{round3(start)};{round3(type_end)};{round3(hold_end)};1"
    else:
        values   = f"0;0;{reveal_width};{reveal_width};0;0"
        keyTimes = f"0;{round3(start)};{round3(type_end)};{round3(hold_end)};{round3(erase_end)};1"

    return values, keyTimes


def build_svg(lines, *, width, height, font_size, font_weight, total_dur, reveal_w,
              text_x, text_y, has_cursor=False, output_path):
    n = len(lines)
    parts = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="cycling typing animation, {n} lines">'
    )
    parts.append(f"  <!-- Auto-generated by scripts/build_typing_svgs.py — do not hand-edit. -->")
    parts.append("  <style>")
    parts.append(
        f"    .term {{ font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', "
        f"Consolas, monospace; font-size: {font_size}px; font-weight: {font_weight}; }}"
    )
    if has_cursor:
        parts.append("    .cursor { fill: #F90001; }")
        parts.append("    .cursor-blink { animation: blink 0.8s step-end infinite; }")
        parts.append("    @keyframes blink { 50% { opacity: 0; } }")
    parts.append("  </style>")
    parts.append("  <defs>")

    # Build a clipPath per line
    for i in range(n):
        values, keyTimes = build_clip_path(i, n, reveal_w, height)
        parts.append(
            f'    <clipPath id="t{i:02d}"><rect x="0" y="0" height="{height}">'
            f'<animate attributeName="width" values="{values}" keyTimes="{keyTimes}" '
            f'dur="{total_dur}s" repeatCount="indefinite"/></rect></clipPath>'
        )

    parts.append("  </defs>")

    # Text lines, all at same position, each clipped to its window
    for i, (text, color) in enumerate(lines):
        # Escape XML special chars
        safe_text = (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
        )
        parts.append(
            f'  <text class="term" x="{text_x}" y="{text_y}" fill="{color}" '
            f'clip-path="url(#t{i:02d})">{safe_text}</text>'
        )

    if has_cursor:
        cursor_h = font_size + 2
        cursor_y = text_y - font_size + 2
        parts.append(
            f'  <rect class="cursor cursor-blink" x="6" y="{cursor_y}" '
            f'width="3" height="{cursor_h}"/>'
        )

    parts.append("</svg>")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts) + "\n")
    print(f"[OK] Wrote {output_path} ({os.path.getsize(output_path):,} bytes, {n} lines)")


def main() -> int:
    # 50 lines × 2s = 100s cycle; line text up to ~24 chars at 22pt mono ~= 480px wide
    build_svg(
        ABOUT_LINES,
        width=600, height=60,
        font_size=22, font_weight=700,
        total_dur=100, reveal_w=580,
        text_x=20, text_y=40,
        has_cursor=True,
        output_path=os.path.join(REPO_ROOT, "assets", "about-typing.svg"),
    )
    # 50 lines × 3s = 150s cycle; longest motto ~ 55 chars at 17pt mono ~= 580px wide
    build_svg(
        MOTTO_LINES,
        width=900, height=40,
        font_size=17, font_weight=500,
        total_dur=150, reveal_w=880,
        text_x=10, text_y=26,
        has_cursor=False,
        output_path=os.path.join(REPO_ROOT, "assets", "motto-typing.svg"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
