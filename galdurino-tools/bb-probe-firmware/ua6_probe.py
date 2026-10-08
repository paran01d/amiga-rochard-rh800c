#!/usr/bin/env python3
"""
ua6_probe.py -- UA6 GAL22V10 black-box probe host.

Talks over serial to Galdurino-BB.ino, drives input patterns to the UA6,
reads the output word, and dumps a truth table CSV. Optionally minimises
per-output-bit truth tables into candidate boolean equations using pyeda.

Wiring & bit layouts must match Galdurino-BB.ino.

INPUT pattern is 14 bits, LSB=bit 0:
   0 AB1    4 AB5    8 CFG4M    12 CFGIN
   1 AB2    5 AB6    9 CFG2M    13 RST
   2 AB3    6 STRB  10 BASEA
   3 AB4    7 CFG8M 11 RW

OUTPUT word is 8 bits, LSB=bit 0:
   0 BIN3   4 NC2    6 NC1
   1 BIN2   5 DRVEN  7 ACPHASE
   2 BIN1
   3 BIN0

Usage:
    python3 ua6_probe.py --port /dev/ttyUSB0 --out sweep.csv
    python3 ua6_probe.py --port /dev/ttyUSB0 --mode range --start 0x0 --end 0xff
    python3 ua6_probe.py --port /dev/ttyUSB0 --analyze-only sweep.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

try:
    import serial  # pyserial
except ImportError:
    serial = None

# ---------------------------------------------------------------------------
# Bit-name tables
# ---------------------------------------------------------------------------
INPUT_BITS = [
    "AB1", "AB2", "AB3", "AB4", "AB5", "AB6", "STRB", "CFG8M",
    "CFG4M", "CFG2M", "BASEA", "RW", "CFGIN", "RST",
]
OUTPUT_BITS = [
    "BIN3", "BIN2", "BIN1", "BIN0", "NC2", "DRVEN", "NC1", "ACPHASE",
]
INPUT_WIDTH = len(INPUT_BITS)   # 14
OUTPUT_WIDTH = len(OUTPUT_BITS) # 8
INPUT_MASK = (1 << INPUT_WIDTH) - 1

def input_hex_width() -> int:
    return (INPUT_WIDTH + 3) // 4  # 4

# ---------------------------------------------------------------------------
# Serial link
# ---------------------------------------------------------------------------
@dataclass
class Link:
    ser: "serial.Serial"

    def send(self, line: str) -> None:
        self.ser.write((line + "\n").encode("ascii"))
        self.ser.flush()

    def read_line(self, timeout_s: float = 2.0) -> str:
        deadline = time.monotonic() + timeout_s
        buf = b""
        while time.monotonic() < deadline:
            c = self.ser.read(1)
            if not c:
                continue
            if c in (b"\n", b"\r"):
                if buf:
                    return buf.decode("ascii", errors="replace").rstrip()
                continue
            buf += c
        raise TimeoutError(f"no line within {timeout_s}s")

    def command(self, line: str, expect: Optional[str] = None,
                timeout_s: float = 2.0) -> str:
        self.send(line)
        reply = self.read_line(timeout_s)
        if expect and expect not in reply:
            raise RuntimeError(f"{line!r}: expected {expect!r}, got {reply!r}")
        return reply

    def drain(self) -> None:
        self.ser.reset_input_buffer()


def open_link(port: str, baud: int) -> Link:
    if serial is None:
        sys.exit("pyserial not installed. Try: pip install pyserial")
    s = serial.Serial(port, baudrate=baud, timeout=0.1)
    time.sleep(2.0)  # Uno auto-reset on serial-open; wait for boot banner
    s.reset_input_buffer()
    return Link(s)


# ---------------------------------------------------------------------------
# Firmware interaction
# ---------------------------------------------------------------------------
def init_device(link: Link) -> None:
    link.drain()
    link.command("POWER ON", expect="OK")
    time.sleep(0.02)
    link.command("INIT", expect="OK")

def shutdown_device(link: Link) -> None:
    try:
        link.command("POWER OFF", expect="OK", timeout_s=1.0)
    except Exception:
        pass


SWEEP_ROW = re.compile(r"^([0-9A-Fa-f]+),([0-9A-Fa-f]+)$")

def sweep(link: Link, start: int, end: int, step: int) -> Iterable[tuple[int, int]]:
    """Fire a SWEEP command and yield (input, output) pairs as they stream."""
    cmd = f"SWEEP {start:X} {end:X} {step:X}"
    link.send(cmd)
    # Wait for BEGIN
    while True:
        line = link.read_line(timeout_s=5.0)
        if line.startswith("BEGIN"):
            break
    while True:
        line = link.read_line(timeout_s=5.0)
        if line.strip() == "END":
            return
        m = SWEEP_ROW.match(line.strip())
        if m:
            yield int(m.group(1), 16), int(m.group(2), 16)


# ---------------------------------------------------------------------------
# Pattern generators
# ---------------------------------------------------------------------------
def gen_full() -> tuple[int, int, int]:
    return 0x0000, INPUT_MASK, 1

def gen_range(start: int, end: int, step: int) -> tuple[int, int, int]:
    return start & INPUT_MASK, end & INPUT_MASK, max(1, step)


# ---------------------------------------------------------------------------
# CSV write + read
# ---------------------------------------------------------------------------
def write_csv(path: Path, rows: Iterable[tuple[int, int]]) -> int:
    n = 0
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["input_hex", "output_hex",
                    *[f"in_{name}" for name in INPUT_BITS],
                    *[f"out_{name}" for name in OUTPUT_BITS]])
        for ip, op in rows:
            in_bits = [(ip >> i) & 1 for i in range(INPUT_WIDTH)]
            out_bits = [(op >> i) & 1 for i in range(OUTPUT_WIDTH)]
            w.writerow([f"{ip:0{input_hex_width()}X}", f"{op:02X}",
                        *in_bits, *out_bits])
            n += 1
    return n

def read_csv(path: Path) -> list[tuple[int, int]]:
    rows = []
    with path.open() as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append((int(row["input_hex"], 16), int(row["output_hex"], 16)))
    return rows


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
def summarise(rows: list[tuple[int, int]]) -> None:
    print()
    print(f"=== Summary of {len(rows)} samples ===")
    if not rows:
        return
    # Per-output-bit statistics
    per_bit_counts = [[0, 0] for _ in range(OUTPUT_WIDTH)]
    for _, op in rows:
        for b in range(OUTPUT_WIDTH):
            per_bit_counts[b][(op >> b) & 1] += 1
    print(f"{'bit':>3}  {'name':<8}  {'0 count':>8}  {'1 count':>8}  observation")
    for b, name in enumerate(OUTPUT_BITS):
        zeros, ones = per_bit_counts[b]
        if zeros == 0:
            note = "constant HIGH"
        elif ones == 0:
            note = "constant LOW"
        else:
            note = "varies"
        print(f"{b:>3}  {name:<8}  {zeros:>8}  {ones:>8}  {note}")


def maybe_minimise(rows: list[tuple[int, int]]) -> None:
    try:
        from pyeda.inter import exprvars, truthtable, espresso_tts  # noqa: F401
    except ImportError:
        print()
        print("pyeda not installed - skipping equation minimisation.")
        print("Install with:  pip install pyeda")
        return
    from pyeda.inter import exprvars, truthtable, espresso_tts
    if not rows:
        print("no rows - nothing to minimise")
        return
    total_needed = 1 << INPUT_WIDTH
    seen = {ip: op for ip, op in rows}
    if len(seen) < total_needed:
        print()
        print(f"skip minimisation: have {len(seen)}/{total_needed} patterns, "
              f"pyeda needs an exhaustive truth table. Rerun with --mode full.")
        return
    xs = exprvars("x", INPUT_WIDTH)
    print()
    print("=== Minimised equations (Espresso) ===")
    for bit in range(OUTPUT_WIDTH):
        outs = [(seen[ip] >> bit) & 1 for ip in range(total_needed)]
        # Skip constants
        if all(v == outs[0] for v in outs):
            print(f"  {OUTPUT_BITS[bit]:<8} = {outs[0]}  (constant)")
            continue
        try:
            tt = truthtable(xs, outs)
            (min_expr,) = espresso_tts(tt)
            expr_str = str(min_expr).replace("Or", "OR").replace("And", "AND")
            print(f"  {OUTPUT_BITS[bit]:<8} = {expr_str}")
        except Exception as e:
            print(f"  {OUTPUT_BITS[bit]:<8} = <minimise failed: {e}>")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def hex_or_int(s: str) -> int:
    return int(s, 0)

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default=os.environ.get("GALDURINO_PORT", "/dev/ttyUSB0"),
                    help="serial device (env: GALDURINO_PORT, default /dev/ttyUSB0)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--out", default="ua6_sweep.csv", help="CSV output path")
    ap.add_argument("--mode", choices=("full", "range"), default="full",
                    help="full = exhaustive 14-bit sweep; range = pick your own")
    ap.add_argument("--start", type=hex_or_int, default=0)
    ap.add_argument("--end",   type=hex_or_int, default=INPUT_MASK)
    ap.add_argument("--step",  type=hex_or_int, default=1)
    ap.add_argument("--no-analyze", action="store_true",
                    help="skip post-sweep summary + minimisation")
    ap.add_argument("--analyze-only", metavar="CSV",
                    help="skip probe; load CSV and just do analysis")
    args = ap.parse_args()

    if args.analyze_only:
        rows = read_csv(Path(args.analyze_only))
        summarise(rows)
        maybe_minimise(rows)
        return

    if args.mode == "full":
        start, end, step = gen_full()
    else:
        start, end, step = gen_range(args.start, args.end, args.step)

    link = open_link(args.port, args.baud)
    try:
        # eat any boot banner
        drain_until = time.monotonic() + 0.5
        while time.monotonic() < drain_until:
            try:
                banner = link.read_line(timeout_s=0.2)
                print(f"[dev] {banner}")
            except TimeoutError:
                break

        print(f"initialising device on {args.port}...")
        init_device(link)
        expected = (end - start) // step + 1
        print(f"sweeping {expected:,} patterns from {start:0{input_hex_width()}X} "
              f"to {end:0{input_hex_width()}X} step {step:X}")
        started = time.monotonic()
        out_path = Path(args.out)
        rows: list[tuple[int, int]] = []
        # Stream through firmware SWEEP command
        with out_path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["input_hex", "output_hex"])
            n = 0
            for ip, op in sweep(link, start, end, step):
                w.writerow([f"{ip:0{input_hex_width()}X}", f"{op:02X}"])
                rows.append((ip, op))
                n += 1
                if n % 1024 == 0:
                    elapsed = time.monotonic() - started
                    rate = n / max(elapsed, 1e-6)
                    print(f"  {n:>6} rows  ({rate:.0f} /s)")
        elapsed = time.monotonic() - started
        print(f"wrote {out_path} ({len(rows)} rows in {elapsed:.1f}s)")
    finally:
        shutdown_device(link)

    if not args.no_analyze:
        summarise(rows)
        maybe_minimise(rows)


if __name__ == "__main__":
    main()
