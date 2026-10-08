; RocHard $200000 WORD-granular low-address test (confirm A1 fault)
; Word accesses like ATK detection. Logs each word addr before access.
; Supervisor() entry (bootblock is user mode). Serial 9600 8N1.
CUSTOM   = $dff000
SERDATR  = $018
SERDAT   = $030
SERPER   = $032
RAMBASE  = $200000
        dc.b    "DOS",0
        dc.l    0
        dc.l    0
start:  move.w  #$FFF,$dff180           ; white=loaded (user mode)
        move.l  $4.w,a6                 ; ExecBase
        lea     main(pc),a5
        jsr     -30(a6)                 ; Supervisor()
        rts
main:   move.w  #$2700,sr               ; supervisor: ints off
        move.w  #$01FF,$dff096          ; DMA off (solid COLOR00)
        lea     CUSTOM,a6
        move.w  #368,SERPER(a6)
        suba.l  a3,a3                   ; fault flag
        move.w  #$00F,$180(a6)          ; blue
        lea     buserr(pc),a0
        move.l  a0,$0008.w
        move.l  a0,$000C.w
        lea     m_banner(pc),a0
        bsr     puts
        ; --- word walk: offsets 0,2,4,...,62 (32 words) ---
        moveq   #0,d4                   ; byte offset (0..62)
.wl:    cmp.w   #64,d4
        bge     .done
        move.l  #RAMBASE,a0
        add.w   d4,a0                   ; addr = base + offset
        move.l  a0,d3
        move.b  #'W',d0
        bsr     putc
        move.b  #' ',d0
        bsr     putc
        move.l  d3,d1
        bsr     puthex
        move.w  d4,d5
        or.w    #$A000,d5               ; value = $A0xx (xx=offset)
        move.l  d3,a0
        move.w  d5,d1
        bsr     safe_wrw
        tst.b   d7
        bne     .berr
        move.l  d3,a0
        bsr     safe_rdw                ; d0 = word read
        and.l   #$FFFF,d0
        cmp.w   d5,d0
        bne     .mism
        lea     m_ok(pc),a0
        bsr     puts
        bra     .nxt
.berr:  bsr     setfault
        lea     m_berr(pc),a0
        bsr     puts
        bra     .nxt
.mism:  bsr     setfault
        lea     m_got(pc),a0
        bsr     puts
        move.l  d0,d1
        bsr     puthex
        bsr     crlf
.nxt:   addq.w  #2,d4
        bra     .wl
.done:  lea     m_done(pc),a0
        bsr     puts
        move.l  a3,d0
        bne.s   .red
        move.w  #$0F0,$dff180
        bra.s   .h
.red:   move.w  #$F00,$dff180
.h:     bra.s   .h
; word write/read with bus-error catch (SP in a4)
safe_wrw: moveq #0,d7
        move.l  sp,a4
        move.w  d1,(a0)
        rts
safe_rdw: moveq #0,d7
        move.l  sp,a4
        move.w  (a0),d0
        rts
buserr: move.l  a4,sp
        moveq   #1,d7
        rts
setfault: move.w #$F00,$dff180
        movea.w #1,a3
        rts
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
puthex: movem.l d0/d2/d3,-(sp)
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
crlf:   move.l  d0,-(sp)
        move.b  #13,d0
        bsr     putc
        move.b  #10,d0
        bsr     putc
        move.l  (sp)+,d0
        rts
m_banner: dc.b 13,10,"RocHard word-walk (A1 test)",13,10,0
m_ok:   dc.b " ok",13,10,0
m_berr: dc.b " BERR",13,10,0
m_got:  dc.b " MISMATCH got=",0
m_done: dc.b "-- DONE --",13,10,0
        cnop 0,2
