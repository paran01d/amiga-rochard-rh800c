// L-bracket: hangs the CF adapter board off the unused external D-sub's
// two mounting screw holes. Print TWO (they are identical/symmetric).
//
//   panel leg  - flat against the inside of the rear panel, screwed through the
//                D-sub mounting hole (the jack-screw hole, usually 4-40 UNC)
//   board leg  - runs back from the panel; the CF board's FRONT mounting hole
//                (the CF-slot edge) screws into it
//
// D-sub holes are 62.0 mm apart, the board's front holes 62.2 mm apart, so
// both holes are SLOTS (sideways) to soak up that and any small offset.
//
// Coordinates: X = sideways (along the panel), Y = away from the panel into
// the case, Z = up. The panel's inside face is the plane Y = 0.

/* [Bracket] */
t          = 2.5;    // material thickness of both legs
leg_w      = 10;     // bracket width (along X)

/* [Panel leg (D-sub hole)] */
panel_hole_d   = 2.6;   // pilot: the screw passes through the D-sub hole and self-taps here
panel_slot     = 2.0;   // sideways slot travel for adjustment (oval hole)
drop           = 7.5;   // D-sub hole centre ABOVE the board-leg's top face (measured)
                        // (negative = hole below it; the leg is then a "Z")
panel_above    = 5;     // material above the hole centre

/* [Board leg (CF board front hole)] */
board_hole_d   = 2.6;   // pilot for an M3 self-tapper (3.2 for a clearance hole)
board_slot     = 2.0;   // sideways slot travel for adjustment (oval hole)
board_gap      = 0;     // gap between the panel leg and the board's CF-slot edge (0 = flush)
board_hole_in  = 7.1;   // board front hole centre, in from its flush (CF-slot) edge (measured)
board_beyond   = 5;     // material past the board hole centre

$fn = 40;

// ---------------------------------------------------------------------------

module slot(d, travel, len) {   // horizontal slot along X, axis along `len`
    hull() for (dx = [-travel / 2, travel / 2])
        translate([dx, 0, 0]) rotate([-90, 0, 0]) cylinder(d = d, h = len);
}
module vslot(d, travel, len) {  // slot along X, axis vertical
    hull() for (dx = [-travel / 2, travel / 2])
        translate([dx, 0, 0]) cylinder(d = d, h = len);
}

setback       = t + board_gap + board_hole_in;   // hole centre from the panel face
board_leg_len = setback + board_beyond;
panel_top     = max(drop + panel_above, t);
panel_bottom  = min(0, drop - panel_above);

difference() {
    union() {
        // panel leg: vertical plate against the panel, Y = 0 .. t
        translate([-leg_w / 2, 0, panel_bottom])
            cube([leg_w, t, panel_top - panel_bottom]);
        // board leg: horizontal plate, top face at Z = 0 (board sits on it)
        translate([-leg_w / 2, 0, -t])
            cube([leg_w, board_leg_len, t]);
    }
    // D-sub screw slot through the panel leg
    translate([0, -0.1, drop]) slot(panel_hole_d, panel_slot, t + 0.2);
    // board screw slot through the board leg
    translate([0, setback, -t - 0.1]) vslot(board_hole_d, board_slot, t + 0.2);
}
