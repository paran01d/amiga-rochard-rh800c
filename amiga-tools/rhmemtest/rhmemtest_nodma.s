; ============================================================
; RocHard RH800C  -  $200000 fast-RAM memtest  (bootblock)
; ------------------------------------------------------------
; Bare-metal bootblock. Takes over the machine, tests the card
; RAM at $200000-$3FFFFF, logs every address to SERIAL (9600 8N1)
; BEFORE touching it, and installs a BUS ERROR handler so a
; no-DTACK access (with the berr_wdog GAL fitted) is caught and
; the scan CONTINUES instead of hanging.
;
;  * With the berr_wdog GAL (asserts /BERR on $200000 timeout):
;    a dead address -> bus error -> " BERR" -> next addr.
;  * WITHOUT the GAL: a dead address hangs; the LAST serial line
;    ("W addr") is the culprit.
;
; Position-independent: PC-relative strings; saved SP kept in a4
; (no absolute variables). Serial only, no OS calls.
; Build: vasmm68k_mot -Fbin.
; ============================================================

CUSTOM   = $dff000
SERDATR  = $018
SERDAT   = $030
SERPER   = $032
RAMBASE  = $200000
RAMTOP   = $400000

        dc.b    "DOS",0         ; +0  bootblock id
        dc.l    0               ; +4  checksum (patched by builder)
        dc.l    0               ; +8  rootblock (unused)
; ---- entry (+12) -------------------------------------------
start:
        move.w  #$FFF,$dff180           ; WHITE = loaded (user mode)
        move.l  $4.w,a6                 ; ExecBase (abs $4)
        lea     main(pc),a5
        jsr     -30(a6)                 ; Supervisor() -> run main in supervisor
        rts                             ; (not reached)
main:
        move.w  #$2700,sr               ; supervisor now: ints off
        ; (DMA left enabled - serial is primary output)
        lea     CUSTOM,a6
        move.w  #368,SERPER(a6)         ; 9600 baud PAL
        suba.l  a3,a3                   ; a3 = fault flag (0=clean)
        move.w  #$00F,$180(a6)          ; COLOR00 = blue (running)

        lea     buserr(pc),a0           ; install bus-error (2) + addr-error (3)
        move.l  a0,$0008.w
        move.l  a0,$000C.w

        lea     m_banner(pc),a0
        bsr     puts

; ---- Test A: base cell -------------------------------------
        lea     m_base(pc),a0
        bsr     puts
        move.l  #RAMBASE,a0
        move.l  #$A5A5A5A5,d1
        bsr     safe_wr                 ; -> d7
        tst.b   d7
        bne     .afail
        move.l  #RAMBASE,a0
        bsr     safe_rd                 ; -> d0,d7
        move.l  d0,d6
        tst.b   d7
        bne     .afail
        cmp.l   #$A5A5A5A5,d6
        bne     .adata
        lea     m_ok(pc),a0
        bsr     puts
        bra     .bwalk
.afail: bsr     setfault
        lea     m_berr(pc),a0
        bsr     puts
        bra     .bwalk
.adata: lea     m_derr(pc),a0
        bsr     puts
        move.l  d6,d1
        bsr     puthex
        bsr     crlf

; ---- Test B: walking-address write phase -------------------
.bwalk:
        lea     m_wr(pc),a0
        bsr     puts
        bsr     crlf
        moveq   #2,d4                   ; k (start 2: long-aligned, non-overlapping)
.wloop:
        moveq   #1,d5
        lsl.l   d4,d5                   ; 1<<k
        move.l  #RAMBASE,a0
        add.l   d5,a0                   ; addr
        cmp.l   #RAMTOP,a0
        bge     .rdphase
        move.l  a0,d3                   ; keep addr
        move.b  #'W',d0                 ; log "W addr" BEFORE access
        bsr     putc
        move.b  #' ',d0
        bsr     putc
        move.l  d3,d1
        bsr     puthex
        move.l  d3,a0
        move.l  d3,d1                   ; value = addr itself
        bsr     safe_wr
        tst.b   d7
        bne     .wberr
        lea     m_sp(pc),a0
        bsr     puts
        bra     .wnext
.wberr: bsr     setfault
        lea     m_sberr(pc),a0
        bsr     puts
.wnext:
        addq.l  #1,d4
        cmp.l   #21,d4
        blt     .wloop

; ---- read/verify phase -------------------------------------
.rdphase:
        lea     m_rd(pc),a0
        bsr     puts
        bsr     crlf
        moveq   #2,d4
.rloop:
        moveq   #1,d5
        lsl.l   d4,d5
        move.l  #RAMBASE,a0
        add.l   d5,a0
        cmp.l   #RAMTOP,a0
        bge     .done
        move.l  a0,d3                   ; expected = addr
        move.l  d3,a0
        bsr     safe_rd                 ; -> d0,d7
        move.l  d0,d6                   ; save read value
        tst.b   d7
        beq     .rok
        bsr     setfault
        move.b  #'R',d0                 ; read bus error
        bsr     putc
        move.b  #' ',d0
        bsr     putc
        move.l  d3,d1
        bsr     puthex
        lea     m_sberr(pc),a0
        bsr     puts
        bra     .rnext
.rok:
        cmp.l   d3,d6
        beq     .rnext                  ; match -> quiet
        bsr     setfault
        move.b  #'R',d0                 ; mismatch
        bsr     putc
        move.b  #' ',d0
        bsr     putc
        move.l  d3,d1
        bsr     puthex
        lea     m_got(pc),a0
        bsr     puts
        move.l  d6,d1
        bsr     puthex
        bsr     crlf
.rnext:
        addq.l  #1,d4
        cmp.l   #21,d4
        blt     .rloop
.done:
        lea     m_done(pc),a0
        bsr     puts
        move.l  a3,d0
        bne.s   .redend
        move.w  #$0F0,$dff180          ; green = all passed
        bra.s   .hang
.redend:
        move.w  #$F00,$dff180          ; red = faults found
.hang:  bra     .hang

; ============================================================
; safe_wr : a0=addr d1=data -> d7=0 ok /1 bus error (SP saved in a4)
safe_wr:
        moveq   #0,d7
        move.l  sp,a4
        move.l  d1,(a0)
        rts
; safe_rd : a0=addr -> d0=data d7=fault
safe_rd:
        moveq   #0,d7
        move.l  sp,a4
        move.l  (a0),d0
        rts
; bus-error handler: abandon faulting access, return to caller, d7=1
buserr:
        move.l  a4,sp
        moveq   #1,d7
        rts
; setfault: red screen + mark fault flag (a3), preserves d0-d7/a0-a2
setfault:
        move.w  #$F00,$dff180
        movea.w #1,a3
        rts

; ============================================================
; putc : d0.b char (preserves d0)
putc:
        move.l  d1,-(sp)
.w:     move.w  CUSTOM+SERDATR,d1
        and.w   #$2000,d1
        beq.s   .w
        move.w  d0,d1
        and.w   #$00ff,d1
        or.w    #$0100,d1
        move.w  d1,CUSTOM+SERDAT
        move.l  (sp)+,d1
        rts
; puts : a0 asciiz (preserves d0)
puts:
        move.l  d0,-(sp)
.l:     move.b  (a0)+,d0
        beq.s   .e
        bsr     putc
        bra.s   .l
.e:     move.l  (sp)+,d0
        rts
; puthex : d1.l value, 8 digits (preserves d1-d5)
puthex:
        movem.l d0/d2/d3,-(sp)
        move.l  d1,d3
        moveq   #7,d2
.h:     rol.l   #4,d3
        move.b  d3,d0
        and.b   #$0f,d0
        cmp.b   #10,d0
        blt.s   .n
        add.b   #'A'-10,d0
        bra.s   .p
.n:     add.b   #'0',d0
.p:     bsr     putc
        dbra    d2,.h
        movem.l (sp)+,d0/d2/d3
        rts
; crlf
crlf:
        move.l  d0,-(sp)
        move.b  #13,d0
        bsr     putc
        move.b  #10,d0
        bsr     putc
        move.l  (sp)+,d0
        rts

; ============================================================
m_banner: dc.b 13,10,"RocHard $200000 memtest",13,10,0
m_base:   dc.b "base $200000: ",0
m_ok:     dc.b "OK",13,10,0
m_berr:   dc.b "BUS ERROR",13,10,0
m_derr:   dc.b "DATA ERR got=",0
m_wr:     dc.b "-- write walk --",0
m_rd:     dc.b "-- read/verify walk --",0
m_sp:     dc.b " ok",13,10,0
m_sberr:  dc.b " BERR",13,10,0
m_got:    dc.b " MISMATCH got=",0
m_done:   dc.b "-- DONE --",13,10,0
        cnop 0,2
