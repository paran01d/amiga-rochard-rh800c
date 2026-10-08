#!/usr/bin/env python3
"""
gen_vectors.py -- Emit a logicic.xml compatible with minipro --logicic.

For a chip config (see gal_configs.py), sweep the driven-input space, writing
one test vector per pattern. Output pins get 'Z' as a placeholder -- minipro
--logic_test --logicic_out overwrites those with the observed L / H / Z states.

Usage:
    python3 gen_vectors.py UA6                       # full 2^N sweep
    python3 gen_vectors.py U11 --sample 512          # 512 random patterns
    python3 gen_vectors.py UA4 --start 0 --end 0xff  # range slice
    python3 gen_vectors.py UA6 -o ua6_vectors.xml    # explicit output path
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gal_configs


def build_vector(cfg: gal_configs.GALConfig, pattern: int) -> str:
    """Return a space-separated 24-char string encoding one vector."""
    tokens: list[str] = []
    for pin in range(1, cfg.pins + 1):
        if pin == cfg.vcc_pin:
            tokens.append("V")
        elif pin == cfg.gnd_pin:
            tokens.append("G")
        elif pin in cfg.input_pins:
            idx = cfg.input_pins.index(pin)
            tokens.append("1" if (pattern >> idx) & 1 else "0")
        elif pin in cfg.output_pins:
            tokens.append("Z")
        else:
            tokens.append("X")
    return " ".join(tokens)


def generate_patterns(cfg: gal_configs.GALConfig, args: argparse.Namespace) -> list[int]:
    total = 1 << len(cfg.input_pins)
    if args.sample is not None:
        rng = random.Random(args.seed)
        return sorted(rng.sample(range(total), min(args.sample, total)))
    start = args.start if args.start is not None else 0
    end   = args.end if args.end is not None else total - 1
    step  = args.step
    if end >= total:
        end = total - 1
    if start > end:
        start, end = end, start
    return list(range(start, end + 1, step))


def emit_xml(cfg: gal_configs.GALConfig, patterns: list[int], path: Path) -> None:
    with path.open("w") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write('<logicic>\n')
        f.write('  <database type="LOGIC">\n')
        f.write('    <manufacturer name="galdumper">\n')
        f.write(f'      <ic name="{cfg.name}" type="5" '
                f'voltage="{cfg.voltage}" pins="{cfg.pins}">\n')
        for i, pattern in enumerate(patterns):
            f.write(f'        <vector id="{i}"> {build_vector(cfg, pattern)} </vector>\n')
        f.write('      </ic>\n')
        f.write('    </manufacturer>\n')
        f.write('  </database>\n')
        f.write('</logicic>\n')


def hex_or_int(s: str) -> int:
    return int(s, 0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chip", help="chip name (UA6, U11, UA4)")
    ap.add_argument("-o", "--output", help="XML output path (default: <chip>_vectors.xml)")
    ap.add_argument("--sample", type=int, help="pick N random patterns instead of a full sweep")
    ap.add_argument("--seed", type=int, default=1, help="random seed (default: 1)")
    ap.add_argument("--start", type=hex_or_int, help="range start (default: 0)")
    ap.add_argument("--end",   type=hex_or_int, help="range end inclusive (default: 2^N - 1)")
    ap.add_argument("--step",  type=hex_or_int, default=1, help="range step (default: 1)")
    args = ap.parse_args()

    cfg = gal_configs.get(args.chip)
    out_path = Path(args.output or f"{cfg.name.lower()}_vectors.xml")

    patterns = generate_patterns(cfg, args)
    total = 1 << len(cfg.input_pins)
    if not patterns:
        raise SystemExit("no patterns to emit")

    print(f"chip = {cfg.name}  pins={cfg.pins}  "
          f"inputs={len(cfg.input_pins)}  outputs={len(cfg.output_pins)}", file=sys.stderr)
    print(f"input space = {total:,}  emitting = {len(patterns):,}", file=sys.stderr)
    print(f"input pins  = {cfg.input_pins}", file=sys.stderr)
    print(f"output pins = {cfg.output_pins}", file=sys.stderr)

    emit_xml(cfg, patterns, out_path)
    print(f"wrote {out_path} ({out_path.stat().st_size:,} bytes)", file=sys.stderr)


if __name__ == "__main__":
    main()
