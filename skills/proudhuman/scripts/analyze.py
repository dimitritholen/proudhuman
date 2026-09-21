"""proudhuman analyze: extract the beats of one pull request from Claude Code transcripts.

A beat is one dated, cited fact the story is built from. Everything here is a
proxy for reading and judgment, which leave no trace; the beats say what the
record holds and nothing more.

Vocabulary: CONTEXT.md at the plugin root.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA_VERSION = 1
HUMAN_PROMPT_SOURCES = {"typed", "queued", "suggestion_accepted"}
TRIVIAL_LINE = re.compile(r"^[\s{}()\[\];,.'\"`/*#\-=+<>|&:]*$")
MIN_LINE_LEN = 8
PASSTHROUGH_PROBE = 160
EXCERPT_CHARS = 200
CONSEQUENCE_CALLS = 5
TEST_COMMANDS = re.compile(r"\b(pytest|cargo test|npm test|pnpm test|yarn test|go test|dotnet test|mix test|rspec|jest|vitest|make test)\b")
HOUSEKEEPING_COMMANDS = {"clear", "compact", "exit", "quit", "help", "cost", "status", "resume", "config", "model", "login", "logout"}
QUESTION = re.compile(r"\?\s*$|^\s*(why|how|what|where|which|waarom|hoe|wat|welke|waar)\b", re.I | re.M)


class AnalyzeError(SystemExit):
    pass


# ---------------------------------------------------------------- helpers


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise AnalyzeError(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.strip().replace("Z", "+00:00")).astimezone(timezone.utc)


def iso(t: datetime | None) -> str | None:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ") if t else None


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def excerpt(s: str, n: int = EXCERPT_CHARS) -> str:
    s = normalize(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def encode_cwd(p: Path) -> str:
    return re.sub(r"[:\\/.]", "-", str(p))


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(x.get("text", "") for x in content if isinstance(x, dict) and x.get("type") == "text")
    return ""


# ---------------------------------------------------------------- git side


@dataclass
class Commit:
    sha: str
    author: str
    email: str
    when: datetime
    subject: str
    has_trailer: bool


@dataclass
class PR:
    number: int | None
    subject: str
    head: str
    base: str
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
        commits = load_commits(repo, f"{sha}^1", f"{sha}^2")
        title = commits[-1].subject if commits else subject
        return PR(number, title, head, trunk, git(repo, "rev-parse", f"{sha}^1").strip(), git(repo, "rev-parse", f"{sha}^2").strip(), sha, parse_ts(when), committer, commits)
    raise AnalyzeError(f"no merge commit for PR #{number} on {trunk}")


def find_branch(repo: Path, branch: str, base: str) -> PR:
    base_sha = git(repo, "merge-base", base, branch).strip()
    commits = load_commits(repo, base_sha, branch)
    title = commits[-1].subject if commits else branch
    return PR(None, title, branch, base, base_sha, git(repo, "rev-parse", branch).strip(), None, None, None, commits)


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


def diff_lines(repo: Path, base: str, head: str) -> tuple[dict[str, list[str]], set[str]]:
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


# ---------------------------------------------------------- transcripts


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

    @property
    def sidechain(self) -> bool:
        return bool(self.raw.get("isSidechain"))

    @property
    def citation(self) -> str:
        return f"{self.session}:{self.line}"

    def tool_uses(self):
        c = self.content
        if self.type == "assistant" and isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    yield b

    def tool_results(self):
        c = self.content
        if self.type == "user" and isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    yield b


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


def load_sessions(d: Path) -> dict[str, list[Record]]:
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


def is_human_typed(r: Record) -> bool:
    if r.type != "user" or r.raw.get("isMeta") or r.sidechain:
        return False
    c = r.content
    if not isinstance(c, str):
        return False
    src = r.raw.get("promptSource")
    if src is not None:
        return src in HUMAN_PROMPT_SOURCES
    return not c.lstrip().startswith("<")


def is_rejection(r: Record) -> bool:
    if r.raw.get("toolUseResult") == "User rejected tool use":
        return True
    return any("doesn't want to proceed" in json.dumps(b.get("content", "")) for b in r.tool_results())


def is_interrupt(r: Record) -> bool:
    return r.type == "user" and isinstance(r.content, list) and "[Request interrupted by user" in text_of(r.content)


def result_text(b: dict) -> str:
    c = b.get("content")
    return c if isinstance(c, str) else text_of(c)


# ------------------------------------------------------------ extraction


def ai_written_lines(recs: list[Record]) -> tuple[set[str], set[str]]:
    written: set[str] = set()
    said: set[str] = set()
    for r in recs:
        if r.type != "assistant" or not isinstance(r.content, list):
            continue
        for b in r.content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text":
                for ln in b.get("text", "").splitlines():
                    ln = ln.strip()
                    if len(ln) >= MIN_LINE_LEN and not TRIVIAL_LINE.match(ln):
                        said.add(ln)
            elif b.get("type") == "tool_use":
                inp = b.get("input") or {}
                blobs = [v for k in ("new_string", "content", "command", "new_source") if isinstance((v := inp.get(k)), str)]
                blobs += [e["new_string"] for e in inp.get("edits") or [] if isinstance(e, dict) and isinstance(e.get("new_string"), str)]
                for blob in blobs:
                    for ln in blob.splitlines():
                        ln = ln.strip()
                        if len(ln) >= MIN_LINE_LEN and not TRIVIAL_LINE.match(ln):
                            written.add(ln)
    return written, said


def find_passthrough(prompt: str, all_sessions: dict[str, list[Record]], own_ts: datetime) -> dict | None:
    probe = normalize(prompt)[:PASSTHROUGH_PROBE]
    if len(probe) < 60:
        return None
    for sid in sorted(all_sessions):
        for r in all_sessions[sid]:
            if r.type != "assistant" or not r.ts or r.ts >= own_ts or not isinstance(r.content, list):
                continue
            for b in r.content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and probe in normalize(b.get("text", "")):
                    return {"session": sid, "line": r.line, "citation": r.citation, "where": "assistant text"}
                if b.get("type") == "tool_use":
                    inp = b.get("input") or {}
                    for k in ("content", "new_string"):
                        v = inp.get(k)
                        if isinstance(v, str) and probe in normalize(v):
                            return {"session": sid, "line": r.line, "citation": r.citation, "where": f"{b.get('name')} {k}", "path": inp.get("file_path", "")}
    return None


def consequence(recs: list[Record], start: int) -> list[str]:
    """File paths from Claude's next few tool calls after index `start` in the main session."""
    paths: list[str] = []
    calls = 0
    for r in recs[start + 1:]:
        if r.sidechain or r.type != "assistant":
            continue
        for b in r.tool_uses():
            calls += 1
            p = (b.get("input") or {}).get("file_path") or (b.get("input") or {}).get("notebook_path")
            if isinstance(p, str) and p not in paths:
                paths.append(p)
            if calls >= CONSEQUENCE_CALLS:
                return paths
    return paths


def next_typed(recs: list[Record], start: int) -> dict | None:
    for r in recs[start + 1:]:
        if is_human_typed(r) and r.ts:
            return {"ts": iso(r.ts), "citation": r.citation, "excerpt": excerpt(r.content)}
    return None


def last_claude_text(recs: list[Record], start: int) -> str:
    for r in reversed(recs[:start]):
        if r.type == "assistant" and not r.sidechain:
            t = text_of(r.content)
            if t.strip():
                return excerpt(t)
    return ""


def session_events(recs: list[Record], head: str, window: tuple[datetime, datetime], tool_use_index: dict[str, tuple[str, dict]]) -> dict:
    """Spark, steers, judgments and verifications of one session, in order."""
    out = {"spark": None, "steers": [], "judgments": [], "verifications": []}
    last_assistant: datetime | None = None
    on_branch_session = any(r.branch == head for r in recs)
    spark_seen = not on_branch_session
    for i, r in enumerate(recs):
        ts = r.ts
        if r.type == "assistant" and not r.sidechain and ts:
            last_assistant = ts
            continue
        if r.type != "user" or r.sidechain or not ts:
            continue
        dwell = round((ts - last_assistant).total_seconds()) if last_assistant else None
        c = r.content
        if not spark_seen and is_human_typed(r):
            spark_seen = True
            out["spark"] = {"ts": iso(ts), "dwell_s": dwell, "excerpt": excerpt(c), "text": c, "citation": r.citation, "on_branch": r.branch == head}
            continue
        in_scope = r.branch == head or (window[0] <= ts <= window[1])
        if not in_scope:
            continue
        if isinstance(c, str):
            if r.raw.get("isMeta"):
                continue
            if c.lstrip().startswith("<bash-input>"):
                out["verifications"].append({"kind": "shell", "ts": iso(ts), "citation": r.citation, "text": re.sub(r"</?bash-input>", "", c).strip()})
            elif c.lstrip().startswith("<command-name>"):
                name = re.search(r"<command-name>(.*?)</command-name>", c, re.S)
                args = re.search(r"<command-args>(.*?)</command-args>", c, re.S)
                cmd = name.group(1).strip() if name else "?"
                if cmd.lstrip("/") in HOUSEKEEPING_COMMANDS:
                    continue
                out["verifications"].append({"kind": "slash", "ts": iso(ts), "citation": r.citation, "text": f"{cmd} {args.group(1).strip() if args else ''}".strip()})
            elif is_human_typed(r):
                out["steers"].append({"ts": iso(ts), "dwell_s": dwell, "excerpt": excerpt(c), "text": c, "citation": r.citation, "is_question": bool(QUESTION.search(c.strip())), "consequence": consequence(recs, i)})
            continue
        if isinstance(c, list):
            if is_interrupt(r):
                out["judgments"].append({"kind": "interrupt", "ts": iso(ts), "citation": r.citation, "content": {"last_claude_text": last_claude_text(recs, i)}, "next_turn": next_typed(recs, i)})
                continue
            if is_rejection(r):
                tool, inp_excerpt = "", ""
                for b in r.tool_results():
                    hit = tool_use_index.get(b.get("tool_use_id", ""))
                    if hit:
                        tool = hit[0]
                        inp = hit[1]
                        qs = inp.get("questions")
                        first_q = qs[0].get("question") if isinstance(qs, list) and qs and isinstance(qs[0], dict) else None
                        inp_excerpt = excerpt(inp.get("command") or inp.get("new_string") or inp.get("content") or inp.get("file_path") or first_q or json.dumps(inp, ensure_ascii=False))
                out["judgments"].append({"kind": "rejection", "ts": iso(ts), "citation": r.citation, "content": {"tool": tool, "input_excerpt": inp_excerpt}, "next_turn": next_typed(recs, i)})
            tur = r.raw.get("toolUseResult")
            if isinstance(tur, dict) and tur.get("userModified") is True:
                out["judgments"].append({"kind": "hand_edit", "ts": iso(ts), "citation": r.citation, "content": {"path": str(tur.get("filePath", ""))}, "next_turn": next_typed(recs, i)})
    return out


def index_tool_uses(recs: list[Record]) -> dict[str, tuple[str, dict]]:
    idx = {}
    for r in recs:
        for b in r.tool_uses():
            idx[b.get("id", "")] = (b.get("name", ""), b.get("input") or {})
    return idx


def iterations(recs: list[Record]) -> dict:
    errors = 0
    tests = 0
    edits: dict[str, int] = defaultdict(int)
    for r in recs:
        for b in r.tool_results():
            if b.get("is_error"):
                errors += 1
        for b in r.tool_uses():
            inp = b.get("input") or {}
            if b.get("name") == "Bash" and TEST_COMMANDS.search(inp.get("command", "")):
                tests += 1
            if b.get("name") in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
                p = inp.get("file_path") or inp.get("notebook_path")
                if isinstance(p, str):
                    edits[p] += 1
    return {"tool_errors": errors, "test_runs": tests, "files_edited_more_than_twice": [{"path": p, "count": n} for p, n in sorted(edits.items()) if n > 2]}


def ai_bash_calls(recs: list[Record]):
    for r in recs:
        if r.type != "assistant" or not r.ts:
            continue
        for b in r.tool_uses():
            if b.get("name") == "Bash":
                yield r.ts, (b.get("input") or {}).get("command", ""), r.citation, b.get("id", "")


def commit_attribution(pr: PR, used: dict[str, list[Record]], verifications: list[dict]) -> list[dict]:
    bash = [c for sid in sorted(used) for c in ai_bash_calls(used[sid])]
    out = []
    for c in pr.commits:
        run_by, evidence, citation = "unknown", "no matching command in the matched sessions", None
        for ts, cmd, cit, _ in bash:
            if "git commit" in cmd and abs((ts - c.when).total_seconds()) <= 180:
                run_by, evidence, citation = "claude", f"Bash tool call {abs((ts - c.when).total_seconds()):.0f}s from the commit time", cit
                break
        else:
            for v in verifications:
                if v["kind"] == "shell" and "git commit" in v["text"] and abs((parse_ts(v["ts"]) - c.when).total_seconds()) <= 180:
                    run_by, evidence, citation = "human", "typed as a shell command", v["citation"]
                    break
        out.append({"sha": c.sha, "short": c.sha[:8], "when": iso(c.when), "author": c.author, "email": c.email, "subject": c.subject, "has_trailer": c.has_trailer, "run_by": run_by, "evidence": evidence, "citation": citation})
    return out


def ship(pr: PR, all_sessions: dict[str, list[Record]]) -> dict:
    if not pr.merge_sha:
        return {"status": "unmerged", "merged_at": None, "merger": None, "attempts": [], "fallback_turn": None}
    pat = re.compile(rf"\bpr merge\b.*\b{pr.number}\b|\bgit merge\b.*{re.escape(pr.head)}", re.S) if pr.number else re.compile(rf"\bgit merge\b.*{re.escape(pr.head)}", re.S)
    attempts = []
    for sid in sorted(all_sessions):
        recs = all_sessions[sid]
        results = {b.get("tool_use_id"): b for r in recs for b in r.tool_results()}
        for r in recs:
            if not r.ts:
                continue
            delta = (r.ts - pr.merged_at).total_seconds()
            if r.type == "user" and isinstance(r.content, str) and r.content.lstrip().startswith("<bash-input>") and pat.search(r.content):
                attempts.append({"who": "human", "ts": iso(r.ts), "delta_s": round(delta), "command": re.sub(r"</?bash-input>", "", r.content).strip(), "outcome": "ran", "output_excerpt": "", "citation": r.citation})
            for b in r.tool_uses():
                if b.get("name") == "Bash" and pat.search((b.get("input") or {}).get("command", "")):
                    res = results.get(b.get("id")) or {}
                    out = result_text(res)
                    outcome = "error" if res.get("is_error") or re.search(r"error|failed|protected|not mergeable|Required", out, re.I) else "ok"
                    attempts.append({"who": "claude", "ts": iso(r.ts), "delta_s": round(delta), "command": (b.get("input") or {}).get("command", ""), "outcome": outcome, "output_excerpt": excerpt(out, 160), "citation": r.citation})
    if attempts:
        closest = min(attempts, key=lambda a: abs(a["delta_s"]))
        for a in attempts:
            a["closest"] = a is closest
        attempts.sort(key=lambda a: a["ts"])
    fallback = None
    if not attempts:
        for sid in sorted(all_sessions):
            for r in all_sessions[sid]:
                if is_human_typed(r) and r.ts and abs((r.ts - pr.merged_at).total_seconds()) <= 600 and re.search(r"\bmerge", r.content, re.I):
                    fallback = {"ts": iso(r.ts), "delta_s": round((r.ts - pr.merged_at).total_seconds()), "excerpt": excerpt(r.content), "citation": r.citation}
                    break
            if fallback:
                break
    return {"status": "merged", "merged_at": iso(pr.merged_at), "merger": pr.merger, "attempts": attempts, "fallback_turn": fallback}


def composition(repo: Path, pr: PR, written: set[str], said: set[str]) -> dict:
    added, removed = diff_lines(repo, pr.base_sha, pr.head_sha)
    files = []
    tot = {"added": 0, "emitted": 0, "moved": 0, "said": 0, "none": 0}
    for f in sorted(added):
        st = {"path": f, "added": 0, "emitted": 0, "moved": 0, "said": 0, "none": 0, "samples": []}
        for ln in added[f]:
            s = ln.strip()
            if len(s) < MIN_LINE_LEN or TRIVIAL_LINE.match(s):
                continue
            st["added"] += 1
            if s in written:
                st["emitted"] += 1
            elif s in removed:
                st["moved"] += 1
            elif s in said:
                st["said"] += 1
            else:
                st["none"] += 1
                if len(st["samples"]) < 3:
                    st["samples"].append(excerpt(s, 120))
        for k in tot:
            tot[k] += st[k]
        files.append(st)
    return {"totals": tot, "files": files, "caveat": "No-origin lines match no text Claude emitted through a tool and no removed line. They may be hand-written, formatter output, or produced by a shell transformation Claude ran. The count is a sample to inspect, not a count of hand-written lines."}


# ------------------------------------------------------------------ main


def analyze(repo: Path, projects_dir: Path, pr_number: int | None, branch: str | None, base: str, lang: str, accent: str | None) -> dict:
    repo = repo.resolve()
    if base == "main" and subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "-q", "main"], capture_output=True).returncode != 0:
        base = "master"
    pr = find_pr(repo, pr_number, base) if pr_number else find_branch(repo, branch, base)
    if not pr.commits:
        raise AnalyzeError("no commits in range")
    window = (min(c.when for c in pr.commits) - timedelta(hours=1), pr.merged_at or max(c.when for c in pr.commits) + timedelta(hours=1))

    pdir = projects_dir / encode_cwd(repo)
    if not pdir.is_dir():
        raise AnalyzeError(f"no transcript directory {pdir}")
    all_sessions = load_sessions(pdir)

    used: dict[str, list[Record]] = {}
    matched_by: dict[str, str] = {}
    for sid in sorted(all_sessions):
        recs = all_sessions[sid]
        if any(r.branch == pr.head for r in recs):
            used[sid], matched_by[sid] = recs, "branch"
        elif any(r.ts and window[0] <= r.ts <= window[1] and str(r.raw.get("cwd", "")).lower().startswith(str(repo).lower()) for r in recs):
            used[sid], matched_by[sid] = recs, "window"
    if not used:
        raise AnalyzeError("no session matched: no transcript in the project directory mentions this branch or overlaps the PR's time window")

    spark = None
    steers, judgments, verifications = [], [], []
    written_all: set[str] = set()
    said_all: set[str] = set()
    sessions_out = []
    presence = 0
    iter_tot = {"tool_errors": 0, "test_runs": 0, "files_edited_more_than_twice": []}
    for sid in sorted(used):
        recs = used[sid]
        ev = session_events(recs, pr.head, window, index_tool_uses(recs))
        if ev["spark"] and (spark is None or ev["spark"]["ts"] < spark["ts"]):
            if spark:
                steers.append({k: v for k, v in spark.items() if k != "on_branch"} | {"is_question": bool(QUESTION.search(spark["text"].strip())), "consequence": []})
            spark = ev["spark"]
        elif ev["spark"]:
            steers.append({k: v for k, v in ev["spark"].items() if k != "on_branch"} | {"is_question": bool(QUESTION.search(ev["spark"]["text"].strip())), "consequence": []})
        steers += ev["steers"]
        judgments += ev["judgments"]
        verifications += ev["verifications"]
        w, s = ai_written_lines(recs)
        written_all |= w
        said_all |= s
        on = [r.ts for r in recs if r.branch == pr.head and r.ts and r.type in ("user", "assistant")]
        span = round((max(on) - min(on)).total_seconds()) if on else 0
        presence += span
        first = min((r.ts for r in recs if r.ts), default=None)
        last = max((r.ts for r in recs if r.ts), default=None)
        sessions_out.append({"id": sid, "first": iso(first), "last": iso(last), "on_branch_records": len(on), "matched_by": matched_by[sid], "presence_s": span, "tool_calls": [iso(r.ts) for r in recs if r.type == "assistant" and not r.sidechain and r.ts and any(True for _ in r.tool_uses())]})
        it = iterations(recs)
        iter_tot["tool_errors"] += it["tool_errors"]
        iter_tot["test_runs"] += it["test_runs"]
        merged: dict[str, int] = {e["path"]: e["count"] for e in iter_tot["files_edited_more_than_twice"]}
        for e in it["files_edited_more_than_twice"]:
            merged[e["path"]] = merged.get(e["path"], 0) + e["count"]
        iter_tot["files_edited_more_than_twice"] = [{"path": p, "count": n} for p, n in sorted(merged.items())]

    steers.sort(key=lambda e: e["ts"])
    judgments.sort(key=lambda e: e["ts"])
    verifications.sort(key=lambda e: e["ts"])

    passthroughs = []
    for turn in ([spark] if spark else []) + steers:
        hit = find_passthrough(turn["text"], all_sessions, parse_ts(turn["ts"]))
        turn["passthrough_origin"] = hit
        if hit:
            passthroughs.append({"turn_citation": turn["citation"], "ts": turn["ts"], "chars": len(turn["text"]), "origin": hit})

    commits = commit_attribution(pr, used, verifications)
    authors = sorted({(c.author, c.email) for c in pr.commits})

    return {
        "schema_version": SCHEMA_VERSION,
        "source": {"repo_name": repo.name, "repo_path": str(repo), "projects_dir": str(pdir)},
        "options": {"lang": lang, "accent": accent},
        "pr": {"number": pr.number, "subject": pr.subject, "head": pr.head, "base": pr.base, "base_sha": pr.base_sha, "head_sha": pr.head_sha, "merge_sha": pr.merge_sha, "merged_at": iso(pr.merged_at)},
        "accountable": {"authors": [{"name": a, "email": e} for a, e in authors], "merger": pr.merger},
        "sessions": sessions_out,
        "presence": {"seconds": presence, "sessions": sum(1 for s in sessions_out if s["on_branch_records"])},
        "spark": spark,
        "steers": steers,
        "judgments": judgments,
        "verifications": verifications,
        "commits": commits,
        "ship": ship(pr, all_sessions),
        "composition": composition(repo, pr, written_all, said_all),
        "passthroughs": passthroughs,
        "claude_iterations": iter_tot,
    }


def story_dir(reports_root: Path, repo_name: str, pr_number: int | None, head: str) -> Path:
    return reports_root / repo_name / (f"pr{pr_number}" if pr_number else head.replace("/", "_"))


def write_beats(beats: dict, d: Path) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    out = d / "beats.json"
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(beats, fh, ensure_ascii=False, indent=2, sort_keys=False)
        fh.write("\n")
    return out
