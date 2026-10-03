"""TESTGEN -- a measurement source: exact, reproducible test signals on a track.

An FX2 insert that replaces its track's audio with a known signal, so the
track's output (analog, or a channel of the USB audio out) carries it: for
measuring the Octatrack's path, the USB audio stream, or any module's
response. modules/testgen/README.md says what each signal is proved to be.

0.1: SINE (ISO third-octave frequencies, exact 1 kHz), LEVL in 0.5 dB steps,
CHAN routing. The sweep, noises and impulses follow.
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

# P table, 159 words, read through the ptable literal:
#   +0    LEVEL[128]  LEVL k -> 10^(-(127 - k) * 0.5 / 20), Q23 (0 dBFS held at 0x7fffff)
#   +128  FINC[31]    FREQ k -> the phase increment f / FS * 2^24 for ISO_THIRDS[k]
#                     (a cycle is 2^24; 1 kHz is 380436, 1000.0007 Hz)
# The sine's five polynomial coefficients are immediates in testgen.asm.
LEVEL = tuple(_q23(10 ** (-(127 - k) * 0.5 / 20)) for k in range(128))
FINC = tuple(round(f / _FS * (1 << 24)) for f in ISO_THIRDS)

_P = Formatter.PLAIN
_S = Formatter.STEPPED
_BLANK = Param(b"", 0)

MODE_LABELS = ("SINE", "SWEP", "PINK", "WHIT", "IMPL")
CHAN_LABELS = ("L+R", "L", "R", "L-R")

MODULE = Module(
    name="testgen",
    key="TESTGEN",
    kind=Kind.DSP_EFFECT,
    category=Category.TRACK, author="Ignorato", author_url="https://github.com/Ignorato",
    proof=Proof.RENDER, proof_note="its own render gate (verify_testgen); not on hardware",
    doc="Measurement source: a known test signal replaces the track's audio (0.1: a sine at ISO third-octave frequencies).",
    menu=MenuEntry(
        fx2_id=0x17,
        donor_desc=0x400d58b8,        # DARK REV
        abbr=b"TGEN",
        fullname=b"TESTGEN",
        build_tag=False,
    ),
    params=(
        Param(b"LEVL", 115, 128, active=True, formatter=_P,
              doc="output level: 127 = 0 dBFS, 0.5 dB a step (115 = -6 dBFS, 0 = -63.5 dBFS)"),
        Param(b"FREQ", 17, 128, active=True, formatter=_P,
              doc="SINE frequency: ISO third-octave centres, 0 = 20 Hz .. 17 = 1 kHz .. 30 = 20 kHz"),
        Param(b"LEN", 32, 128, active=True, formatter=_P,
              doc="SWEEP length and IMPULSE period (from 0.2)"),
        _BLANK, _BLANK, _BLANK,
        Param(b"MODE", 0, 5, active=True, formatter=_S, labels=MODE_LABELS,
              doc="the signal: SINE (0.1); SWEEP, PINK, WHITE, IMPULSE to follow"),
        _BLANK,
        Param(b"CHAN", 0, 4, active=True, formatter=_S, labels=CHAN_LABELS,
              doc="where it goes: both, L only, R only, or L and inverted R (polarity)"),
        _BLANK, _BLANK, _BLANK,
    ),
    mode_slot=6,
    dsp=DspSection(
        asm="modules/testgen/testgen.asm",
        ptable=LEVEL + FINC,
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
