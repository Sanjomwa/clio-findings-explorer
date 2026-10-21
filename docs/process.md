# Process

How work is tracked, committed and finished in this repository. Issue [#9](https://github.com/Sanjomwa/clio-findings-explorer/issues/9). Who does what, and how each limit is enforced, is in [agent-team.md](agent-team.md); the rules an agent must follow are in [AGENTS.md](../AGENTS.md). This page does not repeat the roles.

## The tracker

Tasks are public GitHub Issues: <https://github.com/Sanjomwa/clio-findings-explorer/issues>. Each has acceptance criteria.

- **Labels.** `agent-task` (a task given to a coding agent, with acceptance criteria), `buffer` (small cleanup), one `rubric: ...` label per course criterion (problem description, product specification, agent team specification, context management, deployment, ci/cd, observability, alerting, on-call agent), and `incident` (an on-call agent escalation). GitHub's standard labels exist too.
- **Every task prompt names its issue.** At the start, the agent reads it: `gh issue view <N> --json title,body,state,comments`. The plain `--comments` form fails with a Projects (classic) GraphQL error.
- **One comment at STOP.** `gh issue comment <N> --body-file <file>`, with the file written in the session scratchpad directory. It says what was done, the checks run and their results, which acceptance criteria are met, and what is left for Sam. It must not contain secrets, tokens, database URLs or personal data. When a prompt says not to comment yet, the agent does not.
- **Agents never close, edit, reopen or delete issues.** Sam closes them through commit messages. The only GitHub writes an agent may make are `gh issue create` and `gh label create` (when a prompt explicitly asks for them) and `gh issue comment` (on the issue the prompt names). The `block-autonomous-git` hook denies the rest ([permissions.md](permissions.md)).
- **One closing keyword per issue.** GitHub closes only the issue that follows a keyword. On 18 October the commit `368418b` said `Closes #3 #4`: #3 closed with the push (12:22 UTC) and #4 closed four minutes later (12:26 UTC), apparently by hand, because the keyword had applied to #3 only. Write `Closes #3` and `Closes #4`, one per issue. Use `Refs #N` for a commit that does not finish an issue.

## Commit conventions

Only Sam commits. The planning session drafts the message; Sam uses it.

- **Subject:** a type, a colon and a short description, for example `feat: alert on finding-page user impact (Grafana, provisioned)`, `docs: ...`, `chore: ...`. Name the issue in the subject when the commit is one part of it (`(issue #7, Part B)`).
- **Body:** what changed and what was recorded (counts, run results), in plain words.
- **Issue links:** `Closes #N` (one per issue) or `Refs #N`.
- **Trailers:** `Co-Authored-By: Claude <model> <noreply@anthropic.com>` and a `Claude-Session:` link, as in `f39c631`.
- **`[skip ci]`:** for docs-only commits that need no test run and no deploy (for example `2ed5809`). A commit that skips CI does not deploy, because dev deploys only after CI passes.
- **One concern per commit** where it can be done; a task with a STOP in the middle is committed in the parts Sam chooses.

## The sync rule

Sam keeps the repository in WSL and the planning session reads a mirror of it in a separate workspace. He moves files with `sync.sh` and always runs it as a **dry run first**, and pushes only if nothing would be deleted. The planning session reviews the mirror, never the live repository, and has no git access. Claude Code reads the OneDrive prompt file only and never copies, syncs or changes anything there.

## STOP and report

A prompt marks each point where the agent must stop with a **STOP** section. At a STOP the agent stops, does nothing further on its own judgment, and reports ([AGENTS.md](../AGENTS.md) rule 8). Anything blocked is also a STOP: a hook block, an auto-mode classifier block or a prompt that contradicts the repo. The agent says what was blocked and does not try another route. The report has the same shape every time:

1. what changed (files);
2. what was run and the result;
3. what was not done;
4. anything in the prompt that was wrong;
5. any command Sam needs to run himself;
6. the `git status --short` output and the complete `git add` list when the prompt asks for them.

## Definition of done

A task is done when all of these are true:

- **Tests.** The relevant suites pass (`scripts/test-all.sh` for code changes; the checks the prompt names for docs), ruff is clean, and no test was deleted or weakened to pass. New behaviour has a test.
- **Docs.** Every document that describes the changed behaviour is updated in the same piece of work (AGENTS.md rule 7): `README.md`, `product-spec.md`, `openapi.yaml`, `docs/`. Links resolve (checked by `ops/tests/test_docs_links.py`).
- **Claims.** Every statement about the data comes from a query that is quoted in the report (rule 5), and rule 6 (no causal claims) is respected.
- **Workflow log.** An entry is appended to [ai-workflow-log.md](ai-workflow-log.md) as the work happens: the task as given, what was produced, what was verified and how, what was not done.
- **Issue comment.** One comment on the task's issue, at STOP, as above.
- **Review.** The planning session reviews the result in the mirror before Sam commits.
- **Commit.** Sam commits with `Closes #N`; CI passes; dev deploys; production is a manual promotion ([deploy.md](deploy.md)).
