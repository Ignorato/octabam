"""TESTGEN beside 13 stock effects: PLATE REV gives up its words for TESTGEN's code."""
from remix.schema import Proof, Remix
REMIX = Remix(family="effects", proof=Proof.HARDWARE, proof_note="Ignorato's MKII, OCTABAM6, 4 Oct 2026",
              name="testgen", doc="TESTGEN beside the stock effects (all but PLATE REV, whose words it takes).",
              modules=("TESTGEN",
                       "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
                       "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
                       "DELAY", "SPRING REV", "DARK REV"),
              fallback="NONE")
