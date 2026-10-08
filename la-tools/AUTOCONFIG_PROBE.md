# RocHard RH800C — autoconfig probe setup

> **Historical document.** This is the logic-analyser plan we wrote *before* the
> first autoconfig capture. Several of its premises were later superseded: the
> er_Type values below omit the CHAINEDCONFIG bit, the "RAM is mounted at
> $200000 with no autoconfig" idea was wrong (the RAM is announced as a second
> autoconfig board), and the U17 "wired-AND" model was never confirmed. For the
> working design see [`../gal/ua6/ua6_ram6.pld`](../gal/ua6/ua6_ram6.pld) and
> [`../docs/autoconfig.md`](../docs/autoconfig.md). The probe map itself is still useful.

Goal: capture the **autoconfig enumeration** at the card's config space so we can see exactly how many
boards the card presents, what nibbles it drives per register, and what a RAM board would have to add.
No capture taken so far has ever looked at this phase — every existing trace is boot or ATK memory test.

## Why this is the right measurement

- `AddMemList` appears nowhere in ROM v2 (fitted), ROM v1, the on-disk driver `driveinit_seg.bin`, or
  the supplied `RocHard.adf`. Nothing in software ever announces the RAM.
- The RAM works with the HD disabled ⇒ the RAM is a **separate autoconfig board**, not a side effect of
  the HD driver.
- The ROM's address lines are hardwired (`U6/U20 A0-A5` = `AB1-AB6`, `A12` = `/ABEN`), so during a config
  access the ROM can only ever serve **one** 64-byte identity — the HD controller (er_Type C1/D1,
  64 KB, MEMLIST=0, manuf 2144, product 1). A second board's nibbles **cannot** come from the ROM.
  They must be driven by UA6 (and/or UA4/U17) onto `DB12-15`.
- The fitted `ua6_hd_b001d` uses **none** of `AB1-6` and **none** of `RAMCFG_2M/4M/8M`, so it cannot
  serve a register-indexed block nor encode the installed size.

## Electrical model to confirm (new)

`U17` (74LS245) has `DIR`(p1)=GND and `/CE`(p19)=GND — **permanently enabled, B→A** — so it continuously
drives `DB15/DB14/DB13` from `/HDEN` / `/RAMEN?` / `/ABEN`, and `DB12..DB8` high (B0-B4 float).
UA4 reaches `DB15/14/13` only through the 32.7 Ω resistors `R11/R14/R15`. UA6 sits directly on
`DB15..DB12` (pins 18..21).

⇒ **`DB12-15` behaves as a wired-AND during config**: U17 supplies the strap-derived default level, and
UA6 / UA4 / the ROM can only pull individual bits **LOW**. This is consistent with `b001d` successfully
forcing `DB15`/`DB14` low. **Design consequence: a UA6 autoconfig responder can only ever pull nibble
bits to 0 — every bit that must read as 1 has to be left released.** The capture tests this directly by
watching `DB12-15` and `/_ROMOE` at the same time.

## Channel map (16 ch) — spaced so no two probes sit on touching pins

Every signal here is a bus net available on several chips, so the assignment is chosen to keep at least
**one free pin between any two probes on the same side of the same package** (verified against the
netlist — minimum same-side gap is 2). Only two ICs take more than one clip, and the address/data bits
alternate between them, so consecutive bus bits are never neighbours.

| ch | label (use verbatim in KingstVIS) | probe point | notes |
|----|-----------------------------------|-------------|-------|
| 0  | `_AS`        | **UA4 pin 15** | bus cycle, active low (only clip on UA4) |
| 1  | `R_W`        | **U11 pin 4**  | 1 = read, 0 = write |
| 2  | `_CFGMATCH`  | **U10 pin 19** | 74LS688 `P=R`, **trigger** (only clip on U10) |
| 3  | `DB15`       | **R11 pin 2**  | resistor pad — DB side, *not* the `/_CFGD15` side |
| 4  | `DB14`       | **R14 pin 2**  | resistor pad — DB side |
| 5  | `DB13`       | **R15 pin 2**  | resistor pad — DB side |
| 6  | `DB12`       | **U6 pin 16**  | ROM D4 (no series resistor exists on DB12) |
| 7  | `AB1`        | **U6 pin 10**  | ROM A0 |
| 8  | `AB2`        | **U11 pin 10** | |
| 9  | `AB3`        | **U6 pin 8**   | ROM A2 |
| 10 | `AB4`        | **U11 pin 8**  | |
| 11 | `AB5`        | **U6 pin 6**   | ROM A4 |
| 12 | `AB6`        | **U11 pin 6**  | |
| 13 | `_DRVEN`     | **UA6 pin 23** | UA6 → UA4 pin 14 (only clip on UA6) |
| 14 | `_ROMOE`     | **U6 pin 22**  | is the ROM actually serving the data? |
| 15 | `_DTACK`     | **U11 pin 18** | does the card ack the config cycle? |

**Ground: U12 pin 10** — U12 takes no probes at all, so the ground lead is nowhere near a signal clip.

Grouped by part (8 parts total, only U6 and U11 take several clips):

| part | pins used | same-side spacing |
|---|---|---|
| **U6** (27C64, 28-pin) | left p6, p8, p10 · right p16, p22 | gaps of 2 and 6 |
| **U11** (GAL22V10, 24-pin) | left p4, p6, p8, p10 · right p18 | gaps of 2 |
| R11, R14, R15 | pin 2 each | discrete 2-pin parts, isolated |
| U10 p19 · UA4 p15 · UA6 p23 | one clip each | isolated |

The three DB15/14/13 probes deliberately use the **resistor pads** rather than a chip: every IC that
carries those nets (U17 p7-9, U2 p11-13, U6 p17-19, U7 p7-9) has them on three *touching* pins, whereas
R11/R14/R15 are separate 2-pin parts with no shorting risk at all. Take **pin 2** of each — that is the
`DBxx` (bus) side; pin 1 is UA4's `/_CFGDxx` side, which is what we do *not* want to measure.

*Fallback if the resistor pads are awkward to reach:* `DB15` → U6 p19, `DB14` → U17 p8, `DB13` → U2 p13.
That keeps them on three different packages and still leaves U6 at p16/p19/p22 (gaps of 3).

`AB1-AB6` give register offsets `$00-$7E`; autoconfig uses `$00`-`$4C`. Offset `$48` is the base-address
write, `$4C` is shut-up.

## Capture settings

- **Trigger:** `_CFGMATCH` **falling**, pre-trigger ~5 %.
- **Rate:** 16 MSa/s is sufficient (`_AS` cycles are ~560 ns). Use 50-100 MSa/s if depth allows.
- **Depth:** autoconfig completes in a few ms — 100 ms of capture is far more than enough.
- Arm the LA **while the Amiga is held in reset**, then release reset. The first `_CFGMATCH` fall after
  reset is the first autoconfig register read.
- If `_CFGMATCH` never triggers, fall back to triggering on `_DRVEN` falling, or `_AS` falling with a
  long capture, and we'll find the window in software.

## Runs to take (two captures — the diff is the point)

1. `roctec_ac_ramon.csv` — **DIP-1 ON, DIP-2 ON, JPA1 = 2M**, SIMMs in bank 0, `ua3b_rebuild8`,
   `ua6_hd_b001d`. Normal working config.
2. `roctec_ac_ramoff.csv` — identical, but **DIP-2 OFF**.

If the two config sequences are byte-for-byte identical, that is direct proof the card currently
presents nothing extra for the RAM, and run 1 becomes the baseline we design the UA6 responder against.

## Analysis

    python3 rh_acprobe.py roctec_ac_ramon.csv
    python3 rh_acprobe.py roctec_ac_ramon.csv roctec_ac_ramoff.csv   # diff mode

The script reconstructs the autoconfig registers exactly as `expansion.library` does
(`byte = (nibble@off & 0xf0) | (nibble@off+2 >> 4)`, one's-complemented for every register except
`$00/$02/$40/$42`), splits the trace into boards at each `$48`/`$4C` write, and decodes er_Type,
manufacturer, product, flags and size.

## What each outcome means

| observation | conclusion |
|---|---|
| exactly one board enumerated (er_Type `D1`, 64 KB, MEMLIST=0) | as expected — the RAM board is simply absent; proceed to design it into UA6 |
| a second board appears with MEMLIST set | the card *is* announcing RAM; the fault is elsewhere (size/base/DTACK) |
| `$48` base write observed | tells us the value UA4's latch is meant to capture — compare against the forced `(0,0,1)` |
| `DB12-15` change with `AB1-6` while `/_ROMOE` is high | something other than the ROM serves nibbles — identify it before designing UA6 |
| `DB12-15` only ever pulled low, never actively high | confirms the wired-AND model and constrains the UA6 equations |

## Target for the UA6 responder (once the baseline is in)

Second board, ZorroII + MEMLIST, size from `RAMCFG_2M/4M/8M`:

| jumper | size bits | er_Type |
|---|---|---|
| 2M | 110 | `0xE6` |
| 4M | 111 | `0xE7` |
| 8M | 000 | `0xE0` |

manuf 2144 (`0x0860`), a product code distinct from 1, DIAGVALID = 0, and the base write at `$48`
accepted (and ignored — the window stays hard-decoded at `$200000`, which is what the Amiga hardware
database means by "always mounted at $200000 (no autoconfig) — may have problems with other expansions").
