# Galdurino host tools (our additions)

> **Galdurino is not our project.** The Galdurino GAL reader is designed and published by Matthias Heinrichs:
> **<https://gitlab.com/MHeinrichs/galdurino>**
> You need its shield, firmware and documentation to use anything here. Credit for the hardware, the firmware and the read-protection bypass belongs to the upstream project.

This folder contains the Linux-side tools we wrote to drive a stock Galdurino while recovering the RH800C's GALs, plus a separate bit-bang probe we built for UA6. For the story and results, see [docs/gal-reverse-engineering.md](../docs/gal-reverse-engineering.md).

## Reader tools (stock Galdurino firmware, serial 9600 8N1)

| File | Purpose |
|------|---------|
| `galduread.py` | Command-line reader: `--type 16V8\|20V8\|22V10 --poti N --out x.dump`, with `--sweep`, `--fine-sweep`, `--sweep-range LO HI STEP`, `--attempts`, `--delays` and `--discharge`. |
| `gald_ui.py` | Interactive terminal replacement for the Java UI. Commands: `status`, `identify`, `read16/20/22`, `spread` (poti sweep), `hold`, `prime`, `jed`, `decompile`, `save` and `raw`. Type commands at its prompt. |
| `minimal_read.py` | Sends exactly what the Java UI sends: `minimal_read.py <port> <poti> <out.dump>` (16V8). |
| `crack22v10.py` | `crack22v10.py [start_poti] [count]`. Repeated 22V10 reads around a poti value (default 238, the value that read UA4). |
| `overnight_crack.py` | `overnight_crack.py <stop_epoch>`. Unattended sweep over delay and poti combinations, capped at poti 235 to protect the shield's 25 V capacitor. |
| `dump_gal.sh` | `dump_gal.sh <ref> <16V8\|22V10> [poti]`. Wrapper around the two tools above. |
| `gald2jed.py` | Converts a 16V8 dump to JEDEC: `gald2jed.py in.dump out.jed`. |
| `gald2jed_22v10.py` | Converts a 22V10 dump to JEDEC, including CFG bits: `gald2jed_22v10.py in.dump out.jed`. |
| `jed-converter-repaint-fix.patch` | A fix for the upstream Java UI (JED-Converter), whose text area stops repainting under Java 21. The file is a readable diff summary, not `git apply` format, so apply the change by hand. |

Decode a JEDEC with [MAME's `jedutil`](https://github.com/mamedev/mame): `jedutil -view x.jed gal22v10`.

The "CRACKED" flag in these scripts fires at 200 zero bits, which only tells you that something changed. A real 22V10 program is 55-97% zeros. Triage candidate dumps with [`../tl866-probe/check_jed.py`](../tl866-probe/check_jed.py).

### Local paths and ports: pass your own

These were bench scripts, and several have the author's setup **hard-coded near the top**. Edit them before use:

- Serial port `/dev/ttyACM0`: `crack22v10.py`, `overnight_crack.py`, `gald_ui.py`, `dump_gal.sh`. `galduread.py` takes `--port`, and `minimal_read.py` takes the port as its first argument.
- Output and tool locations default to the script's own folder (or the current directory) and can be overridden with environment variables: `GALD_CRACK_DIR`, `GALD_DUMP_DIR`, `GALD_LOG`, `ROCTEC_DIR`, and `JEDUTIL` (MAME `jedutil`, default: from PATH).

`pyserial` is required.

## Galdurino-BB: bit-bang probe (separate hardware)

This isn't a fuse reader. It's a static pattern generator and output reader that we used to probe UA6 empirically.

- [`bb-probe-hardware/`](bb-probe-hardware/): KiCad schematic. An Arduino Uno and two MCP23S17 (SPI) port expanders on perfboard. One expander drives UA6's 14 inputs, and the other reads its 8 outputs through pull-ups.
- [`bb-probe-firmware/Galdurino-BB.ino`](bb-probe-firmware/Galdurino-BB.ino): Uno firmware. Serial commands: `INIT`, `POWER ON|OFF`, `DRIVE <hex14>`, `READ`, `STEP <hex14>`, `SWEEP <a> <b> [s]` (CSV output) and `STATUS`. Type `HELP` for the full list.
- [`bb-probe-firmware/ua6_probe.py`](bb-probe-firmware/ua6_probe.py): host sweeper. Writes a truth-table CSV and can optionally minimise each output with `pyeda`. Run it as `ua6_probe.py --port /dev/ttyUSB0 --out sweep.csv`, or set the `GALDURINO_PORT` environment variable.

With pull-ups only, this probe can't distinguish a driven-high output from a tri-stated one. For that, use the two-pass TL866 method in [`../tl866-probe/`](../tl866-probe/).
