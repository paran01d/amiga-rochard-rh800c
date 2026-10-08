# UA3b: replacement DRAM controller

**Use [`ua3b_rebuild8.jed`](ua3b_rebuild8.jed) (fuse checksum `0xC824`)**, built from [`ua3b_rebuild8.pld`](ua3b_rebuild8.pld). It's a GAL22V10 that goes in the UA3b socket on the **UA3 daughterboard**.

UA3b generates `_RAMRAS`, the four bank CAS lines (`_RAMCAS0-3`), `SIMMA8/9`, the row/column select and output enable for the 74LS158 address muxes (UA1/UA2), and `/_UA3SEL`, which enables U11's DTACK for RAM cycles.

## Why it was rebuilt

The original chip was read-protected and had a fault: its access path required A17 = 1, so only alternate 128 KB blocks (those with A17 = 1) could be reached, and any A17 = 0 access hung the CPU. We couldn't read it with Galdurino, and a TL866 sweep couldn't characterise it either. Its outputs are feedback latches, and the tester disturbs them while measuring. So we captured the original's behaviour in circuit with a logic analyser and wrote a new design:

- **Measured from the original:** row/column address mapping, bank-to-CAS decode, mux timing, `_UA3SEL` timing, CAS and RAS widths.
- **Our own design:** the CBR refresh scheme and the RAS/CAS sequencing inside the access window.

All macrocells are combinatorial, with self-holding latches, like the original. Pin 1 is AB17, so registered macrocells aren't available. The `.pld` header separates what was **measured** from what was **designed**. Read it before you change anything.

## Revisions

| Rev | Status |
|-----|--------|
| **8** (`0xC824`) | **Keeper.** Stable at 2 MB and 4 MB. Measured row-address hold (tRAH) is 60 ns. |
| 9 (`0xC81C`, `history/`) | **Harmful. Don't use.** An attempted RAS-precharge "fix" that cut tRAH to 10 ns, below the DRAM minimum. It turned out that rev 8's `/CDAC`-armed mux was what provided the hold. See [`../../captures/`](../../captures/). |
| 1-7 (`history/`) | Bring-up history. Revs 1-3 used pin 23 as internal state. It actually drives the '158 mux enable, a trace the schematic doesn't show, so every address in a block aliased to one cell. Rev 7 was the first build with working long accesses. |

## Seat the daughterboard properly

On this card, most apparent "RAM logic" faults turned out to be a **poorly seated UA3 daughterboard**: it wouldn't boot with RAM enabled, the RAM was reported "defective", and writes were intermittently lost. If RAM suddenly fails, reseat UA3 first, and secure it mechanically.

Build with `make ua3b/ua3b_rebuild8.jed` from [`..`](../).
