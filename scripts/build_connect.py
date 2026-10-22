"""Generate the Connect / Guestbook / Support buttons and the footer as small SVG
tiles in the same editorial look as the rest of the README. Each tile is its own
image so the README can wrap it in a link. Pure SVG for GitHub's <img> proxy."""
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "connect"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'JetBrains Mono',Menlo,Consolas,monospace"

ICONS = {  # 24x24 single-path glyphs
    "linkedin": "M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.86 0-2.14 1.45-2.14 2.94v5.67H9.34V9h3.42v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13zM7.12 20.45H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0z",
    "github": "M12 .3a12 12 0 0 0-3.8 23.4c.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.4-1.8-1.4-1.8-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-6 0-1.2.5-2.3 1.3-3.1-.2-.4-.6-1.6 0-3.2 0 0 1-.3 3.4 1.2a11.5 11.5 0 0 1 6 0c2.3-1.5 3.3-1.2 3.3-1.2.6 1.6.2 2.8.1 3.2.8.8 1.3 1.9 1.3 3.1 0 4.6-2.8 5.6-5.5 5.9.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0 0 12 .3",
    "mail": "M2 5.5A1.5 1.5 0 0 1 3.5 4h17A1.5 1.5 0 0 1 22 5.5v13a1.5 1.5 0 0 1-1.5 1.5h-17A1.5 1.5 0 0 1 2 18.5zm2.2.5 7.8 6.2L19.8 6zM20 7.8l-7.4 5.9a1 1 0 0 1-1.2 0L4 7.8V18h16z",
    "telegram": "M21.9 3.3 18.6 19c-.2 1.1-.9 1.4-1.8.9l-5-3.7-2.4 2.3c-.3.3-.5.5-1 .5l.4-5.1L18.1 5c.4-.4-.1-.6-.6-.2L6 12.1l-5-1.6c-1.1-.3-1.1-1.1.2-1.6L20.5 1.8c.9-.3 1.7.2 1.4 1.5z",
    "instagram": "M12 2.2c3.2 0 3.6 0 4.8.1 3.3.1 4.8 1.7 4.9 4.9.1 1.3.1 1.6.1 4.8s0 3.6-.1 4.8c-.1 3.2-1.7 4.8-4.9 4.9-1.3.1-1.6.1-4.8.1s-3.6 0-4.8-.1c-3.3-.1-4.8-1.7-4.9-4.9C2.2 15.6 2.2 15.2 2.2 12s0-3.6.1-4.8C2.4 3.9 3.9 2.4 7.2 2.3 8.4 2.2 8.8 2.2 12 2.2zM12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm0 8.2a3.2 3.2 0 1 1 0-6.4 3.2 3.2 0 0 1 0 6.4zm5.2-9.6a1.2 1.2 0 1 0 0 2.4 1.2 1.2 0 0 0 0-2.4z",
    "pen": "M3 17.2V21h3.8L17.8 9.9l-3.8-3.8zM20.7 7a1 1 0 0 0 0-1.4l-2.3-2.3a1 1 0 0 0-1.4 0l-1.8 1.8 3.8 3.8z",
    "book": "M4 4.5A2.5 2.5 0 0 1 6.5 2H20v17H6.5a1 1 0 0 0 0 2H20v1H6.5A2.5 2.5 0 0 1 4 19.5z",
    "coffee": "M4 8h13v5a6 6 0 0 1-6 6H10a6 6 0 0 1-6-6zm13 1h1.5a2.5 2.5 0 0 1 0 5H17v-1.6h1.5a.9.9 0 0 0 0-1.8H17zM7 2.5c0 1 .8 1.3.8 2.3S7 6 7 6M10.5 2.5c0 1 .8 1.3.8 2.3s-.8 1.2-.8 1.2M14 2.5c0 1 .8 1.3.8 2.3S14 6 14 6",
}

def tile(name, icon, accent, kicker, title, sub, w=440, h=124):
    stroke_icon = icon == "coffee"
    glyph = (f'<path d="{ICONS[icon]}" fill="none" stroke="{accent}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
             if stroke_icon else f'<path d="{ICONS[icon]}" fill="{accent}"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(kicker)} {escape(title)}">'
           f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#141b24"/><stop offset="1" stop-color="#0d1117"/></linearGradient></defs>'
           f'<rect x=".75" y=".75" width="{w-1.5}" height="{h-1.5}" rx="16" fill="url(#bg)" stroke="#30363d" stroke-width="1.5"/>'
           f'<rect x="0" y="22" width="4" height="{h-44}" rx="2" fill="{accent}"/>'
           f'<rect x="26" y="{h/2-28}" width="56" height="56" rx="14" fill="{accent}" fill-opacity=".12" stroke="{accent}" stroke-opacity=".45"/>'
           f'<g transform="translate({54-14} {h/2-14}) scale({28/24})">{glyph}</g>'
           f'<text x="104" y="{h/2-16}" font-family="{MONO}" font-size="12.5" font-weight="700" letter-spacing="2.4" fill="#42b883">{escape(kicker)}</text>'
           f'<text x="104" y="{h/2+12}" font-family="{SANS}" font-size="22" font-weight="800" fill="#ffffff">{escape(title)}</text>'
           f'<text x="104" y="{h/2+36}" font-family="{SANS}" font-size="15" fill="#8b949e">{escape(sub)}</text>'
           f'<text x="{w-26}" y="{h/2+8}" text-anchor="end" font-family="{SANS}" font-size="22" fill="#58a6ff">&#8594;</text></svg>')
    (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")

def footer():
    w, h = 1400, 220
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="Thanks for stopping by">'
           '<defs><linearGradient id="r" x1="0" x2="1"><stop offset="0" stop-color="#F90001" stop-opacity="0"/><stop offset=".5" stop-color="#F90001"/>'
           '<stop offset="1" stop-color="#F90001" stop-opacity="0"/></linearGradient></defs>'
           f'<rect x="0" y="20" width="{w}" height="2" fill="url(#r)"/>'
           f'<circle cx="{w/2}" cy="21" r="6" fill="#F90001"/>'
           f'<text x="{w/2}" y="98" text-anchor="middle" font-family="{MONO}" font-size="15" font-weight="700" letter-spacing="3.5" fill="#42b883">// END OF FILE</text>'
           f'<text x="{w/2}" y="150" text-anchor="middle" font-family="{SANS}" font-size="44" font-weight="800" letter-spacing="-1" fill="#ffffff">Thanks for stopping by<tspan fill="#F90001">.</tspan></text>'
           f'<text x="{w/2}" y="190" text-anchor="middle" font-family="{SANS}" font-size="19" font-style="italic" fill="#8b949e">If you\'re building something, I\'d like to hear about it.</text></svg>')
    (OUT / "footer.svg").write_text(svg, encoding="utf-8")

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tile("linkedin", "linkedin", "#58a6ff", "FASTEST REPLY", "LinkedIn", "in/abdullah-bakir-809065273")
    tile("email", "mail", "#ff652f", "WRITE TO ME", "Email", "abdullah.bakir.204@gmail.com")
    tile("github", "github", "#e6edf3", "CODE", "GitHub", "@AbdullahBakir97")
    tile("telegram", "telegram", "#38bdf8", "CHAT", "Telegram", "@BlackSea0011")
    tile("guestbook-sign", "pen", "#F90001", "LEAVE A NOTE", "Sign the guestbook", "opens a short pre-filled issue")
    tile("guestbook-read", "book", "#42b883", "SEE WHO STOPPED BY", "Read past entries", "every note, in public")
    tile("coffee", "coffee", "#e3b341", "SUPPORT MY WORK", "Buy me a coffee", "if my tools helped you", w=900)
    footer()
    print("wrote", len(list(OUT.glob("*.svg"))), "tiles to", OUT.relative_to(ROOT))

if __name__ == "__main__":
    main()
