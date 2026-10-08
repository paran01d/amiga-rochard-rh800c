# Troubleshooting

This page lists every fault we found while restoring an RH800C. The main lesson
first:

> **Most of our "logic" faults were physical.** An unseated daughterboard, a
> bridging SIMM-socket contact, a detached factory bodge wire, an open resistor,
> a dirty edge connector, a weak −12 V rail. Each one looked like a GAL or
> design problem at first, and several cost us weeks. **Check the mechanical and
> electrical basics before suspecting the logic.**

Related pages: [hardware overview](hardware-overview.md) ·
[IDE and disk images](ide-and-disk-images.md) ·
[schematic corrections](schematic-corrections.md) ·
[RAM subsystem](ram-subsystem.md)

---

## First checks

Go through these before anything else, and again whenever the card "suddenly"
stops working:

- [ ] **UA3 daughterboard fully seated.** Press it down firmly. This is the most common fault by far.
- [ ] **Game switch (SW1) plugged in and in position II** (HD + RAM enabled). Unplugged is the same as position O, which disables everything.
- [ ] **DIP switches.** DIP-1 = HD (ON = enabled; the card does not autoconfig at all with DIP-1 OFF). DIP-2 = RAM (ON = enabled). DIP-3 = Kickstart (OFF = 1.3+, autoboot ROM half; ON = 1.2, non-autoboot half).
- [ ] **JPA1 matches the fitted SIMMs** (2M / 4M / 8M). Start with **DIP-2 OFF and no SIMMs** to get the HD side working on its own. The manual says the card needs no RAM.
- [ ] **A500 edge connector clean**, and the card fully engaged on it.
- [ ] **Power supply has a real −12 V rail.** Pico PSUs often don't.
- [ ] **SIMM sockets: no bent or bridging contacts**, especially in any socket you have been swapping modules in.
- [ ] **Factory bodge wires intact.** On our board one wire runs from U6 pin 2 (`/ABEN`) to RA4 pin 7.
- [ ] **Logic rail about 5 V at the chips** (we measured 4.84 V, which is fine). The card has its own power input, separate from the Amiga.
- [ ] **No clone GALs left in sockets by mistake.** Label every chip you burn.

---

## Symptom → cause → fix

| Symptom | Cause we found | Fix |
|---|---|---|
| RAM "dead": boots only with DIP-2 OFF, DiagROM fast-RAM test goes to a black screen, logic-analyser trace goes completely static after the first `$200000` access | **UA3 daughterboard not seated** | Reseat it and secure it (see [below](#ua3-daughterboard-seating)) |
| Intermittent RAM errors: a burst of consecutive longwords holds the **previous pass's** pattern | **UA3 daughterboard contact** again: writes are acknowledged but not stored | Reseat and secure UA3 |
| Card autoconfigs (DiagROM shows the board) but **black screen at autoboot**. Booting with DIP-3 set to KS 1.2 works | **ROM data bit 3 stuck high**: a SIMM socket contact bridge held `/DB3` at about 4 V | Straighten the socket contacts (see [below](#simm-socket-contact-bridge-on-db3)) |
| DiagROM shows `er_Type` **C1** ("AutoBoot: No") even with DIP-3 set to 1.3. The card configures but never autoboots | **Detached factory bodge wire** on `/ABEN` (ROM A12) | Resolder U6 pin 2 → RA4 pin 7 (see [below](#detached-aben-bodge-wire)) |
| No autoconfig at all. ROM never enabled | **R21 open** (marked "RC" on the board; U14 pin 15 → ROM `/OE`). Measured 4.5 kΩ | Replace it. Ours is now 10 Ω 1 % |
| No autoconfig at all, whatever logic is fitted | **Game switch unplugged**. Its pull-ups make that equal to position O (HD + RAM disabled) | Plug it in and set position II |
| Autoconfig stopped after the case was reassembled or the card was moved | **Dirty A500 edge connector** | Clean the contacts |
| Autoconfig fails after swapping GALs. The ROM `/OE` behaves backwards | A **clone U14 with inverted `/_ROMOE` polarity** was left in the socket | Fit the original U14. A read-protected U14 is almost certainly the original |
| Amiga→PC serial dead **and** distorted audio, on more than one A500 | **Pico PSU with a weak or missing −12 V.** The MC1488 RS-232 driver and the LF347 audio filter both need −12 V | Use a full ATX (or original) PSU. Swapping Paula didn't help |
| Disk mounts by hand (`rt.device` unit 0) but never autoboots | Disk image problem: RDB has no DriveInit driver or no `$d4` marker | See [IDE and disk images](ide-and-disk-images.md#what-the-boot-rom-needs-to-autoboot) |
| RDB written on Linux is never found. Sector 0 reads `DRKS` | The card byte-swaps IDE data | `dd conv=swab` the image ([details](ide-and-disk-images.md#the-byte-swap)) |
| Half the IDENTIFY model string is `ÿ` (every other byte `$FF`), wrong capacity | Dead high-byte IDE buffer U7 (74LS245). An LA showed both sides stuck high while enabled | Replace U7 |
| RocHard formatter: "Could not save partition information / try different parameters", or it aborts on a large disk | Unresolved on real hardware (the formatter is CHS-only and runs out of memory on large disks) | Build the disk on Linux with `mkrochard.py`. In an emulator, only format small (~128 MB) disks |
| `Echo` to `SER:` does nothing, or `AUX:` fails, on Workbench 1.3 | Shell quirks, not hardware | See [below](#workbench-13-serial-shell-quirks) |

---

## UA3 daughterboard seating

UA3 is a small daughterboard that carries the DRAM controller GAL (UA3b). Its
socket contact is poor, and it **came unseated at least three times**: twice
while we were working on the card and once after moving the card between two
A500s. It caused:

- RAM reported as defective, or the machine not booting with RAM enabled;
- at least three false "logic fault" investigations (a GAL "dead", a mux select
  "stuck", RAM "defective");
- the intermittent RAM errors. Our `rhstress` tool found a burst of 33
  consecutive longwords whose **writes were lost**: they still held the previous
  pass's pattern, with no decay and no aliasing. Pressing the board down fixed
  booting. Reseating and securing it fixed the errors.

How to recognise it on a logic analyser: a **hung 68000 still leaves UA3b
refreshing the DRAM.** If RAS/CAS stop completely after the trigger, UA3b is not
in circuit, so the daughterboard is unseated. If the CPU has stalled but RAS/CAS
keep toggling, you have a real missing-DTACK hang.

**Fix:** reseat it, then hold it in mechanically (a strap or tie, or a
turned-pin socket). Reseat UA3 first whenever the RAM fails suddenly.

---

## SIMM socket contact bridge on `/DB3`

**Symptom:** with HD enabled and DIP-3 set to 1.3, the card autoconfigured
perfectly (full DiagROM buffer correct) and then the screen went black during
autoboot. With DIP-3 set to KS 1.2 (non-autoboot ROM half) the machine booted
from floppy.

**How we found it:**

1. **rhmon ROM reads.** In KS 1.2 mode we read ROM words over serial and
   compared them with values computed from the ROM dump
   (see [techniques](#rhmon-rom-word-reads)): `r E90080` returned **`9008`**
   instead of `9000`, `r E90084` returned `0078` instead of `0070`, and other
   words such as `r E915E6` = `7FFF` were correct. So **bit 3 was stuck high**.
2. **The ROM itself was fine.** U20 (odd ROM) read correctly out of circuit on a
   programmer: its CRC matched the known dump.
3. **LA capture**, triggered on the data buffer enable while reading `E90080`:
   ROM D3 and `/DB3` went low, but the Amiga-side D3 of U1 (74LS245) was 1.
   That made U1 look guilty.
4. **Scope:** `/DB3` idled at **about 4 V**, while a healthy floating line such
   as `/DB2` sat at about 1.5 V (normal for an undriven LS input). The ROM could
   only pull it down to about 1.4 V, which U1 read as a 1.
5. **Elimination:** we replaced U1 (no change; the old one was fine), cut U8
   pin 5 (the IDE low-byte buffer, also on `/DB3`), removed U20 and U1, and
   disconnected the Amiga. `/DB3` stayed at about 4 V, so the source was on the
   card itself.
6. **The schematic didn't help.** It does not draw the SIMM data pins at all
   (see [schematic corrections](schematic-corrections.md)). On the low-byte-lane
   SIMM sockets, pin 13 (DQ3) connects directly to `/DB3`, and its neighbour,
   pin 12 (SIMMA5), is driven by UA2 pin 9 through a series resistor array.
7. **Continuity and contacts:** the fault was a **bridge between pins 12 and 13
   inside the SIMM4 socket**, not visible by eye. UA2's high output on SIMMA5 was
   holding `/DB3` up. It went open while we were bending and probing the contacts.

**Cause:** worn or bent contacts from swapping SIMMs during the RAM work. The
bridge was present **with no SIMM fitted**. Inserting a module re-bridges it.

**Fix:** straighten the pin 12/13 contacts (Kapton tape helps keep them apart).
We now leave SIMM4 empty. It is in bank 2 (`$600000`), which is only needed for
8 MB. After the fix, `r E90080` read `9000` and autoboot worked once the CF had
been re-imaged. The disk had picked up a checksum error while bit 3 was bad.

---

## Detached `/ABEN` bodge wire

The ROM is split into two 4 KB halves selected by ROM A12 (`/ABEN`):

| `/ABEN` (A12) | Half | DiagROM `er_Type` |
|---|---|---|
| High (pull-up) | Autoboot (KS 1.3+) | **D1** (AutoBoot: Yes) |
| Low (DIP-3 ON) | Non-autoboot (KS 1.2) | **C1** (AutoBoot: No) |

The two halves differ only in word 0.

**Symptom:** DiagROM showed **C1** with DIP-3 set to 1.3, and U6/U20 pin 2
measured low in **both** DIP-3 positions.

**Cause:** on our board, the `/ABEN` pull-up is a **factory bodge wire from U6
pin 2 to RA4 pin 7** (the schematic shows RA4 pin 8). It had come off, probably
from all the probing and clipping on U6.

**Fix:** resolder it and glue or tape it down. DiagROM then showed D1 and the
card autobooted. If your board has the same bodge, check it before anything else
when the card stops offering autoboot.

---

## Other physical faults

- **R21 open** ("RC" on the board, U14 pin 15 `/_ROMOE2` → R21 → ROM `/OE` on U6
  and U20). It measured 4.5 kΩ. Until we replaced it the ROM was never enabled,
  so the card could not present its autoconfig ID. The part now fitted is
  10 Ω 1 % (brown-black-black-gold-brown, measures 9.9 Ω in circuit).
- **Game switch unplugged.** With SW1 disconnected, the pull-ups put the card in
  "HD and RAM disabled". Position II grounds `/_BANK_SEL` (HD + RAM on).
  Position I grounds `/_AUTOBOOT_EN` (HD off, RAM on). Centre = both off.
- **Clone U14 with inverted `/_ROMOE`.** A test clone with the wrong output
  polarity was left in the socket and sent us looking for a fault that wasn't
  there. We later validated the original U14 on a TL866 (1024 vectors,
  0 mismatches against the decoded equations).
- **Dirty A500 edge connector.** After the case was closed up, autoconfig
  disappeared. Cleaning the connector fixed it.
- **Dead U7 (74LS245).** High IDE byte stuck at `$FF`. We replaced it.

---

## Pico PSU and −12 V

Both of our A500s showed **dead Amiga→PC serial and distorted audio** on a pico
PSU. The MC1488 RS-232 line driver (pins 14/1 = +12 V/−12 V) and the LF347 audio
filter op-amp (split ±12 V) both need a proper −12 V. A full ATX PSU fixed both
symptoms on both machines. **We swapped Paula on both machines first, and that
was a red herring.** If serial transmit and audio both go wrong at once, measure
−12 V before replacing chips.

---

## Workbench 1.3 serial-shell quirks

We used a serial shell on Workbench 1.3 for diagnostics. These are software
quirks, not hardware faults:

- **Redirection goes after the command name** in the 1.3 shell:
  `Echo >SER: "hello"` works, `>SER: Echo "hello"` does not.
- **`Type SER:` is block-buffered**, so it shows nothing until a buffer fills,
  and it **holds `serial.device` exclusively**. While it is running (or after it
  is interrupted), opening `AUX:` fails.
- **Use `NewCLI AUX:`** for an interactive serial shell, **after a reboot** so
  nothing else holds `serial.device`. You need `L:Aux-Handler` and to
  `Mount AUX:` first, if your startup does not already do it. On the PC side,
  9600 8N1 (e.g. `picocom -b 9600 /dev/ttyUSB0`).

---

## Diagnostic techniques that worked

### rhmon ROM-word reads

[`rhmon`](../amiga-tools/rhmon) is a 1 KB bootblock serial monitor (9600 8N1):
`r` reads a word, `l` reads a long, `w`/`W` write, `t` runs a RAM test at an
address. Boot it with DIP-3 set to **KS 1.2**, so the card configures without
running its boot code, and read ROM words directly. Compute the expected values
from your own ROM dumps:

```python
even = open('u6_even.bin', 'rb').read()   # 8 KB each
odd  = open('u20_odd.bin', 'rb').read()
def rom_word(offset, a12=0):              # offset = address - board base
    n = offset // 2 + a12 * 0x1000        # a12=0: KS1.2 half (DIP-3 ON)
    return (even[n] << 8) | odd[n]
print(f"{rom_word(0x80):04X}")            # expect 9000 at base+$80
```

A single bit that is always wrong across several words points at one data line.
That is much quicker than taking LA captures.

### DiagROM: read the full autoconfig buffer

DiagROM's one-line board summary misled us once. It showed "2144/0", and we
wrongly concluded a data line was stuck. **Always look at the full autoconfig
buffer.** A healthy RH800C HD board reads:

```
D1 01 40 00 08 60 00 00 04 D2 00 80 00 00 00 00
```

(`er_Type` D1 = Zorro II, autoboot ROM, 64 KB; product 1; manufacturer
`$0860` = 2144; serial 1234; diag vector `$0080`.) `C1` in the first byte means
the non-autoboot ROM half is selected (see [`/ABEN`](#detached-aben-bodge-wire)).
With our rebuilt UA6 and RAM enabled, a second board (product 2, `er_Type`
`$EE`/`$EF`/`$E8` for 2/4/8 MB; 8 MB untested) is listed first. Note that DiagROM only writes
the base address if you answer **Y** when it asks.

### Logic analyser: distrust channels with 0 transitions

**A channel showing 0 transitions is a dead probe until proven otherwise.** Dead
micro-clips cost us more than six capture cycles, including three false "stuck"
readings on one awkward pin. Before you trust a capture:

- free-run for a second and confirm **every** channel toggles;
- for signals that really are static, probe both the source end and the
  destination end;
- keep signals on the same channels between captures and only add clips.
  Re-seating micro-clips is how channels die.

### Scope: look at voltage levels, not only logic states

An LA only shows 0 or 1. A scope shows *why*. A floating LS-TTL input sits at
about **1.5 V**. A bus line idling at about 4 V when nothing should be driving
it is being pulled up or driven by something it shouldn't be connected to. A
"low" that only reaches 1.4 V is a fight between two drivers. That is how we
found the [SIMM bridge](#simm-socket-contact-bridge-on-db3). Another example:
3.4 V on a '374 output means it is driving high against a pull-down.

### Use an emulator to separate disk problems from hardware problems

Amiberry emulates the RocHard with its real ROM. If an image autoboots in
Amiberry but not on the card, the problem is the hardware. If it fails in
Amiberry too, the problem is the image. (The emulator does not model the card's
RAM.) See [IDE and disk images](ide-and-disk-images.md#testing-in-amiberry).
