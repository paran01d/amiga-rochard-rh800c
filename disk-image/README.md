# Disk-image tools

## mkrochard.py: bootable RocHard CF images on Linux

`mkrochard.py` builds a bootable hard-disk image of any size for the RocHard. It reproduces what the original RocHard formatter writes, which we reverse-engineered from a genuine reference disk. Because it runs on Linux, the formatter's out-of-memory size limit doesn't apply.

```sh
python3 mkrochard.py --size 512M --boot 60M --out rochard.img [--wb <dir>]
sudo dd if=rochard.img of=/dev/sdX bs=1M conv=fsync status=progress
```

| Option | Default | Meaning |
|--------|---------|---------|
| `--size` | (required) | Total disk size, such as `512M` or `1G` |
| `--boot` | `60M` | Size of the bootable first partition |
| `--out` | (required) | Output path. Writes `<out>` and `<out>.logical`. |
| `--wb` | none | Directory tree to copy into the boot partition, for example an installed Workbench, so the partition boots |
| `--heads` / `--secs` | 16 / 63 | Geometry |
| `--bootname` / `--mountname` | `DH0` / `DH1` | Device names for the two partitions |
| `--nomount-second` | | Marks the second partition as no-automount |

What the image contains:

- An RDB whose **`rdb_DriveInit` points at the embedded RocHard driver (an LSEG chain)**, and **`RDB[0xD4] = 0x00020000`**. The card's ROM checks for both, and won't autoboot without them.
- Two FFS (`DOS\1`) partitions: a small bootable one (BootPri 1) and a large one for storage.
- An FSHD with an embedded FastFileSystem.

**Two outputs.** The card **byte-swaps the IDE data bus**, so the file you `dd` to the CF (`<out>`) is the byte-swapped "media order" image. `<out>.logical` is the unswapped image. Attach that one to Amiberry as a hardfile.

### Parts you must supply

The RocHard driver and FastFileSystem are copyrighted, so they aren't in this repository. The RocHard **installation disk** (with the formatter that writes them) is on [amiga.resource.cx/exp/rochard](https://amiga.resource.cx/exp/rochard). Put the extracted segments in `rochard_parts/`, next to the script:

| File | Contents |
|------|----------|
| `rochard_parts/driveinit_seg.bin` | The RocHard DriveInit driver as a LoadSeg hunk executable, extracted from the RDB LSEG chain of a disk prepared by the genuine RocHard formatter |
| `rochard_parts/ffs_seg.bin` | The FastFileSystem segment, extracted from the FSHD LSEG chain of the same formatter-built reference disk (FFS v36.03). Using `L:FastFileSystem` from a Workbench disk instead should work but is **untested**. See [obtaining the driver and FFS segments](../docs/ide-and-disk-images.md#obtaining-the-driver-and-ffs-segments). |

Requirements: Python 3, and `xdftool` from [amitools](https://github.com/cnvogelg/amitools), which formats the partitions and populates them.

### Testing in an emulator

Amiberry (WinUAE core) emulates the RocHard with its real ROM and autoboots these images. Configure it with `rochard_rom_file=<rom>` and a hardfile on the **logical** image using the `ide0_rochard` controller, for example `hardfile2=...,0,0,0,512,0,,ide0_rochard`. fs-uae couldn't autoboot it. Neither emulator models the card's RAM subsystem.

## whdmem.py: WHDLoad memory needs

```sh
python3 whdmem.py Game.slave other.lha ...
```

`whdmem.py` prints each WHDLoad slave's chip-RAM requirement (`BaseMem`) and its extra memory (`ExpMem`, which can live in fast RAM), and says whether the game is likely to fit in 0.5 MB of chip RAM. `.lha` archives are scanned for `*.slave` files; that requires the `lha` command.
