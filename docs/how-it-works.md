# How proudhuman works

The long version of the README: what the analyser reads, what each beat means, how the charts are derived, and where the signals stop.

## Pipeline

Two passes of one script and one plugin agent, per [ADR-0001](adr/0001-prose-in-slots.md):

```
python skills/proudhuman/scripts/proudhuman.py analyze --repo C:\dev\tasqx --pr 16 [--lang nl]
    → ~/.proudhuman/tasqx/pr16/beats.json
(the prose-writer agent reads beats.json, slots.json and PROSE-RULES.md, writes prose.json)
python skills/proudhuman/scripts/proudhuman.py render ~/.proudhuman/tasqx/pr16
    → ~/.proudhuman/tasqx/pr16/story.html
```

Stories live outside the repository. Render needs no model and can be rerun after a template change. A slot the writer missed or overran renders as a visible "Unwritten" block, never as a blank.

## What analyze reads

The PR's git range (`merge^1..merge^2` for a merged PR, `merge-base..branch` for an open branch) and the Claude Code transcripts under `~/.claude/projects/<encoded repo path>/`. A session is matched when any record carries `gitBranch == head branch`, or when records inside the PR's time window have a `cwd` inside the repo. Subagent transcripts in the sibling `<session-id>/` directory are folded into their parent session. The `Claude-Session:` commit trailer is not used; its value matches nothing in the transcripts.

## Beats

`beats.json`, `schema_version` 1. Every transcript-derived beat carries a citation of the form `session:line`.

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

## The page

Six chapters, each headed by a scene: the Spark, the Steering (with the session timeline and the commands you ran yourself), Moments of Judgment (with the judgment strip), the Build (with the composition chart and the commits), the Ship, and What the Record Cannot See.

Charts are inline SVG rendered by the script from the beats. Timeline: one band per session, Claude's tool-call density as a hatched band, your marks on a thread above it, distinguished by shape (star spark, dot steer, ring question, diamond judgment, triangle verification), commits as ticks, the ship as a flag. Composition: one stacked bar for the PR plus the top eight files, segments written by Claude, moved, said in chat, no-origin. Judgment strip: the judgments in order, linked to their scenes.

Colours come from CSS custom properties defined once with `light-dark()`: the human's marks in the accent, Claude's material in graphite, so light, dark and print share one file. The theme selector in the masthead (auto, light, dark) is three radio buttons and a `:has()` rule on the root that sets `color-scheme`; the choice lives for the page view and is not remembered, because the page runs no script. No JavaScript anywhere; expands use `<details>`, hover detail uses `title`.

## Scenes

The six chapter illustrations under `skills/proudhuman/scenes/` were generated with Recraft's vector model through OpenRouter and post-processed into the scene contract: every fill in the ink colour or the paper colour, no gradients, filters, scripts or external references, cropped and fitted into a 320x200 box. `tools/generate_scenes.py` does both steps and needs `OPENROUTER_API_KEY` in the environment or in a `.env` at the plugin root (ignored by git). Raw responses are kept under `scenes/recraft/raw/` so post-processing can be redone without new calls (`--reprocess`); `--preview` writes a comparison page; `--logo` produces the README logo. The earlier hand-drawn set is under `scenes/handmade/`.

## Limits

- Reading and understanding are unobservable. Every signal is a proxy. A fast expert skim and no review look the same; a long dwell with zero comprehension looks like verification. The story says "the record holds no evidence of" where that is what the data shows.
- Lines produced by Claude's shell transformations (a `sed` that adds `pub(crate)` to every function, a formatter run) have no origin in emitted text and land in the no-origin column. It is a sample to inspect, not a count of hand-written lines.
- Line attribution under-credits the human: a line you wrote by hand counts as Claude's if Claude later re-emits it inside a Write or a wide Edit, and `userModified` only fires when an AI edit follows your touch.
- Pass-through detection searches only sessions in the same project directory.
- Sessions matched by time window alone can carry unrelated turns from minutes before the branch started; their spark is not counted, their in-window turns are.
- Work done outside Claude Code (an editor, a GitHub UI merge, another machine) leaves no transcript. The story says so rather than guessing. When no session matches, analyze stops and writes nothing.
- The prose is model-written. The rules bind it to the beats, but a sentence can still be wrong; the citation beside each beat is there so you can check.

## Development

```
python -m unittest discover -s tests -v
python tests/update_golden.py     # after a template change; inspect the diff before committing
```

`tests/test_analyze.py` builds a synthetic git repository and a hand-written transcript in a temp directory and drives `analyze` through the CLI. `tests/test_render.py` drives `render` on the committed fixtures under `examples/` and compares byte-for-byte against the committed stories. Nothing in the tests touches `~/.claude/projects`.

Vocabulary: [CONTEXT.md](../CONTEXT.md). Prose rules: [PROSE-RULES.md](../skills/proudhuman/PROSE-RULES.md). Design notes: [design-notes.md](design-notes.md).
