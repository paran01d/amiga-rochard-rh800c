# Original Roctec GAL logic

These files were read or characterised from the GALs on an original Roctec RocHard RH800C. They are here so the card can be repaired and preserved. The original logic design is copyright of its authors. We didn't write it, and we publish these recovered copies only so that surviving cards can be kept running.

## Files per chip

| Chip | Raw dump | JEDEC | Equations | Notes |
|------|----------|-------|-----------|-------|
| UA4 (22V10) | `ua4_original.dump` | `ua4_original.jed` | `ua4_equations.txt` | Galdurino read at poti 238. `ua4_original_v2.jed` is an identical reconversion. `ua4_verification_original.dump` is a later read attempt. |
| U11 (22V10) | `U11_22v10_original.dump` | `u11_original.jed` | `u11_equations.txt` | Five byte-identical reads |
| U12 (16V8)  | `U12_original.dump` | `u12_original.jed` | `u12_equations.txt` | |
| U13 (16V8)  | `U13_original.dump` | `u13_original.jed` | `u13_equations.txt` | |
| U14 (16V8)  | `u14_verification_original.dump` | `u14_original.jed` | `u14_equations.txt` | Read-protected. Read via the Galdurino bug. Two reads agree (`u14_verification_original.jed` is identical), and a TL866 functional check matched 1024 vectors with 0 mismatches. |
| UA6 (22V10) | | `ua6_original_crack.jed` | `ua6_original_crack.pld` | **Not a fuse read.** See below. |
| UA3b (22V10) | | `ua3b_protected_readback.jed` | | What minipro reads from the protected original: near-blank, with zeros in the UES bits. Kept as a reference for what a protected read looks like. |

- `.dump` is raw Galdurino serial output (`GAL:` / `PES:` / `FUSEMAP:` / `UES:` / `CFG:` sections). Convert it with `galdurino-tools/gald2jed.py` (16V8) or `gald2jed_22v10.py` (22V10).
- `*_equations.txt` is MAME `jedutil -view` output. Pins are named `iN` (input) and `oN` (output), and `oN.oe` is the output enable. A term such as `o16 = ... + o16` is a self-holding latch.
- For the signal names behind each pin, see the schematic and [docs/gal-reverse-engineering.md](../../docs/gal-reverse-engineering.md).

## UA6: what the `ua6_original_crack` files are

UA6 couldn't be read. `ua6_original_crack.pld` encodes only what a TL866 black-box sweep could *see* at the pins: two outputs held low, everything else Hi-Z. The sweep can't observe UA6's internal state (most likely internal feedback on unconnected pads; the original's real logic was never recovered), so this file does **not** reproduce the chip. A GAL burned from it red-screens the Amiga. Some of the comments in the `.pld` interpret the sweep in ways we later found to be wrong. The replacement design that works is [`../ua6/ua6_ram6.jed`](../ua6/).
