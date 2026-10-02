/* WAVE LOAD: K instances of the 4-voice engine rendered per frame
 * interrupt, output discarded. Each instance has its own table (a track
 * each, for the data cache), all four voices gated, and the frame
 * crossfade kept running (the dearest path: two table reads per voice).
 * The instruction path does not depend on the tables' values, only their
 * addresses, so they are not in the image: they are the platform reserve's
 * unwritten words from 1 MB above this unit's data (TABLES_OFFSET), well
 * above the packed stage and below the reserve's 10,487,808-byte ceiling
 * (the 1,622,016 B of tables in the image made the loader's hash loop a
 * spin to the port's stall check). */
#include "engine.h"

#define NINST 12

/* .data, not .bss: the platform runtime is the linked image's bytes
 * (objcopy -O binary), and the packed stage starts where they end. */
#define DATA __attribute__((section(".data")))
#define TABLES_OFFSET 0x100000
static Engine inst[NINST] DATA;
static int32_t scratch[16] DATA;
static int32_t ready[NINST] DATA;

/* C4 E4 G4 B4, phase increments at 44.1 kHz */
static const uint32_t note_inc[4] = {25480119, 32102938, 38177043, 48100060};

static const Cmd setup[] = {
    {C_INIT, 0, 0},
    {C_FLFO_INC, 0, 481913},           /* .14 (65.41 / .14)^.58 Hz, the engine's init rate */
    {C_PLFO_INC, 0, 481913},
    {C_FLFO_AMP, 0, 644245094},        /* .3 */
    {C_PLFO_AMP, 0, 1073741824},       /* .5 */
    {C_RES, 0, 1938103992},            /* .95 x .95 */
    {C_CUTOFF, 0, 375809638},          /* .7 */
    {C_ATK_D0, 0, 99362},              /* setAttack(.01) */
    {C_ATK_TGT, 0, 1383784776},        /* 10.31 */
    {C_REL_D0, 0, 162313},             /* setRelease(.3) */
};

void cl_frame(int32_t k)
{
    if (k > NINST) k = NINST;
    for (int i = 0; i < k; ++i) {
        Engine *e = &inst[i];
        if (!ready[i]) {
            uintptr_t base = ((uintptr_t)inst + TABLES_OFFSET) & ~(uintptr_t)0xffff;
            e->table = (const int16_t *)base + i * FRAMES * FRAME_LEN;
            eng_cmds(e, setup, sizeof setup / sizeof setup[0]);
            for (int v = 0; v < EV; ++v) {
                Cmd on[3] = {{C_BASEINC, v, (int32_t)note_inc[v & 3]},
                             {C_VGAIN, v, 338186154},   /* .2 x 100 / 127 */
                             {C_GATE, v, 1}};
                eng_cmds(e, on, 3);
            }
            ready[i] = 1;
        }
        if (!e->fading || e->fade_ctr >= FADE_LEN / 2) {
            Cmd step = {C_CYCLE, 0, 1};
            eng_cmds(e, &step, 1);
        }
        eng_render(e, scratch, 16);
    }
}
