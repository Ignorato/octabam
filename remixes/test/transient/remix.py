"""TRANSIENT alone, for its render gate; unflashed."""
from remix.schema import Proof, Remix
REMIX = Remix(family="effects", proof=Proof.RENDER, proof_note="`tools/verify/verify_transient.py`",
              name="transient", doc="The transient shaper on its own: ATCK, SUST, TIME, OUT, MIX.",
              modules=("TRANSIENT",), fallback="NONE")
