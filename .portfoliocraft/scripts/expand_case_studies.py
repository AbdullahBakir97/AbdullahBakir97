"""Expand summary-case-studies.md to cover every meaningful repo (full coverage)."""
import json, re, datetime as dt
from pathlib import Path

REPO_DIR = Path(r"C:\Users\abdul\projects\Abdullah-Readme\src")
REPOS_JSON = Path(r"C:\Users\abdul\AppData\Local\Temp\repos.json")
CS_PATH = REPO_DIR / ".portfoliocraft" / "summary-case-studies.md"

with REPOS_JSON.open(encoding='utf-8') as f:
    repos = json.load(f)

# Reset to original 6-entry file (regenerate cleanly each run)
ORIGINAL_HEADER = "# Project case studies\n"

# Pull the original 6 sections from the file (those PortfolioCraft generated)
with CS_PATH.open(encoding='utf-8') as f:
    full = f.read()

# Take everything up to the "Additional repositories" separator if it exists,
# else use the full file as-is — that gives us the canonical PortfolioCraft block.
split = full.split("\n---\n\n## Additional repositories", 1)
canonical = split[0].rstrip()

already_covered = set(re.findall(r'^## (\S+)$', canonical, re.MULTILINE))
print(f"Canonical PortfolioCraft entries ({len(already_covered)}): {sorted(already_covered)}")

PINNED = {
    'Django-Store', 'Barber-Salon', 'Project-Management-Tool',
    'Python-Django-join_with', 'Weather--App-django-vue.js',
    'Django-Vuejs-Courses-Filter', 'API', 'Jobs-Portal',
    'Stock-Manager', 'PortfolioCraft',
}
PYDEV = {'commit-craft', 'pr-coach', 'repodoc-ai', 'ai-quality-gate', 'issue-triage-bot', 'release-pilot'}
SKIP = {'test', 'email', 'schedule-', 'tzgf', 'HTML-1'}  # truly throwaway names

today = dt.date(2026, 5, 4)

def parse_iso(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00')).date()

def status_for(r):
    if r.get('archived'): return 'archived'
    pushed = parse_iso(r['pushed'])
    return 'active' if (today - pushed).days <= 90 else 'dormant'

def duration_for(r):
    c = parse_iso(r['created']); p = parse_iso(r['pushed'])
    months = max(1, (p.year - c.year) * 12 + (p.month - c.month))
    return f"{c.strftime('%b %Y')}–{p.strftime('%b %Y')} ({months} month{'s' if months != 1 else ''})"

DOMAIN_RULES = [
    ('Tooling / CLI', lambda r: any(t in (r.get('topics') or []) for t in ('cli','github-action','automation','developer-portfolio','devtool')) or r['name'] in {'PortfolioCraft','GitHub-Doc-Generator','Repo-Directory-Structure','API-Client-Generator','Python-Environment-Management-Tool','commit-craft','pr-coach','repodoc-ai','ai-quality-gate','issue-triage-bot','release-pilot'}),
    ('Machine learning / data', lambda r: any(t in (r.get('topics') or []) for t in ('ai','ml','machine-learning','rag','llm','scraping')) or r['name'] in {'AI-KI','Mini-RAG','Web-Scraping-','cortex','BOT','Content-Creator-Tool','Logo-Generator','image-cropping'}),
    ('Game', lambda r: any(t in (r.get('topics') or []) for t in ('game','pygame')) or r['name'] in {'Py-Tetris-Game','Python-Game','Space-Shooter'}),
    ('Frontend / UI', lambda r: (r.get('lang') or '') in ('Vue','JavaScript','TypeScript','HTML','CSS') or any(t in (r.get('topics') or []) for t in ('vue','react','frontend','landing-page','portfolio','bootstrap'))),
]
def domain_for(r):
    for name, rule in DOMAIN_RULES:
        try:
            if rule(r): return name
        except Exception: pass
    return 'Backend / API'

def stack_for(r):
    lang = r.get('lang') or '—'
    topics = sorted(r.get('topics') or [])[:3]
    return f"{lang} · {', '.join(topics)}" if topics else lang

def overview_for(r):
    desc = (r.get('description') or '').strip()
    if desc: return desc
    lang = r.get('lang') or 'Multi-language'
    topics = r.get('topics') or []
    name = r['name'].replace('-', ' ').replace('_', ' ').strip()
    if topics:
        return f"{name} — {lang} project. Tags: {', '.join(topics[:5])}."
    return f"{name} — {lang} repository. Detailed write-up pending."

def scale_for(r):
    s = f"{r['stars']} star{'s' if r['stars'] != 1 else ''}, {r['forks']} fork{'s' if r['forks'] != 1 else ''}"
    if r['name'] in PINNED: s += ' · pinned'
    return s

def topics_line(r):
    t = sorted(r.get('topics') or [])
    return ', '.join(t) if t else '—'

def include(r):
    if r['name'] in SKIP: return False
    if r['name'] in already_covered: return False
    return True  # full portfolio coverage

new_repos = [r for r in repos if include(r)]
# Sort: pinned first, pyDev apps next, then by stars desc
def sort_key(r):
    bucket = 0 if r['name'] in PINNED else (1 if r['name'] in PYDEV else 2)
    return (bucket, -r['stars'], -r['forks'], r['name'].lower())
new_repos.sort(key=sort_key)

print(f"\nNew entries: {len(new_repos)}")

chunks = []
for r in new_repos:
    block = (
        f"\n## {r['name']}\n\n"
        f"**Repository:** [AbdullahBakir97/{r['name']}]({r['url']})  \n"
        f"**Stack:** {stack_for(r)}  \n"
        f"**Duration:** {duration_for(r)}  \n"
        f"**Status:** {status_for(r)}  \n"
        f"**Scale:** {scale_for(r)}\n\n"
        f"### Overview\n{overview_for(r)}\n\n"
        f"### Domain\n{domain_for(r)}\n\n"
        f"### Topics\n{topics_line(r)}\n"
    )
    chunks.append(block)

header = (
    "\n\n---\n\n"
    "## Additional repositories\n\n"
    f"_Generated {today.isoformat()} from the live GitHub catalogue to cover the wider "
    f"portfolio beyond the pinned showcase. Concise stubs — narrative write-ups will be "
    f"added incrementally. Order: pinned → PyDev Apps suite → by community traction (stars/forks)._\n"
)
new_content = canonical + header + ''.join(chunks) + '\n'

CS_PATH.write_text(new_content, encoding='utf-8')
print(f"\nWrote {CS_PATH}")
print(f"  size: {len(new_content)} bytes")
print(f"  sections: {new_content.count(chr(10) + '## ')}")
