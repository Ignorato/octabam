; ---------------------------------------------------------------------------
; VOCODER -- a ten-band channel vocoder after the Roland VP-330
; (modules/vocoder/DESIGN.md; float reference vocoder_ref.py, which holds the
; law in this form).
;
; Insert contract: frames in place at x:(r0)/x:(r0+n0), knobs from r6,
; state in this instance's r7 block. No bus, no buffers, no shared window.
; Uses r4, r5 (m5 linear); r1 is left alone.
;
; ---- the law ------------------------------------------------------------------
;   m = (L + R)/2 (INT) or L (EXT);  c = 0.3 saw(NOTE) + 0.2 saw(NOTE + 12) (INT)
;       or R/2 (EXT); the two sawtooths share one 24-bit phase (the 4' is the
;       phase doubled), polyBLEP, branch-free
;   each band k: two Chamberlin band-pass sections (f1, then f2, Q 7), each
;       input scaled by q = 1/7 so a section peaks at its input's level; the
;       same pair on m and on c
;   v = (W_k/2) |band_k(m)|;  e += 0.073 (v - e) rising, 0.00227 falling
;       (0.3 ms, 10 ms), e in 48 bits: in 24 it stuck above zero in a pause
;   out = LEVL limit(2^8 sum_k e_k band_k(c) + 4 CONS hp6(m/2) + DRY m)
;   hp6: three Chamberlin high-pass sections at 4 kHz (Q 0.518, 0.707, 1.932),
;       q/2 stored and applied twice (q is above 1)
;
; ---- the P table (the manifest's ptable, 152 words) -------------------------
;   +0   BAND[10] x {f1, f2, W/2}
;   +30  NINC[61] the phase increment of NOTE step k (C1 + k), a cycle 2^24
;   +91  NIDT[61] 1/(du 2^11), du = NINC / 2^24
;
; ---- r7 slots ---------------------------------------------------------------
;   $00..$63 ten band blocks of 10, band k at 10k:
;       +0 +1 m section 1 (low, band)   +2 +3 m section 2   +4 +5 c section 1
;       +6 +7 c section 2   +8 +9 the envelope (high word, low word)
;   $64 the carrier phase   $65..$6a hp6: three sections of (low, band)
; per sample: $6b q m   $6c q c   $6d $6e the band sum (48 bits)   $6f m
; per block:  $70 NINC   $71 NIDT   $72 CONS   $73 DRY   $74 LEVL   $75 MODE
;             $76 the table base   $77 NIDT/2 (for the 4' sawtooth)
;
; Every multiply is one of the valid signed pairs (x0,y1  y0,x0  x1,x0  y1,x1
; x1,y0  x0,x0). Every Tcc reads the arithmetic directly above it, with only
; moves between.
; ---------------------------------------------------------------------------

init:
        move    #>$ffffff,m5
        move    r7,r5
        clr     a
        rep     #$6b                    ; every persistent slot, $00..$6a
        move    a,x:(r5)+
        rts

proc:
; ---- per block: the knobs ---------------------------------------------------------
        move    #>$ffffff,m5
        move    #>$fab1e0,r4            ; the table base
        move    r4,x:(r7+$76)
        move    x:(r6+$0),a             ; NOTE: the step in bits 16 and up
        and     #>$7f0000,a
        asr     #$10,a,a
        move    #>$00003c,x0            ; 60, C6
        cmp     x0,a
        tgt     x0,a
        add     #>$00001e,a             ; + 30, NINC
        move    a1,n5
        move    r4,r5
        move    (r5)+n5
        move    p:(r5),x0
        move    x0,x:(r7+$70)
        move    #>$00003d,n5            ; + 61, NIDT
        move    (r5)+n5
        move    p:(r5),a
        move    a,x:(r7+$71)
        asr     #$1,a,a
        move    a,x:(r7+$77)
        move    x:(r6+$1),a             ; CONS: value/128
        and     #>$7f0000,a
        move    a,x:(r7+$72)
        move    x:(r6+$2),a             ; DRY: value/128
        and     #>$7f0000,a
        move    a,x:(r7+$73)
        move    x:(r6+$3),a             ; LEVL: value/128, 127 pinned to full
        and     #>$7f0000,a
        move    #>$7f0000,x0
        cmp     x0,a
        move    #>$7fffff,x0
        teq     x0,a
        move    a,x:(r7+$74)
        move    x:(r6+$c),a             ; MODE, slot 6: 0 INT, 1 EXT
        and     #>$7f0000,a
        asr     #$10,a,a
        move    a1,x:(r7+$75)
        move    #$1,n0

        do      n7,>vc_end
; ---- the modulator: (L + R)/2, or L with MODE EXT -----------------------------------
        move    x:(r0),x1               ; L
        move    x1,a
        asr     #$1,a,a
        move    x:(r0+n0),b             ; R
        asr     #$1,b,b
        add     b,a                     ; (L + R)/2
        move    x:(r7+$75),b
        tst     b
        tne     x1,a                    ; EXT -> L
        move    a,x:(r7+$6f)            ; m
        move    a,y0
        move    #>$124925,x1            ; q = 1/7
        mpyr    x1,y0,a
        move    a,x:(r7+$6b)            ; q m
; ---- the carrier: two polyBLEP sawtooths on one phase, or R/2 ----------------------
        move    x:(r7+$64),b            ; s, the 8' phase
        move    x:(r7+$71),y1           ; 1/(du 2^11)
        bsr     vc_blep                 ; x0 = the 8' sawtooth
        move    #>$266666,y1            ; 0.3
        mpy     x0,y1,a
        move    a,x:(r7+$6c)            ; (the 8' part, for a moment)
        move    x:(r7+$64),b
        asl     #$1,b,b
        move    b1,x0                   ; the 4' phase: doubled, wrapped
        move    x0,b
        move    x:(r7+$77),y1           ; du is twice as large: 1/(du 2^11) halved
        bsr     vc_blep                 ; x0 = the 4' sawtooth
        move    #>$19999a,y1            ; 0.2
        move    x:(r7+$6c),a
        mac     x0,y1,a                 ; 0.3 saw8 + 0.2 saw4
        move    x:(r0+n0),b             ; R
        asr     #$1,b,b
        move    b,x1                    ; R/2
        move    x:(r7+$75),b
        tst     b
        tne     x1,a                    ; EXT -> R/2
        move    a,y0
        move    #>$124925,x1            ; q
        mpyr    x1,y0,a
        move    a,x:(r7+$6c)            ; q c
        move    x:(r7+$64),a            ; the phase advances
        move    x:(r7+$70),x0
        add     x0,a
        move    a1,x:(r7+$64)           ; (a1 is not limited: it wraps)
; ---- the ten bands ---------------------------------------------------------------------
        clr     a
        move    a,x:(r7+$6d)
        move    a,x:(r7+$6e)
        move    x:(r7+$76),r4           ; BAND
        move    r7,r5
        move    #>$00000a,n5
        do      #10,>vc_bend
; m, section 1 (f1); x1 = q throughout the four sections
        move    p:(r4)+,x0              ; f1
        move    x:(r5),a                ; low
        move    x:(r5+1),y1             ; band
        macr    x0,y1,a                 ; low += f band
        move    a,x:(r5)
        move    x:(r7+$6b),b            ; q m
        sub     a,b
        macr    -y1,x1,b                ; hp = q m - low - q band
        move    b,y0
        move    y1,a
        macr    y0,x0,a                 ; band += f hp
        move    a,x:(r5+1)
; c, section 1 (f1)
        move    x:(r5+4),a
        move    x:(r5+5),y1
        macr    x0,y1,a
        move    a,x:(r5+4)
        move    x:(r7+$6c),b            ; q c
        sub     a,b
        macr    -y1,x1,b
        move    b,y0
        move    y1,a
        macr    y0,x0,a
        move    a,x:(r5+5)
; m, section 2 (f2): its input is q times section 1's band
        move    x:(r5+1),y0
        mpy     x1,y0,b
        move    p:(r4)+,x0              ; f2
        move    x:(r5+2),a
        move    x:(r5+3),y1
        macr    x0,y1,a
        move    a,x:(r5+2)
        sub     a,b
        macr    -y1,x1,b
        move    b,y0
        move    y1,a
        macr    y0,x0,a
        move    a,x:(r5+3)
; c, section 2 (f2)
        move    x:(r5+5),y0
        mpy     x1,y0,b
        move    x:(r5+6),a
        move    x:(r5+7),y1
        macr    x0,y1,a
        move    a,x:(r5+6)
        sub     a,b
        macr    -y1,x1,b
        move    b,y0
        move    y1,a
        macr    y0,x0,a
        move    a,x:(r5+7)
        move    a,x1                    ; the carrier's band
; the envelope: v = (W/2) |m band|, e += 0.00227 d + 0.0706 max(d, 0), 48 bits
        move    x:(r5+3),a
        abs     a
        move    a,y0
        move    p:(r4)+,x0              ; W/2
        mpy     y0,x0,b                 ; v
        move    x:(r5+8),a
        move    x:(r5+9),a0             ; e
        move    #0,x0
        sub     a,b                     ; d = v - e
        move    b,y1
        tmi     x0,b                    ; max(d, 0)
        move    b,y0
        move    #>$004a38,x0            ; 0.00227: 10 ms
        mac     x0,y1,a
        move    #>$090749,x0            ; 0.0706: 0.3 ms, less the 10 ms term
        mac     y0,x0,a
        move    a1,x:(r5+8)
        move    a0,x:(r5+9)
; the VCA: the band sum += e (c band), 48 bits
        move    a,x0                    ; e, the high word
        move    x:(r7+$6d),b
        move    x:(r7+$6e),b0
        mac     x1,x0,b
        move    b1,x:(r7+$6d)
        move    b0,x:(r7+$6e)
        move    #>$124925,x1            ; q, for the next band
        move    (r5)+n5
vc_bend:
; ---- hp6: m/2 through three high-pass sections at 4 kHz --------------------------------
        move    x:(r7+$6f),a
        asr     #$1,a,a                 ; m/2
        move    #>$47f6e6,x0            ; f, 4 kHz
        move    a,b
        move    x:(r7+$65),a
        move    x:(r7+$66),y1
        macr    x0,y1,a
        move    a,x:(r7+$65)
        sub     a,b
        move    #>$7ba5c9,x1            ; q/2, Q 0.518
        macr    -y1,x1,b
        macr    -y1,x1,b
        move    b,y0
        move    y1,a
        macr    y0,x0,a
        move    a,x:(r7+$66)
        move    x:(r7+$67),a
        move    x:(r7+$68),y1
        macr    x0,y1,a
        move    a,x:(r7+$67)
        sub     a,b
        move    #>$5a82b2,x1            ; q/2, Q 0.707
        macr    -y1,x1,b
        macr    -y1,x1,b
        move    b,y0
        move    y1,a
        macr    y0,x0,a
        move    a,x:(r7+$68)
        move    x:(r7+$69),a
        move    x:(r7+$6a),y1
        macr    x0,y1,a
        move    a,x:(r7+$69)
        sub     a,b
        move    #>$2120c5,x1            ; q/2, Q 1.932
        macr    -y1,x1,b
        macr    -y1,x1,b
        move    b,y0
        move    y1,a
        macr    y0,x0,a
        move    a,x:(r7+$6a)
; ---- out = LEVL limit(2^8 sum + 4 CONS hp + DRY m) -------------------------------------
        move    y0,x0                   ; hp
        move    x:(r7+$72),y1           ; CONS
        mpy     x0,y1,b
        asl     #$2,b,b
        move    x:(r7+$6f),x0           ; m
        move    x:(r7+$73),y1           ; DRY
        mac     x0,y1,b
        move    x:(r7+$6d),a
        move    x:(r7+$6e),a0
        asl     #$8,a,a                 ; 2^8, the make-up gain
        add     a,b
        move    b,x0                    ; (limited)
        move    x:(r7+$74),y1           ; LEVL
        mpyr    x0,y1,a
        move    a,x:(r0)+
        move    a,x:(r0)+
vc_end:
        nop
        rts

; ---- x0 = the polyBLEP sawtooth at phase b; y1 = 1/(du 2^11); uses a, b, x0, x1 ----------
; corr = (1 - min(u/du, 1))^2 - (1 - min((1 - u)/du, 1))^2, u = s/2 + 1/2
vc_blep:
        move    b,x1                    ; s
        asr     #$1,b,b
        add     #>$400000,b             ; u
        move    #>$7fffff,a
        sub     b,a                     ; 1 - u
        move    a,x0
        mpy     x0,y1,a                 ; (1 - u)/(du 2^11)
        move    #>$001000,x0            ; 2^-11
        cmp     x0,a
        tgt     x0,a                    ; min(., 2^-11)
        asl     #$b,a,a
        move    a,x0                    ; t_b (1.0 limited)
        move    #>$7fffff,a
        sub     x0,a
        move    a,x0
        mpyr    x0,x0,a                 ; (1 - t_b)^2
        move    a,x0
        move    x1,a
        sub     x0,a                    ; s - (1 - t_b)^2
        move    a,x1
        move    b,x0                    ; u
        mpy     x0,y1,a                 ; u/(du 2^11)
        move    #>$001000,x0
        cmp     x0,a
        tgt     x0,a
        asl     #$b,a,a
        move    a,x0                    ; t_a
        move    #>$7fffff,a
        sub     x0,a
        move    a,x0
        mpyr    x0,x0,a                 ; (1 - t_a)^2
        add     x1,a
        move    a,x0                    ; (limited)
        rts
