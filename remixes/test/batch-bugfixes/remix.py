"""stock effects with BATCH_BUGFIXES: the MIDI Plays-Free trig, empty-pattern LED and Part-change carryover fixes."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="batch-bugfixes",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with BATCH_BUGFIXES: the MIDI Plays-Free trig, empty-pattern LED and Part-change carryover fixes.",
    modules=("BATCH_BUGFIXES",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
