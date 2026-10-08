#!/usr/bin/env python3
"""
mkrochard.py - build a bootable Roctec RocHard RH800C hard-disk image of any size.

Reproduces (on Linux, no formatter/OOM limit) exactly what the RocHard formatter
writes, as reverse-engineered from a genuine reference disk:
  * RDB with rdb_DriveInit -> embedded RocHard driver (LSEG chain)   <- required for autoboot
  * RDB[0xd4] = 0x00020000  (the capacity/valid marker the ROM gates on)
  * partition(s) DosType = DOS\\1 (FFS), boot partition bootable + BootPri 1
  * FSHD -> embedded FastFileSystem (LSEG chain)
Two partitions: a small bootable one + a large mount one.
Outputs a swab (media-order) image ready to `dd` to the CF, plus a .logical copy
you can attach to Amiberry as an .hdf.

Usage:
  mkrochard.py --size 512M --boot 60M --out rochard.img [--wb <dir-to-pack-into-boot>]
"""
import struct, os, sys, argparse, subprocess, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
FFS_SEG = os.path.join(HERE, "rochard_parts", "ffs_seg.bin")
DI_SEG  = os.path.join(HERE, "rochard_parts", "driveinit_seg.bin")
BLOCK = 512
DOS1  = 0x444F5301
HOSTID = 7
NEG1 = 0xFFFFFFFF

def parse_size(s):
    s=str(s).strip().upper()
    mul=1
    if s.endswith('G'): mul=1024**3; s=s[:-1]
    elif s.endswith('M'): mul=1024**2; s=s[:-1]
    elif s.endswith('K'): mul=1024; s=s[:-1]
    return int(float(s)*mul)

def setchk(buf, summedlongs, chkoff=8):
    b=bytearray(buf)
    struct.pack_into('>I', b, chkoff, 0)
    s=sum(struct.unpack('>%dI'%summedlongs, bytes(b[:summedlongs*4]))) & 0xFFFFFFFF
    struct.pack_into('>I', b, chkoff, (-s)&0xFFFFFFFF)
    return bytes(b)

def build_lseg(data, block_nums):
    """Return {block_num: 512-byte LSEG block} for a LoadSeg hunk exe."""
    if len(data)%4: data += b'\x00'*(4-len(data)%4)
    out={}
    per=123  # data longs per block
    for i,bn in enumerate(block_nums):
        chunk=data[i*per*4:(i+1)*per*4]
        clongs=len(chunk)//4
        nxt=block_nums[i+1] if i+1<len(block_nums) else NEG1
        b=bytearray(BLOCK)
        b[0:4]=b'LSEG'
        struct.pack_into('>I', b, 4, 5+clongs)   # SummedLongs
        struct.pack_into('>I', b, 0xc, HOSTID)
        struct.pack_into('>I', b, 0x10, nxt)
        b[0x14:0x14+len(chunk)]=chunk
        out[bn]=setchk(b, 5+clongs)
    return out

def build_rdb(cyls, heads, secs, cylblocks, partlist, fshdlist, driveinit, highrdsk):
    b=bytearray(BLOCK)
    b[0:4]=b'RDSK'
    struct.pack_into('>I', b, 4, 64)          # SummedLongs
    struct.pack_into('>I', b, 0xc, HOSTID)    # HostID
    struct.pack_into('>I', b, 0x10, BLOCK)    # BlockBytes
    struct.pack_into('>I', b, 0x14, 0x1f)     # Flags
    struct.pack_into('>I', b, 0x18, NEG1)     # BadBlockList
    struct.pack_into('>I', b, 0x1c, partlist) # PartitionList
    struct.pack_into('>I', b, 0x20, fshdlist) # FileSysHeaderList
    struct.pack_into('>I', b, 0x24, driveinit)# DriveInit  <-- REQUIRED
    for o in range(0x28,0x40,4): struct.pack_into('>I', b, o, NEG1)  # reserved
    struct.pack_into('>I', b, 0x40, cyls)     # Cylinders
    struct.pack_into('>I', b, 0x44, secs)     # Sectors
    struct.pack_into('>I', b, 0x48, heads)    # Heads
    struct.pack_into('>I', b, 0x4c, 1)        # Interleave
    struct.pack_into('>I', b, 0x50, cyls-1)   # Park
    # --- logical drive characteristics (CORRECT standard offsets) ---
    struct.pack_into('>I', b, 0x80, 0)          # RDBBlocksLo
    struct.pack_into('>I', b, 0x84, cylblocks-1)# RDBBlocksHi (reserved = cyl 0)
    struct.pack_into('>I', b, 0x88, 1)          # LoCylinder (partitions start cyl 1)
    struct.pack_into('>I', b, 0x8c, cyls-1)     # HiCylinder
    struct.pack_into('>I', b, 0x90, cylblocks)  # CylBlocks
    struct.pack_into('>I', b, 0x94, 0)          # AutoParkSeconds
    struct.pack_into('>I', b, 0x98, 0)          # HighRDSKBlock (matches reference)
    struct.pack_into('>I', b, 0xd4, 0x00020000) # <-- REQUIRED capacity marker
    return setchk(b, 64)

def build_part(name, nxt, bootable, bootpri, heads, secs, lowcyl, highcyl, nomount=False):
    b=bytearray(BLOCK)
    b[0:4]=b'PART'
    struct.pack_into('>I', b, 4, 64)          # SummedLongs
    struct.pack_into('>I', b, 0xc, HOSTID)
    struct.pack_into('>I', b, 0x10, nxt)      # Next
    struct.pack_into('>I', b, 0x14, (1 if bootable else 0) | (2 if nomount else 0))  # Flags: bit0 BOOTABLE, bit1 NOMOUNT
    struct.pack_into('>I', b, 0x18, NEG1); struct.pack_into('>I', b, 0x1c, NEG1)
    struct.pack_into('>I', b, 0x20, 0)        # DevFlags
    nm=name.encode('latin1')[:31]
    b[0x24]=len(nm); b[0x25:0x25+len(nm)]=nm  # BSTR drive name
    # DosEnvVec at 0x80 (matches reference)
    env=[17,128,0,heads,1,secs,2,0,0,lowcyl,highcyl,30,0,0x7fffffff,0x00fffffe,bootpri,DOS1,0]
    for i,v in enumerate(env): struct.pack_into('>I', b, 0x80+i*4, v & 0xFFFFFFFF)
    return setchk(b, 64)

def build_fshd(nxt, seglist):
    b=bytearray(BLOCK)
    b[0:4]=b'FSHD'
    struct.pack_into('>I', b, 4, 64)
    struct.pack_into('>I', b, 0xc, HOSTID)
    struct.pack_into('>I', b, 0x10, nxt)      # Next (-1)
    struct.pack_into('>I', b, 0x14, 0)        # Flags
    struct.pack_into('>I', b, 0x20, DOS1)     # DosType
    struct.pack_into('>I', b, 0x24, 1)        # Version
    struct.pack_into('>I', b, 0x28, 0x180)    # PatchFlags (Type + SegList)
    struct.pack_into('>I', b, 0x48, seglist)  # SegListBlocks -> FFS LSEG
    struct.pack_into('>I', b, 0x4c, NEG1)     # GlobalVec
    return setchk(b, 64)

def _fix_name(n):
    # affs mounts surrogate-escape high bytes (e.g. 0xEA='e-circ'); re-decode as Latin-1
    # so the resulting name is valid UTF-8 that xdftool can re-encode to Latin-1.
    if any(0xdc00 <= ord(c) <= 0xdcff for c in n):
        return os.fsencode(n).decode('latin-1')
    return n

def stage_tree(src, dst):
    """Copy a directory tree, sanitising filenames that carry raw high bytes."""
    os.makedirs(dst, exist_ok=True)
    for entry in os.scandir(src):
        d = os.path.join(dst, _fix_name(entry.name))
        if entry.is_dir(follow_symlinks=False):
            stage_tree(entry.path, d)
        else:
            shutil.copy2(entry.path, d)

def main():
    ap=argparse.ArgumentParser(description="Build a bootable RocHard RH800C disk image (any size).")
    ap.add_argument('--size', required=True, help="total disk size, e.g. 512M, 1G")
    ap.add_argument('--boot', default='60M', help="boot partition size (default 60M)")
    ap.add_argument('--out', required=True, help="output image path (writes <out> media-order + <out>.logical)")
    ap.add_argument('--heads', type=int, default=16)
    ap.add_argument('--secs', type=int, default=63)
    ap.add_argument('--bootname', default='DH0')
    ap.add_argument('--mountname', default='DH1')
    ap.add_argument('--wb', default=None, help="directory tree to pack into the boot partition (makes it a bootable WB)")
    ap.add_argument('--nomount-second', action='store_true', help="mark the second partition no-automount")
    a=ap.parse_args()

    for p in (FFS_SEG, DI_SEG):
        if not os.path.exists(p): sys.exit("missing part: "+p)
    ffs=open(FFS_SEG,'rb').read(); di=open(DI_SEG,'rb').read()

    heads,secs=a.heads,a.secs
    cylblocks=heads*secs
    total_blocks=parse_size(a.size)//BLOCK
    total_cyls=total_blocks//cylblocks
    boot_cyls=max(1, parse_size(a.boot)//(cylblocks*BLOCK))
    if boot_cyls>=total_cyls-1: sys.exit("boot partition too large for disk")

    # reserved-area (cyl 0) layout
    nffs=(len(ffs)+491)//492
    ndi =(len(di)+491)//492
    RDB_B=0; PART_BOOT=1; PART_MNT=2; FSHD_B=3
    FFS_START=4; DI_START=FFS_START+nffs
    if DI_START+ndi > cylblocks: sys.exit("reserved cylinder too small; increase heads/secs")
    highrdsk=DI_START+ndi-1

    # partition cylinder ranges
    boot_low, boot_high = 1, boot_cyls
    mnt_low, mnt_high    = boot_cyls+1, total_cyls-1

    print(f"geometry {total_cyls}c/{heads}h/{secs}s  cylblocks={cylblocks}  total {total_blocks} blocks ({total_blocks*512//(1024*1024)}MB)")
    print(f"reserved cyl0: RDB=0 PARTs=1,2 FSHD=3 FFS={FFS_START}..{FFS_START+nffs-1} DriveInit={DI_START}..{DI_START+ndi-1}")
    print(f"boot  '{a.bootname}': cyls {boot_low}..{boot_high}  ({(boot_high-boot_low+1)*cylblocks*512//(1024*1024)}MB, BOOTABLE)")
    print(f"mount '{a.mountname}': cyls {mnt_low}..{mnt_high}  ({(mnt_high-mnt_low+1)*cylblocks*512//(1024*1024)}MB)")

    # build reserved blocks
    blocks={}
    blocks[RDB_B]=build_rdb(total_cyls,heads,secs,cylblocks,PART_BOOT,FSHD_B,DI_START,highrdsk)
    blocks[PART_BOOT]=build_part(a.bootname, PART_MNT, True, 1, heads,secs, boot_low,boot_high)
    blocks[PART_MNT]=build_part(a.mountname, NEG1, False, 0, heads,secs, mnt_low,mnt_high, nomount=a.nomount_second)
    blocks[FSHD_B]=build_fshd(NEG1, FFS_START)
    blocks.update(build_lseg(ffs, list(range(FFS_START,FFS_START+nffs))))
    blocks.update(build_lseg(di,  list(range(DI_START, DI_START+ndi))))

    # create image
    out=a.out+'.logical'
    with open(out,'wb') as f:
        f.truncate(total_blocks*BLOCK)
        for bn,data in blocks.items():
            f.seek(bn*BLOCK); f.write(data)

    # format + populate partitions via xdftool
    def fmt_partition(low,high,name,wbdir):
        nblocks=(high-low+1)*cylblocks
        tmp=tempfile.mktemp(suffix='.hdf')
        subprocess.run(['xdftool',tmp,'create','size=%d'%(nblocks*BLOCK)],check=True)
        subprocess.run(['xdftool',tmp,'format',name,'ffs'],check=True)
        if wbdir:
            # write each top-level entry so the tree lands at the volume ROOT
            for child in sorted(os.listdir(wbdir)):
                subprocess.run(['xdftool',tmp,'write',os.path.join(wbdir,child)],check=True)
        with open(tmp,'rb') as pf, open(out,'r+b') as mf:
            mf.seek(low*cylblocks*BLOCK); mf.write(pf.read())
        os.remove(tmp)

    wbstage=None
    if a.wb:
        wbstage=tempfile.mkdtemp(prefix='rhwb_')
        stage_tree(a.wb, wbstage)
    print("formatting boot partition...");  fmt_partition(boot_low,boot_high,a.bootname,wbstage)
    print("formatting mount partition..."); fmt_partition(mnt_low,mnt_high,a.mountname,None)
    if wbstage: shutil.rmtree(wbstage, ignore_errors=True)

    # swab -> media order for the real CF
    print("byte-swapping -> media order for CF ...")
    with open(out,'rb') as f, open(a.out,'wb') as g:
        while True:
            chunk=f.read(1024*1024)
            if not chunk: break
            b=bytearray(chunk)
            b[0::2],b[1::2]=b[1::2],b[0::2]
            g.write(bytes(b))
    print(f"\nDONE:\n  {a.out}          (media order - dd this to the CF)\n  {out}  (logical - attach to Amiberry as .hdf)")
    print(f"  dd if={a.out} of=/dev/sdX bs=1M conv=fsync status=progress")

if __name__=='__main__':
    main()
