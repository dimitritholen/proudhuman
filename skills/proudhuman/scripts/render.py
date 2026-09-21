"""proudhuman render: assemble story.html from beats.json and prose.json.

Per ADR-0001 the model writes prose into slots and never touches HTML. This
module owns the page: template, scenes, charts, slot validation, citations.
It never calls the clock; two renders of the same inputs are byte-identical.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import charts

HERE = Path(__file__).parent
SCENES = HERE.parent / "scenes"
CHAPTERS = ("spark", "steering", "judgment", "build", "ship", "unseen")
SCENE_FILES = {"spark": "spark.svg", "steering": "tiller.svg", "judgment": "hand.svg", "build": "workshop.svg", "ship": "launch.svg", "unseen": "lantern.svg"}
DEFAULT_ACCENT = {"light": "#1F5E9E", "dark": "#5296DB"}


class RenderError(SystemExit):
    pass


# ------------------------------------------------------------- helpers


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def fmt_dt(s: str | None) -> str:
    return ts(s).strftime("%Y-%m-%d %H:%M") + " UTC" if s else ""


def fmt_hm(s: str | None) -> str:
    return ts(s).strftime("%H:%M") if s else ""


def fmt_dur(seconds: int | None) -> str:
    if seconds is None:
        return ""
    s = int(seconds)
    h, m = divmod(s // 60, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s % 60:02d}s"
    return f"{s}s"


def fmt_delta(seconds: int) -> str:
    sign = "+" if seconds >= 0 else "-"
    return sign + fmt_dur(abs(seconds))


def words(s: str) -> int:
    return len(re.findall(r"\S+", s or ""))


def paras(s: str) -> str:
    return "".join(f"<p>{escape(p.strip())}</p>" for p in re.split(r"\n\s*\n", s.strip()) if p.strip())


def rel(path: str, repo: str) -> tuple[str, bool]:
    """(display path, inside repo?)"""
    p = path.replace("\\", "/")
    r = repo.replace("\\", "/").rstrip("/") + "/"
    if p.lower().startswith(r.lower()):
        return p[len(r):], True
    return p.split("/")[-1], False


# ----------------------------------------------------------- citations


class Cites:
    def __init__(self):
        self.order: list[str] = []

    def mark(self, citation: str | None) -> str:
        if not citation:
            return ""
        if citation not in self.order:
            self.order.append(citation)
        n = self.order.index(citation) + 1
        return f'<a class="cite" id="c-{n}" href="#fn-{n}" title="{escape(citation)}">{n}</a>'

    def footnotes(self, chrome: dict) -> str:
        if not self.order:
            return ""
        def short(c: str) -> str:
            sid, _, line = c.rpartition(":")
            return f"{sid[:8]}:{line}"

        items = "".join(f'<li id="fn-{i + 1}"><span class="fn-n">{i + 1}</span> <span title="{escape(c)}">{escape(short(c))}</span></li>' for i, c in enumerate(self.order))
        sessions = sorted({c.rpartition(":")[0] for c in self.order})
        key = " ".join(f'<span class="fn-key"><span class="mono">{escape(s[:8])}</span> {escape(s)}</span>' for s in sessions)
        return f'<footer class="footnotes" aria-label="{escape(chrome["citations"])}"><h2>{escape(chrome["citations"])}</h2><p class="hint">{escape(chrome["citation_hint"])}</p><ol>{items}</ol><p class="fn-keys">{key}</p></footer>'


# ---------------------------------------------------------------- slots


def slot(prose: dict, path: list[str], bound: int, chrome: dict, kind: str = "body") -> tuple[str, bool]:
    """(html, written?) for one slot; an unwritten block if missing, empty or over bound."""
    cur = prose
    for k in path:
        cur = cur.get(k) if isinstance(cur, dict) else None
        if cur is None:
            break
    name = ".".join(path)
    if isinstance(cur, str) and cur.strip() and words(cur) <= bound:
        return (paras(cur) if kind == "body" else escape(cur.strip())), True
    return f'<span class="unwritten" title="{escape(chrome["unwritten_hint"])}">{escape(chrome["unwritten"])}: {escape(name)}</span>', False


# ---------------------------------------------------------------- scenes


def scene(name: str, badge: int | None, muted: bool) -> str:
    f = SCENES / SCENE_FILES[name]
    if not f.is_file():
        return f'<div class="scene scene-missing"></div>'
    svg = f.read_text(encoding="utf-8")
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg).strip()
    svg = re.sub(r'\bid="title"', f'id="title-{name}"', svg, count=1)
    svg = re.sub(r'aria-labelledby="title"', f'aria-labelledby="title-{name}"', svg, count=1)
    # The badge is an HTML element over the drawing's corner, on a paper disc, so it
    # stays legible whatever the drawing does under it; the SVG's own badge group goes.
    svg = re.sub(r'<g id="badge".*?</g>', "", svg, count=1, flags=re.S)
    cls = "scene muted" if muted else "scene"
    badge_html = f'<span class="badge">{badge}</span>' if badge is not None else ""
    return f'<div class="{cls}">{svg}{badge_html}</div>'


# -------------------------------------------------------------- sections


def excerpt_block(turn: dict, chrome: dict, cites: Cites, kind_label: str = "", repo: str = "") -> str:
    full = turn.get("text") or ""
    details = f'<details><summary>{escape(chrome["full_text"])}</summary><pre>{escape(full)}</pre></details>' if full and full.strip() != turn["excerpt"].rstrip("…") else ""
    dwell = f' <span class="dwell">{escape(chrome["dwell"])} {fmt_dur(turn["dwell_s"])}</span>' if turn.get("dwell_s") else ""
    pt = ""
    if turn.get("passthrough_origin"):
        o = turn["passthrough_origin"]
        where = o.get("path") or o.get("where", "")
        if o.get("path") and repo:
            where = rel(o["path"], repo)[0]
        pt = f'<p class="passthrough">{escape(chrome["passthrough"])} <span class="mono">{escape(where)}</span> {cites.mark(o.get("citation"))}</p>'
    return f'<div class="turn"><div class="meta"><time>{fmt_hm(turn["ts"])}</time>{dwell}{(" · " + escape(kind_label)) if kind_label else ""} {cites.mark(turn["citation"])}</div><blockquote class="excerpt">{escape(turn["excerpt"])}</blockquote>{details}{pt}</div>'


def chapter_head(name: str, chrome: dict, prose: dict, slots: dict, badge: int | None, muted: bool, thin: bool = False) -> str:
    if thin:
        lede_html = ""
    else:
        lede, _ = slot(prose, ["chapters", name, "lede"], slots["chapters"][name]["lede"]["max_words"], chrome, "line")
        lede_html = f'<p class="lede">{lede}</p>'
    return f'<header class="chapter-head">{scene(name, badge, muted)}<div class="chapter-title"><p class="chapter-word">{escape(chrome["chapter_word"])}</p><h2 id="ch-{name}">{escape(chrome["chapters"][name])}</h2>{lede_html}</div></header>'


def chapter_body(name: str, prose: dict, slots: dict, chrome: dict) -> str:
    body, _ = slot(prose, ["chapters", name, "body"], slots["chapters"][name]["body"]["max_words"], chrome)
    return f'<div class="prose">{body}</div>'


def thin_body(name: str, slots: dict, lang: str) -> str:
    return f'<div class="prose thin"><p>{escape(slots["thin"][name][lang])}</p></div>'


def render_spark(b: dict, prose: dict, slots: dict, chrome: dict, cites: Cites) -> str:
    parts = [chapter_head("spark", chrome, prose, slots, None, b.get("spark") is None), chapter_body("spark", prose, slots, chrome)]
    if b.get("spark"):
        parts.append(f'<div class="beats"><p class="beat-label">{escape(chrome["spark_from"])} {fmt_dt(b["spark"]["ts"])}</p>{anchor(b["spark"]["citation"])}{excerpt_block(b["spark"], chrome, cites, repo=b["source"]["repo_path"])}</div>')
    return f'<section class="chapter" id="spark">{"".join(parts)}</section>'


def anchor(citation: str) -> str:
    return f'<span class="anchor" id="b-{citation}"></span>'


def render_steering(b: dict, prose: dict, slots: dict, chrome: dict, cites: Cites, repo: str) -> str:
    steers = b["steers"]
    lang = b["options"]["lang"]
    parts = [chapter_head("steering", chrome, prose, slots, len(steers) or None, not steers, thin=not steers)]
    if not steers:
        parts.append(thin_body("steering", slots, lang))
    else:
        parts.append(chapter_body("steering", prose, slots, chrome))
        tl = charts.timeline_svg(b, chrome)
        if tl:
            parts.append(f'<figure class="chart-fig"><figcaption><span class="fig-title">{escape(chrome["timeline"])}</span> {escape(chrome["timeline_caption"])}</figcaption>{tl}</figure>')
        items = []
        for i, s in enumerate(steers):
            cap, _ = slot(prose, ["steer_captions", s["citation"]], slots["per_beat"]["steer_caption"]["max_words"], chrome, "line")
            cons = ""
            inside_paths = [(rel(p, repo)[0], p) for p in s.get("consequence", []) if rel(p, repo)[1]]
            if inside_paths:
                shown = [f'<span class="path" title="{escape(p)}">{escape(d)}</span>' for d, p in inside_paths]
                cons = f'<p class="consequence">{" ".join(shown)}</p>'
            label = chrome["question"] if s["is_question"] else ""
            items.append(f'<li class="beat">{anchor(s["citation"])}{excerpt_block(s, chrome, cites, label, repo)}<p class="caption">{cap}</p>{cons}</li>')
        first, rest = items[:8], items[8:]
        parts.append(f'<ol class="beats steers">{"".join(first)}</ol>')
        if rest:
            parts.append(f'<details class="more"><summary>{escape(chrome["more_steers"].format(n=len(rest)))}</summary><ol class="beats steers" start="9">{"".join(rest)}</ol></details>')
    # verifications belong to steering as the human's own hands on the work
    vs = b["verifications"]
    if vs:
        rows = "".join(f'<li>{anchor(v["citation"])}<time>{fmt_hm(v["ts"])}</time> <code>{escape(v["text"])}</code> {cites.mark(v["citation"])}</li>' for v in vs)
        parts.append(f'<div class="verifications"><h3>{escape(chrome["verifications"])}</h3><ul>{rows}</ul></div>')
    else:
        parts.append(f'<p class="hint">{escape(chrome["no_verifications"])}</p>')
    return f'<section class="chapter" id="steering">{"".join(parts)}</section>'


def render_judgment(b: dict, prose: dict, slots: dict, chrome: dict, cites: Cites) -> str:
    js = b["judgments"]
    lang = b["options"]["lang"]
    parts = [chapter_head("judgment", chrome, prose, slots, len(js) or None, not js, thin=not js)]
    if not js:
        parts.append(thin_body("judgment", slots, lang))
    else:
        parts.append(chapter_body("judgment", prose, slots, chrome))
        strip = charts.judgment_strip_svg(b, chrome)
        parts.append(f'<figure class="chart-fig"><figcaption><span class="fig-title">{escape(chrome["judgment_strip"])}</span></figcaption>{strip}</figure>')
        items = []
        for j in js:
            sc, _ = slot(prose, ["judgment_scenes", j["citation"]], slots["per_beat"]["judgment_scene"]["max_words"], chrome)
            c = j["content"]
            if j["kind"] == "rejection":
                ev = f'<p class="ev"><span class="ev-label">{escape(chrome["claude_was_about_to"])}</span> <code>{escape(c.get("tool", ""))}</code> <span class="ev-text">{escape(c.get("input_excerpt", ""))}</span></p>'
            elif j["kind"] == "interrupt":
                ev = f'<p class="ev"><span class="ev-label">{escape(chrome["claude_had_just_said"])}</span> <span class="ev-text">{escape(c.get("last_claude_text", ""))}</span></p>'
            else:
                ev = f'<p class="ev"><span class="ev-text mono">{escape(c.get("path", ""))}</span></p>'
            nxt = ""
            if j.get("next_turn"):
                nxt = f'<p class="next"><span class="ev-label">{escape(chrome["judgment_next"])}</span> <q>{escape(j["next_turn"]["excerpt"])}</q> {cites.mark(j["next_turn"]["citation"])}</p>'
            items.append(f'<li class="beat judgment-{j["kind"]}">{anchor(j["citation"])}<div class="meta"><time>{fmt_hm(j["ts"])}</time> · {escape(chrome["judgment_kinds"][j["kind"]])} {cites.mark(j["citation"])}</div>{ev}{nxt}<div class="scene-text">{sc}</div></li>')
        parts.append(f'<ol class="beats judgments">{"".join(items)}</ol>')
    return f'<section class="chapter" id="judgment">{"".join(parts)}</section>'


def render_build(b: dict, prose: dict, slots: dict, chrome: dict, cites: Cites) -> str:
    parts = [chapter_head("build", chrome, prose, slots, len(b["commits"]) or None, False), chapter_body("build", prose, slots, chrome)]
    comp = charts.composition_svg(b, chrome)
    if comp:
        parts.append(f'<figure class="chart-fig"><figcaption><span class="fig-title">{escape(chrome["composition"])}</span> {escape(chrome["composition_caption"])}</figcaption>{comp}<p class="caveat">{escape(chrome["comp_caveat"])}</p></figure>')
    rows = [
        f'<li>{anchor(c["citation"]) if c["citation"] else ""}<time>{fmt_hm(c["when"])}</time> <code class="sha">{escape(c["short"])}</code> <span class="subject">{escape(c["subject"])}</span> <span class="who who-{c["run_by"]}">{escape(chrome["run_by"][c["run_by"]])}</span> {cites.mark(c["citation"])}</li>'
        for c in b["commits"]
    ]
    first, rest = rows[:12], rows[12:]
    more = f'<details class="more"><summary>{escape(chrome["more_commits"].format(n=len(rest)))}</summary><ol start="13">{"".join(rest)}</ol></details>' if rest else ""
    parts.append(f'<div class="commits"><h3>{escape(chrome["commits"])}</h3><ol>{"".join(first)}</ol>{more}</div>')
    it = b["claude_iterations"]
    parts.append(f'<p class="iterations">{escape(chrome["iterations"].format(errors=it["tool_errors"], tests=it["test_runs"], files=len(it["files_edited_more_than_twice"])))}</p>')
    return f'<section class="chapter" id="build">{"".join(parts)}</section>'


def render_ship(b: dict, prose: dict, slots: dict, chrome: dict, cites: Cites) -> str:
    s = b["ship"]
    parts = [chapter_head("ship", chrome, prose, slots, None, s["status"] != "merged"), chapter_body("ship", prose, slots, chrome)]
    if s["status"] == "merged":
        parts.append(f'<p class="ship-line"><span class="strong">{escape(chrome["ship_merged"])}</span> {fmt_dt(s["merged_at"])}, {escape(chrome["ship_by"])} {escape(s["merger"] or "")}</p>')
        if s["attempts"]:
            rows = "".join(
                f'<li class="attempt who-{a["who"]}{" closest" if a.get("closest") else ""}">{anchor(a["citation"])}<time>{fmt_hm(a["ts"])}</time> {escape(chrome["attempt_who"][a["who"]])} <code>{escape(a["command"][:120])}</code> <span class="outcome outcome-{a["outcome"]}">{escape(chrome["attempt_outcome"][a["outcome"]])}</span>{(" <span class=" + chr(34) + "ev-text" + chr(34) + ">" + escape(a["output_excerpt"]) + "</span>") if a["output_excerpt"] else ""} <span class="delta">{fmt_delta(a["delta_s"])} {escape(chrome["from_merge"])}</span> {cites.mark(a["citation"])}</li>'
                for a in sorted(s["attempts"], key=lambda a: a["ts"])
            )
            parts.append(f'<div class="attempts"><h3>{escape(chrome["ship_attempts"])}</h3><ol>{rows}</ol></div>')
        elif s["fallback_turn"]:
            f = s["fallback_turn"]
            parts.append(f'<p class="ship-none">{escape(chrome["ship_none"])}</p><p class="fallback"><span class="ev-label">{escape(chrome["ship_fallback"])}</span> <q>{escape(f["excerpt"])}</q> <span class="delta">{fmt_delta(f["delta_s"])} {escape(chrome["from_merge"])}</span> {cites.mark(f["citation"])}</p>')
        else:
            parts.append(f'<p class="ship-none">{escape(chrome["ship_none"])}</p>')
    else:
        parts.append(f'<p class="ship-line"><span class="strong">{escape(chrome["ship_unmerged"])}</span></p>')
    return f'<section class="chapter" id="ship">{"".join(parts)}</section>'


def render_unseen(b: dict, prose: dict, slots: dict, chrome: dict) -> str:
    p = b["presence"]
    n = p["sessions"]
    word = chrome["session_one"] if n == 1 else chrome["session_many"]
    line = chrome["presence"].format(duration=fmt_dur(p["seconds"]), sessions=n, session_word=word)
    parts = [chapter_head("unseen", chrome, prose, slots, None, False), chapter_body("unseen", prose, slots, chrome), f'<p class="presence">{escape(line)}</p>']
    return f'<section class="chapter" id="unseen">{"".join(parts)}</section>'


# ------------------------------------------------------------------ page


def render(beats: dict, prose: dict, template: str, chrome_all: dict, slots: dict) -> str:
    lang = beats.get("options", {}).get("lang") or "en"
    chrome = chrome_all[lang]
    cites = Cites()
    repo = beats["source"]["repo_path"]
    pr = beats["pr"]
    title, written = slot(prose, ["title"], slots["title"]["max_words"], chrome, "line")
    if not written:
        title = escape(pr["subject"])
    accent = beats.get("options", {}).get("accent")
    accent_light = accent or DEFAULT_ACCENT["light"]
    accent_dark = accent or DEFAULT_ACCENT["dark"]

    ident = f'{chrome["masthead_pr"]} #{pr["number"]}' if pr["number"] else f'{chrome["masthead_branch"]} {pr["head"]}'
    authors = ", ".join(a["name"] for a in beats["accountable"]["authors"])
    merged = fmt_dt(pr["merged_at"]) if pr["merged_at"] else chrome["ship_unmerged"]
    sessions = ", ".join(s["id"][:8] for s in beats["sessions"] if s["on_branch_records"]) or ", ".join(s["id"][:8] for s in beats["sessions"])

    body = "".join([
        render_spark(beats, prose, slots, chrome, cites),
        render_steering(beats, prose, slots, chrome, cites, repo),
        render_judgment(beats, prose, slots, chrome, cites),
        render_build(beats, prose, slots, chrome, cites),
        render_ship(beats, prose, slots, chrome, cites),
        render_unseen(beats, prose, slots, chrome),
        cites.footnotes(chrome),
    ])

    fields = {
        "lang": lang,
        "title": title,
        "title_text": re.sub(r"<[^>]+>", "", title),
        "kicker": escape(chrome["masthead_kicker"]),
        "ident": escape(ident),
        "subject": escape(pr["subject"]),
        "repo": escape(beats["source"]["repo_name"]),
        "authors_label": escape(chrome["authors"]),
        "authors": escape(authors),
        "merged": escape(merged),
        "sessions_label": escape(chrome["sessions_matched"]),
        "sessions": escape(sessions),
        "body": body,
        "note": escape(chrome["generated_note"]),
        "accent_light": accent_light,
        "accent_dark": accent_dark,
    }
    return re.sub(r"\{\{(\w+)\}\}", lambda m: fields.get(m.group(1), m.group(0)), template)


def render_dir(d: Path) -> Path:
    beats_f = d / "beats.json"
    if not beats_f.is_file():
        raise RenderError(f"no beats.json in {d}")
    beats = json.loads(beats_f.read_text(encoding="utf-8"))
    prose_f = d / "prose.json"
    prose = json.loads(prose_f.read_text(encoding="utf-8")) if prose_f.is_file() else {}
    template = (HERE / "template.html").read_text(encoding="utf-8")
    chrome = json.loads((HERE / "chrome.json").read_text(encoding="utf-8"))
    slots = json.loads((HERE / "slots.json").read_text(encoding="utf-8"))
    html = render(beats, prose, template, chrome, slots)
    out = d / "story.html"
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    return out
