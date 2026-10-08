# Work log: Roctec RocHard RH800C restoration

This is the dated log of restoring a Roctec RocHard RH800C, an Amiga 500 side expansion that combines a
Zorro II IDE controller with up to 8 MB of fast RAM on 30-pin SIMMs. It also has an unpopulated,
untested SCSI section. The card was bought faulty. The owner did the work together with Claude
(Anthropic's AI assistant, running in Claude Code) between July and October 2026.

The entries are kept in order and include the dead ends, because the dead ends account for most of
what we learned. Some theories were believed for days and then disproved. When an entry records one
of those, it is labelled as a hypothesis and the entry that disproved it is named. For the current
state of the card, read the final section and the top-level documentation, not the middle of this log.

**Conventions.** Signal names follow the KiCad schematic in `schematic/`. A leading `/` or `_` usually
means active-low. "LA" is the 16-channel Kingst logic analyser. "TL866" is the TL866II+ programmer run
through `minipro`. Fuse checksums are the values `minipro` reports when it verifies a GAL.

---

## Before mid-July: the starting point

### Before mid-July: UA4 replacement drafts 05-08 (dead end)

- The card arrived faulty. UA4 (a GAL22V10; the schematic draws it with a 20V8 symbol only as a
  placeholder) looked dead, with pin 19 stuck high. We assumed every GAL on the card was read-protected
  and could not be copied (it later turned out only some were: U14 and UA3b).
- We wrote replacement UA4 logic by guesswork, in `gal/ua4/ua4.pld`.
  - **Draft 05**, the "broken-chip emulator", holds every output at a safe level. The Amiga boots
    and the card stays invisible.
  - **Draft 06** pulsed `/GALCLK1`. The machine hung on a grey screen with `/OVR` asserted and
    `/AS` stuck low, waiting for a `/DTACK` that never came.
  - **Draft 07** also pulsed `/_GALSTROBE`. It hung the same way.
  - **Draft 08** inverted the strobe and gave a red screen.
- Lesson: autoconfig depends on a cascade of U11, U12, U14, UA6 and UA4. Without the real equations of
  the other chips, guessing at UA4 alone cannot work. That sent us off to build a GAL reader.

---

## July 2026

### 2026-07-14: UA4 cracked

- We used a home-built Galdurino reader (an Arduino that drives the programming voltage through a
  digital potentiometer; the tools are in `galdurino-tools/`) to attack UA4's security fuse with
  voltage glitches. After hundreds of failed attempts, a read at **poti = 238** returned a believable
  fuse map: 77 % zeros, and it decompiles cleanly with MAME's `jedutil`.
- Results are in `gal/original/ua4_original.jed` and `ua4_equations.txt`. The read is rare and did not
  repeat, so `galdurino-tools/crack22v10.py` captures the exact procedure.
- All of UA4's outputs are combinatorial. Pins 16/17/18 are self-holding latches (`o16 = ... + o16`), and
  their output enable comes from pin 14.

### 2026-07-15: hidden traces and the `/_E8WIN` / `/_DRVEN` link

- Netlist cross-referencing and probing the PCB found several traces that the schematic did not show:
  - UA4 pin 23 is `/_E8WIN` (it feeds U11 pin 23).
  - UA4 pin 14 is driven by **UA6 pin 23 (`/_DRVEN`)**. That net has no pull resistor.
  - UA6 pin 14 is `/CFGIN`, pin 17 is `/_RST`, and pins 18-21 sit on `/DB15`-`/DB12`.
- This put UA6 directly in the autoconfig path. UA6 had not given up a fuse map at any voltage.

### 2026-07-17: clocks and straps

- U12 rebuilds a 7.09 MHz clock locked to the chip bus from `_CCK` XNOR `_CCKQ`. That clock drives
  `/BASE_A` and `/_LATCH_CLK` into U11.
- The JPA1 straps select RAM size, not autoconfig behaviour. UA6 pins 8/9/10 = `/RAMCFG_8M/4M/2M` and
  pin 11 = `/BASE_A`. An earlier pin-8 assignment was wrong and was corrected here.

### 2026-07-19: TL866 black-box pipeline; UA6 sweep and its paradox

- We built a black-box sweep pipeline (`tl866-probe/`). It generates every input vector, runs it
  through `minipro --logic_test` with a custom `logicic.xml`, and makes two passes (pull-up and
  pull-down) so a truly Hi-Z output can be told apart from a driven one.
- We validated it against U11's fuse-map crack: all **131,072 vectors matched, 0 mismatches**.
- We swept all 16,384 input combinations of the original UA6. Pins 15 and 16 read constant low and
  pins 18-23 read Hi-Z. A second run was bit-identical to the first.
- A clone burned from that result (`gal/original/ua6_original_crack.pld`) red-screened the Amiga,
  while the original chip in the same socket did not.
- Hypothesis recorded at the time: "the original UA6 is broken". This was later dropped. The real
  explanation is most likely that a static sweep cannot see UA6's internal feedback state (held on
  unconnected pads); the original's logic was never recovered. See 2026-08-16.

### 2026-07-20: netlist export, WinUAE source, first UA6 rebuilds

- A `kicad-cli` netlist export settled most pin directions. On the A500, `/CFGIN` (J1.12) is tied to
  ground, because the side slot is a single-card chain.
- WinUAE's RocHard emulation (`rochard_init`, `rochard_sub`) and its `expamem_read` gave us the
  authoritative Zorro II nibble format: each register byte is two nibbles on D15-D12, one's-complemented
  except at offsets `$00/$02/$40/$42`. Decoding the board's boot ROM this way gives manufacturer
  **2144**. The autoconfig ID is served by the ROM, not generated by a GAL.
- We disassembled the boot ROM and found no `AddMemList` call. We then went back and forth on whether
  the RAM is an autoconfig board at all. "RAM is not autoconfig" became the working assumption. It
  was disproved on 2026-08-16.
- We wrote two UA6 rebuilds from first principles:
  - `ua6_rebuild` (0x52B4) boots cleanly but nothing autoconfigures.
  - `ua6_rebuild2` (0x51F6) damps a `/_DRVEN` and `/_E8WIN` oscillation that the LA had shown ringing
    in bursts.
- With a RAM strap grounded by hand, DiagROM got as far as fast-RAM detection and then hung.

### 2026-07-21: the card enumerates for the first time

Three faults were stacked on top of each other, and fixing any single one would have changed nothing:

- **The Game switch (SW1) was unplugged.** With it unplugged, both of its lines float high, which
  selects position O: HD and RAM disabled. The card had been switched off for the whole
  investigation. The user manual (now in hand) confirms that position II enables HD and RAM, and that
  the HD runs with **no RAM at all**.
- **R21 had failed open.** R21 is the series resistor from U14 pin 15 to the ROM `/OE` pins,
  silkscreened "RC". It measured 4.5 kΩ in circuit, so the ROM was never enabled. After replacement
  the fitted part is a 10 Ω 1 % resistor.
- **A rogue clone U14 with inverted `_ROMOE` polarity** was in the socket. Putting the original U14
  back fixed that. A fresh re-crack, our own `gald2jed.py` and a Java JED converter all produced the
  same fuse map, which confirmed the original equations.
- We also rewrote UA6 as an HD-only build. `gal/ua6/ua6_hd.pld` (fuse **0x654B**) latches `/_DRVEN`
  low after the first synced access, with no dependence on the RAM straps. It leaves `/_AC_PHASE`
  Hi-Z, because driving it low red-screened the machine, and it leaves DB12-15 Hi-Z.
- Result: DiagROM lists one Zorro II board, manufacturer 2144, product 1.

### 2026-07-22 to 07-24: IDE bring-up; U7 replaced; the formatter wall

- With the CF master/slave jumper fixed, the RocHard formatter could see the drive. The model string
  came back half-garbled ("ÿIÿIÿOÿSÿS...", every other byte `$FF`) and the reported size was wrong.
- A LA capture during a partition write showed both data pins of **U7** (the high-byte IDE buffer,
  a 74LS245) stuck high with zero transitions while the chip was enabled. We replaced U7, and IDENTIFY
  then read cleanly: the full model string and the correct 497 MB size.
- The formatter's "Save Part Info" still failed on every CF ("try different parameters"). We
  disassembled the formatter and found it is CHS-only.
- DiagROM read the full autoconfig buffer from the hardware:
  `D1 01 40 00 08 60 00 00 04 D2 00 80 00 00 00 00`. That decodes as er_Type `$D1` (Zorro II,
  DIAGVALID set, 64 KB), product 1, manufacturer `$0860` = 2144, serial 1234, DiagArea at `$0080`.
- We built an RDB from Linux and wrote it to the CF, but no DH0 appeared. An SD2IDE adapter behaved the
  same way, so the problem was on the card side.
- Two more suspects were ruled out by LA: a short between IDE address lines DA1 and DA2, and the U8 DD0
  buffer.

### 2026-07-25: rocdiag finds the byte swap

- We wrote a standalone IDE probe, `rocdiag`; its source was lost and the binary is kept in
  `amiga-tools/rocdiag/`. The ROM decompile gave the card's address map:
  - IDE task file at board + `$8000`
  - control/data latch at board + `$7000`
  - drive 1 at board + `$0`
- With the base fixed, every command succeeded: IDENTIFY, INIT DEVICE PARAMETERS `$91` and READ SECTOR.
  Sector 0 read back as **`DRKS`** instead of `RDSK`.
- **The card byte-swaps the IDE data bus, by design.** ATA stores IDENTIFY strings byte-swapped, so
  the swap cancels there, but ordinary sector data is reversed. This explains why our RDB was
  invisible, and it is why the manual says the card "cannot read disks formatted by other controllers".
- In the same session we settled a side question: U11's real fuse map does not use `/_AC_PHASE`
  anywhere.

### 2026-07-26: DH0 mounts

- After `dd conv=swab` on the image, DH0 mounted read/write through `rt.device` unit 0: 509 MB,
  0 errors. Autoboot still did not create the DOS node.

### 2026-07-31: what autoboot actually needs

- We dumped the board's EPROMs. Their CRCs match WinUAE's known-good v2 set exactly: even `c88843cb`,
  odd `c5b8f068`, combined `5c27be3f`. So the ROM is authentic.
- We ran the real RocHard formatter inside Amiberry, which emulates this card with its ROM, to get a
  genuine reference disk. It runs out of memory on large disks, so we used a small one.
- Diffing the reference RDB against ours showed two requirements:
  - **`rdb_DriveInit` must point to an LSEG chain holding the RocHard driver.** The reference has
    block 28; ours had -1.
  - **`RDB[0xd4]` must be `$00020000`.** The ROM checks this value before autobooting.

---

## August 2026

### 2026-08-01: HD side complete; LA arrives; the RAM red screen

- `disk-image/mkrochard.py` builds bootable CF images of any size on Linux. It writes a media-order
  (byte-swapped) image for the CF and a logical image for Amiberry. The last bug it had: the RDB
  logical-drive fields were written `$10` too low, so `CylBlocks` read as 0. The **card autoboots
  Workbench on real hardware.**
- The 16-channel LA arrived, and work turned to the RAM. The emulators do not model the card's RAM,
  so this all had to be done on real hardware.
- With a RAM strap on, the machine red-screened even with the SIMMs removed. The LA caught why: on the
  very first Kickstart fetch at `$F8xxxx`, `/_RAMCE` asserted and U2 drove D8-15, which corrupted the
  opcode.
- Tracing the cracked equations explained it. UA4's `/GALCLK1` RAM-window decode only looks at A21-A23
  plus the three-bit **base latch** (UA4 o16/o17/o18). With the latch settled at (1,1,1), it decodes
  the whole `$E0-$FF` region, which includes Kickstart.
- Each UA6 tweak moved the window somewhere else, which mapped out the latch values:
  - `ua6_hd_wr` (0x6616) released `/_DRVEN` on writes. It fixed nothing and broke the HD.
  - `ua6_hd_db13` latched (1,1,0), which decodes `$D8` (CIA). Result: yellow screen.
  - `ua6_hd_b001` (0x66AA) latched (1,0,1), which decodes `$A0`. One bit failed to move, because
    **the schematic mislabels UA4 pin 16**: it is `/_CFGD15` on DB15, not DB12. We found that by
    continuity.
  - `ua6_hd_b001c` (0x66D3) drives DB15/DB14 low at reset, giving latch (0,0,1) and a window at
    **`$200000`**. The machine now boots with RAM enabled.

### 2026-08-03: UA3b is alive

- A boot capture showed UA3b (the DRAM controller GAL on the UA3 daughterboard) producing proper
  CAS-before-RAS refresh continuously. An earlier reading of "`_UA3SEL` stuck high, chip dead" had
  been taken **with the daughterboard unseated**. This was the first of several false alarms that
  came from that daughterboard.

### 2026-08-05: `/_AC_PHASE` and U11 dead ends

- Hypothesis: a floating `/_AC_PHASE` blocks RAM select. We tested it with `ua6_hd_acp` (0x656A),
  which drives it low. That gave a yellow screen and broke the HD path too. The hypothesis was later
  disproved: a working RAM access was captured with `/_AC_PHASE` high.
- We re-swept U11 on the TL866 with pins 17 and 19 configured as outputs. They read Hi-Z for every one
  of the 131,072 vectors. At the time we took this to mean "dynamic output enable, can't be cracked
  statically". On 2026-08-09 the real explanation turned out to be simpler: pin 17 is an input.

### 2026-08-07: the RAM answers, sometimes

- A capture during ATK's memory *detection* showed complete reads and writes at `$200000`, with
  `_UA3SEL` and `_DTACK` returning. The datapath worked. ATK's memory *test*, run straight afterwards,
  hung the machine.
- We built two tools to find the failing address:
  - `gal/misc/berr_wdog.pld`, a GAL22V10 watchdog that asserts `/BERR` on expansion-slot pin 46 if a
    `$200000` access gets no `DTACK` within about 2.2 µs.
  - `amiga-tools/rhmemtest/`, a bootblock memory test that reports over serial.

### 2026-08-08: tooling bugs, then the A1 theory

- Our bootblock crashed on real hardware. Two bugs:
  - The walk started at an odd address, which raises an address error.
  - Bootblocks run in **user mode**, so `move.w #$2700,sr` is a privilege violation. The fix is to
    enter supervisor mode through exec's `Supervisor()`.
- We found both by bisection in fs-uae running headless under Xvfb. Each build colours the screen
  solid, and a script reads the screenshot's histogram.
- On real hardware, the test hung on the first write to `$200000`. ATK's source showed that its
  detect uses word writes and its test uses long writes.
- Hypothesis: address bit A1 is faulty. Disproved the next day.

### 2026-08-09: a long day of wrong turns

- **U11's real fuse map shows pin 17 (`/_UA3SEL`) is an input**, driven by UA3b pin 14. U11's `_DTACK`
  output has an empty data term (`o18 =`) and `o18.oe = /i17`. So `DTACK` is simply an echo of
  UA3b's select. No DTACK means UA3b never selected.
- With DIP-2 off, `t 200000` returned `$4E75` (open bus) instead of hanging. So the motherboard
  terminates unclaimed cycles, and when the card claims a cycle it is UA3b that fails to finish it.
- The A1 theory died: A1 = 0 addresses hung as well.
- Hypothesis: R15 is open. A LA channel showed `CFGD13` stuck low, and a careful argument based on that
  reading concluded that R15 was open. It was the **wrong probe clipped on**. Measured properly, the
  base latch reads **(0,0,1)**.
- Two UA6 builds made on the strength of that misreading, `b001e` (0x6C0C) and `b001f` (0x6BC0), fixed
  nothing.
- Checked as possibly faulty and found good:
  - UA4. A plain `minipro -r` read of the removed chip matched the 07-14 crack on all **5,892 fuses**,
    and a TL866 test showed pin 18 is not stuck.
  - Where the probe code runs. `amiga-tools/rhmemtest/rhchip.s` runs the probe from chip RAM instead
    of slow RAM, and it hung just the same.
  - DMA state and interrupt state.

### 2026-08-11: `b001f` red screen; the A17 signature

- `b001f` turned out to red-screen the machine, so we reverted to **`ua6_hd_b001d` (0x670D)**. b001f
  differed from b001d in three ways, not the one we had described, because we had diffed it against
  the wrong ancestor.
- A capture made address bit 5 look decisive. It was a coincidence from n = 1 and died within hours.
- Walking `t` across the window gave the real answer. `t 27FFFE` returned RAM FOUND, the first time
  the card had ever answered us, and so did `t 23FFFE`. The block map was conclusive:
  **A17 = 1 works, A17 = 0 hangs.** ATK's detect only worked because its probe anchor happens to have
  A17 set.
- UA3b out of circuit on the TL866: `_UA3SEL` only ever asserts with **AB17 (pin 1) high**. The chip is
  read-protected (64 zeros out of 5,892 fuses) and the Galdurino attack failed on it.
- Hypothesis: the architecture fuses decayed, turning macrocells into registers clocked by pin 1. This
  was dropped the same day. A GAL22V10 has a single register clock, but UA3b's state changed on edges
  of two different pins, so its state must come from **combinatorial feedback latches** (the same
  construct UA4 and U11 use).
- Black-box sweeping UA3b on the TL866 is a dead end. Sweeping the same 4,096 patterns in three
  different orders gave **23-44 % disagreement per output**, and minipro's Hi-Z detection drives
  values into the GAL's feedback paths. The chip had to be characterised in circuit.

### 2026-08-15: UA3b rebuilt from LA captures

- We found good probe points:
  - The ferrite beads FB3/4/5/8-12 carry `_CCK`, `_CCKQ`, `_CDAC`, `_DTACK`, `R_W`, `_LDS`, `_UDS` and
    `_AS`.
  - The SIMM socket pins carry the RAM signals. The R1-R7 pack sits under the daughterboard and
    cannot be reached.
- One trap: with 16 channels enabled the Kingst caps at 16 MSa/s. With 12 channels it does 25 MSa/s.
- Measured behaviour:
  - SIMMA8 carries row `/A18` and column `/A17`. SIMMA9 carries row `/A20` and column `/A19`.
  - Bank = (A23,A22,A21) − 1. We mapped it by moving JPA1 to 8M: accesses to empty banks then complete
    and return garbage instead of hanging.
  - An access lasts about 640 ns. The mux switches to column 80-440 ns in, and `_UA3SEL` asserts at
    about +400 ns.
- **`ua3b_rebuild` (0xA821) made `t 200000` return RAM FOUND.** Revisions 2-7 then fixed what that
  exposed:
  - **128 KB aliasing.** We had used pin 23 as a scratch state bit, but it is the `/G` enable of the
    UA1/UA2 '158 address muxes, a connection the schematic does not show.
  - **Refresh leaking into accesses.** The rule we arrived at: an access term may only key off a
    signal that refresh cannot leave asserted. We broke that rule three times, on RAS, CAS and
    `_UA3SEL`, before we saw the pattern.
- `ua3b_rebuild7` (0xC7F3): long accesses are correct and there is no aliasing.
- **`gal/ua3b/ua3b_rebuild8.pld` (0xC824)** widens the refresh RAS pulse from about 70 ns to about
  140 ns, by driving RAS from `/CCKQ`. Before this, a single bit decayed within seconds. With it,
  **ATK's "Test All Memory" completed a round for the first time.**
- The RAM was still not announced to the OS. We searched both ROM versions, the RDB driver and the
  install disk for any call to exec's `AddMemList` (LVO −618) and found none. The two ROM halves (4 KB
  per EPROM, selected by A12) differ only in word 0: the DIAGVALID bit of er_Type.

### 2026-08-16: autoconfig captured; UA6 rebuilt as a two-board responder

- `la-tools/AUTOCONFIG_PROBE.md` and the decoder `la-tools/rh_acprobe.py` capture the config phase
  itself. The decoder was validated against a synthetic capture generated from the real ROM.
- Captures with RAM enabled and RAM disabled came out **byte-for-byte identical**: one board (`$D1`),
  then a single base write of nibble 9 at `$4A`, which places the board at `$E90000`. **Nothing on the
  card was announcing the RAM.**
- Using the UA4 and U14 cracks, we then worked out the chain that lets UA6 announce it:
  1. UA6 raises `/_DRVEN`.
  2. UA4 releases `/_E8WIN`.
  3. U10 is disabled, so `/_CFGADDR_MATCH` goes high.
  4. U14 releases `/_ROMOE` and the ROM stops driving DB12-15.
  5. UA6 is free to present a second board. UA4's base latch sits in capture mode at the same time.
- None of the original chips needs changing. Our design keeps its phase latch on UA6's unconnected
  pad 22; the original very likely did something similar, which would explain why no socket sweep
  could ever see it.
- We burned six revisions in one day:

  | build | fuse | outcome |
  |---|---|---|
  | `ua6_ram` | 0x80D6 | RAM board enumerated, but the base latched (1,1,1) and froze the machine. The base value is on the bus for only one 62 ns sample. |
  | `ua6_ram2` | 0x900E | The drop term killed its own condition, so `/_DRVEN` stuck high and the HD never came back. |
  | `ua6_ram3` | 0x8F92 | Moved the phase latch to pad 22. Lost `/_DRVEN`'s self-hold, which broke the no-RAM path. |
  | `ua6_ram4` | 0x93A5 | Both paths latch. Kickstart lists "2144 / 2, DEFECTIVE": the base was captured as (0,0,0). |
  | `ua6_ram5` | 0x98AC | CHAINEDCONFIG cleared. Not needed; never fitted. |
  | **`ua6_ram6`** | **0x9365** | **Works.** `/BASEA` delays the drop to mid-cycle, and `$4A` is excluded from the base drive. |

- DiagROM reads the RAM board exactly as designed: `EE 02 00 00 08 60 00 00 ...`, Zorro II, linked to
  the free pool, 2 MB, assigned `$200000-$3FFFFF`.
- The last "crash" of the day was the **UA3 daughterboard sitting unseated again**. Once it was
  reseated, the **2 MB of fast RAM worked in Workbench.**

### 2026-08-17: long writes fail; a precharge theory

- `W 200000 A5A51234` read back as `A5A5FFFF`: every word with A1 = 1 failed, with both bytes failing
  together.
- `/UA3B8` (the row/column mux select) read "stuck low" on the LA. For the **third time**, that turned
  out to be a probe not seated on the pin.
- A capture suggested that an access RAS started only about 60 ns after a refresh RAS ended, which
  would be a precharge (tRP) violation. We built `ua3b_rebuild9` (0xC81C) to force a longer gap.

### 2026-08-18: rev 9 measured, rev 9 harmful

- This was the first properly resolved timing measurement of the project: 3 channels at 100 MSa/s.
  Under rev 9, the row address was pulled away **10 ns** after RAS fell (tRAH = 10 ns; DRAM needs
  15-20 ns). Rev 8's `/CDAC` arming term had been providing that hold time without our noticing.
- We **reverted to `ua3b_rebuild8`.** Rev 9 fixed a problem we had never measured and broke one we had
  never noticed.
- Rig rule adopted: debug the RAM with `ua6_hd_b001d`, which maps the window without announcing it.
  With `ua6_ram6` fitted, a faulty RAM makes Kickstart stop at the expansion-diagnostic screen.

---

## September 2026

### 2026-09-28: rev 8 baseline; the card goes quiet; schematic corrections

- Rev 8's baseline capture (`captures/roctec_write_cdac1002.csv`) shows **tRAH = 60 ns**, comfortably
  within spec.
- The same capture shows refresh RAS cut short when an access arrives (a "runt" refresh). We recorded
  this as a hypothesis for the RAM errors and planned a rev 10. It was **never confirmed**. The errors
  later turned out to have physical causes, and rev 10 was never built.
- We identified the unlabelled chips by reading back their fuses. With HD enabled, the machine
  black-screened under both UA6 builds. We reburned the b001d chip as `ua6_hd` (0x654B). A blank spare
  GAL refused to program and was written off.
- U14 is read-protected, so we validated it functionally on the TL866: **1,024 vectors, 0 mismatches**
  against `u14_equations.txt`, including the active-low `/_ROMOE`. R21 measured 9.9 Ω.
- Corrections to the schematic:
  - **U9 is a 74LS374**, not a 74LS688. It latches the base address the OS assigns, from D8-15, on
    `/BASE_C`.
  - **RN2's common goes to GND** (pull-down) and RN1's to +5 V. Together they hard-wire U10's
    pre-config reference to `$E8`.
- Autoconfig was in fact perfect: DiagROM's full buffer matched July's. DiagROM's one-line summary
  ("2144/0") misled us into a "DB12 stuck high" theory, which we withdrew once we had the full buffer.
- With DIP-1 off the card does not autoconfig at all, so **DIP-1 gates hardware**.
- With the KS1.2 ROM half selected (no boot code runs), rhmon read `E90080 = 9008` where `9000` was
  expected: **ROM data bit 3 stuck high**.
- U20, read out of circuit, matched its CRC perfectly, so the ROM contents were fine.
- A capture (`captures/roctec_db3.csv`) seemed to show U1 driving D3 high. U1 became the suspect.

### 2026-09-29: two physical faults, and autoboot is back

- On the scope, `/DB3` idled at about 4 V, and the ROM could only pull it down to about 1.4 V. A new U1
  behaved identically, **so U1 was not the fault.** The 4 V persisted with U1, U8 (one leg lifted) and
  U20 removed and the Amiga disconnected, so the source was on the card itself.
- **Root cause #1: a bridged SIMM4 socket contact.** Pin 12 (SIMMA5, driven by UA2 through a series
  resistor array) was touching pin 13 (DQ3 = `/DB3`). Neither the SIMM DQ lines nor that resistor
  array appear in the schematic. The bridge probably came from swapping SIMMs during the RAM work.
- After straightening the contacts and leaving SIMM4 empty, rhmon read `E90080 = 9000`. DH0 had been
  corrupted while bit 3 was bad, so we re-imaged the CF.
- Autoboot still failed. DiagROM showed er_Type `$C1` (AutoBoot: NO) even with DIP-3 set to 1.3.
- **Root cause #2: a factory bodge wire had come off.** The wire runs from U6 pin 2 (`/ABEN`, ROM A12,
  which selects the autoboot half) to the pull-up at RA4 pin 7. The schematic shows RA4.8 and does not
  draw DIP-3 at all. After resoldering, the **HD autoboots again.**
- RAM, with `ua6_ram6` and `ua3b_rebuild8` fitted:
  - **2 MB boots to Workbench.**
  - **4 MB works first time** (SIMM0-3, JPA1 = 4M). This was the first use of bank 1's `_RAMCAS1`,
    UA6's 4M er_Type `$EF` and UA4's 4M decode.
  - **ATK 4 MB: round 2, no errors.**

---

## October 2026

### 2026-10-02: A500 work (not the card)

- We upgraded the rev 5 A500 to 1 MB of chip RAM: an 8372A Agnus in a new socket, plus JP2 (centre to
  A19).
- It black-screened until **Gary pin 32 (`_EXRAM` from the trapdoor) was isolated.** The Sordan mini
  trapdoor card has no chip/slow jumper, so without this change the same 512 KB appears at both
  `$080000` and `$C00000`.
- After the case was reassembled, the RocHard stopped autoconfiguring. See 10-04.

### 2026-10-03: first intermittent error at 5 MB

- ATK at 5 MB (4 MB card + 1 MB chip) ran 6 clean passes, then reported an error on pass 7 at
  `$580000-$5FFFFF` (bank 1, SIMM2/3).
- The WHDLoad install of Speedball 2 crashed on real hardware, with and without PRELOAD. WHDLoad
  allocates fast RAM top-down, so the game lives at the very top of the RAM.
- We dropped back to 2 MB for stability runs.

### 2026-10-04: power supply, edge connector, daughterboard (again)

- **The pico PSU was the cause of two A500 faults.** Both A500s had dead Amiga-to-PC serial and
  distorted audio. Pico supplies have a weak or absent −12 V rail, and both the MC1488 RS-232 driver
  and the LF347 audio filter need it. A full ATX PSU fixed both faults on both machines. The Paula
  swaps we had tried were red herrings.
- **The loss of autoconfig after closing the case** was caused by a dirty A500 edge connector.
- After the card was moved between A500s, the **UA3 daughterboard had unseated a third time.** The RAM
  looked "dead": the machine only booted with DIP-2 off. Reseating fixed it.
- Speedball 2 from a copy of the same CF runs fine in Amiberry, so the crash is a real-hardware fault.
  We wrote **`amiga-tools/rhstress/`**: WHDLoad-like copies from fast RAM to chip RAM with `movem`, then
  verification, with an error table and per-bit/per-bank summary on the console and over polled serial.
- The spare A500 boots a Workbench 1.3 CF built for KS1.3. Amiberry, not fs-uae, is the working
  RocHard autoboot testbed.

### 2026-10-05: the lost-writes burst, and the end of the refresh theory

- We wrote **`amiga-tools/marchu/`**: March U (13N) over 6 data backgrounds, for fast RAM or, with `c`,
  the largest chip block. A self-test build caught an injected bit flip at the right address.
- An overnight rhstress run (`captures/rhstress_overnight_pass10_lostwrites.log`) completed
  **249 passes with one burst of errors in pass 10**: 33 consecutive longwords at
  `$376DD8-$376E58`.
- Every bad value equalled the **previous pass's** pattern for the same address. So the writes were
  acknowledged with DTACK but never stored. The data that was there was retained: no decay and no
  aliasing.
- That rules out refresh or retention, so the runt-refresh theory is not supported. It points instead
  to an intermittent drop-out on the write path, and with this card's history, that means the UA3
  daughterboard contact.
- Pressing the daughterboard down had already been needed to get the machine to boot. Reseating and
  securing it mechanically cleared the errors.

### October: mechanical

- We designed a 3D-printed faceplate (`mechanical/cf-faceplate/`) that mounts the CF adapter, upside
  down, behind the A500's unused external D-sub opening, screwed through the D-sub holes.
- Two earlier designs were abandoned: a plate in the drive position (`mechanical/cf-bracket/`) and
  L-brackets (`mechanical/dsub-bracket/`).

### State at the time of writing

| item | state |
|---|---|
| UA6 | `gal/ua6/ua6_ram6.jed` (0x9365): two-board autoconfig, RAM board first (mfr 2144, product 2), then the HD controller |
| UA3b | `gal/ua3b/ua3b_rebuild8.jed` (0xC824): DRAM controller rebuilt from LA captures |
| UA4, U11, U12, U13, U14 | originals, unmodified |
| HD | autoboots Workbench (OS 3.1.4 CF; also a WB 1.3 CF for a KS1.3 A500) |
| RAM | 2 MB stable; 4 MB (SIMM0-3, JPA1 = 4M) working; long-run verification ongoing. SIMM4 is left empty because of its socket. |
| 8 MB | not yet tested (needs the SIMM4 socket) |
| SCSI | untested |

---

## Lessons learned

- **Physical faults look like logic faults.** The biggest time sinks were not logic:
  - an unseated UA3 daughterboard (at least three false hunts, plus the lost writes)
  - a bridged SIMM socket contact
  - a detached factory bodge wire
  - an open resistor
  - an unplugged Game switch
  - a dirty edge connector
  - a power supply with no −12 V

  Before deriving equations, reseat the sockets, meter the passives end to end, and check the rails.
- **A LA channel with 0 transitions is a dead clip until proven otherwise.** This bit us at least six
  times: `CFGD13`, `/UA3B8` three times, `AB1`/`AB5`, swapped wires on two channels, and `/BASE_C`
  clipped one pin over on `/_RAMCE`. Before trusting any capture, free-run it and confirm that every
  channel toggles. For a signal that really is static, probe the source end as well.
- **A completely static trace after the trigger means a part is missing, not that the CPU hung.** A
  hung 68000 still leaves the DRAM controller refreshing. If refresh stops as well, look for a missing
  part, such as an unseated board.
- **Measure before changing timing.** UA3b rev 9 "fixed" a precharge problem that had never been
  measured, and broke a row-address hold time that had never been noticed. One 100 MSa/s capture
  settled both.
- **A meter across a component does not test its solder joints.** For a suspected open circuit,
  measure the whole path end to end. With the load removed, both sides of a series element must sit at
  the same voltage.
- **A deterministic result does not prove a chip is healthy, and a static sweep cannot see internal
  state.** The UA6 sweep was repeatable and empty; UA6's real job most likely lives in internal
  feedback on unconnected pads.
- **The bench programmer perturbs feedback logic.** minipro's two-pass Hi-Z detection drives values
  into a GAL's feedback paths. For latch-based designs, the system's own behaviour, captured in
  circuit, is the only trustworthy reference.
- **Design rule for this card's GALs:** an access term may only key off a signal that unrelated
  traffic (refresh, per-cycle strobes such as `/BASE_A`) cannot leave asserted. Every self-hold must
  depend on nothing external except reset.
- **Diff GAL revisions against the chip that is actually fitted,** not against whatever revision it was
  derived from. When the chips are unlabelled, identify them by fuse readback.
- **Don't build on n = 1.** The AB5 "signature" was a coincidence of one sample.
- **The schematic was a reconstruction with errors.** Among them: U9's part type, RN2's common, UA4
  pin 16's label, the undrawn `/G` on UA1/UA2, the SIMM DQ lines, DIP-3 and the `/ABEN` bodge. When
  the schematic disagrees with continuity, a decoded fuse map or the user manual, trust those over the
  schematic.
- **Read the full data, not the summary line.** DiagROM's one-line board summary misreported the
  product; the full autoconfig buffer was correct.
- **When something only fails sometimes, ask what persists across resets.** Several "intermittent"
  faults were mechanical contacts that changed every time a chip was reseated.
