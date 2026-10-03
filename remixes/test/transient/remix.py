"""TRANSIENT beside 13 stock effects: PLATE REV gives up its words for TRANSIENT's code."""
from remix.schema import Proof, Remix
REMIX = Remix(family="effects", proof=Proof.PORT, proof_note="`verify_set` on a project made on a MKII",
              name="transient", doc="TRANSIENT beside the stock effects (all but PLATE REV, whose words it takes).",
              modules=("TRANSIENT",
                       "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
                       "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
                       "DELAY", "SPRING REV", "DARK REV"),
              fallback="NONE")
