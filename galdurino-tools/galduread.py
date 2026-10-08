#!/usr/bin/env python3
"""
galduread.py - drive Galdurino directly from Python, no Java required.

Talks to the Arduino at 9600 8N1 over the serial protocol implemented in
Galdurino.ino. Reads a GAL (16V8, 20V8, 22V10) at a chosen poti value and
saves the raw fuse-map dump to a file.

Usage:
    ./galduread.py --port /dev/ttyACM0 --type 22V10 --poti 180 --out chip.dump
    ./galduread.py --port /dev/ttyACM0 --type 22V10 --sweep    # try poti sweep

Wire protocol (see Galdurino.ino):
    commands (case-insensitive, \\r terminated):
        STATUS
        IDENTIFY
        SETPOTI n           # 0..255
        16V8READ / 20V8READ / 22V10READ
    responses:
        text lines separated by \\r\\n
        a 22V10READ block ends with a line "END"
        an IDENTIFY block ends with a line "ID end"
"""

import argparse
import serial
import sys
import time


def send(ser, cmd):
    ser.write((cmd + "\n").encode())
    ser.flush()


def read_until(ser, sentinel, timeout=15):
    """Collect lines from serial until `sentinel` matches. `sentinel` may be
    a string (exact-line match after strip) or a callable (predicate on stripped
    line text). Prior versions did substring matching, which broke on lines
    containing the sentinel as a substring (e.g. `END` in `VENDOR:`)."""
    match = sentinel if callable(sentinel) else (lambda t: t == sentinel)
    end = time.time() + timeout
    lines = []
    buf = b""
    while time.time() < end:
        chunk = ser.read(256)
        if chunk:
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.decode(errors="replace").rstrip("\r")
                lines.append(text)
                if match(text.strip()):
                    return lines
    label = sentinel.__name__ if callable(sentinel) else repr(sentinel)
    raise TimeoutError(f"timed out waiting for {label} after {timeout}s. Got {len(lines)} lines.")


def open_port(port):
    return serial.Serial(port, 9600, timeout=0.2)


def wake(ser):
    """Give the Arduino a moment after DTR-reset on port open."""
    time.sleep(2.0)
    ser.reset_input_buffer()


def _starts_with(prefix):
    def _pred(t):
        return t.startswith(prefix)
    _pred.__name__ = f"startswith({prefix!r})"
    return _pred


def cmd_status(ser):
    ser.reset_input_buffer()
    send(ser, "STATUS")
    return read_until(ser, _starts_with("VPP-voltage:"), timeout=5)


def cmd_identify(ser, poti=180):
    """IDENTIFY takes a poti value as its argument; the firmware uses that
    to set VPP for the PES read. Without an argument the string parses to 0
    (VPP = 6.4V) and identification always returns FF/FF."""
    ser.reset_input_buffer()
    send(ser, f"IDENTIFY {poti}")
    return read_until(ser, "ID end", timeout=8)


def cmd_setdelays(ser, d0, d1, d2, d3):
    """Set the four timing delays used by the read routines. Values are ints.
    d3 can be -1 to skip the VPP-off/on pulse trick in the read crack."""
    ser.reset_input_buffer()
    send(ser, f"SETDELAYS {d0} {d1} {d2} {d3}")
    time.sleep(0.4)  # firmware prints ack + reads back current state
    ser.reset_input_buffer()


def cmd_read(ser, gal_type, poti):
    ser.reset_input_buffer()
    read_cmd = {"16V8": "16V8READ", "20V8": "20V8READ", "22V10": "22V10READ"}[gal_type]
    send(ser, f"{read_cmd} {poti}")
    return read_until(ser, "END", timeout=30)


def cmd_discharge(ser, low_poti=0, settle_ms=3000, post_ms=500):
    """Mimic the SWEEP command's preamble: set poti low, briefly turn VPP on
    to let the DC-DC start delivering the (low) voltage, then turn VPP off
    for post_ms to let C8 discharge fully. This aims to give a repeatable
    'cold-start' state before each attempt, matching the crack protocol some
    Lattice parts respond to."""
    ser.reset_input_buffer()
    send(ser, f"SETPOTI {low_poti}")
    time.sleep(0.15)
    ser.reset_input_buffer()
    send(ser, "VPP ON")
    time.sleep(settle_ms / 1000.0)
    ser.reset_input_buffer()
    send(ser, "VPP OFF")
    time.sleep(post_ms / 1000.0)
    ser.reset_input_buffer()


def cmd_measure_vpp(ser, poti):
    """Set the digital pot to `poti`, turn VPP on, read the actual voltage, then
    turn VPP off. Returns the voltage as a float, or None if unparseable.
    Used to confirm the DC-DC is delivering the expected voltage per poti step."""
    import re
    ser.reset_input_buffer()
    send(ser, f"SETPOTI {poti}")
    time.sleep(0.2)
    ser.reset_input_buffer()
    send(ser, "VPP ON")
    time.sleep(0.3)  # let boost settle
    ser.reset_input_buffer()
    send(ser, "STATUS")
    try:
        lines = read_until(ser, _starts_with("VPP-voltage:"), timeout=5)
    except TimeoutError:
        send(ser, "VPP OFF")
        return None
    send(ser, "VPP OFF")
    time.sleep(0.1)
    for line in lines:
        m = re.search(r"VPP-voltage:\s*(-?\d+(?:\.\d+)?)", line)
        if m:
            return float(m.group(1))
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", default="/dev/ttyACM0")
    p.add_argument("--type", required=True, choices=["16V8", "20V8", "22V10"])
    p.add_argument("--poti", type=int, default=180,
                   help="single poti value to try (default: 180)")
    p.add_argument("--sweep", action="store_true",
                   help="try multiple poti values around the sweet spots")
    p.add_argument("--wide-sweep", action="store_true",
                   help="expanded poti sweep 100..250, 10-step increments")
    p.add_argument("--fine-sweep", action="store_true",
                   help="fine poti sweep 1-step around readme's sweet spots 130/180/220")
    p.add_argument("--sweep-range", default=None, metavar="LO HI STEP",
                   help='custom sweep, e.g. --sweep-range "125 135 1"')
    p.add_argument("--attempts", type=int, default=1,
                   help="attempts per poti value (readme suggests some GALs need multiple)")
    p.add_argument("--delays", default=None, metavar="D0 D1 D2 D3",
                   help='override read timing (e.g. --delays "10 0 100 -1" to skip '
                        'the VPP off/on pulse). Persisted in Arduino EEPROM until reset.')
    p.add_argument("--discharge", action="store_true",
                   help='before each read, apply the SWEEP-style discharge preamble '
                        '(poti=0, VPP on 3s, VPP off 500ms) to give a repeatable cold-start.')
    p.add_argument("--out", default=None,
                   help="write raw dump to this file (per-poti .N suffix if sweeping)")
    args = p.parse_args()

    ser = open_port(args.port)
    print(f"[+] opened {args.port}", flush=True)
    wake(ser)

    if args.delays:
        try:
            d0, d1, d2, d3 = (int(x) for x in args.delays.split())
        except ValueError:
            sys.exit("--delays must be four whitespace-separated integers")
        print(f"[+] SETDELAYS {d0} {d1} {d2} {d3}", flush=True)
        cmd_setdelays(ser, d0, d1, d2, d3)

    print("[+] STATUS:", flush=True)
    for line in cmd_status(ser):
        print(f"    {line}", flush=True)

    # Skipping standalone IDENTIFY: the firmware's readType() calls readPES()
    # (16V8/20V8 layout) for ALL chip types, so it returns garbage on 22V10.
    # The chip-specific 22V10READ / 20V8READ / 16V8READ commands do their own
    # correct-family PES read as part of the fuse-map dump, which is what we
    # actually care about.

    if args.sweep_range:
        try:
            lo, hi, step = (int(x) for x in args.sweep_range.split())
        except ValueError:
            sys.exit('--sweep-range must be three ints, e.g. "125 135 1"')
        poti_values = list(range(lo, hi + 1, step))
    elif args.fine_sweep:
        poti_values = sorted(set(
            list(range(125, 136))       # ~9V READ trigger neighborhood
            + list(range(175, 186))     # ~12V READ nominal neighborhood
            + list(range(215, 226))     # ~15V WRITE trigger neighborhood
        ))
    elif args.wide_sweep:
        poti_values = list(range(100, 260, 10))
    elif args.sweep:
        poti_values = [130, 170, 180, 190, 200, 220, 230]
    else:
        poti_values = [args.poti]

    # Cache measured VPP per poti so we don't re-measure on every attempt.
    vpp_cache = {}

    for poti in poti_values:
        if poti not in vpp_cache:
            vpp_cache[poti] = cmd_measure_vpp(ser, poti)
        vpp = vpp_cache[poti]
        vpp_str = f"{vpp:.1f}V" if vpp is not None else "?V"

        for attempt in range(1, args.attempts + 1):
            label = f"poti={poti} (VPP={vpp_str})" + (f" attempt {attempt}/{args.attempts}" if args.attempts > 1 else "")
            print(f"\n[+] {args.type} read at {label}", flush=True)
            if args.discharge:
                cmd_discharge(ser)
            try:
                dump = cmd_read(ser, args.type, poti)
            except TimeoutError as e:
                print(f"    TIMEOUT: {e}", flush=True)
                continue

            # Only count characters in lines that actually look like fuse data,
            # i.e. long lines of 0s and 1s (skip the section labels like FUSEMAP:).
            fuse_lines = [l for l in dump if len(l) >= 20 and set(l) <= set("01")]
            zeros = sum(l.count("0") for l in fuse_lines)
            ones = sum(l.count("1") for l in fuse_lines)
            print(f"    got {len(dump)} lines ({len(fuse_lines)} look like fuses). "
                  f"chars: {zeros} zeros, {ones} ones", flush=True)

            if args.out:
                sweeping = args.sweep or args.wide_sweep
                suffix = f"{poti}" + (f".a{attempt}" if args.attempts > 1 else "")
                path = f"{args.out}.{suffix}" if (sweeping or args.attempts > 1) else args.out
                with open(path, "w") as f:
                    for line in dump:
                        f.write(line + "\n")
                print(f"    saved -> {path}", flush=True)

    ser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
