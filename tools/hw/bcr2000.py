#!/usr/bin/env python3
"""Program a Behringer BCR2000 for the rig: BCL built from the module manifests,
sent to the unit over SysEx (each line acknowledged) or written for BC Manager.

    python3 tools/hw/bcr2000.py ping                                  # `$rev R1` handshake, prints the ack
    python3 tools/hw/bcr2000.py bcl  [--preset rig|t1..t8|all] [--out FILE]
    python3 tools/hw/bcr2000.py send [--preset rig|t1..t8|all] [--store N]
                                     [--port BCR2000] [--channels 1,2,3,4,5,6,7,8]

Presets (`--preset`, default `rig`):
  rig     push-encoder groups 1-4 = DEL send, REV send, LEVEL, AMP VOL per track
          (eight encoders = eight tracks); lower row 1 = BusDelay on T1 (slots
          2-9), row 2 = BusVerb on T5 (slots 2-9), row 3 = delay PTCH TIME, verb
          DLY TIME, crossfader; buttons 33-40 MUTE, 41-48 SOLO per track.
  t1..t8  one track: groups 1-4 = FX1 page 1, FX1 page 2, FX2 page 1, FX2 page 2
          (LEVEL, AMP VOL, crossfader on the spare encoders); lower rows =
          PLAYBACK, AMP, LFO page 1; buttons as `rig`.
  all     rig then t1..t8; `--store N` stores rig at N and t1..t8 at N+1..N+8.

Without `--store` the preset lands in the BCR's edit buffer only.

CC numbers: page 1 is stock (docs/firmware/MIDI.md: PLAYBACK 16-21, AMP 22-27,
LFO 28-33, FX1 34-39, FX2 40-45, LEVEL 46, AMP VOL 25, crossfader 48, MUTE 49,
SOLO 50, on the track's trig channel); page 2 is CC MAP (modules/cc-map: FX2
62-67, FX1 68-73). Select ranges and defaults come from the manifests; MODE
over CC re-defaults the knobs around it (MODE DEFAULTS). Delay TONE (CC 42
on T1) reaches the DSP only while T1's FX2 page is on screen (MIDI.md
"Hardware findings"). MUTE/SOLO are sent as 127/0 toggles; the value the OT
treats as "on" is not measured here.

The OT: PROJECT > MIDI > CONTROL > AUDIO CC IN on; each track's trig channel
set (T1-8 = 1-8 is the default, `--channels` follows the project).
The BCR's mode (hold EDIT, press STORE; encoder 1; EXIT): U-1 over its own USB
(DIN ports off); S-4 over a DIN interface (`--port UM-ONE`: interface OUT ->
BCR IN, BCR OUT A -> interface IN). Playing the OT: S-4, BCR OUT A -> OT MIDI
IN, no Mac.

SysEx: F0 00 20 32 <dev> <model> 20 <idx hi> <idx lo> <ascii line> F7 per
BCL line, dev/model 7F = any; the ack is ... 21 <idx hi> <idx lo> <err> F7,
err 0 = accepted. Needs python-rtmidi (`pip install python-rtmidi`).
"""
import argparse, pathlib, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402

PAGE1 = {"PB": 16, "AMP": 22, "LFO": 28, "FX1": 34, "FX2": 40}
PAGE2 = {"FX2": 62, "FX1": 68}
LEVEL, AMPVOL, XFADE, MUTE, SOLO = 46, 25, 48, 49, 50
ROLES = {1: "DELAY SERVER", 5: "REVERB SERVER"}      # the rig's hosts; every other track runs SEND
STATIONS = ("SPECTRUM", "CHARACTER", "MODULATION")   # FX1; the track's pick is not known here

# BCL acknowledge codes (BCL revision R1); the code is what the unit said.
ERRORS = {0: "ok", 1: "unknown token", 2: "data without token", 3: "argument missing",
          4: "wrong device", 5: "wrong revision", 6: "missing revision", 7: "internal error",
          8: "mode missing", 9: "bad item index", 10: "not a number", 11: "value out of range",
          12: "invalid argument", 13: "invalid command", 14: "wrong number of arguments",
          15: "too much data", 16: "already defined", 17: "preset missing",
          18: "preset too complex", 19: "wrong preset", 20: "unknown preset error",
          21: "sequence error", 22: "wrong context", 23: "preset error", 24: "memory full"}


def _mods():
    return registry.modules()


def slot_cc(page, slot):
    """CC number for `page` ('FX1'/'FX2') slot 0..11."""
    return PAGE1[page] + slot if slot < 6 else PAGE2[page] + slot - 6


def knob(ch, cc, label, count=None, default=0):
    hi = 127 if not count or count >= 128 else count - 1
    return dict(ch=ch, cc=cc, lo=0, hi=hi, default=default or 0, label=label)


def param_knob(ch, page, slot, param, tag):
    return knob(ch, slot_cc(page, slot), f"{tag} {param.name.decode() or '-'}", param.count, param.default)


def rig_preset(channels):
    mods = _mods()
    enc = {}
    for t in range(8):
        ch = channels[t]
        enc[1 + t] = knob(ch, PAGE1["FX2"] + 0, f"T{t+1} DEL")
        enc[9 + t] = knob(ch, PAGE1["FX2"] + 1, f"T{t+1} REV")
        enc[17 + t] = knob(ch, LEVEL, f"T{t+1} LEVEL")
        enc[25 + t] = knob(ch, AMPVOL, f"T{t+1} AMP VOL")
    dly, vrb = mods["DELAY SERVER"].params, mods["REVERB SERVER"].params
    cd, cv = channels[0], channels[4]
    for i, s in enumerate(range(2, 10)):
        enc[33 + i] = param_knob(cd, "FX2", s, dly[s], "T1 BDLY")
        enc[41 + i] = param_knob(cv, "FX2", s, vrb[s], "T5 BVRB")
    enc[49] = param_knob(cd, "FX2", 10, dly[10], "T1 BDLY")
    enc[50] = param_knob(cd, "FX2", 11, dly[11], "T1 BDLY")
    enc[51] = param_knob(cv, "FX2", 10, vrb[10], "T5 BVRB")
    enc[52] = param_knob(cv, "FX2", 11, vrb[11], "T5 BVRB")
    enc[53] = knob(channels[0], XFADE, "CROSSFADER")
    return "OCTABAM RIG", enc, mute_solo(channels)


def mute_solo(channels):
    btn = {}
    for t in range(8):
        btn[33 + t] = dict(ch=channels[t], cc=MUTE, label=f"T{t+1} MUTE")
        btn[41 + t] = dict(ch=channels[t], cc=SOLO, label=f"T{t+1} SOLO")
    return btn


def track_preset(track, channels):
    mods = _mods()
    ch = channels[track - 1]
    fx2 = mods[ROLES.get(track, "SEND")].params
    st = [mods[n].params for n in STATIONS]
    enc = {}
    for s in range(12):
        # FX1: whichever station is on the track; a select takes the widest count, the cave clamps the rest
        names = {p[s].name.decode() for p in st if p[s].active}
        count = max((p[s].count or 128) for p in st)
        default = st[0][s].default
        enc[1 + s + 2 * (s // 6)] = knob(ch, slot_cc("FX1", s), f"T{track} FX1 {'/'.join(sorted(names)) or '-'}", count, default)
        enc[17 + s + 2 * (s // 6)] = param_knob(ch, "FX2", s, fx2[s], f"T{track} FX2")
    enc[7], enc[8], enc[15] = knob(ch, LEVEL, f"T{track} LEVEL"), knob(ch, AMPVOL, f"T{track} AMP VOL"), knob(ch, XFADE, "CROSSFADER")
    for row, page in enumerate(("PB", "AMP", "LFO")):
        for s in range(6):
            enc[33 + 8 * row + s] = knob(ch, PAGE1[page] + s, f"T{track} {page} {s+1}")
    return f"OCTABAM T{track}", enc, mute_solo(channels)


def bcl(name, enc, btn, store=None):
    out = ["$rev R1", "$preset", f"  .name '{name:<24.24}'", "  .snapshot off", "  .request off",
           "  .egroups 4", "  .fkeys on", "  .lock off", "  .init"]
    for n in sorted(enc):
        e = enc[n]
        select = e["hi"] < 127
        out += [f"$encoder {n} ; {e['label']}",
                f"  .easypar CC {e['ch']} {e['cc']} {e['lo']} {e['hi']} absolute",
                "  .showvalue on",
                f"  .mode {'1dot' if select else 'bar'}",
                f"  .resolution {'24 24 24 24' if select else '96 96 96 96'}",
                f"  .default {min(e['default'], e['hi'])}"]
    for n in sorted(btn):
        b = btn[n]
        out += [f"$button {n} ; {b['label']}",
                f"  .easypar CC {b['ch']} {b['cc']} 127 0 toggleon",
                "  .showvalue on", "  .default 0"]
    if store:
        out.append(f"$store {store}")
    out.append("$end")
    return out


def presets(which, channels):
    if which == "rig":
        return [rig_preset(channels)]
    if which == "all":
        return [rig_preset(channels)] + [track_preset(t, channels) for t in range(1, 9)]
    return [track_preset(int(which[1:]), channels)]


def strip(lines):
    """Comments and blank lines out; what the unit is sent."""
    out = []
    for ln in lines:
        ln = ln.split(";")[0].rstrip()
        if ln.strip():
            out.append(ln)
    return out


class BCR:
    def __init__(self, port):
        try:
            import rtmidi
        except ImportError:
            sys.exit("python-rtmidi is missing: pip install python-rtmidi")
        self.mo, self.mi = rtmidi.MidiOut(), rtmidi.MidiIn()
        outs = [i for i, n in enumerate(self.mo.get_ports()) if port in n]
        ins = [i for i, n in enumerate(self.mi.get_ports()) if port in n]
        if not outs or not ins:
            sys.exit(f"no MIDI port matching {port!r}; out={self.mo.get_ports()} in={self.mi.get_ports()}")
        self.mo.open_port(outs[0]); self.mi.open_port(ins[0])
        self.mi.ignore_types(sysex=False, timing=True, active_sense=True)

    def line(self, idx, text, timeout=1.0):
        """Send one BCL line as message `idx`; return (err, raw reply) or (None, None) on silence."""
        self.mo.send_message([0xF0, 0x00, 0x20, 0x32, 0x7F, 0x7F, 0x20, (idx >> 7) & 0x7F, idx & 0x7F]
                             + list(text.encode("ascii")) + [0xF7])
        t0 = time.time()
        while time.time() - t0 < timeout:
            m = self.mi.get_message()
            if not m:
                time.sleep(0.002); continue
            d = m[0]
            if len(d) >= 11 and d[:4] == [0xF0, 0x00, 0x20, 0x32] and d[6] == 0x21 and ((d[7] << 7) | d[8]) == idx:
                return d[9], d
        return None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("ping", "bcl", "send"))
    ap.add_argument("--preset", default="rig", choices=("rig", "all") + tuple(f"t{i}" for i in range(1, 9)))
    ap.add_argument("--store", type=int, help="store at this preset number (1-32); `all` uses N..N+8")
    ap.add_argument("--port", default="BCR2000")
    ap.add_argument("--channels", default="1,2,3,4,5,6,7,8", help="MIDI channel of tracks 1..8")
    ap.add_argument("--out", help="bcl: write here instead of stdout")
    ap.add_argument("--timeout", type=float, default=1.0)
    a = ap.parse_args()
    channels = [int(c) for c in a.channels.split(",")]
    if len(channels) != 8 or not all(1 <= c <= 16 for c in channels):
        sys.exit("--channels: eight values 1..16")

    if a.cmd == "ping":
        err, raw = BCR(a.port).line(0, "$rev R1", a.timeout)
        if raw is None:
            sys.exit(f"no reply within {a.timeout}s (USB needs mode U-1; a DIN interface needs S-4 with its OUT on the BCR's IN and the BCR's OUT A on its IN)")
        print("ack", " ".join("%02x" % x for x in raw), "->", err, ERRORS.get(err, "?"))
        return

    docs = []
    for i, (name, enc, btn) in enumerate(presets(a.preset, channels)):
        docs.append(bcl(name, enc, btn, a.store + i if a.store else None))
    if a.cmd == "bcl":
        text = "\n".join("\n".join(d) for d in docs) + "\n"
        if a.out:
            pathlib.Path(a.out).write_text(text); print(f"wrote {a.out}")
        else:
            sys.stdout.write(text)
        return

    unit = BCR(a.port)
    for d in docs:
        lines = strip(d)
        for i, ln in enumerate(lines):
            err, raw = unit.line(i, ln, a.timeout)
            if raw is None:
                sys.exit(f"line {i} {ln!r}: no reply within {a.timeout}s")
            if err:
                sys.exit(f"line {i} {ln!r}: error {err} ({ERRORS.get(err, '?')}) "
                         + " ".join("%02x" % x for x in raw))
        print(f"{lines[2].strip()}: {len(lines)} lines accepted" + (f", stored ({lines[-2]})" if a.store else ", edit buffer only"))


if __name__ == "__main__":
    main()
