# TL866 black-box GAL probe

These tools characterise a GAL (or any small DIP logic part) in a **TL866II+** programmer by sweeping its inputs and recording every output as L, H or Z. They use [minipro](https://gitlab.com/DavidGriffith/minipro) `--logic_test`. For background and results, see [docs/gal-reverse-engineering.md](../docs/gal-reverse-engineering.md#2-tl866ii-black-box-pipeline).

minipro measures each output twice, once with a pull-up and once with a pull-down, so it can tell a genuinely tri-stated pin from one that is actively driven. You pass the test vectors as a custom `logicic.xml` with `--logicic`. minipro looks up the `-p` name in that file first, so nothing installed is modified.

## Files

| File | Purpose |
|------|---------|
| `gal_configs.py` | Pin roles per chip: inputs, outputs, VCC, GND. Each entry's `name` (for example `UA6_SWEEP` or `U11_VALIDATE`) is the `-p` name you pass to minipro. Add an entry here for a new chip. |
| `gen_vectors.py` | Writes the vector XML: a full 2^N sweep, `--sample N`, or `--start/--end/--step`. |
| `parse_measured.py` | Converts minipro's `--logicic_out` XML into a CSV with per-pin bits and `z_<pin>` tri-state flags. |
| `validate_against_equations.py` | Compares a measured CSV with a `jedutil`-style equations file. A latch passes if the measured state is a stable fixed point of its equation. Registered outputs are skipped. |
| `check_jed.py` | Triages Galdurino read candidates by fuse density and groups identical dumps. Uses MAME's `jedutil` from your PATH, or set `JEDUTIL=/path/to/jedutil`. |
| `run_o17_chunks.sh` | Example of a 2^17 sweep split into 8 chunks with retries. Runs from its own folder. |
| `u11_measured.csv`, `ua4_measured.csv` | Sample measured data from the original U11 and UA4. |

## Usage

```sh
python3 gen_vectors.py U11 -o u11_vectors.xml               # full sweep (or --sample 512)
minipro -p U11_VALIDATE --logicic u11_vectors.xml -T --logicic_out u11_meas.xml
python3 parse_measured.py U11 -i u11_meas.xml -o u11_measured.csv
python3 validate_against_equations.py --chip U11 \
    --equations ../gal/original/u11_equations.txt --measured u11_measured.csv
```

Large sweeps can time out. If that happens, split them into chunks with `--start/--end`, as `run_o17_chunks.sh` does.

## Results and limits

- U11: all 131,072 patterns, **0 mismatches**. U14: 1024 vectors, **0 mismatches**. U14 is read-protected, so this check is what validated its Galdurino read.
- A sweep only sees the pins. It can't observe state held in internal feedback on unconnected macrocells (very likely the case for UA6), and on designs built from feedback latches (UA3b) the two-pass Hi-Z measurement drives values into the feedback path and changes the result. If a chip gives different answers when you visit the same patterns in a different order, it's stateful, and a truth table of it won't be valid.
- Before running anything, confirm the right chip is seated. A different chip left in the socket produces confident nonsense.
