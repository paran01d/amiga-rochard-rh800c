#!/usr/bin/env python3
"""
check_jed.py -- triage candidate GAL22V10 dumps from a poti/voltage-margining sweep.

A security-fused GAL reads back near-blank; a genuine read has a realistic fuse
density. This scores each candidate so you can spot a real crack instantly
instead of decoding them all by hand.

Usage:
    python3 check_jed.py cand_*.jed
    python3 check_jed.py --ref ../ua4_original.jed cand_*.jed

Reference densities measured on this board (zeros = blown = programmed):
    UA4  (known good)  77.4%
    U11  (known good)  92.0%
    UA3b (read-blocked) 1.1%   <- what a protected read looks like
"""
import os, re, sys, subprocess, itertools, argparse
from pathlib import Path

JEDUTIL = os.environ.get("JEDUTIL", "jedutil")   # MAME jedutil, from PATH or $JEDUTIL
PLAUSIBLE = (55.0, 97.0)   # % zeros for a real GAL22V10 program


def load(path):
    """Return {fuse_addr: '0'|'1'} parsed from either JED line format."""
    fuses = {}
    txt = Path(path).read_text(errors="replace")
    for m in re.finditer(r'\*?L0*(\d+)\s+([01]+)', txt):
        a = int(m.group(1))
        for i, b in enumerate(m.group(2)):
            fuses[a + i] = b
    return fuses


def density(fuses):
    if not fuses:
        return 0.0
    return 100.0 * sum(1 for v in fuses.values() if v == '0') / len(fuses)


def decodes(path):
    """Does jedutil accept it, and does it yield real equations?"""
    if not JEDUTIL.exists():
        return None, "jedutil not found"
    try:
        r = subprocess.run([str(JEDUTIL), "-view", str(path), "gal22v10"],
                           capture_output=True, text=True, timeout=30)
    except Exception as e:
        return False, str(e)
    out = r.stdout
    if "Invalid" in out or "Invalid" in r.stderr or not out.strip():
        return False, "jedutil: invalid"
    n_terms = len(re.findall(r'^\s*[/\w]+\s*=', out, re.M))
    return True, f"jedutil OK, {n_terms} equations"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--ref", help="known-good JED to compare density against")
    args = ap.parse_args()

    if args.ref:
        rf = load(args.ref)
        print(f"reference {args.ref}: {len(rf)} fuses, {density(rf):.1f}% zeros\n")

    results = {}
    print(f"{'file':<34} {'fuses':>6} {'%zeros':>8}  {'verdict':<28} decode")
    print("-" * 100)
    for f in args.files:
        fu = load(f)
        d = density(fu)
        results[f] = fu
        if not fu:
            verdict = "UNPARSEABLE"
        elif d < 10:
            verdict = "BLOCKED (near-blank)"
        elif PLAUSIBLE[0] <= d <= PLAUSIBLE[1]:
            verdict = "*** PLAUSIBLE REAL READ ***"
        else:
            verdict = "suspect density"
        ok, msg = decodes(f)
        print(f"{Path(f).name:<34} {len(fu):>6} {d:>7.1f}%  {verdict:<28} {msg}")

    # cross-compare: identical maps from different settings = strong evidence
    names = [f for f in args.files if results[f]]
    if len(names) > 1:
        print("\ncross-comparison (identical maps from different settings = strong evidence):")
        seen = {}
        for f in names:
            key = tuple(sorted(results[f].items()))
            seen.setdefault(key, []).append(Path(f).name)
        for i, (key, group) in enumerate(seen.items(), 1):
            d = density(dict(key))
            tag = "  <-- repeatable" if len(group) > 1 else ""
            print(f"  group {i}: {d:>5.1f}% zeros  x{len(group)}  {', '.join(group)}{tag}")


if __name__ == "__main__":
    main()
