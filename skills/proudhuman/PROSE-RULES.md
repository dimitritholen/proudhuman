# Prose rules for a proudhuman story

You are writing the prose of one story: the account of one pull request, told from the Claude Code transcripts that produced it, with the human's steering as the subject and Claude's build as the material. You have two inputs and one output.

- Input `beats.json`: every fact the story may use. Each transcript-derived beat carries a `citation` of the form `session:line`.
- Input `slots.json`: the slots you must fill and the word bound of each.
- Output `prose.json`: the filled slots, in the shape shown at the end of this document.

The story is read by the person whose transcripts these are. It is recognition, not surveillance. Where the record holds little of them, it says so plainly.

## What to write

Fill every slot in `slots.json`:

- `title`: at most eight words. A story title, not a summary. The PR number and subject are already in the masthead.
- Six chapters, each a `lede` and a `body`, in the vocabulary of the glossary: the Spark, the Steering, Moments of Judgment, the Build, the Ship, What the Record Cannot See.
- One `steer_caption` per steer, keyed by the steer's citation: one sentence on what the human asked for, and, if the steer carries a `consequence`, what the build turned to next.
- One `judgment_scene` per judgment, keyed by its citation: a short scene built from the judgment's `content` and its `next_turn`, nothing else.

Skip the slots of a chapter that has no beats (`steering` with an empty `steers`, `judgment` with an empty `judgments`). The renderer places a fixed honest sentence there. Write the other chapters as usual, including the Spark and the Unseen.

## How to write

- Second person: the human is "you". Claude is "Claude". Past tense.
- Plain register. No superlatives, no praise words, no filler. A sentence with "remarkable", "impressive", "brilliant" or "seamless" in it is wrong.
- Every sentence traceable to a beat. If no beat supports it, do not write it.
- Intent only where the human's own words support it. "You asked for X" is fine when the steer says X. "You wanted a cleaner design" is not, unless the steer says so.
- Causation only as sequence. A steer's `consequence` lists what Claude touched next; write "next, the build turned to" and never "because you asked, Claude did".
- Quote the human verbatim and in the original language, using the `excerpt` field. Do not translate, correct, or tidy a quote.
- Write the prose in the language named in `options.lang` (`en` or `nl`). Quotes stay as they are.
- A pass-through prompt (a `passthrough_origin` on the spark or a steer) is named in one sentence: the text originated in Claude's own earlier output, with where. No judgment attached.
- The Build chapter tells what Claude produced in service of the steering: the commits it ran, what the composition shows (emitted, moved, no-origin lines), and its iterations as a single line of counts. The no-origin count is described with its caveat and never as lines the human wrote.
- The Ship chapter tells who pressed merge, how, and every attempt before it, from `ship.attempts` and `ship.fallback_turn`. If the status is `unmerged`, it says the work is not shipped yet.
- The Unseen chapter names what leaves no trace: reading, thinking, silent deciding. It uses the wording "the record holds no evidence of" and never "you did not". Its two numbers are `presence.seconds` and `presence.sessions`, phrased as time at the keyboard across sessions, nothing more.
- Thin stories are told straight. One prompt and nothing else is one prompt and nothing else.
- Durations in human units: "27 minutes", "two hours and eighteen minutes", "forty seconds". Never raw seconds.
- A steer caption sits directly under the quoted excerpt, so it never repeats the quote. It says in your own words what was asked for, then what the build turned to next if there is a consequence. When the excerpt already says everything, the caption is the consequence alone, or a single short sentence.
- A judgment scene sits under two lines the page already shows: what Claude was about to do or had just said, and your next words. The scene does not repeat either quote; it tells what the moment was and what changed, in at most three sentences.
- Chapter bodies tell, they do not list. A body that walks every steer with its timestamp is a table in prose; pick the turns that changed the course and let the beats below carry the rest.

## Output shape

```json
{
  "title": "…",
  "chapters": {
    "spark":     {"lede": "…", "body": "…"},
    "steering":  {"lede": "…", "body": "…"},
    "judgment":  {"lede": "…", "body": "…"},
    "build":     {"lede": "…", "body": "…"},
    "ship":      {"lede": "…", "body": "…"},
    "unseen":    {"lede": "…", "body": "…"}
  },
  "steer_captions":  {"<citation>": "…"},
  "judgment_scenes": {"<citation>": "…"}
}
```

Write the file with UTF-8 encoding. Paragraph breaks inside a `body` are a blank line.
