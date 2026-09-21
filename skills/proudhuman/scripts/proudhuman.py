#!/usr/bin/env python3
"""proudhuman: map the human's role in a merged PR from Claude Code transcripts.

Reads the Claude Code session transcripts (JSONL) that touched a PR's head
branch, plus the PR's git range, and writes a markdown report answering:

  - who is the accountable human (commit author, committer, merger) and what
    evidence shows they acted
  - which human turns framed, constrained, verified, or rescued the work
  - which added lines have no origin in any AI-emitted text (human, or a
    formatter)
  - which human prompts are verbatim AI output from an earlier session
    (the pass-through / meat-proxy loop)

Every signal is a proxy. The report says "no evidence of review" where that is
what the data shows; it never says "not reviewed".

Usage:
  python proudhuman.py --repo C:\\dev\\tasqx --pr 13
  python proudhuman.py --repo C:\\dev\\tasqx --branch feat/x --base main

Reports land in ~/.proudhuman/<repo>/<pr>.md unless --out is given. They are
private self-review material and stay outside the repository.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

HUMAN_PROMPT_SOURCES = {"typed", "queued", "suggestion_accepted"}
TRIVIAL_LINE = re.compile(r"^[\s{}()\[\];,.'\"`/*#\-=+<>|&:]*$")
MIN_LINE_LEN = 8
PASSTHROUGH_PROBE = 160  # chars of a prompt to look up in earlier AI output


# ---------------------------------------------------------------- git side


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if out.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout


def parse_ts(s: str) -> datetime:
    s = s.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(s).astimezone(timezone.utc)


@dataclass
class Commit:
    sha: str
    author: str
    author_email: str
    when: datetime
    subject: str
    has_trailer: bool
    attributed: str = "unknown"  # ai-bash | human-bash | unknown
    evidence: str = ""


@dataclass
class PR:
    number: int | None
    head: str
    base_sha: str
    head_sha: str
    merge_sha: str | None
    merged_at: datetime | None
    merger: str | None
    commits: list[Commit]


def find_pr(repo: Path, number: int, trunk: str) -> PR:
    subj_re = re.compile(rf"Merge pull request #{number}\b.*?from (?:\S+?/)?(\S+)")
    for line in git(repo, "log", trunk, "--merges", "--first-parent", "--format=%H%x1f%cI%x1f%cn%x1f%s").splitlines():
        sha, when, committer, subject = line.split("\x1f")
        m = subj_re.search(subject)
        if not m:
            continue
        head = m.group(1)
        return PR(number, head, f"{sha}^1", f"{sha}^2", sha, parse_ts(when), committer, load_commits(repo, f"{sha}^1", f"{sha}^2"))
    raise SystemExit(f"no merge commit for PR #{number} on {trunk}")


def find_branch(repo: Path, branch: str, base: str) -> PR:
    base_sha = git(repo, "merge-base", base, branch).strip()
    return PR(None, branch, base_sha, branch, None, None, None, load_commits(repo, base_sha, branch))


def load_commits(repo: Path, base: str, head: str) -> list[Commit]:
    out = git(repo, "log", "--reverse", f"{base}..{head}", "--format=%H%x1f%an%x1f%ae%x1f%cI%x1f%s%x1f%(trailers:key=Claude-Session,valueonly)%x1e")
    commits = []
    for rec in out.split("\x1e"):
        rec = rec.strip()
        if not rec:
            continue
        sha, an, ae, when, subject, trailer = (rec.split("\x1f") + [""])[:6]
        commits.append(Commit(sha, an, ae, parse_ts(when), subject, bool(trailer.strip())))
    return commits


def added_lines(repo: Path, base: str, head: str) -> tuple[dict[str, list[str]], set[str]]:
    """Added lines per file, and the set of removed lines (to recognise moved code)."""
    diff = git(repo, "diff", "--unified=0", "--no-color", base, head)
    files: dict[str, list[str]] = defaultdict(list)
    removed: set[str] = set()
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[4:].removeprefix("b/")
        elif line.startswith("--- "):
            continue
        elif line.startswith("+") and current:
            files[current].append(line[1:])
        elif line.startswith("-"):
            removed.add(line[1:].strip())
    return files, removed


# ---------------------------------------------------------- transcript side


def encode_cwd(p: Path) -> str:
    return re.sub(r"[:\\/.]", "-", str(p))


@dataclass
class Record:
    session: str
    line: int
    raw: dict

    @property
    def type(self) -> str:
        return self.raw.get("type", "")

    @property
    def ts(self) -> datetime | None:
        t = self.raw.get("timestamp")
        return parse_ts(t) if t else None

    @property
    def branch(self) -> str | None:
        return self.raw.get("gitBranch")

    @property
    def content(self):
        return (self.raw.get("message") or {}).get("content")


def load_session_dir(d: Path) -> dict[str, list[Record]]:
    """Main transcripts keyed by session id; subagent files are folded into their parent."""
    sessions: dict[str, list[Record]] = {}
    for f in sorted(d.glob("*.jsonl")):
        sid = f.stem
        recs = read_jsonl(f, sid)
        sub = d / sid
        if sub.is_dir():
            for sf in sorted(sub.rglob("*.jsonl")):
                for r in read_jsonl(sf, sid):
                    r.raw.setdefault("isSidechain", True)
                    recs.append(r)
        sessions[sid] = recs
    return sessions


def read_jsonl(f: Path, sid: str) -> list[Record]:
    out = []
    with open(f, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(Record(sid, i, json.loads(line)))
            except json.JSONDecodeError:
                continue
    return out


# ------------------------------------------------------------ human events


@dataclass
class Event:
    kind: str  # framing | typed | slash | shell | interrupt | rejection | user-modified | question
    ts: datetime
    session: str
    line: int
    text: str
    dwell_s: float | None = None
    on_branch: bool = True


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(x.get("text", "") for x in content if isinstance(x, dict) and x.get("type") == "text")
    return ""


def is_human_typed(r: Record) -> bool:
    if r.type != "user" or r.raw.get("isMeta") or r.raw.get("isSidechain"):
        return False
    c = r.content
    if not isinstance(c, str):
        return False
    src = r.raw.get("promptSource")
    if src is not None:
        return src in HUMAN_PROMPT_SOURCES
    return not c.lstrip().startswith("<")


def extract_events(recs: list[Record], head: str, window: tuple[datetime, datetime] | None) -> list[Event]:
    events: list[Event] = []
    last_assistant_ts: datetime | None = None
    # A session's first typed turn is its framing, but only for sessions that actually worked on the
    # branch; a session matched by time window alone contributes only its in-window turns.
    first_typed_seen = not any(r.branch == head for r in recs)
    for r in recs:
        ts = r.ts
        if r.type == "assistant" and not r.raw.get("isSidechain") and ts:
            last_assistant_ts = ts
            continue
        if r.type != "user" or r.raw.get("isSidechain") or not ts:
            continue
        on_branch = r.branch == head
        in_window = bool(window and window[0] <= ts <= window[1])
        c = r.content
        dwell = (ts - last_assistant_ts).total_seconds() if last_assistant_ts else None

        # The session's first typed turn is the framing, wherever the checkout was at the time.
        if not first_typed_seen and is_human_typed(r):
            first_typed_seen = True
            events.append(Event("framing", ts, r.session, r.line, c, dwell, on_branch))
            continue
        if not (on_branch or in_window):
            continue

        if isinstance(c, str):
            if r.raw.get("isMeta"):
                continue
            if c.lstrip().startswith("<bash-input>"):
                cmd = re.sub(r"</?bash-input>", "", c).strip()
                events.append(Event("shell", ts, r.session, r.line, cmd, dwell, on_branch))
            elif c.lstrip().startswith("<command-name>"):
                name = re.search(r"<command-name>(.*?)</command-name>", c, re.S)
                args = re.search(r"<command-args>(.*?)</command-args>", c, re.S)
                events.append(Event("slash", ts, r.session, r.line, f"{name.group(1).strip() if name else '?'} {args.group(1).strip() if args else ''}".strip(), dwell, on_branch))
            elif is_human_typed(r):
                kind = "question" if re.search(r"\?\s*$|^\s*(why|how|what|where|which|waarom|hoe|wat)\b", c.strip(), re.I | re.M) else "typed"
                events.append(Event(kind, ts, r.session, r.line, c, dwell, on_branch))
            continue

        if isinstance(c, list):
            txt = text_of(c)
            if "[Request interrupted by user" in txt:
                events.append(Event("interrupt", ts, r.session, r.line, txt.strip(), dwell, on_branch))
                continue
            dumped = json.dumps(c)
            if "doesn't want to proceed" in dumped or r.raw.get("toolUseResult") == "User rejected tool use":
                events.append(Event("rejection", ts, r.session, r.line, "tool call rejected by user", dwell, on_branch))
            tur = r.raw.get("toolUseResult")
            if isinstance(tur, dict) and tur.get("userModified") is True:
                events.append(Event("user-modified", ts, r.session, r.line, str(tur.get("filePath", "")), dwell, on_branch))
    return events


# ---------------------------------------------------------- AI emitted text


def ai_emitted_lines(recs: list[Record]) -> tuple[set[str], set[str]]:
    """(lines written through tools, lines merely said in chat)."""
    written: set[str] = set()
    said: set[str] = set()
    for r in recs:
        if r.type != "assistant":
            continue
        c = r.content
        if not isinstance(c, list):
            continue
        for b in c:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text":
                for ln in b.get("text", "").splitlines():
                    ln = ln.strip()
                    if len(ln) >= MIN_LINE_LEN and not TRIVIAL_LINE.match(ln):
                        said.add(ln)
            elif b.get("type") == "tool_use":
                inp = b.get("input") or {}
                blobs = []
                for k in ("new_string", "content", "command", "new_source"):
                    v = inp.get(k)
                    if isinstance(v, str):
                        blobs.append(v)
                for e in inp.get("edits") or []:
                    if isinstance(e, dict) and isinstance(e.get("new_string"), str):
                        blobs.append(e["new_string"])
                for blob in blobs:
                    for ln in blob.splitlines():
                        ln = ln.strip()
                        if len(ln) >= MIN_LINE_LEN and not TRIVIAL_LINE.match(ln):
                            written.add(ln)
    return written, said


def ai_bash_commands(recs: list[Record]) -> list[tuple[datetime, str, str, int]]:
    out = []
    for r in recs:
        if r.type != "assistant" or not r.ts:
            continue
        c = r.content
        if not isinstance(c, list):
            continue
        for b in c:
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash":
                out.append((r.ts, (b.get("input") or {}).get("command", ""), r.session, r.line))
    return out


# ---------------------------------------------------------- pass-through


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def find_passthrough(prompt: str, all_sessions: dict[str, list[Record]], own_session: str, own_ts: datetime) -> tuple[str, int, str] | None:
    probe = normalize(prompt)[:PASSTHROUGH_PROBE]
    if len(probe) < 60:
        return None
    for sid, recs in all_sessions.items():
        for r in recs:
            if r.type != "assistant" or not r.ts or r.ts >= own_ts:
                continue
            c = r.content
            if not isinstance(c, list):
                continue
            for b in c:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and probe in normalize(b.get("text", "")):
                    return sid, r.line, "assistant text"
                if b.get("type") == "tool_use":
                    inp = b.get("input") or {}
                    for k in ("content", "new_string"):
                        v = inp.get(k)
                        if isinstance(v, str) and probe in normalize(v):
                            return sid, r.line, f"{b.get('name')} {k} -> {inp.get('file_path', '')}"
    return None


def merge_attribution(pr: PR, all_sessions: dict[str, list[Record]]) -> str:
    """Every merge attempt in any session of the project, ordered by distance to the merge time."""
    if not pr.merge_sha:
        return "not merged"
    pat = re.compile(rf"\bpr merge\b.*\b{pr.number}\b|\bgit merge\b.*{re.escape(pr.head)}", re.S) if pr.number else re.compile(rf"\bgit merge\b.*{re.escape(pr.head)}", re.S)
    attempts: list[tuple[float, str]] = []
    for sid, recs in all_sessions.items():
        results = {}
        for r in recs:
            if r.type == "user" and isinstance(r.content, list):
                for b in r.content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        results[b.get("tool_use_id")] = b
        for r in recs:
            if not r.ts:
                continue
            delta = (r.ts - pr.merged_at).total_seconds()
            if r.type == "user" and isinstance(r.content, str) and r.content.lstrip().startswith("<bash-input>") and pat.search(r.content):
                cmd = re.sub(r"</?bash-input>", "", r.content)
                attempts.append((abs(delta), f"human ran `{short(cmd, 80)}` (`{sid[:8]}:{r.line}`, {delta:+.0f}s from merge time)"))
            if r.type == "assistant" and isinstance(r.content, list):
                for b in r.content:
                    if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash" and pat.search((b.get("input") or {}).get("command", "")):
                        res = results.get(b.get("id")) or {}
                        out = res.get("content")
                        out = out if isinstance(out, str) else text_of(out)
                        outcome = "error" if res.get("is_error") or re.search(r"error|failed|protected|not mergeable|Required", out or "", re.I) else "ok"
                        attempts.append((abs(delta), f"AI ran `{short((b.get('input') or {}).get('command', ''), 80)}` (`{sid[:8]}:{r.line}`, {delta:+.0f}s from merge time, result: {outcome}: {short(out or '', 60)})"))
    if not attempts:
        # No command found. Look for a typed human turn mentioning the merge within 10 minutes of it.
        for sid, recs in all_sessions.items():
            for r in recs:
                if is_human_typed(r) and r.ts and abs((r.ts - pr.merged_at).total_seconds()) <= 600 and re.search(r"\bmerge", r.content, re.I):
                    delta = (r.ts - pr.merged_at).total_seconds()
                    return f"no merge command in any transcript (GitHub UI or another machine); the human typed `{short(r.content, 60)}` {delta:+.0f}s from the merge time (`{sid[:8]}:{r.line}`)"
        return "not found in any transcript (GitHub UI, another machine, or unmatched session)"
    attempts.sort(key=lambda a: a[0])
    lines = [attempts[0][1] + " ← closest to the merge time"] + [a[1] for a in attempts[1:]]
    return "; ".join(lines) if len(lines) == 1 else "\n  - " + "\n  - ".join(lines)


# ---------------------------------------------------------------- report


def fmt_ts(t: datetime | None) -> str:
    return t.strftime("%Y-%m-%d %H:%M:%SZ") if t else "?"


def short(s: str, n: int = 100) -> str:
    s = normalize(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def build_report(repo: Path, pr: PR, sessions_used: dict[str, list[Record]], all_sessions: dict[str, list[Record]], events: list[Event], attribution: dict, merge_ev: str, passthroughs: list[tuple[Event, tuple[str, int, str]]]) -> str:
    L: list[str] = []
    title = f"PR #{pr.number}" if pr.number else f"branch {pr.head}"
    L.append(f"# proudhuman — {repo.name} {title} (`{pr.head}`)")
    L.append("")
    L.append("Developer self-review. Every signal below is a proxy for reading and judgment, which are unobservable. Absence of a signal means *no evidence*, not *did not happen*.")
    L.append("")

    # accountable human
    L.append("## Accountable human")
    authors = sorted({(c.author, c.author_email) for c in pr.commits})
    L.append(f"- Commit author(s): {', '.join(f'{a} <{e}>' for a, e in authors) or 'none'}")
    L.append(f"- Merged: {fmt_ts(pr.merged_at)} by `{pr.merger}` (git committer of the merge)" if pr.merge_sha else "- Not merged")
    L.append(f"- Merge action in transcripts: {merge_ev}")
    L.append("")

    # commits
    L.append("## Commits and who ran `git commit`")
    L.append("")
    L.append("| when (UTC) | sha | subject | committed by | evidence |")
    L.append("|---|---|---|---|---|")
    for c in pr.commits:
        L.append(f"| {fmt_ts(c.when)} | `{c.sha[:8]}` | {short(c.subject, 70)} | {c.attributed} | {c.evidence} |")
    n_trailer = sum(c.has_trailer for c in pr.commits)
    L.append("")
    L.append(f"{n_trailer} of {len(pr.commits)} commits carry a `Claude-Session` trailer. The trailer does not identify a transcript; sessions were matched by `gitBranch`, `cwd` and time window.")
    L.append("")

    # sessions
    L.append("## Sessions matched")
    L.append("")
    for sid, recs in sessions_used.items():
        on = sum(1 for r in recs if r.branch == pr.head and r.type in ("user", "assistant"))
        first = min((r.ts for r in recs if r.ts), default=None)
        last = max((r.ts for r in recs if r.ts), default=None)
        L.append(f"- `{sid}`: {on} conversation records on `{pr.head}`, {fmt_ts(first)} → {fmt_ts(last)}")
    if not sessions_used:
        L.append("- none. No transcript in the project directory mentions this branch or overlaps the PR's time window.")
    L.append("")

    # human events
    by_kind = defaultdict(list)
    for e in events:
        by_kind[e.kind].append(e)
    L.append("## Human turns and actions")
    L.append("")
    L.append("| kind | count |")
    L.append("|---|---|")
    for k in ("framing", "typed", "question", "slash", "shell", "interrupt", "rejection", "user-modified"):
        L.append(f"| {k} | {len(by_kind.get(k, []))} |")
    L.append("")
    typed = by_kind.get("framing", []) + by_kind.get("typed", []) + by_kind.get("question", [])
    typed.sort(key=lambda e: e.ts)
    L.append("### Typed by the human")
    L.append("")
    if typed:
        L.append("| when (UTC) | dwell before | chars | where | text |")
        L.append("|---|---|---|---|---|")
        for e in typed:
            dwell = f"{e.dwell_s:.0f}s" if e.dwell_s is not None else "—"
            L.append(f"| {fmt_ts(e.ts)} | {dwell} | {len(e.text)} | `{e.session[:8]}:{e.line}` | {short(e.text)} |")
    else:
        L.append("None on this branch or inside the PR's time window.")
    L.append("")
    L.append("### Constraint events (interrupts, rejections)")
    L.append("")
    cons = sorted(by_kind.get("interrupt", []) + by_kind.get("rejection", []), key=lambda e: e.ts)
    L.extend(f"- {fmt_ts(e.ts)} `{e.session[:8]}:{e.line}` {e.kind}: {short(e.text, 80)}" for e in cons) if cons else L.append("None recorded.")
    L.append("")
    L.append("### Verification and shell actions by the human (`!` commands, slash commands, files touched between AI edits)")
    L.append("")
    ver = sorted(by_kind.get("shell", []) + by_kind.get("slash", []) + by_kind.get("user-modified", []), key=lambda e: e.ts)
    L.extend(f"- {fmt_ts(e.ts)} `{e.session[:8]}:{e.line}` {e.kind}: `{short(e.text, 90)}`" for e in ver) if ver else L.append("None recorded.")
    L.append("")

    # line attribution
    L.append("## Added lines with no origin in AI-emitted text")
    L.append("")
    L.append("Each non-trivial added line in the PR diff was looked up in every string the AI wrote through a tool (Edit, Write, MultiEdit, Bash, NotebookEdit; main session and subagents). Unmatched lines came from a human, a formatter, a generator, or a transcript not matched to this PR.")
    L.append("")
    L.append("| file | added (non-trivial) | AI-written | moved from elsewhere in the diff | only said in chat | no origin |")
    L.append("|---|---|---|---|---|---|")
    tot = [0, 0, 0, 0, 0]
    samples: list[tuple[str, str]] = []
    for f, st in attribution.items():
        L.append(f"| `{f}` | {st['total']} | {st['written']} | {st['moved']} | {st['said']} | {st['none']} |")
        for i, k in enumerate(("total", "written", "moved", "said", "none")):
            tot[i] += st[k]
        samples.extend((f, s) for s in st["samples"])
    L.append(f"| **all** | {tot[0]} | {tot[1]} | {tot[2]} | {tot[3]} | {tot[4]} |")
    L.append("")
    if samples:
        L.append("Sample of lines with no origin:")
        L.append("")
        for f, s in samples[:12]:
            L.append(f"- `{f}`: `{short(s, 90)}`")
        L.append("")

    # pass-through
    L.append("## Pass-through prompts (human input that is verbatim earlier AI output)")
    L.append("")
    if passthroughs:
        for e, (sid, ln, where) in passthroughs:
            L.append(f"- Prompt at {fmt_ts(e.ts)} (`{e.session[:8]}:{e.line}`, {len(e.text)} chars) originates in session `{sid[:8]}` line {ln} ({where}).")
    else:
        L.append("None detected among prompts longer than 60 characters.")
    L.append("")

    # verdict lines
    L.append("## What the evidence supports")
    L.append("")
    if not sessions_used:
        L.append("- No transcript matched this branch. Nothing can be said about the human's role from Claude Code data; the work may have been done in another tool, on another machine, or in a project directory this tool did not scan.")
        L.append("")
        return "\n".join(L)
    n_human_signals = sum(len(by_kind.get(k, [])) for k in ("typed", "question", "interrupt", "rejection", "user-modified", "shell"))
    if not typed and n_human_signals == 0:
        L.append("- No evidence of review by the human on this branch: no typed turns, no interrupts, no rejections, no shell commands, no files touched between AI edits.")
    else:
        L.append(f"- Human signals on the branch: {n_human_signals} (typed turns after framing, questions, interrupts, rejections, shell actions, files touched).")
    if tot[4] == 0 and tot[0] > 0:
        L.append(f"- Every non-trivial added line has an origin in AI-emitted text or was moved from elsewhere in the diff ({tot[2]} moved). No evidence of hand-written code.")
    elif tot[0] > 0:
        L.append(f"- {tot[4]} of {tot[0]} non-trivial added lines have no origin in AI-emitted text ({tot[2]} more were moved from elsewhere in the diff). These may be hand-written, formatter output, or from an unmatched session.")
    if passthroughs:
        L.append(f"- {len(passthroughs)} prompt(s) are verbatim earlier AI output: the meat-proxy loop, in the thread's words.")
    L.append(f"- Merge: {merge_ev}")
    L.append("")
    return "\n".join(L)


# ------------------------------------------------------------------ main


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--pr", type=int)
    ap.add_argument("--branch")
    ap.add_argument("--base", default="main")
    ap.add_argument("--projects-dir", default=str(Path.home() / ".claude" / "projects"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if args.base == "main" and subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "-q", "main"], capture_output=True).returncode != 0:
        args.base = "master"
    if args.pr:
        pr = find_pr(repo, args.pr, args.base)
    elif args.branch:
        pr = find_branch(repo, args.branch, args.base)
    else:
        raise SystemExit("give --pr N or --branch NAME")
    if not pr.commits:
        raise SystemExit("no commits in range")

    window = (min(c.when for c in pr.commits) - timedelta(hours=1), pr.merged_at or max(c.when for c in pr.commits) + timedelta(hours=1))

    pdir = Path(args.projects_dir) / encode_cwd(repo)
    if not pdir.is_dir():
        raise SystemExit(f"no transcript directory {pdir}")
    all_sessions = load_session_dir(pdir)

    used: dict[str, list[Record]] = {}
    for sid, recs in all_sessions.items():
        hit = any(r.branch == pr.head for r in recs) or any(
            r.ts and window[0] <= r.ts <= window[1] and str(r.raw.get("cwd", "")).lower().startswith(str(repo).lower()) for r in recs
        )
        if hit:
            used[sid] = recs

    events: list[Event] = []
    written_all: set[str] = set()
    said_all: set[str] = set()
    bash_cmds = []
    for sid, recs in used.items():
        events.extend(extract_events(recs, pr.head, window))
        w, s = ai_emitted_lines(recs)
        written_all |= w
        said_all |= s
        bash_cmds.extend(ai_bash_commands(recs))
    events.sort(key=lambda e: e.ts)

    # commit attribution
    for c in pr.commits:
        for ts, cmd, sid, ln in bash_cmds:
            if "git commit" in cmd and abs((ts - c.when).total_seconds()) <= 180:
                c.attributed, c.evidence = "AI (Bash tool)", f"`{sid[:8]}:{ln}` {abs((ts - c.when).total_seconds()):.0f}s before commit"
                break
        else:
            for e in events:
                if e.kind == "shell" and "git commit" in e.text and abs((e.ts - c.when).total_seconds()) <= 180:
                    c.attributed, c.evidence = "human (`!` shell)", f"`{e.session[:8]}:{e.line}`"
                    break
            else:
                c.attributed, c.evidence = "not in matched transcripts", "hand commit, other tool, or unmatched session"

    merge_ev = merge_attribution(pr, all_sessions)

    # line attribution
    attribution: dict[str, dict] = {}
    added, removed = added_lines(repo, pr.base_sha, pr.head_sha)
    for f, lines in added.items():
        st = {"total": 0, "written": 0, "moved": 0, "said": 0, "none": 0, "samples": []}
        for ln in lines:
            s = ln.strip()
            if len(s) < MIN_LINE_LEN or TRIVIAL_LINE.match(s):
                continue
            st["total"] += 1
            if s in written_all:
                st["written"] += 1
            elif s in removed:
                st["moved"] += 1
            elif s in said_all:
                st["said"] += 1
            else:
                st["none"] += 1
                if len(st["samples"]) < 3:
                    st["samples"].append(s)
        attribution[f] = st

    # pass-through
    passthroughs = []
    for e in events:
        if e.kind in ("framing", "typed", "question"):
            hit = find_passthrough(e.text, all_sessions, e.session, e.ts)
            if hit:
                passthroughs.append((e, hit))

    report = build_report(repo, pr, used, all_sessions, events, attribution, merge_ev, passthroughs)
    out = Path(args.out) if args.out else Path.home() / ".proudhuman" / repo.name / f"{'pr' + str(pr.number) if pr.number else pr.head.replace('/', '_')}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"wrote {out}")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(report)


if __name__ == "__main__":
    main()
