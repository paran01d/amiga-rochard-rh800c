// CF faceplate for the unused external D-sub opening on the RocHard.
//
// A plate that sits BEHIND the D-sub cut-out, screwed to the case through the
// two D-sub mounting holes. It has a slot for the CF card socket and a hole
// for the activity LED. Two tabs ("legs") run back from it; the CF adapter
// board (mounted component side DOWN) screws onto them through its two front
// mounting holes, so the socket hangs into the slot.
//
// Left/right are as seen from OUTSIDE the case, looking at the D-sub opening.
// Coordinates: X = across the plate (0 = left edge seen from outside), Z = up
// (0 = bottom edge), Y = into the case (the face against the panel is Y = 0).
// The geometry is built inside-out and mirrored at the end so that holds.

/* [Plate] */
plate_w = 75;          // +2.5 mm on each side (was 70)
v_grow  = 2.5;         // added to the top edge and the bottom edge
plate_h_full = 13 + 2 * v_grow;   // height before trimming (everything is placed from this)
top_trim = 1;          // removed from the LEG edge (model top = installed bottom)
plate_h = plate_h_full - top_trim;
led_side_ext = 5;      // extra plate width added on the LED side only
plate_t = 2;

/* [D-sub mounting holes] */
dsub_spacing = 62;      // centre-to-centre of the pair (kept fixed; the pair shifts together)
dsub_z       = plate_h_full / 2; // hole centre height (unchanged by top_trim)
dsub_hole_d  = 2.6;     // self-tap pilot: the screw bites into the plate + boss
dsub_slot    = 0;       // sideways slot travel (0 = round)
// Left hole as installed, seen from outside (the side away from the LED).
// Positive moves it toward that end of the plate. Right hole stays put.
dsub_left_out = 1;
// Both holes then shift toward the edge that has the LED, until the hole
// beside the LED is this far (centre to centre, sideways) from the LED centre.
dsub_led_gap = 6;
boss_d       = 6;       // boss (post) behind each hole, for more thread
led_clear_d  = 5.5;     // clearance pocket for the LED body/flange, cut from anything behind the plate
boss_len     = 3;       // boss depth behind the plate (kept short to clear the PCB screws)

/* [CF card slot] */
cf_w        = 46;
cf_h        = 6;
cf_top_gap  = 1;        // slot top edge below the plate top edge, before installed_up
// Positive moves the slot up once the plate is installed (that direction is
// toward the bottom edge of this model, because it mounts upside down).
installed_up = 2;

/* [LED] */
led_d        = 4;       // hole diameter (4 mm LED)
led_side     = -1;      // -1 = LEFT of the slot, +1 = RIGHT (as seen from outside)
led_from_cf  = 4.5;     // LED centre, out from that side's slot edge (D-sub holes are placed from this)
led_move_out = 1;       // then move the LED this much further from the slot (D-sub holes stay put)

/* [Board tabs (legs)] */
tab_spacing  = 64;      // PCB front holes, centre-to-centre. Not the D-sub holes.
tab_t        = 2.5;     // leg (and joining rib) thickness, flush with the leg-side plate edge
// Legs are one uniform thickness (no step). The board rests on the leg's inner
// face, leg_up above the ORIGINAL (untrimmed) leg-side edge once installed;
// the leg thickness grows outward from there.
leg_up       = 2;       // (unused now: legs are flush with the plate edge)
leg_far_in   = 1;       // leg AWAY from the LED: moved this much toward the LED side
leg_led_out  = 2;       // leg on the LED side: moved this much further from the LED
tab_w        = 8;       // tab width (along X)
board_hole_y = 7.3;     // board hole centre, back from the plate's BACK face (measured from the fascia)
                        // (the board edge butts against the plate back)
tab_beyond   = 4;       // tab material past the hole centre
tab_hole_d   = 2.6;     // self-tap pilot
tab_slot     = 2;       // sideways slot travel (oval, for adjustment)
rib_depth    = 4;       // rib joining the legs along the plate back (0 = none)

$fn = 40;

// ---------------------------------------------------------------------------

cx      = plate_w / 2;
// Installed bottom is this model's top edge. The legs follow that new edge.
// The slot stays put against the original edge; v_grow sits outside it.
orig_top = plate_h_full - v_grow;
board_face_z = plate_h - tab_t;          // legs FLUSH with the leg-side plate edge (no overhang)
cf_z0   = orig_top - cf_top_gap - cf_h - installed_up;
cf_x0   = cx - cf_w / 2;                              // recentered on the plate
function led_x_at(d) = cf_x0 + (led_side < 0 ? -d : cf_w + d);
led_x0  = led_x_at(led_from_cf);                     // reference for the D-sub holes
led_x   = led_x_at(led_from_cf + led_move_out);      // actual LED position
led_z   = cf_z0 + cf_h / 2;                          // centred on the slot height
// s = +1 is the left hole once the plate is installed and viewed from outside.
function dsub_base_x(s) = cx + s * dsub_spacing / 2 + (s > 0 ? dsub_left_out : 0);
dsub_shift = (led_x0 + led_side * dsub_led_gap) - dsub_base_x(led_side);
function dsub_pre_x(s) = dsub_base_x(s) + dsub_shift;
hole_y  = plate_t + board_hole_y;          // tab hole, from the plate front face
tab_len = board_hole_y + tab_beyond;
// leg centres: s = led_side is the LED-side leg
function leg_x(s) = cx + s * tab_spacing / 2
                    + (s == led_side ? led_side * leg_led_out : led_side * leg_far_in);

module xslot(d, travel, len) {   // slot along X, axis along +Y
    hull() for (dx = [-travel / 2, travel / 2])
        translate([dx, 0, 0]) rotate([-90, 0, 0]) cylinder(d = d, h = len);
}
module zslot(d, travel, len) {   // slot along X, axis along +Z
    hull() for (dx = [-travel / 2, travel / 2])
        translate([dx, 0, 0]) cylinder(d = d, h = len);
}

translate([plate_w, 0, 0]) mirror([1, 0, 0])   // X as seen from outside
difference() {
    union() {
        translate([led_side < 0 ? -led_side_ext : 0, 0, 0])          // the plate
            cube([plate_w + led_side_ext, plate_t, plate_h]);
        if (boss_len > 0) for (s = [-1, 1])                      // D-sub bosses
            translate([dsub_pre_x(s), plate_t, dsub_z])
                rotate([-90, 0, 0]) cylinder(d = boss_d, h = boss_len);
        // rib along the back of the plate joining the two legs into one piece
        translate([leg_x(-1) - tab_w / 2, plate_t, board_face_z])
            cube([leg_x(1) - leg_x(-1) + tab_w, rib_depth, tab_t]);
        for (s = [-1, 1])                                        // board legs
            translate([leg_x(s) - tab_w / 2, plate_t, board_face_z])
                cube([tab_w, tab_len, tab_t]);                   // uniform, no step
    }
    // CF card slot
    translate([cf_x0, -0.1, cf_z0]) cube([cf_w, plate_t + 0.2, cf_h]);
    // LED hole
    translate([led_x, -0.1, led_z]) rotate([-90, 0, 0]) cylinder(d = led_d, h = plate_t + 0.2);
    // LED body/flange clearance behind the plate (keeps the boss off the LED)
    translate([led_x, plate_t, led_z]) rotate([-90, 0, 0]) cylinder(d = led_clear_d, h = boss_len + 20);
    // D-sub screw holes (through plate + boss)
    for (s = [-1, 1])
        translate([dsub_pre_x(s), -0.1, dsub_z])
            xslot(dsub_hole_d, dsub_slot, plate_t + boss_len + 0.2);
    // board screw holes in the tabs
    for (s = [-1, 1])
        translate([leg_x(s), hole_y, board_face_z - 0.1])
            zslot(tab_hole_d, tab_slot, tab_t + 0.2);
}

// clearance report (shown in the console)
echo(str("LED-side boss: wall between screw pilot and LED pocket = ",
         sqrt(pow(dsub_pre_x(led_side) - led_x, 2) + pow(dsub_z - led_z, 2)) - led_clear_d / 2 - dsub_hole_d / 2, " mm"));
echo(str("Boss Z ", dsub_z - boss_d / 2, "..", dsub_z + boss_d / 2, "  vs legs/rib Z ", board_face_z, "..", board_face_z + tab_t));
echo(str("LED hole edge to nearest D-sub hole edge: ",
         sqrt(pow(dsub_pre_x(led_side) - led_x, 2) + pow(dsub_z - led_z, 2)) - (dsub_hole_d + dsub_slot) / 2 - led_d / 2, " mm"));
echo(str("D-sub holes at ", dsub_pre_x(-1), " and ", dsub_pre_x(1),
         ", ", abs(dsub_pre_x(1) - dsub_pre_x(-1)), " mm apart"));
echo(str("LED-side D-sub centre to LED centre, sideways: ", abs(dsub_pre_x(led_side) - led_x), " mm"));
echo(str("Left D-sub hole is ", plate_w - dsub_pre_x(1), " mm from the left end (installed, outside)"));

echo(str("PCB legs at ", leg_x(-1), " and ", leg_x(1), ", ", leg_x(1) - leg_x(-1), " mm apart"));
echo(str("CF slot: X ", cf_x0, "..", cf_x0 + cf_w, "  Z ", cf_z0, "..", cf_z0 + cf_h));
echo(str("Plate height ", plate_h, " (trimmed ", top_trim, " on the leg edge), width ", plate_w + led_side_ext,
         "; legs Z ", board_face_z, "..", board_face_z + tab_t));
echo(str("LED centre: X ", led_x, "  Z ", led_z));
