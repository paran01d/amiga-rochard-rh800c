# Mechanical

3D-printable parts for mounting a CF-to-IDE adapter in the RocHard's case, all written in [OpenSCAD](https://openscad.org/).

## cf-faceplate: the design in use

[`cf-faceplate/cf_faceplate.scad`](cf-faceplate/cf_faceplate.scad) (with `cf_faceplate.stl` prebuilt) is a plate that sits **behind the case's unused external D-sub opening**. It's screwed to the case through the D-sub's two mounting holes, which go through the plate into 3 mm-deep bosses (posts) behind it. The plate has a slot for the CF socket and a hole for the activity LED. Two tabs run back from the plate, and the CF adapter board screws onto them through its front mounting holes, **mounted upside down** (component side down), so the socket hangs into the slot.

- **Parametric.** Plate size, D-sub hole spacing and offsets, slot and LED positions, and boss and pilot-hole sizes are all variables at the top of the `.scad`. Measure your case and adapter, then adjust the values.
- **Printing:** print it lying on its back, in **PETG**.
- `cf_faceplate_installed.scad` is for viewing only. It shows the part turned over as installed. Don't print it.
- The PNGs show the part and its fit in the case.

## Earlier designs (abandoned)

| Folder | Idea |
|--------|------|
| [`cf-bracket/`](cf-bracket/) | A plate in the 3.5" drive position that uses the drive's bottom screw holes, with standoffs for the adapter. `make_template.py` produces a 1:1 printable top-view template (`cf_bracket_template.pdf`) for checking it against the card. |
| [`dsub-bracket/`](dsub-bracket/) | A pair of L-brackets that hang the adapter off the D-sub screw holes. The faceplate replaced them. |

## tools/make_viewer.py

`make_viewer.py` wraps an STL in a self-contained HTML page that shows it in three.js (drag to rotate, scroll to zoom). The three.js scripts load from a CDN. Usage: `python3 tools/make_viewer.py cf-faceplate/cf_faceplate.stl` writes `cf_faceplate_view.html` next to the STL (or give an output path as a second argument).
