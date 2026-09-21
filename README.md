# proudhuman

Tells the story of one pull request from the Claude Code transcripts that produced it, with the human's steering as the subject and Claude's build as the material.

The tool exists because of a recurring complaint: engineers generate specs, code, tests and reports with Claude Code under "just ship" pressure, without time to read any of it, and afterwards nobody can say what the human decided, checked, or fixed, and nobody notices when they engineered it all. The minority position in that debate is the target here: AI-assisted work is fine when there is a human who understands and is accountable for the output. This tool answers, per PR, who that human is, what the record shows they did, and what it cannot show.

It is developer-facing. Run it on your own PRs. It is not a scorecard for managers, and nothing in a story should be read as one.

## What you get

One story per PR: a self-contained HTML page, no script, no external requests, light and dark by system preference, printable with one chapter per page. Six chapters, each headed by a line-art scene:

1. **The Spark**: your first typed turn, quoted in your own words.
2. **The Steering**: every steer with a one-sentence caption and what the build turned to next; the session timeline (your marks on a thread over Claude's activity); the commands you ran yourself.
3. **Moments of Judgment**: every interrupt, rejected tool call, and file you changed by hand, told as a short scene with Claude's action and your next words.
4. **The Build**: what Claude wrote, moved, and iterated on; the composition of the change; the commits and who ran each.
5. **The Ship**: who pressed merge, how, and every attempt before it.
6. **What the Record Cannot See**: reading, thinking, silent deciding; and your time at the keyboard, phrased as presence.

Every beat carries a citation (session and line in the transcript), shown as a footnote mark. The prose is written by a model from the beats under fixed rules; the visuals are rendered deterministically by the script. Where the record holds little of you, the story says so: "the record holds no steer after the spark". It never invents an arc.

Examples of both a rich story (tasqx PR 16) and a thin one (tasqx PR 13) are under `examples/`; open the `story.html` files.

## Install

This directory is a Claude Code plugin and its own marketplace.

```
claude plugin marketplace add dimitritholen/proudhuman
claude plugin install proudhuman@proudhuman
```

Or from a local checkout: `claude plugin marketplace add C:\dev\proudhuman`. Python 3.10 or newer on the path; no Python dependencies.

That adds one skill, `proudhuman`, and one agent, `prose-writer`. Ask what you did on a PR, who is accountable for a change, or for the story of a branch; or type `/proudhuman:proudhuman 16`.

## How it works

Two passes of one script and one subagent, per [ADR-0001](docs/adr/0001-prose-in-slots.md):

```
python skills/proudhuman/scripts/proudhuman.py analyze --repo C:\dev\tasqx --pr 16 [--lang nl]
    → ~/.proudhuman/tasqx/pr16/beats.json
(the prose-writer agent reads beats.json, slots.json and PROSE-RULES.md, writes prose.json)
python skills/proudhuman/scripts/proudhuman.py render ~/.proudhuman/tasqx/pr16
    → ~/.proudhuman/tasqx/pr16/story.html
```

Stories live outside the repository. Render needs no model and can be rerun after a template change. A slot the writer missed or overran renders as a visible "Unwritten" block, never as a blank.

**What analyze reads.** The PR's git range (`merge^1..merge^2` for a merged PR, `merge-base..branch` for an open branch) and the Claude Code transcripts under `~/.claude/projects/<encoded repo path>/`. A session is matched when any record carries `gitBranch == head branch`, or when records inside the PR's time window have a `cwd` inside the repo. Subagent transcripts in the sibling `<session-id>/` directory are folded into their parent session. The `Claude-Session:` commit trailer is not used; its value matches nothing in the transcripts.

**Beats** (`beats.json`, `schema_version` 1):

| beat | derived from |
|---|---|
| spark | the first typed turn of a session that worked on the branch |
| steers | later typed turns (`promptSource` typed, queued, suggestion_accepted; not meta, not a subagent), with dwell since Claude's last output, a question flag, and the file paths from Claude's next five tool calls |
| judgments | `[Request interrupted by user]`; a tool result saying the user declined, with the tool and an excerpt of its input; an Edit result flagged `userModified`; each with your next typed turn |
| verifications | `!` shell commands and slash commands, except housekeeping (`/clear`, `/compact`, …) |
| commits | git; who ran `git commit`: an AI Bash call within three minutes, a human `!` command, or unknown |
| ship | every `gh pr merge` / `git merge` attempt in any session, human or Claude, with the result and the distance to the merge time; a typed turn mentioning the merge as fallback |
| composition | each non-trivial added line looked up in every string Claude wrote through a tool; lines that also appear as removed lines count as moved; the rest is no-origin |
| pass-through | the first 160 normalised characters of a prompt found in earlier Claude output |
| claude_iterations | tool errors, test runs (by command pattern), files edited more than twice |
| presence | the sum of on-branch spans of the matched sessions |

Vocabulary: [CONTEXT.md](CONTEXT.md). Prose rules: [skills/proudhuman/PROSE-RULES.md](skills/proudhuman/PROSE-RULES.md). Design notes: [docs/design-notes.md](docs/design-notes.md).

## Limits

- Reading and understanding are unobservable. Every signal is a proxy. A fast expert skim and no review look the same; a long dwell with zero comprehension looks like verification. The story says "the record holds no evidence of" where that is what the data shows.
- Lines produced by Claude's shell transformations (a `sed` that adds `pub(crate)` to every function, a formatter run) have no origin in emitted text and land in the no-origin column. It is a sample to inspect, not a count of hand-written lines.
- Line attribution under-credits the human: a line you wrote by hand counts as Claude's if Claude later re-emits it inside a Write or a wide Edit, and `userModified` only fires when an AI edit follows your touch.
- Pass-through detection searches only sessions in the same project directory.
- Sessions matched by time window alone can carry unrelated turns from minutes before the branch started; their spark is not counted, their in-window turns are.
- Work done outside Claude Code (an editor, a GitHub UI merge, another machine) leaves no transcript. The story says so rather than guessing. When no session matches, analyze stops and writes nothing.
- The prose is model-written. The rules bind it to the beats, but a sentence can still be wrong; the citation beside each beat is there so you can check.

## Scenes

The six chapter illustrations under `skills/proudhuman/scenes/` were generated with Recraft's vector model through OpenRouter and post-processed into the scene contract: every fill in the ink colour or the paper colour, no gradients, filters, scripts or external references, one badge group, cropped and fitted into a 320x200 box. `tools/generate_scenes.py` does both steps and needs `OPENROUTER_API_KEY` in the environment or in a `.env` at the plugin root (ignored by git). Raw responses are kept under `scenes/recraft/raw/` so the post-processing can be redone without new calls (`--reprocess`), and `--preview` writes a comparison page. The earlier hand-drawn set is under `scenes/handmade/` and satisfies the same contract.

## Development

```
python -m unittest discover -s tests -v
python tests/update_golden.py     # after a template change; inspect the diff before committing
```

`tests/test_analyze.py` builds a synthetic git repository and a hand-written transcript in a temp directory and drives `analyze` through the CLI. `tests/test_render.py` drives `render` on the committed fixtures under `examples/` and compares byte-for-byte against the committed stories. Nothing in the tests touches `~/.claude/projects`.
