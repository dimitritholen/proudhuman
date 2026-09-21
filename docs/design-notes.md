# Design notes for the story template

Working notes, kept so the next pass does not start from zero. The decisions that bind are in the grill memory and the ADR; this file is the studio's sketchbook.

## Brief

Subject: one pull request, told as the story of the person who steered it. Audience: that person, first; then whoever they show it to. Primary job: let them read their own contribution and believe it.

## Plan

**Colour.** The human is the coloured thread; Claude is the material, in graphite. That is the one semantic rule and everything follows from it.

| token | light | dark | role |
|---|---|---|---|
| paper | `#F5F4F0` | `#161A1F` | page |
| ink | `#1E262E` | `#E6E4DF` | text |
| ink-2 | `#5C6570` | `#A3A9B1` | secondary text |
| rule | `#D9D8D2` | `#2C333B` | hairlines, grid |
| accent | `#1F5E9E` | `#5C9BDD` | the human: marks, scenes, links |
| graphite | `#8A8F98` | `#7A8088` | Claude: activity band, commits, build |

No cream, no terracotta, no near-black. The paper is a cool stone white; the dark surface is blue-black, not tinted `#111`.

**Type.** Display serif with a real voice from the system: Iowan Old Style, Palatino Linotype, Book Antiqua, Georgia. Body sans: system-ui, Segoe UI, Helvetica Neue, Arial. Scale from a 17px base with a 1.25 ratio; serif display at 40/32/24; sans body 17/16 with 1.6 line-height; small 14. Line length 66ch.

**Layout.** One column, left-aligned, 66ch text measure, charts allowed to 88ch. Masthead: kicker line, small PR identity, then the story title large. Each chapter opens with its scene at the left (240px) and the chapter title beside it, the lede under the title, then body, then the chapter's beats. Beats sit on a thin vertical rule with a mark in accent; time and dwell in small ink-2; excerpt in serif italic; caption in sans.

```
┌────────────────────────────────────────────┐
│ kicker                                     │
│ Pull request #16 · subject (small)         │
│ TITLE (serif, large)                       │
│ author · merged 2026-08-31                 │
├────────────────────────────────────────────┤
│ [scene]  The Spark                         │
│          lede                               │
│ body ...                                   │
│ ┃● 08:35  "Pick up the tasqx…"  [Full text]│
│ ┃  caption                                 │
├────────────────────────────────────────────┤
│ [scene]  The Steering                      │
│ ...      timeline chart (full width)       │
└────────────────────────────────────────────┘
```

**Principles.** Spend the boldness on the timeline: the accent thread of human marks over the graphite activity band is the memorable image, the loom. Everything else quiet. Structure encodes information: the vertical rule is a timeline, so the beats are in time order; there are no numbered markers because chapters are named, not counted. No all-caps, no middle dots, no arrows, no monospace for data labels. Sentence case throughout.

## Review against the brief

First draft of the plan had a warm off-white paper and a serif body; both are the generic editorial default. Changed the paper to a cool stone white and the body to a sans so the serif is reserved for what is read as story (title, chapter names, quotes). The timeline was going to be a plain scatter; changed to a band-and-thread so it carries the one semantic rule of the page.

## Palette validation

Categorical pair accent vs graphite, dataviz validator: light passes CVD and normal-vision separation (ΔE 17.9 protan, 20.1 normal); the chroma-floor flag on graphite is by design, Claude's band is meant to read as neutral. Dark pair validated separately; the accent lightened, the graphite darkened until separation held.

## Scenes, second pass

The first set was hand-authored line art by an agent: clean, consistent, a little iconic. The user asked for Recraft's vector model through OpenRouter. It returns filled-path engravings with grey tonal steps, not strokes, so the contract had to bend: fills map to ink at three opacities and white maps to the paper token. Cropped to their own bounds they read as small book engravings, which suits the editorial page better than icons did. The match lying across the frame is the best of them; the tiller's solid mast-top dot is the one artefact of the tone mapping worth fixing by hand some day. Cost per scene $0.08; size per scene up to 109 KB, so a story is ~400 KB.

## Tried and dropped

- Dwell curve: reads as attention. Dropped in the grill.
- Terracotta accent: the generic tell. Dropped.
- Per-chapter numbered markers: the chapters are named, not sequential steps in a process. Dropped.
