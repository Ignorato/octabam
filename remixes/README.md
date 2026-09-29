# Remixes

A remix is a named selection of modules; `make image REMIX=<name> BUILD=<n>` builds it into a card-flashable image from your own OS 1.40C. Each remix is a directory here: `remix.py` is the selection, `README.md` says what is in it, where it has run and how to flash it. This index is rendered from the selections (`make docs`).

- What to install first (the Xcode Command Line Tools, Homebrew, Python 3.10+, `cmake`, `uv`) and every step to a flashed unit: [BUILDING.md](../docs/guide/BUILDING.md).
- Composing your own: [REMIXER.md](../docs/guide/REMIXER.md).
- The remixes that carry one module for its gates: [test/](test/README.md).

## The rig

| remix | contains | proof |
|---|---|---|
| [`bottleservice`](bottleservice/README.md) | The rig + USB MIDI + USB AUDIO OUT MASTER (T8 to the computer) + USB AUDIO IN CD (the computer onto inputs C/D) + Octakit. | on hardware: Sam's MKII, image 88, 27 Sep 2026 |

## Firmware mods on the stock effects

| remix | contains | proof |
|---|---|---|
| [`octatrick`](octatrick/README.md) | SYNTH MACHINE + SCALE QUANTIZER + DIRECT JUMP on the stock effects. | `make check` |
| [`octatrick-usb`](octatrick-usb/README.md) | SYNTH MACHINE + SCALE QUANTIZER + DIRECT JUMP + USB MIDI + USB AUDIO on the stock effects. | on hardware: Tim's MKI, 26 Sep 2026 (OCTATRICK9), USB audio on all 20 channels |
| [`ok-ms`](ok-ms/README.md) | Octakit + MIDI SCENES on the stock effects: the two mods alone. | on hardware: midisc's author's unit, 14 Sep 2026 (OKMS2) |

Never share a built image: it contains Elektron's OS.
