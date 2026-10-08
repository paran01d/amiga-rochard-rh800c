// CF-adapter bracket for the RocHard RH800C 3.5" drive position.
//
// The plate takes the place of a 3.5" IDE drive and screws on with the SAME
// bottom-mount screws (6-32 UNC) the drive would use, so no new holes are
// needed. On top sit stand-offs for the CF-to-IDE adapter board, which can be
// moved/rotated so the CF slot lines up with the unused external DB socket.
//
// Coordinate system (looking down on the plate, i.e. on the drive's top side):
//   X = across the drive width (0 = left edge), Y = along the drive length
//   (0 = FRONT edge, the end opposite the IDE connector), Z = up.
//
// !! MEASURE YOUR CARD !! Defaults are the standard SFF-8301 3.5" bottom hole
// positions (95.25 mm across, A7 = 41.28 mm, A6 pair 44.45 mm further back).
// If the RocHard's mounting differs, change the hole_* values below.

/* [Plate] */
plate_w      = 101.6;   // drive width (the screw holes are placed on this)
plate_side_ext = 5;     // extra plate width on EACH side (screw posts don't move)
plate_l      = 100;     // how much of the drive length the plate covers (from the front edge)
plate_front_ext = 50;   // plate extends this far IN FRONT of the drive's front edge
plate_t      = 3;       // plate thickness

/* [Drive mounting holes (bottom, 6-32 UNC)] */
hole_span_x  = 95.25;   // centre-to-centre across the width (SFF-8301 A4)
hole_y1      = 41.28;   // first pair, from the front edge (SFF-8301 A7)
hole_pitch_y = 44.45;   // to the second pair (SFF-8301 A6)
// The screw comes up from below into the plate, as it would into a drive:
// - self-tapping a 6-32 into PLA/PETG: pilot ~2.9 mm
// - M3 / 6-32 heat-set insert: set to the insert's recommended bore
screw_pilot_d = 2.9;
boss_d        = 6.2;    // boss diameter around each screw hole
boss_h        = 7;      // total boss height (screw engagement depth)

/* [CF adapter board] */
// Measured with the board landscape, looking down on its component side:
adapter_w     = 73.5;   // board width  (left-right, X before rotation)
adapter_l     = 37.2;   // board height (top-bottom, Y before rotation)
// Hole centres exactly as measured: [from TOP edge, from LEFT edge]
adapter_holes_measured = [[3.4, 7.2], [3.4, 69.4], [32.4, 7.2], [32.4, 69.4]];
adapter_x     = 5;      // board's left edge, measured from the origin (X = 0)
adapter_front_gap = 0;  // board (CF-slot) edge distance from the PLATE front edge (0 = flush)
adapter_rot   = 0;      // rotate the board footprint (degrees, about that corner)
// Mount the board COMPONENT SIDE DOWN (flipped left-to-right about the
// front-back axis, so the CF-slot edge stays at the front). Mirrors the holes.
adapter_upside_down = true;
adapter_hole_d     = 2.6;  // pilot for M3 self-tap (or insert bore)
standoff_d    = 6;
standoff_h    = 15;     // PLACEHOLDER: tallest underside part (+ plugged connectors) + margin

/* [Options] */
show_drive_ghost   = true;   // translucent 3.5" drive outline for reference
show_adapter_ghost = true;   // translucent adapter board outline
$fn = 40;

// ---------------------------------------------------------------------------

drive_l = 147;              // full 3.5" drive length, for the ghost only
adapter_y = adapter_front_gap - plate_front_ext;   // board follows the plate front edge

hole_x0 = (plate_w - hole_span_x) / 2;
drive_holes = [
    [hole_x0,               hole_y1],
    [hole_x0 + hole_span_x, hole_y1],
    [hole_x0,               hole_y1 + hole_pitch_y],
    [hole_x0 + hole_span_x, hole_y1 + hole_pitch_y],
];

// convert [from top, from left] to board-local X (from left) / Y (from bottom)
adapter_holes = [for (h = adapter_holes_measured)
                    [adapter_upside_down ? adapter_w - h[1] : h[1], adapter_l - h[0]]];

module place_on_adapter() {
    translate([adapter_x, adapter_y, 0]) rotate([0, 0, adapter_rot]) children();
}

module bracket() {
    difference() {
        union() {
            translate([-plate_side_ext, -plate_front_ext, 0])
                cube([plate_w + 2 * plate_side_ext, plate_l + plate_front_ext, plate_t]);
            // bosses for the drive screws
            for (h = drive_holes)
                translate([h[0], h[1], 0]) cylinder(d = boss_d, h = boss_h);
            // stand-offs for the adapter board
            place_on_adapter()
                for (h = adapter_holes)
                    translate([h[0], h[1], 0])
                        cylinder(d = standoff_d, h = plate_t + standoff_h);
        }
        // drive screw pilots, from underneath
        for (h = drive_holes)
            translate([h[0], h[1], -0.1]) cylinder(d = screw_pilot_d, h = boss_h + 0.2);
        // adapter screw pilots
        place_on_adapter()
            for (h = adapter_holes)
                translate([h[0], h[1], -0.1])
                    cylinder(d = adapter_hole_d, h = plate_t + standoff_h + 0.2);
    }
}

bracket();

if (show_drive_ghost)
    %cube([plate_w, drive_l, 26.1]);   // the space the 1"-high drive occupied

if (show_adapter_ghost)
    %place_on_adapter()
        translate([0, 0, plate_t + standoff_h]) cube([adapter_w, adapter_l, 1.6]);
