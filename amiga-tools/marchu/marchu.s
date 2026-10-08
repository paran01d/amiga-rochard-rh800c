; marchu - March U RAM test for the RocHard fast RAM (or chip RAM).
;
; March U (van de Goor), 13N, run over six 32-bit data backgrounds B
; ("0" = B, "1" = ~B) so intra-word coupling faults are covered too:
;   M0 up/down (w0)
;   M1 up   (r0,w1,r1,w0)
;   M2 up   (r0,w1)
;   M3 down (r1,w0,r0,w1)
;   M4 down (r1,w0)
; Every mismatch prints element / address / expected / got / xor to the
; console AND straight to the serial hardware (9600 8N1, polled - survives a
; crash). Serial also gets the element number as each one completes.
;
; Usage (Shell, OS 2.0+):  marchu [c] [passes]
;   c       test the largest free CHIP block instead of fast RAM
;   passes  0 or none = until Ctrl-C
; Build: vasmm68k_mot -Fhunkexe -nosym -o marchu marchu.s

_LVOOpenLibrary  = -552
_LVOCloseLibrary = -414
_LVOAllocMem     = -198
_LVOFreeMem      = -210
_LVOAvailMem     = -216
_LVOSetSignal    = -306
_LVORawDoFmt     = -522
_LVOPutStr       = -948

SERDATR     = $dff018
SERDAT      = $dff030
SERPER      = $dff032
SERPER_9600 = 368                       ; 3546895/9600 - 1 (PAL)

MEMF_CHIP    = 2
MEMF_FAST    = 4
MEMF_LARGEST = $20000
CTRL_C_BIT   = 12
MAXPRINT     = 40

        section code,code

start:  movem.l d2-d7/a2-a6,-(sp)
        ; args: optional 'c' (chip) and a pass count
        moveq   #0,d1
.arg:   subq.l  #1,d0
        bmi.s   .argdone
        moveq   #0,d2
        move.b  (a0)+,d2
        cmp.b   #' ',d2
        beq.s   .arg
        cmp.b   #'c',d2
        beq.s   .chip
        cmp.b   #'C',d2
        beq.s   .chip
        sub.b   #'0',d2
        bcs.s   .argdone
        cmp.b   #9,d2
        bhi.s   .argdone
        mulu    #10,d1
        add.l   d2,d1
        bra.s   .arg
.chip:  lea     memtype(pc),a1
        move.l  #MEMF_CHIP,(a1)
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

        move.l  memtype(pc),d1
        or.l    #MEMF_LARGEST,d1
        jsr     _LVOAvailMem(a6)
        sub.l   #65536,d0               ; leave the OS some room
        and.l   #-16,d0
        ble     q_nomem
        lea     memsize(pc),a0
        move.l  d0,(a0)
        move.l  memtype(pc),d1
        jsr     _LVOAllocMem(a6)
        lea     membuf(pc),a0
        move.l  d0,(a0)
        beq     q_nomem

        move.w  #SERPER_9600,SERPER
        lea     args(pc),a0
        move.l  memsize(pc),(a0)        ; %ld bytes
        lea     m_fast(pc),a1
        move.l  a1,4(a0)                ; of %s RAM
        cmp.l   #MEMF_CHIP,memtype
        bne.s   .t
        lea     m_chip(pc),a1
        move.l  a1,4(a0)
.t:     move.l  membuf(pc),8(a0)        ; at $%08lx
        lea     m_banner(pc),a1
        bsr     printf

pass:   lea     bgtab(pc),a5            ; walk the data backgrounds
bgloop: move.l  (a5)+,d6                ; d6 = "0" = background
        cmp.l   #-1,d6                  ; end-of-table marker
        beq     passdone
        move.l  d6,d5
        not.l   d5                      ; d5 = "1" = inverse
        lea     args(pc),a0
        move.l  d6,(a0)
        lea     m_bg(pc),a1
        bsr     printf

        move.l  membuf(pc),a2           ; a2 = start
        move.l  a2,a4
        add.l   memsize(pc),a4          ; a4 = end

        ; M0: (w0)
        moveq   #0,d7
        move.l  a2,a0
.m0:    move.l  d6,(a0)+
        cmp.l   a4,a0
        bne.s   .m0
        bsr     elemdone

        ; M1 up: (r0,w1,r1,w0)
        moveq   #1,d7
        move.l  a2,a0
.m1:    move.l  (a0),d1
        cmp.l   d6,d1
        beq.s   .m1a
        move.l  d6,d0
        bsr     error
.m1a:   move.l  d5,(a0)
        move.l  (a0),d1
        cmp.l   d5,d1
        beq.s   .m1b
        move.l  d5,d0
        bsr     error
.m1b:   move.l  d6,(a0)+
        cmp.l   a4,a0
        bne.s   .m1
        bsr     elemdone

        ; M2 up: (r0,w1)
        moveq   #2,d7
        move.l  a2,a0
.m2:    move.l  (a0),d1
        cmp.l   d6,d1
        beq.s   .m2a
        move.l  d6,d0
        bsr     error
.m2a:   move.l  d5,(a0)+
        cmp.l   a4,a0
        bne.s   .m2
        bsr     elemdone

        ifd     FAULT                   ; self-test build only: flip bit 2
        eor.l   #4,256(a2)              ; of one longword before M3 reads it
        endif

        ; M3 down: (r1,w0,r0,w1)
        moveq   #3,d7
        move.l  a4,a0
.m3:    subq.l  #4,a0
        move.l  (a0),d1
        cmp.l   d5,d1
        beq.s   .m3a
        move.l  d5,d0
        bsr     error
.m3a:   move.l  d6,(a0)
        move.l  (a0),d1
        cmp.l   d6,d1
        beq.s   .m3b
        move.l  d6,d0
        bsr     error
.m3b:   move.l  d5,(a0)
        cmp.l   a2,a0
        bne.s   .m3
        bsr     elemdone

        ; M4 down: (r1,w0)
        moveq   #4,d7
        move.l  a4,a0
.m4:    subq.l  #4,a0
        move.l  (a0),d1
        cmp.l   d5,d1
        beq.s   .m4a
        move.l  d5,d0
        bsr     error
.m4a:   move.l  d6,(a0)
        cmp.l   a2,a0
        bne.s   .m4
        bsr     elemdone

        lea     m_nl(pc),a1             ; end of this background's line
        bsr     printf
        bsr     ctrlc
        bne     q_done
        bra     bgloop

passdone:
        lea     passno(pc),a0
        addq.l  #1,(a0)
        lea     args(pc),a1
        move.l  (a0),(a1)
        move.l  errcount(pc),4(a1)
        lea     m_pass(pc),a1
        bsr     printf
        move.l  maxpass(pc),d0
        beq     pass
        cmp.l   passno(pc),d0
        bhi     pass

q_done: lea     args(pc),a0
        move.l  passno(pc),(a0)
        move.l  errcount(pc),4(a0)
        lea     m_done(pc),a1
        bsr     printf
        bra.s   q_free

q_nomem:
        lea     m_nomem(pc),a1
        bsr     printf
q_free: move.l  4.w,a6
        move.l  membuf(pc),d0
        beq.s   .f1
        move.l  d0,a1
        move.l  memsize(pc),d0
        jsr     _LVOFreeMem(a6)
.f1:    move.l  dosbase(pc),a1
        jsr     _LVOCloseLibrary(a6)
q_exit: movem.l (sp)+,d2-d7/a2-a6
        moveq   #0,d0
        rts

; elemdone: element d7 finished - send its digit to serial
elemdone:
        move.l  d0,-(sp)
        moveq   #'0',d0
        add.b   d7,d0
        bsr     serch
        moveq   #' ',d0
        bsr     serch
        move.l  (sp)+,d0
        rts

; ctrlc: Z clear (bne taken) if Ctrl-C was pressed
ctrlc:  movem.l d0-d1/a0-a1/a6,-(sp)
        move.l  4.w,a6
        moveq   #0,d0
        move.l  #1<<CTRL_C_BIT,d1
        jsr     _LVOSetSignal(a6)
        btst    #CTRL_C_BIT,d0
        movem.l (sp)+,d0-d1/a0-a1/a6    ; movem doesn't touch flags
        rts

; error: d7=element, a0=address, d0=expected, d1=got
error:  movem.l d0-d7/a0-a6,-(sp)
        lea     errcount(pc),a1
        addq.l  #1,(a1)
        cmp.l   #MAXPRINT,(a1)
        bhi.s   .quiet
        lea     args(pc),a1
        move.l  d7,(a1)+
        move.l  a0,(a1)+
        move.l  d0,(a1)+
        move.l  d1,(a1)+
        eor.l   d0,d1
        move.l  d1,(a1)
        lea     m_err(pc),a1
        bsr.s   printf
.quiet: movem.l (sp)+,d0-d7/a0-a6
        rts

; printf: a1=format, args in 'args'. Console + polled serial.
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

bgtab:    dc.l $00000000,$55555555,$33333333,$0F0F0F0F,$00FF00FF,$0000FFFF
          dc.l -1                       ; end marker (~0 is not a background)

dosbase:  dc.l 0
memtype:  dc.l MEMF_FAST
membuf:   dc.l 0
memsize:  dc.l 0
maxpass:  dc.l 0
passno:   dc.l 0
errcount: dc.l 0
args:     ds.l 6
outbuf:   ds.b 256

dosname:  dc.b "dos.library",0
m_fast:   dc.b "fast",0
m_chip:   dc.b "chip",0
m_banner: dc.b "marchu: March U on %ld bytes of %s RAM at $%08lx",10
          dc.b "  6 backgrounds x 13N. Ctrl-C to stop (checked between backgrounds).",10,0
m_bg:     dc.b "bg %08lx: ",0
m_nl:     dc.b 10,0
m_err:    dc.b 10,"  M%ld ERR @$%08lx exp %08lx got %08lx xor %08lx",10,0
m_pass:   dc.b "pass %ld done, total errors %ld",10,0
m_done:   dc.b "marchu finished: %ld passes, %ld errors",10,0
m_nomem:  dc.b "marchu: not enough memory",10,0
          even
