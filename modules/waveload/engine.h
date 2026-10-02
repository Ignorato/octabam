/* Fixed-point port of CHOMPI WAVE's voice engine (subtractiveEngine.h,
 * WavetableManager.h, DJFilter.h, BasicMMF.h at CHOMPI-Club/CHOMPI
 * a73d732), mono. Derived from CHOMPI WAVE, Copyright (c) 2026 CHOMPI Club,
 * MIT License (README.md carries the notice).
 *
 * Formats: signal and filter state Q27, coefficients Q31, feedback and its
 * reciprocal Q26, LFO outputs Q30. mul() is the EMAC's fractional multiply,
 * (a * b) >> 31, which needs MACSR = 0x20 and ACC0 = 0 on entry. */
#pragma once
#include <stdint.h>

#ifndef EV
#define EV 8
#endif
#define FRAMES 33
#define FRAME_LEN 2048
#define FADE_LEN 960

typedef struct {
    uint32_t phase, base_inc;
    int32_t vgain;              /* 0.2 * velocity / 127, Q31 */
    int32_t env;                /* Q27 */
    int32_t mode, gate, gate_prev;
    int32_t lp0, lp1, hp0, hp1; /* Q27 */
} Voice;

typedef struct {
    Voice v[EV];
    const int16_t *table;       /* FRAMES x FRAME_LEN */
    int32_t cur, last, fading, fade_ctr;
    uint32_t flfo_ph, flfo_inc, plfo_ph, plfo_inc;
    int32_t flfo_amp, plfo_amp; /* Q31 */
    int32_t cutoff;             /* Q29 */
    int32_t res;                /* Q31, DjFilter's res_ (x .95) */
    int32_t lp, hp;             /* the slewed coefficients, Q31 */
    int32_t lp_y, hp_y;         /* 1 / (1 - lp), 1 / (1 - hp), Q26 */
    int32_t atk_d0, atk_tgt, rel_d0;  /* Q31, Q27, Q31 */
} Engine;

enum { C_BASEINC, C_VGAIN, C_GATE, C_CUTOFF, C_RES, C_FLFO_AMP, C_FLFO_INC,
       C_PLFO_AMP, C_PLFO_INC, C_ATK_D0, C_ATK_TGT, C_REL_D0, C_CYCLE, C_TABLE,
       C_INIT };

typedef struct { int16_t id, voice; int32_t val; } Cmd;

void eng_cmds(Engine *e, const Cmd *c, int n);
void eng_render(Engine *e, int32_t *out, int n);
