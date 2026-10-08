# Captures

These are raw evidence behind specific findings. The `.csv` files are KingstVIS logic-analyser exports in transition format: a time column in seconds, relative to the trigger, followed by one column per channel.

| File | Channels | What it shows |
|------|----------|---------------|
| `roctec_db3.csv` | `_U1CE`, `DATADIR`, `DB3`, `D3`, `ROMD3`, `IDEEN`, `DB2`, `D2`, `AS` | **The `/DB3` fault.** A bent contact in the SIMM4 socket bridged pin 12 (SIMMA5) to pin 13 (DQ3, `/DB3`). That held `/DB3` near 4 V, so ROM data bit 3 always read as 1 and autoboot gave a black screen. In the capture, `DB3` (and the ROM-side `ROMD3`) stays high for almost the whole trace. We fixed it by straightening the socket contacts, and SIMM4 now stays empty. |
| `roctec_write_cdac100.csv` | `_RAMRAS`, `GALCLK1`, `SIMMA0` (100 MSa/s) | RAM write cycles with **UA3b rev 9**. Row-address hold (tRAH: from `_RAMRAS` falling until `SIMMA0` switches to the column address) measures **10 ns**, below the DRAM minimum. Rev 9 was reverted. |
| `roctec_write_cdac1002.csv` | same as above | The same measurement on **UA3b rev 8** (the keeper): tRAH is **60 ns**. |
| `rhstress_overnight_pass10_lostwrites.log` | serial log | An overnight [`rhstress`](../amiga-tools/) run at 2 MB: 249 passes, 66 errors, all from **one burst in pass 10**. 33 consecutive longwords at `$376DD8-$376E58` (bank 0) read back with **pass 9's pattern**. The pass-10 writes had been acknowledged by DTACK but never stored. There was no decay and no aliasing. The cause was the poorly seated UA3 daughterboard. After it was reseated and secured, the errors stopped. |

For the UA3b revisions, see [`../gal/ua3b/`](../gal/ua3b/).
