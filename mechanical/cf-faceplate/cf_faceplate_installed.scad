// View-only: the faceplate as INSTALLED (turned upside down, i.e. rotated
// 180 degrees about the front-back axis). Print cf_faceplate.stl, not this.
// 80 x 17 = current plate width x height from cf_faceplate.scad
// (plate_w + led_side_ext, plate_h) - update if those change.
translate([80, 0, 17]) rotate([0, 180, 0]) import("cf_faceplate.stl");
