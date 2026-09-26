"""hello-dram -- the reference minimal ColdFire build: one DRAM unit, alone.

No chooser row, no DSP words, one boot-site redirect and a few hundred
bytes appended. The loader path's canary: the boot verifier must find the
unit at its linked address.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="hello-dram",
    family="reference", proof=Proof.CHECK, proof_note="",
    doc="Reference minimal ColdFire build: the HELLO DRAM unit, alone.",
    modules=("HELLO DRAM",),
    fallback="NONE",
)
