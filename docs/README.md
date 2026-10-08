# Documentation

> The RocHard **manual, installation disk and ROM images** are on
> [amiga.resource.cx/exp/rochard](https://amiga.resource.cx/exp/rochard). They are
> not in this repository.

Start with **[troubleshooting](troubleshooting.md)** if you have a misbehaving
RocHard on the bench, or with the **[hardware overview](hardware-overview.md)**
if you want to understand how the card works.

| Page | What it covers |
|---|---|
| [Hardware overview](hardware-overview.md) | What the RH800C is, every chip's job, switches/jumpers, address map |
| [Autoconfig](autoconfig.md) | How the card is found and placed by Kickstart; how our UA6 adds a second board for the RAM |
| [RAM subsystem](ram-subsystem.md) | SIMM banks, the UA3b DRAM controller rebuild, timing, and RAM testing |
| [IDE and disk images](ide-and-disk-images.md) | IDE register map, the byte-swap, autoboot requirements, building/patching CF images, emulation |
| [GAL reverse engineering](gal-reverse-engineering.md) | Galdurino, the TL866 black-box pipeline, rebuilding a protected GAL from LA captures, and gotchas |
| [Troubleshooting](troubleshooting.md) | Symptom → cause → fix for every fault we hit (mostly physical!) |
| [Schematic corrections](schematic-corrections.md) | Where the board differs from what a first-pass schematic suggests |
| [A500 1 MB chip RAM upgrade](a500-1mb-chip-upgrade.md) | 8372A Agnus on a rev 5 A500 with a jumperless trapdoor card |
| [Work log](worklog.md) | The project day by day, dead ends included |
| [How AI was used](ai-usage.md) | Who did what, and where the AI was wrong |
