; rhstress - RocHard fast-RAM stress test that mimics WHDLoad's access mix.
;
; Fills (almost) all fast RAM with an address-dependent pattern, then per pass:
;   1. copies it to a chip buffer in 32K chunks with movem.l bursts (fast reads
;      interleaved with chip writes, as WHDLoad does when a game loads) and
;      verifies every longword that landed in chip,
;   2. re-reads and verifies fast RAM in place,
;   3. changes the pattern seed and rewrites fast RAM.
; Errors print live (first MAXPRINT) and are stored (first MAXREC). On exit the
; full error list is printed, plus per-bit and per-bank failure counts.
; Exit: Ctrl-C or hold the LEFT MOUSE BUTTON (checked after every 32K chunk).
; All output goes to the console AND straight to the serial hardware (9600 8N1,
; polled), so it survives a crash.
;
; Usage (Shell, OS 2.0+):  rhstress [passes]     (0 or none = until stopped)
; Build: vasmm68k_mot -Fhunkexe -nosym -o rhstress rhstress.s

_LVOOpenLibrary  = -552
_LVOCloseLibrary = -414
_LVOAllocMem     = -198
_LVOFreeMem      = -210
_LVOAvailMem     = -216
_LVOSetSignal    = -306
_LVOPutStr       = -948
_LVORawDoFmt     = -522

SERDATR     = $dff018
SERDAT      = $dff030
SERPER      = $dff032
SERPER_9600 = 368                       ; 3546895/9600 - 1 (PAL)
CIAAPRA     = $bfe001                   ; bit 6 = left mouse button (0 = down)

MEMF_CHIP    = 2
MEMF_FAST    = 4
MEMF_LARGEST = $20000
CTRL_C_BIT   = 12
CHUNK        = 32768
MAXPRINT     = 200                      ; errors printed live
MAXREC       = 1000                     ; errors stored for the exit report
RECSIZE      = 24                       ; pass, phase, addr, exp, got, xor

; expected value for the longword at address \1, using seed d7, result in \2
PAT     macro
        move.l  \1,\2
        eor.l   d7,\2
        rol.l   #5,\2
        add.l   \1,\2
        endm

        section code,code

start:  movem.l d2-d7/a2-a6,-(sp)
        ; parse optional pass count from the command line (a0/d0)
        moveq   #0,d1
.arg:   subq.l  #1,d0
        bmi.s   .argdone
        moveq   #0,d2
        move.b  (a0)+,d2
        cmp.b   #' ',d2                 ; skip leading spaces
        beq.s   .arg
        sub.b   #'0',d2
        bcs.s   .argdone
        cmp.b   #9,d2
        bhi.s   .argdone
        mulu    #10,d1
        add.l   d2,d1
        bra.s   .arg
.argdone:
        lea     maxpass(pc),a0
        move.l  d1,(a0)

        move.l  4.w,a6
        lea     dosname(pc),a1
        moveq   #37,d0
        jsr     _LVOOpenLibrary(a6)
        lea     dosbase(pc),a0
        move.l  d0,(a0)
        beq     q_exit

        move.l  #CHUNK,d0
        moveq   #MEMF_CHIP,d1
        jsr     _LVOAllocMem(a6)
        lea     chipbuf(pc),a0
        move.l  d0,(a0)
        beq     q_nomem

        move.l  #MEMF_FAST|MEMF_LARGEST,d1
        jsr     _LVOAvailMem(a6)
        sub.l   #65536,d0               ; leave the OS some room
        and.l   #-CHUNK,d0              ; whole chunks only
        ble     q_nomem
        lea     fastsize(pc),a0
        move.l  d0,(a0)
        moveq   #MEMF_FAST,d1
        jsr     _LVOAllocMem(a6)
        lea     fastbuf(pc),a0
        move.l  d0,(a0)
        beq     q_nomem

        move.w  #SERPER_9600,SERPER     ; serial 9600 8N1 (PAL clock)
        lea     args(pc),a0
        move.l  fastsize(pc),(a0)
        move.l  fastbuf(pc),4(a0)
        move.l  chipbuf(pc),8(a0)
        lea     m_banner(pc),a1
        bsr     printf

        move.l  #$13579BDF,d7           ; pattern seed
        bsr     fill

pass:   ifd     FAULT                   ; self-test build only: corrupt one
        move.l  fastbuf(pc),a0          ; longword (bits 2 and 17) per pass
        eor.l   #$00020004,$100(a0)
        endif
        ; ---- copy fast -> chip in chunks, verify each chunk in chip ----
        move.l  fastbuf(pc),a2
        move.l  fastsize(pc),d5
.chunk: move.l  a2,a0
        move.l  chipbuf(pc),a1
        move.w  #CHUNK/16-1,d4
.cp:    movem.l (a0)+,d0-d3
        movem.l d0-d3,(a1)
        lea     16(a1),a1
        dbra    d4,.cp

        move.l  a2,a3                   ; fast address the data came from
        move.l  chipbuf(pc),a1
        move.w  #CHUNK/4-1,d4
.vc:    PAT     a3,d0
        move.l  (a1)+,d1
        cmp.l   d1,d0
        beq.s   .vcok
        lea     m_copy(pc),a0
        bsr     error
.vcok:  addq.l  #4,a3
        dbra    d4,.vc

        moveq   #'.',d0                 ; serial progress: one dot per chunk
        bsr     serch
        bsr     checkexit               ; Ctrl-C or left mouse button?
        bne     q_done

        add.l   #CHUNK,a2
        sub.l   #CHUNK,d5
        bne.s   .chunk

        ; ---- verify fast RAM in place ----
        move.l  fastbuf(pc),a3
        move.l  fastsize(pc),d6
        lsr.l   #2,d6
.vf:    PAT     a3,d0
        move.l  (a3),d1
        cmp.l   d1,d0
        beq.s   .vfok
        lea     m_fast(pc),a0
        bsr     error
.vfok:  addq.l  #4,a3
        subq.l  #1,d6
        bne.s   .vf

        ; ---- pass summary ----
        moveq   #13,d0                  ; end the row of dots on serial
        bsr     serch
        moveq   #10,d0
        bsr     serch
        lea     passno(pc),a0
        addq.l  #1,(a0)
        lea     args(pc),a1
        move.l  (a0),(a1)
        move.l  errcount(pc),4(a1)
        lea     m_pass(pc),a1
        bsr     printf

        move.l  maxpass(pc),d0
        beq.s   .again
        cmp.l   passno(pc),d0
        bls.s   q_done
.again: add.l   #$9E3779B9,d7           ; new pattern, rewrite fast RAM
        bsr     fill
        bra     pass

; ---- exit report ----
q_done: lea     m_nl(pc),a1
        bsr     printf
        lea     args(pc),a0
        move.l  passno(pc),(a0)
        move.l  errcount(pc),4(a0)
        lea     m_done(pc),a1
        bsr     printf

        move.l  errcount(pc),d6         ; stored records = min(errcount, MAXREC)
        beq     .nobits
        cmp.l   #MAXREC,d6
        bls.s   .n
        move.l  #MAXREC,d6
.n:     lea     m_list(pc),a1
        bsr     printf
        lea     errtab,a2
.rec:   lea     args(pc),a0
        moveq   #RECSIZE/4-1,d0
.cpy:   move.l  (a2)+,(a0)+
        dbra    d0,.cpy
        lea     m_rec(pc),a1
        bsr     printf
        subq.l  #1,d6
        bne.s   .rec

        lea     m_bits(pc),a1           ; how often each data bit failed
        bsr     printf
        lea     bitcnt,a2               ; walk bits 31..0
        moveq   #31,d5
.bl:    move.w  d5,d1
        lsl.w   #2,d1
        move.l  (a2,d1.w),d0
        beq.s   .bskip
        lea     args(pc),a0
        moveq   #0,d1
        move.w  d5,d1
        move.l  d1,(a0)
        move.l  d0,4(a0)
        lea     m_bit(pc),a1
        bsr     printf
.bskip: dbra    d5,.bl

        lea     args(pc),a0             ; errors per bank
        lea     bankcnt,a2
        moveq   #4,d0
.bk:    move.l  (a2)+,(a0)+
        dbra    d0,.bk
        lea     m_banks(pc),a1
        bsr     printf
.nobits:
        bra.s   q_free

q_nomem:
        lea     m_nomem(pc),a1
        bsr     printf
q_free: move.l  4.w,a6
        move.l  fastbuf(pc),d0
        beq.s   .f1
        move.l  d0,a1
        move.l  fastsize(pc),d0
        jsr     _LVOFreeMem(a6)
.f1:    move.l  chipbuf(pc),d0
        beq.s   .f2
        move.l  d0,a1
        move.l  #CHUNK,d0
        jsr     _LVOFreeMem(a6)
.f2:    move.l  dosbase(pc),a1
        jsr     _LVOCloseLibrary(a6)
q_exit: movem.l (sp)+,d2-d7/a2-a6
        moveq   #0,d0
        rts

; fill fast RAM with the pattern for seed d7
fill:   move.l  fastbuf(pc),a0
        move.l  fastsize(pc),d6
        lsr.l   #2,d6
.fl:    PAT     a0,d0
        move.l  d0,(a0)+
        subq.l  #1,d6
        bne.s   .fl
        rts

; checkexit: returns NE (Z clear) if Ctrl-C was pressed or the LMB is down
checkexit:
        movem.l d0-d1/a0-a1/a6,-(sp)
        btst    #6,CIAAPRA
        beq.s   .yes
        move.l  4.w,a6
        moveq   #0,d0
        move.l  #1<<CTRL_C_BIT,d1
        jsr     _LVOSetSignal(a6)
        btst    #CTRL_C_BIT,d0
        bne.s   .yes
        moveq   #0,d0                   ; Z set: keep going
        bra.s   .out
.yes:   moveq   #1,d0                   ; Z clear: stop
.out:   movem.l (sp)+,d0-d1/a0-a1/a6    ; movem to registers keeps the flags
        rts

; error: a0=phase string, a3=fast address, d0=expected, d1=got
error:  movem.l d0-d7/a0-a6,-(sp)
        move.l  d1,d2
        eor.l   d0,d2                   ; d2 = failing bits
        ; per-bit counts
        lea     bitcnt,a1
        moveq   #31,d3
.b:     btst    d3,d2
        beq.s   .nb
        move.w  d3,d4
        lsl.w   #2,d4
        addq.l  #1,(a1,d4.w)
.nb:    dbra    d3,.b
        ; per-bank count: bank = (addr - $200000) >> 21, else "other"
        move.l  a3,d3
        sub.l   #$200000,d3
        bcs.s   .other
        moveq   #21,d4
        lsr.l   d4,d3
        cmp.l   #4,d3
        bcs.s   .bank
.other: moveq   #4,d3
.bank:  lsl.w   #2,d3
        lea     bankcnt,a1
        addq.l  #1,(a1,d3.w)
        ; store the record
        lea     errcount(pc),a1
        move.l  (a1),d3
        addq.l  #1,(a1)
        move.l  passno(pc),d4
        addq.l  #1,d4                   ; pass in progress
        cmp.l   #MAXREC,d3
        bcc.s   .norec
        mulu    #RECSIZE,d3
        lea     errtab,a1
        add.l   d3,a1
        move.l  d4,(a1)+
        move.l  a0,(a1)+
        move.l  a3,(a1)+
        move.l  d0,(a1)+
        move.l  d1,(a1)+
        move.l  d2,(a1)
.norec: ; live print (first MAXPRINT)
        move.l  errcount(pc),d3
        cmp.l   #MAXPRINT,d3
        bhi.s   .quiet
        lea     args(pc),a1
        move.l  d4,(a1)+
        move.l  a0,(a1)+
        move.l  a3,(a1)+
        move.l  d0,(a1)+
        move.l  d1,(a1)+
        move.l  d2,(a1)
        lea     m_err(pc),a1
        bsr     printf
.quiet: movem.l (sp)+,d0-d7/a0-a6
        rts

; printf: a1=format, args in 'args'. Formats once with RawDoFmt, then writes
; the text to the console and, polled straight to the hardware, to serial -
; so output already sent survives a crash.
printf: movem.l d0-d7/a0-a6,-(sp)
        move.l  4.w,a6
        move.l  a1,a0
        lea     args(pc),a1
        lea     putch(pc),a2
        lea     outbuf(pc),a3
        jsr     _LVORawDoFmt(a6)
        move.l  dosbase(pc),a6
        lea     outbuf(pc),a0
        move.l  a0,d1
        jsr     _LVOPutStr(a6)
        lea     outbuf(pc),a0
.s:     move.b  (a0)+,d0
        beq.s   .x
        cmp.b   #10,d0
        bne.s   .c
        moveq   #13,d0
        bsr.s   serch
        moveq   #10,d0
.c:     bsr.s   serch
        bra.s   .s
.x:     movem.l (sp)+,d0-d7/a0-a6
        rts

putch:  move.b  d0,(a3)+
        rts

; serch: send byte d0 to the serial port, polling TBE (no OS involved)
serch:  move.l  d1,-(sp)
.w:     move.w  SERDATR,d1
        btst    #13,d1
        beq.s   .w
        and.w   #$ff,d0
        or.w    #$100,d0                ; stop bit
        move.w  d0,SERDAT
        move.l  (sp)+,d1
        rts

dosbase:  dc.l 0
chipbuf:  dc.l 0
fastbuf:  dc.l 0
fastsize: dc.l 0
maxpass:  dc.l 0
passno:   dc.l 0
errcount: dc.l 0
args:     ds.l 6
outbuf:   ds.b 256

dosname:  dc.b "dos.library",0
m_banner: dc.b "rhstress: %ld bytes of fast RAM at $%08lx, chip buffer $%08lx",10
          dc.b "  Stop: Ctrl-C or hold the LEFT MOUSE BUTTON. Full report on exit.",10,0
m_copy:   dc.b "copy",0
m_fast:   dc.b "fast",0
m_nl:     dc.b 10,0
m_err:    dc.b "  [pass %ld] %s ERR @$%08lx exp %08lx got %08lx xor %08lx",10,0
m_pass:   dc.b "pass %ld done, total errors %ld",10,0
m_done:   dc.b "=== rhstress stopped: %ld full passes, %ld errors ===",10,0
m_list:   dc.b "--- error list (first 1000) ---",10,0
m_rec:    dc.b "  [pass %ld] %s @$%08lx exp %08lx got %08lx xor %08lx",10,0
m_bits:   dc.b "--- failures per data bit ---",10,0
m_bit:    dc.b "  bit %2ld: %ld",10,0
m_banks:  dc.b "--- errors per bank ---",10
          dc.b "  bank0 $200000-$3FFFFF (SIMM0/1): %ld",10
          dc.b "  bank1 $400000-$5FFFFF (SIMM2/3): %ld",10
          dc.b "  bank2 $600000-$7FFFFF (SIMM4/5): %ld",10
          dc.b "  bank3 $800000-$9FFFFF (SIMM6/7): %ld",10
          dc.b "  other: %ld",10,0
m_nomem:  dc.b "rhstress: not enough memory (no fast RAM?)",10,0
          even

        section bss,bss
bitcnt:   ds.l 32
bankcnt:  ds.l 5
errtab:   ds.b MAXREC*RECSIZE
