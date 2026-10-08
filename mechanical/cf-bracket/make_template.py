#!/usr/bin/env python3
"""Make a 1:1 A4 top-view template of cf_bracket.scad for checking against the card.

Reads the parameters straight from cf_bracket.scad, writes cf_bracket_template.svg
and (via Inkscape) cf_bracket_template.pdf. Print at 100% / "actual size".
"""
import math, re, subprocess, pathlib

HERE = pathlib.Path(__file__).parent
SCAD = HERE / "cf_bracket.scad"

# --- read numeric parameters from the .scad -----------------------------------
p = {}
for line in SCAD.read_text().splitlines():
    m = re.match(r"\s*([a-z_0-9]+)\s*=\s*([-0-9.]+)\s*;", line)
    if m:
        p[m.group(1)] = float(m.group(2))

pw, pl = p["plate_w"], p["plate_l"]
ext = p.get("plate_front_ext", 0.0)
side = p.get("plate_side_ext", 0.0)
ay = p.get("adapter_front_gap", 0.0) - ext      # board follows the plate front edge
span, y1, pitch = p["hole_span_x"], p["hole_y1"], p["hole_pitch_y"]
pilot, boss = p["screw_pilot_d"], p["boss_d"]
aw, al, ax, arot = p["adapter_w"], p["adapter_l"], p["adapter_x"], p["adapter_rot"]
ahole, sod = p["adapter_hole_d"], p["standoff_d"]
# measured holes: [from top, from left] -> board-local (x from left, y from bottom)
m = re.search(r"adapter_holes_measured\s*=\s*(\[.*?\]\s*\])\s*;", SCAD.read_text())
measured = [tuple(float(v) for v in re.findall(r"[-0-9.]+", pair))
            for pair in re.findall(r"\[([^\[\]]+)\]", m.group(1))]
DRIVE_L = 147.0

# --- page layout: A4 portrait, mm. Drive front edge at the bottom, Y up. -------
W, H = 210.0, 297.0
OX, OY = 54.0, 214.0                       # page position of the origin
def P(x, y):                               # model (X right, Y up) -> page
    return OX + x, OY - y

hx0 = (pw - span) / 2
drive_holes = [(hx0, y1), (hx0 + span, y1), (hx0, y1 + pitch), (hx0 + span, y1 + pitch)]

def adapter_pt(x, y):                      # board-local -> model, with rotation
    a = math.radians(arot)
    return ax + x * math.cos(a) - y * math.sin(a), ay + x * math.sin(a) + y * math.cos(a)

flip = re.search(r"adapter_upside_down\s*=\s*true", SCAD.read_text()) is not None
ahs = [((aw - fl) if flip else fl, al - ft) for (ft, fl) in measured]

out = []
def add(s): out.append(s)
def line(x1, y1_, x2, y2, w=0.25, c="#000", dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<line x1="{x1:.3f}" y1="{y1_:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" stroke="{c}" stroke-width="{w}"{d}/>')
def circle(cx, cy, r, w=0.25, c="#000", fill="none"):
    add(f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" stroke="{c}" stroke-width="{w}" fill="{fill}"/>')
def text(x, y, s, size=2.6, c="#000", anchor="start", weight="normal"):
    add(f'<text x="{x:.3f}" y="{y:.3f}" font-family="sans-serif" font-size="{size}" fill="{c}" '
        f'text-anchor="{anchor}" font-weight="{weight}">{s}</text>')
def cross(cx, cy, r, c="#000", w=0.2):
    line(cx - r, cy, cx + r, cy, w, c); line(cx, cy - r, cx, cy + r, w, c)
def poly(pts, w=0.3, c="#000", dash=None, fill="none"):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    s = " ".join(f"{x:.3f},{y:.3f}" for x, y in pts)
    add(f'<polygon points="{s}" stroke="{c}" stroke-width="{w}" fill="{fill}"{d}/>')

add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">')
add(f'<rect width="{W}" height="{H}" fill="#fff"/>')

# title + instructions
text(10, 12, "RocHard CF bracket - 1:1 TOP VIEW TEMPLATE", 5, weight="bold")
text(10, 18, "Print at 100% / 'Actual size' (no fit-to-page). Check the 100 mm ruler with calipers before use.", 3)
text(10, 22.5, "Generated from cf_bracket.scad - dims in mm. Origin = FRONT-LEFT corner of the 3.5in drive footprint.", 3)

# calibration rulers: 100 mm horizontal (top) and vertical (left)
rx, ry = 10, 32
line(rx, ry, rx + 100, ry, 0.35)
for i in range(0, 101):
    t = 3 if i % 10 == 0 else (2 if i % 5 == 0 else 1.2)
    line(rx + i, ry, rx + i, ry - t, 0.15)
    if i % 10 == 0:
        text(rx + i, ry + 3.6, str(i), 2.4, anchor="middle")
text(rx + 104, ry + 1, "100 mm calibration", 2.8)
vx, vy = 18, OY
line(vx, vy, vx, vy - 100, 0.35)
for i in range(0, 101):
    t = 3 if i % 10 == 0 else (2 if i % 5 == 0 else 1.2)
    line(vx, vy - i, vx - t, vy - i, 0.15)
    if i % 10 == 0:
        text(vx - 4, vy - i + 0.9, str(i), 2.4, anchor="end")

# drive footprint (reference) and plate outline
x0, ytop = P(0, DRIVE_L)
add(f'<rect x="{x0:.3f}" y="{ytop:.3f}" width="{pw:.3f}" height="{DRIVE_L:.3f}" fill="none" '
    f'stroke="#888" stroke-width="0.3" stroke-dasharray="2,1.5"/>')
text(OX + pw / 2, ytop - 2, "3.5in drive footprint (101.6 x 147) - REAR / IDE connector end", 2.6, "#666", "middle")
line(OX - 6, OY, OX + pw + 6, OY, 0.2, "#888", "2,1.5")
text(OX + pw + 7, OY + 1, "FRONT edge of drive", 2.6, "#666")
x0, ytop = P(-side, pl)
add(f'<rect x="{x0:.3f}" y="{ytop:.3f}" width="{pw + 2 * side:.3f}" height="{pl + ext:.3f}" fill="#eef4fc" '
    f'stroke="#1f5fbf" stroke-width="0.4"/>')
text(OX + pw + side - 1, ytop + 3.5, f"bracket plate {pw + 2 * side:g} x {pl + ext:g} ({ext:g} in front, +{side:g} each side)", 2.6, "#1f5fbf", "end")

# drive screw holes
for (hx, hy) in drive_holes:
    cx, cy = P(hx, hy)
    circle(cx, cy, boss / 2, 0.25, "#1f5fbf")
    circle(cx, cy, pilot / 2, 0.25, "#c00")
    cross(cx, cy, 4.5, "#c00", 0.15)
    right = hx > pw / 2
    text(cx + (-5 if right else 5), cy - 2.2, f"({hx:.2f}, {hy:.2f})", 2.4, "#c00", "end" if right else "start")
# dimension callouts for the hole pattern
ax1, ay1 = P(drive_holes[0][0], drive_holes[0][1]); bx1, _ = P(drive_holes[1][0], 0)
_, ay2 = P(0, drive_holes[2][1])
line(ax1, ay2 - 6, bx1, ay2 - 6, 0.15, "#c00", "1,1")
text((ax1 + bx1) / 2, ay2 - 7, f"{span:g} c-c (6-32 drive screws)", 2.6, "#c00", "middle")
text(ax1 + 3, (ay1 + ay2) / 2, f"{pitch:g} c-c", 2.6, "#c00")
text(ax1 + 3, OY - y1 / 2, f"{y1:g} from front", 2.6, "#c00")

# CF adapter footprint + stand-offs
corners = [adapter_pt(0, 0), adapter_pt(aw, 0), adapter_pt(aw, al), adapter_pt(0, al)]
poly([P(*c) for c in corners], 0.3, "#2a8a2a", "1.5,1")
lx, ly = P(*adapter_pt(aw / 2, al / 2))
text(lx, ly, f"CF adapter {aw:g} x {al:g}" + (" (UPSIDE DOWN)" if flip else ""), 2.6, "#2a8a2a", "middle")
for h in ahs:
    cx, cy = P(*adapter_pt(*h))
    circle(cx, cy, sod / 2, 0.25, "#2a8a2a")
    circle(cx, cy, ahole / 2, 0.25, "#2a8a2a")
    cross(cx, cy, 3, "#2a8a2a", 0.12)

# origin marker + axes
cross(OX, OY, 8, "#000", 0.35)
circle(OX, OY, 1.2, 0.35)
text(OX - 2, OY + 9, "ORIGIN (0,0)", 3, "#000", "end", "bold")
line(OX, OY, OX + 25, OY, 0.35); text(OX + 26, OY + 1, "+X", 3, weight="bold")
line(OX, OY, OX, OY - 25, 0.35); text(OX + 1, OY - 26, "+Y", 3, weight="bold")

add("</svg>")
svg = HERE / "cf_bracket_template.svg"
svg.write_text("\n".join(out))
pdf = HERE / "cf_bracket_template.pdf"
subprocess.run(["inkscape", str(svg), "--export-type=pdf", f"--export-filename={pdf}"],
               check=True, capture_output=True)
print(f"wrote {svg.name} and {pdf.name}")
