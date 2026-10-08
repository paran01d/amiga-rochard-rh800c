#!/usr/bin/env python3
"""
parse_measured.py -- Convert a minipro --logicic_out XML into a CSV.

minipro rewrites the L/H/Z placeholders in each vector with the actual
observed state after driving the vector. This tool re-reads the driven
inputs and the observed outputs and emits one row per vector:

    input_hex, output_hex, in_<name>[, ...], out_<name>[, ...]

where output bits are 0 (measured LOW), 1 (measured HIGH), or Z (tri-state).
Any per-pin 'Z' collapses to bit 1 in output_hex (matches MCP pull-up model)
but is preserved in the per-column tri_state flag.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gal_configs


# Tri-state token in the observed column
TRISTATE_TOKEN = "Z"


def parse_vector_line(text: str) -> list[str]:
    """Split a vector body into per-pin tokens."""
    tokens = text.strip().split()
    return tokens


def read_measured(path: Path) -> tuple[str, int, list[list[str]]]:
    """Return (chip_name, pin_count, [tokens per vector])."""
    tree = ET.parse(path)
    ic = tree.getroot().find(".//ic")
    if ic is None:
        raise SystemExit(f"no <ic> element in {path}")
    name = ic.get("name", "UNKNOWN")
    pins = int(ic.get("pins", "0"))
    if pins <= 0:
        raise SystemExit(f"bad pins attribute in {path}")
    vectors = []
    for v in ic.findall("vector"):
        toks = parse_vector_line(v.text or "")
        if len(toks) != pins:
            raise SystemExit(
                f"vector id={v.get('id')} has {len(toks)} tokens, expected {pins}")
        vectors.append(toks)
    return name, pins, vectors


def token_to_bit(tok: str) -> tuple[int, bool]:
    """Return (bit_value, is_tri_state).  Raises on unexpected token."""
    if tok in ("0", "L"):
        return 0, False
    if tok in ("1", "H"):
        return 1, False
    if tok == "Z":
        # Undriven; report as HIGH in the packed word (pull-up default) but
        # keep the tri-state flag so downstream can tell.
        return 1, True
    raise SystemExit(f"unexpected pin token {tok!r}")


def emit_csv(cfg: gal_configs.GALConfig, vectors: list[list[str]],
             out_path: Path) -> int:
    in_cols = [f"in_{p}" for p in cfg.input_pins]
    out_cols = [f"out_{p}" for p in cfg.output_pins]
    tristate_cols = [f"z_{p}" for p in cfg.output_pins]
    in_hex_width = (len(cfg.input_pins) + 3) // 4
    out_hex_width = (len(cfg.output_pins) + 3) // 4

    n = 0
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["input_hex", "output_hex", *in_cols, *out_cols, *tristate_cols])
        for tokens in vectors:
            in_vals = []
            out_vals = []
            out_z = []
            input_word = 0
            output_word = 0
            for i, pin in enumerate(cfg.input_pins):
                bit, _ = token_to_bit(tokens[pin - 1])
                in_vals.append(bit)
                if bit:
                    input_word |= 1 << i
            for i, pin in enumerate(cfg.output_pins):
                bit, z = token_to_bit(tokens[pin - 1])
                out_vals.append(bit)
                out_z.append(1 if z else 0)
                if bit:
                    output_word |= 1 << i
            w.writerow([
                f"{input_word:0{in_hex_width}X}",
                f"{output_word:0{out_hex_width}X}",
                *in_vals, *out_vals, *out_z,
            ])
            n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chip", help="chip name (UA6, U11, UA4) -- must match generator")
    ap.add_argument("-i", "--input", required=True, help="minipro --logicic_out XML")
    ap.add_argument("-o", "--output", help="CSV output (default: <chip>_measured.csv)")
    args = ap.parse_args()

    cfg = gal_configs.get(args.chip)
    in_path = Path(args.input)
    out_path = Path(args.output or f"{cfg.name.lower()}_measured.csv")

    name, pins, vectors = read_measured(in_path)
    if pins != cfg.pins:
        raise SystemExit(f"pin count mismatch: XML says {pins}, config says {cfg.pins}")
    if name != cfg.name:
        print(f"warning: XML ic name {name!r} != config {cfg.name!r}", file=sys.stderr)

    n = emit_csv(cfg, vectors, out_path)
    print(f"parsed {n} vectors from {in_path}", file=sys.stderr)
    print(f"wrote {out_path}", file=sys.stderr)

    # Quick per-output summary
    print("", file=sys.stderr)
    print("per-output-pin state totals (0 / 1 / Z):", file=sys.stderr)
    counts = {p: [0, 0, 0] for p in cfg.output_pins}
    for tokens in vectors:
        for pin in cfg.output_pins:
            bit, z = token_to_bit(tokens[pin - 1])
            counts[pin][2 if z else bit] += 1
    for pin in cfg.output_pins:
        zeros, ones, zs = counts[pin]
        print(f"  pin {pin:>2}:  L={zeros:>6}  H={ones:>6}  Z={zs:>6}", file=sys.stderr)


if __name__ == "__main__":
    main()
