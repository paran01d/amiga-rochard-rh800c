# Hardware overview

The **Roctec RocHard RH800C** is a side-mounted expansion for the Amiga 500. It
plugs into the 86-pin expansion edge connector and combines three things on
one board:

- a **Zorro II autoconfig IDE controller** with an 8 KB boot ROM (autoboot
  under Kickstart 1.3 and later),
- up to **8 MB of fast RAM** in eight 30-pin SIMM sockets (four 2 MB banks of
  two 1 MB SIMMs each),
- an **unpopulated / untested SCSI** section. We did not touch it, and nothing
  in this repository covers it.

The card has its own power supply input; it is not powered from the Amiga.

Our card arrived faulty. This document describes how the board works as we now
understand it. The understanding comes from tracing the PCB into a KiCad
schematic (see [`../schematic/`](../schematic/)), reading out the GALs that
could be read, and logic-analyser captures. For how the two autoconfig boards
come up, see [Autoconfig](autoconfig.md). For the DRAM controller and the RAM
debugging, see [RAM subsystem](ram-subsystem.md).

> **Note on the schematic.** We drew the schematic by tracing the board, and it
> has known errors and omissions. They are listed in
> [Schematic corrections](#schematic-corrections) below. Where the schematic and
> this document disagree, this document reflects what we measured.

---

## Block diagram

```
                 Amiga 500 expansion edge connector (J1, plus J2 overflow pins)
   A1-A23, D0-D15, _AS _UDS _LDS R/W _DTACK _CCK _CCKQ _CDAC _CFGIN _RST ...
        |                 |                         |
        |          +------+-------+          ferrite beads FB3-FB12
        |          | U1 / U2      |          (control signals)
        |          | data buffers |                 |
        |          | '245 lo / hi |                 |
        |          +------+-------+                 |
        |                 | card data bus /DB0-/DB15
        v                 |
  +-----------+           +-----------------+--------------------+------------------+
  | U3 '245   |           |                 |                    |                  |
  | AB16-AB23 |     +-----+------+   +------+------+     +-------+------+    +------+------+
  | U5 '245   |     | U6 / U20   |   | U7 / U8     |     | UA6 GAL22V10 |    | SIMM0..7    |
  | low addr  |     | 27C64 boot |   | IDE data    |     | RAM-board    |    | 30-pin      |
  +-----+-----+     | ROM even/  |   | buffers     |     | autoconfig + |    | 4 banks x2  |
        |           | odd        |   | (byte-swap) |     | phase control|    +------+------+
        |           +-----+------+   +------+------+     +-------+------+           ^
        |                 ^ /_ROMOE         |                    | /_DRVEN          | SIMMA0-9,
        |                 |                 v                    v                  | RAS, CAS0-3
        |                 |           IDE header        +--------------+            |
        |                 |           (U15 addr/ctl)    | UA4 GAL22V10 |    +-------+--------+
        |           +-----+------------------------+    | $E8 window,  |    | UA3 daughter-  |
        +---------->| U10 '688 compare AB16-23     |    | RAM window,  |    | board:         |
        |           |  vs reference (U9 '374 latch |    | RAM base     |--->| UA3b GAL22V10  |
        |           |  + RN1 pull-ups/RN2 pull-    |    | latch        |    | (DRAM ctl)     |
        |           |  downs = $E8 before config)  |    +--------------+    | UA3a '244 buf  |
        |           +--------------+---------------+       /GALCLK1         +-------+--------+
        |                          | /_CFGADDR_MATCH                                |
        |                    +-----+-------------------------------------+    UA1/UA2 '158
        +------------------->| U11 GAL22V10, U12/U13/U14 GAL16V8       |    row/col address
                             | config latch, bus timing, DTACK, buffer |    muxes -> SIMMA0-7
                             | and ROM enables, SIMM write enables     |
                             +-----------------------------------------+
```

The diagram is simplified. In particular, several signals pass through 33 Ω
series resistors (R1-R26) and resistor arrays that are left out here.

---

## Chip-by-chip

We only list a role where our sources support it. "Original" means the factory
part is still fitted. "Rebuilt" means we replaced the part with our own GAL
design.

### Programmable logic

| Ref | Part | Status | Role |
|---|---|---|---|
| **UA4** | GAL22V10 (Lattice GAL22V10B) | Original, read out and decoded ([equations](../gal/original/ua4_equations.txt)) | Generates `/_E8WIN`, the $E8xxxx autoconfig window (o23). Holds the 3-bit **RAM base latch** o16/o17/o18 (`/_CFGD15/14/13`, captured from DB15/14/13 while `/_DRVEN` is high). Decodes the RAM window `/GALCLK1` (o19) from the latch, the JPA1 size straps and AB21-23. Generates `/_GALSTROBE` (o21). Holds the RAM-enable latch o22. Its pin 14 input is `/_DRVEN` from UA6. |
| **UA6** | GAL22V10 | **Rebuilt**: [`ua6_ram6`](../gal/ua6/ua6_ram6.pld) (fuse checksum 0x9365) | Phase control for autoconfig. It drives `/_DRVEN`, which gates the ROM and UA4's latch. It also presents the RAM as a second Zorro II board on DB12-15 and reads the size straps RCFG2/4/8. See [Autoconfig](autoconfig.md). We could not recover the original's logic: a TL866 black-box sweep cannot see its internal feedback state. |
| **UA3b** | GAL22V10 | **Rebuilt**: [`ua3b_rebuild8`](../gal/ua3b/ua3b_rebuild8.pld) (0xC824) | DRAM controller on the UA3 daughterboard. It produces RAS, CAS0-3 (one per bank), SIMMA8/SIMMA9, the row/column select and enable for UA1/UA2, and `_UA3SEL`, which enables U11's DTACK driver. The original was read-protected and had an AB17 bug. See [RAM subsystem](ram-subsystem.md). |
| **U11** | GAL22V10 | Original, decoded ([equations](../gal/original/u11_equations.txt)) | Config latch `/BASE_C` (o21, active high, set by the base write at $48 while `/_E8WIN` is low, then self-holding). `_BUFRDY` (o20) enables U9's outputs after configuration. DTACK driver on pin 18 (output enable = `/_UA3SEL`). Buffer enables `/_RAMCE` (o22) and `/_U1CE` (o16). |
| **U12** | GAL16V8 | Original, decoded ([equations](../gal/original/u12_equations.txt)) | Bus timing. `BASE_A` is `_AS` registered twice (about 280 ns into a bus cycle). `/BASE_B` = `/_LATCH_EN & /_GALSTROBE`. |
| **U13** | GAL16V8 | Original, decoded ([equations](../gal/original/u13_equations.txt)) | IDE/SCSI glue. Takes `/_CFGADDR_MATCH` from U10. |
| **U14** | GAL16V8 | Original, read-protected, functionally validated (1024 vectors, 0 mismatches against [equations](../gal/original/u14_equations.txt)) | ROM output enable `/_ROMOE` (o15, through R21 to U6/U20 pin 22), SIMM byte-lane write enables, and IDE decode. Its pin 1 input is `/GALCLK1` from UA4. |

### TTL and memory

| Ref | Part | Role |
|---|---|---|
| **U1 / U2** | 74LS245 | Card data bus buffers, low byte / high byte, enabled by `/_U1CE` and `/_RAMCE` from U11. The ROM, RAM and IDE data all pass through them. |
| **U3** | 74LS245 | Buffers A16-A23 from the edge connector onto AB16-AB23, non-inverting. The "/" in the net names does not mean inverted. |
| **U5** | 74LS245 | Buffers low-order address lines onto the card. We inferred this from tracing and did not characterise it in detail. |
| **U4** | 74LS245 | Bus buffer. We did not need to characterise its role. |
| **U7 / U8** | 74LS245 | IDE data buffers, high / low byte. The wiring **swaps the bytes**; see [IDE byte-swap](#the-ide-byte-swap). |
| **U15** | 74LS245 | IDE address/control buffer. IDE DA0/DA1/DA2 come from card address bits A5/A6/A7. |
| **U17** | 74LS245 | Strap reader. It puts DIP-switch states such as `/HDEN` (DIP-1) on the data bus for the ROM firmware. |
| **U9** | **74LS374** (the schematic wrongly says 74LS688) | Latches the base address the OS assigns (D8-D15) when `/BASE_C` clocks it. Its outputs are tri-stated (`/OE` = `_BUFRDY`) until configuration is done. The latched value drives U10's reference inputs. |
| **U10** | 74LS688 | 8-bit comparator. It compares AB16-AB23 with the reference from U9/RN1/RN2 and outputs `/_CFGADDR_MATCH`. |
| **RN1 / RN2** | Resistor networks | Before configuration they set U10's reference to **$E8**. RN1 (common to +5 V) pulls up the AB19/21/22/23 reference pins, and RN2 (common to **GND**) pulls down AB16/17/18/20. See [Autoconfig](autoconfig.md#e8-decode). |
| **U6 / U20** | 27C64 EPROM | Boot ROM. U6 holds the even (high) bytes and U20 the odd (low) bytes. The two 4 KB halves are selected by A12 (`/ABEN`). See [the ROM](#the-boot-rom). |
| **UA1 / UA2** | 74LS158 | Inverting quad 2:1 multiplexers that drive SIMMA0-SIMMA7 with the DRAM row or column address. UA3b drives their select (pin 1, `UA3B8`) and their `/G` enable (`MUXEN`, UA3b pin 23; this connection is not drawn in the schematic). |
| **UA3a** | 74LS244 | Buffer on the UA3 daughterboard. It drives `_RAMRAS`, `_RAMCAS0-3`, SIMMA8 and SIMMA9 from UA3b to the SIMM sockets. |
| **SIMM0-SIMM7** | 30-pin SIMM sockets | Four banks of two. Each pair is one 16-bit bank: one SIMM is the upper byte lane, the other the lower (`_SIMMWEU` / `_SIMMWEL`). |
| **FB3-FB12** | Ferrite beads | In series with J1 control signals (`_CCK`, `_CCKQ`, `_CDAC`, `_DTACK`, `R_W`, `_LDS`, `_UDS`, `_AS`). They are also the most convenient logic-analyser probe points. |

### The UA3 daughterboard

The "UA3" socket does not hold a single chip. It holds a small piggyback
daughterboard with one GAL22V10 (**UA3b**) and one 74LS244 (**UA3a**). We have
seen photos of cards that have a bare GAL in this position instead.

> **Seat the UA3 daughterboard firmly, and secure it if you can.** A badly
> seated daughterboard caused at least three false "logic fault"
> investigations on our card. It also caused the intermittent RAM errors we
> chased for weeks. If the RAM suddenly stops working, reseat UA3 first.

---

## Switches and jumpers

| Control | Function |
|---|---|
| **DIP-1** | **HD enable.** It also gates autoconfig. With DIP-1 OFF the card does not appear in the autoconfig chain at all. |
| **DIP-2** | **RAM enable.** With DIP-2 OFF no RAM size strap is active, and our UA6 skips the RAM board (it behaves as an HD-only card). |
| **DIP-3** | **Kickstart 1.2 / 1.3+ ROM half.** DIP-3 grounds `/ABEN` (ROM A12) to select the non-autoboot half (er_Type `$C1`, for KS 1.2). Open, a pull-up selects the autoboot half (er_Type `$D1`). The schematic does not show DIP-3. |
| **JPA1** (JPA1-1 / -2 / -3) | **RAM size: 2 MB / 4 MB / 8 MB.** The jumper routes the RAM-enable common to one of `/RAMCFG_2M`, `/RAMCFG_4M`, `/RAMCFG_8M` (active low). These go to UA4 (window size) and to UA6 (RCFG2/4/8, which sets the size the RAM board advertises). Set it to match the SIMMs fitted. |
| **SW1 "Game switch"** | Three-position switch, normally on an external cable. **II** = HD and RAM enabled. This grounds `/_BANK_SEL`, which UA4 needs before `/_E8WIN` can open. **I** = HD disabled, RAM enabled. **O** (centre) = both disabled. With the switch unplugged the card is disabled. These positions come from the manual and UA4's equations. |

Working settings on our card: **SW1 = II, DIP-1 ON, DIP-2 ON, DIP-3 = 1.3,
JPA1 = 2M or 4M** to match the fitted SIMMs. With 4M the SIMMs are in
SIMM0-SIMM3.

---

## Address map

| Region | Contents |
|---|---|
| `$E80000` (before config) | Autoconfig space. Our UA6 answers here first (the RAM board), then the ROM (the HD board). |
| Board base, e.g. **`$E90000`** (64 KB) | HD controller I/O, assigned by the OS. |
| base + `$0000`.. | Boot ROM. Word *n* = `u6_even[n] << 8 \| u20_odd[n]`. |
| base + `$7000` | Control / data-latch window. IDE data moves through a latch here, with handshake bits; it is not a plain IDE data register. |
| base + `$8000` | IDE task file, drive 0 (master). Registers sit at odd offsets spaced `$20` apart (e.g. command at `$E1`, alt-status/control at `$20C1`). |
| base + `$0000` | Drive 1 (slave), according to the ROM decompile. This overlaps the ROM range above. We did not verify it on hardware, because we only ever used drive 0. |
| `$200000`-`$3FFFFF` | Fast RAM bank 0 (SIMM0/1). |
| `$400000`-`$5FFFFF` | Fast RAM bank 1 (SIMM2/3), with JPA1 = 4M or 8M. |
| `$600000`-`$7FFFFF` | Fast RAM bank 2 (SIMM4/5), with JPA1 = 8M. |
| `$800000`-`$9FFFFF` | Fast RAM bank 3 (SIMM6/7), with JPA1 = 8M. |

The IDE offsets come from disassembling the boot ROM's driver. We confirmed
base + `$8000` on hardware with our `rocdiag` probe: every ATA command
completed and returned the expected status there.

---

## The IDE byte-swap

The card connects IDE DD0-7 and DD8-15 to the **opposite halves** of the Amiga
data bus. It does this by design. Many Amiga IDE interfaces do the same, and
it is the reason the manual says the card "cannot read disks formatted by
other controllers".

The swap has these effects:

- Sector data reads back byte-swapped within every 16-bit word. A standard
  `RDSK` block at sector 0 reads as `DRKS`.
- ATA IDENTIFY strings look **correct**. ATA stores those strings byte-swapped
  already, so the hardware swap cancels out.
- A disk image built on another machine must be byte-swapped before you write
  it to the CF card or drive (`dd conv=swab`). Emulators that model the
  RocHard (WinUAE / Amiberry) take the **unswapped** (logical) image, because
  they model the swap themselves.

See [`../disk-image/`](../disk-image/) for our Linux image builder.

---

## The boot ROM

- Two 27C64 EPROMs: **U6** holds even bytes (D8-D15) and **U20** holds odd
  bytes (D0-D7). Our dumps match WinUAE's known-good "RocHard RH800C v2" ROM
  by CRC.
- **A12 (`/ABEN`) selects one of two 4 KB halves**, and DIP-3 drives it. The
  halves differ **only in word 0**, which carries the er_Type nibble:
  - A12 high (pull-up): **autoboot** half, er_Type `$D1` (DIAGVALID set, so
    Kickstart runs the boot code).
  - A12 low (DIP-3 to ground): **KS 1.2** half, er_Type `$C1` (no boot code).
- The `/ABEN` pull-up is a **factory bodge wire** from U6 pin 2 to RA4
  **pin 7**. The schematic shows RA4.8. On our card this wire came off. The
  card then showed er_Type `$C1` whatever DIP-3 was set to, and never
  autobooted.
- The ROM also serves the HD board's whole autoconfig identity on DB12-DB15.
  The identity comes from ROM data, not from GAL logic. See
  [Autoconfig](autoconfig.md#the-hd-board-rom-served-identity).
- For autoboot, the ROM loads a driver (`DriveInit`, an LSEG chain) from the
  disk's RDB and checks a capacity marker at RDB offset `$D4` (it needs at
  least `$20000`). A disk that has neither will mount but not autoboot. The
  driver is copyrighted and is **not** included in this repository.

---

## Schematic corrections

The [KiCad schematic](../schematic) is reverse-engineered by hand from one board
and is incomplete (no SCSI section, power circuitry or RAM data return paths).
Several parts were mis-identified on the first pass, most notably **U9, which is
a 74LS374 latch, not the 74LS688 drawn**. Every known correction, with the
evidence and whether it is already fixed in the drawing, is in
[schematic corrections](schematic-corrections.md).

## Physical faults we found

Most of the "logic" faults on this card turned out to be physical. If your card
misbehaves, check these first:

1. **UA3 daughterboard not fully seated.** Symptoms: the RAM looks
   "defective", the machine won't boot with RAM enabled, there are
   intermittent lost writes, or a logic-analyser trace goes completely static
   after the first RAM access.
2. **SIMM socket contact bridge.** On our card the SIMM4 socket shorted pin 12
   (SIMMA5) to pin 13 (DQ3 = `/DB3`). That held `/DB3` at about 4 V, so ROM
   bit 3 always read as 1 and autoboot crashed to a black screen.
   Straightening the contacts fixed it. We left SIMM4 empty afterwards.
3. **Detached `/ABEN` bodge wire** (U6.2 to RA4.7). The card showed er_Type
   `$C1` and never autobooted.
4. **Dirty A500 edge connector.** The card did not autoconfigure.
5. **R21** (U14.15 `/_ROMOE` to the ROM `/OE` pins) had gone open. We replaced
   it with 10 Ω 1 %.
6. **Amiga PSU with weak or missing -12 V** (a "pico" PSU). This killed serial
   TX and distorted the audio on both of our A500s. It was not a card fault, but it
   cost us debugging time because we used serial for diagnostics.
