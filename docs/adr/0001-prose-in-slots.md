---
status: accepted
date: 2026-09-21
---

# The model writes prose into slots; it never produces the story's HTML

The story report is a polished HTML page with illustrations and charts, and its prose has to be written by a model because templated sentences read as accounting. The obvious route is to let the model write the whole page. We decided instead on a two-pass pipeline: the script extracts beats to `beats.json`, a subagent that sees only the beats and the prose rules writes `prose.json` with named slots, and the script renders a fixed template with hand-crafted SVG and deterministic charts, placing the prose into the slots. The model never touches HTML. An unwritten slot renders as a visible block, never as a blank.

## Considered options

- **Model writes the whole page from a design skill.** Maximum freedom, but the visuals vary per run, cannot be snapshot-tested, and a story someone wants to keep must look the same when regenerated.
- **Templated sentences, no model.** Deterministic and cheap, but the output reads as a table in disguise, which is the thing the story exists to replace.
- **Prose in slots (chosen).** Visuals are deterministic and testable against golden samples; the model's variance is confined to the writing, where it is wanted.

## Consequences

- The template, the beats schema, and the slot list form a contract; changing one means changing the others.
- The subagent's isolation is a feature: the story cannot borrow from unrelated context in the main session.
- Rendering never needs a model, so a story can be re-rendered from saved beats and prose after a template change.
