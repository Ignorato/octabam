"""stock effects with MUTE_MODES: PERSONALIZE > MUTE MODE (OT, OTFX, OTFX-T, DT-T)."""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="mute-modes",
    family="mods", proof=Proof.CHECK, proof_note="",
    doc="stock effects with MUTE_MODES: PERSONALIZE > MUTE MODE (OT, OTFX, OTFX-T, DT-T).",
    modules=("MUTE_MODES",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
             "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
             "DELAY", "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
