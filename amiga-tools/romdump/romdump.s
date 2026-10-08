; romdump - copy the RocHard ROM window ($E90000, 8 KB) to RAM:romdump
; so it can be sent over the AUX: serial shell with "Type RAM:romdump HEX".
; Board base is taken from expansion.library FindConfigDev(2144,1).
        section code,code
start:  move.l  4.w,a6
        lea     expname(pc),a1
        moveq   #0,d0
        jsr     -552(a6)                ; OpenLibrary(expansion)
        tst.l   d0
        beq     .fail
        move.l  d0,a6
        sub.l   a0,a0
        move.l  #2144,d0
        moveq   #1,d1
        jsr     -72(a6)                 ; FindConfigDev(NULL,2144,1)
        move.l  d0,d7
        move.l  a6,a1
        move.l  4.w,a6
        jsr     -414(a6)                ; CloseLibrary(expansion)
        tst.l   d7
        beq     .fail
        move.l  d7,a0
        move.l  32(a0),d6               ; cd_BoardAddr
        lea     dosname(pc),a1
        moveq   #0,d0
        jsr     -552(a6)                ; OpenLibrary(dos)
        tst.l   d0
        beq     .fail
        move.l  d0,a6
        lea     fname(pc),a0
        move.l  a0,d1
        move.l  #1006,d2                ; MODE_NEWFILE
        jsr     -30(a6)                 ; Open
        move.l  d0,d5
        beq     .closedos
        move.l  d5,d1
        move.l  d6,d2                   ; buffer = board base (ROM)
        move.l  #8192,d3
        jsr     -48(a6)                 ; Write
        move.l  d5,d1
        jsr     -36(a6)                 ; Close
        moveq   #0,d7
        bra.s   .cd
.closedos:
        moveq   #20,d7
.cd:    move.l  a6,a1
        move.l  4.w,a6
        jsr     -414(a6)                ; CloseLibrary(dos)
        move.l  d7,d0
        rts
.fail:  moveq   #20,d0
        rts
expname: dc.b   "expansion.library",0
dosname: dc.b   "dos.library",0
fname:  dc.b    "RAM:romdump",0
        even
