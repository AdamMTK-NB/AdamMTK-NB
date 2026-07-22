"""
Convert a portrait photo into a CLEAN, monochrome ASCII-art SVG (Andrew6rant
style: one light-gray color, subject isolated on a dark background) that "types"
itself in like a terminal, then holds.

Monochrome is deliberate -- per-character rainbow color is what makes ASCII
portraits look noisy. One fill color + a good density ramp + high contrast (so a
busy background washes out to blank) reads as neat and legible.

GitHub renders SVGs embedded via <img> and runs their SMIL animations there (JS
does not run). Each row is revealed with a left-to-right clip wipe plus a small
block cursor riding the wipe edge, staggered top -> bottom, so the whole
portrait prints once and freezes.
"""
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import html
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# defaults to the prepped grayscale image (see prep_photo.py), which already has
# the background removed + local contrast applied.
ARGS = [a for a in sys.argv[1:] if a != "--full"]
SRC = ARGS[0] if len(ARGS) > 0 else os.path.join(HERE, "..", "source-prepped.png")
OUT = ARGS[1] if len(ARGS) > 1 else os.path.join(HERE, "..", "adam-ascii.svg")

COLS = 100
ROWS = 56
CELL_W = 8
CELL_H = 15
RAMP = " .`:-=+*cs#%@"  # bright(sparse) -> dark(dense); leading space clears bg

# Face-forward crop keeps more rows on eyes/nose/mouth so thin features
# (mustache, smile) survive the downsample instead of merging into a blob.
# Set FULL_FRAME=1 (or pass --full) for logos/icons that must not be cropped.
FULL_FRAME = bool(os.environ.get("FULL_FRAME")) or "--full" in sys.argv
FACE_HEIGHT_FRAC = 1.0 if FULL_FRAME else 0.66
FACE_SIDE_TRIM = 0.0 if FULL_FRAME else 0.08
DARK_BIAS = 0.35          # blend mean toward darker percentile (preserves thin dark lines)
# Extra white margin so circular logos aren't flush against the status bar.
FRAME_PAD_FRAC = 0.06 if FULL_FRAME else 0.0

CONTRAST = 1.28
BRIGHTNESS = 1.02
GAMMA = 1.02
SHARPEN = True
WHITE_FLOOR = 0.84        # luminance above this is forced to blank (space)

PAD = 20
TITLEBAR_H = 30
STATUS_H = 30
ART_W = COLS * CELL_W
ART_H = ROWS * CELL_H
CANVAS_W = ART_W + PAD * 2
CANVAS_H = TITLEBAR_H + ART_H + STATUS_H + PAD

BG = "#0d1117"
BG2 = "#111722"
FRAME = "#30363d"
TITLE_TEXT = "#7d8590"
INK = "#c9d1d9"      # the single ascii color (matches Andrew6rant)
CURSOR = "#c9d1d9"

# ---- reveal timing (one-shot; a cursor rasters top -> bottom) -------------
ROW_DUR = 0.11
STAGGER = 0.11       # == ROW_DUR -> a single cursor sweeping down

# ---- 1. sample the image into a COLS x ROWS grayscale grid ----------------
im = Image.open(SRC).convert("L")               # grayscale

# Crop to subject, then bias toward the face so mouth/mustache get more pixels.
mask = im.point(lambda p: 255 if p < 248 else 0)
bbox = mask.getbbox()
if bbox:
    x0, y0, x1, y1 = bbox
    bw, bh = max(1, x1 - x0), max(1, y1 - y0)
    x0 = int(x0 + bw * FACE_SIDE_TRIM)
    x1 = int(x1 - bw * FACE_SIDE_TRIM)
    y1 = int(y0 + bh * FACE_HEIGHT_FRAC)
    im = im.crop((x0, y0, x1, y1))

if FRAME_PAD_FRAC > 0:
    pad = int(max(im.size) * FRAME_PAD_FRAC)
    canvas = Image.new("L", (im.width + pad * 2, im.height + pad * 2), 255)
    canvas.paste(im, (pad, pad))
    im = canvas

if SHARPEN:
    im = im.filter(ImageFilter.UnsharpMask(radius=1.8, percent=175, threshold=2))
im = ImageEnhance.Brightness(im).enhance(BRIGHTNESS)
im = ImageEnhance.Contrast(im).enhance(CONTRAST)

# Dark-biased block sample: average each cell, then pull toward its darker
# values so a thin mustache does not get averaged away into skin tone.
cw = im.width / COLS
ch = im.height / ROWS
src = im.load()

STATIC = bool(os.environ.get("STATIC"))  # emit frozen state for previews

rows_txt = []
for y in range(ROWS):
    chars = []
    y0 = int(y * ch)
    y1 = max(y0 + 1, int((y + 1) * ch))
    for x in range(COLS):
        x0 = int(x * cw)
        x1 = max(x0 + 1, int((x + 1) * cw))
        vals = [src[px, py] for py in range(y0, y1) for px in range(x0, x1)]
        vals.sort()
        mean = sum(vals) / len(vals)
        dark = vals[max(0, int(len(vals) * 0.22))]
        lum = ((1.0 - DARK_BIAS) * mean + DARK_BIAS * dark) / 255.0
        lum = pow(lum, GAMMA)
        if lum >= WHITE_FLOOR:
            chars.append(" ")
            continue
        idx = int((1.0 - lum) * (len(RAMP) - 1) + 0.5)
        idx = max(0, min(len(RAMP) - 1, idx))
        chars.append(RAMP[idx])
    rows_txt.append("".join(chars))

art_top = TITLEBAR_H + PAD * 0.35

# ---- 2. assemble SVG ------------------------------------------------------
parts = []
parts.append(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" '
    f'viewBox="0 0 {CANVAS_W} {CANVAS_H}" font-family="ui-monospace, SFMono-Regular, '
    f'Menlo, Consolas, monospace">'
)
parts.append('<defs>'
             f'<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/>'
             f'</linearGradient></defs>')

parts.append(f'<rect width="{CANVAS_W}" height="{CANVAS_H}" rx="12" fill="url(#bg)"/>')
parts.append(f'<rect x="0.5" y="0.5" width="{CANVAS_W-1}" height="{CANVAS_H-1}" rx="12" '
             f'fill="none" stroke="{FRAME}" stroke-width="1"/>')

parts.append(f'<line x1="0" y1="{TITLEBAR_H}" x2="{CANVAS_W}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>')
for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
    parts.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dotcol}"/>')
parts.append(f'<text x="{CANVAS_W/2}" y="{TITLEBAR_H/2 + 4}" fill="{TITLE_TEXT}" font-size="12" '
             f'text-anchor="middle">adam@github: ~$ ./portrait.sh</text>')

# one <text> per row (single color -> no per-char markup, tiny file)
font_size = CELL_H * 0.86
for ry, line in enumerate(rows_txt):
    y = art_top + ry * CELL_H + CELL_H * 0.74
    row_y = art_top + ry * CELL_H
    delay = ry * STAGGER
    safe = html.escape(line)
    text = (f'<text xml:space="preserve" x="{PAD}" y="{y:.1f}" fill="{INK}" '
            f'font-size="{font_size:.1f}" textLength="{ART_W}" lengthAdjust="spacing">{safe}</text>')

    if STATIC:
        parts.append(text)
        continue

    parts.append(
        f'<clipPath id="r{ry}"><rect x="{PAD}" y="{row_y:.1f}" height="{CELL_H}" width="0">'
        f'<animate attributeName="width" from="0" to="{ART_W}" begin="{delay:.3f}s" '
        f'dur="{ROW_DUR:.2f}s" fill="freeze"/></rect></clipPath>'
    )
    parts.append(f'<g clip-path="url(#r{ry})">{text}</g>')
    parts.append(
        f'<rect y="{row_y+1:.1f}" width="{CELL_W}" height="{CELL_H-2}" fill="{CURSOR}" opacity="0">'
        f'<animate attributeName="x" from="{PAD}" to="{PAD+ART_W}" begin="{delay:.3f}s" '
        f'dur="{ROW_DUR:.2f}s" fill="freeze"/>'
        f'<set attributeName="opacity" to="0.85" begin="{delay:.3f}s"/>'
        f'<set attributeName="opacity" to="0" begin="{delay+ROW_DUR:.3f}s"/></rect>'
    )

# status bar with a steady blinking cursor
status_line_y = TITLEBAR_H + ART_H + PAD * 0.35
status_y = status_line_y + 19
parts.append(f'<line x1="0" y1="{status_line_y:.1f}" x2="{CANVAS_W}" y2="{status_line_y:.1f}" stroke="{FRAME}"/>')
parts.append(f'<text x="{PAD}" y="{status_y:.1f}" fill="{TITLE_TEXT}" font-size="13">'
             f'adam@github:~$ whoami <tspan fill="{INK}">Adam Maatouk</tspan></text>')
parts.append(f'<rect x="{PAD+208}" y="{status_y-12:.1f}" width="8" height="14" fill="{INK}">'
             f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" '
             f'dur="1s" repeatCount="indefinite"/></rect>')

parts.append("</svg>")
svg = "".join(parts)
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write(svg)
print("wrote", OUT, len(svg), "bytes;", CANVAS_W, "x", CANVAS_H)
