# Roctec RocHard RH800C — restoration notes, tools and rebuilt logic

The **Roctec RocHard RH800C** is a 1990-era side expansion for the Amiga 500:
a Zorro II **IDE hard-disk controller** with an autoboot ROM, plus sockets for
up to **8 MB of fast RAM** on 30-pin SIMMs (and an unpopulated SCSI section).
Documentation for it is almost non-existent, and several of its logic chips are
read-protected GALs.

This repository is everything from bringing a **faulty RH800C back to life**:
the reverse-engineered logic, two rebuilt GALs, a hand-drawn schematic, the
diagnostic tools we wrote, a 3D-printed CF-card faceplate, and a detailed write-up
of what went wrong and how it was found.

> 🤖 **Made with generative AI.** This project was carried out by one person
> working with **Claude** (Anthropic's AI) via **Claude Code**. The AI wrote most
> of the code, logic equations and documentation, and helped analyse
> measurements; all hardware work, measurements and real-machine testing were
> done by the human. See **[How AI was used](docs/ai-usage.md)**, including
> where it got things wrong.

## Essential resource: the RocHard page on amiga.resource.cx

**<https://amiga.resource.cx/exp/rochard>** is where to find what this repo
deliberately does not include: the **user manual**, the **installation disk**
(driver and formatter) and the **boot ROM images** (v1.0 and v2.0, odd/even
pairs), plus the card's specifications. Our card runs the **v2.0** ROM.

## Status (October 2026)

| | |
|---|---|
| IDE / CompactFlash | ✅ Autoboots Workbench (OS 3.1.4, and a WB 1.3 image for Kickstart 1.3 machines) |
| Autoconfig | ✅ HD controller board, plus a second board that announces the RAM |
| Fast RAM | ✅ 2 MB stable, 4 MB working (long-run verification ongoing); 8 MB untested |
| SCSI | ⬜ untested |
| Original chips | Only **UA6** and **UA3b** replaced with our rebuilt GALs; all other logic is original |

**To get a card like this working you need:** UA6 = [`gal/ua6/ua6_ram6.jed`](gal/ua6)
(fuse checksum `0x9365`), UA3b = [`gal/ua3b/ua3b_rebuild8.jed`](gal/ua3b) (`0xC824`),
and a CF image built with [`disk-image/mkrochard.py`](disk-image).
Then read [troubleshooting](docs/troubleshooting.md): **most of our "logic"
faults turned out to be physical** (an unseated daughterboard, a bridging SIMM
socket contact, a detached factory bodge wire, a dirty edge connector, a weak
−12 V rail).

## Repository layout

| Folder | What's in it |
|---|---|
| [`docs/`](docs/README.md) | The write-up: hardware overview, autoconfig, RAM, IDE & disk images, GAL reverse engineering, troubleshooting, schematic corrections, the A500 1 MB chip upgrade, the [work log](docs/worklog.md) and [AI usage](docs/ai-usage.md) |
| [`gal/`](gal) | GAL logic: our rebuilt **UA6** and **UA3b** (plus full revision history), UA4 test vectors, and the decoded **original** chips |
| [`schematic/`](schematic) | KiCad 9 schematic **reverse-engineered by hand** from one board: incomplete (no SCSI section, power circuitry or RAM data return paths) and not guaranteed correct |
| [`amiga-tools/`](amiga-tools) | 68000 tools: `rhmon` serial monitor, `rocdiag` IDE probe, `rhstress` and `marchu` RAM tests, `romdump`, `rhmemtest` |
| [`disk-image/`](disk-image) | `mkrochard.py` (bootable RocHard CF images on Linux) and `whdmem.py` |
| [`tl866-probe/`](tl866-probe) | Black-box GAL testing on a TL866II+ (`minipro --logic_test`) and equation validation |
| [`galdurino-tools/`](galdurino-tools) | Our host tools and probe firmware for the [Galdurino](https://gitlab.com/MHeinrichs/galdurino) GAL reader |
| [`la-tools/`](la-tools) | Logic-analyser helpers (autoconfig decoder, probe plan) |
| [`captures/`](captures) | A few small logic-analyser/scope captures and logs that back up key findings |
| [`mechanical/`](mechanical) | OpenSCAD models: the CF-adapter faceplate (in use) and earlier bracket designs |

## Licences

- Code and our GAL designs: **MIT** ([LICENSE](LICENSE)).
- Docs, schematics, 3D models and data: **CC BY 4.0** ([LICENSE-docs](LICENSE-docs)).
- Third-party material, and what is deliberately **not** included (ROM images,
  the RocHard software, Kickstart/Workbench, game data): see [NOTICE.md](NOTICE.md).

## Thanks

To the authors of Galdurino, minipro, GALasm, vasm, amitools, WinUAE/Amiberry,
Amiga Test Kit, DiagROM and WHDLoad — see [NOTICE.md](NOTICE.md).
Issues and corrections are very welcome, especially from other RocHard owners.
