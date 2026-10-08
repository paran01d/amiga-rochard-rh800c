#!/usr/bin/env python3
"""
rh_acprobe.py - decode a RocHard RH800C autoconfig capture (KingstVIS transition CSV).

Reconstructs the Zorro II autoconfig registers exactly as expansion.library reads them and
decodes each board the card enumerates.  See AUTOCONFIG_PROBE.md for the channel map.

  python3 rh_acprobe.py roctec_ac_ramon.csv
  python3 rh_acprobe.py roctec_ac_ramon.csv roctec_ac_ramoff.csv   # diff two runs

Required columns (matched case-insensitively, leading '/' '_' and '~' ignored):
  AS  RW  CFGMATCH  DB15 DB14 DB13 DB12  AB1..AB6
Optional but used if present:
  DRVEN  ROMOE  DTACK
"""
import csv
import gzip
import sys

# ---------------------------------------------------------------- CSV loading

REQUIRED = ['AS', 'RW', 'CFGMATCH', 'DB15', 'DB14', 'DB13', 'DB12',
            'AB1', 'AB2', 'AB3', 'AB4', 'AB5', 'AB6']
OPTIONAL = ['DRVEN', 'ROMOE', 'DTACK']

# tolerate the label variants used across the existing captures
ALIASES = {
    'AS': ('AS', '_AS', 'BUSAS'),
    'RW': ('RW', 'R_W', 'RNW', 'R/W'),
    'CFGMATCH': ('CFGMATCH', 'CFGADDRMATCH', 'CFGADDR_MATCH', 'ADDRMATCH', 'PEQR', 'P=R'),
    'DRVEN': ('DRVEN',),
    'ROMOE': ('ROMOE', 'ROMOE2'),
    'DTACK': ('DTACK',),
}


def norm(s):
    return s.strip().lstrip('/').replace('~', '').replace('{', '').replace('}', '') \
            .replace('_', '').replace('-', '').replace('.', '').upper()


def open_maybe_gz(path):
    return gzip.open(path, 'rt') if path.endswith('.gz') else open(path, 'r')


def header_index(header, path):
    cols = [norm(h) for h in header]
    idx = {}
    for name in REQUIRED + OPTIONAL:
        for c in ALIASES.get(name, (name,)):
            nc = norm(c)
            if nc in cols:
                idx[name] = cols.index(nc)
                break
    missing = [n for n in REQUIRED if n not in idx]
    if missing:
        sys.exit('%s: missing column(s) %s\n  header was: %s'
                 % (path, ', '.join(missing), ', '.join(header)))
    return idx


def cycles(path, stats=None):
    """Stream the CSV and yield one dict per bus cycle where CFGMATCH is asserted (low).

    Data is sampled from the last transition state before _AS is released, which is
    when the card's data is valid.  Memory use is O(1) in the number of transitions.
    """
    with open_maybe_gz(path) as fh:
        rd = csv.reader(fh)
        idx = header_index(next(rd), path)
        iT = 0
        iAS, iCM, iRW = idx['AS'], idx['CFGMATCH'], idx['RW']
        iAB = [idx['AB%d' % b] for b in range(1, 7)]
        iD = [idx['DB15'], idx['DB14'], idx['DB13'], idx['DB12']]
        iOpt = [(o, idx[o]) for o in OPTIONAL if o in idx]

        prev = None
        start_t = None
        ntrans = 0
        for r in rd:
            try:
                t = float(r[iT])
                # keep header-relative indices valid: slot 0 is the Time placeholder
                cur = [0] + [int(v) for v in r[1:]]
            except (ValueError, IndexError):
                continue
            ntrans += 1
            if prev is None:
                prev, prev_t = cur, t
                continue
            if prev[iAS] == 1 and cur[iAS] == 0:          # _AS falling -> cycle begins
                start_t = t
            elif prev[iAS] == 0 and cur[iAS] == 1:        # _AS rising -> cycle ends
                if start_t is not None and prev[iCM] == 0:
                    off = 0
                    for b, i in enumerate(iAB, start=1):
                        off |= prev[i] << b
                    nib = (prev[iD[0]] << 3) | (prev[iD[1]] << 2) \
                          | (prev[iD[2]] << 1) | prev[iD[3]]
                    c = {'t': start_t, 'off': off, 'nib': nib, 'read': prev[iRW] == 1}
                    for o, i in iOpt:
                        c[o.lower()] = prev[i]
                    yield c
                start_t = None
            prev = cur
        if stats is not None:
            stats['transitions'] = ntrans


# ------------------------------------------------------------- decode helpers

STRAIGHT = {0x00, 0x02, 0x40, 0x42}
SIZES = ['8MB', '64KB', '128KB', '256KB', '512KB', '1MB', '2MB', '4MB']
REGNAME = {0x00: 'er_Type', 0x04: 'er_Product', 0x08: 'er_Flags', 0x0c: 'er_Reserved03',
           0x10: 'er_Manuf_hi', 0x14: 'er_Manuf_lo', 0x18: 'er_SerNum0', 0x1c: 'er_SerNum1',
           0x20: 'er_SerNum2', 0x24: 'er_SerNum3', 0x28: 'er_InitDiagVec_hi',
           0x2c: 'er_InitDiagVec_lo', 0x40: 'ec_Interrupt', 0x44: 'ec_Z3_HighByte',
           0x48: 'ec_BaseAddress', 0x4c: 'ec_Shutup'}


def regbyte(nibs, off):
    if off not in nibs or (off + 2) not in nibs:
        return None
    v = (nibs[off] << 4) | nibs[off + 2]
    return v if off in STRAIGHT else (~v) & 0xff


def split_boards(cyc):
    """Split the cycle stream into boards: a write to $48/$4C terminates the current board."""
    boards, cur = [], []
    for c in cyc:
        cur.append(c)
        if not c['read'] and c['off'] in (0x48, 0x4c):
            boards.append(cur)
            cur = []
    if cur:
        boards.append(cur)
    return boards


def describe(board, n):
    reads = [c for c in board if c['read']]
    writes = [c for c in board if not c['read']]
    nibs = {}
    for c in reads:
        nibs.setdefault(c['off'], c['nib'])      # first read of each offset

    print('\n--- board #%d --- %d reads, %d writes, t = %.6f .. %.6f s'
          % (n, len(reads), len(writes), board[0]['t'], board[-1]['t']))

    if not nibs:
        print('    (no reads)')
    else:
        print('    reg  name                 nibbles   byte')
        for r in range(0x00, 0x50, 4):
            b = regbyte(nibs, r)
            if b is None:
                continue
            print('    %02X   %-20s %X %X       %02X'
                  % (r, REGNAME.get(r, ''), nibs[r], nibs[r + 2], b))

        t = regbyte(nibs, 0x00)
        if t is not None:
            kind = {0xc0: 'ZorroII', 0x80: 'ZorroIII'}.get(t & 0xc0, 'INVALID(%02X)' % (t & 0xc0))
            print('    => er_Type %02X : %s  MEMLIST=%d  DIAGVALID=%d  CHAINED=%d  size=%s'
                  % (t, kind, (t >> 5) & 1, (t >> 4) & 1, (t >> 3) & 1, SIZES[t & 7]))
            if (t >> 5) & 1:
                print('    => *** MEMLIST SET - this board IS offered to exec as RAM ***')
        mh, ml, pr = regbyte(nibs, 0x10), regbyte(nibs, 0x14), regbyte(nibs, 0x04)
        if None not in (mh, ml):
            print('    => manuf %d (0x%04X)%s  product %s'
                  % ((mh << 8) | ml, (mh << 8) | ml,
                     '  [Roctec]' if ((mh << 8) | ml) == 2144 else '', pr))

    for c in writes:
        extra = ''
        if c['off'] == 0x48:
            extra = '   <- BASE ADDRESS write, nibble %X = A23-A20' % c['nib']
        elif c['off'] == 0x4c:
            extra = '   <- SHUT UP (board declined)'
        print('    WRITE off $%02X nibble %X  t=%.6f%s' % (c['off'], c['nib'], c['t'], extra))

    # side-channel signals across the board's cycles
    for sig in ('drven', 'romoe', 'dtack'):
        vals = set(c[sig] for c in board if sig in c)
        if vals:
            print('    %-6s : %s' % (sig, 'always %d' % vals.pop() if len(vals) == 1 else 'TOGGLES'))


def analyse(path):
    stats = {}
    cyc = list(cycles(path, stats))
    print('=' * 72)
    print('%s : %d transitions, %d config-window bus cycles'
          % (path, stats.get('transitions', 0), len(cyc)))
    if not cyc:
        print('  No cycles with CFGMATCH asserted. Check the trigger and the _CFGMATCH probe')
        print('  (U10 pin 19); if the comparator never matched, re-run triggering on _DRVEN.')
        return []
    boards = split_boards(cyc)
    print('  boards enumerated: %d' % len(boards))
    for n, b in enumerate(boards, 1):
        describe(b, n)
    return boards


def signature(boards):
    """Compact comparable form: per board, the sorted (offset, read/write, nibble) set."""
    return [sorted(set((c['off'], c['read'], c['nib']) for c in b)) for b in boards]


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    results = [(p, analyse(p)) for p in args]

    if len(results) == 2:
        (p1, b1), (p2, b2) = results
        print('\n' + '=' * 72)
        print('DIFF  %s  vs  %s' % (p1, p2))
        s1, s2 = signature(b1), signature(b2)
        if not s1 and not s2:
            print('  BOTH captures decoded zero config cycles - nothing to compare.')
        elif s1 == s2:
            print('  *** config sequences are IDENTICAL ***')
            print('  The RAM strap changes nothing in the autoconfig phase - the card presents')
            print('  no RAM board. Use the first capture as the baseline for the UA6 responder.')
        else:
            print('  sequences DIFFER: %d board(s) vs %d board(s)' % (len(s1), len(s2)))
            for n in range(max(len(s1), len(s2))):
                a = set(s1[n]) if n < len(s1) else set()
                b = set(s2[n]) if n < len(s2) else set()
                only_a, only_b = sorted(a - b), sorted(b - a)
                if only_a or only_b:
                    print('  board #%d:' % (n + 1))
                    for off, rd, nib in only_a:
                        print('    only in %s: off $%02X %s nibble %X'
                              % (p1, off, 'R' if rd else 'W', nib))
                    for off, rd, nib in only_b:
                        print('    only in %s: off $%02X %s nibble %X'
                              % (p2, off, 'R' if rd else 'W', nib))


if __name__ == '__main__':
    main()
