"""Analyze at the CLI seam, on a synthetic fixture.

The test builds a temporary git repository with one merged PR and a temporary
transcripts directory with one hand-written session, runs `proudhuman.py
analyze`, and asserts on beats.json. Nothing here touches the real
~/.claude/projects.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "proudhuman" / "scripts" / "proudhuman.py"
SESSION = "11111111-2222-3333-4444-555555555555"


def encode_cwd(p: Path) -> str:
    return re.sub(r"[:\\/.]", "-", str(p))


def git(repo: Path, *args: str, env: dict | None = None) -> str:
    e = {**os.environ, "GIT_AUTHOR_NAME": "Ada Tester", "GIT_AUTHOR_EMAIL": "ada@example.test", "GIT_COMMITTER_NAME": "Ada Tester", "GIT_COMMITTER_EMAIL": "ada@example.test", **(env or {})}
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", env=e)
    if out.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {out.stderr}")
    return out.stdout


def commit(repo: Path, when: datetime, msg: str, env: dict | None = None) -> str:
    stamp = when.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg, env={"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp, **(env or {})})
    return git(repo, "rev-parse", "HEAD").strip()


def iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S.000Z")


class Fixture:
    """A merged PR #7 on branch feat/greeting, and a session that worked on it."""

    def __init__(self, base: Path):
        self.repo = base / "repo"
        self.projects = base / "projects"
        self.root = base / "stories"
        self.repo.mkdir()
        self.t0 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
        self.build_repo()
        self.build_transcript()

    def build_repo(self):
        r = self.repo
        git(r, "init", "-q", "-b", "main")
        (r / "app.py").write_text("def hello():\n    return 'hello'\n", encoding="utf-8")
        (r / "old.py").write_text("def relocated_function_body():\n    return 42\n", encoding="utf-8")
        commit(r, self.t0, "chore: base")
        git(r, "checkout", "-q", "-b", "feat/greeting")
        (r / "app.py").write_text("def hello(name):\n    return f'hello {name}'\n\n\ndef farewell(name):\n    return f'bye {name}'\n", encoding="utf-8")
        self.c1 = commit(r, self.t0 + timedelta(minutes=30), "feat: greet by name")
        (r / "old.py").unlink()
        (r / "new.py").write_text("def relocated_function_body():\n    return 42\n\n\ndef handwritten_helper_nobody_emitted():\n    return 'human'\n", encoding="utf-8")
        self.c2 = commit(r, self.t0 + timedelta(minutes=50), "refactor: move helper")
        git(r, "checkout", "-q", "main")
        stamp = (self.t0 + timedelta(minutes=70)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        git(r, "merge", "-q", "--no-ff", "-m", "Merge pull request #7 from ada/feat/greeting", "feat/greeting", env={"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp})

    def rec(self, t: datetime, **kw) -> dict:
        base = {"sessionId": SESSION, "cwd": str(self.repo), "gitBranch": "feat/greeting", "timestamp": iso(t), "version": "2.1.0", "isSidechain": False}
        base.update(kw)
        return base

    def build_transcript(self):
        d = self.projects / encode_cwd(self.repo.resolve())
        d.mkdir(parents=True)
        t = self.t0
        rows = []
        # spark, on the branch
        rows.append(self.rec(t + timedelta(minutes=5), type="user", promptSource="typed", origin={"kind": "human"}, message={"role": "user", "content": "Make hello take a name and add a farewell function, keep it small."}))
        rows.append(self.rec(t + timedelta(minutes=6), type="assistant", message={"role": "assistant", "content": [{"type": "text", "text": "I'll edit app.py."}, {"type": "tool_use", "id": "tu1", "name": "Edit", "input": {"file_path": str(self.repo / "app.py"), "old_string": "def hello():\n    return 'hello'\n", "new_string": "def hello(name):\n    return f'hello {name}'\n\n\ndef farewell(name):\n    return f'bye {name}'\n"}}]}))
        rows.append(self.rec(t + timedelta(minutes=6, seconds=5), type="user", message={"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu1", "content": "ok", "is_error": False}]}, toolUseResult={"filePath": str(self.repo / "app.py"), "userModified": False}))
        # a test run and a tool error
        rows.append(self.rec(t + timedelta(minutes=7), type="assistant", message={"role": "assistant", "content": [{"type": "tool_use", "id": "tu2", "name": "Bash", "input": {"command": "pytest -q"}}]}))
        rows.append(self.rec(t + timedelta(minutes=7, seconds=10), type="user", message={"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu2", "content": "boom", "is_error": True}]}))
        # a steer that is a question, then Claude touches app.py next
        rows.append(self.rec(t + timedelta(minutes=8), type="user", promptSource="typed", origin={"kind": "human"}, message={"role": "user", "content": "why did the test fail?"}))
        rows.append(self.rec(t + timedelta(minutes=9), type="assistant", message={"role": "assistant", "content": [{"type": "text", "text": "The fixture was stale. Fixing it."}, {"type": "tool_use", "id": "tu3", "name": "Edit", "input": {"file_path": str(self.repo / "app.py"), "old_string": "x", "new_string": "y"}}]}))
        rows.append(self.rec(t + timedelta(minutes=9, seconds=5), type="user", message={"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu3", "content": "ok", "is_error": False}]}))
        # a rejected tool call, then the human's next words
        rows.append(self.rec(t + timedelta(minutes=10), type="assistant", message={"role": "assistant", "content": [{"type": "text", "text": "Let me delete old.py."}, {"type": "tool_use", "id": "tu4", "name": "Bash", "input": {"command": "rm old.py"}}]}))
        rows.append(self.rec(t + timedelta(minutes=10, seconds=30), type="user", message={"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu4", "content": "The user doesn't want to proceed with this tool use. The tool use was rejected."}]}, toolUseResult="User rejected tool use"))
        rows.append(self.rec(t + timedelta(minutes=11), type="user", promptSource="typed", origin={"kind": "human"}, message={"role": "user", "content": "no, move the helper into new.py first"}))
        # an interrupt
        rows.append(self.rec(t + timedelta(minutes=12), type="assistant", message={"role": "assistant", "content": [{"type": "text", "text": "Moving the helper now."}]}))
        rows.append(self.rec(t + timedelta(minutes=12, seconds=20), type="user", message={"role": "user", "content": [{"type": "text", "text": "[Request interrupted by user]"}]}))
        # a verification typed by the human
        rows.append(self.rec(t + timedelta(minutes=13), type="user", message={"role": "user", "content": "<bash-input>pytest -q</bash-input>"}))
        rows.append(self.rec(t + timedelta(minutes=13, seconds=4), type="user", message={"role": "user", "content": "<bash-stdout>1 passed</bash-stdout><bash-stderr></bash-stderr>"}))
        # a housekeeping slash command that must not count
        rows.append(self.rec(t + timedelta(minutes=14), type="user", message={"role": "user", "content": "<command-name>/clear</command-name>\n<command-message>clear</command-message>\n<command-args></command-args>"}))
        # Claude commits, one second before the commit time
        rows.append(self.rec(t + timedelta(minutes=29, seconds=59), type="assistant", message={"role": "assistant", "content": [{"type": "tool_use", "id": "tu5", "name": "Bash", "input": {"command": "git add -A && git commit -m 'feat: greet by name'"}}]}))
        rows.append(self.rec(t + timedelta(minutes=30, seconds=2), type="user", message={"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu5", "content": "[feat/greeting abc] feat: greet by name", "is_error": False}]}))
        # a merge attempt by Claude that fails, and the human's own merge
        rows.append(self.rec(t + timedelta(minutes=68), type="assistant", message={"role": "assistant", "content": [{"type": "tool_use", "id": "tu6", "name": "Bash", "input": {"command": "gh pr merge 7 --merge"}}]}))
        rows.append(self.rec(t + timedelta(minutes=68, seconds=5), type="user", message={"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu6", "content": "X Pull request #7 is not mergeable: required status checks", "is_error": True}]}))
        rows.append(self.rec(t + timedelta(minutes=70, seconds=10), type="user", message={"role": "user", "content": "<bash-input>gh pr merge 7 --merge --admin</bash-input>"}))
        with open(d / f"{SESSION}.jsonl", "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")


def run_analyze(fx: Fixture, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "analyze", "--repo", str(fx.repo), "--pr", "7", "--projects-dir", str(fx.projects), "--root", str(fx.root), *extra], capture_output=True, text=True, encoding="utf-8")


class AnalyzeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.fx = Fixture(Path(cls.tmp.name))
        cls.proc = run_analyze(cls.fx)
        cls.beats_path = cls.fx.root / "repo" / "pr7" / "beats.json"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def beats(self) -> dict:
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        self.assertTrue(self.beats_path.is_file(), self.proc.stdout)
        return json.loads(self.beats_path.read_text(encoding="utf-8"))

    def test_pr_and_sessions(self):
        b = self.beats()
        self.assertEqual(b["schema_version"], 1)
        self.assertEqual(b["pr"]["number"], 7)
        self.assertEqual(b["pr"]["head"], "feat/greeting")
        self.assertEqual(b["pr"]["subject"], "refactor: move helper")
        self.assertEqual(len(b["sessions"]), 1)
        self.assertEqual(b["sessions"][0]["matched_by"], "branch")
        self.assertEqual(b["accountable"]["authors"][0]["name"], "Ada Tester")

    def test_spark_and_steers(self):
        b = self.beats()
        self.assertTrue(b["spark"]["excerpt"].startswith("Make hello take a name"))
        self.assertEqual(b["spark"]["citation"], f"{SESSION}:1")
        self.assertIsNone(b["spark"]["passthrough_origin"])
        steers = b["steers"]
        self.assertEqual([s["excerpt"] for s in steers], ["why did the test fail?", "no, move the helper into new.py first"])
        self.assertTrue(steers[0]["is_question"])
        self.assertFalse(steers[1]["is_question"])
        self.assertTrue(any(p.endswith("app.py") for p in steers[0]["consequence"]))
        self.assertEqual(steers[0]["dwell_s"], 60)

    def test_judgments(self):
        b = self.beats()
        kinds = [j["kind"] for j in b["judgments"]]
        self.assertEqual(kinds, ["rejection", "interrupt"])
        rej = b["judgments"][0]
        self.assertEqual(rej["content"]["tool"], "Bash")
        self.assertEqual(rej["content"]["input_excerpt"], "rm old.py")
        self.assertEqual(rej["next_turn"]["excerpt"], "no, move the helper into new.py first")
        self.assertEqual(b["judgments"][1]["content"]["last_claude_text"], "Moving the helper now.")

    def test_verifications_skip_housekeeping(self):
        b = self.beats()
        self.assertEqual([v["text"] for v in b["verifications"]], ["pytest -q", "gh pr merge 7 --merge --admin"])

    def test_commit_attribution(self):
        b = self.beats()
        by_subject = {c["subject"]: c for c in b["commits"]}
        self.assertEqual(by_subject["feat: greet by name"]["run_by"], "claude")
        self.assertEqual(by_subject["feat: greet by name"]["citation"], f"{SESSION}:17")
        self.assertEqual(by_subject["refactor: move helper"]["run_by"], "unknown")

    def test_ship(self):
        b = self.beats()
        s = b["ship"]
        self.assertEqual(s["status"], "merged")
        self.assertEqual([a["who"] for a in s["attempts"]], ["claude", "human"])
        self.assertEqual(s["attempts"][0]["outcome"], "error")
        self.assertTrue(s["attempts"][1]["closest"])

    def test_composition(self):
        b = self.beats()
        files = {f["path"]: f for f in b["composition"]["files"]}
        self.assertEqual(files["app.py"]["emitted"], files["app.py"]["added"])
        self.assertEqual(files["new.py"]["moved"], 2)
        self.assertEqual(files["new.py"]["none"], 2)
        self.assertTrue(any("handwritten_helper" in s for s in files["new.py"]["samples"]))

    def test_iterations_and_presence(self):
        b = self.beats()
        it = b["claude_iterations"]
        self.assertEqual(it["tool_errors"], 2)
        self.assertEqual(it["test_runs"], 1)
        self.assertEqual(b["presence"]["sessions"], 1)
        self.assertGreater(b["presence"]["seconds"], 3600)

    def test_every_transcript_beat_has_a_citation(self):
        b = self.beats()
        for coll in ("steers", "judgments", "verifications"):
            for e in b[coll]:
                self.assertRegex(e["citation"], r"^[0-9a-f-]{36}:\d+$")


class NoSessionTest(unittest.TestCase):
    def test_stops_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = Fixture(Path(tmp))
            empty = Path(tmp) / "empty-projects" / encode_cwd(fx.repo.resolve())
            empty.mkdir(parents=True)
            proc = subprocess.run([sys.executable, str(SCRIPT), "analyze", "--repo", str(fx.repo), "--pr", "7", "--projects-dir", str(empty.parent), "--root", str(fx.root / "x")], capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("no session matched", proc.stderr)
            self.assertFalse((fx.root / "x").exists())


if __name__ == "__main__":
    unittest.main()
