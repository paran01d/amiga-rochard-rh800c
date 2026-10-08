#!/usr/bin/env python3
"""Minimal Galdurino read — mimic exactly what the Java UI does.

No SETDELAYS, no SETPOTI, no discharge, no STATUS. Just open the port,
sleep for the Arduino reset, and send `16v8read <poti>\\n`. Collect output
until END.
"""
import serial, sys, time

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
poti = int(sys.argv[2]) if len(sys.argv) > 2 else 230
out_path = sys.argv[3] if len(sys.argv) > 3 else "minimal.dump"

ser = serial.Serial(port, 9600, timeout=0.2)
print(f"opened {port}")

# Wait for Arduino boot
time.sleep(2.0)
ser.reset_input_buffer()

# EXACT command Java UI sends
cmd = f"16v8read {poti}\n"
ser.write(cmd.encode())
ser.flush()
print(f"sent: {cmd!r}")

# Read until we see END on its own line
end_deadline = time.time() + 30
lines = []
buf = b""
while time.time() < end_deadline:
    chunk = ser.read(256)
    if not chunk:
        continue
    buf += chunk
    while b"\n" in buf:
        line, buf = buf.split(b"\n", 1)
        text = line.decode(errors="replace").rstrip("\r")
        lines.append(text)
        if text.strip() == "END":
            end_deadline = 0
            break
    if end_deadline == 0:
        break

ser.close()

with open(out_path, "w") as f:
    for line in lines:
        f.write(line + "\n")

# Analyze
if "FUSEMAP:" in lines and "UES:" in lines:
    fs = lines.index("FUSEMAP:") + 1
    us = lines.index("UES:")
    fuse = "".join(l for l in lines[fs:us] if len(l) > 20)
    z = fuse.count("0")
    o = fuse.count("1")
    print(f"result: {z} zeros, {o} ones ({100*z/max(1,len(fuse)):.1f}% zeros)")
    print(f"saved -> {out_path}")
else:
    print(f"no FUSEMAP found. First 20 lines:")
    for l in lines[:20]:
        print(f"  {l!r}")
