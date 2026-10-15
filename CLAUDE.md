# wsjtx-free-freq

## Agent skills

### Issue tracker

Issues and specs live in GitHub Issues on vk5as/wsjtx-free-freq, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Checks

`.venv/bin/python scripts/check.py` runs everything CI does (`lint` or `tests` for half). It's what implementers run before committing.

### Implementing and reviewing

Building a spec's tickets with subagents: `docs/agents/implementing.md`. Code review: `CODING_STANDARDS.md`.
