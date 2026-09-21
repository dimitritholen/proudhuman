"""The three charts of a story, rendered as inline SVG from beats.

Deterministic: no clock, sorted iteration, fixed geometry. Colour comes from CSS
custom properties on the page (accent for the human, graphite for Claude), so
the same SVG serves light, dark and print. Hover detail uses <title>, which
needs no script.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from html import escape

W = 880  # drawing width; the page scales it


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def hm(s: str | None) -> str:
    return ts(s).strftime("%H:%M") if s else ""


def day(s: str | None) -> str:
    return ts(s).strftime("%Y-%m-%d") if s else ""


# ------------------------------------------------------------- marks

MARK_R = 5.5


def mark(kind: str, x: float, y: float, title: str, href: str | None = None) -> str:
    """One human mark. Kinds differ by shape so print in monochrome still reads."""
    t = f"<title>{escape(title)}</title>"
    if kind == "spark":
        pts = " ".join(f"{x + 8 * math.cos(a):.1f},{y + 8 * math.sin(a):.1f}" if i % 2 == 0 else f"{x + 3.2 * math.cos(a):.1f},{y + 3.2 * math.sin(a):.1f}" for i, a in enumerate(-math.pi / 2 + k * math.pi / 4 for k in range(8)))
        body = f'<polygon class="m-spark" points="{pts}">{t}</polygon>'
    elif kind == "question":
        body = f'<circle class="m-question" cx="{x:.1f}" cy="{y:.1f}" r="{MARK_R}">{t}</circle><circle class="m-question-dot" cx="{x:.1f}" cy="{y:.1f}" r="1.6"/>'
    elif kind == "judgment":
        body = f'<rect class="m-judgment" x="{x - 5.5:.1f}" y="{y - 5.5:.1f}" width="11" height="11" transform="rotate(45 {x:.1f} {y:.1f})">{t}</rect>'
    elif kind == "verification":
        body = f'<polygon class="m-verification" points="{x:.1f},{y - 6.5:.1f} {x + 6:.1f},{y + 4.5:.1f} {x - 6:.1f},{y + 4.5:.1f}">{t}</polygon>'
    elif kind == "commit":
        body = f'<line class="m-commit" x1="{x:.1f}" y1="{y - 7}" x2="{x:.1f}" y2="{y + 7}">{t}</line>'
    elif kind == "ship":
        body = f'<path class="m-ship" d="M{x - 4:.1f},{y - 11} v22 M{x - 4:.1f},{y - 10} h9 l-3,4 l3,4 h-9">{t}</path>'
    else:
        body = f'<circle class="m-steer" cx="{x:.1f}" cy="{y:.1f}" r="{MARK_R}">{t}</circle>'
    return f'<a href="{href}">{body}</a>' if href else body


def legend(items: list[tuple[str, str]], y: float) -> str:
    out = []
    x = 0.0
    for kind, label in items:
        out.append(f'<g transform="translate({x:.1f},{y:.1f})">{mark(kind, 8, 0, label)}<text class="lgd" x="20" y="4">{escape(label)}</text></g>')
        x += 24 + 7.2 * len(label) + 18
    return "".join(out)


# ------------------------------------------------------------- timeline


def timeline_svg(beats: dict, chrome: dict) -> str:
    sessions = [s for s in sorted(beats["sessions"], key=lambda s: s["first"] or "") if s["first"] and s["last"]]
    if not sessions:
        return ""
    band_h, gap, top, left, right = 64, 62, 34, 120, 24
    plot_w = W - left - right
    h = top + len(sessions) * (band_h + gap) + 40
    out = [f'<svg class="chart timeline" viewBox="0 0 {W} {h}" role="img" aria-label="{escape(chrome["timeline"])}"><defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" class="hatch-line"/></pattern></defs>']

    events = []
    if beats.get("spark"):
        events.append(("spark", beats["spark"]["ts"], beats["spark"]["citation"], f'{chrome["legend"]["spark"]} {hm(beats["spark"]["ts"])}: {beats["spark"]["excerpt"][:80]}'))
    for s in beats["steers"]:
        k = "question" if s["is_question"] else "steer"
        events.append((k, s["ts"], s["citation"], f'{chrome["legend"][k]} {hm(s["ts"])}: {s["excerpt"][:80]}'))
    for j in beats["judgments"]:
        events.append(("judgment", j["ts"], j["citation"], f'{chrome["judgment_kinds"][j["kind"]]} {hm(j["ts"])}'))
    for v in beats["verifications"]:
        events.append(("verification", v["ts"], v["citation"], f'{chrome["legend"]["verification"]} {hm(v["ts"])}: {v["text"][:80]}'))

    for i, s in enumerate(sessions):
        y0 = top + i * (band_h + gap)
        base = y0 + band_h - 14
        t0, t1 = ts(s["first"]), ts(s["last"])
        span = max((t1 - t0).total_seconds(), 60.0)

        def X(t: datetime) -> float:
            return left + plot_w * ((t - t0).total_seconds() / span)

        # session label
        out.append(f'<text class="band-label" x="{left - 12}" y="{base - 6}" text-anchor="end">{escape(s["id"][:8])}</text>')
        out.append(f'<text class="band-sub" x="{left - 12}" y="{base + 10}" text-anchor="end">{escape(day(s["first"]))}</text>')
        out.append(f'<text class="axis" x="{left}" y="{base + 22}">{hm(s["first"])}</text><text class="axis" x="{left + plot_w}" y="{base + 22}" text-anchor="end">{hm(s["last"])}</text>')
        # Claude activity: density of tool calls in 72 bins, drawn as an area with hatch
        bins = 72
        counts = [0] * bins
        for t in s.get("tool_calls", []):
            k = min(bins - 1, int(bins * ((ts(t) - t0).total_seconds() / span)))
            counts[k] += 1
        peak = max(counts) or 1
        pts = [f"{left:.1f},{base:.1f}"]
        for k, c in enumerate(counts):
            x = left + plot_w * (k + 0.5) / bins
            pts.append(f"{x:.1f},{base - 36 * (c / peak):.1f}")
        pts.append(f"{left + plot_w:.1f},{base:.1f}")
        out.append(f'<polygon class="activity" points="{" ".join(pts)}"><title>{escape(chrome["legend"]["claude"])}: {sum(counts)}</title></polygon>')
        out.append(f'<polygon class="activity-hatch" points="{" ".join(pts)}" fill="url(#hatch)"/>')
        out.append(f'<line class="baseline" x1="{left}" y1="{base}" x2="{left + plot_w}" y2="{base}"/>')
        # commits
        for c in beats["commits"]:
            t = ts(c["when"])
            if t0 <= t <= t1:
                out.append(mark("commit", X(t), base, f'{chrome["legend"]["commit"]} {c["short"]} {hm(c["when"])}: {c["subject"][:70]}'))
        # ship
        if beats["ship"]["status"] == "merged" and beats["ship"]["merged_at"]:
            t = ts(beats["ship"]["merged_at"])
            if t0 <= t <= t1:
                out.append(mark("ship", X(t), base - 14, f'{chrome["legend"]["ship"]} {hm(beats["ship"]["merged_at"])}'))
        # human marks, on the thread above the band
        ys = base - 46
        placed: list[float] = []
        for kind, when, cit, title in sorted(events, key=lambda e: e[1]):
            t = ts(when)
            if not (t0 <= t <= t1) or not cit.startswith(s["id"]):
                continue
            x = X(t)
            lift = 0
            for px in placed:
                if abs(px - x) < 12:
                    lift += 1
            placed.append(x)
            out.append(mark(kind, x, ys - 12 * min(lift, 2), title, f"#b-{cit}"))
        out.append(f'<line class="thread" x1="{left}" y1="{ys}" x2="{left + plot_w}" y2="{ys}"/>')

    out.append(f'<g transform="translate({left},{h - 10})">{legend([(k, chrome["legend"][k]) for k in ("spark", "steer", "question", "judgment", "verification", "commit", "ship")], 0)}</g>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------- composition


SEGMENTS = ("emitted", "moved", "said", "none")


def _bar(x: float, y: float, w: float, h: float, row: dict, total: int, chrome: dict) -> str:
    out = []
    cur = x
    for seg in SEGMENTS:
        n = row.get(seg, 0)
        if n <= 0:
            continue
        sw = max(w * n / total - 2, 0.5) if total else 0
        out.append(f'<rect class="seg seg-{seg}" x="{cur:.1f}" y="{y:.1f}" width="{sw:.1f}" height="{h}" rx="2"><title>{escape(chrome["comp_legend"][seg])}: {n} {chrome["lines"]}</title></rect>')
        cur += w * n / total
    return "".join(out)


def composition_svg(beats: dict, chrome: dict) -> str:
    comp = beats["composition"]
    tot = comp["totals"]
    if tot["added"] == 0:
        return ""
    files = sorted(comp["files"], key=lambda f: (-f["added"], f["path"]))[:8]
    biggest = max((f["added"] for f in files), default=1) or 1
    left, right, row_h, gap = 300, 70, 16, 10
    legend_rows = legend_layout([chrome["comp_legend"][s] for s in SEGMENTS], W - left - right)
    h = 28 + 30 + 22 + len(files) * (row_h + gap) + 24 + 20 * len(legend_rows)
    out = [f'<svg class="chart composition" viewBox="0 0 {W} {h}" role="img" aria-label="{escape(chrome["composition"])}">']
    bw = W - left - right
    out.append(f'<text class="row-label strong" x="{left - 12}" y="{28 + 20}" text-anchor="end">{tot["added"]} {escape(chrome["lines"])}</text>')
    out.append(_bar(left, 28, bw, 26, tot, tot["added"], chrome))
    y = 28 + 30 + 22
    for f in files:
        name = f["path"].split("/")[-1]
        w = bw * f["added"] / biggest
        out.append(f'<text class="row-label" x="{left - 12}" y="{y + 12}" text-anchor="end"><title>{escape(f["path"])}</title>{escape(name[:38])}</text>')
        out.append(_bar(left, y, w, row_h, f, f["added"], chrome))
        out.append(f'<text class="row-count" x="{left + w + 8:.1f}" y="{y + 12}">{f["added"]}</text>')
        y += row_h + gap
    ly = y + 14
    for row in legend_rows:
        for seg, label, lx in row:
            out.append(f'<rect class="seg seg-{seg}" x="{left + lx:.1f}" y="{ly}" width="14" height="14" rx="2"/><text class="lgd" x="{left + lx + 20:.1f}" y="{ly + 11}">{escape(label)}</text>')
        ly += 20
    out.append("</svg>")
    return "".join(out)


def legend_layout(labels: list[str], width: float, char_w: float = 6.4, swatch: float = 20, pad: float = 22) -> list[list[tuple[str, str, float]]]:
    """Wrap legend entries into rows that fit `width`. Returns rows of (segment key, label, x)."""
    rows: list[list[tuple[str, str, float]]] = [[]]
    x = 0.0
    for seg, label in zip(SEGMENTS, labels):
        w = swatch + char_w * len(label) + pad
        if x + w > width and rows[-1]:
            rows.append([])
            x = 0.0
        rows[-1].append((seg, label, x))
        x += w
    return rows


# ------------------------------------------------------ judgment strip


def judgment_strip_svg(beats: dict, chrome: dict) -> str:
    js = beats["judgments"]
    if not js:
        return ""
    h = 70
    out = [f'<svg class="chart strip" viewBox="0 0 {W} {h}" role="img" aria-label="{escape(chrome["judgment_strip"])}">']
    left, right = 24, 24
    n = len(js)
    step = (W - left - right) / max(n, 1)
    out.append(f'<line class="thread" x1="{left}" y1="30" x2="{W - right}" y2="30"/>')
    for i, j in enumerate(js):
        x = left + step * (i + 0.5)
        title = f'{chrome["judgment_kinds"][j["kind"]]} {hm(j["ts"])}'
        out.append(mark("judgment", x, 30, title, f"#b-{j['citation']}"))
        out.append(f'<text class="axis" x="{x:.1f}" y="56" text-anchor="middle">{hm(j["ts"])}</text>')
    out.append("</svg>")
    return "".join(out)
