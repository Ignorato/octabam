# `cfmeter-port` — `cfmeter` without the idle loop, for the port gate

The same selection as [`cfmeter`](../cfmeter/README.md) without CF METER
IDLE: the ColdFire port advances its clock only at main's stock `bras .`,
which the idle loop replaces, so `cfmeter` does not load a project there.
The idle slot reads 0.

    OT_PROJECT=<dir> make check REMIX=cfmeter-port
    python3 tools/harness/cfmeter.py --dump out/setverify/port.dump

With T8's FX2 = CF METER (`tools/hw/ot_project.py set-fx <dir> fx2 8 "CF
METER"`) the decoder prints the interrupt timing; see
[`modules/cfmeter/README.md`](../../modules/cfmeter/README.md) "Measured
under the port". Not for flashing.
