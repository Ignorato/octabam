/* Fixed-point CHOMPI WAVE voice engine; see engine.h for the formats and
 * the licence.
 * Every voice shares the cutoff, the LFOs, the resonance and the frame
 * crossfade in CHOMPI (setMasterCutoff, setCycle and setMasterResonance set
 * all eight alike), so those run once a sample here. DjFilter's `hp_ > .8`
 * branch is absent: hp_ is clamped to at most .9^3 = .729. */
#include "engine.h"

#ifdef __mcoldfire__
static inline int32_t mul(int32_t a, int32_t b)
{
    int32_t r;
    __asm__ volatile("mac.l %1,%2,%%acc0\n\tmovclr.l %%acc0,%0"
                     : "=r"(r) : "r"(a), "r"(b));
    return r;
}
#define SHL(x, n) ((x) << (n))
#else  /* the host build, for the comparison against CHOMPI's float code */
static inline int32_t mul(int32_t a, int32_t b)
{
    return (int32_t)(((int64_t)a * b) >> 31);
}
long eng_ovf;
static inline int32_t shl_chk(int32_t x, int n)
{
    int64_t r = (int64_t)x << n;
    if (r != (int32_t)r) eng_ovf++;
    return (int32_t)r;
}
#define SHL(x, n) shl_chk((x), (n))
#endif

enum { IDLE, ATTACK, DECAY, RELEASE };

#define ONE27 (1 << 27)
#define ONE26 (1 << 26)
#define REL_TARGET (-1342177)          /* -0.01, Q27 */
#define SLEW 429497                    /* fonepole .0002, Q31 */
#define LP_BIAS 2684355                /* .01, Q28 */
#define LP_MAX 263066746               /* .98, Q28 */
#define HP_K 2040109466                /* .95, Q31: 1.9c = mul(c, .95) << 1 */
#define HP_MAX 483183821               /* .9, Q29 */
#define FADE_STEP 1118481              /* 1 / 960, Q30 */

void eng_cmds(Engine *e, const Cmd *c, int n)
{
    for (; n > 0; --n, ++c) {
        Voice *v = &e->v[c->voice];
        switch (c->id) {
        case C_BASEINC: v->base_inc = (uint32_t)c->val; break;
        case C_VGAIN: v->vgain = c->val; break;
        case C_GATE: v->gate = c->val; break;
        case C_CUTOFF: e->cutoff = c->val; break;
        case C_RES: e->res = c->val; break;
        case C_FLFO_AMP: e->flfo_amp = c->val; break;
        case C_FLFO_INC: e->flfo_inc = (uint32_t)c->val; break;
        case C_PLFO_AMP: e->plfo_amp = c->val; break;
        case C_PLFO_INC: e->plfo_inc = (uint32_t)c->val; break;
        case C_ATK_D0: e->atk_d0 = c->val; break;
        case C_ATK_TGT: e->atk_tgt = c->val; break;
        case C_REL_D0: e->rel_d0 = c->val; break;
        case C_TABLE: e->table = (const int16_t *)(uintptr_t)(uint32_t)c->val; break;
        case C_INIT:
            e->lp_y = e->hp_y = ONE26;     /* 1 / (1 - 0) */
            e->plfo_ph = 1u << 30;         /* pitchLfo.PhaseAdd(.25f) */
            break;
        case C_CYCLE: {                    /* wavetable::cycleThroughTable(dir, false) */
            int retarget = e->fading && e->fade_ctr < FADE_LEN / 2;
            if (!retarget) e->last = e->cur;
            e->cur += c->val;
            if (e->cur < 0) e->cur = 0;
            if (e->cur > FRAMES - 1) e->cur = FRAMES - 1;
            e->fading = 1;
            if (!retarget) e->fade_ctr = 0;
            break;
        }
        }
    }
}

/* DaisySP's WAVE_TRI, Q30, before the phase advances */
static inline int32_t tri30(uint32_t ph)
{
    int32_t t = (int32_t)(ph ^ 0x80000000u) >> 1;
    if (t < 0) t = -t;
    return SHL(t, 1) - (1 << 30);
}

/* 2^x for |x| <= 1/6 (x Q30), cubic, result Q30 */
static inline int32_t exp2_30(int32_t x)
{
    int32_t y = mul(x, 1488522236);                /* x ln2, Q30 */
    int32_t y2 = mul(y, y);                        /* y^2 Q29 = y^2/2 Q30 */
    int32_t y3 = mul(y2, y);                       /* y^3 Q28 */
    return (1 << 30) + y + y2 + mul(y3, 1431655765);   /* + y^3 2/3 Q28 = y^3/6 Q30 */
}

void eng_render(Engine *e, int32_t *out, int n)
{
    const int16_t *cur = e->table + e->cur * FRAME_LEN;
    const int16_t *last = e->table + e->last * FRAME_LEN;

    for (; n > 0; --n) {
        /* LFOs (myEngine::Process) */
        int32_t flfo = mul(tri30(e->flfo_ph), e->flfo_amp);
        e->flfo_ph += e->flfo_inc;
        /* pitch: 2^(lfo * 2/12) */
        int32_t pl = mul(tri30(e->plfo_ph), e->plfo_amp);
        e->plfo_ph += e->plfo_inc;
        int32_t pmul = exp2_30(mul(pl, 357913941));   /* x 1/6 */

        /* DjFilter::SetControl + its fonepoles + BasicMMF::CalculateFeedback */
        int32_t c = e->cutoff + (flfo >> 1);           /* Q29 */
        int32_t x = LP_BIAS + c;                        /* .01 + 2c, Q28 */
        if (x < 0) x = 0;
        if (x > LP_MAX) x = LP_MAX;
        x = SHL(x, 3);
        int32_t lpt = mul(mul(x, x), x);
        int32_t h = SHL(mul(c, HP_K), 1) - (1 << 29);  /* 1.9c - 1, Q29 */
        if (h < 0) h = 0;
        if (h > HP_MAX) h = HP_MAX;
        h = SHL(h, 2);
        int32_t hpt = mul(mul(h, h), h);
        e->lp += mul(SLEW, lpt - e->lp);
        e->hp += mul(SLEW, hpt - e->hp);
        /* one Newton step from last sample's reciprocal */
        e->lp_y += SHL(mul(e->lp_y, ONE26 - mul(0x7fffffff - e->lp, e->lp_y)), 5);
        e->hp_y += SHL(mul(e->hp_y, ONE26 - mul(0x7fffffff - e->hp, e->hp_y)), 5);
        int32_t fbl = (e->res >> 5) + mul(e->res, e->lp_y);   /* Q26 */
        int32_t fbh = (e->res >> 5) + mul(e->res, e->hp_y);
        int32_t fl = e->lp, fh = e->hp;
        int32_t fa = e->fading ? e->fade_ctr * FADE_STEP : 0;

        int32_t sum = 0;
        Voice *v = e->v;
        for (int k = 0; k < EV; ++k, ++v) {
            /* wavetable::PopSample */
            uint32_t ph = v->phase;
            int idx = ph >> 21;
            int32_t fr = (ph >> 7) & 0x3fff;
            int32_t s1 = cur[idx], s2 = cur[(idx + 1) & (FRAME_LEN - 1)];
            int32_t s = (s1 << 12) + ((fr * (s2 - s1)) >> 2);
            if (e->fading) {
                int32_t l1 = last[idx], l2 = last[(idx + 1) & (FRAME_LEN - 1)];
                int32_t l = (l1 << 12) + ((fr * (l2 - l1)) >> 2);
                s = l + SHL(mul(s - l, fa), 1);
            }
            v->phase = ph + (uint32_t)SHL(mul((int32_t)v->base_inc, pmul), 1);

            /* Adsr::Process */
            int32_t g = v->gate;
            if (g && !v->gate_prev) v->mode = ATTACK;
            else if (!g && v->gate_prev) v->mode = RELEASE;
            v->gate_prev = g;
            int32_t env = v->env;
            if (v->mode == ATTACK) {
                env += mul(e->atk_d0, e->atk_tgt - env);
                if (env > ONE27) { env = ONE27; v->mode = DECAY; }
            } else if (v->mode == RELEASE) {
                env += mul(e->rel_d0, REL_TARGET - env);
                if (env < 0) { env = 0; v->mode = IDLE; }
            }
            v->env = env;
            int32_t smp = v->mode == IDLE ? 0 : SHL(mul(mul(s, v->vgain), env), 4);

            /* DjFilter::Process: BasicMMF low-pass, then high-pass */
            int32_t b0 = v->lp0, b1 = v->lp1;
            b0 += mul(fl, smp - b0 + SHL(mul(fbl, b0 - b1), 5));
            b1 += mul(fl, b0 - b1);
            v->lp0 = b0; v->lp1 = b1;
            int32_t h0 = v->hp0, h1 = v->hp1;
            h0 += mul(fh, b1 - h0 + SHL(mul(fbh, h0 - h1), 5));
            h1 += mul(fh, h0 - h1);
            v->hp0 = h0; v->hp1 = h1;
            sum += b1 - h0;
        }
        if (e->fading && ++e->fade_ctr >= FADE_LEN) e->fading = 0;
        *out++ = sum >> 3;
    }
}
