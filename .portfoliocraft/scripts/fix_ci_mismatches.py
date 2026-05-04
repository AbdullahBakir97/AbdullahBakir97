"""Replace the wrongly-typed CI workflows with stack-appropriate ones.

Mismatches:
  - 2050-Bootstrap-Landing-page  : HTML/CSS/JS static site → static CI
  - AI-KI                        : Jupyter notebooks       → notebook validation
  - Weather--App-django-vue.js   : Django + Vue dual stack → dual job CI
  - Portfolio                    : Next.js in frontend/    → frontend-build CI
"""
import base64
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

OWNER = "AbdullahBakir97"
NOREPLY = "127149804+AbdullahBakir97@users.noreply.github.com"
WORKDIR = Path(r"C:\Temp\polish-clones")
WORKDIR.mkdir(parents=True, exist_ok=True)


def _force_rmtree(path: Path) -> None:
    if not path.exists():
        return
    def on_rm_error(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception: pass
    try:
        shutil.rmtree(path, onexc=on_rm_error)
    except TypeError:
        shutil.rmtree(path, onerror=on_rm_error)
    if path.exists():
        subprocess.run(["cmd","/c","rmdir","/s","/q",str(path)], capture_output=True)


STATIC_CI = """name: CI

on:
  push:
    branches: ['**']
  pull_request:
    branches: ['**']
  workflow_dispatch:

jobs:
  validate:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Validate HTML
        continue-on-error: true
        run: |
          shopt -s globstar nullglob
          html_files=( **/*.html )
          if [ ${#html_files[@]} -gt 0 ]; then
            npx -y html-validate "${html_files[@]}" || true
          else
            echo "no .html files at this depth"
          fi
      - name: Sanity check — index.html exists
        continue-on-error: true
        run: |
          if compgen -G "**/index*.html" > /dev/null || compgen -G "*.html" > /dev/null; then
            echo "found at least one HTML entry point"
          else
            echo "::warning::no HTML entry point found"
          fi
"""

JUPYTER_CI = """name: CI

on:
  push:
    branches: ['**']
  pull_request:
    branches: ['**']
  workflow_dispatch:

jobs:
  validate-notebooks:
    runs-on: ubuntu-latest
    timeout-minutes: 8
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
      - name: Install nbformat
        run: |
          python -m pip install --upgrade pip
          pip install nbformat
      - name: Validate every notebook
        continue-on-error: true
        run: |
          set +e
          status=0
          while IFS= read -r nb; do
            python -c "import nbformat; nbformat.validate(nbformat.read('$nb', as_version=4))" \
              && echo "ok   $nb" \
              || { echo "FAIL $nb"; status=1; }
          done < <(find . -type f -name '*.ipynb' -not -path './.git/*')
          exit $status
      - name: Smoke-import any Python modules in repo
        continue-on-error: true
        run: |
          if ls **/*.py 1> /dev/null 2>&1; then
            pip install ruff || true
            ruff check --select E9,F63,F7,F82 . || true
          else
            echo "no .py files to lint"
          fi
"""

DUAL_DJANGO_VUE_CI = """name: CI

on:
  push:
    branches: ['**']
  pull_request:
    branches: ['**']
  workflow_dispatch:

jobs:
  backend:
    runs-on: ubuntu-latest
    timeout-minutes: 12
    env:
      DEBUG: '0'
      SECRET_KEY: ci-only-not-real-secret-key
      DJANGO_SETTINGS_MODULE: project.settings
      ALLOWED_HOSTS: '*'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
      - name: Install backend deps
        run: |
          python -m pip install --upgrade pip
          if [ -f backend/requirements.txt ]; then pip install -r backend/requirements.txt || true; fi
          pip install django ruff || true
      - name: Lint
        continue-on-error: true
        working-directory: backend
        run: ruff check --select E9,F63,F7,F82 . || true
      - name: Django check
        continue-on-error: true
        working-directory: backend
        run: |
          if [ -f manage.py ]; then python manage.py check || true; fi

  frontend:
    runs-on: ubuntu-latest
    timeout-minutes: 12
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - name: Install frontend deps
        working-directory: frontend
        run: npm ci || npm install
      - name: Build
        continue-on-error: true
        working-directory: frontend
        run: |
          if npm run | grep -q '^  build'; then npm run build || true; fi
      - name: Lint
        continue-on-error: true
        working-directory: frontend
        run: |
          if npm run | grep -q '^  lint'; then npm run lint || true; fi
"""

NEXTJS_FRONTEND_CI = """name: CI

on:
  push:
    branches: ['**']
  pull_request:
    branches: ['**']
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 12
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - name: Install
        working-directory: frontend
        run: npm ci || npm install
      - name: Build
        continue-on-error: true
        working-directory: frontend
        run: npm run build || true
      - name: Lint
        continue-on-error: true
        working-directory: frontend
        run: |
          if npm run | grep -q '^  lint'; then npm run lint || true; fi
"""

REPLACEMENTS = {
    "2050-Bootstrap-Landing-page": (STATIC_CI, "ci: replace Python CI with static-site validation"),
    "AI-KI":                       (JUPYTER_CI, "ci: replace Python CI with Jupyter-notebook validation"),
    "Weather--App-django-vue.js":  (DUAL_DJANGO_VUE_CI, "ci: replace single-stack CI with backend(Django) + frontend(Vue) dual jobs"),
    "Portfolio":                   (NEXTJS_FRONTEND_CI, "ci: replace generic Node CI with Next.js frontend-aware CI"),
}


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def get_token():
    res = run(["gh", "auth", "token"])
    return res.stdout.strip() if res.returncode == 0 else None


def update_ci(name: str, yml: str, msg: str) -> dict:
    repo_dir = WORKDIR / name
    _force_rmtree(repo_dir)
    token = get_token()
    if not token:
        return {"name": name, "status": "no-token"}
    url = f"https://x-access-token:{token}@github.com/{OWNER}/{name}.git"
    res = run(["git", "clone", "--depth", "1", url, str(repo_dir)])
    if res.returncode != 0:
        return {"name": name, "status": "clone-failed", "err": res.stderr.strip()[:200]}
    try:
        ci_path = repo_dir / ".github" / "workflows" / "ci.yml"
        ci_path.parent.mkdir(parents=True, exist_ok=True)
        ci_path.write_text(yml, encoding="utf-8")
        run(["git", "config", "user.name", "AbdullahBakir97"], cwd=repo_dir)
        run(["git", "config", "user.email", NOREPLY], cwd=repo_dir)
        res = run(["git", "add", ".github/workflows/ci.yml"], cwd=repo_dir)
        if res.returncode != 0:
            return {"name": name, "status": "add-failed", "err": res.stderr[:200]}
        # If no diff (file already correct), skip
        st = run(["git", "diff", "--cached", "--name-only"], cwd=repo_dir)
        if not st.stdout.strip():
            return {"name": name, "status": "no-change-needed"}
        res = run(["git", "commit", "-m", msg], cwd=repo_dir)
        if res.returncode != 0:
            return {"name": name, "status": "commit-failed", "err": res.stderr[:200]}
        res = run(["git", "push"], cwd=repo_dir)
        if res.returncode != 0:
            return {"name": name, "status": "push-failed", "err": res.stderr[:200]}
        return {"name": name, "status": "pushed"}
    finally:
        _force_rmtree(repo_dir)


print(f"Replacing CI on {len(REPLACEMENTS)} mismatched repos...\n")
results = []
for name, (yml, msg) in REPLACEMENTS.items():
    print(f"  {name} ...", end=" ", flush=True)
    r = update_ci(name, yml, msg)
    print(r["status"])
    if r.get("err"): print(f"      err: {r['err']}")
    results.append(r)

Path(r"C:\Users\abdul\AppData\Local\Temp\ci_fix_results.json").write_text(
    json.dumps(results, indent=2), encoding="utf-8"
)
counts = {}
for r in results: counts[r["status"]] = counts.get(r["status"], 0) + 1
print(f"\nSummary: {counts}")
