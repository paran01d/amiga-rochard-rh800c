# Logic-analyser tools

## rh_acprobe.py: autoconfig decoder

`rh_acprobe.py` decodes a logic-analyser capture of the card's **Zorro II autoconfig** sequence (a KingstVIS transition CSV, optionally gzipped). It rebuilds the configuration registers the way `expansion.library` reads them, splits the trace into boards at each `$48` / `$4C` write, and prints er_Type, manufacturer, product, flags and size for each board.

```sh
python3 rh_acprobe.py capture.csv                 # decode one run
python3 rh_acprobe.py run_a.csv run_b.csv         # diff two runs
```

The capture needs these columns: `AS`, `RW`, `CFGMATCH`, `DB15`-`DB12` and `AB1`-`AB6`. `DRVEN`, `ROMOE` and `DTACK` are used if present. Matching is case-insensitive, and leading `/`, `_` and `~` are ignored.

We used this to confirm that our replacement UA6 makes the card enumerate as two boards (RAM, then HD) and to debug its base-latch timing. See [`../gal/ua6/`](../gal/ua6/).

## AUTOCONFIG_PROBE.md

[`AUTOCONFIG_PROBE.md`](AUTOCONFIG_PROBE.md) is the **plan written before the first autoconfig capture**: the probe points (chosen so that no clip sits on adjacent pins), the trigger settings (`_CFGMATCH` falling, 16 MSa/s or faster, armed while the Amiga is held in reset), and what each possible outcome would mean. The probe points and method are still useful. Its target er_Type table (which leaves out the CHAINED bit) was a working assumption at the time. The design that works, and its er_Types, are in [`../gal/ua6/ua6_ram6.pld`](../gal/ua6/ua6_ram6.pld).
