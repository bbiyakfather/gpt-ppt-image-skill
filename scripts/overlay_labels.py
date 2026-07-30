#!/usr/bin/env python3
"""Composite CJK text labels onto a text-free base image.

gpt-image-2 cannot render Korean/CJK glyphs reliably, so the base art is
generated with no text at all and every label is drawn here from a JSON spec
using a real system font. Coordinates are percentages of the canvas, which is
exactly what the pin-review popup reports (x_pct / y_pct), so a pin comment
asking for a label change becomes a one-line spec edit + re-render instead of
a costly image regeneration.

Usage:
    python overlay_labels.py spec.json
    python overlay_labels.py --selfcheck

Spec (only "base" and "out" are required):
{
  "base": "gpt-image/20260730-120000-foo-base.png",
  "out":  "gpt-image/20260730-120000-foo-v02.png",
  "canvas": {"aspect": 2.5023, "height": 1065, "bg": "#ffffff"},   // or {"width":.., "height":..}
  "font": "C:/Windows/Fonts/malgun.ttf",
  "font_bold": "C:/Windows/Fonts/malgunbd.ttf",
  "labels": [
    {"text": "태양광 발전부", "x": 12, "y": 8, "size": 30,
     "anchor": "mm", "bold": false, "leader": [20, 15]}
  ],
  "arrows": [
    {"from": [30, 60], "to": [55, 60], "color": "#2b6cb0", "width": 6,
     "text": "급수", "size": 26}
  ]
}

Theme: by default each label samples the image brightness under its pill and
picks a dark translucent scrim (white text) on bright areas or a light
translucent pill (dark text) on dark areas. Explicit "pill"/"color" values
always win; "pill": "none" disables the pill.

stdout contract (last line, ASCII-safe JSON):
  {"out": "<path>", "canvas": [w, h], "art_rect": [x, y, w, h]}
art_rect is where the base art sits inside the canvas — use it to convert
canvas-relative pin percentages back to base-art coordinates when the canvas
was letterboxed.
"""
import json
import math
import os
import sys
from PIL import Image, ImageDraw, ImageFont, ImageStat

DEFAULT_FONT = "C:/Windows/Fonts/malgun.ttf"
DEFAULT_BOLD = "C:/Windows/Fonts/malgunbd.ttf"

# auto-theme design tokens
DARK_SCRIM = (17, 24, 39, 184)     # rgba(17,24,39,0.72) — pill on bright areas
DARK_SCRIM_TEXT = (255, 255, 255, 255)
LIGHT_PILL = (255, 255, 255, 199)  # rgba(255,255,255,0.78) — pill on dark areas
LIGHT_PILL_TEXT = (17, 17, 17, 255)
LEADER_DARK = (17, 24, 39, 255)
LEADER_HALO = (255, 255, 255, 170)


def _rgba(value, fallback=(0, 0, 0, 255)):
    """Accept #rgb, #rrggbb, #rrggbbaa or a [r,g,b,a] list."""
    if value is None:
        return fallback
    if isinstance(value, (list, tuple)):
        vals = list(value) + [255] * (4 - len(value))
        return tuple(int(v) for v in vals[:4])
    s = str(value).lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) == 6:
        s += "ff"
    if len(s) != 8:
        raise SystemExit(f"invalid color {value!r} — use #rgb, #rrggbb, #rrggbbaa or [r,g,b,a]")
    try:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4, 6))
    except ValueError:
        raise SystemExit(f"invalid color {value!r} — non-hex characters")


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        raise SystemExit(f"font not found: {path} — set \"font\"/\"font_bold\" in the spec "
                         "to a .ttf that exists on this machine")


def _canvas_size(spec, base):
    cv = spec.get("canvas") or {}
    if cv.get("width") and cv.get("height"):
        return int(cv["width"]), int(cv["height"])
    if cv.get("aspect"):
        h = int(cv.get("height") or base.height)
        return int(round(h * float(cv["aspect"]))), h
    return base.width, base.height


def _mean_luminance(img_l, box):
    """Mean brightness (0-255) of a clamped box on a grayscale image."""
    x0, y0, x1, y1 = box
    x0 = max(0, min(int(x0), img_l.width - 1))
    y0 = max(0, min(int(y0), img_l.height - 1))
    x1 = max(x0 + 1, min(int(x1), img_l.width))
    y1 = max(y0 + 1, min(int(y1), img_l.height))
    return ImageStat.Stat(img_l.crop((x0, y0, x1, y1))).mean[0]


def render(spec):
    base = Image.open(spec["base"]).convert("RGBA")
    cw, ch = _canvas_size(spec, base)
    bg = _rgba((spec.get("canvas") or {}).get("bg", "#ffffff"), (255, 255, 255, 255))
    canvas = Image.new("RGBA", (cw, ch), bg)

    # letterbox the base art into the canvas (contain, centred)
    scale = min(cw / base.width, ch / base.height)
    bw, bh = int(base.width * scale), int(base.height * scale)
    ax, ay = (cw - bw) // 2, (ch - bh) // 2
    art = base.resize((bw, bh), Image.LANCZOS)
    canvas.paste(art, (ax, ay), art)

    lum = canvas.convert("L")  # brightness map for auto theming
    overlay = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    fp = spec.get("font", DEFAULT_FONT)
    fpb = spec.get("font_bold", DEFAULT_BOLD)

    def px(x, y):
        return x / 100.0 * cw, y / 100.0 * ch

    for a in spec.get("arrows", []):
        x1, y1 = px(*a["from"])
        x2, y2 = px(*a["to"])
        col = _rgba(a.get("color", "#2b6cb0"))
        w = int(a.get("width", 6))
        draw.line([(x1, y1), (x2, y2)], fill=col, width=w)
        ang = math.atan2(y2 - y1, x2 - x1)
        hl = max(w * 3, 14)
        for side in (+1, -1):
            draw.line([(x2, y2),
                       (x2 - hl * math.cos(ang - side * 0.45),
                        y2 - hl * math.sin(ang - side * 0.45))], fill=col, width=w)
        if a.get("text"):
            f = _font(fpb if a.get("bold") else fp, int(a.get("size", 26)))
            draw.text(((x1 + x2) / 2, (y1 + y2) / 2 - hl), a["text"], font=f,
                      fill=col, anchor="mb")

    for lb in spec.get("labels", []):
        x, y = px(lb["x"], lb["y"])
        f = _font(fpb if lb.get("bold") else fp, int(lb.get("size", 30)))
        anchor = lb.get("anchor", "mm")
        pad = int(lb.get("pad", 10))
        bx = draw.textbbox((x, y), lb["text"], font=f, anchor=anchor)
        pill_box = (bx[0] - pad, bx[1] - pad, bx[2] + pad, bx[3] + pad)

        # auto theme: sample brightness under the pill, pick scrim vs light pill
        pill_val = lb.get("pill", "auto")
        color_val = lb.get("color")
        if pill_val == "auto":
            bright = _mean_luminance(lum, pill_box) >= 128
        if pill_val in (False, "none"):
            pill_col = None
        elif pill_val == "auto":
            pill_col = DARK_SCRIM if bright else LIGHT_PILL
        else:
            pill_col = _rgba(pill_val)
        if color_val is not None:
            text_col = _rgba(color_val)
        elif pill_val == "auto":
            text_col = DARK_SCRIM_TEXT if bright else LIGHT_PILL_TEXT
        else:
            text_col = (17, 17, 17, 255)

        if lb.get("leader"):
            lx, ly = px(*lb["leader"])
            lw = int(lb.get("leader_width", 3))
            lcol = _rgba(lb.get("leader_color"), LEADER_DARK)
            draw.line([(x, y), (lx, ly)], fill=LEADER_HALO, width=lw + 3)
            draw.line([(x, y), (lx, ly)], fill=lcol, width=lw)
            r = max(lw + 2, 5)  # target dot
            draw.ellipse([lx - r, ly - r, lx + r, ly + r], fill=lcol,
                         outline=LEADER_HALO, width=2)
        if pill_col:
            draw.rounded_rectangle(
                pill_box, radius=int(lb.get("radius", 10)), fill=pill_col,
                outline=_rgba(lb.get("border")) if lb.get("border") else None,
                width=int(lb.get("border_width", 2)))
        draw.text((x, y), lb["text"], font=f, fill=text_col, anchor=anchor)

    canvas = Image.alpha_composite(canvas, overlay)
    out = spec["out"]
    parent = os.path.dirname(os.path.abspath(out))
    os.makedirs(parent, exist_ok=True)
    canvas.convert("RGB").save(out)
    return out, (cw, ch), (ax, ay, bw, bh)


def _over(fg, bg):
    """Expected RGB of translucent fg composited over opaque bg (for selfcheck)."""
    a = fg[3] / 255.0
    return tuple(round(fg[i] * a + bg[i] * (1 - a)) for i in range(3))


def _row_has(im, y, expect, tol=6):
    return any(all(abs(im.getpixel((x, y))[i] - expect[i]) <= tol for i in range(3))
               for x in range(0, im.width, 2))


def selfcheck():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        sky, soil = (200, 220, 235), (60, 45, 35)
        base = os.path.join(d, "base.png")
        im = Image.new("RGB", (600, 400), sky)
        ImageDraw.Draw(im).rectangle([0, 200, 600, 400], fill=soil)
        im.save(base)

        out = os.path.join(d, "sub", "out.png")  # also proves out-dir auto-creation
        spec = {"base": base, "out": out,
                "canvas": {"aspect": 2.5, "height": 400, "bg": "#ffffff"},
                "labels": [
                    {"text": "밝은 배경 라벨", "x": 50, "y": 20, "size": 28,
                     "leader": [50, 10]},                       # auto → dark scrim on sky
                    {"text": "어두운 배경 라벨", "x": 50, "y": 80, "size": 28},  # auto → light pill on soil
                ]}
        path, (w, h), art = render(spec)
        im = Image.open(path)
        assert (w, h) == (1000, 400), f"canvas aspect wrong: {(w, h)}"
        assert art == (200, 0, 600, 400), f"art_rect wrong: {art}"
        assert im.getpixel((2, 200)) == (255, 255, 255), "letterbox margin missing"
        # real translucency + auto theme: pill pixels must equal the alpha blend
        assert _row_has(im, 80, _over(DARK_SCRIM, sky)), "dark scrim blend missing on bright bg"
        assert _row_has(im, 320, _over(LIGHT_PILL, soil)), "light pill blend missing on dark bg"
        # leader target dot at (50%, 10%) → (500, 40), dark fill
        assert im.getpixel((500, 40))[:3] == LEADER_DARK[:3], "target dot missing"
        print("selfcheck OK")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--selfcheck":
        selfcheck()
    elif len(sys.argv) == 2:
        with open(sys.argv[1], encoding="utf-8") as fh:
            spec = json.load(fh)
        path, size, art_rect = render(spec)
        print(json.dumps({"out": path, "canvas": list(size),
                          "art_rect": list(art_rect)}, ensure_ascii=True))
    else:
        print(__doc__)
        sys.exit(2)
