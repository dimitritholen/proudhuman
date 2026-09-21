# proudhuman

Maps the human's role in a merged pull request from Claude Code session transcripts.

The tool exists because of a recurring complaint: engineers generate specs, code, tests and reports with Claude Code under "just ship" pressure, without time to read any of it, and afterwards nobody can say what the human decided, checked, or fixed. The minority position in that debate is the target here: AI-assisted work is fine when there is a human who understands and is accountable for the output. This tool answers, per PR, who that human is and what evidence shows they acted.

It is developer-facing. Run it on your own PRs as a self-review. It is not a scorecard for managers, and nothing in the report should be read as one.

## What it reads

- The PR's git range (`merge^1..merge^2` for a merged PR, or `merge-base..branch` for an open branch): commits, authors, timestamps, the diff.
- Claude Code transcripts under `~/.claude/projects/<encoded repo path>/`. A session is matched to the PR when any record carries `gitBranch == head branch`, or when records inside the PR's time window have a `cwd` inside the repo. Subagent transcripts in the sibling `<session-id>/` directory are folded into their parent session.

The `Claude-Session:` commit trailer is not used. Its value matches neither the transcript filename nor the bridge session id stored inside the file, and many commits lack it.

## What the report contains

| Section | Signal | How it is derived |
|---|---|---|
| Accountable human | commit author, merge committer, merge action | git metadata; every `gh pr merge` / `git merge` attempt in any session of the project, human (`!` command) or AI (Bash tool), with the AI attempt's result; fallback: a typed turn mentioning the merge within 10 minutes of it |
| Commits | who ran `git commit` | an AI Bash tool call containing `git commit` within 3 minutes of the commit time, or a human `!` command; otherwise "not in matched transcripts" |
| Human turns | framing, typed, question, slash, shell, interrupt, rejection, user-modified | see below |
| Added lines | AI-written, moved, only said in chat, no origin | each non-trivial added line is looked up in every string the AI wrote through Edit, Write, MultiEdit, Bash or NotebookEdit; lines that also appear as removed lines in the same diff count as moved |
| Pass-through prompts | human input that is verbatim earlier AI output | the first 160 normalized characters of each typed prompt are searched in earlier assistant text and Write/Edit content across all sessions of the project |

Human-turn labels:

- **framing**: the first typed turn of a session that worked on the branch.
- **typed**: any later typed turn (`promptSource` in typed, queued, suggestion_accepted; not meta, not a subagent).
- **question**: a typed turn ending in `?` or starting with why/how/what/where/which (English or Dutch).
- **slash**: a slash command.
- **shell**: a `!` command run by the human.
- **interrupt**: `[Request interrupted by user]`.
- **rejection**: a tool call the human refused.
- **user-modified**: an Edit result flagged `userModified`, meaning the human changed the file between AI edits.

Dwell is the time between the previous assistant record and the human turn. It is reported, not interpreted.

## Install

This directory is a Claude Code plugin and its own marketplace.

```
claude plugin marketplace add C:\dev\proudhuman
claude plugin install proudhuman@proudhuman
```

That adds one skill, `proudhuman`, which the model can invoke when you ask what you did on a PR, who is accountable for a change, or whether a PR had a human review. You can also type `/proudhuman:proudhuman 13`.

## Usage

Through the skill: name a PR number or a branch in the repo you are working in.

Directly:

```
python skills\proudhuman\scripts\proudhuman.py --repo C:\dev\tasqx --pr 13
python skills\proudhuman\scripts\proudhuman.py --repo C:\dev\tasqx --branch feat/x --base main
```

Reports land in `~/.proudhuman/<repo>/<pr>.md`, outside the repository, unless `--out` is given. Python 3.10+, no dependencies. `--pr` needs a `Merge pull request #N` commit on the trunk (`main`, falling back to `master`); squash-merged PRs need the `--branch` form.

Example reports from the validation run are in `examples/`.

## Limits

- Reading and understanding are unobservable. Every signal is a proxy. A fast expert skim and no review look the same; a long dwell with zero comprehension looks like verification. The report says "no evidence of review" where that is what the data shows. It never says "not reviewed".
- Lines produced by AI shell transformations (a `sed` that adds `pub(crate)` to every function, a formatter run) have no origin in emitted text and show up as "no origin". Treat that column as a sample to inspect, not a count of hand-written lines.
- Pass-through detection only searches sessions in the same project directory. A prompt generated in another project's session is not found.
- Sessions matched by time window alone can include unrelated work that happened in the same repo minutes before the branch started. Their framing turn is not counted; their in-window turns are.
- Work done outside Claude Code (an editor, a GitHub UI merge, another machine) leaves no transcript. The report says so rather than guessing. When no session matches at all, the verdict section says only that, and the line table is not interpreted.
- Line attribution under-credits the human. A line the human wrote by hand counts as AI-written if the AI later re-emits it inside a Write or a wide Edit, and `userModified` only fires when an AI edit follows the human's touch. The tool cannot tell a human line that was later re-typed by the AI from an AI line.
- `--branch` mode (open branch against a base) has been smoke-tested once, on a branch with no matching transcripts. Treat it as less exercised than `--pr`.

## Validation so far (2026-09-21, tasqx repo)

| PR | shape | what the report showed |
|---|---|---|
| #13 | 5 commits, +1221/-51 | zero human turns after framing; framing prompt was an AI-written handoff file from the previous session; AI enabled auto-merge; 21 of 942 lines with no origin, all formatter-shaped |
| #17 | 2 commits, +151/-1 | one question, one `/permissions`; AI's two merge attempts failed (not mergeable, then permission denied), the human merged with `--admin` |
| #16 | 35 commits, +5107/-4162 refactor | 7 typed turns, 3 questions, 2 interrupts, 1 rejection; 2331 of 3932 added lines were moved code; merged in the GitHub UI, followed by the human typing "merged, push a new release" |

The three are distinguishable from the report alone, which is the bar the prototype had to clear.
