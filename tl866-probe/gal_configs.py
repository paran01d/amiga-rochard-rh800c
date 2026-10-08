"""
GAL chip configurations for the minipro logic-test pipeline.

Each entry describes: DIP package pin count, which pin is VCC, which is GND,
which pins are driven inputs (0/1 in the vector), and which pins are observed
outputs (Z placeholder in the vector, minipro replaces with L / H / Z).

Everything else on the pin list becomes 'X' (don't care / unconnected) in the
generated vectors.
"""

from dataclasses import dataclass
from typing import List

@dataclass
class GALConfig:
    name: str                  # short name; appears in the generated XML
    pins: int                  # DIP package pin count
    vcc_pin: int               # physical pin carrying +5V (marked V in vectors)
    gnd_pin: int               # physical pin carrying GND (marked G in vectors)
    input_pins: List[int]      # driven inputs (0 or 1 in vectors)
    output_pins: List[int]     # observed outputs (Z placeholder in vectors)
    voltage: str = "5V"

    def all_signal_pins(self) -> List[int]:
        return sorted(self.input_pins + self.output_pins)


# ---------------------------------------------------------------------------
# UA6 -- target we're trying to reverse-engineer.
# Pin functions come from the schematic reverse-engineering effort and the
# do-nothing Draft 11 .pld:
#   pin 1..11  = AB1..AB6, STRB, CFG8M, CFG4M, CFG2M, BASEA   (11 inputs)
#   pin 13     = R/W
#   pin 14     = CFGIN
#   pin 17     = /RST
#   pin 15,16,18-23 = outputs
UA6 = GALConfig(
    name="UA6_SWEEP",
    pins=24,
    vcc_pin=24,
    gnd_pin=12,
    input_pins=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 17],
    output_pins=[15, 16, 18, 19, 20, 21, 22, 23],
)


# ---------------------------------------------------------------------------
# U11 -- already cracked GAL22V10; used as a validation reference.
# From u11_equations.txt: outputs are 16, 18, 20, 21, 22; all other pins
# (except VCC/GND) are used as inputs by the fused logic.
U11 = GALConfig(
    name="U11_VALIDATE",
    pins=24,
    vcc_pin=24,
    gnd_pin=12,
    input_pins=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 17, 19, 23],
    output_pins=[16, 18, 20, 21, 22],
)


# ---------------------------------------------------------------------------
# UA4 -- already cracked GAL22V10; second validation reference.
# From ua4_equations.txt: outputs 16, 17, 18, 19, 21, 22, 23; inputs cover
# 1-11, 13, 14, 15, 20.
UA4 = GALConfig(
    name="UA4_VALIDATE",
    pins=24,
    vcc_pin=24,
    gnd_pin=12,
    input_pins=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 20],
    output_pins=[16, 17, 18, 19, 21, 22, 23],
)


# ---------------------------------------------------------------------------
# U11X -- CORRECTED U11 sweep to capture the two unread outputs.
# The original U11 config (above) wrongly drove pins 15, 17, 19 as INPUTS,
# but all three are U11 OUTPUTS: 15=_LDS(O1), 17=/_UA3SEL(O3), 19=/_LATCH_EN(O5).
# Driving them fought the chip. Here they are OUTPUTS so we MEASURE them.
# Goal: recover /_UA3SEL (o17) and /_LATCH_EN (o19) as functions of the real
# inputs incl pin5 /_AC_PHASE -> derive the AC_PHASE requirement for UA6.
# Fuse-read protection does NOT block operation, so this logic sweep works.
# Inputs (14): 1 /_LATCH_CLK, 2 /BASE_A, 3 /BASE_B, 4 R_W, 5 /_AC_PHASE,
#   6-11 /AB6../AB1, 13 _RST(OE), 14 _UDS, 23 /_E8WIN.
U11X = GALConfig(
    name="U11X_OUTS",
    pins=24,
    vcc_pin=24,
    gnd_pin=12,
    input_pins=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 23],
    output_pins=[15, 16, 17, 18, 19, 20, 21, 22],
)


U11O17 = GALConfig(
    name="U11O17_ONLY",
    pins=24, vcc_pin=24, gnd_pin=12,
    input_pins=[1,2,3,4,5,6,7,8,9,10,11,13,14,15,18,19,23],
    output_pins=[17],
)


# ---------------------------------------------------------------------------
# U14 -- GAL16V8, fuse-read PROTECTED. Validated functionally against
# u14_equations.txt. Inputs 1-9 + 11 (CLK1 LDS UDS AB13 AB14 CFGAM AS LATCH
# R_W AB15); outputs 12-19 (13-18 have feedback, 14-18 latch on /i8).
# Key check: o15 = /_ROMOE must go LOW on a config match (/i6 & /i7 & /i11).
# A known rogue clone had it INVERTED.
U14 = GALConfig(
    name="U14_VALIDATE",
    pins=20,
    vcc_pin=20,
    gnd_pin=10,
    input_pins=[1, 2, 3, 4, 5, 6, 7, 8, 9, 11],
    output_pins=[12, 13, 14, 15, 16, 17, 18, 19],
)


BY_SHORT_NAME = {
    "ua6": UA6,
    "u11": U11,
    "u11x": U11X,
    "u11o17": U11O17,
    "ua4": UA4,
    "u14": U14,
}


def get(name: str) -> GALConfig:
    key = name.lower()
    if key not in BY_SHORT_NAME:
        raise SystemExit(f"unknown chip {name!r}. Options: {', '.join(BY_SHORT_NAME)}")
    return BY_SHORT_NAME[key]


# ---------------------------------------------------------------------------
# UA3b -- the RAM decode GAL on the UA3 daughterboard (GAL22V10B).
# Board pinout (from kicad-cli netlist, 2026-08-09):
#   1=/AB17  2=/AB18  3=/AB19  4=/AB20  5=/AB22  6=/AB23
#   7=_CCK   8=_CCKQ  9=_CDAC  10=/GALCLK1  11=GND  12=GND  13=/AB21
#   14=/_UA3SEL (the signal that gates DTACK via U11 pin 17)
#   15..22=/UA3B1../UA3B8 (-> UA3a 74LS244 -> _RAMRAS/_RAMCAS0-3/SIMMA8-9)
#   23=NC (socket only)  24=+5V
# NOTE: on a GAL22V10, PIN 1 IS THE DEDICATED CLOCK for registered macrocells,
# and here pin 1 carries /AB17. Any registered output is therefore clocked by
# address bit 17. Pin 1 is bit 0 of the sweep pattern, so it toggles on every
# vector -- that deliberately generates clock edges to exercise registers.
# Pin 11 is GND on the board; it is swept here as a normal input, so filter
# results to pin11=0 when comparing against in-circuit behaviour.
UA3B = GALConfig(
    name="UA3B_SWEEP",
    pins=24,
    vcc_pin=24,
    gnd_pin=12,
    input_pins=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13],
    output_pins=[14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
)

BY_SHORT_NAME["ua3b"] = UA3B
