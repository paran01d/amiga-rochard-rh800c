# GAL logic

Sources, JEDEC files and decoded originals for the RH800C's programmable logic. For how we recovered them, see [docs/gal-reverse-engineering.md](../docs/gal-reverse-engineering.md).

## What is fitted on the working card

| Socket | Fit | Fuse checksum | Function |
|--------|-----|---------------|----------|
| **UA6**  | [`ua6/ua6_ram6.jed`](ua6/ua6_ram6.jed) | `0x9365` | Autoconfig sequencer. Presents the second (RAM) autoconfig board. |
| **UA3b** | [`ua3b/ua3b_rebuild8.jed`](ua3b/ua3b_rebuild8.jed) | `0xC824` | DRAM controller on the UA3 daughterboard |
| UA4  | original chip ([`original/ua4_*`](original/)) | | Address decode, `$E8` window, base-address latch |
| U11  | original chip ([`original/u11_*`](original/)) | | Autoconfig slot decode, DTACK, buffer/RAM enables |
| U12  | original chip ([`original/u12_*`](original/)) | | Latch clock, `/BASE_A` / `/BASE_B` |
| U13  | original chip ([`original/u13_*`](original/)) | | Registered state machine |
| U14  | original chip ([`original/u14_*`](original/)) | | Glue: SIMM write enables, `/_ROMOE`, IDE CS, `/_OVR` |

All the chips are GAL22V10 except U12, U13 and U14, which are GAL16V8. To replace a dead original, burn the `original/*_original.jed` file for that chip.

Burn with a TL866II+ (or similar) and confirm the checksum by reading the chip back:

```sh
minipro -p GAL22V10B -w ua6/ua6_ram6.jed > burn.log 2>&1   # never pipe into head
minipro -p GAL22V10B -r readback.jed > /dev/null 2>&1; grep '^\*C' readback.jed
```

Make sure the chip is actually seated in the socket first. An empty socket reads as blank (checksum `0xDD2F`) and fails verification just like a bad fuse would.

## Building from source

The `Makefile` runs [GALasm](https://github.com/daveho/GALasm) (`galasm` on `PATH`). Run it from this directory:

```sh
make              # build the two card GALs: ua6/ua6_ram6.jed and ua3b/ua3b_rebuild8.jed
make ua6-hd       # UA6 HD-only diagnostic build (ua6/ua6_hd_b001d.jed)
make history      # rebuild every historical revision
make checksums    # print the fuse checksum of every .jed (expect 9365 / c824 / 670d)
make clean        # remove galasm's .fus/.chp/.pin side files (committed .jed files are kept)
make lgc          # TL866 logic-test vectors from ua4/*.toml (needs xgpro-logic)
make ua6/ua6_ram4.jed   # any single source can be built by path
```

Building from source reproduces the committed JEDs exactly (same fuse checksums).

Before you burn a rebuilt JED, check it with MAME's `jedutil -view x.jed gal22v10` and diff the result against the previous revision. GALasm has two silent polarity traps, covered under [lessons](../docs/gal-reverse-engineering.md#5-practical-lessons): slashes on both the pin declaration and the equation, and `.T = VCC`.

## Layout

| Folder | Contents |
|--------|----------|
| [`original/`](original/) | Dumps, JEDEC files and decoded equations read from the original Roctec chips |
| [`ua6/`](ua6/) | Our replacement UA6 designs. `ua6_ram6` is the one to use. |
| [`ua3b/`](ua3b/) | Our replacement UA3b designs. `ua3b_rebuild8` is the one to use. |
| `ua4/` | Early UA4 draft (`ua4.pld`, "Draft 05", the card stays invisible), from before the original was read. Also XGPro test vectors (`*.toml` / `.lgc`) for checking UA4 and U14 clones. Historical only. Fit the original UA4 logic. |
| `*/history/` | Every superseded revision, kept for reference. Each `.pld` header says what changed and why. Don't burn these unless you're retracing the work. |
| `misc/berr_wdog.*` | **Diagnostic only.** A GAL22V10 bus-error watchdog that pulls `/BERR` (expansion slot pin 46) low if a `$200000-$3FFFFF` access gets no DTACK within about 8 CDAC cycles (~2.2 µs). With it fitted, a dead RAM address makes the CPU take a bus error instead of hanging, so memory tests can log the address and carry on. It is wired with flying leads and isn't part of the card. |
