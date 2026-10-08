# A500 1 MB chip RAM upgrade (rev 5 board, jumperless trapdoor card)

This is the **Amiga-side** work we did alongside the RocHard: turning the A500's
512 KB trapdoor RAM into **chip RAM**, for 1 MB chip in total. The RocHard
doesn't need it. We did it because many WHDLoad installs need more than 512 KB
of chip RAM (see [WHDLoad notes](ide-and-disk-images.md#whdload-notes)).

Our setup was a little unusual, and the common guides don't cover all of it:

| | |
|---|---|
| Motherboard | **A500 rev 5** (most guides describe rev 6A) |
| Trapdoor card | **Sordan mini** 512 KB card, which has **no chip/slow (`_EXRAM`) jumper** |
| Agnus fitted | **8372A** "Fat Agnus", part **318069-02**, in a new PLCC84 socket |
| Reference | The **A500 rev 6 schematic** (we found nothing equivalent for rev 5; signal names and functions carry over, pad locations may not) |

> ⚠️ This involves cutting and soldering on the motherboard. Read the
> [sources](#sources) and check your own board revision first. What follows is
> what worked on **our** rev 5 board.

---

## What has to change

The trapdoor RAM shows up as "slow" RAM at `$C00000` by default. To make it chip
RAM at `$080000`, three things are needed:

1. **An Agnus that can address 1 MB.** The original 8371 cannot. The 8372A can.
2. **JP2** moved so that Agnus's extra address line (A19 side) reaches the RAM.
3. **The trapdoor card must stop appearing at `$C00000`.** Most cards have a
   jumper for this. Ours did not, so we **isolated Gary pin 32 (`_EXRAM`)**.

### 1. Fit the 8372A Agnus

The Agnus is a PLCC84 chip in a socket. Use a proper PLCC extraction tool.

**PAL/NTSC: pin 41.** On the 8372A, pin 41 selects the video standard:
**grounded = NTSC**, otherwise PAL. Check what pin 41's pad does on your
board before fitting. On **our rev 5 board it was not grounded**, so the
machine stayed PAL. On some boards the pad is tied to ground, and you have to
lift or cut it to keep PAL (or the reverse, if you want NTSC).

**Finding pin 41 on a PLCC84.** PLCC pin 1 is in the **middle** of the side with
the bevelled corner or dot. Pins count **anticlockwise** looking down on the
chip, 21 pins per side. So pins 1-11 run from the centre of the pin-1 side to
its corner, 12-32 run down the next side, and pin 41 is the 9th pin along the
third side (33-53). Check this against the socket's own moulded numbering and
the schematic before you cut or solder anything. Counting from the wrong
corner is easy.

### 2. JP2: centre pad to the A19 side

JP2 decides whether the RAM sees the extra Agnus address line. Bridge JP2's
**centre pad to the A19 side** and cut the original link to the other side. On
rev 6A the usual instruction is "cut 2-3, bridge 1-2". On rev 5, confirm with
continuity and the schematic which outer pad is the A19 side rather than
trusting the pad numbers.

### 3. Isolate Gary pin 32 (`_EXRAM`)

Normally the trapdoor card has a jumper that tells Gary the RAM is not at
`$C00000` any more. **The Sordan mini card has none.** Without it, Gary still
decodes the trapdoor RAM at `$C00000`, while Agnus now addresses the **same
512 KB** at `$080000` as chip RAM. The machine gave a **black screen** at power-on.

The fix was to **isolate Gary pin 32 (`_EXRAM`)** so the trapdoor signal no
longer reaches Gary. After that we had a solid 1 MB of chip RAM and no slow
RAM, and the Amiga Test Kit booted and reported it correctly.

> We had first advised *against* cutting the rev 5 equivalent of the JP7A
> trace. **That advice was wrong for a jumperless trapdoor card.** Something
> has to stop `_EXRAM` reaching Gary, either a jumper on the card or isolating
> it on the motherboard.

---

## How it fits with the RocHard and WHDLoad

- After the upgrade the machine has 1 MB chip, 0 slow, plus the RocHard's
  fast RAM (2 or 4 MB in our case). Before it, ATK showed Chip 0.5 /
  Fast 4 / Slow 0.5.
- **WHDLoad** loads games into chip RAM (the slave's `BaseMem`). Many installs
  need more than 512 KB, so before the upgrade they could not run at all.
  [`whdmem.py`](../disk-image/whdmem.py) tells you which ones.
- The RocHard's fast RAM is still useful to WHDLoad for preloading and
  "extra" memory (`ExpMem`).

---

## Sources

We worked from these. All describe related but not identical setups, mostly
rev 6A boards:

- **Lyon's Den**, A500 1 MB chip RAM article: <https://lyonsden.net/upgrade-amiga-a500-1mb-chip-ram/>
- **one-n.co.uk Amiga guides**, "A500 rev 6A JP2 and JP7A":
  <https://sites.google.com/one-n.co.uk/amiga-guides/a500-rev-6a-jp2-and-jp7a>
- **English Amiga Board** thread 72673:
  <https://eab.abime.net/showthread.php?t=72673>
- **RetroNerd**, A500 1 MB chip mod: <https://retronerd.co.uk/commodore-amiga-500-1mb-chip-ram-mod/>
- **AmiBay**, forum thread on 8372A PAL/NTSC selection (pin 41):
  <https://www.amibay.com/showthread.php?45118-How-to-boot-A500-PAL-NTSC=>
- **Commodore A500 rev 6 schematic**, used as our wiring reference.

