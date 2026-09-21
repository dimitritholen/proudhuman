---
name: proudhuman
description: Map the human's role in a pull request or branch from the Claude Code transcripts that produced it. Use when the user asks what they actually did on a PR, who is accountable for a change, whether a PR was reviewed by a human, how much of a branch the AI wrote, to run proudhuman, or for a self-review of their AI-assisted work.
---

# proudhuman

Reads the Claude Code session transcripts that worked on a branch, plus the branch's git range, and writes a private markdown report: the accountable human and how the merge happened, every human turn and action, added lines with no origin in AI-emitted text, and prompts that were verbatim earlier AI output.

The report is self-review material for the person whose transcripts it reads. Present it in a flat tone, with transcript references, and with the report's own wording for absence: "no evidence of review", never "not reviewed".

## 1. Resolve the target

Repository: the current working directory unless the user names another path.

- PR number given: use `--pr N`. The script finds the `Merge pull request #N` commit on the trunk (`main`, falling back to `master`; pass `--base` for another trunk). Squash-merged PRs leave no such commit; use the branch form instead.
- Branch name given, or the user is on a feature branch and names no PR: use `--branch NAME --base <trunk>`.
- On the trunk with no PR named: ask which PR or branch.

Done when you have one command line to run.

## 2. Run the script

Python 3.10 or newer, no dependencies. The script lives in `scripts/` under this skill's base directory.

```
python <skill base directory>/scripts/proudhuman.py --repo <repo> --pr <N>
python <skill base directory>/scripts/proudhuman.py --repo <repo> --branch <name> --base <trunk>
```

It prints the report and writes it to `~/.proudhuman/<repo>/<pr>.md`. Reports stay outside the repository.

Done when the script prints `wrote <path>`. An exit with `no merge commit` or `no commits in range` means step 1 chose the wrong form; switch form and rerun once.

## 3. Relay the findings

From the report, give the user, in this order, each with the transcript reference (`session:line`) the report prints beside it:

1. **Accountable human**: commit author, how the merge happened (human `!` command, AI tool call and its result, GitHub UI, or not found), and who ran each commit.
2. **Human turns**: the counts table, then the typed turns with their dwell times, and every interrupt, rejection, shell command, and file the human touched between AI edits.
3. **Pass-through prompts**: each prompt that originates in earlier AI output, with the session and line it came from.
4. **Lines with no origin**: the totals row, the moved-code count, and the sample. Say what the README says about that column: shell transformations and formatters land there too, so it is a sample to inspect, not a count of hand-written lines.
5. **What the evidence supports**: the report's closing bullets, verbatim in substance.

When no session matched, relay only that: nothing can be said about the human's role from Claude Code data.

Done when all five items are relayed and the report path is named once.

## Reference

Signal definitions, how each column is derived, and the limits of every signal: `README.md` at the plugin root. Read it before answering a question about what a number means or why a line shows no origin.
