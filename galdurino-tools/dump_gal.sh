#!/bin/bash
# Wrapper to try cracking a GAL chip.
# Usage: ./dump_gal.sh <chip_ref> <gal_type> [poti]
#   chip_ref: label like UA6, U11, U12, UA3
#   gal_type: 16V8 or 22V10
#   poti: starting poti (default 238)

set -e

REF="${1:-UNKNOWN}"
TYPE="${2:-16V8}"
POTI="${3:-238}"

OUTDIR="${GALD_CRACK_DIR:-$(cd "$(dirname "$0")" && pwd)/crack_attempts}"
mkdir -p "$OUTDIR"

cd "$(dirname "$0")"

if [ "$TYPE" = "22V10" ]; then
    echo "=== Cracking $REF as GAL22V10 starting at poti=$POTI ==="
    ./crack22v10.py "$POTI" 8
else
    # 16V8: single attempt at poti 230 (proven for U14) then a few neighbors
    echo "=== Cracking $REF as GAL16V8 ==="
    for p in 230 231 229 232 228 233 227; do
        echo ""
        echo "--- Attempt at poti=$p ---"
        # Use minimal_read.py or galduread
        python3 minimal_read.py /dev/ttyACM0 "$p" "$OUTDIR/${REF}_${p}.dump" 2>&1 | tail -5
        # Quick check
        python3 -c "
import sys
try:
    lines = open('$OUTDIR/${REF}_${p}.dump').read().splitlines()
    if 'FUSEMAP:' in lines and 'UES:' in lines:
        fuse = ''.join(l for l in lines[lines.index('FUSEMAP:')+1:lines.index('UES:')] if len(l)>20)
        z = fuse.count('0')
        has_cfg = 'CFG:' in lines
        print(f'    zeros={z}, has_cfg={has_cfg}', '*** CRACKED ***' if z >= 200 else '')
        if z >= 200 and has_cfg:
            sys.exit(0)
except Exception as e:
    print(f'    error: {e}')
sys.exit(1)
" && break || true
    done
fi

# Show best result
echo ""
echo "=== Best dump for $REF ==="
python3 <<EOF
import glob, os
files = sorted(glob.glob('$OUTDIR/${REF}_*.dump'))
best = (None, 0)
for f in files:
    lines = open(f).read().splitlines()
    if 'FUSEMAP:' in lines and 'UES:' in lines:
        fuse = ''.join(l for l in lines[lines.index('FUSEMAP:')+1:lines.index('UES:')] if len(l)>20)
        z = fuse.count('0')
        cfg = 'CFG:' in lines
        end = 'END' in lines
        marker = '*** CRACK+CFG+END ***' if z >= 200 and cfg and end else '*** cracked partial ***' if z >= 200 else ''
        print(f'  {os.path.basename(f):40} zeros={z:5} cfg={cfg} end={end} {marker}')
        if z > best[1]:
            best = (f, z)
if best[0]:
    print(f'  BEST: {best[0]} ({best[1]} zeros)')
EOF
