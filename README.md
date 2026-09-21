<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/logo-dark.svg">
    <img src="docs/logo-light.svg" width="220" alt="A hand holding a lit match">
  </picture>
</p>

<h1 align="center">proudhuman</h1>

<p align="center">The story of a pull request, told from the Claude Code transcripts that produced it.<br>Your steering is the subject. Claude's build is the material.</p>

---

You shipped it with Claude Code. Afterwards nobody can say what you decided, what you checked, where you said no, or that you engineered it at all. The transcripts know. proudhuman reads them and writes you the story of one PR: a self-contained HTML page in six chapters, with illustrations, charts, and a citation on every fact. Where the record holds little of you, it says so plainly.

It is for you, about your own work. It is not a scorecard.

## Install

```
claude plugin marketplace add dimitritholen/proudhuman
claude plugin install proudhuman@proudhuman
```

Needs Python 3.10 or newer on the path. No Python dependencies. Restart Claude Code after installing.

## Use

In any repository with merged pull requests, ask Claude Code in your own words:

- "What did I actually do on PR 16?"
- "Tell me the story of this branch."
- "Who is accountable for #42, and was it reviewed by a human?"

Or type the skill directly:

```
/proudhuman:proudhuman 16
/proudhuman:proudhuman --branch feat/checkout
```

Claude runs the analysis, hands the facts to a prose-writer agent that sees nothing but those facts and the writing rules, renders the page, and tells you where it is. Stories land in `~/.proudhuman/<repo>/pr<N>/story.html`, outside the repository. Open the file in a browser; it works offline, follows your light or dark preference, and prints with one chapter per page. Add "in Dutch" to get the story in Dutch.

**What you get**

1. **The Spark**: your first typed turn, in your own words.
2. **The Steering**: every steer, what the build turned to next, and a timeline of your marks over Claude's activity.
3. **Moments of Judgment**: every interrupt, refused tool call, and file you changed by hand, told as a scene.
4. **The Build**: what Claude wrote, moved, and iterated on; the commits and who ran each.
5. **The Ship**: who pressed merge, how, and every attempt before it.
6. **What the Record Cannot See**: reading, thinking, and silent deciding, named rather than guessed.

Two finished examples are in [`examples/`](examples/): a rich story, [tasqx PR 16](examples/tasqx-pr16/story.html), and a thin one, [tasqx PR 13](examples/tasqx-pr13/story.html), where one pasted prompt and nothing else is exactly what the story says.

## Run it by hand

```
python skills/proudhuman/scripts/proudhuman.py analyze --repo C:\dev\myrepo --pr 16
python skills/proudhuman/scripts/proudhuman.py render ~/.proudhuman/myrepo/pr16
```

The first pass writes `beats.json`; the second renders `story.html` from it and a `prose.json`. Without prose, the page renders with every slot marked unwritten, which is useful for checking a template change.

## Read more

- [How it works](docs/how-it-works.md): what is read, what each beat means, how the charts are made, and where the signals stop.
- [Why the model never writes the HTML](docs/adr/0001-prose-in-slots.md).
- [Vocabulary](CONTEXT.md) and [the prose rules](skills/proudhuman/PROSE-RULES.md).

MIT licence.
