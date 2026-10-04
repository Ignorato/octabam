"""VOCODER beside 13 stock effects: PLATE REV gives up its words for VOCODER's code."""
from remix.schema import Proof, Remix
REMIX = Remix(family="effects", proof=Proof.RENDER, proof_note="verify_vocoder renders; not yet on hardware",
              name="vocoder", doc="VOCODER beside the stock effects (all but PLATE REV, whose words it takes).",
              modules=("VOCODER",
                       "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
                       "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
                       "DELAY", "SPRING REV", "DARK REV"),
              fallback="NONE")
