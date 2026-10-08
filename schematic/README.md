# Schematic

> ⚠️ **Reverse-engineered — do not trust it blindly.** This is not a Roctec
> drawing. It was traced by hand from one physical board (continuity probing),
> and it is **incomplete and certainly contains errors**. In particular it does
> **not** include:
> - the **SCSI** section of the card,
> - the **power** circuitry (supply input, regulation, decoupling),
> - the **RAM data return paths** (SIMM DQ lines back to the data bus, and the
>   SIMM power pins).
>
> Use it as a guide for finding your way around the board, and verify any net
> with a meter before relying on it. Known errors are tracked in
> [docs/schematic-corrections.md](../docs/schematic-corrections.md).

[`rotecrh800c.kicad_sch`](rotecrh800c.kicad_sch) is a **KiCad 9** schematic of the RocHard RH800C, drawn by hand from the physical board by probing continuity. It's a single sheet. Open `rotecrh800c.kicad_pro` in KiCad 9 or later.

- The symbols are embedded in the schematic, so the project-local `sym-lib-table` is empty. You don't need any extra libraries.
- `rotecrh800c.kicad_pcb` is an empty placeholder. No layout has been drawn.
- GAL pin names follow the decoded equations. See [`../gal/original/`](../gal/original/).

**The drawing has known errors and omissions.** Still outstanding: U9 is drawn as a 74LS688 (it is a 74LS374); UA4 and U11 use a PAL20R8 symbol; U11 pin 17 is still labelled `~O3`; DIP-3 is not drawn; the SIMM data/power pins and the SIMM address series resistor arrays are not drawn; and R21's value is wrong. Read [docs/schematic-corrections.md](../docs/schematic-corrections.md) before trusting any net. Where the schematic disagrees with a decoded GAL fuse map, trust the fuse map.
