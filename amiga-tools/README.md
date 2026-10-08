# Amiga-side test tools

These are 68000 assembly tools we wrote to probe and stress the RocHard's IDE and fast RAM on real hardware. Every tool that reports results also writes them straight to the serial port (**9600 8N1**, polled), so the output survives a crash. Log the other end with any terminal program.

## Building

The tools assemble with [vasm](http://sun.hasenbraten.de/vasm/) (`vasmm68k_mot`).

```sh
# Shell tools (AmigaOS executables)
vasmm68k_mot -Fhunkexe -nosym -o rhstress rhstress.s

# Bootblock tools: raw binary, then wrap it in a bootable ADF
vasmm68k_mot -Fbin -o rhmon.bin rhmon.s
python3 rhmon/mkboot.py rhmon.bin rhmon.adf
```

`mkboot.py` places the binary in the bootblock, computes the bootblock checksum and pads the result to a full 880 KB ADF. A bootblock is **1024 bytes, hard limit**. Kickstart loads and runs only those two sectors, whatever the size of the disk.

## Tools

| Tool | Type | What it does |
|------|------|--------------|
| [`rhmon/`](rhmon/) | bootblock (`rhmon.adf` prebuilt) | Interactive serial memory monitor. Commands (hex): `r <a>` reads a word, `l <a>` reads a long, `w <a> <v>` writes a word, `W <a> <v32>` writes a long, `t <a>` runs ATK's two-point RAM test at that address. Runs in supervisor mode. If the [`berr_wdog`](../gal/misc/) GAL is fitted, an access with no DTACK prints `BERR`. Without it, the machine hangs, but you know which address you typed. About 820 bytes, out of the 1024 available. |
| [`rhstress/`](rhstress/) | Shell, OS 2.0+ | Fast-RAM stress test that mimics WHDLoad. See below. |
| [`marchu/`](marchu/) | Shell, OS 2.0+ | March U memory test. See below. |
| [`rhmemtest/`](rhmemtest/) | bootblocks | Bare-metal tests of `$200000-$3FFFFF`. Each logs `W <addr>` over serial *before* touching an address, so if the machine hangs, the last line identifies the culprit. With `berr_wdog` fitted, the test catches the bus error and keeps going. `rhmemtest_nodma` runs with DMA off, `rhmemtest_lane` uses word-granular low addresses (an A1 check), and `rhchip` runs the probe from chip RAM. These are diagnostic one-offs from the bring-up. |
| [`romdump/`](romdump/) | Shell | Finds the RocHard (2144/1) through `expansion.library`, then copies its 8 KB ROM window to `RAM:romdump`. To get the file off the Amiga, `Type RAM:romdump HEX` over an AUX: serial shell. |
| [`rocdiag/`](rocdiag/) | Shell (binary only; keeps its symbol table, which helps if you recreate the source) | IDE probe. It issues commands to the card's task file and prints the status and error register for each one. **The source is lost.** Only the binary survives. |

### rhstress

```
rhstress [passes]          ; 0 or none = run until stopped
```

rhstress fills nearly all fast RAM with an address-dependent pattern. Each pass then copies it to a chip-RAM buffer in 32 KB `movem.l` bursts (fast-RAM reads interleaved with chip-RAM writes, like WHDLoad loading a game), verifies the copy, verifies fast RAM in place, and rewrites fast RAM with a new seed. Serial gets one `.` per 32 KB chunk. To stop it, press Ctrl-C or hold the **left mouse button**. Errors are printed as they happen:

```
[pass 10] copy ERR @$00376DDC exp 6FE94570 got A4B7FD3C xor CB5EB84C
```

On exit, rhstress prints the full error list (first 1000 errors), failures per data bit, and errors per bank (bank 0 = SIMM0/1 at `$200000`, bank 1 = SIMM2/3 at `$400000`, and so on). For a real example, see [`../captures/rhstress_overnight_pass10_lostwrites.log`](../captures/).

### marchu

```
marchu [c] [passes]        ; c = largest free CHIP block instead of fast RAM
```

marchu runs March U (13N) over six 32-bit data backgrounds: `00000000`, `55555555`, `33333333`, `0F0F0F0F`, `00FF00FF` and `0000FFFF`. Each mismatch prints as `M<element> ERR @addr exp got xor`, and serial also gets each element number as it completes. Ctrl-C is checked between backgrounds.

### Bootable disk

[`rhstress/rhstress_marchu.adf`](rhstress/) is a bootable floppy that holds both `rhstress` and `marchu`. Its startup-sequence prints their usage and leaves you at a Shell. It needs **Kickstart 2.0 or later**.
