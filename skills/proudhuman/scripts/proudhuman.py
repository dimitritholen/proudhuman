#!/usr/bin/env python3
"""proudhuman: the story of one pull request, told from the Claude Code transcripts that produced it.

Two passes, per ADR-0001 (the model writes prose into slots; it never produces HTML):

  proudhuman.py analyze --repo <path> --pr <N>          writes <root>/<repo>/pr<N>/beats.json
  proudhuman.py analyze --repo <path> --branch <name>   same, for an unmerged branch
  proudhuman.py render  <story dir>                     reads beats.json + prose.json, writes story.html

<root> is ~/.proudhuman unless --root is given. Stories are private self-review material and stay
outside the repository.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import analyze as A  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="proudhuman")
    sub = ap.add_subparsers(dest="cmd", required=True)

    an = sub.add_parser("analyze", help="extract beats.json for one PR or branch")
    an.add_argument("--repo", required=True)
    an.add_argument("--pr", type=int)
    an.add_argument("--branch")
    an.add_argument("--base", default="main")
    an.add_argument("--projects-dir", default=str(Path.home() / ".claude" / "projects"))
    an.add_argument("--root", default=str(Path.home() / ".proudhuman"))
    an.add_argument("--lang", default="en", choices=["en", "nl"])
    an.add_argument("--accent", default=None)

    rn = sub.add_parser("render", help="assemble story.html from beats.json and prose.json")
    rn.add_argument("story_dir")

    args = ap.parse_args(argv)

    if args.cmd == "analyze":
        if not args.pr and not args.branch:
            ap.error("give --pr N or --branch NAME")
        beats = A.analyze(Path(args.repo), Path(args.projects_dir), args.pr, args.branch, args.base, args.lang, args.accent)
        d = A.story_dir(Path(args.root), beats["source"]["repo_name"], beats["pr"]["number"], beats["pr"]["head"])
        out = A.write_beats(beats, d)
        print(f"wrote {out}")
        print(f"sessions {len(beats['sessions'])}, steers {len(beats['steers'])}, judgments {len(beats['judgments'])}, verifications {len(beats['verifications'])}, passthroughs {len(beats['passthroughs'])}, ship {beats['ship']['status']}")
        return 0

    if args.cmd == "render":
        import render as R  # noqa: E402

        out = R.render_dir(Path(args.story_dir))
        print(f"wrote {out}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
