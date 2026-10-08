#!/usr/bin/env python3
"""Interactive Python UI for Galdurino - replaces the Java UI.

Runs in a terminal. Provides:
  status - show Galdurino Delays/Poti/VCC/VPP/VPP-voltage
  poti <val>  - set poti value
  identify [poti] - identify chip
  read16 [poti] [retries] - read GAL16V8 (retries=N attempts; stop early on crack)
  read20 [poti] [retries] - read GAL20V8 (retries=N attempts; stop early on crack)
  read22 [poti] [retries] - read GAL22V10 (retries=N attempts; stop early on crack)
  spread <read16|read20|read22> start=N end=N step=N - sweep poti range
                                                        also positional: spread read22 210 240 1
                                                        stops early on full crack+CFG
  hold <poti> <seconds> [vpp] [read16|read20|read22]
                               - set poti, optionally VPP-on for N seconds, optionally
                                  read at that voltage before returning.
                                  e.g. hold 255 3 vpp read22
  prime <read22> <read_poti> <prime_poti> <hold_secs> [repeats]
                               - voltage-priming crack: hold VPP high at prime_poti,
                                  then read at prime_poti (intermediate), then drop to
                                  read_poti and read (final).
                                  e.g. prime read22 180 255 3 3  (3 primes at 255, read at 180)
  jed <input.dump> <output.jed> [16v8|22v10] - convert dump to JED
  decompile <input.jed> [16v8|22v10] - decompile via jedutil
  save <ref> - save last-read dump to $ROCTEC_DIR/<ref>_original.dump (default: current dir)
  raw <cmd>  - send raw command to Arduino
  quit
"""
import serial, sys, time, os, subprocess, re, glob, atexit
import os
HERE = os.path.dirname(os.path.abspath(__file__))

# Enable readline for arrow-key history, line editing, Ctrl+R search
try:
    import readline
    HIST_FILE = os.path.expanduser("~/.galdurino_history")
    try:
        readline.read_history_file(HIST_FILE)
    except FileNotFoundError:
        pass
    readline.set_history_length(1000)
    atexit.register(readline.write_history_file, HIST_FILE)
except ImportError:
    pass  # non-Linux fallback: no history, but everything else works

PORT = "/dev/ttyACM0"
JEDUTIL = os.environ.get("JEDUTIL", "jedutil")          # MAME jedutil, from PATH or $JEDUTIL
GALD2JED_16V8 = os.path.join(HERE, "gald2jed.py")
GALD2JED_22V10 = os.path.join(HERE, "gald2jed_22v10.py")
ROCTEC_DIR = os.environ.get("ROCTEC_DIR", os.getcwd())   # where .dump/.jed files are written
CRACKS_DIR = os.environ.get("GALD_CRACK_DIR", os.path.join(HERE, "crack_attempts"))


class GaldTerminal:
    def __init__(self, port):
        self.ser = serial.Serial(port, 9600, timeout=0.2)
        print(f"[+] opened {port}, waiting for Arduino reset...")
        time.sleep(2.0)
        self.ser.reset_input_buffer()
        self.last_dump = None  # store the most recent read
        self.last_dump_type = None

    def send(self, cmd):
        """Send a command, no response wait."""
        self.ser.reset_input_buffer()
        self.ser.write((cmd + "\n").encode())
        self.ser.flush()

    def read_response(self, sentinel_pred, timeout=30, progress=True):
        """Read lines until sentinel_pred(line.strip()) returns True.
        Returns list of lines. Strips CR-symbol and \\r variants.
        Prints a spinner + line count while receiving so the user can see
        the read is in progress (Galdurino 22V10 reads take ~20s)."""
        CR_SYMBOL = b'\xe2\x90\x8d'
        SPINNER = "|/-\\"
        end = time.time() + timeout
        lines = []
        buf = b""
        total_bytes = 0
        spin_i = 0
        last_print = 0.0
        try:
            while time.time() < end:
                chunk = self.ser.read(256)
                if not chunk:
                    # Update spinner even during idle bytes
                    if progress and sys.stdout.isatty() and (time.time() - last_print) > 0.15:
                        sys.stdout.write(
                            f"\r    {SPINNER[spin_i % 4]}  {len(lines):4d} lines  "
                            f"{total_bytes:6d} bytes   ")
                        sys.stdout.flush()
                        spin_i += 1
                        last_print = time.time()
                    continue
                buf += chunk.replace(CR_SYMBOL, b'')
                total_bytes += len(chunk)
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    text = line.decode(errors="replace").rstrip("\r")
                    lines.append(text)
                    if sentinel_pred(text.strip()):
                        if progress and sys.stdout.isatty():
                            sys.stdout.write("\r" + " " * 60 + "\r")
                            sys.stdout.flush()
                        return lines
                # Spinner update on any data
                if progress and sys.stdout.isatty() and (time.time() - last_print) > 0.15:
                    sys.stdout.write(
                        f"\r    {SPINNER[spin_i % 4]}  {len(lines):4d} lines  "
                        f"{total_bytes:6d} bytes   ")
                    sys.stdout.flush()
                    spin_i += 1
                    last_print = time.time()
        finally:
            if progress and sys.stdout.isatty():
                sys.stdout.write("\r" + " " * 60 + "\r")
                sys.stdout.flush()
        return lines  # timeout

    def cmd_status(self):
        self.send("STATUS")
        lines = self.read_response(lambda s: s.startswith("VPP-voltage:"), timeout=5)
        for l in lines:
            print(f"    {l}")

    def cmd_setpoti(self, val):
        self.send(f"SETPOTI {val}")
        time.sleep(0.35)  # firmware delays 300ms then prints VPP
        lines = self.read_response(lambda s: s.startswith("VPP-voltage:"), timeout=3)
        for l in lines:
            print(f"    {l}")

    def cmd_identify(self, poti):
        self.send(f"IDENTIFY {poti}")
        lines = self.read_response(lambda s: s == "ID end", timeout=8)
        for l in lines:
            print(f"    {l}")

    def cmd_read(self, gal_type, poti, retries=1):
        """Read a GAL fuse map. retries = max attempts (default 1).
        Stops early if a crack succeeds (zeros >= 200)."""
        if retries < 1:
            retries = 1
        cmd = {"16V8": "16V8READ", "20V8": "20V8READ", "22V10": "22V10READ"}[gal_type]
        result = None
        for attempt in range(1, retries + 1):
            if retries > 1:
                print(f"    --- attempt {attempt}/{retries} ---")
            print(f"    sending {cmd} {poti}...")
            self.send(f"{cmd} {poti}")
            lines = self.read_response(lambda s: s == "END", timeout=45)
            # Analyze
            result = self._analyze(lines)
            for l in lines[:10]:
                print(f"    {l}")
            print(f"    ...")
            print(f"    (received {len(lines)} lines total)")
            print(f"    fuse zeros: {result['zeros']}, ones: {result['ones']}")
            print(f"    has_cfg: {result['has_cfg']}, has_end: {result['has_end']}")
            self.last_dump = lines
            self.last_dump_type = gal_type
            if result['zeros'] >= 200:
                print(f"    *** CRACKED ***")
                if retries > 1 and attempt < retries:
                    print(f"    crack successful — stopping retries")
                return result
            if attempt < retries:
                print(f"    no crack (zeros={result['zeros']}), retrying...")
        return result

    @staticmethod
    def _analyze(lines):
        result = {'zeros': 0, 'ones': 0, 'has_cfg': False, 'has_end': False}
        result['has_cfg'] = "CFG:" in lines
        result['has_end'] = "END" in lines
        if "FUSEMAP:" in lines and "UES:" in lines:
            fs = lines.index("FUSEMAP:") + 1
            us = lines.index("UES:")
            fuse = "".join(l for l in lines[fs:us] if len(l) > 20)
            # For 22V10 rows are 138 chars: first 132 are fuses, last 6 are counter
            # For 16V8 rows are 64 chars: all fuses
            # Simpler: count all 0/1 chars in fuse section
            result['zeros'] = fuse.count('0')
            result['ones'] = fuse.count('1')
        return result

    def save_dump(self, ref):
        if not self.last_dump:
            print("    No dump to save. Do a read first.")
            return
        os.makedirs(CRACKS_DIR, exist_ok=True)
        crack_path = os.path.join(CRACKS_DIR, f"{ref}.dump")
        with open(crack_path, "w") as f:
            for l in self.last_dump:
                f.write(l + "\n")
        print(f"    saved -> {crack_path}")
        # Also copy to Roctec dir if it's a real crack
        result = self._analyze(self.last_dump)
        if result['zeros'] >= 200:
            roctec_path = os.path.join(ROCTEC_DIR, f"{ref}_original.dump")
            with open(roctec_path, "w") as f:
                for l in self.last_dump:
                    f.write(l + "\n")
            print(f"    also -> {roctec_path} (real crack)")

    def raw(self, cmd):
        self.send(cmd)
        time.sleep(0.5)
        lines = self.read_response(lambda s: False, timeout=2)  # timeout-based
        for l in lines:
            print(f"    {l}")


def do_jed(dump_path, jed_path, gal_type):
    if not os.path.exists(dump_path):
        print(f"    dump not found: {dump_path}")
        return
    script = GALD2JED_22V10 if "22" in gal_type else GALD2JED_16V8
    r = subprocess.run(["python3", script, dump_path, jed_path], capture_output=True, text=True)
    print(r.stdout, end='')
    if r.returncode != 0:
        print(r.stderr, end='')


def do_decompile(jed_path, gal_type):
    if not os.path.exists(jed_path):
        print(f"    JED not found: {jed_path}")
        return
    gal_name = {"16v8": "GAL16V8", "20v8": "GAL20V8", "22v10": "GAL22V10"}[gal_type.lower()]
    r = subprocess.run([JEDUTIL, "-view", jed_path, gal_name], capture_output=True, text=True)
    print(r.stdout, end='')


def main():
    print("Galdurino Python UI - type 'help' for commands")
    try:
        term = GaldTerminal(PORT)
    except Exception as e:
        print(f"[!] Could not open {PORT}: {e}")
        print("    Is the Arduino connected?")
        sys.exit(1)

    while True:
        try:
            line = input("gald> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        try:
            if cmd in ("quit", "exit", "q"):
                break
            elif cmd == "help":
                print(__doc__)
            elif cmd == "status":
                term.cmd_status()
            elif cmd == "poti":
                if not args:
                    print("    usage: poti <0..255>")
                    continue
                term.cmd_setpoti(int(args[0]))
            elif cmd == "identify":
                poti = int(args[0]) if args else 180
                term.cmd_identify(poti)
            elif cmd == "read16":
                poti = int(args[0]) if args else 230
                retries = int(args[1]) if len(args) > 1 else 1
                term.cmd_read("16V8", poti, retries=retries)
            elif cmd == "read20":
                poti = int(args[0]) if args else 230
                retries = int(args[1]) if len(args) > 1 else 1
                term.cmd_read("20V8", poti, retries=retries)
            elif cmd == "read22":
                poti = int(args[0]) if args else 238
                retries = int(args[1]) if len(args) > 1 else 1
                term.cmd_read("22V10", poti, retries=retries)
            elif cmd == "spread":
                if len(args) < 2:
                    print("    usage: spread <read16|read20|read22> [start=N] [end=N] [step=N]")
                    print("           or:  spread read22 210 240 1")
                    continue
                sub = args[0].lower()
                gal_type = {"read16": "16V8", "read20": "20V8", "read22": "22V10"}.get(sub)
                if not gal_type:
                    print(f"    unknown read command: {sub}")
                    continue
                # Parse start/end/step from either named or positional args
                params = {"start": 210, "end": 240, "step": 1}
                positional = []
                for a in args[1:]:
                    if "=" in a:
                        k, v = a.split("=", 1)
                        if k in params:
                            params[k] = int(v)
                    else:
                        positional.append(int(a))
                if positional:
                    if len(positional) >= 1: params["start"] = positional[0]
                    if len(positional) >= 2: params["end"] = positional[1]
                    if len(positional) >= 3: params["step"] = positional[2]
                start, end, step = params["start"], params["end"], params["step"]
                if step <= 0:
                    print("    step must be > 0")
                    continue
                potis = list(range(start, end + 1, step))
                print(f"    spread over {len(potis)} poti values ({start}..{end} step {step})")
                best = None  # (poti, zeros, lines, has_cfg)
                results = []  # per-attempt summary
                for i, p in enumerate(potis, 1):
                    print(f"\n  [{i}/{len(potis)}] poti={p}")
                    result = term.cmd_read(gal_type, p)
                    results.append((p, result))
                    if result['zeros'] > 200 and (best is None or result['zeros'] > best[1]):
                        best = (p, result['zeros'], term.last_dump, result['has_cfg'])
                        if result['has_cfg']:
                            print(f"    *** FULL CRACK with CFG at poti={p} — stopping spread ***")
                            break
                # Summary
                print("\n" + "=" * 60)
                print(f"    Spread summary ({gal_type}, {len(results)} attempts):")
                for p, r in results:
                    marker = "  *** CRACK ***" if r['zeros'] > 200 else ""
                    print(f"      poti={p:3d}  zeros={r['zeros']:5d}  cfg={r['has_cfg']}"
                          f"  end={r['has_end']}{marker}")
                if best:
                    # Restore best dump so `save` picks it up (loop overwrote last_dump)
                    term.last_dump = best[2]
                    term.last_dump_type = gal_type
                    print(f"    BEST: poti={best[0]} with {best[1]} zeros (cfg={best[3]})")
                    print(f"    Best dump stored as last_dump — use 'save <ref>' to persist.")
                else:
                    print("    No crack detected in this spread.")
            elif cmd == "hold":
                # hold <poti> <seconds> [vpp] [read16|read20|read22]
                # Set poti + optionally VPP-on for N seconds, then optionally read at that voltage
                if len(args) < 2:
                    print("    usage: hold <poti> <seconds> [vpp] [read16|read20|read22]")
                    print("           e.g. hold 255 3 vpp read22")
                    continue
                pval = int(args[0])
                secs = float(args[1])
                use_vpp = "vpp" in [a.lower() for a in args[2:]]
                read_after = None
                for a in args[2:]:
                    if a.lower() in ("read16", "read20", "read22"):
                        read_after = {"read16": "16V8", "read20": "20V8", "read22": "22V10"}[a.lower()]
                print(f"    setting poti={pval}, VPP={'on' if use_vpp else 'off'}, hold for {secs}s"
                      + (f", read {read_after} at hold voltage" if read_after else ""))
                term.send(f"SETPOTI {pval}")
                time.sleep(0.35)
                term.ser.reset_input_buffer()
                if use_vpp:
                    term.send("VPP ON")
                    time.sleep(0.2)
                    term.ser.reset_input_buffer()
                # Countdown
                start = time.time()
                while time.time() - start < secs:
                    remain = secs - (time.time() - start)
                    if sys.stdout.isatty():
                        sys.stdout.write(f"\r    holding... {remain:5.1f}s remaining   ")
                        sys.stdout.flush()
                    time.sleep(0.1)
                if sys.stdout.isatty():
                    sys.stdout.write("\r" + " " * 40 + "\r")
                    sys.stdout.flush()
                # Read AT the hold voltage (before releasing VPP) if requested
                if read_after:
                    if use_vpp:
                        # The read routine turns VPP on internally too, but sequence
                        # matters — turn ours off cleanly first so the read routine
                        # has a clean starting state at the target poti
                        term.send("VPP OFF")
                        time.sleep(0.15)
                        term.ser.reset_input_buffer()
                    print(f"    reading at hold voltage (poti={pval})...")
                    term.cmd_read(read_after, pval)
                else:
                    if use_vpp:
                        term.send("VPP OFF")
                        time.sleep(0.2)
                        term.ser.reset_input_buffer()
                    print(f"    done")

            elif cmd == "prime":
                # prime <read16|read20|read22> <read_poti> <prime_poti> <hold_secs> [repeats]
                # Voltage priming recipe: set poti to prime voltage with VPP on for N seconds,
                # then drop back to read voltage and immediately read.
                # This defeats some Lattice security-fuse caches.
                if len(args) < 4:
                    print("    usage: prime <read16|read20|read22> <read_poti> <prime_poti> <hold_secs> [repeats]")
                    print("           e.g. prime read22 180 255 3 3   (3 primes at 255, read at 180)")
                    continue
                sub = args[0].lower()
                gal_type = {"read16": "16V8", "read20": "20V8", "read22": "22V10"}.get(sub)
                if not gal_type:
                    print(f"    unknown read command: {sub}")
                    continue
                read_poti = int(args[1])
                prime_poti = int(args[2])
                hold_secs = float(args[3])
                repeats = int(args[4]) if len(args) > 4 else 1

                for r in range(1, repeats + 1):
                    print(f"\n  [prime cycle {r}/{repeats}] poti={prime_poti} hold {hold_secs}s")
                    term.send(f"SETPOTI {prime_poti}")
                    time.sleep(0.35)
                    term.ser.reset_input_buffer()
                    term.send("VPP ON")
                    time.sleep(0.2)
                    term.ser.reset_input_buffer()
                    # Countdown
                    start = time.time()
                    while time.time() - start < hold_secs:
                        remain = hold_secs - (time.time() - start)
                        if sys.stdout.isatty():
                            sys.stdout.write(f"\r    priming at {prime_poti}... {remain:4.1f}s   ")
                            sys.stdout.flush()
                        time.sleep(0.1)
                    if sys.stdout.isatty():
                        sys.stdout.write("\r" + " " * 40 + "\r")
                        sys.stdout.flush()
                    term.send("VPP OFF")
                    time.sleep(0.15)
                    term.ser.reset_input_buffer()

                # First: read AT the prime voltage. Chip should show all-1s and no
                # identity if the priming successfully disrupted the security cache.
                print(f"\n  intermediate read at prime voltage (poti={prime_poti})...")
                prime_result = term.cmd_read(gal_type, prime_poti)
                if prime_result['zeros'] > 200 and prime_result['has_cfg']:
                    print(f"    *** cracked already at prime voltage! ***")

                # Then: drop to read voltage and read again.
                print(f"\n  final read at read voltage (poti={read_poti})...")
                result = term.cmd_read(gal_type, read_poti)
                if result['zeros'] > 200 and result['has_cfg']:
                    print(f"    *** FULL CRACK with CFG ***")
                elif result['zeros'] > 200:
                    print(f"    *** cracked but no CFG (still worth saving) ***")

            elif cmd == "save":
                if not args:
                    print("    usage: save <ref>  (e.g. save UA6)")
                    continue
                term.save_dump(args[0])
            elif cmd == "jed":
                if len(args) < 2:
                    print("    usage: jed <input.dump> <output.jed> [16v8|22v10]")
                    continue
                gtype = args[2] if len(args) > 2 else ("22v10" if "22" in args[0] else "16v8")
                do_jed(args[0], args[1], gtype)
            elif cmd == "decompile":
                if not args:
                    print("    usage: decompile <input.jed> [16v8|20v8|22v10]")
                    continue
                gtype = args[1] if len(args) > 1 else ("22v10" if "22" in args[0] else "16v8")
                do_decompile(args[0], gtype)
            elif cmd == "raw":
                term.raw(" ".join(args))
            elif cmd == "ls":
                # Convenience: list recent dumps
                for f in sorted(glob.glob(os.path.join(CRACKS_DIR, "*.dump")))[-10:]:
                    print(f"    {f}")
            else:
                print(f"    unknown command '{cmd}'. try 'help'")
        except Exception as e:
            print(f"    error: {e}")

    print("bye")


if __name__ == "__main__":
    main()
