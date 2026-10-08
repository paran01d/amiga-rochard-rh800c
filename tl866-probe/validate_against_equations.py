#!/usr/bin/env python3
"""
validate_against_equations.py -- compare a measured CSV against a known-good
GALasm-style equations file, per output pin, per input pattern.

Handles:
  * sum-of-products main equations:  o16 = i1 & /i2 + i3
  * inverted LHS:                    /o19 = ...
  * output-enable:                   o16.oe = /i14   (or "vcc")
  * self-feedback in the RHS (o16 = ... + i8 & /o16 -- latch): the measured
    state must be a stable fixed point of the equation.

Skips registered outputs (rfN := ...) -- those need a clock we don't drive.

Usage:
    python3 validate_against_equations.py \
        --equations ../u11_equations.txt \
        --measured u11_measured.csv \
        --chip U11
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
import gal_configs


# ----- RHS parser --------------------------------------------------------
@dataclass
class Clause:
    """One AND term: list of (var_name, is_negated) literals."""
    literals: list[tuple[str, bool]] = field(default_factory=list)

    def eval(self, env: dict[str, int]) -> int:
        for name, neg in self.literals:
            v = env.get(name)
            if v is None:
                # undefined variable -- treat as "don't know"; return 0 so this
                # AND term doesn't contribute a spurious 1
                return 0
            if neg:
                v ^= 1
            if not v:
                return 0
        return 1


@dataclass
class Sop:
    """Sum-of-products: OR over Clauses."""
    clauses: list[Clause] = field(default_factory=list)
    always_true: bool = False

    def eval(self, env: dict[str, int]) -> int:
        if self.always_true:
            return 1
        for c in self.clauses:
            if c.eval(env):
                return 1
        return 0

    def variables(self) -> set[str]:
        vs = set()
        for c in self.clauses:
            for name, _ in c.literals:
                vs.add(name)
        return vs


def parse_sop(rhs: str) -> Sop:
    """Turn a GALasm-style RHS into an Sop."""
    rhs = re.sub(r"\s+", " ", rhs.strip())
    if rhs.upper() == "VCC":
        return Sop(always_true=True)
    if rhs.upper() == "GND" or rhs == "":
        return Sop()
    sop = Sop()
    for or_term in rhs.split("+"):
        clause = Clause()
        for lit in or_term.split("&"):
            lit = lit.strip()
            if not lit:
                continue
            neg = lit.startswith("/")
            if neg:
                lit = lit[1:]
            clause.literals.append((lit, neg))
        if clause.literals:
            sop.clauses.append(clause)
    return sop


# ----- equations file parser --------------------------------------------
@dataclass
class OutputEqn:
    name: str                 # e.g. "o16"
    value_sop: Sop
    value_inverted: bool      # True if LHS was "/o16"
    oe_sop: Sop = field(default_factory=lambda: Sop(always_true=True))
    registered: bool = False


LHS_RE = re.compile(r"^\s*(/?)([oOrR][fF]?\d+)(\.\w+)?\s*(:?=)\s*(.*)$")


def parse_equations_file(text: str) -> dict[str, OutputEqn]:
    """Return {output_name: OutputEqn} keyed on 'oN' (no leading slash)."""
    start = text.find("Equations:")
    if start < 0:
        raise SystemExit("no 'Equations:' section found")
    body = text[start + len("Equations:") :]

    # Group physical lines into logical statements. A new statement begins
    # on any line whose LHS matches LHS_RE; continuation lines are appended.
    statements: list[str] = []
    current: list[str] = []
    for raw in body.splitlines():
        if LHS_RE.match(raw):
            if current:
                statements.append(" ".join(current))
            current = [raw]
        elif raw.strip():
            current.append(raw)
    if current:
        statements.append(" ".join(current))

    equations: dict[str, OutputEqn] = {}
    for stmt in statements:
        m = LHS_RE.match(stmt)
        if not m:
            continue
        neg, name, prop, assign, rhs = m.groups()
        base = name.lower()  # oN, rfN
        if not (base.startswith("o") or base.startswith("rf")):
            continue
        target_key = base
        registered = base.startswith("rf") or assign == ":="
        sop = parse_sop(rhs)

        # Track keyed by their DIP pin number: turn oN or rfN into the
        # canonical "oN" form for lookups.
        if base.startswith("rf"):
            target_key = "o" + base[2:]

        entry = equations.get(target_key)
        if entry is None:
            entry = OutputEqn(name=target_key, value_sop=Sop(), value_inverted=False)
            equations[target_key] = entry
        entry.registered = entry.registered or registered

        if prop is None:
            # main value equation
            entry.value_sop = sop
            entry.value_inverted = bool(neg)
        elif prop.strip() == ".oe":
            entry.oe_sop = sop
        elif prop.strip() in (".T", ".E", ".ap", ".ar", ".ck"):
            # tri-state / async preset+reset / clock -- ignore for pure combi
            pass

    return equations


# ----- expected-output evaluation ---------------------------------------
def expected_value(eqn: OutputEqn, env: dict[str, int]) -> Optional[int]:
    """
    Return the expected value for eqn given the input env.
    If the RHS has self-feedback (references eqn.name), tries both stable
    assumptions; if both are stable returns None (hysteresis).
    """
    self_key = eqn.name
    refs = eqn.value_sop.variables() | eqn.oe_sop.variables()
    has_self = self_key in refs

    def eval_one(assumed_self: Optional[int]) -> Optional[int]:
        local = dict(env)
        if assumed_self is not None:
            local[self_key] = assumed_self
        oe = eqn.oe_sop.eval(local)
        if not oe:
            return None   # Hi-Z
        raw = eqn.value_sop.eval(local)
        if eqn.value_inverted:
            raw ^= 1
        return raw

    if not has_self:
        return eval_one(None)

    v0 = eval_one(0)
    v1 = eval_one(1)
    stable_at_0 = (v0 == 0)
    stable_at_1 = (v1 == 1)
    if stable_at_0 and not stable_at_1:
        return 0
    if stable_at_1 and not stable_at_0:
        return 1
    if stable_at_0 and stable_at_1:
        return None    # hysteresis: depends on prior state
    # neither stable -- oscillator; can't predict
    return None


# ----- main comparison --------------------------------------------------
def build_env(cfg: gal_configs.GALConfig, row: dict[str, str]) -> dict[str, int]:
    env: dict[str, int] = {}
    for pin in cfg.input_pins:
        env[f"i{pin}"] = int(row[f"in_{pin}"])
    for pin in cfg.output_pins:
        env[f"o{pin}"] = int(row[f"out_{pin}"])
        # Latches read their own past state through the "o<n>" name
    return env


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--equations", required=True, help="path to *_equations.txt")
    ap.add_argument("--measured", required=True, help="CSV from parse_measured.py")
    ap.add_argument("--chip", required=True, help="chip name (must match CSV)")
    ap.add_argument("--report", help="write full per-row mismatch CSV to this path")
    ap.add_argument("--limit", type=int, help="stop after N rows (debugging)")
    args = ap.parse_args()

    cfg = gal_configs.get(args.chip)
    eqns = parse_equations_file(Path(args.equations).read_text())

    # Restrict to outputs the config actually observes
    active = {}
    for pin in cfg.output_pins:
        name = f"o{pin}"
        e = eqns.get(name)
        if e is None:
            print(f"warning: no equation for {name} -- skipping", file=sys.stderr)
            continue
        if e.registered:
            print(f"info: {name} is registered -- skipping (needs clocked flow)",
                  file=sys.stderr)
            continue
        active[pin] = e

    print(f"validating {len(active)} outputs: "
          f"{sorted(active)}", file=sys.stderr)

    totals = {pin: {"match": 0, "mismatch": 0, "hi_z_meas": 0,
                    "hi_z_expected": 0, "hysteresis": 0}
              for pin in active}

    with open(args.measured) as f:
        reader = csv.DictReader(f)
        report_fp = None
        report_writer = None
        if args.report:
            report_fp = open(args.report, "w", newline="")
            report_writer = csv.writer(report_fp)
            report_writer.writerow(
                ["input_hex", "pin", "expected", "measured", "meas_z", "verdict"])

        for i, row in enumerate(reader):
            if args.limit is not None and i >= args.limit:
                break
            env = build_env(cfg, row)
            for pin, eqn in active.items():
                measured = int(row[f"out_{pin}"])
                meas_z = int(row[f"z_{pin}"])
                exp = expected_value(eqn, env)
                if exp is None:
                    verdict = "hysteresis" if not meas_z else "hi_z_expected"
                    totals[pin]["hysteresis" if not meas_z else "hi_z_expected"] += 1
                elif meas_z:
                    verdict = "meas_z"
                    totals[pin]["hi_z_meas"] += 1
                elif exp == measured:
                    verdict = "match"
                    totals[pin]["match"] += 1
                else:
                    verdict = "mismatch"
                    totals[pin]["mismatch"] += 1
                if report_writer and verdict in ("mismatch",):
                    report_writer.writerow(
                        [row["input_hex"], pin, exp, measured, meas_z, verdict])
        if report_fp:
            report_fp.close()

    print()
    print(f"{'pin':>4}  {'match':>7}  {'mismatch':>9}  {'meas_Z':>7}  "
          f"{'exp_Z':>7}  {'hyster':>7}")
    ok = True
    for pin in sorted(active):
        t = totals[pin]
        marker = "" if t["mismatch"] == 0 else "  <-- FAIL"
        if t["mismatch"]:
            ok = False
        print(f"{pin:>4}  {t['match']:>7}  {t['mismatch']:>9}  "
              f"{t['hi_z_meas']:>7}  {t['hi_z_expected']:>7}  "
              f"{t['hysteresis']:>7}{marker}")

    print()
    if ok:
        print("VALIDATION OK -- every predictable output matches measured.")
    else:
        print("VALIDATION FAILED -- see --report for per-mismatch details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
