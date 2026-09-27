"""usb-io -- the Octatrack as a USB interface: twenty channels out, a stereo
pair in, plus USB MIDI, on the stock effects.

USB AUDIO EXTENDED (the tracks, MAIN and CUE to the host), USB AUDIO IN (a
stereo pair from the host into inputs A/B; the jacks while its stream is
closed; C/D always the jacks) and USB CROSSBAR (the controller served first
on the crossbar, without which IN loses packet tails under load). Stock
effects minus SPATIALIZER, whose words on payload A hold USB AUDIO IN's RX
inject: listed on neither chooser, so neither menu offers it. Bryan T's
usbin-test `usb-io` (26 Sep 2026) was four channels each way beside MAIN +
CUE; `usb-mc` keeps that input layout.
"""

from remix.schema import Proof, Remix

REMIX = Remix(
    name="usb-io",
    family="mods", proof=Proof.PORT, proof_note="`make check` (verify_usb, verify_usb_in) under the port, 28 Sep 2026; not on hardware in this form",
    doc="stock - SPATIALIZER + USB MIDI + USB AUDIO EXTENDED (20 ch out) + USB CROSSBAR + USB AUDIO IN (stereo -> inputs A/B).",
    modules=("USB MIDI", "USB AUDIO EXTENDED", "USB CROSSBAR", "USB AUDIO IN",
             "FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
             "COMB FILTER", "COMPRESSOR", "LO-FI", "DELAY",
             "PLATE REV", "SPRING REV", "DARK REV"),
    fx1=("FILTER", "EQUALIZER", "DJ EQ", "PHASER", "FLANGER", "CHORUS",
         "COMB FILTER", "COMPRESSOR", "LO-FI"),
    fallback="NONE",
)
