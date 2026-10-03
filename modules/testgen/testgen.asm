; ---------------------------------------------------------------------------
; TESTGEN -- a measurement source: the track's audio is replaced by a known
; signal (modules/testgen/README.md, float reference testgen_ref.py).
;
; Insert contract: frames in place at x:(r0)/x:(r0+n0), knobs from r6,
; state in this instance's r7 block. No bus, no buffers, no shared window.
;
; ---- SINE ---------------------------------------------------------------------
;   p  += inc                      24-bit phase, a cycle is 2^24 (wraps by
;                                  storing a1 unlimited)
;   r   = wrap(p - 1/2)            sin(pi p) = cos(pi r) = sin(pi (1/2 - |r|))
;   u   = 2 (1/2 - |r|)            in [-1, 1], +1 held at $7fffff
;   s   = u (c1 + w (c3 + w (c5 + w (c7 + w c9)))),  w = u^2
;         sin(pi u / 2) on Chebyshev nodes, max error 3.4e-9 (-169 dB);
;         the coefficients are stored halved and the product doubled
;   L   = s * gL,  R = s * gR      gL, gR from LEVL and CHAN, per block
; A change of FREQ or MODE restarts the phase at 0, so every tone starts
; at the same sample value as the reference.
;
; ---- the P table (the manifest's ptable, 159 words) -------------------------
;   +0   LEVEL  10^(-(127 - k)/40), k = 0..127 (0.5 dB steps, 127 = $7fffff)
;   +128 FINC   the phase increment of ISO third-octave k, k = 0..30
;
; ---- r7 slots ---------------------------------------------------------------
; persistent, set at init:
;   $00 phase   $01 the FREQ index last block   $02 the MODE last block
; per block:
;   $10 gL   $11 gR   $12 inc
;
; Every multiply is x0,x0, x1,x0 or x0,y1 (the signed encodings), and rounds
; (mpyr, macr, rnd): truncation left the peak 5 LSB short of full scale. Every Tcc
; reads the compare directly above it with only moves between. No branch.
; ---------------------------------------------------------------------------

init:
        clr     a
        move    a,x:(r7+$00)
        move    a,x:(r7+$01)
        move    a,x:(r7+$02)
        rts

proc:
; ---- per block: MODE (slot 6) and FREQ; a change restarts the phase ----------
        move    x:(r6+$c),a             ; MODE, slot 6: the value in bits 22..16
        and     #>$7f0000,a
        asr     #$10,a,a
        move    a1,x1                   ; mode
        move    x:(r6+$1),b             ; FREQ: value/128 in bits 22..16
        and     #>$7f0000,b
        asr     #$10,b,b
        move    #>$00001e,x0            ; 30, the last ISO third (20 kHz)
        cmp     x0,b
        tgt     x0,b
        move    b1,y1                   ; the FREQ index
        move    #0,x0
        move    x:(r7+$00),b            ; phase
        move    x:(r7+$01),a
        cmp     y1,a
        tne     x0,b                    ; FREQ changed -> phase 0
        move    x:(r7+$02),a
        cmp     x1,a
        tne     x0,b                    ; MODE changed -> phase 0
        move    b1,x:(r7+$00)
        move    y1,x:(r7+$01)
        move    x1,x:(r7+$02)
; ---- the increment and the level, from the P table ----------------------------
        move    #>$ffffff,m5
        move    #>$fab1e0,r4            ; the table base
        move    r4,r5
        move    y1,a
        add     #>$000080,a             ; + 128, FINC
        move    a1,n5
        move    (r5)+n5
        move    p:(r5),x0
        move    x0,x:(r7+$12)           ; inc
        move    r4,r5
        move    x:(r6+$0),a             ; LEVL: value/128 in bits 22..16
        and     #>$7f0000,a
        asr     #$10,a,a
        move    a1,n5
        move    (r5)+n5
        move    p:(r5),b                ; g
        move    #0,y0
        move    x1,a                    ; mode
        tst     a
        tne     y0,b                    ; not SINE -> silence (0.1 has SINE only)
        move    b,y1                    ; g
; ---- CHAN (slot 8): L+R, L, R, L and inverted R -------------------------------
        neg     b
        move    b,x1                    ; -g
        move    x:(r6+$d),a
        and     #>$7f0000,a
        asr     #$10,a,a                ; chan
        move    y1,b                    ; gL = g
        move    #>$000002,x0
        cmp     x0,a
        teq     y0,b                    ; R only -> 0
        move    b,x:(r7+$10)
        move    y1,b                    ; gR = g
        move    #>$000001,x0
        cmp     x0,a
        teq     y0,b                    ; L only -> 0
        move    #>$000003,x0
        cmp     x0,a
        teq     x1,b                    ; L and inverted R -> -g
        move    b,x:(r7+$11)
        move    #$1,n0

        do      n7,>tg_end
; ---- the phase: output p, then advance -----------------------------------------
        move    x:(r7+$00),b            ; p
        move    x:(r7+$12),x0
        move    b,a
        add     x0,a
        move    a1,x:(r7+$00)           ; p + inc, wrapped (a1 is not limited)
; ---- fold to the quarter wave: u = 2 (1/2 - |wrap(p - 1/2)|) -------------------
        sub     #>$400000,b
        move    b1,x0                   ; wrapped
        move    x0,b
        abs     b
        neg     b
        add     #>$400000,b
        asl     #$1,b,b
        move    b,y1                    ; u (+1 limited to $7fffff)
        move    y1,x0
        mpyr    x0,x0,a
        move    a,x1                    ; w = u^2
; ---- Horner, coefficients halved -----------------------------------------------
        move    #>$000279,x0            ;  c9/2 =  0.000150817160/2
        move    #>$ffb373,a             ;  c7/2 = -0.00467222026/2
        macr    x1,x0,a
        move    a,x0
        move    #>$05199e,a             ;  c5/2 =  0.0796884748/2
        macr    x1,x0,a
        move    a,x0
        move    #>$d6a889,a             ;  c3/2 = -0.645963358/2
        macr    x1,x0,a
        move    a,x0
        move    #>$6487ed,a             ;  c1/2 =  1.57079629/2
        macr    x1,x0,a
        move    a,x0                    ; P/2
        mpy     x0,y1,a                 ; s/2 = u P/2, 48 bits
        asl     #$1,a,a                 ; s
        rnd     a
        move    a,x0                    ; (limited)
; ---- out ----------------------------------------------------------------------
        move    x:(r7+$10),y1           ; gL
        mpyr    x0,y1,a
        move    a,x:(r0)+
        move    x:(r7+$11),y1           ; gR
        mpyr    x0,y1,a
        move    a,x:(r0)+
tg_end:
        nop
        rts
