# GAL reverse engineering

The RH800C's glue logic lives in seven GALs. Without their equations we couldn't tell a logic fault from a physical one, and we couldn't replace a dead or faulty chip. This page covers how we got the logic back out of each chip, which tools we used, and the mistakes that cost us time.

| Chip | Type | How recovered | Result |
|------|------|---------------|--------|
| UA4  | GAL22V10 | Galdurino read (poti = 238) | Full fuse map + equations. Original fitted. |
| U11  | GAL22V10 | Galdurino read, 5 identical reads | Full fuse map + equations. Original fitted. |
| U12  | GAL16V8  | Galdurino read | Full fuse map + equations. Original fitted. |
| U13  | GAL16V8  | Galdurino read | Full fuse map + equations. Original fitted. |
| U14  | GAL16V8  | Galdurino read; TL866 functional check | Read-protected, but read anyway. Validated: 1024 vectors, 0 mismatches. Original fitted. |
| UA6  | GAL22V10 | Galdurino-BB and TL866 black-box sweeps | Unreadable. Replaced by a new design: [`ua6_ram6.jed`](../gal/ua6/). |
| UA3b | GAL22V10 | Logic-analyser captures on the running card | Unreadable and buggy. Rebuilt: [`ua3b_rebuild8.jed`](../gal/ua3b/). |

The recovered dumps, JEDEC files and decoded equations are in [`gal/original/`](../gal/original/).

---

## 1. Galdurino: reading the fuse maps

[**Galdurino**](https://gitlab.com/MHeinrichs/galdurino) by Matthias Heinrichs is an Arduino shield that reads GAL16V8, GAL20V8 and GAL22V10 chips. Because of a bug in many parts, it can also read the fuse map of chips that have their security fuse set. The shield has a digital potentiometer ("poti") that sets the programming voltage used during the read. Whether a protected chip gives up its fuse map depends strongly on that voltage, and sometimes on timing.

The upstream project includes the shield, the firmware and a Java UI (JED-Converter). We drove it from Linux with our own Python host tools, which are in [`galdurino-tools/`](../galdurino-tools/):

| Tool | Purpose |
|------|---------|
| `galduread.py` | Command-line reader. Talks to the stock Galdurino firmware (9600 8N1). Supports `--sweep`, `--fine-sweep`, `--sweep-range`, `--delays` and `--discharge`. |
| `gald_ui.py` | Interactive terminal UI that replaces the Java UI. It keeps command history and provides `read16/20/22`, `spread` (poti sweep), `hold` and `prime` (voltage priming), `jed` (convert) and `decompile` (runs MAME's `jedutil`). |
| `minimal_read.py` | Reproduces exactly what the Java UI sends, with no extra commands. Use it when the full-featured tools disturb a marginal read. |
| `gald2jed.py` | Converts a Galdurino dump to JEDEC for 16V8 parts (chip ID 1A/1B). |
| `gald2jed_22v10.py` | Converts a Galdurino dump to JEDEC for 22V10 parts, including the 20 architecture (CFG) bits. |
| `crack22v10.py` | Repeatedly reads a 22V10 in a small poti window around a starting value. This is the script that reproduced the UA4 read at 238. |
| `overnight_crack.py` | Unattended sweep over delay and poti combinations. Caps the poti at 235 to stay inside the shield's 25 V capacitor rating. |
| `dump_gal.sh` | Wrapper: a 16V8 neighbour sweep around poti 230, or `crack22v10.py` for a 22V10. |
| `jed-converter-repaint-fix.patch` | Fixes the upstream Java UI not repainting its text area under Java 21. |

To turn a dump into equations we used [MAME's `jedutil`](https://github.com/mamedev/mame): `jedutil -view chip.jed gal22v10`.

### UA4: the 22V10 we caught once

Hundreds of attempts failed before UA4 (a Lattice GAL22V10B) gave a real read, at **poti = 238**. That read is 77% zeros and a sensible CFG word (`10111010101111111010`), and it decodes cleanly. Most later reads at the same setting failed again, because the chip has to be caught in a narrow power-up window. Keep any good dump you get. You may not get a second one.

The decoded equations ([`ua4_equations.txt`](../gal/original/ua4_equations.txt)) showed:

- All outputs are combinatorial. Pins 14, 15 and 20 are inputs.
- Pins 16, 17 and 18 are **self-holding latches** (`o16 = ... + o16`) whose output enable is `/i14`. They capture the base-address bits that the OS writes during autoconfig.
- Pin 23 is `/_E8WIN`, the decode of the `$E8xxxx` autoconfig window, which feeds U11.
- Pin 14, the master enable for those latches, is driven by **UA6 pin 23 (`/_DRVEN`)**. The schematic didn't show this trace; we found it by probing the board. It puts UA6 on the autoconfig path.

The self-holding latch built from combinatorial feedback turned out to be this designer's standard construct. It also appears in U11 and in UA3b, which mattered later (see section 4).

### U11, U12, U13, U14

- **U11** (22V10) is the autoconfig slot decoder (`/BASE_C`) and the `_DTACK` / `/_BUFRDY` / `/_RAMCE` / `/_U1CE` generator. Five reads were byte-identical (about 92% zeros). `jedutil` reproduces [`u11_equations.txt`](../gal/original/u11_equations.txt) exactly from the real fuse map. Input 5 (`/_AC_PHASE`, from UA6) appears in no product term, so it has no effect on U11.
- **U12** (16V8) is a two-stage shift register plus parity. It generates `/_LATCH_CLK` and `/BASE_A` / `/BASE_B`.
- **U13** (16V8) is a registered state machine with simple inverters on pins 15-17.
- **U14** (16V8) is combinatorial glue: `/SIMMWEL`, `/SIMMWEU`, `/_ROMOE`, `/_IDE2CS0`, the mux signals and `/_OVR`. U14 is read-protected, but the 16V8 bug let us read it at around poti 230. A second read (`u14_verification_original.*`) is identical to the first, and the TL866 functional check below confirmed it.

### What a protected read looks like

`tl866-probe/check_jed.py` scores candidate JEDs by fuse density. A real 22V10 program is 55-97% zeros (UA4 77%, U11 92%). A blocked read is nearly blank (UA3b 1.1%). Bit-identical dumps at *different* poti values are the strongest sign that a read is genuine. Don't trust `crack22v10.py`'s "CRACKED" flag on its own: it fires at just 200 zero bits (about 3.4% of the array), so it only tells you that something changed.

---

## 2. TL866II+ black-box pipeline

For chips we couldn't read, and to check the ones we could, we used the TL866II+ programmer as a logic tester. minipro's `--logic_test` mode drives a vector onto the chip and reports each output as L, H or Z. Each output pin is measured twice, once with a pull-up and once with a pull-down, so a real tri-state output can be told apart from one that is actively driven. A perfboard rig with a single pull-up can't make that distinction.

minipro reads test vectors from a `logicic.xml`. If you pass `--logicic <file>`, minipro looks up the `-p <name>` device in that file first and never touches the installed database. So we generate a custom XML per chip, and nothing installed gets modified.

The pipeline lives in [`tl866-probe/`](../tl866-probe/):

| Tool | Purpose |
|------|---------|
| `gal_configs.py` | Pin roles per chip: driven inputs, observed outputs, VCC/GND. Contains UA6, U11, UA4, U14, UA3b and a few partial-sweep variants. |
| `gen_vectors.py` | Writes the logicic XML: a full 2^N sweep, `--sample N` random patterns, or a `--start/--end/--step` slice. |
| `parse_measured.py` | Converts minipro's `--logicic_out` XML into a CSV with one bit column and one `z_` (tri-state) flag per output pin. |
| `validate_against_equations.py` | Evaluates a `jedutil` / GALasm-style equations file for every measured row and reports mismatches. A self-feedback latch passes if the measured state is a stable fixed point of its equation. Registered outputs are skipped, because the tester doesn't clock them. |
| `check_jed.py` | Triage tool for Galdurino sweep output (see above). |

**Validation.** Before we trusted the pipeline on an unknown chip, we ran it on chips whose equations we already had. **U11 was swept over all 2^17 = 131,072 input patterns with zero mismatches** against its equations. **U14 matched over 1024 vectors with zero mismatches**, which validated its Galdurino read even though the chip is protected.

**Limits.** The tester only sees what reaches the pins:

- **UA6**: a full 16,384-pattern sweep, repeated with bit-identical results, showed only two pins driven (constant low) and everything else Hi-Z. That's the externally visible behaviour only. UA6's real job is a sequencer, and its state is most likely held in internal feedback on *unconnected* pads, which a socket sweep can neither drive nor observe. (We never recovered the original's actual logic; our own replacement does keep its phase latch on unconnected pad 22.) A clone burned from the sweep (`gal/original/ua6_original_crack.*`) red-screened the Amiga. In the end we designed UA6 again from the Zorro II autoconfig spec, the neighbouring chips' equations and logic-analyser captures (see [`gal/ua6/`](../gal/ua6/)).
- **UA3b**: sweeping the same 4096 patterns in three different orders gave different answers for every output, so the chip is stateful. Most transitions start from a tri-stated state, and minipro measures Hi-Z by driving the pin both ways, which pushes values straight into the GAL's feedback path. **The tester perturbs what it measures**, so a truth table of a feedback-latch design isn't reliable.

---

## 3. Galdurino-BB: a bit-bang probe for UA6

Before the TL866 pipeline existed, we built a static pattern generator to probe UA6 in place of the Galdurino reader. **Galdurino-BB** is an Arduino Uno with two MCP23S17 SPI port expanders. One expander drives UA6's 14 input pins, and the other reads its 8 output pins (pins 15, 16 and 18-23) through pull-ups.

- Firmware: [`galdurino-tools/bb-probe-firmware/Galdurino-BB.ino`](../galdurino-tools/bb-probe-firmware/Galdurino-BB.ino). It accepts serial commands such as `INIT`, `DRIVE <hex14>`, `READ`, `STEP` and `SWEEP`.
- Host: [`ua6_probe.py`](../galdurino-tools/bb-probe-firmware/ua6_probe.py). It sweeps patterns, writes a truth-table CSV and can minimise each output with `pyeda`.
- Hardware: [`galdurino-tools/bb-probe-hardware/`](../galdurino-tools/bb-probe-hardware/), a KiCad schematic of the perfboard.

With only pull-ups, Galdurino-BB can't distinguish "driven high" from "tri-stated". That's why we moved to the TL866 two-pass method.

---

## 4. UA3b: rebuilt from logic-analyser captures

UA3b is the DRAM controller GAL on the UA3 daughterboard. It generates RAS, the four bank CASes, SIMMA8/9, the row/column mux select and enable, and `/_UA3SEL`, which enables U11's DTACK for RAM cycles. The original chip was read-protected. Galdurino sweeps never got past a near-blank read: a protected 22V10 still reads zeros in the UES bits (5828-5891), while a blank chip reads all ones. The TL866 couldn't characterise it either (section 2). The original also had a fault: its access path required A17 = 1, so half of every bank was unreachable and any A17 = 0 access hung the CPU.

So we rebuilt UA3b from its **in-circuit behaviour**. We captured real RAM accesses and refresh with a 16-channel logic analyser and measured the row/column address mapping, bank-to-CAS decode, mux timing, `_UA3SEL` timing and CAS/RAS widths. We then wrote a new design ([`ua3b_rebuild8.pld`](../gal/ua3b/ua3b_rebuild8.pld)) that uses only combinatorial macrocells with self-holding latches, like the original. Pin 1 carries AB17, so registered macrocells weren't an option. The access timing is measured from the original. The refresh scheme is our own, because the original's couldn't be separated from the captures.

**Rev 8** (fuse checksum `0xC824`) is the keeper. **Rev 9** tried to "fix" RAS precharge, and measuring it showed the change cut the row-address hold time (tRAH) to 10 ns. Rev 8 measures 60 ns, because its `/CDAC`-armed mux provides the hold. Rev 9 was reverted. The captures are in [`captures/`](../captures/).

---

## 5. Practical lessons

**GALasm polarity.** For an active-low tri-state output, declare the pin **without** a slash and put the slash only in the equation:

```
; pin list: ... CLK1 ...
/CLK1.T = term          ; correct: macrocell ACTIVE_LOW
```

If you put a slash in *both* places, they cancel. The macrocell becomes active-high, the source still reads as active-low, and nothing warns you. Check the `.fus` file for S0 = 0 on active-low outputs. A related trap: `X.T = VCC` assembles to an empty term and drives the pin **low** whenever its output is enabled. For a constant high, use `X.T = A + /A`. (`ua6_ram6.pld` uses `X.T = VCC` for its unused ACPHASE and NC15 outputs; that is harmless there only because their `.E = AB1 & /AB1` is never true, so the pins stay Hi-Z.) Diff the `jedutil -view` output of each new revision against the previous one before you burn it.

**Confirm the chip is seated before every `minipro -w`.** During burn-and-test cycles the chip moves between the programmer and the Amiga all the time. An empty or half-seated socket reads as all-FF: a 22V10 gives checksum **0xDD2F**, which is the blank checksum, and a failed verify looks exactly like a stuck fuse. When a write fails to verify, suspect, in order: an empty or half-seated socket, an open ZIF lever, the wrong device type, and only then a worn chip.

**Decode a verify-failure address.** For a 22V10, `row = addr // 44` and `col = addr % 44`. Look up that row in the `.fus` to find the literal, and therefore the pin. For example, 0x005F is row 2, column 7: the `/NC22` literal, which pointed at a bad contact on pin 22. Reseating fixed it.

**Never pipe minipro into `head`.** When `head` closes the pipe, minipro gets SIGPIPE in the middle of a write and leaves the GAL partially programmed. Log to a file instead (`minipro ... > burn.log 2>&1`) and check for both `exit=0` and "Verification OK". Then read the chip back with `-r` and compare the `*C` checksum with the source JED.

**Protected or blank?** A protected 22V10 still reads **zeros in the UES bits**. A blank or erased chip reads all ones (checksum 0xDD2F).

**Old EPROMs.** Use `minipro -y` to skip the ID check on old EPROMs whose ID reads wrong. A 28-pin chip sitting one row off in the ZIF also reads all-FF. Check the position before you conclude the chip is blank.

**Black-box results aren't health checks.** A repeatable sweep rules out intermittent faults, but a chip that's stuck is just as repeatable. Before you trust any sweep, classify each GAL pin as an input or output from the schematic and the bus semantics.
