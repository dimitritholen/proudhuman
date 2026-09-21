# proudhuman — tasqx PR #13 (`fix/daemon-field-test-findings`)

Developer self-review. Every signal below is a proxy for reading and judgment, which are unobservable. Absence of a signal means *no evidence*, not *did not happen*.

## Accountable human
- Commit author(s): Dimitri Tholen <dtholen@gmail.com>
- Merged: 2026-08-31 11:04:32Z by `GitHub` (git committer of the merge)
- Merge action in transcripts: 
  - AI ran `cd C:/dev/tasqx && gh pr merge 13 --merge --admin --delete-branch 2>&1 | tail -…` (`c3eb310f:1261`, -279s from merge time, result: error: Permission for this action was denied by the Claude Code au…) ← closest to the merge time
  - AI ran `cd C:/dev/tasqx && gh pr merge 13 --merge --delete-branch 2>&1 | tail -2 && git…` (`c3eb310f:1250`, -304s from merge time, result: ok: To have the pull request merged after all the requirements …)

## Commits and who ran `git commit`

| when (UTC) | sha | subject | committed by | evidence |
|---|---|---|---|---|
| 2026-08-31 08:55:30Z | `33e5320c` | fix(daemon): the shutdown that exited before its writers drained, and… | AI (Bash tool) | `c3eb310f:352` 1s before commit |
| 2026-08-31 09:05:25Z | `b3545748` | fix(cli): the socket flag four verbs accepted and discarded, and the … | AI (Bash tool) | `c3eb310f:590` 0s before commit |
| 2026-08-31 09:27:47Z | `bbf527ba` | feat(daemon): the store nobody could name, and the retirement nothing… | AI (Bash tool) | `c3eb310f:972` 1s before commit |
| 2026-08-31 09:38:43Z | `32ac74a9` | fix(daemon): the banner that preceded its own bind, the gap marker th… | AI (Bash tool) | `c3eb310f:1180` 0s before commit |
| 2026-08-31 09:38:44Z | `06636aa3` | fix(mcp): the schema that read as the inverse of the server, and the … | AI (Bash tool) | `c3eb310f:1180` 1s before commit |

0 of 5 commits carry a `Claude-Session` trailer. The trailer does not identify a transcript; sessions were matched by `gitBranch`, `cwd` and time window.

## Sessions matched

- `c3eb310f-b806-40bc-ba31-26321e60dd77`: 462 conversation records on `fix/daemon-field-test-findings`, 2026-08-31 08:35:16Z → 2026-08-31 11:06:05Z

## Human turns and actions

| kind | count |
|---|---|
| framing | 1 |
| typed | 0 |
| question | 0 |
| slash | 0 |
| shell | 0 |
| interrupt | 0 |
| rejection | 0 |
| user-modified | 0 |

### Typed by the human

| when (UTC) | dwell before | chars | where | text |
|---|---|---|---|---|
| 2026-08-31 08:35:16Z | — | 4743 | `c3eb310f:6` | Pick up the tasqx daemon field test where the 2026-08-31 session left it. **State, verified at hand… |

### Constraint events (interrupts, rejections)

None recorded.

### Verification and shell actions by the human (`!` commands, slash commands, files touched between AI edits)

None recorded.

## Added lines with no origin in AI-emitted text

Each non-trivial added line in the PR diff was looked up in every string the AI wrote through a tool (Edit, Write, MultiEdit, Bash, NotebookEdit; main session and subagents). Unmatched lines came from a human, a formatter, a generator, or a transcript not matched to this PR.

| file | added (non-trivial) | AI-written | moved from elsewhere in the diff | only said in chat | no origin |
|---|---|---|---|---|---|
| `DESIGN.md` | 25 | 19 | 0 | 0 | 6 |
| `crates/tasqx-cli/src/docs.rs` | 27 | 26 | 0 | 0 | 1 |
| `crates/tasqx-cli/src/lib.rs` | 196 | 195 | 0 | 0 | 1 |
| `crates/tasqx-cli/tests/daemon_visibility.rs` | 244 | 239 | 0 | 0 | 5 |
| `crates/tasqx-cli/tests/regressions.rs` | 46 | 45 | 0 | 0 | 1 |
| `crates/tasqx-core/src/daemon.rs` | 244 | 243 | 0 | 0 | 1 |
| `crates/tasqx-core/src/engine.rs` | 19 | 19 | 0 | 0 | 0 |
| `crates/tasqx-core/src/mcp.rs` | 8 | 8 | 0 | 0 | 0 |
| `crates/tasqx-core/tests/conformance.rs` | 4 | 4 | 0 | 0 | 0 |
| `crates/tasqx-core/tests/daemon.rs` | 96 | 96 | 0 | 0 | 0 |
| `crates/tasqx-core/tests/mcp.rs` | 33 | 27 | 0 | 0 | 6 |
| **all** | 942 | 921 | 0 | 0 | 21 |

Sample of lines with no origin:

- `DESIGN.md`: `| **Daemon (opt-in)** | Long-lived clients: TUI, GUI, watch mode (not the MCP server, whi…`
- `DESIGN.md`: `- **socket / named pipe (daemon):** the *identical* request objects, newline-delimited an…`
- `DESIGN.md`: `The MCP server is **a long-lived stdio host over the in-process core** (§4, D73 — earlier…`
- `crates/tasqx-cli/src/docs.rs`: `real["result"]["store"] = serde_json::Value::String("~/.local/share/tasqx/tasks.db".into(…`
- `crates/tasqx-cli/src/lib.rs`: `Ok(PathBuf::from("/home/u/.local/tasqx/tasks.db")),`
- `crates/tasqx-cli/tests/daemon_visibility.rs`: `assert!(out.status.success(), "list through the daemon: {stderr}");`
- `crates/tasqx-cli/tests/daemon_visibility.rs`: `for line in std::io::BufReader::new(stderr)`
- `crates/tasqx-cli/tests/daemon_visibility.rs`: `.map_while(Result::ok)`
- `crates/tasqx-cli/tests/regressions.rs`: `.args(args)`
- `crates/tasqx-core/src/daemon.rs`: `"a settled debt must not re-announce"`
- `crates/tasqx-core/tests/mcp.rs`: `for load_bearing in [`
- `crates/tasqx-core/tests/mcp.rs`: `"omitted",`

## Pass-through prompts (human input that is verbatim earlier AI output)

- Prompt at 2026-08-31 08:35:16Z (`c3eb310f:6`, 4743 chars) originates in session `3ee0a556` line 805 (Write content -> C:\dev\tasqx\docs\reviews\NEXT-daemon-fixes-prompt.md).

## What the evidence supports

- Human signals on the branch: 0 (typed turns after framing, questions, interrupts, rejections, shell actions, files touched).
- 21 of 942 non-trivial added lines have no origin in AI-emitted text (0 more were moved from elsewhere in the diff). These may be hand-written, formatter output, or from an unmatched session.
- 1 prompt(s) are verbatim earlier AI output: the meat-proxy loop, in the thread's words.
- Merge: 
  - AI ran `cd C:/dev/tasqx && gh pr merge 13 --merge --admin --delete-branch 2>&1 | tail -…` (`c3eb310f:1261`, -279s from merge time, result: error: Permission for this action was denied by the Claude Code au…) ← closest to the merge time
  - AI ran `cd C:/dev/tasqx && gh pr merge 13 --merge --delete-branch 2>&1 | tail -2 && git…` (`c3eb310f:1250`, -304s from merge time, result: ok: To have the pull request merged after all the requirements …)
