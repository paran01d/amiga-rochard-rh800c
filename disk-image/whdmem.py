#!/usr/bin/env python3
"""whdmem.py - print a WHDLoad slave's chip (BaseMem) and extra (ExpMem) memory needs.
Usage: whdmem.py <file.slave | archive.lha> ...   (lha archives are scanned for *.slave)"""
import sys, struct, subprocess, tempfile, os, glob

def slave_info(data):
    i = data.find(b'WHDLOADS')
    if i < 4: return None
    v, flags, base = struct.unpack('>HHI', data[i+8:i+16])
    exp = struct.unpack('>I', data[i+24+4:i+24+8])[0] if v >= 8 else 0  # ws_ExpMem after keydebug/keyexit
    return v, base, exp

def report(name, data):
    r = slave_info(data)
    if not r: print(f"{name}: not a WHDLoad slave"); return
    v, base, exp = r
    fit = "likely OK on 0.5MB chip" if base <= 0x60000 else "needs 1MB chip"
    print(f"{name}: slave v{v}  BaseMem(chip)={base//1024}K  ExpMem(fast ok)={exp//1024}K  -> {fit}")

for arg in sys.argv[1:]:
    if arg.lower().endswith('.lha'):
        with tempfile.TemporaryDirectory() as t:
            subprocess.run(['lha', 'xqw=' + t, os.path.abspath(arg)], check=True)
            for f in glob.glob(t + '/**/*', recursive=True):
                if f.lower().endswith('.slave'):
                    report(os.path.basename(arg) + ':' + os.path.relpath(f, t), open(f, 'rb').read())
    else:
        report(arg, open(arg, 'rb').read())
