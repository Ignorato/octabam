# CF METER IDLE

Main's idle loop, timed, for [CF METER](../cfmeter/README.md)'s idle-time
slot. It replaces main's last init call (`0x4001fc96`, `jsr 0x40098a2c`)
and the `bras .` after it with the call and a loop that reads DMA timer 3.
A step shorter than twice the shortest step seen, + 8 counts, is added to
CF METER's idle counter; a longer step was taken by an interrupt or a
task. The shortest step goes to slot 6.

Main is the priority-0 task and never blocks (`docs/firmware/KERNEL.md`),
so it runs only when no other task is ready and no interrupt is being
served.

**Under the port** an image with this loop boots (`verify_dram_boot`:
the loop runs and writes its shortest step) and does not load a project
or finish `verify_usb`'s scripted host calls: the port advances its clock,
and returns from a call, only when the PC is at main's stock `bras .`
(`tools/emu/ot_emu/rtos.cpp`, `g_mainSpin`). `make check REMIX=cfmeter`
passes every gate up to `verify_usb`; remix `cfmeter-port` leaves the loop
out and passes all of them. On the unit time passes regardless.
