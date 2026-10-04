"""TESTGEN beside 13 stock effects, on both choosers: PLATE REV gives up its words for TESTGEN's code.

TESTGEN is buffer-free, so it takes an FX1 row as well; FX1 keeps all ten of its stock effects."""
from remix.schema import Proof, Remix
REMIX = Remix(family="effects", proof=Proof.HARDWARE, proof_note="Ignorato's MKII, OCTABAM6, 4 Oct 2026",
              name="testgen", doc="TESTGEN beside the stock effects (all but PLATE REV, whose words it takes), on FX2 and FX1.",
              modules=("TESTGEN",
                       "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER",
                       "CHORUS", "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI",
                       "DELAY", "SPRING REV", "DARK REV"),
              fx1=("TESTGEN",
                   "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
                   "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI"),
              fallback="NONE")
