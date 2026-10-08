# RAM subsystem

The RH800C carries up to **8 MB of Zorro II fast RAM** in eight 30-pin SIMM
sockets. The card arrived with its RAM unusable. This page describes how the
RAM path works, the original DRAM-controller bug, how we rebuilt that
controller from logic-analyser captures, and where things stand now.

How the RAM is announced to the OS (our rebuilt UA6 and the second autoconfig
board) is covered in [Autoconfig](autoconfig.md). The chips are listed in the
[Hardware overview](hardware-overview.md).

**Status (October 2026):** 2 MB is stable. 4 MB (SIMM0-3, JPA1 = 4M) works
and passes ATK memory tests. Long-run verification under load is still going.
The 8 MB configuration has never been tested.

---

## Organisation

Each bank is a **pair** of 1 MB x8 SIMMs forming one 16-bit word. One SIMM in
each pair is the upper byte lane, the other the lower, selected by the write
enables `_SIMMWEU` / `_SIMMWEL`. All banks share RAS, SIMMA0-9 and the write
enables; each bank has its own CAS.

| Bank | Address range | SIMMs | CAS | (A23,A22,A21) |
|---|---|---|---|---|
| 0 | `$200000`-`$3FFFFF` | SIMM0 / SIMM1 | `_RAMCAS0` (UA3b pin 18) | 001 |
| 1 | `$400000`-`$5FFFFF` | SIMM2 / SIMM3 | `_RAMCAS1` (pin 17) | 010 |
| 2 | `$600000`-`$7FFFFF` | SIMM4 / SIMM5 | `_RAMCAS2` (pin 16) | 011 |
| 3 | `$800000`-`$9FFFFF` | SIMM6 / SIMM7 | `_RAMCAS3` (pin 15) | 100 |

**bank = (A23,A22,A21) − 1.** JPA1 sets how many banks UA4 decodes:
2M = bank 0, 4M = banks 0-1, 8M = banks 0-3.

Useful 30-pin SIMM socket pins for probing (empty sockets are easiest): pin 2 =
CAS, pin 17 = SIMMA8, pin 18 = SIMMA9, pin 27 = RAS.

### Signal path for one access

```
 CPU address --> UA4: is it in the RAM window? (base latch + JPA1 strap + AB21-23)
                   |  /GALCLK1 (low for the whole ~640 ns access window)
                   v
                 UA3b (DRAM controller, on the UA3 daughterboard)
                   |-- MUXEN (pin 23) ---------> /G of UA1, UA2 (74LS158)
                   |-- UA3B8 (pin 22) ---------> row/column select of UA1, UA2
                   |                               UA1/UA2 --> SIMMA0-7 (inverted)
                   |-- UA3B7/UA3B6 --UA3a '244--> SIMMA8 / SIMMA9
                   |-- UA3B5      --UA3a '244--> _RAMRAS (all banks)
                   |-- UA3B4..1   --UA3a '244--> _RAMCAS0..3 (one per bank)
                   '-- _UA3SEL (pin 14) -------> U11 pin 17 = output enable of U11's DTACK driver
 Data: SIMM DQ <--> /DB0-15 <--> U1/U2 '245 (enables /_U1CE, /_RAMCE from U11) <--> CPU
```

The whole SIMM address bus is **inverted**: UA3b outputs the inverse address
bit, and the 74LS158s invert too. That is harmless for DRAM, which only needs
a consistent mapping.

There is a quirk in the UA3b pinout. **Pin 1, the GAL22V10's dedicated clock
pin, is wired to AB17.** The design is therefore purely combinatorial: it
holds state in self-holding feedback latches, never in registered macrocells.
UA4 and U11 use the same construct.

---

## The original fault: UA3b only worked when A17 = 1

With the RAM window mapped at `$200000`, accesses hung the CPU at some
addresses and worked at others. A 128 KB block map gave the answer:

| Block | Range | A18 | A17 | Result |
|---|---|---|---|---|
| 0 | `$200000`-`$21FFFF` | 0 | 0 | Hang |
| 1 | `$220000`-`$23FFFF` | 0 | 1 | Works |
| 2 | `$240000`-`$25FFFF` | 1 | 0 | Hang |
| 3 | `$260000`-`$27FFFF` | 1 | 1 | Works |

**A17 alone decided it**, uniformly across all four banks. A capture with
A17 = 0 showed that UA3b **never started the cycle**: there was no mux switch,
no RAS, no CAS and no `_UA3SEL`, so U11 never drove DTACK. Meanwhile refresh
carried on normally. With the chip pulled and tested on a TL866, `_UA3SEL`
could only go low with AB17 = 1.

This also explained an earlier puzzle. ATK's direct memory **detection**
probes an address with A17 set, so it found the RAM, while its **test**
started at absolute `$200000` (A17 = 0) and died at once.

The original UA3b is **read-protected**. A normal read returns almost no
fuses, and our Galdurino cracking attempts failed. We could not copy it, and
tying pin 1 high would not have fixed it: A17 is also a SIMM address bit
(SIMMA8 column), so the two halves would have aliased. The only fix was to
**rebuild UA3b from its observed behaviour**.

A TL866 black-box sweep could not do this either. Every output depends on
previous state (feedback latches), and the programmer drives the output pins
to classify Hi-Z, which corrupts that feedback. We therefore captured only
the cycles the real system produces (accesses and refresh), **in circuit**
with a 16-channel logic analyser.

---

## The UA3b rebuild

### What was measured (treat as fixed)

These came from captures at many addresses, with A17 = 1 so the original chip
still worked:

- **SIMMA8 / SIMMA9 pairing rule.** Each line multiplexes an **adjacent pair**
  of address bits, inverted. The row phase takes the higher bit and the
  column phase the lower:

  | Line | Row (UA3B8 high) | Column (UA3B8 low) |
  |---|---|---|
  | SIMMA8 | `/A18` | `/A17` |
  | SIMMA9 | `/A20` | `/A19` |

  SIMMA8's column value could not be observed directly, since it needs
  A17 = 0, where the old chip did nothing. The pairing rule leaves only one
  candidate, and it agrees with every measurement.
- **Bank/CAS decode:** `(A23,A22,A21) − 1`. Most of this was measured by
  setting JPA1 to 8M with only bank 0 fitted. Accesses to empty banks then
  complete (DTACK comes from UA3b, not from the RAM) and return garbage
  instead of hanging, so CAS1-3 become observable.
- **Original timing:** access window (`/GALCLK1` low) 620-640 ns. Mux to
  column at +80 ns, back to row at +440 ns. `_UA3SEL` low +400..+640 ns.
  Refresh CAS pulse 100 ns, refresh RAS pulse 280-300 ns.
- **Refresh is CAS-before-RAS (CBR)** and drives **all four CAS lines**
  together. It runs continuously, in bursts, interleaved with accesses.

### What was designed (not copied)

The original's refresh cadence and intra-cycle sequencing could not be
separated from the captures, so we designed our own. Any CBR scheme that meets
the DRAM retention spec is valid. The final sequencer, paced by `_CDAC`:

```
MUXEN -> RAS -> UA3B8 (column) -> CAS -> _UA3SEL (DTACK)      all released when /GALCLK1 rises
```

From [`ua3b_rebuild8.pld`](../gal/ua3b/ua3b_rebuild8.pld):

```
/MUXEN.T = /GALCLK & /CDAC                 ; enable the '158 muxes; arm the access
         + /GALCLK & /MUXEN
/UA3B5.T = /GALCLK & /MUXEN                ; access RAS
         + GALCLK & /CCKQ                  ; refresh RAS (~140 ns, starts 70 ns after CAS)
/UA3B8.T = /GALCLK & /MUXEN & /UA3B5 & CDAC
         + /GALCLK & /UA3B8                ; switch to column one CDAC phase after RAS
/UA3B4.T = /GALCLK & /UA3B8 & /CDAC & /AB23 & /AB22 & AB21   ; bank 0 CAS (access)
         + /GALCLK & /UA3B8 & /UA3B4 & /AB23 & /AB22 & AB21
         + GALCLK & /CCK                                     ; refresh CAS (all banks)
/UA3B7.T = UA3B8 & AB18 + /UA3B8 & AB17    ; SIMMA8 (measured)
/UA3B6.T = UA3B8 & AB20 + /UA3B8 & AB19    ; SIMMA9 (measured)
```

The fix itself is that **AB17 appears in exactly one place**, SIMMA8's column
term. Nothing in the access path depends on it.

The design rule that took several revisions to learn:

> **An access term may only key off a signal that refresh cannot leave
> asserted.** Refresh drives RAS and all four CAS lines. Any access term keyed
> off them can be satisfied by a refresh that happens to be in progress when
> the access starts. Only `MUXEN` and `UA3B8` are guaranteed released while
> `/GALCLK1` is high.

### Revision ledger

All builds are in [`../gal/ua3b/`](../gal/ua3b/); superseded ones are in
[`history/`](../gal/ua3b/history/).

| Rev | Fuse | Change | Outcome |
|---|---|---|---|
| 1 | 0xA821 | First reconstruction. AB17 used only for SIMMA8 | `$200000` answers for the first time. Hidden faults remained |
| 2 | | RAS made a sequencer stage instead of a copy of `/GALCLK` | RAS's self-hold latched a refresh-asserted RAS: no precharge, no new row |
| 3 | | RAS self-hold removed, precharge flag on pin 23 | Pin 23 is really the UA1/UA2 `/G` enable (not drawn in the schematic), so SIMMA0-7 never varied and addresses aliased within 128 KB |
| 4 | | Pin 23 became `MUXEN` (mux enable, which also gates RAS) | Aliasing fixed |
| 5 | | DTACK one CDAC phase after CAS, not on the same edge | Data-valid margin for tCAC + buffer delay |
| 6 | | CAS hold terms qualified with `/UA3B8` | A refresh-asserted CAS no longer swallows the column strobe |
| 7 | 0xC7F3 | `_UA3SEL` keyed only off refresh-proof signals | Long (`move.l`) accesses correct, no aliasing |
| **8** | **0xC824** | **Refresh RAS widened from ~70 ns (`/CCK & /CDAC`) to ~140 ns (`/CCKQ`)** | **ATK "Test All Memory" passes. The keeper.** |
| 9 | 0xC81C | `MUXEN` armed on `CCKQ & /CCK` to guarantee RAS precharge after refresh | **Harmful, reverted.** See below |

**Rev 7 to 8 (refresh strength).** A 70 ns refresh RAS sits right at the
SIMMs' tRAS minimum. Most cells held, but some did not. The signature was a
**single bit decaying within seconds**, for example `$200002` read `1234` and
then `1A34`, plus ATK failing the check pass after a clean fill. Driving
refresh RAS from `/CCKQ` doubles the pulse and keeps CAS-before-RAS ordering.

**Rev 9 (and why it was reverted).** We reasoned that an access RAS could
start immediately after a refresh RAS, leaving no precharge time, and rev 9
moved `MUXEN` arming into a fixed post-refresh window:

```
rev 8   /MUXEN.T = /GALCLK & /CDAC       + /GALCLK & /MUXEN
rev 9   /MUXEN.T = /GALCLK & CCKQ & /CCK + /GALCLK & /MUXEN
```

We then measured rev 9 at 100 MSa/s ([`../captures/roctec_write_cdac100.csv`](../captures/roctec_write_cdac100.csv),
channels `_RAMRAS`, `GALCLK1`, `SIMMA0`). RAS fell at +640 ns and the row
address changed at +650 ns, so **the row-address hold time tRAH was 10 ns**.
These DRAMs need about 15-20 ns minimum. Rev 8's `/CDAC` arming had been
silently providing that hold time: RAS falls while CDAC is low, and the column
switch must wait for CDAC to go high. Rev 9 lost that relationship.

The same capture of rev 8 ([`../captures/roctec_write_cdac1002.csv`](../captures/roctec_write_cdac1002.csv))
shows **tRAH = 60 ns**. Rev 8 went back in. The lesson: rev 9 fixed a timing
problem we had never measured and broke one we had never noticed. Measure
before changing timing.

> **Known open question, not a confirmed fault.** In rev 8 the refresh
> RAS/CAS terms have no hold, so the start of an access can cut a refresh
> pulse short. The same rev 8 capture shows one truncated ("runt") refresh
> RAS. For a while we suspected this caused the RAM errors under load, and we
> sketched a "rev 10" with uninterruptible refresh. **That theory was never
> confirmed.** The errors turned out to be lost writes from a poorly seated
> UA3 daughterboard (below). Rev 10 stays unwritten unless errors return.

---

## Physical faults that looked like logic faults

### The UA3 daughterboard (the big one)

UA3b and UA3a sit on a small piggyback board in the UA3 socket. When it was
not fully seated we saw, at different times:

- `_UA3SEL` stuck high, which we misread as "the chip is dead";
- a logic-analyser trace that went **completely static** after the first RAM
  access. A CPU waiting forever for DTACK still leaves UA3b refreshing, so
  *no refresh at all* means UA3b is not connected;
- the RAM board marked "defective", or the machine refusing to boot with
  DIP-2 ON;
- **intermittent lost writes** (below).

### The rhstress finding: lost writes, not decay

An overnight run of `rhstress` (bank 0, 2 MB) logged **249 passes with one
burst of errors in pass 10**: 33 consecutive longwords at
`$376DD8`-`$376E58`. The copy check and the in-place check agreed. That gives
66 error lines in the log,
[`../captures/rhstress_overnight_pass10_lostwrites.log`](../captures/rhstress_overnight_pass10_lostwrites.log).

Decoding the bad values showed that **every bad longword held pass 9's
pattern for that same address**. So the pass-10 fill writes to those
addresses were silently lost: the CPU got DTACK, but nothing was stored. The
old data was intact. There was no decay, no single-bit pattern and no
aliasing, so the cause was not refresh or retention. It pointed at an
intermittent write-path dropout. When the card next refused to boot with
RAM, **pressing the UA3 daughterboard down fixed it**. Reseating and securing
it fixed the intermittent errors.

### Other physical faults

- **SIMM4 socket bridge.** Pin 12 (SIMMA5) shorted to pin 13 (DQ3 = `/DB3`).
  This corrupted ROM reads (bit 3). Because the bridge sits on the data bus,
  it may also explain some of the earlier RAM "instability"; we did not
  confirm that. SIMM4 is left empty, which limits our card to 4 MB unless the
  socket is replaced.

---

## Test tools

| Tool | What it does |
|---|---|
| **rhmon** ([`../amiga-tools/rhmon/`](../amiga-tools/rhmon/)) | A serial monitor in a 1024-byte bootblock. `r`/`w` (word), `l`/`W` (long), `t` (write/read-back test). Use it with `ua6_hd_b001d` fitted to poke `$200000` without Kickstart testing the RAM first. `t` touches only one address pair, so it cannot detect aliasing. Always check that two *different* addresses hold *different* values (e.g. `w 200000 1111; w 200004 2222; r 200000`). |
| **rhstress** ([`../amiga-tools/rhstress/`](../amiga-tools/rhstress/)) | WHDLoad-like stress test. It fills fast RAM with an address-dependent pattern, then copies it to chip RAM in `movem.l` bursts and verifies, re-verifies in place and changes the seed each pass. Prints errors live to the console and to polled serial (9600 baud), with per-bit and per-bank summaries. Stop with Ctrl-C or the left mouse button. |
| **marchu** ([`../amiga-tools/marchu/`](../amiga-tools/marchu/)) | March U (13N) over 6 data backgrounds. `c` tests the largest chip-RAM block instead. A fault-injection build, run in an emulator, confirmed that it reports an injected single-bit flip at the right address. |
| **rhmemtest** ([`../amiga-tools/rhmemtest/`](../amiga-tools/rhmemtest/)) | Simple serial-logged sweep of the RAM region. |
| **ATK** (Amiga Test Kit) | `F1` "Test All Memory" was the acceptance test the card failed from the start. ATK's 32-bit error display maps onto the two word cycles of a `move.l` on this 16-bit card: D31-D16 is the first cycle and D15-D0 the second. |
| **DiagROM** | Shows the full autoconfig buffer and runs fast-RAM tests. |

> **Emulators do not help here.** WinUAE/Amiberry emulate the RocHard's ROM and
> IDE side, but they present generic fast RAM. They do not model the card's
> DRAM controller.

### Logic-analyser tips from this work

- Our 16-channel analyser drops to 16 MSa/s with all channels on. Turn
  channels off to get 25 / 32 / 50 / 100 MSa/s. DRAM timing (tRAH, tRP) needs
  the 100 MSa/s, 3-channel setup.
- Trigger on `/GALCLK1` falling (UA4 pin 19 or U14 pin 1) with 20-50 %
  pre-trigger. That catches refresh as well as the access.
- **A channel with 0 transitions is a dead probe until proven otherwise.**
  The UA1/UA2 pin 1 (`UA3B8`) clip gave a false "stuck low" reading three
  times. U11 pins 21 (`/BASE_C`) and 22 (`/_RAMCE`) are easy to confuse.
  The R1-R7 resistor pack sits under the daughterboard and cannot be reached.

---

## Working configuration

| Part | Build | Fuse |
|---|---|---|
| UA6 | [`ua6_ram6`](../gal/ua6/ua6_ram6.pld) | 0x9365 |
| UA3b | [`ua3b_rebuild8`](../gal/ua3b/ua3b_rebuild8.pld) | 0xC824 |
| UA4, U11, U12, U13, U14 | originals, unmodified | |

- SW1 = II, DIP-1 ON, DIP-2 ON.
- **2 MB:** SIMM0 + SIMM1, JPA1 = 2M. Stable.
- **4 MB:** SIMM0-SIMM3, JPA1 = 4M. Workbench and ATK see 4 MB fast and ATK
  passes. This configuration was the first ever use of bank 1's CAS, UA6's
  `$EF` er_Type and UA4's 4M decode, and all three worked first time.
  Long-run verification is ongoing.
- **8 MB:** untested. It needs SIMM4, which is unusable on our card.
- **Seat the UA3 daughterboard firmly and secure it.** If the RAM suddenly
  "dies" after the card has been moved, reseat it first.

### Open items

- Long-run stability at 4 MB under real load. Earlier we saw an ATK error in
  the top 512 KB of bank 1 and a WHDLoad *Speedball 2* crash on hardware (the
  same install runs in Amiberry). Both happened during the period when the
  UA3 daughterboard was badly seated, and neither has been reproduced since.
- The 8 MB strap, banks 2-3 and UA6's 8M er_Type have never been exercised.
