"""VOCODER beside 12 stock effects: PLATE REV gives up its words for VOCODER's code; DJ EQ is
left out on both menus so the module tables move to the stock curve bank in X memory (a P-memory
table read is a multi-cycle MOVEM; VOCODER reads 50 a sample)."""
from remix.schema import Proof, Remix
REMIX = Remix(family="effects", proof=Proof.RENDER, proof_note="verify_vocoder renders; the built-in limit not yet on hardware",
              name="vocoder", doc="VOCODER beside the stock effects (all but PLATE REV, whose words it takes, and DJ EQ, so its table sits in X).",
              modules=("VOCODER",
                       "FILTER", "EQUALIZER", "PHASER", "FLANGER",
                       "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
                       "DELAY", "SPRING REV", "DARK REV"),
              fallback="NONE",
              fx1=("FILTER", "EQUALIZER", "PHASER", "FLANGER", "CHORUS", "SPATIALIZER",
                   "COMB FILTER", "COMPRESSOR", "LO-FI"))
