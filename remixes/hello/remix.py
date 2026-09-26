"""hello -- the reference minimal DSP build: one gain insert, nothing else.

HELLO WORLD (a linear volume knob) alone; absent ids resolve to the
firmware's own NONE. The worked example modules/_template points at, and
the DSP pipeline's canary: it must build and null at GAIN=127.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="hello",
    family="reference", proof=Proof.CHECK, proof_note="",
    doc="Reference minimal build: the HELLO WORLD gain insert, alone.",
    modules=("HELLO WORLD",),
    fallback="NONE",
)
