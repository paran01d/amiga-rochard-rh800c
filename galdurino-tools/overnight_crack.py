#!/usr/bin/env python3
"""
Autonomous overnight crack attempt for a locked Lattice GAL22V10B.

Runs galduread.py repeatedly with varied delay/poti combinations until either:
  - a dump shows evidence of a successful crack (fuse map has meaningful zeros)
  - wallclock passes the stop deadline

All progress logged to overnight.log. Dumps saved to overnight_dumps/.
Safe for unattended operation:
  - Restores default delays on exit (10 0 100 0)
  - Caps poti max at 235 to keep VPP below 25V C8 rating
  - Sleeps briefly between attempts so the DC-DC has recovery time
"""

import subprocess, time, sys, os, itertools, random, signal, re
import os
HERE = os.path.dirname(os.path.abspath(__file__))

# --- CONFIG ---
PORT      = "/dev/ttyACM0"
STOP_EPOCH = int(sys.argv[1]) if len(sys.argv) > 1 else 0    # required
LOG_PATH  = os.environ.get("GALD_LOG", os.path.join(HERE, "overnight.log"))
DUMP_DIR  = os.environ.get("GALD_DUMP_DIR", os.path.join(HERE, "overnight_dumps"))
GALDUREAD = os.path.join(HERE, "galduread.py")

# Delay combinations (d0=poti-settle, d1=vpp-to-vcc, d2=vcc-hold, d3=post-pulse; d3=-1 skips pulse)
DELAY_VARIANTS = [
    (10, 0, 100, 0),      # readme default
    (10, 0, 100, -1),     # skip VPP off/on pulse entirely
    (20, 5, 200, 20),     # slower everything
    (5, 0, 50, 0),        # faster
    (30, 0, 300, 30),     # very slow
    (10, 0, 100, 50),     # long post-pulse settle
    (50, 0, 100, 0),      # long initial poti settle
    (100, 0, 100, 0),     # much longer initial poti settle
    (10, 10, 100, 10),    # both mid-delays present
    (10, 0, 500, 0),      # very long VCC-first hold before read
    (10, 0, 1000, -1),    # very long, no pulse
    (5, 0, 100, 5),       # short pulse variant
    (100, 100, 100, 100), # everything long
    (0, 0, 0, 0),         # everything zero (max speed)
    (0, 0, 0, -1),        # everything zero, no pulse
    (200, 0, 100, 0),     # very long VPP-before-VCC settle
    (10, 50, 100, 0),     # long VPP-to-VCC gap (unusual)
    (10, 0, 100, 200),    # long post-pulse
]

# Try both with and without SWEEP-style discharge preamble
DISCHARGE_VARIANTS = [False, True]

# Poti windows. Max 235 to stay within safe VPP for 25V C8.
POTI_WINDOWS = [
    ("readme-9V-window",   list(range(125, 136))),
    ("readme-12V-window",  list(range(175, 186))),
    ("readme-15V-window",  list(range(215, 226))),
    ("low-8V-window",      list(range(115, 125))),
    ("verylow-7V-window",  list(range(105, 115))),
    ("high-16V-window",    list(range(226, 236))),
    ("mid1-10V-window",    list(range(155, 165))),
    ("mid2-13V-window",    list(range(190, 200))),
]

# --- STATE ---
attempt_count = 0
success_seen = False
start_time = time.time()

def log(msg, tee_stdout=True):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")
    if tee_stdout:
        print(line, flush=True)

def time_left():
    return STOP_EPOCH - int(time.time())

def check_dump_for_crack(path):
    """Parse the dump. Returns (zeros, ones, cracked_boolean). Cracked when
    the fuse map has meaningfully many zeros (>200) after tail-strip."""
    try:
        with open(path) as f:
            lines = f.read().splitlines()
    except OSError:
        return (0, 0, False)
    if "FUSEMAP:" not in lines or "UES:" not in lines:
        return (0, 0, False)
    start = lines.index("FUSEMAP:") + 1
    end   = lines.index("UES:")
    # Trim address-counter tail (Java reads first 132 of 138 chars per row)
    fuse = "".join(r[:132] for r in lines[start:end] if len(r) >= 132)
    if not fuse:
        return (0, 0, False)
    zeros = fuse.count("0")
    ones  = fuse.count("1")
    # "Cracked" heuristic: at least 50 zeros somewhere in the fuse map.
    # A truly cracked Draft 05 read should have ~5240 zeros; a fully-locked
    # chip returns exactly 0 zeros. Anything in between is worth investigating.
    return (zeros, ones, zeros >= 50)

def run_read(delays, poti, out_prefix, discharge=False):
    """Run one read via galduread.py. Returns (dump_path, vpp_string) tuple,
    or (None, None) on failure."""
    dpath = os.path.join(DUMP_DIR, f"{out_prefix}")
    delays_str = " ".join(str(d) for d in delays)
    cmd = [
        GALDUREAD,
        "--port", PORT,
        "--type", "22V10",
        "--delays", delays_str,
        "--poti", str(poti),
        "--out", dpath,
    ]
    if discharge:
        cmd.append("--discharge")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=80)
        if r.returncode != 0:
            log(f"    READ FAILED rc={r.returncode}: {r.stderr[-200:]}", tee_stdout=False)
            return (None, None)
    except subprocess.TimeoutExpired:
        log(f"    READ TIMEOUT: {delays} poti={poti}", tee_stdout=False)
        return (None, None)
    # Extract measured VPP from galduread's stdout ("VPP=12.1V" format)
    m = re.search(r"VPP=([-\d.?]+V?)", r.stdout or "")
    vpp = m.group(1) if m else "?"
    return (dpath, vpp)

def restore_defaults():
    """Set delays back to readme defaults so future manual reads aren't affected."""
    log("[restore] SETDELAYS 10 0 100 0")
    subprocess.run([
        GALDUREAD, "--port", PORT, "--type", "22V10",
        "--delays", "10 0 100 0", "--poti", "180",
        "--out", os.path.join(DUMP_DIR, "restore.dump"),
    ], capture_output=True, timeout=60)

def sigterm(_signum, _frame):
    log("!!! SIGTERM received — restoring defaults and exiting")
    restore_defaults()
    sys.exit(0)

# --- MAIN ---
def main():
    global attempt_count, success_seen
    signal.signal(signal.SIGTERM, sigterm)
    os.makedirs(DUMP_DIR, exist_ok=True)

    if STOP_EPOCH == 0:
        sys.exit("usage: overnight_crack.py <stop_epoch>")

    log("=" * 60)
    log(f"OVERNIGHT CRACK ATTEMPT STARTED (target: locked GAL22V10B)")
    log(f"Stop at epoch {STOP_EPOCH} = {time.ctime(STOP_EPOCH)}")
    log(f"{len(DELAY_VARIANTS)} delay variants × {sum(len(w) for _,w in POTI_WINDOWS)} poti values")
    log("=" * 60)

    # Build the full attack matrix: (delay_variant_name, delays, poti_window_name, poti, discharge)
    matrix = []
    for di, delays in enumerate(DELAY_VARIANTS):
        for wname, potis in POTI_WINDOWS:
            for poti in potis:
                for discharge in DISCHARGE_VARIANTS:
                    matrix.append((di, delays, wname, poti, discharge))

    # Deterministic shuffle so repeated runs cover different ground
    rng = random.Random(time.time())
    rng.shuffle(matrix)
    log(f"Attack matrix size: {len(matrix)} combinations")

    for iter_num in itertools.count(1):
        log(f"--- ITERATION {iter_num} (matrix will be reshuffled after each pass) ---")
        for di, delays, wname, poti, discharge in matrix:
            if time_left() <= 30:
                log(f"!!! Only {time_left()}s left — stopping")
                return
            if success_seen:
                return
            attempt_count += 1
            dc = "dc" if discharge else "  "
            prefix = f"i{iter_num}_d{di}_p{poti}_{dc}"
            log(f"  [{attempt_count:4d}] {dc} delays={delays} poti={poti} ({wname}) ⇒ {prefix}")
            path, vpp = run_read(delays, poti, prefix, discharge=discharge)
            if path is None:
                time.sleep(1)
                continue
            zeros, ones, cracked = check_dump_for_crack(path)
            marker = "  *** CRACK LIKELY ***" if cracked else ("  ~ partial ~" if zeros > 0 else "")
            log(f"           result: {zeros} zeros, {ones} ones  VPP={vpp}{marker}")
            if cracked:
                success_seen = True
                log("!!! POSSIBLE CRACK !!!")
                log(f"    dump path: {path}")
                # Repeat this same config three times to confirm it's reproducible
                for confirm_attempt in range(3):
                    p2, vpp2 = run_read(delays, poti, f"{prefix}_confirm{confirm_attempt}", discharge=discharge)
                    if p2:
                        z2, o2, c2 = check_dump_for_crack(p2)
                        log(f"    confirm attempt {confirm_attempt}: {z2} zeros, {o2} ones VPP={vpp2}"
                            f" {'(cracked)' if c2 else '(NOT cracked — noise?)'}")
                return
            # Between attempts: brief pause to let DC-DC settle & Arduino recover
            time.sleep(0.5)

        # End of matrix pass — reshuffle for next iteration
        rng.shuffle(matrix)
        log(f"--- End of iteration {iter_num}, {attempt_count} attempts, "
            f"{time_left()}s remaining ---")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("KeyboardInterrupt")
    finally:
        restore_defaults()
        log(f"=== DONE. Attempts: {attempt_count}, "
            f"elapsed: {int(time.time()-start_time)}s, "
            f"success: {success_seen} ===")
