"""mods -- every ColdFire mod that can share one image, stock effects only.

MIDI SCENES (bkkbrls-del), Octakit (Em), the LO-FI AMF fix (Bryan T),
CC MAP, SCENES KITS and KITS RELOAD (the bridges), the five recorder
fixes (recfix until 28 Sep 2026), REPITCH (repeat98), DIRECT JUMP, SCALE
QUANTIZER and SYNTH MACHINE (timhastie), USB MIDI and USB AUDIO OUT TRACKS MAIN CUE
(markandrus). No DSP module; the 14 stock effects are listed so the FX2
chooser is stock's. SCENES P2 is out: the ledger refuses it beside KITS
RELOAD and MIDI SCENES. Booted under the ColdFire port; unflashed as a
whole (ok-ms, its subset, has run on hardware).

Octakit migrates Parts into Kits on load: back up projects first. midisc's
Part save/reload menu hooks against Octakit's Kit menus are unmeasured.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="mods",
    family="mods", proof=Proof.PORT, proof_note="",
    doc="Every ColdFire mod in one image on the stock effects: MIDI SCENES, "
        "Octakit, the recorder fixes, REPITCH, octatrick's three, USB MIDI + AUDIO.",
    modules=("MIDI SCENES", "OCTAKIT", "LOFI AMF FIX", "CC MAP", "SCENES KITS", "KITS RELOAD",
             "FLEX SEEK BIND", "FLEX SEEK BIND CTR", "RECORDER SPACING", "RECORDER HOLD", "RLEN PLEN",
             "REPITCH", "DIRECT JUMP", "SCALE QUANTIZER", "SYNTH MACHINE",
             "USB MIDI", "USB AUDIO OUT TRACKS MAIN CUE",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "SPATIALIZER", "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fallback="NONE",
)
