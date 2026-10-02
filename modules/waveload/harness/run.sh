#!/usr/bin/env bash
# The engine against CHOMPI WAVE's own float code, and its ColdFire build
# against its host build, with the ColdFire instruction count.
#   modules/waveload/harness/run.sh [EV]      # EV = voices, 8 (CHOMPI's) or 4 (the probe's)
# CHOMPI is cloned into out/ at the pinned commit; its wavetable01.wav is
# the table. Nothing from it is committed.
set -euo pipefail
cd "$(dirname "$0")/../../.."
EV=${1:-8}
PIN=a73d732613da684e4de844619b690776f0f50ccf
H=modules/waveload/harness
O=out/waveload
mkdir -p "$O"
if [ ! -d out/chompi ]; then git clone -q https://github.com/CHOMPI-Club/CHOMPI out/chompi; fi
git -C out/chompi checkout -q "$PIN"
C=out/chompi/firmware/chompi-wave/code/src
D=out/chompi/firmware/chompi-wave/code/libs/DaisySP/Source
T=out/chompi/firmware/card-profiles/wave-1.0/wavetable01.wav
# their classes, verbatim
{ echo '#pragma once'; echo '#include <algorithm>'; echo '#include <cstdint>';
  echo '#define MAX_SAMPLES_PER_CYCLE 2048'; echo '#define CYCLES 33';
  awk '/^class wavetable \{/{p=1} /^class wavetableLoader/{p=0} p' $C/WavetableManager.h; } > $O/chompi_wavetable.h
{ echo '#pragma once'; echo '#include "chompi_wavetable.h"'; echo '#include "DJFilter.h"';
  awk '/^class subtractiveVoice/{p=1} /^class myEngine/{p=0} p' $C/subtractiveEngine.h; } > $O/chompi_voice.h
cp $C/DJFilter.h $C/BasicMMF.h $O/
clang++ -std=c++17 -O2 -ffp-contract=off -I$O -I$H -I$D -I$D/Utility -I$D/Control -I$D/Synthesis \
    $H/oracle.cpp $D/Control/adsr.cpp $D/Synthesis/oscillator.cpp -o $O/oracle
clang -O2 -DEV=$EV -I$H -o $O/host_fixed $H/host_fixed.c modules/waveload/engine.c -lm
VMASK=$(( (1 << EV) - 1 )) $O/oracle $T $O/oracle.f32
VMASK=$(( (1 << EV) - 1 )) $O/host_fixed $T $O/fixed.f32 $O/cmds.bin $O/table.bin 0x100000 $O/host.i32
.venv/bin/python $H/cmp.py $O/oracle.f32 $O/fixed.f32
printf 'SECTIONS { . = 0x10000; .text : { *(.text*) *(.rodata*) } .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) } }\n' > $O/link.ld
m68k-elf-gcc -DEV=$EV -mcpu=54455 -O2 -fomit-frame-pointer -ffreestanding -fno-builtin -nostdlib \
    -c modules/waveload/engine.c -o $O/engine.o
m68k-elf-gcc -mcpu=54455 -nostdlib -T $O/link.ld $O/engine.o -o $O/engine.elf
m68k-elf-objcopy -O binary $O/engine.elf $O/engine.bin
.venv/bin/python $H/run_cf.py $O/engine.elf $O/engine.bin $O/table.bin $O/cmds.bin $O/cf.i32
.venv/bin/python -c "
import numpy as np, sys
a = np.fromfile('$O/host.i32', '<i4'); b = np.fromfile('$O/cf.i32', '>i4')
ok = np.array_equal(a, b); print('ColdFire build == host build:', ok, len(a), 'samples'); sys.exit(0 if ok else 1)"
