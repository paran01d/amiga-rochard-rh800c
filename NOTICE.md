# Notice: third-party material

## Included, not ours
- **`gal/original/`** contains fuse dumps, JEDEC files and decoded equations
  read from the **original Roctec GAL chips** on the card (UA4, U11, U12, U13,
  U14, plus our black-box model of UA6 and a protected readback of UA3b). The
  logic they describe is the work of its original authors and is **not**
  covered by this repository's licences. It is shared for repair and
  preservation of a long-discontinued product.
- **`galdurino-tools/jed-converter-repaint-fix.patch`** is a small patch to the
  JED-Converter from Galdurino (see below); the surrounding code belongs to its
  author.

## Deliberately NOT included (copyrighted - obtain your own)

The RocHard manual, installation disk and ROM images are available from the
RocHard page on [amiga.resource.cx](https://amiga.resource.cx/exp/rochard).

- The **RocHard boot ROM** images (U6/U20 27C64), the **RocHard manual** and the
  **RocHard software disk** (formatter, driver).
- The **RocHard DriveInit driver** and **FastFileSystem** segments that
  `disk-image/mkrochard.py` embeds in a disk image - extract them from your own
  RocHard-formatted disk and Workbench disks (see `disk-image/README.md`).
- **Kickstart ROMs, Workbench disks, WHDLoad game data, and game images.**

## Tools and projects we used (thanks!)
- [Galdurino](https://gitlab.com/MHeinrichs/galdurino) by Matthias Heinrichs - GAL reader/cracker shield.
- [minipro](https://gitlab.com/DavidGriffith/minipro) - TL866II+ programmer software (incl. `--logic_test`).
- [GALasm](https://github.com/daveho/GALasm) - GAL assembler. MAME `jedutil` - fuse-map decoding.
- [vasm](http://sun.hasenbraten.de/vasm/) - 68k assembler.
- [amitools](https://github.com/cnvogelg/amitools) (`xdftool`, `rdbtool`) - Amiga disk images on Linux.
- [WinUAE](https://www.winuae.net/) / [Amiberry](https://amiberry.com/) - RocHard emulation used as a test bed; fs-uae.
- [Amiga Test Kit](https://github.com/keirf/amiga-stuff) by Keir Fraser, and [DiagROM](https://www.diagrom.com/) by John "Chucky" Hertell.
- [WHDLoad](https://www.whdload.de/) and `skick346` from [Aminet](https://aminet.net/package/util/boot/skick346).
- KiCad, OpenSCAD, three.js, KingstVIS (logic analyser).
