| WAVE LOAD's entry from CF METER's m_isr: d1 = K, the instances to render
| this frame. Runs before the stock handler saves the EMAC, so it saves
| and restores what the engine touches (MACSR, ACC0, ACCext01) the way the
| handler does (0x4000ac96 / 0x4000d968: MACSR to integer mode before the
| accumulator moves). Every register is preserved.

        .text
        .globl  cl_load

cl_load:
        lea     -28(%sp),%sp
        movem.l %d0-%d4/%a0-%a1,(%sp)
        move.l  %macsr,%d2
        move.l  #0,%macsr
        move.l  %accext01,%d3
        movclr.l %acc0,%d4
        move.l  #0x20,%macsr                    | fractional, the engine's mul()
        move.l  %d1,-(%sp)
        jsr     cl_frame
        addq.l  #4,%sp
        move.l  #0,%macsr
        move.l  %d4,%acc0
        move.l  %d3,%accext01
        move.l  %d2,%macsr
        movem.l (%sp),%d0-%d4/%a0-%a1
        lea     28(%sp),%sp
        rts
