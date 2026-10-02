"""RELOAD_FROM_PROJECT -- reload one track's sequence from the CF card without stopping the transport: [PTN] + [TRACK n], or [BANK] + [TRACK n] to re-apply the saved Part.

Source: `upstream/` is Zac Kyoti's repository (Zac-Kyoti/octatrack-kyoti-fw,
submodule, pinned to `7f80b85`). The declaration is
`upstream/octabam-modules/reload-from-project/manifest.py`: one ROM cave (`patch_reload3.s`), each re-linked and
compared with the author's own bytes (`reference`) every build. Its source
paths are derived from its own directory, so it is executed here from the
source on disk, as the registry does for every manifest, and this file only
re-exports its MODULE. Nothing inside `upstream/` is edited here.

On hardware: the author's MKI (standalone image), sequencer and metronome phase kept.
"""

import dataclasses
import pathlib
import runpy

from remix.schema import Category, Proof

_UPSTREAM = pathlib.Path(__file__).resolve().parent / "upstream" / "octabam-modules" / "reload-from-project" / "manifest.py"

MODULE = runpy.run_path(str(_UPSTREAM), run_name="remix_manifest_reload_from_project")["MODULE"]
# The module table's fields are octabam's (README.md, `make docs`), so they
# are added here rather than in his manifest.
MODULE = dataclasses.replace(
    MODULE, category=Category.MACHINES, author="Zac-Kyoti/octatrack-kyoti-fw", author_url="https://github.com/Zac-Kyoti/octatrack-kyoti-fw",
    proof=Proof.HARDWARE, proof_note="the author's MKI (standalone image), sequencer and metronome phase kept")
