"""Render at the CLI seam, on committed fixtures.

Uses the golden beats and prose under examples/ (tasqx PR 16, rich; PR 13,
thin). Nothing here touches ~/.claude/projects or the network.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "proudhuman" / "scripts" / "proudhuman.py"
EXAMPLES = ROOT / "examples"
CHAPTER_ORDER = ["spark", "steering", "judgment", "build", "ship", "unseen"]


def render(fixture: str, mutate=None, lang: str | None = None) -> tuple[str, subprocess.CompletedProcess, Path]:
    tmp = Path(tempfile.mkdtemp())
    d = tmp / fixture
    shutil.copytree(EXAMPLES / fixture, d)
    if lang:
        b = json.loads((d / "beats.json").read_text(encoding="utf-8"))
        b["options"]["lang"] = lang
        (d / "beats.json").write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
    if mutate:
        p = json.loads((d / "prose.json").read_text(encoding="utf-8"))
        mutate(p)
        (d / "prose.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), "render", str(d)], capture_output=True, text=True, encoding="utf-8")
    html = (d / "story.html").read_text(encoding="utf-8") if (d / "story.html").is_file() else ""
    return html, proc, d


class RichStoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html, cls.proc, cls.dir = render("tasqx-pr16")
        cls.prose = json.loads((EXAMPLES / "tasqx-pr16" / "prose.json").read_text(encoding="utf-8"))
        cls.beats = json.loads((EXAMPLES / "tasqx-pr16" / "beats.json").read_text(encoding="utf-8"))

    def test_renders(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        self.assertTrue(self.html)

    def test_six_chapters_in_order(self):
        ids = re.findall(r'<section class="chapter" id="(\w+)">', self.html)
        self.assertEqual(ids, CHAPTER_ORDER)

    def test_every_slot_in_place_and_nothing_unwritten(self):
        for ch in CHAPTER_ORDER:
            self.assertIn(self.prose["chapters"][ch]["lede"][:40], self.html)
        for cit, cap in self.prose["steer_captions"].items():
            self.assertIn(cap[:40].replace("'", "&#x27;").replace('"', "&quot;"), self.html)
        self.assertNotIn('class="unwritten"', self.html)
        self.assertIn(self.prose["title"], self.html)

    def test_no_script_no_network(self):
        self.assertNotIn("<script", self.html.lower())
        self.assertNotRegex(self.html, r'(src|href)="https?://')
        self.assertNotIn("@import", self.html)
        self.assertNotIn("url(http", self.html)

    def test_charts_present(self):
        bands = len(re.findall(r'class="band-label"', self.html))
        self.assertEqual(bands, len(self.beats["sessions"]))
        self.assertIn('class="chart composition"', self.html)
        self.assertIn('class="chart strip"', self.html)
        rows = len(re.findall(r'class="row-label"', self.html))
        self.assertEqual(rows, min(8, len(self.beats["composition"]["files"])))

    def test_print_stylesheet_and_details(self):
        self.assertIn("@media print", self.html)
        self.assertIn("<details", self.html)

    def test_citations_are_footnoted(self):
        marks = re.findall(r'class="cite" id="c-(\d+)"', self.html)
        notes = re.findall(r'<li id="fn-(\d+)">', self.html)
        self.assertTrue(marks)
        self.assertEqual(sorted(set(marks), key=int), sorted(notes, key=int))

    def test_unwritten_block_when_slot_missing(self):
        def drop(p):
            del p["chapters"]["build"]["body"]
        html, proc, _ = render("tasqx-pr16", drop)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('class="unwritten"', html)
        self.assertIn("chapters.build.body", html)

    def test_unwritten_block_when_slot_over_bound(self):
        def bloat(p):
            p["chapters"]["ship"]["lede"] = "word " * 200
        html, _, _ = render("tasqx-pr16", bloat)
        self.assertIn("chapters.ship.lede", html)

    def test_title_falls_back_to_subject(self):
        def no_title(p):
            del p["title"]
        html, _, _ = render("tasqx-pr16", no_title)
        self.assertIn(f'<h1>{self.beats["pr"]["subject"]}</h1>'.replace("'", "&#x27;"), html)

    def test_dutch_chrome(self):
        html, _, _ = render("tasqx-pr16", lang="nl")
        self.assertIn("Wat het Verslag Niet Ziet", html)
        self.assertIn('lang="nl"', html)

    def test_deterministic(self):
        again, _, _ = render("tasqx-pr16")
        self.assertEqual(self.html, again)


class ThinStoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html, cls.proc, _ = render("tasqx-pr13")

    def test_fixed_sentences_in_empty_chapters(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        self.assertIn("The record holds no steer after the spark.", self.html)
        self.assertIn("The record holds no moment where you overruled Claude.", self.html)
        self.assertNotIn('class="unwritten"', self.html)

    def test_muted_scenes_and_no_charts(self):
        self.assertGreaterEqual(self.html.count('class="scene muted"'), 2)
        self.assertNotIn('class="chart timeline"', self.html)
        self.assertNotIn('class="chart strip"', self.html)

    def test_passthrough_named(self):
        self.assertIn("NEXT-daemon-fixes-prompt.md", self.html)


class GoldenTest(unittest.TestCase):
    """Byte-for-byte against the committed rendering. Update deliberately when the template changes."""

    def test_matches_committed_story(self):
        for fixture in ("tasqx-pr16", "tasqx-pr13"):
            golden = EXAMPLES / fixture / "story.html"
            if not golden.is_file():
                self.skipTest(f"no committed story for {fixture}")
            html, _, _ = render(fixture)
            self.assertEqual(html, golden.read_text(encoding="utf-8"), f"{fixture} differs from the committed story; run tests/update_golden.py if the change is intended")


if __name__ == "__main__":
    unittest.main()
