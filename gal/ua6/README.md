# UA6: replacement autoconfig sequencer

**Use [`ua6_ram6.jed`](ua6_ram6.jed) (fuse checksum `0x9365`)**, built from [`ua6_ram6.pld`](ua6_ram6.pld). It's a GAL22V10.

The original UA6 couldn't be read, and a black-box sweep of it couldn't see its internal state (see [`../original/README.md`](../original/README.md)). So we designed this one ourselves. The design draws on the Zorro II autoconfig protocol, the decoded UA4 / U11 / U12 / U14 equations, the board's address map and logic-analyser captures of real enumeration.

## What it does

The card enumerates as **two** Zorro II boards:

1. **RAM board**, served by UA6. While this board is being configured, UA6 holds `/_DRVEN` high. That gates the boot ROM off and makes UA4's base latch transparent. UA6 then drives the autoconfig nibbles itself on `DB12-DB15`:
   - manufacturer 2144, product 2, MEMLIST + CHAINED
   - er_Type **`$EE`** for the 2 MB strap, **`$EF`** for 4 MB, **`$E8`** for 8 MB (the 8 MB setting is untested)
2. **HD controller**. When the OS writes the RAM board's base address (`$48`), UA6 drops `/_DRVEN`. The ROM comes back and serves the original HD board (manufacturer 2144, product 1), exactly as before.

With DIP-2 off (RAM disabled), a no-RAM escape term drops `/_DRVEN` right away, and the card behaves like an HD-only board. No original chip was modified.

Fit it together with [`../ua3b/ua3b_rebuild8.jed`](../ua3b/). The configurations we tested: DIP-1 and DIP-2 on, JPA1 at 2M (SIMM0/1) and JPA1 at 4M (SIMM0-3).

## Other files here

| File | Checksum | Use |
|------|----------|-----|
| `ua6_hd.jed` / `.pld` | `0x654B` | HD only. RAM never announced. The HD-only build from before the RAM work. |
| `ua6_hd_b001d.jed` / `.pld` | `0x670D` | HD only plus a base-latch fix. RAM never announced. A known-good fallback and diagnostic build. |
| `history/` | | Every superseded attempt: `ua6_rebuild*` (first-principles drafts), `ua6_hd_*` (HD bring-up variants) and `ua6_ram` to `ua6_ram5` (two-board revisions). Each header records what was measured and why it changed. |

The `.pld` headers are detailed, so read them before you change anything. The base-latch timing around the `$48` write is subtle, and `/BASE_A` is a per-bus-cycle strobe, not a level, so any term gated on it needs a self-hold.

Build with `make ua6/ua6_ram6.jed` from [`..`](../). See [`../README.md`](../README.md).
