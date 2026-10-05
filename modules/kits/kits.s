| KITS -- 256 Kits per project; a Kit is a saved Part.
|
| The stock Part engine is untouched: four working Part slots per bank, the
| pattern's Part byte (+0x8e57) names one of them, the sequencer and the
| frame ISR apply it. KITS keeps a library of 256 Parts (KLIB) and, per
| pattern, the Kit it plays (ASSIGN). Before a pattern is scheduled its
| Kit is copied into one of its bank's slots that no engine track names,
| and the pattern's Part byte is pointed at that slot. RESID says which Kit
| each of the 64 slots holds.
|
| * Staging: the schedule routine 0x400a0570 (every pattern request: the
|   panel, chains' first entry, program change, the project load, the
|   arranger) and the chain append 0x4009c634 (each later chain entry; the
|   switch at 0x400a4534 queues those without the schedule routine). Task
|   context only: a request with an interrupt level set (the arranger and
|   repeat publishers run in the tick) is counted (CNT_ISR) and plays what
|   is resident.
| * A slot is free when no engine track byte (0x8000182a/0x80001832) names
|   it while the transport runs, no queued or chained pattern's Part byte
|   names it, and its unsaved-changes bit (bank + 0x95048) is clear. No
|   free slot: counted (CNT_NOSLOT), the pattern plays what is resident.
| * LOAD KIT writes the Kit into the saved Part and runs the stock Part
|   Reload 0x4004aab4 on it (working copy, CS1 copy, engine apply, machine
|   transitions). SAVE KIT runs the stock Part Save 0x4004a908; its tail
|   (0x4004a9c4) copies the saved Part into the slot's Kit, so a plain Part
|   Save and SAVE ALL update the resident Kits too. FUNC+CUE is stock Part
|   Reload and reloads the Kit.
| * Files: kits.work / kits.strd in the project directory, the .bss image
|   KIMG as it is (header, ASSIGN, VALID, RESID, KLIB). Written where stock
|   writes the banks (0x400917c8) and on SAVE PROJECT (0x4008ee74), read at
|   the project load (0x40090504) and at the power-up's bank load
|   (0x400905d4, the first after boot). No kits.work: Em's kits3a/b.work
|   are imported when present, else the stock Parts migrate (kit =
|   bank*4 + part).
| * CS1 keeps RESID and ASSIGN over a power-off (KCS1A, KCS1B).
|
| No `illegal`; a refused or failed step takes the stock path and counts.

        .set    BLOB,       0x400e21e0
        .set    BSTRIDE,    0x9b340
        .set    PSTRIDE,    0x8ed8
        .set    PARTSZ,     0x18b2
        .set    WORKOFF,    0x8ed80         | bank: working Parts
        .set    SAVEDOFF,   0x9504a         | bank: saved Parts
        .set    MODBITS,    0x95048         | bank byte: bit p = Part p unsaved
        .set    SVALID,     0x9b312         | bank bytes: Part p has a saved copy
        .set    PNAMES,     0x9b316         | bank: Part names, 7 B each
        .set    BDIRTY,     0x9b332         | bank long: written by the bank writer
        .set    PBYTE,      0x8e57          | pattern: its Part
        .set    CS1_WORK,   0x100a4ece      | the current bank's copies in CS1
        .set    CS1_SAVED,  0x100ab196
        .set    CS1_MOD,    0x100b145e
        .set    CS1_SVALID, 0x100b145f
        .set    CS1_PTN,    0x1001614e
        .set    GDIRTY,     0x100f8598
        .set    CUR_BANK,   0x80000002
        .set    CUR_PART,   0x80000003
        .set    CUR_PTN,    0x80000004
        .set    TRK_BANK,   0x8000182a
        .set    TRK_PART,   0x80001832
        .set    SCHED,      0x800065b8      | long: 1 while the sequencer queues
        .set    Q_BANK,     0x800065bf
        .set    Q_PTN,      0x800065c0
        .set    P_BANK,     0x800065bd      | the playing pattern
        .set    CHAINED,    0x80006546
        .set    CHAIN_N,    0x8000654e
        .set    CHAIN,      0x80006552      | longs, pattern in the low byte
        .set    MEMCPY,     0x40020898      | (dst, src, n)
        .set    DIRTYEV,    0x40027e00      | stock's edited-state refresh
        .set    HASCONT,    0x4009a464      | (pattern, bank) -> nonzero
        .set    P_SAVE,     0x4004a908      | (part): working -> saved
        .set    P_RELOAD,   0x4004aab4      | (part): saved -> working, applied
        .set    P_SET,      0x4004a8a4      | (part): current pattern's Part, applied
        .set    PUSHED,     0x4003171c      | (key) -> nonzero while held
        .set    KFUNC,      0x2d
        .set    NOTIFY,     0x4005a2b8      | (str, ticks)
        .set    M_OPEN,     0x4006d94c      | (count, sel, &sel, labels, callbacks)
        .set    M_OBJ,      0x460e5e30      | long: the open callback menu
        .set    M_CLOSE,    0x4006d754
        .set    T_OPEN,     0x4007e664      | (max, title, buffer, 1, done(confirmed))
        .set    T_OBJ,      0x460e7612
        .set    SPRINTF,    0x40013a08
        .set    F_OPEN,     0x40016864      | (fo, path, mode, buffer, size)
        .set    F_READ,     0x40016564      | (fo, dst, n) -> 1
        .set    F_WRITE,    0x400166b8      | (fo, src, n) -> 1
        .set    F_CLOSE,    0x4001677c      | (fo)
        .set    F_COPY,     0x40016388      | (dst, src, 0)
        .set    PROJDIR,    0x40025230      | (0, 0) -> the project directory
        .set    IOB_LEN,    0x1000
        .set    NKITS,      256
        .set    REC,        6338            | name 8, flags 4, reserved 4, payload
        .set    R_PAY,      16
        .set    HDR_LEN,    64
        .set    O_ASSIGN,   HDR_LEN
        .set    O_VALID,    O_ASSIGN+256
        .set    O_RESID,    O_VALID+32
        .set    O_LIB,      O_RESID+64
        .set    IMG_LEN,    O_LIB+NKITS*REC
        .set    MAGIC,      0x4b495453      | 'KITS'
        .set    VERSION,    1
        .set    KCS1A,      0x100f85a0      | CS1: magic, RESID, sum (72 B)
        .set    KCS1B,      0x100ffe00      | CS1: ASSIGN (256 B)
        .set    CS1MAGIC,   0x4b435331      | 'KCS1'
        .set    V3_REC,     0x1a00          | Em's v3 record
        .set    V3_RECS,    0x600

        .text
        .globl  kits_sched, kits_chain, kits_loadall, kits_loadmask, kits_newproj
        .globl  kits_bankw, kits_pstore, kits_preload, kits_saved, kits_clear
        .globl  kits_partkey, kits_savekey, kits_mkisave
        .globl  KIMG, KSTATE, kits_stage, kits_load_current, kits_save_current

| ============================================================ the hooks ====

| 0x400a0570 (bank, pattern, ...): the schedule routine's entry.
kits_sched:
        lea     %sp@(-16),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@
        movel   %sp@(16+4),%d0
        movel   %sp@(16+8),%d1
        bsr.w   stage_req
        movem.l %sp@,%d0-%d1/%a0-%a1
        lea     %sp@(16),%sp
        lea     %sp@(-20),%sp           | displaced
        moveml  %d2-%d6,%sp@
        jmp     0x400a0578

| 0x4009c634 (pattern): the chain append; the chain is the queued bank's.
kits_chain:
        lea     %sp@(-16),%sp
        movem.l %d0-%d1/%a0-%a1,%sp@
        moveb   Q_BANK,%d0
        extb.l  %d0
        bpl.s   1f
        moveb   P_BANK,%d0
        extb.l  %d0
1:      movel   %sp@(16+4),%d1
        bsr.w   stage_req
        movem.l %sp@,%d0-%d1/%a0-%a1
        lea     %sp@(16),%sp
        movel   %d2,%sp@-               | displaced
        movel   %sp@(8),%d2
        jmp     0x4009c63a

| 0x40090504: the project load's bank load. The library first; the
| migration, the import and the current pattern's Kit after every bank is
| in RAM.
kits_loadall:
        lea     %sp@(-60),%sp
        movem.l %d0-%d7/%a0-%a6,%sp@
        bsr.w   kinit
        clrl    READY
        bsr.w   read_project
        movem.l %sp@,%d0-%d7/%a0-%a6
        lea     %sp@(60),%sp
        movel   %sp@+,LA_RET
        pea     la_after
        lea     %sp@(-328),%sp          | displaced
        moveml  %d2-%d7/%a2-%fp,%sp@
        jmp     0x4009050c
la_after:
        movel   LA_RET,%sp@-
        lea     %sp@(-60),%sp
        movem.l %d0-%d7/%a0-%a6,%sp@
        moveq   #0,%d0                  | no CS1 copy: a load from the menu
        bsr.w   post_load
        movem.l %sp@,%d0-%d7/%a0-%a6
        lea     %sp@(60),%sp
        rts

| 0x400905d4 (?, mask, ...): a masked bank load, told apart by where it
| returns to (measured under the port, OCTABAM89_setgate):
|   0x400853de  LOAD PROJECT, every bank: the project's Kits (LM_MODE 1)
|   0x40084d66  every bank but the current one, the current from CS1: the
|               power-up's load when no project has been loaded since boot
|               (2: the Kits, RESID and ASSIGN from CS1), else the one that
|               follows a LOAD PROJECT (3)
|   any other   (3) banks reloaded from their files
| In 3 the masked banks' slots hold their files' Parts, which KITS knows
| only right after a LOAD PROJECT (JUSTLOADED); otherwise they are
| forgotten and restaged at their next schedule.
kits_loadmask:
        lea     %sp@(-60),%sp
        movem.l %d0-%d7/%a0-%a6,%sp@
        movel   %sp@(60),%d0            | the return address
        moveq   #1,%d1
        cmpil   #0x400853de,%d0
        beq.s   1f
        moveq   #3,%d1
        cmpil   #0x40084d66,%d0
        bne.s   1f
        movel   KMAGIC,%d0
        cmpil   #MAGIC,%d0
        beq.s   1f
        moveq   #2,%d1
1:      movel   %d1,LM_MODE
        subql   #3,%d1
        beq.s   5f
        bsr.w   kinit
        clrl    READY
        clrl    JUSTLOADED
        bsr.w   read_project
        bra.s   2f
5:      tstl    JUSTLOADED
        beq.s   6f
        clrl    JUSTLOADED
        bra.s   2f
6:      moveq   #0,%d3
        movew   %sp@(60+10),%d3         | the mask
        moveq   #0,%d4
3:      btst    %d4,%d3
        beq.s   4f
        movel   %d4,%d0
        bsr.w   forget_bank
4:      addql   #1,%d4
        cmpil   #16,%d4
        bne.s   3b
        bsr.w   cs1_save
2:      movem.l %sp@,%d0-%d7/%a0-%a6
        lea     %sp@(60),%sp
        movel   %sp@+,LM_RET
        pea     lm_after
        lea     %sp@(-328),%sp          | displaced
        moveml  %d2-%d7/%a2-%fp,%sp@
        jmp     0x400905dc
lm_after:
        movel   LM_RET,%sp@-
        movel   LM_MODE,%d1
        subql   #3,%d1
        beq.s   1f
        lea     %sp@(-60),%sp
        movem.l %d0-%d7/%a0-%a6,%sp@
        addql   #3,%d1
        moveq   #0,%d0
        subql   #2,%d1
        bne.s   2f
        moveq   #1,%d0                  | the power-up: CS1's RESID and ASSIGN win
2:      bsr.w   post_load
        movem.l %sp@,%d0-%d7/%a0-%a6
        lea     %sp@(60),%sp
1:      rts

| 0x400909d8: a new, empty project: an empty library.
kits_newproj:
        lea     %sp@(-60),%sp
        movem.l %d0-%d7/%a0-%a6,%sp@
        bsr.w   kinit
        bsr.w   lib_empty
        moveq   #1,%d0
        movel   %d0,READY
        movel   %d0,KDIRTY
        clrl    NOWRITE
        bsr.w   cs1_save
        movem.l %sp@,%d0-%d7/%a0-%a6
        lea     %sp@(60),%sp
        movel   %a2,%sp@-               | displaced
        clrl    %sp@-
        jsr     0x4000fd34
        jmp     0x400909e2

| 0x400917c8: the bank writer (background save, save-as, new project,
| SAVE PROJECT). After it, kits.work when a Kit or an assignment changed.
kits_bankw:
        movel   %sp@+,BW_RET
        pea     bw_after
        linkw   %fp,#-324               | displaced
        moveml  %d2-%d7/%a2-%a5,%sp@
        jmp     0x400917d0
bw_after:
        movel   BW_RET,%sp@-
        lea     %sp@(-60),%sp
        movem.l %d0-%d7/%a0-%a6,%sp@
        bsr.w   write_if_dirty
        movem.l %sp@,%d0-%d7/%a0-%a6
        lea     %sp@(60),%sp
        rts

| 0x4008ee74: the project store (.work -> .strd). kits.work first, then
| its .strd copy.
kits_pstore:
        lea     %sp@(-60),%sp
        movem.l %d0-%d7/%a0-%a6,%sp@
        bsr.w   write_if_dirty
        movem.l %sp@,%d0-%d7/%a0-%a6
        lea     %sp@(60),%sp
        movel   %sp@+,PS_RET
        pea     ps_after
        linkw   %fp,#-560               | displaced
        moveml  %d2-%d7/%a2-%a5,%sp@
        jmp     0x4008ee7c
ps_after:
        movel   PS_RET,%sp@-
        lea     %sp@(-60),%sp
        movem.l %d0-%d7/%a0-%a6,%sp@
        tstl    READY
        beq.s   1f
        tstl    NOWRITE
        bne.s   1f
        lea     FMT_STRD,%a0
        lea     PSRC,%a1
        bsr.w   path
        lea     FMT_WORK,%a0
        lea     PATH,%a1
        bsr.w   path
        clrl    %sp@-
        pea     PATH
        pea     PSRC
        jsr     F_COPY
        lea     %sp@(12),%sp
1:      movem.l %sp@,%d0-%d7/%a0-%a6
        lea     %sp@(60),%sp
        rts

| 0x4008f180: the project reload (.strd -> .work): kits.strd back, read.
kits_preload:
        movel   %sp@+,PR_RET
        pea     pr_after
        linkw   %fp,#-560               | displaced
        moveml  %d2-%d7/%a2-%a5,%sp@
        jmp     0x4008f188
pr_after:
        movel   PR_RET,%sp@-
        lea     %sp@(-60),%sp
        movem.l %d0-%d7/%a0-%a6,%sp@
        tstl    READY
        beq.s   1f
        lea     FMT_WORK,%a0
        lea     PSRC,%a1
        bsr.w   path
        lea     FMT_STRD,%a0
        lea     PATH,%a1
        bsr.w   path
        clrl    %sp@-
        pea     PATH
        pea     PSRC
        jsr     F_COPY
        lea     %sp@(12),%sp
        tstl    %d0
        bmi.s   1f
        bsr.w   read_kits
        tstl    %d0
        bne.s   1f
        clrl    KDIRTY
        bsr.w   cs1_save
1:      movem.l %sp@,%d0-%d7/%a0-%a6
        lea     %sp@(60),%sp
        rts

| 0x4004a9c4: the stock Part Save's tail, d4 = the part, the current bank.
| The saved Part goes into the slot's Kit (a Part Clear ends here too:
| the slot then holds no Kit).
kits_saved:
        lea     %sp@(-60),%sp
        movem.l %d0-%d7/%a0-%a6,%sp@
        tstl    READY
        beq.s   9f
        moveq   #0,%d2
        moveb   CUR_BANK,%d2
        lsll    #2,%d2
        andil   #3,%d4
        addl    %d4,%d2                 | d2 = the slot
        lea     KIMG+O_RESID,%a2
        tstl    CLEARING
        beq.s   1f
        clrl    CLEARING
        moveq   #-1,%d0
        moveb   %d0,%a2@(0,%d2:l)
        bsr.w   cs1_save
        bra.s   9f
1:      moveq   #0,%d3
        moveb   %a2@(0,%d2:l),%d3       | d3 = the Kit
        cmpil   #0xff,%d3
        beq.s   9f
        movel   %d3,%d0
        bsr.w   kit_at                  | a0 = the record
        moveal  %a0,%a3
        movel   %d4,%d0
        bsr.w   saved_at                | a0 = the saved Part
        pea     PARTSZ
        movel   %a0,%sp@-
        pea     %a3@(R_PAY)
        jsr     MEMCPY
        lea     %sp@(12),%sp
        movel   %d3,%d0
        bsr.w   set_valid
        moveq   #1,%d0
        movel   %d0,KDIRTY
9:      movem.l %sp@,%d0-%d7/%a0-%a6
        lea     %sp@(60),%sp
        moveml  %sp@,%d2-%d4/%a2-%a3    | displaced
        lea     %sp@(20),%sp
        rts

| 0x4004a9d0 (part): the stock Part Clear's entry; it ends in Part Save.
kits_clear:
        movel   %d0,%sp@-
        moveq   #1,%d0
        movel   %d0,CLEARING
        movel   %sp@+,%d0
        lea     %sp@(-16),%sp           | displaced
        moveml  %d2-%d3/%a2-%a3,%sp@
        jmp     0x4004a9d8

| 0x4002e7b8: the PART key (MKII; FUNC+MIDI on the MKI): LOAD KIT.
kits_partkey:
        tstl    READY
        bne.s   1f
        tstl    0x460d1060              | displaced: the stock PART window
        jmp     0x4002e7be
1:      bra.w   load_menu

| 0x4002dc9c: the Part edit menu (MKII FUNC+PART): SAVE KIT.
kits_savekey:
        tstl    READY
        bne.s   1f
        mvzb    0x100b14cf,%d0          | displaced
        jmp     0x4002dca2
1:      bra.w   save_menu

| 0x40058a64: the MKI FUNC+BANK dispatch: SAVE KIT.
kits_mkisave:
        tstl    READY
        bne.s   1f
        movel   %d3,%sp@-               | displaced
        movel   %d2,%sp@-
        movel   %sp@(12),%d3
        jmp     0x40058a6c
1:      bra.w   save_menu

| ============================================================ staging ======

| stage_req: d0 = bank, d1 = pattern. In task context only.
stage_req:
        cmpil   #15,%d0
        bhi.s   9f
        cmpil   #15,%d1
        bhi.s   9f
        tstl    READY
        beq.s   9f
        movel   %d0,%a0
        movew   %sr,%d0
        andil   #0x0700,%d0
        beq.s   1f
        addql   #1,CNT_ISR
        rts
1:      movel   %a0,%d0
        moveq   #0,%d2                  | no apply
        bra.w   kits_stage
9:      rts

| kits_stage: d0 = bank, d1 = pattern, d2 = 1 to apply the pattern's Part
| to the engine afterwards when it is the current pattern (the project
| load's post step; stopped). Keeps d2-d7/a2-a6.
kits_stage:
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        movel   %d0,%d4                 | d4 = bank
        movel   %d1,%d5                 | d5 = pattern
        movel   %d2,%a5                 | a5 = apply
        movel   %d4,%d0
        lsll    #4,%d0
        addl    %d5,%d0
        lea     KIMG+O_ASSIGN,%a0
        moveq   #0,%d6
        moveb   %a0@(0,%d0:l),%d6       | d6 = the Kit
        cmpil   #0xff,%d6
        beq.w   st_out
        movel   %d6,%d0
        bsr.w   is_valid
        tstl    %d0
        bne.s   1f
        addql   #1,CNT_INVALID
        bra.w   st_out
1:      movel   %d4,%d0
        movel   %d5,%d1
        bsr.w   pbyte_at                | a0 = the pattern's Part byte
        moveq   #0,%d7
        moveb   %a0@,%d7                | d7 = its slot
        cmpil   #3,%d7
        bhi.w   st_out
        movel   %d7,%d3                 | d3 = the slot it will play
        lea     KIMG+O_RESID,%a2
        movel   %d4,%d0
        lsll    #2,%d0
        moveal  %a2,%a3
        addal   %d0,%a3                 | a3 = RESID[bank*4]
        moveq   #0,%d0
        moveb   %a3@(0,%d7:l),%d0
        cmpl    %d6,%d0
        beq.w   st_touch                | resident
        movel   %d7,%d1
        bsr.w   slot_ok
        tstl    %d0
        beq.s   2f
        movel   %d6,%d0                 | the pattern's own slot
        movel   %d4,%d1
        movel   %d7,%d2
        bsr.w   load_into
        bra.w   st_touch
| another slot: one already holding the Kit (its unsaved bit is that
| Kit's own edits), else the free one used longest ago
2:      moveq   #0,%d2
3:      cmpl    %d7,%d2
        beq.s   4f
        moveq   #0,%d0
        moveb   %a3@(0,%d2:l),%d0
        cmpl    %d6,%d0
        bne.s   4f
        movel   %d2,%d1
        bsr.w   slot_ok_named
        tstl    %d0
        beq.s   4f
        movel   %d2,%d3
        bra.s   st_point
4:      addql   #1,%d2
        moveq   #4,%d0
        cmpl    %d2,%d0
        bne.s   3b
        moveq   #-1,%d3                 | d3 = the choice
        moveal  %d3,%a4                 | a4 = its stamp
        moveq   #0,%d2
5:      cmpl    %d7,%d2
        beq.s   6f
        movel   %d2,%d1
        bsr.w   slot_ok
        tstl    %d0
        beq.s   6f
        movel   %d4,%d0
        lsll    #2,%d0
        addl    %d2,%d0
        lea     LRU,%a0
        movel   %a0@(0,%d0:l:4),%d0
        cmpl    %a4,%d0
        bcc.s   6f
        moveal  %d0,%a4
        movel   %d2,%d3
6:      addql   #1,%d2
        moveq   #4,%d0
        cmpl    %d2,%d0
        bne.s   5b
        tstl    %d3
        bpl.s   7f
        addql   #1,CNT_NOSLOT
        bra.w   st_out
7:      movel   %d6,%d0
        movel   %d4,%d1
        movel   %d3,%d2
        bsr.w   load_into
st_point:
        movel   %d4,%d0
        movel   %d5,%d1
        movel   %d3,%d2
        bsr.w   set_pbyte
        addql   #1,CNT_REPOINT
st_touch:
        addql   #1,STAMP
        movel   %d4,%d0
        lsll    #2,%d0
        addl    %d3,%d0
        lea     LRU,%a0
        movel   STAMP,%d1
        movel   %d1,%a0@(0,%d0:l:4)
        cmpl    #0,%a5
        beq.s   st_out
        moveq   #0,%d0                  | the current pattern: its Part applied
        moveb   CUR_BANK,%d0
        cmpl    %d4,%d0
        bne.s   st_out
        moveb   CUR_PTN,%d0
        cmpl    %d5,%d0
        bne.s   st_out
        movel   %d3,%sp@-
        jsr     P_SET
        addql   #4,%sp
st_out: movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| slot_ok: d4 = bank, d1 = slot -> d0 = 1 when a Kit may be copied there:
| the slot's working Part is the Kit RESID names for it, byte for byte
| (nothing in it that no Kit holds), and slot_ok_named. Stock's unsaved
| bit is not the test: it stays set after an edit is undone and is set on
| every Part of a project saved without a Part Save (OCTABAM89_setgate:
| 0xf on bank 3, one slot equal to its saved copy). Keeps d1-d7/a1-a6.
slot_ok:
        lea     %sp@(-16),%sp
        movem.l %d1-%d2/%a1-%a2,%sp@
        movel   %d4,%d2
        lsll    #2,%d2
        addl    %d1,%d2
        lea     KIMG+O_RESID,%a0
        moveq   #0,%d0
        moveb   %a0@(0,%d2:l),%d0
        cmpil   #0xff,%d0
        beq.s   2f                      | unknown content: kept
        bsr.w   kit_at
        lea     %a0@(R_PAY),%a2
        movel   %d4,%d0
        bsr.w   bank_at
        addal   #WORKOFF,%a0
        movel   %sp@,%d1
        movel   #PARTSZ,%d0
        mulu.l  %d1,%d0
        addal   %d0,%a0
        movel   #PARTSZ/2,%d2           | PARTSZ is even, both Parts word aligned
1:      mvzw    %a0@+,%d0
        mvzw    %a2@+,%d1
        cmpl    %d1,%d0
        bne.s   2f
        subql   #1,%d2
        bne.s   1b
        movem.l %sp@,%d1-%d2/%a1-%a2
        lea     %sp@(16),%sp
        bra.s   slot_ok_named
2:      movem.l %sp@,%d1-%d2/%a1-%a2
        lea     %sp@(16),%sp
        moveq   #0,%d0
        rts
| slot_ok_named: d4 = bank, d1 = slot -> d0 = 1 when no engine track
| names it (while the transport runs) and no queued or chained pattern's
| Part byte does. Keeps d1-d7/a1-a6.
slot_ok_named:
        movel   %d2,%sp@-
        movel   %a1,%sp@-
        movel   SCHED,%d0
        subql   #1,%d0
        bne.s   2f
        lea     TRK_BANK,%a0
        moveq   #7,%d2
1:      moveq   #0,%d0
        moveb   %a0@(0,%d2:l),%d0
        cmpl    %d4,%d0
        bne.s   3f
        moveb   %a0@(8,%d2:l),%d0
        cmpl    %d1,%d0
        beq.s   ok_no
3:      subql   #1,%d2
        bpl.s   1b
2:      moveb   Q_BANK,%d0              | the queued pattern
        extb.l  %d0
        cmpl    %d4,%d0
        bne.s   ok_yes
        moveb   Q_PTN,%d0
        extb.l  %d0
        bmi.s   ok_yes
        bsr.s   qpart
        cmpl    %d1,%d0
        beq.s   ok_no
        tstl    CHAINED                 | each chain entry, in the same bank
        beq.s   ok_yes
        movel   CHAIN_N,%d2
        cmpil   #16,%d2
        bhi.s   ok_yes
        lea     CHAIN,%a1
4:      subql   #1,%d2
        bmi.s   ok_yes
        movel   %a1@(0,%d2:l:4),%d0
        andil   #15,%d0
        bsr.s   qpart
        cmpl    %d1,%d0
        bne.s   4b
ok_no:  moveq   #0,%d0
        bra.s   ok_ret
ok_yes: moveq   #1,%d0
ok_ret: movel   %sp@+,%a1
        movel   %sp@+,%d2
        rts
| qpart: d4 = bank, d0 = pattern -> d0 = its Part byte (keeps d1/d2/a1)
qpart:  movel   %d1,%sp@-
        movel   %d0,%d1
        movel   %d4,%d0
        bsr.w   pbyte_at
        moveq   #0,%d0
        moveb   %a0@,%d0
        movel   %sp@+,%d1
        rts

| load_into: d0 = Kit, d1 = bank, d2 = slot. The Kit becomes the slot's
| saved and working Part, its name the Part's, the unsaved bit clear; in
| CS1 too for the current bank. Keeps d2-d7/a2-a6.
load_into:
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        movel   %d0,%d5
        movel   %d1,%d6
        movel   %d2,%d7
        movel   %d5,%d0
        bsr.w   kit_at
        moveal  %a0,%a3                 | a3 = the record
        movel   %d6,%d0
        bsr.w   bank_at
        moveal  %a0,%a2                 | a2 = the bank
        movel   #PARTSZ,%d3
        mulu.l  %d7,%d3                 | d3 = slot * PARTSZ
        lea     %a2@(0,%d3:l),%a4
        pea     PARTSZ
        pea     %a3@(R_PAY)
        movel   %a4,%d0
        addil   #SAVEDOFF,%d0
        movel   %d0,%sp@-
        jsr     MEMCPY
        lea     %sp@(12),%sp
        moveal  %a2,%a0
        addal   #SVALID,%a0
        moveq   #1,%d0
        moveb   %d0,%a0@(0,%d7:l)
        tstl    LI_SAVEDONLY
        bne.s   3f
        pea     PARTSZ
        pea     %a3@(R_PAY)
        movel   %a4,%d0
        addil   #WORKOFF,%d0
        movel   %d0,%sp@-
        jsr     MEMCPY
        lea     %sp@(12),%sp
        moveq   #1,%d0
        lsll    %d7,%d0
        notl    %d0
        moveal  %a2,%a0
        addal   #MODBITS,%a0
        moveb   %a0@,%d1
        andl    %d0,%d1
        moveb   %d1,%a0@
3:      movel   %d7,%d0                 | the name: six characters and a NUL
        mulu.w  #7,%d0
        moveal  %a2,%a0
        addal   #PNAMES,%a0
        addal   %d0,%a0
        moveal  %a3,%a1
        bsr.w   name6
        moveal  %a2,%a0
        addal   #BDIRTY,%a0
        moveq   #1,%d0
        movel   %d0,%a0@
        moveq   #0,%d0
        moveb   CUR_BANK,%d0
        cmpl    %d6,%d0
        bne.s   2f
        pea     PARTSZ
        pea     %a3@(R_PAY)
        movel   %d3,%d0
        addil   #CS1_SAVED,%d0
        movel   %d0,%sp@-
        jsr     MEMCPY
        lea     %sp@(12),%sp
        lea     CS1_SVALID,%a0
        moveq   #1,%d0
        moveb   %d0,%a0@(0,%d7:l)
        tstl    LI_SAVEDONLY
        bne.s   4f
        pea     PARTSZ
        pea     %a3@(R_PAY)
        movel   %d3,%d0
        addil   #CS1_WORK,%d0
        movel   %d0,%sp@-
        jsr     MEMCPY
        lea     %sp@(12),%sp
        moveq   #1,%d0
        lsll    %d7,%d0
        notl    %d0
        moveb   CS1_MOD,%d1
        andl    %d0,%d1
        moveb   %d1,CS1_MOD
4:      moveq   #1,%d0
        movel   %d0,GDIRTY
2:      movel   %d6,%d0
        lsll    #2,%d0
        addl    %d7,%d0
        lea     KIMG+O_RESID,%a0
        moveb   %d5,%a0@(0,%d0:l)
        moveq   #1,%d0
        movel   %d0,KDIRTY
        addql   #1,CNT_STAGED
        bsr.w   cs1_save
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| set_pbyte: d0 = bank, d1 = pattern, d2 = slot; the bank's copy, CS1's
| for the current bank, and both marked for the bank writer. Keeps
| d2-d7/a2-a6.
set_pbyte:
        lea     %sp@(-8),%sp
        movem.l %d3-%d4,%sp@
        movel   %d0,%d3
        movel   %d1,%d4
        bsr.w   pbyte_at
        moveb   %d2,%a0@
        movel   %d3,%d0
        bsr.w   bank_at
        addal   #BDIRTY,%a0
        moveq   #1,%d0
        movel   %d0,%a0@
        moveq   #0,%d0
        moveb   CUR_BANK,%d0
        cmpl    %d3,%d0
        bne.s   1f
        movel   %d4,%d0
        movel   #PSTRIDE,%d1
        mulu.l  %d1,%d0
        addil   #CS1_PTN+PBYTE,%d0
        moveal  %d0,%a0
        moveb   %d2,%a0@
        moveq   #1,%d0
        movel   %d0,GDIRTY
1:      movem.l %sp@,%d3-%d4
        lea     %sp@(8),%sp
        rts

| ============================================================ LOAD / SAVE ==

| kits_load_current: d0 = Kit -> the current pattern plays it: the Kit in
| the current Part's saved copy, then the stock Part Reload.
kits_load_current:
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        movel   %d0,%d5
        moveq   #0,%d6
        moveb   CUR_BANK,%d6
        moveq   #0,%d7
        moveb   CUR_PART,%d7
        andil   #3,%d7
        moveq   #0,%d4
        moveb   CUR_PTN,%d4
        andil   #15,%d4
        movel   %d6,%d0                 | UNDO KIT: what the pattern had
        lsll    #4,%d0
        addl    %d4,%d0
        lea     KIMG+O_ASSIGN,%a0
        moveq   #0,%d1
        moveb   %a0@(0,%d0:l),%d1
        cmpil   #0xff,%d1
        bne.s   1f
        movel   %d6,%d1
        lsll    #2,%d1
        addl    %d7,%d1
        lea     KIMG+O_RESID,%a1
        moveb   %a1@(0,%d1:l),%d1
1:      moveb   %d1,UNDOKIT
        moveb   %d5,%a0@(0,%d0:l)       | ASSIGN
        moveq   #1,%d0                  | the Kit as the slot's saved Part; the
        movel   %d0,LI_SAVEDONLY        | stock reload makes it the working one
        movel   %d5,%d0                 | (machine transitions from the Part
        movel   %d6,%d1                 | it replaces)
        movel   %d7,%d2
        bsr.w   load_into
        clrl    LI_SAVEDONLY
        movel   %d7,%sp@-
        jsr     P_RELOAD
        addql   #4,%sp
        moveq   #1,%d0
        movel   %d0,KDIRTY
        bsr.w   cs1_save
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| kits_save_current: d0 = Kit, a0 = name (8 bytes) or 0 to keep the Kit's.
| The stock Part Save on the current Part; its tail fills the Kit.
kits_save_current:
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        movel   %d0,%d5
        moveal  %a0,%a4
        moveq   #0,%d6
        moveb   CUR_BANK,%d6
        moveq   #0,%d7
        moveb   CUR_PART,%d7
        andil   #3,%d7
        movel   %d6,%d0
        lsll    #2,%d0
        addl    %d7,%d0
        lea     KIMG+O_RESID,%a0
        moveb   %d5,%a0@(0,%d0:l)
        movel   %d7,%sp@-
        jsr     P_SAVE
        addql   #4,%sp
        movel   %d5,%d0
        bsr.w   kit_at
        moveal  %a0,%a3
        cmpl    #0,%a4
        beq.s   2f
        moveq   #7,%d1                  | the name, seven characters and a NUL
1:      moveb   %a4@+,%a3@+
        subql   #1,%d1
        bpl.s   1b
        clrb    %a3@(-1)
        movel   %d5,%d0
        bsr.w   kit_at
        moveal  %a0,%a3
2:      tstb    %a3@                    | a Kit has a name
        bne.s   3f
        lea     DEFNAME,%a1
        moveal  %a3,%a0
        moveq   #7,%d1
4:      moveb   %a1@+,%a0@+
        subql   #1,%d1
        bpl.s   4b
3:      movel   %d6,%d0                 | the stock Part's name: six characters
        bsr.w   bank_at
        movel   %d7,%d0
        mulu.w  #7,%d0
        addal   #PNAMES,%a0
        addal   %d0,%a0
        moveal  %a3,%a1
        bsr.w   name6
        movel   %d6,%d0
        lsll    #4,%d0
        moveq   #0,%d1
        moveb   CUR_PTN,%d1
        andil   #15,%d1
        addl    %d1,%d0
        lea     KIMG+O_ASSIGN,%a0
        moveb   %d5,%a0@(0,%d0:l)
        movel   %d5,%d0
        bsr.w   set_valid
        moveq   #1,%d0
        movel   %d0,KDIRTY
        bsr.w   cs1_save
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| ============================================================ the menus ====

| load_menu: UNDO KIT, then the 256 Kits; the cursor on the current Part's.
load_menu:
        tstl    T_OBJ
        bne.w   m_out
        tstl    M_OBJ
        beq.s   1f
        jmp     M_CLOSE                 | PART again closes it
1:      lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        moveq   #1,%d0
        bsr.w   labels                  | the rows, row 0 UNDO KIT
        lea     LOADCB,%a0
        bsr.w   callbacks
        bsr.w   cur_kit
        addql   #1,%d0
        cmpil   #NKITS+1,%d0
        bcs.s   2f
        moveq   #0,%d0
2:      movel   %d0,MSEL
        pea     CBTAB
        pea     LBTAB
        pea     MSEL
        movel   %d0,%sp@-
        pea     NKITS+1
        jsr     M_OPEN
        lea     %sp@(20),%sp
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
m_out:  rts

| save_menu: the 256 Kits; the cursor on the current Part's Kit, else the
| first empty one.
save_menu:
        tstl    T_OBJ
        bne.s   m_out
        tstl    M_OBJ
        beq.s   1f
        jmp     M_CLOSE
1:      lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        moveq   #0,%d0
        bsr.w   labels
        lea     SAVECB,%a0
        bsr.w   callbacks
        bsr.w   cur_kit
        cmpil   #NKITS,%d0
        bcs.s   3f
        moveq   #0,%d2                  | the first empty Kit
2:      movel   %d2,%d0
        bsr.w   is_valid
        tstl    %d0
        beq.s   4f
        addql   #1,%d2
        cmpil   #NKITS,%d2
        bne.s   2b
        moveq   #0,%d2
4:      movel   %d2,%d0
3:      movel   %d0,MSEL
        pea     CBTAB
        pea     LBTAB
        pea     MSEL
        movel   %d0,%sp@-
        pea     NKITS
        jsr     M_OPEN
        lea     %sp@(20),%sp
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| cur_kit -> d0 = the Kit in the current Part's slot (0xff none).
cur_kit:
        moveq   #0,%d0
        moveb   CUR_BANK,%d0
        lsll    #2,%d0
        moveq   #0,%d1
        moveb   CUR_PART,%d1
        andil   #3,%d1
        addl    %d1,%d0
        lea     KIMG+O_RESID,%a0
        moveq   #0,%d1
        moveb   %a0@(0,%d0:l),%d1
        movel   %d1,%d0
        rts

| the LOAD KIT row's YES: row 0 = UNDO KIT
load_yes:
        movel   MSEL,%d0
        bne.s   1f
        moveq   #0,%d0
        moveb   UNDOKIT,%d0
        cmpil   #0xff,%d0
        bne.s   2f
        pea     0x30
        pea     T_NOUNDO
        jsr     NOTIFY
        addql   #8,%sp
        rts
1:      subql   #1,%d0
2:      movel   %d0,%sp@-
        bsr.w   is_valid
        tstl    %d0
        bne.s   3f
        addql   #4,%sp
        pea     0x30
        pea     T_EMPTY
        jsr     NOTIFY
        addql   #8,%sp
        rts
3:      movel   %sp@+,%d0
        bsr.w   kits_load_current
        pea     0x30
        pea     T_LOADED
        jsr     NOTIFY
        addql   #8,%sp
        rts

| the SAVE KIT row's YES: FUNC held saves now under the Kit's name (quick
| save), else the name editor first.
save_yes:
        movel   MSEL,%d0
        cmpil   #NKITS,%d0
        bcc.s   9f
        movel   %d0,SAVEK
        pea     KFUNC
        jsr     PUSHED
        addql   #4,%sp
        tstl    %d0
        beq.s   1f
        movel   SAVEK,%d0
        suba.l  %a0,%a0
        bsr.w   kits_save_current
        pea     0x30
        pea     T_SAVED
        jsr     NOTIFY
        addql   #8,%sp
9:      rts
1:      movel   SAVEK,%d0               | the name to edit: the Kit's, or NEW KIT
        bsr.w   kit_at
        lea     NAMEBUF,%a1
        moveq   #7,%d1
2:      moveb   %a0@+,%a1@+
        subql   #1,%d1
        bpl.s   2b
        clrb    NAMEBUF+7
        movel   SAVEK,%d0
        bsr.w   is_valid
        tstl    %d0
        beq.s   3f
        tstb    NAMEBUF
        bne.s   4f
3:      lea     DEFNAME,%a0
        lea     NAMEBUF,%a1
        moveq   #7,%d1
5:      moveb   %a0@+,%a1@+
        subql   #1,%d1
        bpl.s   5b
4:      pea     save_named
        pea     1
        pea     NAMEBUF
        pea     T_KITNAME
        pea     7
        jsr     T_OPEN
        lea     %sp@(20),%sp
        rts

| the name editor's done (confirmed)
save_named:
        tstl    %sp@(4)
        beq.s   1f
        movel   SAVEK,%d0
        lea     NAMEBUF,%a0
        bsr.w   kits_save_current
        pea     0x30
        pea     T_SAVED
        jsr     NOTIFY
        addql   #8,%sp
1:      rts

| labels: d0 = 1 for the LOAD list (row 0 UNDO KIT). Rows "NNN name",
| "*" after a Kit no pattern plays, "NNN ---" for an empty Kit.
labels:
        lea     %sp@(-28),%sp
        movem.l %d2-%d5/%a2-%a4,%sp@
        movel   %d0,%d5
        lea     REFD,%a0                | which Kits an assignment names
        moveq   #7,%d1
1:      clrl    %a0@+
        subql   #1,%d1
        bpl.s   1b
        lea     KIMG+O_ASSIGN,%a0
        lea     REFD,%a1
        movel   #255,%d2
2:      moveq   #0,%d0
        moveb   %a0@(0,%d2:l),%d0
        cmpil   #0xff,%d0
        beq.s   3f
        movel   %d0,%d1
        lsrl    #3,%d1
        andil   #7,%d0
        bset    %d0,%a1@(0,%d1:l)
3:      subql   #1,%d2
        bpl.s   2b
        lea     LBTAB,%a3
        lea     LBUF,%a4
        tstl    %d5
        beq.s   4f
        lea     T_UNDO,%a0
        movel   %a0,%a3@+
4:      moveq   #0,%d2
5:      movel   %a4,%a3@+
        movel   %d2,%d0
        bsr.w   is_valid
        tstl    %d0
        bne.s   6f
        movel   %d2,%d0
        addql   #1,%d0
        movel   %d0,%sp@-
        pea     F_EMPTY
        movel   %a4,%sp@-
        jsr     SPRINTF
        lea     %sp@(12),%sp
        bra.s   8f
6:      lea     T_SPACE,%a2
        movel   %d2,%d0
        lsrl    #3,%d0
        lea     REFD,%a1
        moveb   %a1@(0,%d0:l),%d0
        movel   %d2,%d1
        andil   #7,%d1
        btst    %d1,%d0
        bne.s   7f
        lea     T_STAR,%a2
7:      movel   %d2,%d0
        bsr.w   kit_at
        movel   %a2,%sp@-
        movel   %a0,%sp@-
        movel   %d2,%d0
        addql   #1,%d0
        movel   %d0,%sp@-
        pea     F_ROW
        movel   %a4,%sp@-
        jsr     SPRINTF
        lea     %sp@(20),%sp
8:      lea     %a4@(16),%a4
        addql   #1,%d2
        cmpil   #NKITS,%d2
        bne.w   5b
        movem.l %sp@,%d2-%d5/%a2-%a4
        lea     %sp@(28),%sp
        rts

| callbacks: a0 = the YES handler for every row
callbacks:
        lea     CBTAB,%a1
        movel   #NKITS,%d0
1:      movel   %a0,%a1@+
        subql   #1,%d0
        bpl.s   1b
        rts

| ============================================================ the files ====

| path: a0 = format ("%s/kits.work"), a1 = 260 bytes. d0/d1/a0/a1 clobbered.
path:   movel   %a2,%sp@-
        movel   %a3,%sp@-
        moveal  %a0,%a2
        moveal  %a1,%a3
        clrl    %sp@-
        clrl    %sp@-
        jsr     PROJDIR
        addql   #8,%sp
        movel   %d0,%sp@-
        movel   %a2,%sp@-
        movel   %a3,%sp@-
        jsr     SPRINTF
        lea     %sp@(12),%sp
        movel   %sp@+,%a3
        movel   %sp@+,%a2
        rts

| fopen: a0 = path, a1 = mode -> d0 (< 0: failed)
fopen:  pea     IOB_LEN
        pea     IOB
        movel   %a1,%sp@-
        movel   %a0,%sp@-
        pea     FOBJ
        jsr     F_OPEN
        lea     %sp@(20),%sp
        rts
| fio: a0 = buffer, d0 = length, a1 = F_READ or F_WRITE -> d0 (1 = done)
fio:    movel   %d0,%sp@-
        movel   %a0,%sp@-
        pea     FOBJ
        jsr     %a1@
        lea     %sp@(12),%sp
        rts
fclose: pea     FOBJ
        jsr     F_CLOSE
        addql   #4,%sp
        rts

| write_if_dirty: kits.work when READY, KDIRTY and the file may be written.
write_if_dirty:
        tstl    READY
        beq.s   1f
        tstl    KDIRTY
        beq.s   1f
        tstl    NOWRITE
        bne.s   1f
        bsr.w   write_kits
        tstl    %d0
        bne.s   1f
        clrl    KDIRTY
1:      rts

| write_kits -> d0 = 0 when kits.work holds KIMG. Keeps d2-d7/a2-a6.
write_kits:
        movel   %d2,%sp@-
        lea     KIMG,%a0
        movel   #MAGIC,%d0
        movel   %d0,%a0@
        moveq   #VERSION,%d0
        movel   %d0,%a0@(4)
        movel   #IMG_LEN,%d0
        movel   %d0,%a0@(8)
        lea     KIMG+HDR_LEN,%a0
        movel   #IMG_LEN-HDR_LEN,%d0
        bsr.w   crc32
        movel   %d0,KIMG+12
        lea     FMT_WORK,%a0
        lea     PATH,%a1
        bsr.w   path
        lea     PATH,%a0
        lea     MODE_W,%a1
        bsr.w   fopen
        tstl    %d0
        bmi.s   8f
        lea     KIMG,%a0
        movel   #IMG_LEN,%d0
        lea     F_WRITE,%a1
        bsr.w   fio
        movel   %d0,%d2
        bsr.w   fclose
        subql   #1,%d2
        bne.s   8f
        moveq   #0,%d0
        bra.s   9f
8:      addql   #1,CNT_IOERR
        moveq   #-1,%d0
9:      movel   %sp@+,%d2
        rts

| read_kits -> d0 = 0 read and checked, 1 missing, 2 present but refused.
| A refused file leaves KIMG unknown; the caller decides.
read_kits:
        movel   %d2,%sp@-
        lea     FMT_WORK,%a0
        lea     PATH,%a1
        bsr.w   path
        lea     PATH,%a0
        lea     MODE_R,%a1
        bsr.w   fopen
        tstl    %d0
        bpl.s   1f
        moveq   #1,%d0
        bra.w   9f
1:      lea     KIMG,%a0
        moveq   #HDR_LEN,%d0
        lea     F_READ,%a1
        bsr.w   fio
        subql   #1,%d0
        bne.s   7f
        lea     KIMG,%a0
        movel   %a0@,%d0
        cmpil   #MAGIC,%d0
        bne.s   7f
        moveq   #VERSION,%d0
        cmpl    %a0@(4),%d0
        bne.s   7f
        movel   %a0@(8),%d0
        cmpil   #IMG_LEN,%d0
        bne.s   7f
        lea     KIMG+HDR_LEN,%a0
        movel   #IMG_LEN-HDR_LEN,%d0
        lea     F_READ,%a1
        bsr.w   fio
        subql   #1,%d0
        bne.s   7f
        bsr.w   fclose
        lea     KIMG+HDR_LEN,%a0
        movel   #IMG_LEN-HDR_LEN,%d0
        bsr.w   crc32
        cmpl    KIMG+12,%d0
        bne.s   6f
        moveq   #0,%d0
        bra.s   9f
7:      bsr.w   fclose
6:      addql   #1,CNT_BADFILE
        moveq   #2,%d0
9:      movel   %sp@+,%d2
        rts

| read_project: kits.work, else Em's v3 files (IMPORT), else the stock
| Parts (MIGRATE) after the banks are in. A kits.work that is refused is
| never overwritten (NOWRITE) and the project plays its Parts as stock.
read_project:
        clrl    PENDING
        clrl    NOWRITE
        clrl    KDIRTY
        bsr.w   read_kits
        tstl    %d0
        beq.s   9f
        subql   #1,%d0
        beq.s   1f
        bsr.w   lib_empty
        moveq   #1,%d0
        movel   %d0,NOWRITE
        bra.s   9f
1:      bsr.w   lib_empty
        moveq   #2,%d0                  | MIGRATE unless the import finds a file
        movel   %d0,PENDING
        bsr.w   v3_present
        tstl    %d0
        beq.s   9f
        moveq   #3,%d0                  | IMPORT
        movel   %d0,PENDING
9:      rts

| post_load: d0 = 1 when CS1's RESID and ASSIGN replace the file's (the
| power-up). Then READY, the CS1 copy, the current pattern's Kit.
post_load:
        movel   %d0,%d7
        movel   PENDING,%d0
        cmpil   #2,%d0
        bne.s   1f
        bsr.w   migrate
        bra.s   2f
1:      cmpil   #3,%d0
        bne.s   3f
        bsr.w   v3_import
2:      clrl    PENDING
        bsr.w   write_kits
        tstl    %d0
        sne     %d0
        extb.l  %d0
        negl    %d0
        movel   %d0,KDIRTY
        bra.s   4f
3:      tstl    %d7
        beq.s   4f
        bsr.w   cs1_load
4:      movel   #MAGIC,%d0
        movel   %d0,KMAGIC
        lea     LRU,%a0
        moveq   #63,%d1
5:      clrl    %a0@+
        subql   #1,%d1
        bpl.s   5b
        tstl    NOWRITE                 | a refused kits.work: the Parts as stock
        bne.s   6f
        moveq   #1,%d0
        movel   %d0,READY
        movel   %d0,JUSTLOADED
        bsr.w   cs1_save
        moveq   #0,%d0
        moveb   CUR_BANK,%d0
        moveq   #0,%d1
        moveb   CUR_PTN,%d1
        andil   #15,%d1
        moveq   #1,%d2
        bra.w   kits_stage
6:      rts

| forget_bank: d0 = bank: its slots' Kits unknown.
forget_bank:
        lsll    #2,%d0
        lea     KIMG+O_RESID,%a0
        moveq   #-1,%d1
        moveb   %d1,%a0@(0,%d0:l)
        moveb   %d1,%a0@(1,%d0:l)
        moveb   %d1,%a0@(2,%d0:l)
        moveb   %d1,%a0@(3,%d0:l)
        rts

| lib_empty: no Kit, no assignment, no slot holds one.
lib_empty:
        lea     KIMG+O_ASSIGN,%a0
        moveq   #-1,%d0
        moveq   #63,%d1
1:      movel   %d0,%a0@+
        subql   #1,%d1
        bpl.s   1b
        lea     KIMG+O_VALID,%a0
        moveq   #7,%d1
2:      clrl    %a0@+
        subql   #1,%d1
        bpl.s   2b
        lea     KIMG+O_RESID,%a0
        moveq   #15,%d1
3:      movel   %d0,%a0@+
        subql   #1,%d1
        bpl.s   3b
        lea     KIMG+O_LIB,%a0          | names cleared: a stale name never shows
        movel   #NKITS-1,%d1
4:      clrl    %a0@
        clrl    %a0@(4)
        lea     %a0@(REC),%a0
        subql   #1,%d1
        bpl.s   4b
        rts

| migrate: Kit bank*4+part = the stock Part as it plays (the working
| copy), its name; the slot holds it; each pattern with content plays its
| Part's Kit. Stock's saved copies are left as they are.
migrate:
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        moveq   #0,%d4                  | bank
1:      movel   %d4,%d0
        bsr.w   bank_at
        moveal  %a0,%a2
        moveq   #0,%d5                  | part
2:      movel   %d4,%d6
        lsll    #2,%d6
        addl    %d5,%d6                 | d6 = Kit = slot
        movel   %d6,%d0
        bsr.w   kit_at
        moveal  %a0,%a3
        movel   #PARTSZ,%d0
        mulu.l  %d5,%d0
        lea     %a2@(0,%d0:l),%a4
        moveal  %a4,%a1
        addal   #WORKOFF,%a1
        pea     PARTSZ
        movel   %a1,%sp@-
        pea     %a3@(R_PAY)
        jsr     MEMCPY
        lea     %sp@(12),%sp
        movel   %d5,%d0
        mulu.w  #7,%d0
        moveal  %a2,%a1
        addal   #PNAMES,%a1
        addal   %d0,%a1
        moveal  %a3,%a0
        bsr.w   name6
        clrb    %a3@(6)
        clrb    %a3@(7)
        movel   %d6,%d0
        bsr.w   set_valid
        lea     KIMG+O_RESID,%a0
        moveb   %d6,%a0@(0,%d6:l)
        addql   #1,%d5
        moveq   #4,%d0
        cmpl    %d5,%d0
        bne.w   2b
        moveq   #0,%d5                  | the patterns
5:      movel   %d4,%sp@-
        movel   %d5,%sp@-
        jsr     HASCONT
        addql   #8,%sp
        tstl    %d0
        beq.s   6f
        movel   %d4,%d0
        movel   %d5,%d1
        bsr.w   pbyte_at
        moveq   #0,%d0
        moveb   %a0@,%d0
        andil   #3,%d0
        movel   %d4,%d1
        lsll    #2,%d1
        addl    %d1,%d0
        movel   %d4,%d1
        lsll    #4,%d1
        addl    %d5,%d1
        lea     KIMG+O_ASSIGN,%a0
        moveb   %d0,%a0@(0,%d1:l)
6:      addql   #1,%d5
        moveq   #16,%d0
        cmpl    %d5,%d0
        bne.s   5b
        addql   #1,%d4
        cmpl    %d4,%d0
        bne.w   1b
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| ---------------------------------------------------- Em's v3 files ------
| kits3a.work and kits3b.work: 0x600 bytes of superblock and manifests
| (root at 0x200, overlay at 0x400: assignments at +0x20, their valid
| bits at +0x120, the generation at +20, CRC-32 at +0x1fc), then 256
| records of 0x1a00 ('OTK3KITS', flags at +9 (bit 0 occupied), the
| generation at +20, the Kit at +24, the name at +0x20, the Part at +0x28,
| CRC-32 at +0x19fc). Per Kit the newest generation of either file;
| ASSIGN from the newest manifest. Read, never written.

v3_present:
        lea     FMT_V3A,%a0
        lea     PATH,%a1
        bsr.w   path
        lea     PATH,%a0
        lea     MODE_R,%a1
        bsr.w   fopen
        tstl    %d0
        bmi.s   1f
        bsr.w   fclose
        moveq   #1,%d0
        rts
1:      lea     FMT_V3B,%a0
        lea     PATH,%a1
        bsr.w   path
        lea     PATH,%a0
        lea     MODE_R,%a1
        bsr.w   fopen
        tstl    %d0
        bmi.s   2f
        bsr.w   fclose
        moveq   #1,%d0
        rts
2:      moveq   #0,%d0
        rts

v3_import:
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        lea     V3GEN,%a0               | no record yet: generation 0, none taken
        movel   #NKITS-1,%d0
1:      clrl    %a0@+
        subql   #1,%d0
        bpl.s   1b
        lea     V3HAVE,%a0
        moveq   #7,%d0
2:      clrl    %a0@+
        subql   #1,%d0
        bpl.s   2b
        clrl    V3MGEN
        clrl    V3MHAVE
        lea     FMT_V3A,%a0
        bsr.w   v3_file
        lea     FMT_V3B,%a0
        bsr.w   v3_file
        bsr.w   infer_resid
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| v3_file: a0 = the name's format. Keeps d2-d7/a2-a6 (v3_import saved them).
v3_file:
        lea     PATH,%a1
        bsr.w   path
        lea     PATH,%a0
        lea     MODE_R,%a1
        bsr.w   fopen
        tstl    %d0
        bmi.w   vf_out
        lea     V3BUF,%a0               | the superblock and both manifests
        movel   #V3_RECS,%d0
        lea     F_READ,%a1
        bsr.w   fio
        subql   #1,%d0
        bne.w   vf_close
        lea     V3BUF+0x200,%a2
        bsr.w   v3_manifest
        lea     V3BUF+0x400,%a2
        bsr.w   v3_manifest
        moveq   #0,%d4                  | the Kit
vf_rec: lea     V3BUF,%a0
        movel   #V3_REC,%d0
        lea     F_READ,%a1
        bsr.w   fio
        subql   #1,%d0
        bne.w   vf_close
        lea     V3BUF,%a2
        movel   %a2@,%d0                | 'OTK3KITS'
        cmpil   #0x4f544b33,%d0
        bne.w   vf_next
        movel   %a2@(4),%d0
        cmpil   #0x4b495453,%d0
        bne.w   vf_next
        moveq   #0,%d0
        movew   %a2@(24),%d0
        cmpl    %d4,%d0
        bne.w   vf_next
        moveal  %a2,%a0
        movel   #0x19fc,%d0
        bsr.w   crc32
        cmpl    %a2@(0x19fc),%d0
        bne.w   vf_next
        movel   %d4,%d0                 | newer than what is taken?
        lsrl    #3,%d0
        lea     V3HAVE,%a0
        moveb   %a0@(0,%d0:l),%d1
        movel   %d4,%d0
        andil   #7,%d0
        btst    %d0,%d1
        beq.s   1f
        lea     V3GEN,%a0
        movel   %d4,%d0
        lsll    #2,%d0
        movel   %a2@(20),%d1
        cmpl    %a0@(0,%d0:l),%d1
        bls.w   vf_next
1:      lea     V3GEN,%a0
        movel   %d4,%d0
        lsll    #2,%d0
        movel   %a2@(20),%d1
        movel   %d1,%a0@(0,%d0:l)
        movel   %d4,%d0
        lsrl    #3,%d0
        lea     V3HAVE,%a0
        movel   %d4,%d1
        andil   #7,%d1
        bset    %d1,%a0@(0,%d0:l)
        movel   %d4,%d0
        bsr.w   kit_at
        moveal  %a0,%a3
        btst    #0,%a2@(9)
        bne.s   2f
        clrl    %a3@                    | an empty Kit
        clrl    %a3@(4)
        movel   %d4,%d0
        bsr.w   clr_valid
        bra.s   vf_next
2:      movel   %a2@(0x20),%a3@
        movel   %a2@(0x24),%a3@(4)
        clrb    %a3@(7)
        pea     PARTSZ
        pea     %a2@(0x28)
        pea     %a3@(R_PAY)
        jsr     MEMCPY
        lea     %sp@(12),%sp
        movel   %d4,%d0
        bsr.w   set_valid
vf_next:
        addql   #1,%d4
        cmpil   #NKITS,%d4
        bne.w   vf_rec
vf_close:
        bsr.w   fclose
vf_out: rts

| v3_manifest: a2 = a manifest block; the newest valid one gives ASSIGN.
v3_manifest:
        movel   %a2@,%d0                | 'OTK3ROOT' or 'OTK3LINK'
        cmpil   #0x4f544b33,%d0
        bne.s   9f
        moveal  %a2,%a0
        movel   #0x1fc,%d0
        bsr.w   crc32
        cmpl    %a2@(0x1fc),%d0
        bne.s   9f
        tstl    V3MHAVE
        beq.s   1f
        movel   %a2@(20),%d0
        cmpl    V3MGEN,%d0
        bls.s   9f
1:      movel   %a2@(20),%d0
        movel   %d0,V3MGEN
        moveq   #1,%d0
        movel   %d0,V3MHAVE
        lea     KIMG+O_ASSIGN,%a0
        moveal  %a2,%a1
        addal   #0x120,%a1              | the valid bits
        moveq   #0,%d2
2:      movel   %d2,%d0
        lsrl    #3,%d0
        moveb   %a1@(0,%d0:l),%d1
        movel   %d2,%d0
        andil   #7,%d0
        btst    %d0,%d1
        bne.s   3f
        moveq   #-1,%d1
        bra.s   4f
3:      moveb   %a2@(0x20,%d2:l),%d1
4:      moveb   %d1,%a0@(0,%d2:l)
        addql   #1,%d2
        cmpil   #NKITS,%d2
        bne.s   2b
9:      rts

| infer_resid: a slot holds Kit k when its working Part equals k's and a
| pattern of that bank pointing at the slot plays k.
infer_resid:
        lea     %sp@(-44),%sp
        movem.l %d2-%d7/%a2-%a6,%sp@
        moveq   #0,%d4                  | bank
1:      moveq   #0,%d5                  | pattern
2:      movel   %d4,%d0
        lsll    #4,%d0
        addl    %d5,%d0
        lea     KIMG+O_ASSIGN,%a0
        moveq   #0,%d6
        moveb   %a0@(0,%d0:l),%d6
        cmpil   #0xff,%d6
        beq.s   5f
        movel   %d4,%d0
        movel   %d5,%d1
        bsr.w   pbyte_at
        moveq   #0,%d7
        moveb   %a0@,%d7
        cmpil   #3,%d7
        bhi.s   5f
        movel   %d6,%d0
        bsr.w   kit_at
        lea     %a0@(R_PAY),%a3
        movel   %d4,%d0
        bsr.w   bank_at
        movel   #PARTSZ,%d0
        mulu.l  %d7,%d0
        moveal  %a0,%a2
        addal   #WORKOFF,%a2
        addal   %d0,%a2
        movel   #PARTSZ,%d0
3:      mvzb    %a2@+,%d1
        mvzb    %a3@+,%d2
        cmpl    %d2,%d1
        bne.s   5f
        subql   #1,%d0
        bne.s   3b
        movel   %d4,%d0
        lsll    #2,%d0
        addl    %d7,%d0
        lea     KIMG+O_RESID,%a0
        moveb   %d6,%a0@(0,%d0:l)
5:      addql   #1,%d5
        moveq   #16,%d0
        cmpl    %d5,%d0
        bne.s   2b
        addql   #1,%d4
        cmpl    %d4,%d0
        bne.w   1b
        movem.l %sp@,%d2-%d7/%a2-%a6
        lea     %sp@(44),%sp
        rts

| ============================================================ CS1 ==========
| cs1_save: RESID and ASSIGN into CS1, the magic written last.
cs1_save:
        lea     %sp@(-12),%sp
        movem.l %d0-%d1/%a0,%sp@
        clrl    KCS1A
        lea     KIMG+O_RESID,%a0
        lea     KCS1A+4,%a1
        moveq   #15,%d1
1:      movel   %a0@+,%a1@+
        subql   #1,%d1
        bpl.s   1b
        lea     KIMG+O_ASSIGN,%a0
        lea     KCS1B,%a1
        moveq   #63,%d1
2:      movel   %a0@+,%a1@+
        subql   #1,%d1
        bpl.s   2b
        bsr.s   cs1_sum
        movel   %d0,KCS1A+68
        movel   #CS1MAGIC,%d0
        movel   %d0,KCS1A
        movem.l %sp@,%d0-%d1/%a0
        lea     %sp@(12),%sp
        rts
cs1_sum:
        moveq   #0,%d0
        lea     KCS1A+4,%a0
        moveq   #15,%d1
1:      addl    %a0@+,%d0
        subql   #1,%d1
        bpl.s   1b
        lea     KCS1B,%a0
        moveq   #63,%d1
2:      addl    %a0@+,%d0
        subql   #1,%d1
        bpl.s   2b
        rts
| cs1_load: the CS1 copy, when whole, over RESID and ASSIGN.
cs1_load:
        movel   KCS1A,%d0
        cmpil   #CS1MAGIC,%d0
        bne.s   9f
        bsr.s   cs1_sum
        cmpl    KCS1A+68,%d0
        bne.s   9f
        lea     KCS1A+4,%a0
        lea     KIMG+O_RESID,%a1
        moveq   #15,%d1
1:      movel   %a0@+,%a1@+
        subql   #1,%d1
        bpl.s   1b
        lea     KCS1B,%a0
        lea     KIMG+O_ASSIGN,%a1
        moveq   #63,%d1
2:      movel   %a0@+,%a1@+
        subql   #1,%d1
        bpl.s   2b
        moveq   #1,%d0
        movel   %d0,KDIRTY
9:      rts

| ============================================================ helpers ======

| name6: a1 = a name -> a0: the stock Part name field, seven bytes: at
| most six characters, the rest NUL.
name6:  moveq   #7,%d1
1:      moveb   %a1@+,%d0
        moveb   %d0,%a0@+
        beq.s   3f
        subql   #1,%d1
        cmpil   #1,%d1
        bne.s   1b
2:      clrb    %a0@+
        subql   #1,%d1
        bne.s   2b
        rts
3:      subql   #1,%d1
        bne.s   2b
        rts

| kinit: the CRC table once.
kinit:  tstl    CRCREADY
        bne.s   9f
        lea     CRCTAB,%a0
        moveq   #0,%d0
1:      movel   %d0,%d1
        moveq   #7,%d2
2:      lsrl    #1,%d1
        bcc.s   3f
        eoril   #0xedb88320,%d1
3:      subql   #1,%d2
        bpl.s   2b
        movel   %d1,%a0@+
        addql   #1,%d0
        cmpil   #256,%d0
        bne.s   1b
        moveq   #1,%d0
        movel   %d0,CRCREADY
9:      rts

| crc32: a0 = data, d0 = length -> d0 = the CRC-32 (zlib's). Keeps d2-d7/a2-a6.
crc32:  movel   %d2,%sp@-
        movel   %a2,%sp@-
        movel   %d0,%d2
        moveq   #-1,%d0
        lea     CRCTAB,%a2
        tstl    %d2
        beq.s   2f
1:      moveq   #0,%d1
        moveb   %a0@+,%d1
        eorl    %d0,%d1
        andil   #0xff,%d1
        lsrl    #8,%d0
        movel   %a2@(0,%d1:l:4),%d1
        eorl    %d1,%d0
        subql   #1,%d2
        bne.s   1b
2:      notl    %d0
        movel   %sp@+,%a2
        movel   %sp@+,%d2
        rts

| bank_at: d0 = bank -> a0 = its RAM (d0, d1 clobbered)
bank_at:
        movel   #BSTRIDE,%d1
        mulu.l  %d1,%d0
        addil   #BLOB,%d0
        moveal  %d0,%a0
        rts
| saved_at: d0 = part of the current bank -> a0 = its saved Part
saved_at:
        movel   #PARTSZ,%d1
        mulu.l  %d1,%d0
        addil   #SAVEDOFF,%d0
        addl    0x46c82456,%d0
        moveal  %d0,%a0
        rts
| pbyte_at: d0 = bank, d1 = pattern -> a0 = the pattern's Part byte
pbyte_at:
        movel   %d2,%sp@-
        movel   #BSTRIDE,%d2
        mulu.l  %d2,%d0
        movel   #PSTRIDE,%d2
        mulu.l  %d1,%d2
        addl    %d2,%d0
        addil   #BLOB+PBYTE,%d0
        moveal  %d0,%a0
        movel   %sp@+,%d2
        rts
| kit_at: d0 = Kit -> a0 = its record
kit_at: movel   #REC,%d1
        mulu.l  %d1,%d0
        addil   #KIMG+O_LIB,%d0
        moveal  %d0,%a0
        rts
| is_valid: d0 = Kit -> d0 = 1 when it holds a Part
is_valid:
        cmpil   #NKITS,%d0
        bcc.s   1f
        movel   %d0,%d1
        lsrl    #3,%d1
        lea     KIMG+O_VALID,%a0
        moveb   %a0@(0,%d1:l),%d1
        andil   #7,%d0
        btst    %d0,%d1
        sne     %d0
        extb.l  %d0
        negl    %d0
        rts
1:      moveq   #0,%d0
        rts
set_valid:
        movel   %d0,%d1
        lsrl    #3,%d1
        lea     KIMG+O_VALID,%a0
        andil   #7,%d0
        bset    %d0,%a0@(0,%d1:l)
        rts
clr_valid:
        movel   %d0,%d1
        lsrl    #3,%d1
        lea     KIMG+O_VALID,%a0
        andil   #7,%d0
        bclr    %d0,%a0@(0,%d1:l)
        rts

| ============================================================ data =========
FMT_WORK:  .asciz  "%s/kits.work"
FMT_STRD:  .asciz  "%s/kits.strd"
FMT_V3A:   .asciz  "%s/kits3a.work"
FMT_V3B:   .asciz  "%s/kits3b.work"
MODE_R:    .asciz  "r"
MODE_W:    .asciz  "w"
F_ROW:     .asciz  "%03d %s%s"
F_EMPTY:   .asciz  "%03d ---"
T_SPACE:   .asciz  ""
T_STAR:    .asciz  " *"
T_UNDO:    .asciz  "UNDO KIT"
T_LOADED:  .asciz  "KIT LOADED"
T_SAVED:   .asciz  "KIT SAVED"
T_EMPTY:   .asciz  "EMPTY KIT"
T_NOUNDO:  .asciz  "NO UNDO KIT"
T_KITNAME: .asciz  "KIT NAME"
DEFNAME:   .asciz  "NEW KIT"
        .align  4
LOADCB:    .long   load_yes
SAVECB:    .long   save_yes

| State in .text: the depacked window is RAM and starts zeroed at boot.
        .align  4
KMAGIC:    .long   0               | MAGIC once a project's Kits are known
KSTATE:                            | the counters, read by the gate in this order
READY:     .long   0               | Kits known for the loaded project
KDIRTY:    .long   0               | kits.work behind KIMG
NOWRITE:   .long   0               | kits.work refused: never overwritten
PENDING:   .long   0               | 2 migrate, 3 import, at the post step
CNT_ISR:   .long   0               | requests in interrupt context
CNT_NOSLOT: .long  0               | requests with no free slot
CNT_INVALID: .long 0               | assignments naming an empty Kit
CNT_IOERR: .long   0               | kits.work writes that failed
CNT_BADFILE: .long 0               | kits.work files refused
CNT_STAGED: .long  0               | Kits copied into a slot
CNT_REPOINT: .long 0               | Part bytes repointed
STAMP:     .long   0
CLEARING:  .long   0
CRCREADY:  .long   0
LM_MODE:   .long   0
JUSTLOADED: .long  0               | a LOAD PROJECT's banks are what RESID says
LI_SAVEDONLY: .long 0
LA_RET:    .long   0
LM_RET:    .long   0
BW_RET:    .long   0
PS_RET:    .long   0
PR_RET:    .long   0
MSEL:      .long   0
SAVEK:     .long   0
V3MGEN:    .long   0
V3MHAVE:   .long   0
UNDOKIT:   .byte   0xff
NAMEBUF:   .space  9
        .align  4

        .section .bss
        .align  4
KIMG:   .space  IMG_LEN
        .align  4
LRU:    .space  64*4
CRCTAB: .space  256*4
LBTAB:  .space  (NKITS+1)*4
CBTAB:  .space  (NKITS+1)*4
LBUF:   .space  NKITS*16
REFD:   .space  32
V3GEN:  .space  NKITS*4
V3HAVE: .space  32
FOBJ:   .space  24
PATH:   .space  260
PSRC:   .space  260
        .align  4
IOB:    .space  IOB_LEN
V3BUF:  .space  V3_REC
