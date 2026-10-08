#!/usr/bin/env python3
# Build a bootable ADF from a raw bootblock binary.
#   mkboot.py <in.bin> <out.adf>
# Places the binary at offset 0 (must start with "DOS\0", checksum long at +4),
# computes the 1024-byte bootblock checksum, pads to a 901120-byte (DD) ADF.
import sys

ADF_SIZE = 901120  # 880K DD floppy
BB_SIZE  = 1024    # bootblock = 2 sectors

def bb_checksum(bb):
    # zero the stored checksum field first
    data = bytearray(bb)
    data[4:8] = b"\x00\x00\x00\x00"
    s = 0
    for i in range(0, BB_SIZE, 4):
        s += int.from_bytes(data[i:i+4], "big")
        if s > 0xFFFFFFFF:            # carry wrap
            s = (s & 0xFFFFFFFF) + 1
    return (~s) & 0xFFFFFFFF

def main():
    inp, outp = sys.argv[1], sys.argv[2]
    code = bytearray(open(inp, "rb").read())
    if code[:4] != b"DOS\x00":
        sys.exit("input does not start with DOS\\0")
    if len(code) > BB_SIZE:
        sys.exit(f"bootblock too big: {len(code)} > {BB_SIZE}")
    bb = bytearray(BB_SIZE)
    bb[:len(code)] = code
    ck = bb_checksum(bb)
    bb[4:8] = ck.to_bytes(4, "big")
    adf = bytearray(ADF_SIZE)
    adf[:BB_SIZE] = bb
    open(outp, "wb").write(adf)
    print(f"{outp}: bootblock {len(code)} bytes, checksum {ck:08X}, ADF {ADF_SIZE} bytes")

if __name__ == "__main__":
    main()
