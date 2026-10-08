# Schematic corrections

> ⚠️ The schematic is **reverse-engineered by hand from one board** and is
> **incomplete**: it leaves out the **SCSI** section, the **power** circuitry and
> the **RAM data return paths**, and it surely has errors we haven't found. Verify
> any net with a meter before relying on it.

The KiCad schematic in [`../schematic/`](../schematic) was **drawn by hand from
the board** before most of the debugging. While fixing the card we found several
places where it disagrees with the real hardware. Each one is listed here with
the evidence for it.

**Status (October 2026):** the schematic in [`../schematic`](../schematic) already
includes corrections 2, 4 and 11 and the U1 D0-D2 connections (part of 8); the
others are still to do. Use this page alongside the drawing.

| # | Item | Schematic shows | Real board | Status |
|---|---|---|---|---|
| 1 | U9 | 74LS688 comparator | **74LS374** octal latch | To do |
| 2 | RN2 common | +5 V (pull-up) | **GND (pull-down)** | ✅ Fixed |
| 3 | DIP-3 | Not drawn | Grounds `/ABEN` (KS 1.2 setting) | To do |
| 4 | `/ABEN` pull-up | RA4 pin 8 | **Factory bodge wire to RA4 pin 7** | ✅ Fixed |
| 5 | SIMM DQ0-7, VCC, GND | Unconnected | Connected (DQ to the `/DB` bus) | To do |
| 6 | SIMM address series resistors | Not drawn | Resistor arrays between UA1/UA2 and the SIMMs | To do |
| 7 | Low-lane SIMM pin 13 | Unconnected | **`/DB3`** | To do (part of 5) |
| 8 | J2 | 2×3 header | Stand-in for extra J1 edge pins | Note only |
| 9 | UA4 | 20-series PAL symbol (`PAL20R8xx-P`) | **GAL22V10** | To do |
| 10 | R21 | 32.7 | **10 Ω 1 %** fitted | To do |
| 11 | UA3b pin 23 (MUXEN) | Goes nowhere | **Drives `/G` of UA1 and UA2** (74LS158) | ✅ Fixed |
| 12 | U11 pin 17 | Labelled as an output (`~O3`) | **Input** (`/_UA3SEL` from UA3b pin 14) | Net fixed; pin label still `~O3` |
| 13 | UA4 pin 16 label | `DB12` | **`/_CFGD15`** (to DB15 via R11) | ✅ Fixed |
| 13 | R22, R23 | | 56 Ω | **Already correct** in the schematic |

---

## 1. U9 is a 74LS374, not a 74LS688

The part on the board is marked **74LS374**. We read the marking after the
schematic was drawn. The wiring only makes sense for a '374:

| U9 pin(s) | Net | '374 function | '688 function would be |
|---|---|---|---|
| 3, 4, 7, 8, 13, 14, 17, 18 | D8-D15 (data bus) | D inputs | mixed P/Q inputs |
| 11 | `/BASE_C` (U11 pin 21) | **CLK** | Q7 input |
| 1 | `_BUFRDY` (U11 pin 20) | **/OE** | /G enable |
| 2, 5, 6, 9, 12, 15, 16, 19 | → RN1/RN2 → U10 reference inputs | Q outputs | 19 would be the single `/P=Q` output |

So **U9 latches the base address the OS writes** (D8-D15, clocked by
`/BASE_C`) and feeds it to U10's reference inputs. U10 *is* a 74LS688. It
compares AB16-AB23 with that reference. Before configuration, U9's outputs are
Hi-Z (`_BUFRDY` high) and the reference comes from the resistor networks only
(see item 2).

U10 reference pin → address bit: p3 = AB16, p5 = AB17, p7 = AB18, p9 = AB19,
p12 = AB20, p14 = AB21, p16 = AB22, p18 = AB23.

## 2. RN2's common goes to GND (pull-down)

The first-pass schematic drew both RN1 and RN2 with their commons on +5 V (now corrected). On the board,
**RN1 common = +5 V** and **RN2 common = GND**. We confirmed this with a powered
scope measurement.

- RN2 feeds U10 reference pins 3/5/7/12 = AB16/17/18/20, the four **0** bits
  of `$E8`.
- RN1 feeds pins 9/14/16/18 = AB19/21/22/23, the four **1** bits.

Together they wire U10's reference to **`$E8`** before configuration, which is
the Zorro II autoconfig space. After configuration U9 drives the assigned base.
On our A500 that is `$E9`, which differs from `$E8` only in AB16. We saw U10 p3
go from low to about 3.4 V: the '374 driving high against RN2's pull-down.

## 3. DIP-3 is missing

The schematic's DIPSW1 has pins 3/14 unconnected. On the board, **DIP-3 grounds
`/ABEN`** (ROM A12) when ON. That selects the non-autoboot (KS 1.2) half of the
boot ROM. OFF leaves `/ABEN` pulled up, which selects the autoboot half.

## 4. `/ABEN` pull-up is a factory bodge to RA4 pin 7

The first-pass schematic showed `/ABEN` on RA4 pin 8 (now corrected). On our board the pull-up is a
**factory bodge wire from U6 pin 2 to RA4 pin 7**. When that wire came off,
the card was stuck on the non-autoboot half
(see [troubleshooting](troubleshooting.md#detached-aben-bodge-wire)). We don't
know whether every RH800C has this bodge.

## 5. SIMM data and power pins are not drawn

The schematic leaves all SIMM **DQ0-DQ7** pins (3, 6, 10, 13, 16, 20, 23, 25)
and **VCC/GND** (1, 30 / 9, 22) unconnected. On the board the DQ pins connect to
the card's `/DB` data bus: each SIMM socket is one byte lane of a 16-bit bank.

## 6. SIMM address series resistor arrays are not drawn

The SIMM address lines go through **series resistor arrays** that the schematic
omits. Example: **SIMMA5 comes from UA2 pin 9 through a resistor array to SIMM
pin 12.** We haven't recorded the array reference designators and values yet.

## 7. Low-byte-lane SIMM pin 13 = `/DB3`

This follows from item 5, and it matters in practice. In the low-byte-lane
sockets, pin 13 (DQ3) sits **directly on `/DB3`**, next to pin 12 (SIMMA5). A
bridge between them in the SIMM4 socket held `/DB3` at about 4 V and corrupted
ROM bit 3 (see [troubleshooting](troubleshooting.md#simm-socket-contact-bridge-on-db3)).
SIMM4 is in this lane. We haven't mapped every socket to its lane.

## 8. J2 is a stand-in for J1

J2 (a 2×3 header) is not a real connector. No KiCad symbol had enough pins for
the edge connector J1, so J2 holds the overflow J1 pins. D3-D7 are on J2, and
U1's Amiga-side D0-D2 (pins 2-4) go to J1 pins 75/77/79.

## 9. UA4 is a GAL22V10

UA4 is a **GAL22V10**. The symbol's value says `GAL22V10B`, but it uses a
20-series PAL symbol (`PAL20R8xx-P`) as a placeholder. On the real part,
pins 14 and 23 are macrocell I/O (pin 23 is `/_E8WIN`), not dedicated inputs,
and there are ten possible outputs (pins 14-23). Don't trust the symbol's pin
types.

## 10. R21 value

R21 is marked "RC" on the board. It sits in the ROM `/OE` path: U14 pin 15
(`/_ROMOE2`) → R21 → `/_ROMOE` → U6/U20 pin 22. The schematic gives its value as
**32.7**. The part now fitted is **10 Ω 1 %** (brown-black-black-gold-brown,
measures 9.9 Ω in circuit). The original was open circuit (4.5 kΩ), which
stopped the card from autoconfiguring. We don't know the original's exact
factory value for certain. A low value like this works.

## 11. UA3b pin 23 (MUXEN) drives the address-mux enables

The first-pass schematic showed UA3 pin 23 going nowhere (now corrected). It is **MUXEN**, the active-low
enable that drives `/G` on both **UA1 and UA2** (74LS158 row/column address
muxes). We found this while rebuilding UA3b (rev 4 of the rebuild). See
[`../gal/ua3b/ua3b_rebuild8.pld`](../gal/ua3b/ua3b_rebuild8.pld).

## 12. U11 pin 17 is an input

The KiCad symbol labels U11 pin 17 `~O3`, which suggests an output. It is the
**input** `/_UA3SEL`, driven by **UA3b pin 14**, and it is the only enable for
U11's DTACK driver for RAM accesses. When DTACK goes missing on a RAM access,
look at UA3b, not U11.

## 13. R22/R23 (already correct)

R22 and R23 measure 56 Ω (green-blue-black). The schematic in this repo already
shows 56.

---

## Open questions

- **DIP-1 behaviour.** In the schematic, DIP-1 only connects `/_E8WIN` to `/HDEN`
  (a pull-up read by U17), which looks like a soft, firmware-level HD enable.
  U10 and U11 take `/_E8WIN` from upstream of the switch. On the real card,
  though, **the HD board does not autoconfig at all with DIP-1 OFF**. Either
  the drawing is missing a connection, or the effect is indirect. We haven't
  resolved this.
- **SCSI section.** It is unpopulated or untested on our card and has not been
  checked against the schematic.
