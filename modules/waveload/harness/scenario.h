/* The test scenario, in CHOMPI's own control terms, applied before each
 * 16-sample block. Shared by the float oracle and the fixed-point driver. */
#pragma once
#include <math.h>
#include <stdlib.h>
/* VMASK=0x01 etc. plays a subset of the eight notes */
static inline int vmask(void)
{
    const char *m = getenv("VMASK");
    return m ? (int)strtol(m, 0, 0) : 0xff;
}

#define SR 44100.0f
#define BLOCK 16
#define SECONDS 4.5f
#define NBLOCKS ((int)(SECONDS * SR / BLOCK))
#define NV 8

static const int kNotes[NV] = {12, 16, 19, 23, 24, 28, 31, 48}; /* transpose_nn */

typedef struct {
    int note_on;        /* voice index or -1 */
    int note_off_all;
    float cutoff;       /* setMasterCutoff, every block */
    float res;          /* setMasterResonance, <0 = unchanged */
    float flfo_depth;   /* <0 = unchanged */
    float plfo_depth;
    int cycle_step;     /* +1 / 0 */
} Ctl;

static inline float block_time(int b) { return b * BLOCK / SR; }

static inline int at(int b, float t) { return b == (int)(t * SR / BLOCK); }

static inline Ctl scenario(int b) {
    Ctl c = {-1, 0, 0.f, -1.f, -1.f, -1.f, 0};
    float t = block_time(b);
    for (int v = 0; v < NV; ++v)
        if (at(b, 0.1f * v) && (vmask() >> v & 1)) c.note_on = v;
    if (at(b, 3.5f)) c.note_off_all = 1;
    /* cutoff: 0.2 -> 1.0 over 0..3 s, then down to 0 at 4 s */
    c.cutoff = t < 3.f ? 0.2f + 0.8f * t / 3.f : fmaxf(0.f, 1.f - (t - 3.f));
    if (at(b, 2.0f)) c.res = 0.95f;
    if (at(b, 1.0f)) c.flfo_depth = 0.3f;
    if (at(b, 1.5f)) c.plfo_depth = 0.5f;
    /* a frame step every 0.2 s, and three 5 ms apart at 2.5 s (retargets) */
    for (int k = 1; k < 22; ++k)
        if (at(b, 0.2f * k)) c.cycle_step = 1;
    if (at(b, 2.505f) || at(b, 2.51f)) c.cycle_step = 1;
    return c;
}

/* CHOMPI's constants at the scenario's settings */
#define ATTACK_AMT 0.01f   /* setAttack: amount * 5 s */
#define RELEASE_AMT 0.3f   /* setRelease: seconds */
#define LFO_RATE 0.58f     /* both LFOs, the engine's init value */
#define VELOCITY 100.f
