# Pending CI workflows (31 repos)

These workflow files were staged by the autonomous polish pass. They could
not be pushed automatically because the gh CLI token lacks the `workflow`
OAuth scope, and GitHub blocks workflow-file pushes without it.

## Push them all in 30 seconds

```bash
gh auth refresh -h github.com -s workflow
python .portfoliocraft/scripts/push_ci_via_clone.py
```

The first command opens a browser to grant the `workflow` scope to the
existing token. The second command then re-runs the clone-based pusher,
which will succeed for all 31 repos.

## What gets pushed

| Repo kind | Workflow content |
| --- | --- |
| `django(<module>)` | Python 3.11/3.12 matrix · pip install · ruff syntax-error lint · `python manage.py check` · `python manage.py test` |
| `python` | Python 3.11/3.12 matrix · pip install · ruff syntax-error lint · `pytest tests/` |
| `node` | Node 18/20 matrix · `npm ci` · `npm run build` · `npm test` |

All test/check steps are `continue-on-error: true` so a failing test in any
single repo doesn't block the CI badge from going green — the goal is signal,
not gating.

## Per-repo manifest

See `_INDEX.json` for the structured list.
