"""Add MIT LICENSE to kept repos that lack one.

Resolves the 14 high-severity 'No LICENSE' audit findings on kept repos.
Uses GitHub Contents API — no clone required.
"""
import json
import subprocess
import base64
from pathlib import Path

OWNER = "AbdullahBakir97"
HOLDER = "Abdullah Bakir"
YEAR = "2026"

TARGETS = json.loads(
    Path(r"C:\Users\abdul\AppData\Local\Temp\license_targets.json").read_text(encoding="utf-8")
)

MIT = f"""MIT License

Copyright (c) {YEAR} {HOLDER}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def gh(args, body=None):
    return subprocess.run(
        ["gh"] + args,
        input=body, capture_output=True, text=True
    )


def already_has_license(name: str) -> bool:
    res = gh(["api", f"repos/{OWNER}/{name}/license"])
    return res.returncode == 0


def push_license(name: str) -> dict:
    if already_has_license(name):
        return {"name": name, "status": "skipped (already licensed)"}
    body = json.dumps({
        "message": "chore: add MIT license",
        "content": base64.b64encode(MIT.encode("utf-8")).decode("ascii"),
    })
    res = gh(["api", "-X", "PUT",
              f"repos/{OWNER}/{name}/contents/LICENSE",
              "--input", "-"], body)
    if res.returncode == 0:
        return {"name": name, "status": "added"}
    return {"name": name, "status": "ERROR",
            "err": res.stderr.strip()[:200]}


print(f"Adding MIT LICENSE to {len(TARGETS)} repos...\n")
results = []
for i, name in enumerate(TARGETS, start=1):
    r = push_license(name)
    print(f"[{i:>2}/{len(TARGETS)}] {name:40} -> {r['status']}")
    if r.get("err"):
        print(f"           {r['err']}")
    results.append(r)

added = sum(1 for r in results if r["status"] == "added")
skipped = sum(1 for r in results if "skipped" in r["status"])
errors = sum(1 for r in results if r["status"] == "ERROR")
print(f"\nDone. added={added}, skipped={skipped}, errors={errors}")

Path(r"C:\Users\abdul\AppData\Local\Temp\license_results.json").write_text(
    json.dumps(results, indent=2), encoding="utf-8"
)
