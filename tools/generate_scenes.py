"""Generate the six chapter scenes with Recraft's vector model through OpenRouter.

A development tool, not part of the plugin's runtime. It asks the model for one
SVG per chapter, then post-processes each into the scene contract the renderer
and tests depend on:

  - root <svg xmlns viewBox="0 0 320 200" role="img" aria-labelledby="title"> with <title id="title">
  - every stroke and fill in currentColor or none; no other colours, gradients, filters, images
  - one badge group (id="badge") with a <text id="badge-text">
  - no <script>, no <style>, no external references, under 12 KB

The raw responses are kept under scenes/recraft/raw/ so a bad post-process can
be redone without another API call. Reads OPENROUTER_API_KEY from .env at the
plugin root or the environment; never prints it.

Usage:
  python tools/generate_scenes.py            # all six
  python tools/generate_scenes.py spark hand # a subset
  python tools/generate_scenes.py --reprocess # post-process the saved raw files only
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "skills" / "proudhuman" / "scenes"
RAW = OUT / "recraft" / "raw"
MODEL = "recraft/recraft-v4.1-vector"
ENDPOINT = "https://openrouter.ai/api/v1/images"

STYLE = (
    "Editorial line illustration for a printed magazine. Single-colour ink line art on a plain white background, "
    "confident hand-drawn strokes of even weight, sparse hatching for shade only, no fills except small solid accents, "
    "no gradients, no text, no frame, no border. The subject is large and fills most of the frame, composed for a wide landscape 16:9 picture."
)

SCENES = {
    "spark": ("The Spark", "A single wooden match lying diagonally across the picture, its head just struck and caught, with short radiating lines of light and a few tiny sparks flying off the flame; a whisper of smoke. The idea that starts the work."),
    "tiller": ("The Steering", "A hand resting on the tiller of a small wooden sailing boat, seen from behind and slightly above, with a few lines of water in the wake. The human redirecting the course."),
    "hand": ("Moments of Judgment", "A raised open hand, palm forward, fingers relaxed, the gesture that says stop, calm not aggressive, drawn from the wrist up."),
    "workshop": ("The Build", "A carpenter's workbench with a half-built wooden boat hull on it, a mallet, a hand plane and a few wood shavings. The material being worked."),
    "launch": ("The Ship", "A small paper boat leaving a wooden dock on calm water, a bollard on the dock, the boat already a little way out. Departure."),
    "lantern": ("What the Record Cannot See", "A hurricane lantern hanging from a short cord, its light reaching a small circle in thick fog, wisps of fog beyond the light. What is there but cannot be seen."),
}


def api_key() -> str:
    k = os.environ.get("OPENROUTER_API_KEY")
    if not k:
        env = ROOT / ".env"
        if env.is_file():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("OPENROUTER_API_KEY="):
                    k = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not k:
        raise SystemExit("OPENROUTER_API_KEY not found in the environment or .env")
    return k


def generate(name: str, subject: str) -> str:
    body = {"model": MODEL, "prompt": f"{subject} {STYLE}", "n": 1, "aspect_ratio": "16:9", "output_format": "svg"}
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"), headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com/dimitritholen/proudhuman", "X-Title": "proudhuman"})
    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{name}: HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    RAW.mkdir(parents=True, exist_ok=True)
    items = data.get("data") or []
    if not items:
        raise SystemExit(f"{name}: no image in the response: {json.dumps(data)[:300]}")
    item = items[0]
    media = item.get("media_type", "")
    (RAW / f"{name}.meta.json").write_text(json.dumps({"media_type": media, "usage": data.get("usage")}, indent=2), encoding="utf-8")
    raw = base64.b64decode(item["b64_json"])
    if "svg" not in media and not raw.lstrip().startswith(b"<"):
        raise SystemExit(f"{name}: expected SVG, got {media}")
    svg = raw.decode("utf-8")
    (RAW / f"{name}.svg").write_text(svg, encoding="utf-8")
    return svg


# ------------------------------------------------------------ post-process

BADGE = '<g id="badge" transform="translate(276,24)"><circle r="16" fill="none" stroke="currentColor" stroke-width="1.5"/><text id="badge-text" text-anchor="middle" dominant-baseline="central" font-family="inherit" font-size="14" fill="currentColor"></text></g>'
FORBIDDEN = re.compile(r"<(script|style|image|foreignObject|filter|linearGradient|radialGradient|pattern)\b", re.I)


def luminance(hex6: str) -> float:
    r, g, b = (int(hex6[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def parse_colour(v: str) -> str | None:
    v = v.strip().lower()
    mm = re.fullmatch(r"#([0-9a-f]{6})", v)
    if mm:
        return mm.group(1)
    mm = re.fullmatch(r"#([0-9a-f]{3})", v)
    if mm:
        return "".join(c * 2 for c in mm.group(1))
    mm = re.match(r"rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)", v)
    if mm:
        return "".join(f"{min(int(x), 255):02x}" for x in mm.groups())
    if v == "white":
        return "ffffff"
    if v == "black":
        return "000000"
    return None


def colour_to_current(m: re.Match) -> str:
    """Map a fill/stroke colour to the ink.

    Dark reads as full ink, greys as ink at reduced opacity (the model's shading), and
    white as the paper, so cut-outs and highlights survive light and dark mode. The
    page supplies --paper; the preview sets it too.
    """
    attr, val = m.group(1), m.group(2).strip()
    v = val.lower()
    if v in ("none", "transparent"):
        return f'{attr}="none"'
    if v == "currentcolor":
        return f'{attr}="currentColor"'
    hex6 = parse_colour(v)
    if hex6 is None:
        return f'{attr}="currentColor"'
    lum = luminance(hex6)
    if lum > 0.92:
        return f'{attr}="var(--paper, #fff)"'
    if lum > 0.55:
        return f'{attr}="currentColor" {attr}-opacity="0.22"'
    if lum > 0.3:
        return f'{attr}="currentColor" {attr}-opacity="0.5"'
    return f'{attr}="currentColor"'


def drawing_bounds(inner: str, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
    """Approximate bounding box of the drawing from the coordinates in its path data.

    Recraft emits absolute M/L/C commands, so every number pair in a d attribute is a
    point (control points included, which only widens the box a little).
    """
    xs: list[float] = []
    ys: list[float] = []
    for d in re.findall(r'\bd="([^"]+)"', inner):
        nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", d)]
        xs.extend(nums[0::2])
        ys.extend(nums[1::2])
    for attr, arr in (("cx", xs), ("cy", ys), ("x", xs), ("y", ys)):
        arr.extend(float(v) for v in re.findall(rf'\b{attr}="(-?\d+(?:\.\d+)?)"', inner))
    if not xs or not ys:
        return x, y, x + w, y + h
    return max(x, min(xs)), max(y, min(ys)), min(x + w, max(xs)), min(y + h, max(ys))


def postprocess(name: str, svg: str) -> str:
    title = SCENES[name][0]
    svg = re.sub(r"<\?xml[^>]*\?>|<!DOCTYPE[^>]*>|<!--.*?-->", "", svg, flags=re.S)
    svg = re.sub(r"<metadata\b.*?</metadata>", "", svg, flags=re.S | re.I)
    svg = re.sub(r"<(title|desc)\b[^>]*>.*?</\1>", "", svg, flags=re.S | re.I)
    if FORBIDDEN.search(svg):
        # drop whole forbidden elements; keep the drawing
        svg = re.sub(r"<(script|style|image|foreignObject|filter|linearGradient|radialGradient|pattern)\b.*?</\1>", "", svg, flags=re.S | re.I)
        svg = re.sub(r"<(image|filter)\b[^>]*/>", "", svg, flags=re.I)
    # root attributes
    m = re.search(r"<svg\b([^>]*)>", svg, re.S)
    if not m:
        raise SystemExit(f"{name}: no <svg> root")
    attrs = m.group(1)
    vb = re.search(r'viewBox="([^"]+)"', attrs)
    if vb:
        x, y, w, h = (float(v) for v in vb.group(1).replace(",", " ").split())
    else:
        w = float(re.search(r'width="([\d.]+)', attrs).group(1))
        h = float(re.search(r'height="([\d.]+)', attrs).group(1))
        x = y = 0.0
    inner = svg[m.end():svg.rfind("</svg>")]
    # remove a full-canvas background, drawn as a rect or as a rectangular path
    inner = re.sub(r'<rect\b[^>]*(width="100%"|width="' + re.escape(str(int(w))) + r'"|width="' + re.escape(f"{w:g}") + r'")[^>]*/>', "", inner, count=1)
    canvas = re.compile(r'<path\b[^>]*d="\s*M\s*0\s+0\s+L\s*' + re.escape(f"{w:g}") + r"\s+0\s+L\s*" + re.escape(f"{w:g}") + r"\s+" + re.escape(f"{h:g}") + r"\s+L\s*0\s+" + re.escape(f"{h:g}") + r'[^"]*"[^>]*/>')
    inner = canvas.sub("", inner, count=1)
    # colours
    inner = re.sub(r'\b(fill|stroke)="([^"]*)"', colour_to_current, inner)
    inner = re.sub(r'\sstyle="[^"]*"', "", inner)
    inner = re.sub(r'\s(id|class|data-[\w-]+)="[^"]*"', "", inner)
    inner = re.sub(r'\s(xlink:href|href)="[^"]*"', "", inner)
    inner = re.sub(r'\stransform="translate\(0,0\)"', "", inner)
    # trim path coordinates to one decimal; the drawing is 2048 wide and scaled down anyway
    inner = re.sub(r"(\d+\.\d)\d+", r"\1", inner)
    # crop to the drawing's own bounds (the model leaves wide margins), then fit into 320x200
    bx0, by0, bx1, by1 = drawing_bounds(inner, x, y, w, h)
    pad = 0.04 * max(bx1 - bx0, by1 - by0)
    bx0, by0, bx1, by1 = max(x, bx0 - pad), max(y, by0 - pad), min(x + w, bx1 + pad), min(y + h, by1 + pad)
    bw, bh = max(bx1 - bx0, 1), max(by1 - by0, 1)
    scale = min(300 / bw, 176 / bh)
    tx = (320 - bw * scale) / 2 - bx0 * scale
    ty = (200 - bh * scale) / 2 - by0 * scale
    out = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 200" role="img" aria-labelledby="title">'
        f'<title id="title">{title}</title>'
        f'<g transform="translate({tx:.2f},{ty:.2f}) scale({scale:.4f})" stroke-linecap="round" stroke-linejoin="round">{inner.strip()}</g>'
        f"{BADGE}</svg>\n"
    )
    return out


def validate(name: str, svg: str) -> list[str]:
    problems = []
    if FORBIDDEN.search(svg):
        problems.append("forbidden element")
    if re.search(r'(fill|stroke)="(?!none|currentColor|var\(--paper, #fff\))', svg):
        problems.append("colour other than currentColor or the paper")
    if re.search(r"url\(|https?://", svg.replace('xmlns="http://www.w3.org/2000/svg"', "")):
        problems.append("external reference")
    if svg.count('id="badge"') != 1 or svg.count('id="badge-text"') != 1:
        problems.append("badge group")
    if len(svg.encode("utf-8")) > 128 * 1024:
        problems.append(f"too big: {len(svg.encode('utf-8'))} bytes")
    ids = re.findall(r'\bid="([^"]+)"', svg)
    if sorted(ids) != ["badge", "badge-text", "title"]:
        problems.append(f"ids: {ids}")
    return problems


def write_preview(names: list[str]) -> Path:
    """A page that inlines the generated scenes on light and dark paper, next to the hand-crafted set."""
    def board(bg: str, ink: str, accent: str, folder: Path) -> str:
        cells = []
        for n in names:
            f = folder / f"{n}.svg"
            if f.is_file():
                cells.append(f'<figure style="margin:0;width:320px;color:{accent}">{f.read_text(encoding="utf-8")}<figcaption style="color:{ink};font:12px monospace">{folder.name}/{n}.svg</figcaption></figure>')
        return f'<section style="--paper:{bg};background:{bg};padding:24px;display:grid;grid-template-columns:repeat(3,320px);gap:24px">{"".join(cells)}</section>'
    html = "<!doctype html><meta charset=utf-8><title>scenes</title><body style='margin:0;font-family:system-ui'>"
    html += board("#F5F4F0", "#5C6570", "#1F5E9E", OUT / "recraft") + board("#161A1F", "#A3A9B1", "#5296DB", OUT / "recraft")
    html += board("#F5F4F0", "#5C6570", "#1F5E9E", OUT) + board("#161A1F", "#A3A9B1", "#5296DB", OUT)
    out = OUT / "recraft" / "preview.html"
    out.write_text(html, encoding="utf-8")
    return out


LOGO_PROMPT = (
    "Only a human forearm and hand, cut off just below the elbow, hovering horizontally above a small pixel-art creature, the hand "
    "resting flat on its head and patting it the way you pat a good dog. The creature is drawn as ink line art: a wide rectangular body "
    "of square pixels, wider than it is tall, two square eyes, a small square arm nub on each side, and two short rectangular legs; "
    "it smiles, a small pixel smile, and looks up at the hand. Directly below the pair, the words \"proud human\" hand-lettered large in the "
    "same ink, lowercase, in a warm, slightly uneven handwritten script, spelled exactly: proud human, stretching the full width of the "
    "drawing above so the lettering and the drawing are equally wide. The picture holds only three things: the forearm, the creature, and "
    "the two lettered words. No shoulder, no body, no ground line. The whole composition is wide and low. "
    + STYLE.replace("composed for a wide landscape 16:9 picture", "composed for a landscape 4:3 picture, the drawing above and the two words below")
)
LOGO_COLOURS = {"light": ("#1F5E9E", "#FFFFFF"), "dark": ("#5296DB", "#0D1117")}


def generate_logo(reprocess: bool, ref: Path | None = None) -> None:
    """The README logo: same drawing, two files with explicit colours for GitHub's light and dark themes."""
    raw_f = RAW / "logo.svg"
    if reprocess and raw_f.is_file():
        svg = raw_f.read_text(encoding="utf-8")
    else:
        body = {"model": MODEL, "prompt": LOGO_PROMPT, "n": 1, "aspect_ratio": "4:3", "output_format": "svg"}
        if ref is not None:
            mime = "image/png" if ref.suffix.lower() == ".png" else "image/jpeg"
            data_url = f"data:{mime};base64," + base64.b64encode(ref.read_bytes()).decode("ascii")
            body["input_references"] = [{"type": "image_url", "image_url": {"url": data_url}}]
        req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"), headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com/dimitritholen/proudhuman", "X-Title": "proudhuman"})
        try:
            with urllib.request.urlopen(req, timeout=240) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise SystemExit(f"logo: HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
        item = (data.get("data") or [{}])[0]
        svg = base64.b64decode(item["b64_json"]).decode("utf-8")
        RAW.mkdir(parents=True, exist_ok=True)
        raw_f.write_text(svg, encoding="utf-8")
        (RAW / "logo.meta.json").write_text(json.dumps({"media_type": item.get("media_type"), "usage": data.get("usage")}, indent=2), encoding="utf-8")
    SCENES["logo"] = ("proudhuman", "")
    processed = postprocess("logo", svg)
    del SCENES["logo"]
    # square box instead of the chapter box, no badge
    processed = re.sub(r'<g id="badge".*?</g>', "", processed, count=1, flags=re.S)
    # the logo keeps the wide chapter box; the drawing is fitted and centred inside it
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    for theme, (ink, paper) in LOGO_COLOURS.items():
        themed = processed.replace('"currentColor"', f'"{ink}"').replace('"var(--paper, #fff)"', f'"{paper}"')
        out = docs / f"logo-{theme}.svg"
        out.write_text(themed, encoding="utf-8", newline="\n")
        print(f"logo {theme}: {len(themed.encode('utf-8'))} bytes -> {out.relative_to(ROOT)}")


def main(argv: list[str]) -> int:
    reprocess = "--reprocess" in argv
    if "--logo" in argv:
        ref = next((Path(a) for a in argv if a.lower().endswith((".png", ".jpg", ".jpeg"))), None)
        generate_logo(reprocess, ref)
        return 0
    names = [a for a in argv if a in SCENES] or list(SCENES)
    (OUT / "recraft").mkdir(parents=True, exist_ok=True)
    if "--preview" in argv:
        print(write_preview(list(SCENES)))
        return 0
    for name in names:
        raw_f = RAW / f"{name}.svg"
        if reprocess and raw_f.is_file():
            svg = raw_f.read_text(encoding="utf-8")
        else:
            svg = generate(name, SCENES[name][1])
        out = postprocess(name, svg)
        problems = validate(name, out)
        target = OUT / "recraft" / f"{name}.svg"
        target.write_text(out, encoding="utf-8", newline="\n")
        print(f"{name}: {len(out.encode('utf-8'))} bytes -> {target.relative_to(ROOT)}" + (f"  PROBLEMS: {', '.join(problems)}" if problems else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
