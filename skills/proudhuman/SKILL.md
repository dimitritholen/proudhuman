---
name: proudhuman
description: Tell the story of a pull request or branch from the Claude Code transcripts that produced it, with the human's steering as the subject. Use when the user asks what they actually did on a PR, who is accountable for a change, whether a PR was reviewed by a human, how much of a branch the AI wrote, for a story or self-review of their AI-assisted work, or to run proudhuman.
---

# proudhuman

One PR, one story: a self-contained HTML page in six chapters (the Spark, the Steering, Moments of Judgment, the Build, the Ship, What the Record Cannot See), with the human's turns as the subject and Claude's build as the material. Two passes of a script and one subagent produce it. The model never writes HTML; it writes prose into slots.

The story is self-review material for the person whose transcripts it reads. Present it in a flat tone. Where the record holds little of the human, the story says so; keep that wording when you relay it: "the record holds no evidence of", never "you did not".

## 1. Resolve the target

Repository: the current working directory unless the user names another path.

- PR number given: `--pr N`. The script finds the `Merge pull request #N` commit on the trunk (`main`, falling back to `master`; `--base` for another trunk). Squash-merged PRs leave no such commit; use the branch form.
- Branch name given, or the user is on a feature branch and names no PR: `--branch NAME --base <trunk>`.
- On the trunk with no PR named: ask which PR or branch.
- Language: `--lang nl` when the user asks for Dutch; English otherwise. Accent colour: `--accent '#hex'` only when asked.

Done when you have one `analyze` command line.

## 2. Analyze

Python 3.10 or newer, no dependencies. Scripts live in `scripts/` under this skill's base directory.

```
python <skill base directory>/scripts/proudhuman.py analyze --repo <repo> --pr <N> [--lang nl]
```

It prints `wrote <story dir>/beats.json` and a one-line count of sessions, steers, judgments, verifications, pass-throughs and ship status. The story directory is `~/.proudhuman/<repo>/pr<N>/`.

An exit saying `no session matched` means no transcript on this machine worked on that branch: report that sentence to the user and stop; there is no story to tell. `no merge commit` or `no commits in range` means step 1 chose the wrong form; switch form and rerun once.

Done when `beats.json` exists.

## 3. Write the prose

Dispatch the `prose-writer` agent shipped with this plugin (its `subagent_type` is `proudhuman:prose-writer`) with exactly these paths, nothing else from your context:

- the rules: `<skill base directory>/PROSE-RULES.md`
- the slots: `<skill base directory>/scripts/slots.json`
- the glossary: `<plugin root>/CONTEXT.md`
- the beats: `<story dir>/beats.json`
- the output: `<story dir>/prose.json`

Tell it the language from step 1. Wait for its report.

Done when `prose.json` exists.

## 4. Render

```
python <skill base directory>/scripts/proudhuman.py render <story dir>
```

It prints `wrote <story dir>/story.html`. Rendering needs no model and can be rerun at any time. A slot the writer missed or overran shows as a visible "Unwritten" block in the page; if the report from step 3 or a grep for `class="unwritten"` shows any, send the writer back for those slots once, then render again.

Done when `story.html` exists with no unwritten block, or with the unwritten blocks named to the user.

## 5. Present

Give the user, in this order:

1. The path of `story.html`, and that it opens offline in any browser and prints with one chapter per page.
2. The story's title.
3. The accountable human and how the ship happened, from the beats: commit author, merger, and the merge attempts with who ran them and their outcome.
4. Counts from the analyze line: steers, judgments, verifications, pass-throughs.
5. Presence from `beats.json`: time at the keyboard across sessions, phrased as presence.

Nothing else. The story is the deliverable; the summary points at it.

## Reference

What each beat means, how each chart is derived, and the limits of every signal: `README.md` at the plugin root. Read it before answering a question about what a number means or why a line shows no origin.
