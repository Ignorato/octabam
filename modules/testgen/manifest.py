"""TESTGEN -- a measurement source: exact, reproducible test signals on a track.

An FX2 insert that replaces its track's audio with a known signal, so the
track's output (analog, or a channel of the USB audio out) carries it: for
measuring the Octatrack's path, the USB audio stream, or any module's
response. modules/testgen/README.md says what each signal is proved to be.

SINE at ISO third-octave frequencies, an exponential SWEEP (20 Hz to 20 kHz
over LEN, then 1 s of silence, repeating), PINK and WHITE noise, and an
IMPULSE train; LEVL in 0.5 dB steps, CHAN routing.
"""
import math as _m

from remix.schema import (BusRole, Category, DspSection, Formatter, Gate, Harness,
                          Kind, MenuEntry, Module, Param, Proof, YBase)

_FS = 44100.0


def _q23(v):
    """Q23, two's complement in 24 bits, held at the largest positive value."""
    return min(round(v * (1 << 23)), 0x7FFFFF) & 0xFFFFFF


ISO_THIRDS = (20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800,
              1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000)

# P table, 191 words, read through the ptable literal:
#   +0    LEVEL[128]  LEVL k -> 10^(-(127 - k) * 0.5 / 20), Q23 (0 dBFS held at 0x7fffff);
#                     LEVL 0 is silence, and the default: choosing TESTGEN makes no sound
#                     until LEVL is turned up (a full-level tone on insert, Ignorato's MKII)
#   +128  FINC[31]    FREQ k -> the phase increment f / FS * 2^24 for ISO_THIRDS[k]
#                     (a cycle is 2^24; 1 kHz is 380436, 1000.0007 Hz)
#   +159  SWN[16]     LEN step t = LEN >> 3 -> the sweep's length, (t + 1) s in samples
#   +175  SWD[16]     the sweep's growth per sample, (r - 1) * 2^35, r^N = 20 kHz / 20.0007 Hz
# The sine's polynomial, the noise generator and the pink filter are
# immediates in testgen.asm; testgen_ref.py holds the same laws.
LEVEL = (0,) + tuple(_q23(10 ** (-(127 - k) * 0.5 / 20)) for k in range(1, 128))
FINC = tuple(round(f / _FS * (1 << 24)) for f in ISO_THIRDS)
_SWEEP_INC0 = 7609                              # 20.0007 Hz; testgen_ref.SWEEP_INC0
SWN = tuple((t + 1) * int(_FS) for t in range(16))
SWD = tuple(round(((20000.0 / (_SWEEP_INC0 * _FS / (1 << 24))) ** (1.0 / n) - 1.0) * (1 << 35)) for n in SWN)

_P = Formatter.PLAIN
_S = Formatter.STEPPED
_W = Formatter.WIDE_STEPPED
_BLANK = Param(b"", 0)

MODE_LABELS = ("SINE", "SWEP", "PINK", "WHIT", "IMPL")
CHAN_LABELS = ("L+R", "L", "R", "L-R")
FREQ_LABELS = ("20", "25", "31.5", "40", "50", "63", "80", "100", "125", "160", "200", "250", "315",
               "400", "500", "630", "800", "1k", "1k25", "1k6", "2k", "2k5", "3k15", "4k", "5k",
               "6k3", "8k", "10k", "12k5", "16k", "20k")

MODULE = Module(
    name="testgen",
    key="TESTGEN",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="Ignorato", author_url="https://github.com/Ignorato",
    proof=Proof.RENDER, proof_note="its own render gate (verify_testgen); not on hardware",
    doc="Measurement source: a sine, sweep, pink or white noise or impulses replace the track's audio.",
    menu=MenuEntry(
        fx2_id=0x17,
        donor_desc=0x400d58b8,        # DARK REV
        abbr=b"TGEN",
        fullname=b"TESTGEN",
        build_tag=False,
    ),
    params=(
        Param(b"LEVL", 0, 128, active=True, formatter=_P,
              doc="output level: 0 = silent (the default), 1 = -63 dBFS .. 127 = 0 dBFS, 0.5 dB a step"),
        Param(b"FREQ", 17, 31, active=True, formatter=_W, labels=FREQ_LABELS,
              doc="SINE frequency, shown in Hz: the 31 ISO third-octave centres, 20 Hz to 20 kHz"),
        Param(b"LEN", 32, 128, active=True, formatter=_P,
              doc="SWEEP length 1..16 s (LEN/8 + 1) and IMPULSE period, a quarter of that"),
        _BLANK, _BLANK, _BLANK,
        Param(b"MODE", 0, 5, active=True, formatter=_S, labels=MODE_LABELS,
              doc="the signal: SINE, SWEEP (20 Hz-20 kHz), PINK, WHITE, IMPULSE"),
        _BLANK,
        Param(b"CHAN", 0, 4, active=True, formatter=_S, labels=CHAN_LABELS,
              doc="where it goes: both, L only, R only, or L and inverted R (polarity)"),
        _BLANK, _BLANK, _BLANK,
    ),
    mode_slot=6,
    dsp=DspSection(
        asm="modules/testgen/testgen.asm",
        ptable=LEVEL + FINC + SWN + SWD,
        priority=18,
        bus_role=BusRole.NONE,        # an insert
        ybase=YBase.NEVER,            # no buffers, nothing in the shared window
        r7_latch_slot=None,
        gate_label=None,
    ),
    harness=Harness(layout_char="G", is_server=False),
    gates=(Gate("tools/verify/verify_testgen.py", remix_arg=False),),
    dear={"LEVL": 127, "FREQ": 30, "LEN": 127, "MODE": 0, "CHAN": 3},
)
