# Implementing tickets

How a spec's tickets get built: an orchestrator dispatches one **implementer** per ticket into its own worktree, then one **merger** at a time folds each finished branch into the **integration branch**.

## Orchestrator

- Create the integration branch from `master` and push it.
- Implementers in worktrees cannot reach the git credential store, so `gh` fails there. Before dispatching, save each ticket body to a file outside the repo (`gh issue view <N> --json number,title,body`), and give the implementer that path plus the spec's path.
- Run one merger at a time; they share the main checkout.
- Close each ticket once it is merged, with a comment naming the merge commit.

## Implementer

1. `git checkout -B ticket/<N> <integration branch>`, so the work starts from its tip.
2. `python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"`.
3. Read the ticket file and only the spec sections it points to. Read `GLOSSARY.md` and use its terms in names, tests and UI text. ADR 0001: never set Tx.
4. Build it with the `tdd` skill, red before green. The seams are already confirmed in the spec's Testing Decisions: the engine's `receive`/`snapshot`/`set_rx` for behaviour, and `scripts/ci_smoke_test.py` for GUI wiring. Test through them, not through private helpers.
5. `.venv/bin/python scripts/check.py` until it ends with "all checks passed".
6. Commit as `<ticket title> (#<N>)`, then `git merge <integration branch>`, re-run the checks, and commit.
7. Report the branch, the final commit, each acceptance criterion as met or not met, and anything the orchestrator should know. Leave pushing and issues to the orchestrator.

## Merger

1. In the main checkout, on a clean integration branch: `git merge --no-ff ticket/<N> -m "Merge ticket #<N>: <title>"`, with the Co-Authored-By trailer. On conflicts, keep both tickets' behaviour and both sides' tests. The commit message is the title plus trailers; the `no-conflict-notes` hook rejects git's "# Conflicts:" list.
2. `.venv/bin/python scripts/check.py`. Fix small breakages in a follow-up commit. If the ticket is fundamentally broken, reset to the pre-merge commit and report why.
3. Push the integration branch, remove the implementer's worktree, and delete `ticket/<N>` and its `worktree-agent-*` branch.
4. Report the merge commit, the check result and any fixes.
