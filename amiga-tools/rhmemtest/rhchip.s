; ============================================================
; rhchip - does ATK's direct-scan probe work when executed
;          from CHIP RAM instead of the bootblock's load address?
; ------------------------------------------------------------
; rhmon executes from wherever DOS loaded the bootblock, which on
; this machine is SLOW RAM (~$C15xxx - proved by an early bug that
; printed dbase+$200000 = $E15D7C). ATK is a loaded executable and
; its direct scan WORKS; every rhmon access HANGS. Execution
; location is the last untested difference between them.
;
; This bootblock:
;   1. AllocMem(MEMF_CHIP) a buffer
;   2. copies itself there
;   3. JUMPS into the chip copy and runs the probe from there
; Only ONE variable changes vs rhmon: where the code executes.
; Interrupts/DMA are left exactly as rhmon had them, deliberately.
;
; Probe A = ATK's exact form: anchor + 4*512KB, where anchor is our
;           chip buffer (ATK uses &s[0], a chip stack address).
; Probe B = absolute $200000 (what ATK's FAILING F1 test uses, and
;           what rhmon's `t 200000` uses).
; A works / B hangs  -> the address is the variable.
; both work          -> executing from chip RAM is the variable.
; both hang          -> execution location is NOT the variable.
; ============================================================
CUSTOM   = $dff000
SERDATR  = $018
SERDAT   = $030
SERPER   = $032
INTREQ   = $09c
ALLOCMEM = -198
SUPERV   = -30

        dc.b    "DOS",0
        dc.l    0
        dc.l    0
; ---- entry: running from the DOS load address (slow RAM) ----
start:  move.w  #$FFF,$dff180           ; white = loaded
        move.l  $4.w,a6                 ; ExecBase
        move.l  #2048,d0
        move.l  #$10002,d1              ; MEMF_CLEAR|MEMF_CHIP
        jsr     ALLOCMEM(a6)
        tst.l   d0
        beq     .fail                   ; no chip RAM -> give up
        move.l  d0,a1                   ; a1 = chip dest
        lea     start(pc),a0            ; a0 = our (slow RAM) base
        move.w  #(endcode-start-1),d2
.cp:    move.b  (a0)+,(a1)+
        dbra    d2,.cp
        ; jump into the CHIP copy
        move.l  d0,a0
        add.l   #(chipentry-start),a0
        jmp     (a0)
.fail:  rts
; ---- from here on we are executing from CHIP RAM ----
chipentry:
        move.l  $4.w,a6
        lea     main(pc),a5
        jsr     SUPERV(a6)              ; Supervisor()
        rts
main:   move.w  #$2700,sr               ; same as rhmon: ints off
        lea     CUSTOM,a6
        move.w  #368,SERPER(a6)         ; 9600 baud PAL
        move.w  #$0800,INTREQ(a6)
        lea     buserr(pc),a0
        move.l  a0,$0008.w              ; bus error
        move.l  a0,$000C.w              ; address error
        lea     m_ban(pc),a0
        bsr     puts
; --- report where we are actually executing from ---
        lea     m_exec(pc),a0
        bsr     puts
        lea     start(pc),a4            ; a4 = chip copy base (anchor)
        move.l  a4,d1
        bsr     phex8
        bsr     crlf
; --- Probe A: ATK's form, anchor + 4*512KB ---
        lea     m_pa(pc),a0
        bsr     puts
        move.l  a4,d3
        add.l   #$200000,d3
        bsr     probe
; --- Probe B: absolute $200000 ---
        lea     m_pb(pc),a0
        bsr     puts
        move.l  #$200000,d3
        bsr     probe
        lea     m_done(pc),a0
        bsr     puts
.hang:  bra     .hang
; ============================================================
; probe: d3 = addr. ATK pattern: word $5555 @ +0, $AAAA @ +$40000,
;        verify both. Prints "<addr>: RAM FOUND / FAIL got=xxxx / BERR"
probe:  move.l  d3,d1
        bsr     phex8
        lea     m_col(pc),a0
        bsr     puts
        move.l  d3,a0
        move.w  #$5555,d1
        bsr     safe_wrw
        tst.b   d7
        bne.s   .b
        move.l  d3,a0
        add.l   #$40000,a0
        move.w  #$AAAA,d1
        bsr     safe_wrw
        tst.b   d7
        bne.s   .b
        move.l  d3,a0
        bsr     safe_rdw
        tst.b   d7
        bne.s   .b
        and.l   #$FFFF,d0
        cmp.w   #$5555,d0
        bne.s   .f
        move.l  d3,a0
        add.l   #$40000,a0
        bsr     safe_rdw
        tst.b   d7
        bne.s   .b
        and.l   #$FFFF,d0
        cmp.w   #$AAAA,d0
        bne.s   .f
        lea     m_ok(pc),a0
        bsr     puts
        bsr     crlf
        rts
.f:     lea     m_fail(pc),a0
        bsr     puts
        move.l  d0,d1
        bsr     phex4
        bsr     crlf
        rts
.b:     lea     m_berr(pc),a0
        bsr     puts
        bsr     crlf
        rts
; ============================================================
safe_wrw: moveq #0,d7
        move.l  sp,a3
        move.w  d1,(a0)
        rts
safe_rdw: moveq #0,d7
        move.l  sp,a3
        move.w  (a0),d0
        rts
buserr: move.l  a3,sp
        moveq   #1,d7
        rts
; ============================================================
putc:   move.l  d1,-(sp)
.w:     move.w  CUSTOM+SERDATR,d1
        and.w   #$2000,d1
        beq.s   .w
        move.w  d0,d1
        and.w   #$00ff,d1
        or.w    #$0100,d1
        move.w  d1,CUSTOM+SERDAT
        move.l  (sp)+,d1
        rts
puts:   move.l  d0,-(sp)
.l:     move.b  (a0)+,d0
        beq.s   .e
        bsr     putc
        bra.s   .l
.e:     move.l  (sp)+,d0
        rts
phexn:  movem.l d0-d4,-(sp)
        move.l  d1,d4
        move.w  d2,d3
        moveq   #8,d0
        sub.w   d2,d0
        lsl.w   #2,d0
        lsl.l   d0,d4
        subq.w  #1,d3
.h:     rol.l   #4,d4
        move.b  d4,d0
        and.b   #$0f,d0
        cmp.b   #10,d0
        blt.s   .n
        add.b   #'A'-10,d0
        bra.s   .p
.n:     add.b   #'0',d0
.p:     bsr     putc
        dbra    d3,.h
        movem.l (sp)+,d0-d4
        rts
phex8:  moveq   #8,d2
        bra.s   phexn
phex4:  moveq   #4,d2
        bra.s   phexn
crlf:   move.l  d0,-(sp)
        move.b  #13,d0
        bsr     putc
        move.b  #10,d0
        bsr     putc
        move.l  (sp)+,d0
        rts
m_ban:  dc.b 13,10,"rhchip: probe from CHIP RAM",13,10,0
m_exec: dc.b "exec base: ",0
m_pa:   dc.b "A anchor+2MB ",0
m_pb:   dc.b "B absolute   ",0
m_col:  dc.b ": ",0
m_ok:   dc.b "RAM FOUND",0
m_fail: dc.b "FAIL got=",0
m_berr: dc.b "BERR",0
m_done: dc.b "-- done --",13,10,0
        cnop 0,2
endcode:
