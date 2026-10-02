/* Native driver for the fixed engine: converts the scenario's CHOMPI
 * control values to the engine's fixed-point commands (the work a ColdFire
 * control path would do per knob change, not priced here), renders, and
 * writes the command stream and table for the ColdFire run.
 * usage: host_fixed table.wav out.f32 cmds.bin table.bin TABLE_ADDR */
#include "../engine.h"
#include "scenario.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern long eng_ovf;
static int16_t table[FRAMES * FRAME_LEN];
static Engine eng;

static int32_t q(double v, int frac)
{
    double r = v * (double)(1LL << frac);
    r = r < 0 ? r - 0.5 : r + 0.5;
    if (r > 2147483647.0) r = 2147483647.0;
    if (r < -2147483648.0) r = -2147483648.0;
    return (int32_t)r;
}

static FILE *fc;
static Cmd buf[64];
static int nb;
static void cmd(int id, int voice, int32_t val) { buf[nb++] = (Cmd){(int16_t)id, (int16_t)voice, val}; }
static void put_be(uint32_t x) { unsigned char b[4] = {x >> 24, x >> 16, x >> 8, x}; fwrite(b, 1, 4, fc); }
static void flush(void)
{
    put_be(nb);
    for (int i = 0; i < nb; ++i) {
        unsigned char b[8] = {(unsigned)buf[i].id >> 8, buf[i].id, (unsigned)buf[i].voice >> 8, buf[i].voice,
                              (uint32_t)buf[i].val >> 24, (uint32_t)buf[i].val >> 16, (uint32_t)buf[i].val >> 8, (uint32_t)buf[i].val};
        fwrite(b, 1, 8, fc);
    }
    eng_cmds(&eng, buf, nb);
    nb = 0;
}

int main(int argc, char **argv)
{
    static float tf[FRAMES * FRAME_LEN];
    FILE *f = fopen(argv[1], "rb");
    fseek(f, 136, SEEK_SET);
    if (fread(tf, 4, FRAMES * FRAME_LEN, f) != FRAMES * FRAME_LEN) return 1;
    fclose(f);
    for (int i = 0; i < FRAMES * FRAME_LEN; ++i) {
        long s = lrintf(tf[i] * 32768.f);
        table[i] = s > 32767 ? 32767 : s < -32768 ? -32768 : (int16_t)s;
    }
    FILE *ft = fopen(argv[4], "wb");
    for (int i = 0; i < FRAMES * FRAME_LEN; ++i) { unsigned char b[2] = {(uint16_t)table[i] >> 8, table[i]}; fwrite(b, 1, 2, ft); }
    fclose(ft);
    uint32_t table_addr = strtoul(argv[5], 0, 0);

    fc = fopen(argv[3], "wb");
    eng.table = table;
    cmd(C_TABLE, 0, (int32_t)table_addr);
    cmd(C_INIT, 0, 0);
    float lfo_hz = .14f * powf(65.41f / .14f, LFO_RATE);
    cmd(C_FLFO_INC, 0, (int32_t)(uint32_t)llround(lfo_hz / SR * 4294967296.0));
    cmd(C_PLFO_INC, 0, (int32_t)(uint32_t)llround(lfo_hz / SR * 4294967296.0));
    cmd(C_RES, 0, q(.63f * .95f, 31));
    float tgt = 9.f * powf(1.f, 10.f) + 0.3f * 1.f + 1.01f;
    float atk = 1.f - expf(logf(1.f - 1.f / tgt) / (ATTACK_AMT * 5.f * SR));
    float rel = 1.f - expf(logf(1. / M_E) / (RELEASE_AMT * SR));
    cmd(C_ATK_D0, 0, q(atk, 31));
    cmd(C_ATK_TGT, 0, q(tgt, 27));
    cmd(C_REL_D0, 0, q(rel, 31));
    /* the C_TABLE word is the ColdFire address; natively the pointer stays */
    eng_cmds(&eng, buf + 1, nb - 1);
    put_be(nb);
    for (int i = 0; i < nb; ++i) {
        unsigned char b[8] = {(unsigned)buf[i].id >> 8, buf[i].id, (unsigned)buf[i].voice >> 8, buf[i].voice,
                              (uint32_t)buf[i].val >> 24, (uint32_t)buf[i].val >> 16, (uint32_t)buf[i].val >> 8, (uint32_t)buf[i].val};
        fwrite(b, 1, 8, fc);
    }
    nb = 0;

    float *out = malloc(sizeof(float) * NBLOCKS * BLOCK);
    FILE *fr = argc > 6 ? fopen(argv[6], "wb") : 0;
    int32_t blk[BLOCK];
    for (int b = 0; b < NBLOCKS; ++b) {
        Ctl c = scenario(b);
        if (c.note_on >= 0 && c.note_on < EV) {
            int v = c.note_on;
            float hz = 440.f * pow(2.f, ((kNotes[v] + 36 - 57 + 0) / 12.f));
            cmd(C_BASEINC, v, (int32_t)(uint32_t)llround(hz / SR * 4294967296.0));
            cmd(C_VGAIN, v, q(.2 * (VELOCITY * 0.00787401f), 31));
            cmd(C_GATE, v, 1);
        }
        if (c.note_off_all) for (int v = 0; v < EV; ++v) cmd(C_GATE, v, 0);
        cmd(C_CUTOFF, 0, q(c.cutoff, 29));
        if (c.res >= 0) cmd(C_RES, 0, q(fminf(fmaxf(c.res, 0.f), .99f) * .95f, 31));
        if (c.flfo_depth >= 0) cmd(C_FLFO_AMP, 0, q(c.flfo_depth, 31));
        if (c.plfo_depth >= 0) cmd(C_PLFO_AMP, 0, q(c.plfo_depth, 31));
        if (c.cycle_step) cmd(C_CYCLE, 0, c.cycle_step);
        flush();
        eng_render(&eng, blk, BLOCK);
        for (int i = 0; i < BLOCK; ++i) out[b * BLOCK + i] = blk[i] / 134217728.f;
        if (fr) fwrite(blk, 4, BLOCK, fr);
    }
    fclose(fc);
    if (fr) fclose(fr);
    FILE *o = fopen(argv[2], "wb");
    fwrite(out, 4, NBLOCKS * BLOCK, o);
    fclose(o);
    fprintf(stderr, "fixed: %d samples, %ld shift overflows\n", NBLOCKS * BLOCK, eng_ovf);
    return 0;
}
