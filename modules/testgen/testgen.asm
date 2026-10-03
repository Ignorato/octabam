; ---------------------------------------------------------------------------
; TESTGEN -- a measurement source: the track's audio is replaced by a known
; signal (modules/testgen/README.md, float reference testgen_ref.py, which
; holds every law below as the module computes it).
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
; ---- SWEEP: the same sine, its increment growing by r each sample --------------
;   inc is 48 bits ($03 integer, $04 fraction); p += inc_hi;
;   inc += (inc_hi * d) >> 12, d = (r - 1) * 2^35 from SWD: 20.0007 Hz to
;   20 kHz in N = (t + 1) s, then 1 s of silence with p and inc held at
;   their start, repeating.
; ---- WHITE: x' = 1664525 x + 1013904223 mod 2^24, each state a sample -----------
;   (the low word of the product: mpy, then asr 1 undoes the fractional doubling)
; ---- PINK: Kellet's three poles on WHITE, scaled by 0.11 (-14.4 dBFS RMS) ------
; ---- IMPULSE: one full-scale sample every (t + 1) / 4 s, from sample 0 ---------
;
; Every signal is full scale, then L = s * gL, R = s * gR, from LEVL and CHAN
; per block. A change of MODE, FREQ or LEN restarts every generator, so a
; capture lines up with the reference from the change on.
;
; ---- the P table (the manifest's ptable, 192 words) -------------------------
;   +0   LEVEL  10^(-(127 - k)/40), k = 0..127 (0.5 dB steps, 127 = $7fffff)
;   +128 FINC   the phase increment of FREQ step k, k = 0..31 (the ISO
;               third-octave centres, and A 440 between 400 and 500)
;   +160 SWN    the sweep's length in samples, LEN step t = LEN >> 3
;   +176 SWD    the sweep's growth, (r - 1) * 2^35
; The module (392 words) and its table fill PLATE REV's 594 words but for 10.
;
; ---- r7 slots ---------------------------------------------------------------
; persistent, set at init and on a restart:
;   $00 phase   $03 sweep inc (integer)   $04 sweep inc (fraction)
;   $05 sweep sample count   $06 the noise state   $07 $08 $09 pink's poles
;   $0a impulse countdown
; persistent, the knobs last block (init sets -1, so the first block restarts):
;   $01 FREQ index   $02 MODE   $0b LEN step
; per block (FINE is applied here, without a restart, so tuning by ear is smooth):
;   $10 gL   $11 gR   $12 the sine's inc   $13 the sweep's N   $14 d
;   $15 the impulse period less one   $16 N + the gap
;
; Every multiply is x0,x0, x1,x0 or x0,y1 (the signed encodings). The sine
; rounds (mpyr, macr, rnd): truncation left the peak 5 LSB short of full
; scale. Every Tcc reads the compare directly above it with only moves
; between. One branch per block picks the mode's loop; the loops are
; branch-free.
; ---------------------------------------------------------------------------

init:
        move    #>$ffffff,x0            ; no knob has this index: the first
        move    x0,x:(r7+$01)           ; block restarts every generator
        move    x0,x:(r7+$02)
        move    x0,x:(r7+$0b)
        clr     a
        move    a,x:(r7+$00)            ; every slot a loop reads before it
        move    a,x:(r7+$03)            ; writes (verify_dirtystate)
        move    a,x:(r7+$04)
        move    a,x:(r7+$05)
        move    a,x:(r7+$06)
        move    a,x:(r7+$07)
        move    a,x:(r7+$08)
        move    a,x:(r7+$09)
        move    a,x:(r7+$0a)
        rts

proc:
; ---- per block: MODE (slot 6), FREQ, LEN; any change restarts -----------------
        move    #0,y0
        clr     b                       ; the change flag
        move    x:(r6+$c),a             ; MODE, slot 6: the value in bits 22..16
        and     #>$7f0000,a
        asr     #$10,a,a
        move    #>$000004,x0
        cmp     x0,a
        tgt     y0,a                    ; an invalid saved byte -> SINE
        move    a1,x1                   ; mode
        move    x:(r7+$02),a
        cmp     x1,a
        tne     x0,b                    ; changed (x0 is non-zero)
        move    x1,x:(r7+$02)
        move    x:(r6+$1),a             ; FREQ: value/128 in bits 22..16
        and     #>$7f0000,a
        asr     #$10,a,a
        move    #>$00001f,x0            ; 31, the last step (20 kHz)
        cmp     x0,a
        tgt     x0,a
        move    a1,y1
        move    x:(r7+$01),a
        cmp     y1,a
        tne     x0,b
        move    y1,x:(r7+$01)
        move    x:(r6+$2),a             ; LEN: the step t in bits 22..19
        and     #>$780000,a
        asr     #$13,a,a
        move    a1,y1
        move    x:(r7+$0b),a
        cmp     y1,a
        tne     x0,b
        move    y1,x:(r7+$0b)
        tst     b
        beq     tg_keep
        clr     a                       ; restart every generator
        move    a,x:(r7+$00)
        move    a,x:(r7+$04)
        move    a,x:(r7+$05)
        move    a,x:(r7+$07)
        move    a,x:(r7+$08)
        move    a,x:(r7+$09)
        move    a,x:(r7+$0a)
        move    #>$001db9,x0            ; 7609: the sweep starts at 20.0007 Hz
        move    x0,x:(r7+$03)
        move    #>$000001,x0            ; the noise seed
        move    x0,x:(r7+$06)
tg_keep:
; ---- the tables -------------------------------------------------------------------
        move    #>$ffffff,m5
        move    #>$fab1e0,r4            ; the table base
        move    r4,r5
        move    x:(r7+$01),a
        add     #>$000080,a             ; + 128, FINC
        move    a1,n5
        move    (r5)+n5
        move    p:(r5),x1               ; FINC[k]
; FINE: inc = FINC[k] * 2^(y/3), y = value/128 - 1/2: +-200 cents, 3.125 a step.
; m/2 = 1/2 + y (a/2 + y (a^2/4 + y (a^3/12 + y a^4/48))), a = ln 2 / 3:
; within 1.9e-7 of 2^(y/3) (0.0002 Hz at 1 kHz); FINE 0 gives m/2 = 1/2
; exactly, so the tone is FINC[k]'s, bit for bit.
        move    x:(r6+$3),a
        and     #>$7fffff,a
        sub     #>$400000,a
        move    a,y1                    ; y
        move    #>$0001f2,x0            ; a^4/48
        move    #>$0021ae,a             ; a^3/12
        mac     x0,y1,a
        move    a,x0
        move    #>$01b552,a             ; a^2/4
        mac     x0,y1,a
        move    a,x0
        move    #>$0ec982,a             ; a/2
        mac     x0,y1,a
        move    a,x0
        move    #>$400000,a             ; 1/2
        mac     x0,y1,a
        move    a,x0                    ; m/2
        mpy     x1,x0,a
        asl     #$1,a,a                 ; FINC[k] m
        rnd     a
        move    #>$74198b,x0            ; 20 kHz (FINC[31]): FINE does not go above it (near
        cmp     x0,a                    ; 22.05 kHz a sine is a few samples a cycle)
        tgt     x0,a
        move    a,x:(r7+$12)            ; the sine's inc
        move    r4,r5
        move    x:(r7+$0b),a
        add     #>$0000a0,a             ; + 160, SWN
        move    a1,n5
        move    (r5)+n5
        move    p:(r5),a
        move    a,x:(r7+$13)            ; N
        add     #>$00ac44,a             ; + 44100, the gap
        move    a,x:(r7+$16)
        move    x:(r7+$13),a            ; the impulse period, N/4 = (t + 1) 11025,
        asr     #$2,a,a                 ; less one
        sub     #>$000001,a
        move    a,x:(r7+$15)
        move    #>$000010,n5            ; + 16, SWD
        move    (r5)+n5
        move    p:(r5),x0
        move    x0,x:(r7+$14)           ; d
        move    r4,r5
        move    x:(r6+$0),a             ; LEVL: value/128 in bits 22..16
        and     #>$7f0000,a
        asr     #$10,a,a
        move    a1,n5
        move    (r5)+n5
        move    p:(r5),b                ; g
        move    b,y1
; ---- CHAN (slot 8): L+R, L, R, L and inverted R -------------------------------
        neg     b
        move    b,x0
        move    x0,x:(r7+$11)           ; -g, for a moment
        move    x:(r6+$d),a
        and     #>$7f0000,a
        asr     #$10,a,a                ; chan
        move    y1,b                    ; gL = g
        move    #>$000002,x0
        cmp     x0,a
        teq     y0,b                    ; R only -> 0
        move    b,x:(r7+$10)
        move    x:(r7+$11),x0           ; -g
        move    y1,b                    ; gR = g
        move    #>$000001,y1
        cmp     y1,a
        teq     y0,b                    ; L only -> 0
        move    #>$000003,y1
        cmp     y1,a
        teq     x0,b                    ; L and inverted R -> -g
        move    b,x:(r7+$11)
        move    #$1,n0
; ---- the mode's loop ---------------------------------------------------------------
        move    x:(r7+$02),a            ; mode
        tst     a
        beq     tg_sin
        move    #>$000001,x0
        cmp     x0,a
        beq     tg_swp
        move    #>$000002,x0
        cmp     x0,a
        beq     tg_pnk
        move    #>$000003,x0
        cmp     x0,a
        beq     tg_wht
        bra     tg_imp

; ---- SINE ---------------------------------------------------------------------------
tg_sin:
        do      n7,>tg_xsin
        move    x:(r7+$00),b            ; p
        move    x:(r7+$12),x0
        move    b,a
        add     x0,a
        move    a1,x:(r7+$00)           ; p + inc, wrapped (a1 is not limited)
        bsr     tg_core                 ; x0 = sin(pi b)
        move    x:(r7+$10),y1           ; gL
        mpyr    x0,y1,a
        move    a,x:(r0)+
        move    x:(r7+$11),y1           ; gR
        mpyr    x0,y1,a
        move    a,x:(r0)+
tg_xsin:
        nop
        rts

; ---- SWEEP --------------------------------------------------------------------------
tg_swp:
        do      n7,>tg_xswp
        move    x:(r7+$00),b            ; p
        bsr     tg_core
        move    x0,y0                   ; s
; p += inc_hi; inc += (inc_hi * d) >> 12
        move    x:(r7+$03),x0           ; inc_hi
        move    x:(r7+$00),a
        add     x0,a
        move    a1,x:(r7+$00)
        move    x:(r7+$14),y1           ; d
        mpy     x0,y1,a                 ; 2 inc_hi d, in units of 2^-47
        asr     #$c,a,a
        move    x:(r7+$03),b
        move    x:(r7+$04),b0
        add     a,b
        move    b1,x:(r7+$03)
        move    b0,x:(r7+$04)
; past the sweep (count >= N): silence, and p and inc held at their start
        move    #0,x0
        move    #>$001db9,x1            ; 7609
        move    x:(r7+$13),y1           ; N
        move    x:(r7+$05),a            ; count
        move    y0,b
        cmp     y1,a
        tge     x0,b                    ; s -> 0
        move    b,y0
        move    x:(r7+$00),b
        cmp     y1,a
        tge     x0,b                    ; p -> 0
        move    b1,x:(r7+$00)
        move    x:(r7+$03),b
        move    x:(r7+$04),b0
        cmp     y1,a
        tge     x1,b                    ; inc -> 7609.0 (b0 cleared)
        move    b1,x:(r7+$03)
        move    b0,x:(r7+$04)
        add     #>$000001,a             ; count + 1, back to 0 after the gap
        move    x:(r7+$16),y1
        cmp     y1,a
        teq     x0,a
        move    a1,x:(r7+$05)
        move    y0,x0
        move    x:(r7+$10),y1           ; gL
        mpyr    x0,y1,a
        move    a,x:(r0)+
        move    x:(r7+$11),y1           ; gR
        mpyr    x0,y1,a
        move    a,x:(r0)+
tg_xswp:
        nop
        rts

; ---- PINK ---------------------------------------------------------------------------
tg_pnk:
        do      n7,>tg_xpnk
        move    x:(r7+$06),x0           ; white, as WHITE
        move    #>$19660d,y1            ; 1664525
        mpy     x0,y1,a
        asr     #$1,a,a
        move    a0,x0
        move    x0,a
        add     #>$6ef35f,a             ; 1013904223 mod 2^24
        move    a1,x:(r7+$06)
        move    a1,x1                   ; w
        move    #>$7fb2ff,x0            ; 0.99765
        move    x:(r7+$07),y1
        mpy     x0,y1,a
        move    #>$016502,x0            ; 0.0990460 * 0.11
        macr    x1,x0,a
        move    a,x:(r7+$07)
        move    #>$7b4396,x0            ; 0.963
        move    x:(r7+$08),y1
        mpy     x0,y1,a
        move    #>$042cca,x0            ; 0.2965164 * 0.11
        macr    x1,x0,a
        move    a,x:(r7+$08)
        move    #>$48f5c3,x0            ; 0.57
        move    x:(r7+$09),y1
        mpy     x0,y1,a
        move    #>$0ed268,x0            ; 1.0526913 * 0.11
        macr    x1,x0,a
        move    a,x:(r7+$09)
        move    x:(r7+$07),a
        move    x:(r7+$08),x0
        add     x0,a
        move    x:(r7+$09),x0
        add     x0,a
        move    #>$029a1c,x0            ; 0.1848 * 0.11
        macr    x1,x0,a
        move    a,x0                    ; s (limited)
        move    x:(r7+$10),y1           ; gL
        mpyr    x0,y1,a
        move    a,x:(r0)+
        move    x:(r7+$11),y1           ; gR
        mpyr    x0,y1,a
        move    a,x:(r0)+
tg_xpnk:
        nop
        rts

; ---- WHITE --------------------------------------------------------------------------
tg_wht:
        do      n7,>tg_xwht
        move    x:(r7+$06),x0
        move    #>$19660d,y1            ; 1664525
        mpy     x0,y1,a                 ; 2 A x
        asr     #$1,a,a                 ; A x: its low word is A x mod 2^24
        move    a0,x0
        move    x0,a
        add     #>$6ef35f,a             ; 1013904223 mod 2^24
        move    a1,x:(r7+$06)           ; (a1 is not limited: mod 2^24)
        move    a1,x0                   ; s
        move    x:(r7+$10),y1           ; gL
        mpyr    x0,y1,a
        move    a,x:(r0)+
        move    x:(r7+$11),y1           ; gR
        mpyr    x0,y1,a
        move    a,x:(r0)+
tg_xwht:
        nop
        rts

; ---- IMPULSE ------------------------------------------------------------------------
tg_imp:
        do      n7,>tg_ximp
        clr     b
        move    #>$7fffff,x0
        move    x:(r7+$0a),a            ; countdown
        tst     a
        teq     x0,b                    ; 0 -> full scale
        move    b,y0                    ; s
        sub     #>$000001,a
        move    x:(r7+$15),x0           ; the period less one
        tmi     x0,a
        move    a1,x:(r7+$0a)
        move    y0,x0
        move    x:(r7+$10),y1           ; gL
        mpyr    x0,y1,a
        move    a,x:(r0)+
        move    x:(r7+$11),y1           ; gR
        mpyr    x0,y1,a
        move    a,x:(r0)+
tg_ximp:
        nop
        rts

; ---- the sine core: x0 = sin(pi b), b the phase (a cycle is 2^24) ------------------
; Uses a, b, x0, x1, y1.
tg_core:
        sub     #>$400000,b             ; the quarter wave: u = 2 (1/2 - |wrap(p - 1/2)|)
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
        rts
