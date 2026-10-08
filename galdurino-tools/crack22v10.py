#!/usr/bin/env python3
"""Try to re-crack UA4 GAL22V10 at poti=238 (and neighbors).

For each attempt: send ONLY `22v10read <poti>\\n`, capture until END, save,
and analyze. Stops early if a crack is detected (>200 zeros in fuse map).

Usage:
    ./crack22v10.py [start_poti] [count]

Defaults: start at 238, 8 attempts, sweeping ±3 around 238.
"""
import serial, sys, time, os, re
import os

port = "/dev/ttyACM0"
start_poti = int(sys.argv[1]) if len(sys.argv) > 1 else 238
attempts = int(sys.argv[2]) if len(sys.argv) > 2 else 8
out_dir = os.environ.get("GALD_CRACK_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "crack_attempts"))
os.makedirs(out_dir, exist_ok=True)

# Try in order: exact target, then wider around it
poti_order = [start_poti, start_poti-1, start_poti+1, start_poti-2, start_poti+2,
              start_poti-3, start_poti+3, start_poti+4][:attempts]

ser = serial.Serial(port, 9600, timeout=0.2)
print(f"opened {port}")
time.sleep(2.0)  # Arduino reset
ser.reset_input_buffer()

def do_read(poti):
    ser.reset_input_buffer()
    cmd = f"22v10read {poti}\n"
    ser.write(cmd.encode())
    ser.flush()

    end_deadline = time.time() + 45  # 22V10 takes longer than 16V8
    lines = []
    buf = b""
    while time.time() < end_deadline:
        chunk = ser.read(256)
        if not chunk:
            continue
        buf += chunk
        # Strip CR-symbol variants
        buf = buf.replace(b'\xe2\x90\x8d', b'')
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            text = line.decode(errors="replace").rstrip("\r")
            lines.append(text)
            if text.strip() == "END":
                return lines
    return lines  # incomplete

def analyze(lines):
    if "FUSEMAP:" not in lines or "UES:" not in lines:
        return {'ok': False, 'reason': 'no FUSEMAP/UES markers'}
    fs = lines.index("FUSEMAP:") + 1
    us = lines.index("UES:")
    fuse_rows = [l for l in lines[fs:us] if len(l) == 138]
    if len(fuse_rows) != 44:
        return {'ok': False, 'reason': f'expected 44 fuse rows, got {len(fuse_rows)}'}
    fuse = "".join(r[:132] for r in fuse_rows)
    zeros = fuse.count('0')
    has_cfg = "CFG:" in lines
    has_end = "END" in lines
    cfg = lines[lines.index("CFG:")+1] if has_cfg else ""
    return {
        'ok': True,
        'zeros': zeros,
        'ones': fuse.count('1'),
        'cracked': zeros >= 200,
        'has_cfg': has_cfg,
        'has_end': has_end,
        'cfg': cfg,
    }

best = None
for i, poti in enumerate(poti_order):
    print(f"\n[+] attempt {i+1}/{len(poti_order)}: poti={poti}", flush=True)
    lines = do_read(poti)
    result = analyze(lines)
    if not result['ok']:
        print(f"    BAD: {result['reason']}", flush=True)
        continue

    path = os.path.join(out_dir, f"attempt_{i+1:02d}_p{poti}.dump")
    with open(path, 'w') as f:
        for l in lines:
            f.write(l + '\n')

    marker = " *** CRACKED ***" if result['cracked'] else ""
    cfg_note = f" (CFG: {result['cfg']})" if result['has_cfg'] else " (NO CFG)"
    print(f"    {result['zeros']:5} zeros, {result['ones']:5} ones{marker}", flush=True)
    print(f"    has_cfg={result['has_cfg']} has_end={result['has_end']}{cfg_note}", flush=True)
    print(f"    saved -> {path}", flush=True)

    if result['cracked'] and result['has_cfg']:
        print(f"\n[!] FULL CRACK WITH CFG at poti={poti} !!!")
        best = (poti, path, result)
        break
    elif result['cracked']:
        print(f"[!] Cracked but no CFG. Trying next attempt for a complete read.")
        if not best or result['zeros'] > best[2]['zeros']:
            best = (poti, path, result)

ser.close()
print("\n" + "="*60)
if best:
    poti, path, r = best
    tag = "with CFG" if r['has_cfg'] else "WITHOUT CFG"
    print(f"BEST: poti={poti} ({r['zeros']} zeros) {tag}")
    print(f"      {path}")
else:
    print("No crack in any attempt.")
