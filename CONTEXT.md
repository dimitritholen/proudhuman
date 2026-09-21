# proudhuman

The language of a report that tells the story of one pull request from the Claude Code transcripts that produced it, with the human's steering as the subject and the AI's build as the material.

## Language

### The record

**Transcript**:
A Claude Code session file (JSONL) whose records carry the branch, working directory and time of every turn.
_Avoid_: log, history, chat

**Session**:
One transcript plus the subagent transcripts that belong to it.

**Story**:
The report for one pull request. One PR, one story.
_Avoid_: report, dashboard, scorecard

**Beat**:
One dated, cited fact extracted from the record that the story is built from: a turn, a judgment, a commit, a merge attempt.
_Avoid_: event, signal, data point

**Citation**:
The session id and line number a beat comes from. Every beat has one.
_Avoid_: reference, source

### The human's part

**Spark**:
The first typed turn of a session that worked on the branch: what the human wanted.
_Avoid_: framing, initial prompt, kickoff

**Steer**:
A typed turn after the spark that redirects the work, including a question.
_Avoid_: prompt, instruction, message

**Judgment**:
A moment where the human overruled the AI: an interrupt, a rejected tool call, or a file changed by hand between AI edits.
_Avoid_: intervention, correction, constraint event

**Verification**:
A shell command or slash command the human ran themselves.
_Avoid_: check, test run

**Pass-through**:
A prompt whose text is verbatim earlier AI output. The human relayed rather than wrote it.
_Avoid_: meat-proxy, copy-paste, relay

**Dwell**:
The time between the AI's last output and the human's next turn. Reported as a number, never read as attention.
_Avoid_: think time, reading time, latency

### The AI's part

**Build**:
The AI's thread of work on the branch: tool calls, edits, commits.
_Avoid_: generation, output, AI work

**Emitted line**:
A line of text the AI wrote through a tool (an edit, a file write, a shell command).
_Avoid_: AI-written, generated line

**Moved line**:
An added line that also appears among the diff's removed lines: code relocated, not written.

**No-origin line**:
An added line that matches no emitted line and no removed line. Hand-written, formatter output, or produced by an AI shell transformation; the story never claims which.
_Avoid_: human line, unexplained line

### The ending

**Ship**:
The merge: who pressed it, how, and every attempt before it.
_Avoid_: merge event, landing

**Accountable human**:
The commit author together with whoever shipped.
_Avoid_: owner, responsible party

**The unseen**:
Reading, thinking and silent deciding: the human's work that leaves no trace in the record. Named in every story.
_Avoid_: unknown, gaps, missing data

### The story's form

**Chapter**:
One of six fixed parts of a story: the Spark, the Steering, Moments of Judgment, the Build, the Ship, and What the Record Cannot See.

**Scene**:
A hand-crafted SVG illustration that heads a chapter. Fixed set, lightly parameterised, shipped with the plugin.
_Avoid_: illustration, hero image, graphic

**Slot**:
A named place in the story template where the model's prose goes. Everything outside the slots is rendered from beats.
_Avoid_: placeholder, field, section

**Excerpt**:
The first part of a human turn, quoted verbatim, with the full text behind an expand.
_Avoid_: snippet, summary, paraphrase
