"""KITS -- 256 Kits per project; a Kit is a saved Part.

The stock Part engine runs as it is: four working Part slots per bank, the
pattern's Part byte names one. KITS keeps a library of 256 Parts and, per
pattern, the Kit it plays; before a pattern is scheduled its Kit is copied
into a slot of its bank that nothing is playing and the pattern's Part byte
names that slot. LOAD KIT and SAVE KIT run the stock Part Reload and Part
Save; FUNC+CUE is the stock reload. kits.work / kits.strd hold the library
beside the bank files. docs/firmware/PARTS.md says what of stock this reads.
"""

from remix.schema import Category, Claims, Detour, Gate, Kind, Linked, Module, Proof

H = bytes.fromhex

MODULE = Module(
    name="kits",
    key="KITS",
    kind=Kind.CF_PATCH,
    category=Category.PARTS, author="sambanks", author_url="https://github.com/sambanks",
    proof=Proof.PORT, proof_note="`verify_kits`",
    doc="256 Kits per project: PART = LOAD KIT, FUNC+PART = SAVE KIT (MKI: FUNC+MIDI / "
        "FUNC+BANK); each pattern plays its Kit through the stock Part slots.",
    linked=(Linked("kits", "modules/kits/kits.s", dram=True),),
    detours=(
        Detour(0x400A0570, H("4fefffec48d7007c"), "kits", "kits_sched",
               "the pattern schedule (every request): the pattern's Kit into a free slot",
               pad_to=8),
        Detour(0x4009C634, H("2f02242f0008"), "kits", "kits_chain",
               "the chain append: each chained pattern's Kit staged"),
        Detour(0x40090504, H("4feffeb848d77cfc"), "kits", "kits_loadall",
               "a load of every bank: the project's Kits", pad_to=8),
        Detour(0x400905D4, H("4feffeb848d77cfc"), "kits", "kits_loadmask",
               "a masked bank load (LOAD PROJECT, the power-up, reloads)", pad_to=8),
        Detour(0x400909D8, H("2f0a42a74eb94000fd34"), "kits", "kits_newproj",
               "a new, empty project: no Kits", pad_to=10),
        Detour(0x400917C8, H("4e56febc48d73cfc"), "kits", "kits_bankw",
               "the bank writer: kits.work after the banks", pad_to=8),
        Detour(0x4008EE74, H("4e56fdd048d73cfc"), "kits", "kits_pstore",
               "the project store: kits.work, then kits.strd", pad_to=8),
        Detour(0x4008F180, H("4e56fdd048d73cfc"), "kits", "kits_preload",
               "the project reload: kits.strd back to kits.work", pad_to=8),
        Detour(0x4004A9C4, H("4cd70c1c4fef00144e75"), "kits", "kits_saved",
               "the Part Save's tail: the saved Part into the slot's Kit", pad_to=10),
        Detour(0x4004A9D0, H("4feffff048d70c0c"), "kits", "kits_clear",
               "the Part Clear: the slot holds no Kit after", pad_to=8),
        Detour(0x4002E7B8, H("4ab9460d1060"), "kits", "kits_partkey",
               "PART (MKII), FUNC+MIDI (MKI): LOAD KIT"),
        Detour(0x4002DC9C, H("71b9100b14cf"), "kits", "kits_savekey",
               "the Part edit menu (MKII FUNC+PART): SAVE KIT"),
        Detour(0x40058A64, H("2f032f02262f000c"), "kits", "kits_mkisave",
               "the MKI FUNC+BANK dispatch: SAVE KIT", pad_to=8),
    ),
    # CS1 (battery SRAM), unused by stock beyond its whole-CS1 init
    # (docs/firmware/STEP_LOCKS.md section 6): RESID with a magic and a sum,
    # and ASSIGN, over a power-off.
    claims=Claims(sram=((0x100F85A0, 0x48, "KITS: which Kit each Part slot holds"),
                        (0x100FFE00, 0x100, "KITS: each pattern's Kit"))),
    conflicts=(("OCTAKIT", "both own the Part slots and the PART key"),),
    gates=(Gate('tools/verify/verify_kits.py'),),
)
