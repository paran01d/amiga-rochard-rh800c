# IDE and disk images

This page covers the RocHard RH800C's IDE side: how the controller is addressed,
the byte-swap that makes "normal" disk images unreadable, exactly what the boot
ROM needs before it will autoboot, and how we build, patch and test
CompactFlash images on Linux.

Short version:

1. The card **byte-swaps the IDE data bus**, so a CF image must be `swab`'d before it is written.
2. The boot ROM only autoboots a disk whose RDB has a **DriveInit** pointing at the
   **RocHard driver** (as an LSEG chain) and the marker **`RDB[0xd4] = 0x00020000`**.
3. [`../disk-image/mkrochard.py`](../disk-image/mkrochard.py) builds such a disk
   of any size on Linux, but **you must supply the RocHard driver segment and the
   FastFileSystem segment yourself**: they are copyrighted and are not in this repo.

---

## Register map

The card configures as a 64 KB Zorro II I/O board (manufacturer 2144, product 1).
Find its base with `expansion.library` `FindConfigDev(NULL, 2144, 1)`, then use
`cd_BoardAddr`. On our A500 it lands at `$E90000`. The offsets below come from
our disassembly of the boot ROM and of the RocHard formatter. The
[`rocdiag`](#rocdiag) probe confirmed the drive 0 task file on hardware (we only
ever used drive 0).

| Window | Address | Notes |
|---|---|---|
| Boot ROM | base + `$0000`… | ROM word *n* is at base + 2*n* and equals `u6_even[n] << 8 \| u20_odd[n]` |
| Drive 0 (master) task file | base + `$8000` | Register writes at the offsets in the table below |
| Drive 0 status | base + `$8000` + `$20c1` | Where the ROM and formatter poll status (see below) |
| Drive 1 (slave) | base + `$0000` | Per the ROM decompile only, **not verified on hardware**: the card appears to pick master/slave by address window, not only by the `$A0`/`$B0` drive bit |
| Control / data latch | base + `$7000` | Registers `$100`-`$10e`, `$200`, `$300`, `$400` |

Task-file register offsets (relative to the drive window). The register number
is encoded as `reg << 5 | 1`, so IDE DA0-DA2 come from card address bits A5-A7:

| IDE register | Offset |
|---|---|
| Data | `$01` |
| Error (read) / features | `$21` |
| Sector count | `$41` |
| Sector number | `$61` |
| Cylinder low | `$81` |
| Cylinder high | `$a1` |
| Drive / head | `$c1` |
| Command (write) | `$e1` |
| Status: what the ROM, driver and formatter poll | `$20c1` |

Bit 13 (`$2000`) of the offset selects a second register group. The ROM and
the formatter read status at `$20c1` (the alternate-status / device-control
position), and the formatter reads data at `$2001`. We aren't sure whether
`$2000` is the CS1 register-block select or the card's read/write address
split. Both views fit the code we read, and the offsets above are the ones that
work. `rocdiag` reads the error register at `$8000 + $21`.

**Bulk sector data.** After DRQ the ROM reads a sector with
`movem.l (a2),d0/d2-d7/a3` sixteen times (= 512 bytes) from offset 0 of the
`$8000` window, and the card advances on its own. A separate handshake on the
`+$7000` latch (bits 5/6 of `$102`, strobes via `$104`/`$108`, data byte at
`$100`; writing `$80` then `$00` to `$102` primes it) is also used by the
driver. We did not need to drive the latch path ourselves, so this part is
only partly understood.

**Command style.** The ROM, the RocHard driver and the formatter all do
period-correct CHS I/O: INITIALIZE DEVICE PARAMETERS (`$91`), then poll for
status **exactly** `$50` (DRDY|DSC) before a command and `$58` (DRDY|DSC|DRQ)
for data, failing on ERR or after a spin timeout. There is no LBA mode. CF cards work with it, and `rocdiag` showed every command
succeeding.

---

## The byte-swap

The RocHard connects IDE DD0-7 and DD8-15 to the **opposite halves** of the Amiga
data bus. The design does this on purpose, and many Amiga IDE interfaces do the
same.

| What you see | Why |
|---|---|
| Sector 0 of a Linux-written RDB reads back as `44 52 4B 53` ("**DRKS**") instead of `52 44 53 4B` ("RDSK") | Each 16-bit word has its bytes swapped |
| The ROM's `cmp.l #'RDSK'` fails, so no RDB, no DH0, no autoboot | Same cause |
| IDENTIFY model strings still read correctly | ATA stores IDENTIFY strings byte-swapped already, so the hardware swap undoes it |
| The manual's warning that the card "cannot read disks formatted by other controllers" | The swap is one reason. The other is that the driver checksums the **whole** 512-byte RDB block (all 128 longwords), not only `rdb_SummedLongs`, so junk left in the unused half of an RDB block from another tool fails the check |

**Fix:** build the image in normal ("logical") byte order and swap every 16-bit
word before you write it to the CF:

```sh
dd if=disk.logical of=disk.media conv=swab bs=1M
```

Two terms used throughout this page:

| Term | Byte order | Used for |
|---|---|---|
| **logical** image (`*.logical`, `*.hdf`) | Normal: block 0 starts `RDSK` | Emulators (Amiberry), amitools |
| **media** image | Swapped: block 0 starts `DRKS` | Writing to the real CF |

A CF written by the RocHard itself (or by its formatter running in an emulator,
then swab'd) is in media order. To inspect it on a PC, swab it back first.

---

## What the boot ROM needs to autoboot

A disk that only *mounts* is not enough. With an ordinary RDB, `Mount` with
`Device = rt.device` and `Unit = 0` worked, but the card never offered the disk at
boot. We got a genuine reference RDB by running the RocHard formatter inside
Amiberry (see [below](#obtaining-the-driver-and-ffs-segments)) and comparing it
field by field with ours:

| RDB / block field | Required value | Ours before | Notes |
|---|---|---|---|
| `rdb_DriveInit` (RDSK + `$24`) | Block number of an **LSEG chain containing the RocHard driver** (a hunk executable, starts `00 00 03 F3`, 9,840 bytes in our reference) | `-1` | The ROM `LoadSeg`s it and runs it. The driver installs the device and creates the boot node. With `-1` there is nothing to run, so no autoboot. |
| RDSK + `$d4` | `0x00020000` | `0` | The ROM requires it to be at least `$20000` (`cmp #$20000; blt fail`; mkrochard writes exactly `$00020000`, as the reference disk does) before trusting DriveInit. We don't know what the formatter means by it, only that the ROM requires it. |
| Partition `DosType` | `DOS\1` (`0x444F5301`, FFS) | `DOS\3` | |
| Partition flags | Bootable, BootPri 1 | | |
| FSHD | `DosType DOS\1`, `SegListBlocks` → an LSEG chain holding **FastFileSystem** | none | FFS is loaded from the disk, not from Kickstart |
| RDB logical-drive fields | `RDBBlocksLo @$80`, `RDBBlocksHi @$84`, `LoCylinder @$88`, `HiCylinder @$8c`, `CylBlocks @$90`, `AutoParkSecs @$94`, `HighRDSKBlock @$98` (`= 0` in the reference) | (see bug below) | |

The reference disk's layout, which `mkrochard.py` copies: RDB in block 0, PART
blocks after it, FSHD, then the FFS LSEG chain and the driver LSEG chain, all
inside cylinder 0. Partitions start at cylinder 1.

### The old mkrochard RDB-offset bug (fixed)

Our first images wrote the RDB logical-drive fields **`0x10` bytes too low**.
The OS then read `CylBlocks` as 0 and could not locate the partitions, even though
DriveInit and `$d4` were correct. The current
[`mkrochard.py`](../disk-image/mkrochard.py) uses the standard offsets in the
table above and is byte-identical to the reference in those fields. Any image
built before the fix should be rebuilt. To check an image, `CylBlocks`
(RDSK + `$90`, logical order) must equal heads × sectors (e.g. 1008 for
16 × 63).

---

## Obtaining the driver and FFS segments

`mkrochard.py` expects two files that are **not in this repo**:

```
disk-image/rochard_parts/driveinit_seg.bin   RocHard driver (hunk executable, ~9.8 KB)
disk-image/rochard_parts/ffs_seg.bin         FastFileSystem (hunk executable)
```

The driver and FastFileSystem are copyrighted (Roctec and Commodore/Hyperion
respectively), so you have to take them from disks you own. We did it like this:

1. **Get the RocHard software disk.** The formatter is the root file `IDE` on
   that disk (`IDE_FormatHdd` is only a 10-byte stub that runs it).
2. **Run the formatter in Amiberry** with the RocHard emulated (see
   [Testing in Amiberry](#testing-in-amiberry)) and a **small, blank hardfile:
   about 128 MB, one partition.** The formatter allocates buffers that scale
   with disk size. On a large disk it runs out of memory and gives up,
   leaving only a fill pattern and no RDB.
3. **Pull the LSEG chains out of the resulting `.hdf`.** It is in logical order:
   block 0 is `RDSK`. `rdb_DriveInit` at `$24` gives the first block of the
   driver chain (block 28 on ours). The FSHD block is found via
   `rdb_FileSysHeaderList` at `$20`, and its `SegListBlocks` at `$48` gives
   the first block of the FFS chain. In each LSEG block the next-block pointer is at `$10` and data
   starts at `$14`, with `(SummedLongs − 5) × 4` data bytes per block:

```python
import struct, sys
img = open(sys.argv[1], 'rb')            # logical-order .hdf from the formatter
def blk(n): img.seek(n * 512); return img.read(512)
def lseg(first):
    out, n = b'', first
    while n != 0xFFFFFFFF:
        b = blk(n); assert b[:4] == b'LSEG'
        summed, = struct.unpack_from('>I', b, 4)
        out += b[0x14:0x14 + (summed - 5) * 4]
        n, = struct.unpack_from('>I', b, 0x10)
    return out
rdb = blk(0); assert rdb[:4] == b'RDSK'
di,   = struct.unpack_from('>I', rdb, 0x24)
fshd, = struct.unpack_from('>I', rdb, 0x20)
ffs,  = struct.unpack_from('>I', blk(fshd), 0x48)
open('driveinit_seg.bin', 'wb').write(lseg(di))
open('ffs_seg.bin', 'wb').write(lseg(ffs))
```

Each extracted file should begin with `00 00 03 F3` (a hunk header). The
LSEG chain may add a few zero bytes of padding at the end. LoadSeg ignores
them.

> In principle `L:FastFileSystem` from your own Workbench disks is the same kind
> of file and could be used as `ffs_seg.bin`. **We have not tested this.** Our
> images use the FFS segment we pulled out of the formatter-built reference disk.

---

## Building an image with `mkrochard.py`

Requirements: Python 3 and [amitools](https://github.com/cnvogelg/amitools)
(`pip install amitools` into a virtualenv; the script calls `xdftool`).

```sh
# exact CF size in bytes (CF in a USB reader)
sudo blockdev --getsize64 /dev/sdX

python3 disk-image/mkrochard.py --size 521773056 --boot 60M \
    --out rochard.img --wb /path/to/workbench-tree
```

| Option | Meaning |
|---|---|
| `--size` | Total disk size (`512M`, `1G`, or exact bytes). Use the CF's exact size or slightly less. |
| `--boot` | Size of the bootable first partition (default 60M) |
| `--wb DIR` | Directory tree copied to the root of the boot partition. This is your own Workbench install. Leave it out to get empty partitions. |
| `--bootname` / `--mountname` | Partition names (default `DH0` / `DH1`) |
| `--heads` / `--secs` | Geometry (default 16 heads × 63 sectors) |

It produces two images:

- `rochard.img`: **media order**, written to the CF;
- `rochard.img.logical`: logical order, used as a hardfile in Amiberry.

The disk has two FFS partitions: a bootable `DH0` (BootPri 1) and a `DH1` that
takes the rest. The script renames files whose names contain raw high-bit
characters, so `xdftool` can write them.

We have built working images this way for **AmigaOS 3.1.4** and for
**Workbench 1.3**. The 1.3 image boots on a Kickstart 1.3 A500. To autoboot, the
card must be set for KS 1.3+ (DIP-3 OFF). With DIP-3 ON (the KS 1.2 setting) the
card uses its non-autoboot ROM half.

### Writing to the CF

```sh
sudo dd if=rochard.img of=/dev/sdX bs=1M conv=fsync status=progress
```

Double-check `/dev/sdX`, because `dd` will overwrite whatever disk you point it
at. A quick sanity check afterwards is that block 0 on the CF reads `DRKS`:

```sh
sudo dd if=/dev/sdX bs=512 count=1 2>/dev/null | head -c 4; echo
```

---

## Patching a CF in place

To add or replace a few files without rewriting the whole card (and without the
time and wear of a full `dd`):

```sh
# 1. read the card and make a logical copy
sudo dd if=/dev/sdX of=cf.media bs=1M status=progress
dd if=cf.media of=cf.logical bs=1M conv=swab

# 2. find the partition's cylinder range
rdbtool cf.logical info
#    offset (blocks) = LowCyl * CylBlocks, length = (HighCyl - LowCyl + 1) * CylBlocks
#    e.g. DH0 = cyls 1..N with CylBlocks 1008 -> skip=1008

# 3. cut the partition out, edit it with xdftool, splice it back
dd if=cf.logical of=dh0.hdf bs=512 skip=1008 count=<length>
xdftool dh0.hdf write myprog C/myprog
xdftool dh0.hdf list C
dd if=dh0.hdf of=cf.logical bs=512 seek=1008 conv=notrunc

# 4. back to media order
dd if=cf.logical of=cf.new.media bs=1M conv=swab
```

Then write **only the 512-byte blocks that changed** and verify them:

```python
import os
BS = 512
old, new = open('cf.media', 'rb'), open('cf.new.media', 'rb')
changed, n = [], 0
while True:
    a, b = old.read(BS), new.read(BS)
    if not b: break
    if a != b: changed.append((n, b))
    n += 1
print(len(changed), 'blocks changed')
fd = os.open('/dev/sdX', os.O_RDWR | os.O_SYNC)        # run as root
for blk, data in changed:
    os.pwrite(fd, data, blk * BS)
os.fsync(fd)
bad = [blk for blk, data in changed if os.pread(fd, BS, blk * BS) != data]
print('verify:', 'OK' if not bad else f'{len(bad)} mismatches, first {bad[0]}')
os.close(fd)
```

To be sure the readback comes from the card and not the page cache, eject and
re-insert the card, then run `cmp` on the device against `cf.new.media`.

---

## Testing in Amiberry

**Amiberry** (WinUAE core) emulates the RocHard with its **real ROM** and
autoboots our images. It was our test bench for every disk-image change.
**FS-UAE has RocHard emulation too, but we could not get it to autoboot this
disk.**

Things to know first:

- You need a ROM image. We interleaved our own dumps of the two EPROMs, even
  (U6) first, into one 16 KB file. The checksums match WinUAE's known-good
  "Roctec RocHard RH800C v2" entries: even `C88843CB`, odd `C5B8F068`,
  combined `5C27BE3F`.
- Attach the **logical** image (`*.logical`), not the media-order one. The
  emulator applies the byte-swap itself.
- **Emulators do not model the card's RAM subsystem.** Amiberry's "fast RAM"
  is generic. Use it for disk and boot testing only. RAM problems have to be
  debugged on real hardware.

Config lines (A500 / 68000 setup, plus):

```ini
rochard_rom_file=/path/to/rochard_v2.rom
hardfile2=rw,DH0:/path/to/rochard.img.logical,0,0,0,512,0,,ide0_rochard
uaehf0=hdf,rw,DH0:/path/to/rochard.img.logical,0,0,0,512,0,,ide0_rochard
```

The geometry fields are `0,0,0` (sectors, surfaces and reserved, taken from the
RDB), followed by the block size `512`. The controller is `ide0_rochard`.

Amiberry is also where we ran the RocHard formatter to make the reference disk
(see [above](#obtaining-the-driver-and-ffs-segments)).

---

## rocdiag

[`../amiga-tools/rocdiag/rocdiag`](../amiga-tools/rocdiag) is a small CLI
program that tests the IDE path without the boot ROM or the driver. **Only the
binary survives; we lost the source.**

What it does:

1. Finds the card with `FindConfigDev(2144, 1)`. It prints "card NOT found" if
   the HD board did not autoconfig. That happens when DIP-1 is OFF.
2. Issues IDENTIFY (`$EC`), INITIALIZE DEVICE PARAMETERS (`$91`) and READ SECTOR
   (`$20`) on drive 0 at base + `$8000`, and prints the status and error register
   after each. Healthy results: `$58` after IDENTIFY, `$50` after `$91`, `$58`
   after READ, error `$00`.
3. Reads sector 0 and dumps its first bytes, then checks for `RDSK` and that the
   RDB checksum is valid.

Running it from a serial shell (see the 1.3 shell notes in
[troubleshooting](troubleshooting.md#workbench-13-serial-shell-quirks)) lets you
log the output on a PC. It is most useful with DIP-3 set to **KS 1.2**. In that
mode the card configures but runs no boot code, so a ROM or boot fault cannot
stop the machine before `rocdiag` runs.

History: the first version used `cd_BoardAddr` directly as the task file. It read
an undecoded region and returned a constant, meaningless `status=$73`. The
`+$8000` offset fixed it. Reading sector 0 then showed `DRKS`, which is how we
found the [byte-swap](#the-byte-swap).

---

## WHDLoad notes

WHDLoad runs from the RocHard on a 68000 A500. Some things we learned:

- **Chip RAM is usually the limit, not fast RAM.** A slave's `BaseMem` (chip)
  must fit in chip RAM. [`../disk-image/whdmem.py`](../disk-image/whdmem.py)
  prints a slave's chip and extra-memory needs. It accepts `.slave` files or
  `.lha` archives, and you need `lha` installed for archives:

  ```sh
  python3 disk-image/whdmem.py Game.lha
  # Game.lha:Game/Game.slave: slave v10  BaseMem(chip)=512K  ExpMem(fast ok)=0K  -> needs 1MB chip
  ```

  Anything that reports "needs 1MB chip" requires the
  [1 MB chip RAM upgrade](a500-1mb-chip-upgrade.md).
- **Kickstart images.** Slaves that use the KickEmu need, in `DEVS:Kickstarts`,
  `kick34005.A500` (the 1.3 ROM image) **and** its `kick34005.A500.RTB`
  relocation table. The `.RTB` comes from Aminet `util/boot/skick346.lha`.
- **WHDLoad's debug features don't help on a 68000.** `DebugKey`, `Snoop` and
  friends need a 68010+ (VBR) or an MMU, so a plain A500 can't use them.
- **What we ran:** Arkanoid II and Lemmings 2 work. Speedball 2 (v1.0 install)
  crashed on the real machine but ran fine from a copy of the same install in
  Amiberry. That pointed at hardware: the crashes happened while the UA3
  daughterboard was not seated properly
  (see [troubleshooting](troubleshooting.md#ua3-daughterboard-seating)).
  WHDLoad allocates fast RAM from the top down, so it exercises the top of the
  card's RAM first.
