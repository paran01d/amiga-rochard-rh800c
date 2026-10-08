; ============================================================
; RocHard serial memory monitor (bootblock, bare-metal)
; Interactive peek/poke over serial 9600 8N1. Bus-error safe.
; Commands (hex, space-separated, RET to run):
;   r <addr>        read word  -> "addr: wwww"
;   l <addr>        read long  -> "addr: llllllll"
;   w <addr> <val>  write word -> "ok"
;   W <addr> <v32>  write LONG (two back-to-back word cycles) -> "ok"
;   t <addr>        ATK 2-point test AT that addr -> "RAM FOUND"/"FAIL"/"BERR"
; A no-DTACK access prints BERR if the berr_wdog GAL is fitted,
; otherwise hangs (you typed the addr, so you know which).
; Enters supervisor via exec Supervisor() (bootblock is user mode).
; ============================================================
CUSTOM   = $dff000
SERDATR  = $018
SERDAT   = $030
SERPER   = $032
INTREQ   = $09c

        dc.b    "DOS",0
        dc.l    0
        dc.l    0
start:  move.w  #$FFF,$dff180           ; white=loaded
        move.l  $4.w,a6                 ; ExecBase
        lea     main(pc),a5
        jsr     -30(a6)                 ; Supervisor()
        rts
main:   move.w  #$2700,sr               ; supervisor, ints off
        move.w  #$01FF,$dff096          ; DMA off (solid screen)
        lea     CUSTOM,a6
        move.w  #368,SERPER(a6)         ; 9600 baud PAL
        move.w  #$0800,INTREQ(a6)       ; clear pending RBF
        lea     buserr(pc),a0
        move.l  a0,$0008.w              ; bus error vector
        move.l  a0,$000C.w              ; address error vector
        move.w  #$0F0,$dff180           ; green = ready
        lea     m_banner(pc),a0
        bsr     puts
; --- command loop ---
cloop:  lea     m_prompt(pc),a0
        bsr     puts
        bsr     getc                    ; command char (echoed)
        cmp.b   #'r',d0
        beq     c_r
        cmp.b   #'l',d0
        beq     c_l
        cmp.b   #'w',d0
        beq     c_w
        cmp.b   #'t',d0
        beq     c_t
        cmp.b   #'W',d0
        beq     c_W
        bra     cloop
; r <addr> : read word
c_r:    bsr     gethex                  ; d3=addr
        bsr     praddr                  ; print "addr: "
        move.l  d3,a0
        bsr     safe_rdw                ; d0=word,d7
        tst.b   d7
        bne     .b
        and.l   #$FFFF,d0
        move.l  d0,d1
        bsr     phex4
        bra     .e
.b:     lea     m_berr(pc),a0
        bsr     puts
.e:     bsr     crlf
        bra     cloop
; l <addr> : read long
c_l:    bsr     gethex
        bsr     praddr
        move.l  d3,a0
        bsr     safe_rd
        tst.b   d7
        bne     .b
        move.l  d0,d1
        bsr     phex8
        bra     .e
.b:     lea     m_berr(pc),a0
        bsr     puts
.e:     bsr     crlf
        bra     cloop
; w <addr> <val> : write word
c_w:    bsr     gethex                  ; d3=addr
        move.l  d3,d5
        bsr     gethex                  ; d3=val
        move.l  d5,a0
        move.w  d3,d1
        bsr     safe_wrw
        bsr     crlf
        tst.b   d7
        bne     .b
        lea     m_ok(pc),a0
        bra     .p
.b:     lea     m_berr(pc),a0
.p:     bsr     puts
        bsr     crlf
        bra     cloop
; W <addr> <val32> : write LONG -> two back-to-back word cycles on a 68000
c_W:    bsr     gethex                  ; d3=addr
        move.l  d3,d5
        bsr     gethex                  ; d3=32-bit value
        move.l  d5,a0
        move.l  d3,d1
        bsr     safe_wrl
        bsr     crlf
        tst.b   d7
        bne     .b
        lea     m_ok(pc),a0
        bra     .p
.b:     lea     m_berr(pc),a0
.p:     bsr     puts
        bsr     crlf
        bra     cloop
; t <addr> : ATK's exact 2-point word test at any address you type
c_t:    bsr     gethex                  ; d3 = addr
        bsr     atktest
        bra     cloop
; atktest: d3=addr. ATK pattern: word $5555 at +0, $AAAA at +$40000, verify
; both. Prints "addr: RAM FOUND" / "FAIL got=xxxx" / "BERR". Preserves d3-d5/a2.
atktest:
        bsr     crlf
        move.l  d3,d1
        bsr     phex8
        lea     m_colon(pc),a0
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
        lea     m_found(pc),a0
        bsr     puts
        rts
.f:     lea     m_fail(pc),a0
        bsr     puts
        move.l  d0,d1
        bsr     phex4
        rts
.b:     lea     m_berr(pc),a0
        bsr     puts
        rts
; praddr: crlf + print d3 as 8 hex + ": "
praddr: bsr     crlf
        move.l  d3,d1
        bsr     phex8
        lea     m_colon(pc),a0
        bsr     puts
        rts
; ============================================================
; safe accessors (bus-error caught, SP saved in a4) -> d7=0/1
safe_wrw: moveq #0,d7
        move.l  sp,a4
        move.w  d1,(a0)
        rts
safe_rdw: moveq #0,d7
        move.l  sp,a4
        move.w  (a0),d0
        rts
safe_wrl: moveq #0,d7
        move.l  sp,a4
        move.l  d1,(a0)
        rts
safe_rd:  moveq #0,d7
        move.l  sp,a4
        move.l  (a0),d0
        rts
buserr: move.l  a4,sp
        moveq   #1,d7
        rts
; ============================================================
; getc: wait for serial byte -> d0 (echoed; CR echoes CRLF)
getc:   move.w  CUSTOM+SERDATR,d0
        btst    #14,d0                  ; RBF?
        beq.s   getc
        move.w  #$0800,CUSTOM+INTREQ    ; clear RBF
        and.w   #$00ff,d0
        move.l  d0,-(sp)
        cmp.b   #13,d0
        bne.s   .n
        move.b  #13,d0
        bsr     putc
        move.b  #10,d0
        bsr     putc
        bra.s   .x
.n:     bsr     putc
.x:     move.l  (sp)+,d0
        rts
; gethex: read hex chars into d3 (skips leading spaces, stops on non-hex)
gethex: moveq   #0,d3
.sk:    bsr     getc
        cmp.b   #' ',d0
        beq.s   .sk
.lp:    cmp.b   #'0',d0
        blt.s   .end
        cmp.b   #'9',d0
        bgt.s   .af
        sub.b   #'0',d0
        bra.s   .ac
.af:    and.b   #$DF,d0                 ; uppercase
        cmp.b   #'A',d0
        blt.s   .end
        cmp.b   #'F',d0
        bgt.s   .end
        sub.b   #'A'-10,d0
.ac:    and.l   #$0F,d0
        lsl.l   #4,d3
        or.l    d0,d3
        bsr     getc
        bra.s   .lp
.end:   rts
; putc: d0.b (preserves d0)
putc:   move.l  d1,-(sp)
.w:     move.w  CUSTOM+SERDATR,d1
        and.w   #$2000,d1               ; TBE
        beq.s   .w
        move.w  d0,d1
        and.w   #$00ff,d1
        or.w    #$0100,d1
        move.w  d1,CUSTOM+SERDAT
        move.l  (sp)+,d1
        rts
; puts: a0 asciiz (preserves d0)
puts:   move.l  d0,-(sp)
.l:     move.b  (a0)+,d0
        beq.s   .e
        bsr     putc
        bra.s   .l
.e:     move.l  (sp)+,d0
        rts
; phexn: d1=value, d2=ndigits (1..8), MSB-first
phexn:  movem.l d0-d4,-(sp)
        move.l  d1,d4                   ; value
        move.w  d2,d3                   ; ndigits (loop count)
        moveq   #8,d0
        sub.w   d2,d0                   ; 8-ndigits
        lsl.w   #2,d0                   ; *4 = bits to left-align
        lsl.l   d0,d4                   ; left-align field to top
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
m_banner: dc.b 13,10,"RHmon r l w W t",13,10,0
m_prompt: dc.b 13,10,"> ",0
m_colon:  dc.b ": ",0
m_ok:     dc.b "ok",0
m_fail:   dc.b "FAIL got=",0
m_found:  dc.b "RAM FOUND",0
m_berr:   dc.b "BERR",0
        cnop 0,2
        cnop 0,2
