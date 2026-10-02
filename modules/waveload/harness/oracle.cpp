// The oracle: CHOMPI WAVE's own voice classes (chompi_*.h, DJFilter.h,
// BasicMMF.h extracted verbatim) and DaisySP, driven the way myEngine::Process
// drives them, at 44.1 kHz. Writes raw float32 mono to argv[2].
#include "daisysp.h"
#include "chompi_voice.h"
#include "scenario.h"
#include <cstdio>
#include <vector>

using namespace daisysp;

static float table[CYCLES][MAX_SAMPLES_PER_CYCLE];
static subtractiveVoice voices[NV];   // static storage: zeroed like the firmware's
static Oscillator filterLfo, pitchLfo;
static float filter_lfo_val = 0.f, pitch_lfo_mult = 1.f;

// myEngine::keyToFrequency, globalFrequency .5, octaveOffset 0
static float keyToFrequency(int nn) {
    float base = 440.f * pow(2.f, ((nn + 36 - 57 + 0) / 12.f));
    float shift = pow(2.f, (0.5f - 0.5f) * 2.f);
    return base * shift;
}

int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb");
    fseek(f, 136, SEEK_SET);   // the firmware reads raw from byte 136
    if (fread(table, 4, CYCLES * MAX_SAMPLES_PER_CYCLE, f) != CYCLES * MAX_SAMPLES_PER_CYCLE) return 1;
    fclose(f);

    // myEngine::Init
    for (int i = 0; i < NV; ++i) {
        voices[i].Init(SR, &filter_lfo_val, &pitch_lfo_mult);
        voices[i].key = -1;
        voices[i].wt.wavetableMemory_ = table;
        voices[i].wt.lastBase_ = table;
    }
    filterLfo.Init(SR); filterLfo.SetWaveform(Oscillator::WAVE_TRI); filterLfo.SetAmp(0.f);
    pitchLfo.Init(SR);  pitchLfo.SetWaveform(Oscillator::WAVE_TRI);  pitchLfo.SetAmp(0.f);
    pitchLfo.PhaseAdd(.25f);
    float r = fclamp(.63f, 0.f, .99f);
    for (auto &v : voices) v.filter_.SetRes(r);
    filterLfo.SetFreq(.14f * powf(65.41f / .14f, LFO_RATE));
    pitchLfo.SetFreq(.14f * powf(65.41f / .14f, LFO_RATE));
    for (auto &v : voices) {
        v.amp_env.SetAttackTime(ATTACK_AMT * 5.f, 1.f);
        v.amp_env.SetReleaseTime(RELEASE_AMT);
    }

    std::vector<float> out;
    out.reserve(NBLOCKS * BLOCK);
    for (int b = 0; b < NBLOCKS; ++b) {
        Ctl c = scenario(b);
        if (c.note_on >= 0) {
            subtractiveVoice &v = voices[c.note_on];
            v.setFrequency(keyToFrequency(kNotes[c.note_on]));
            v.key = c.note_on; v.velocity = VELOCITY * 0.00787401f;
            v.nn = kNotes[c.note_on]; v.gate = true;
        }
        if (c.note_off_all) for (auto &v : voices) v.gate = false;
        for (auto &v : voices) v.cutoff_position = c.cutoff;          // setMasterCutoff
        if (c.res >= 0) { float rr = fclamp(c.res, 0.f, .99f); for (auto &v : voices) v.filter_.SetRes(rr); }
        if (c.flfo_depth >= 0) filterLfo.SetAmp(c.flfo_depth);
        if (c.plfo_depth >= 0) pitchLfo.SetAmp(c.plfo_depth);
        if (c.cycle_step) for (auto &v : voices) v.wt.cycleThroughTable(c.cycle_step, false);

        for (int i = 0; i < BLOCK; ++i) {   // myEngine::Process, the voice part
            filter_lfo_val = filterLfo.Process();
            pitch_lfo_mult = powf(2.f, pitchLfo.Process() * (2.f / 12.f));
            float sigl = 0.f, sigr = 0.f;
            for (auto &v : voices) v.Process(&sigl, &sigr);
            out.push_back(sigl / (float)NV);
        }
    }
    FILE *o = fopen(argv[2], "wb");
    fwrite(out.data(), 4, out.size(), o);
    fclose(o);
    fprintf(stderr, "oracle: %zu samples\n", out.size());
    return 0;
}
