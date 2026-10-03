"""wave -- WAVE (a 4-voice wavetable synth on FX2) with SCALE QUANTIZER for
the played notes, the page-2 tools (CC MAP, SCENES P2, PLOCKS P2) and USB
MIDI + USB AUDIO OUT TRACKS MAIN CUE to record it. DARK REV and SPRING REV
are off the chooser: WAVE runs in their words."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="wave",
    family="effects", proof=Proof.RENDER, proof_note="`tools/verify/verify_wave.py`; not flashed",
    doc="WAVE + SCALE QUANTIZER + CC MAP / SCENES P2 / PLOCKS P2 + USB out, on stock.",
    modules=("WAVE", "SCALE QUANTIZER", "CC MAP", "SCENES P2", "PLOCKS P2",
             "USB MIDI", "USB AUDIO OUT TRACKS MAIN CUE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV"),
    fallback="NONE",
)
