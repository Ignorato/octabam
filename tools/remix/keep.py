"""The build's assert for schema.Keep: kept bytes still hold stock.

The build calls it twice: on the stock image before any write (a keep that
does not match is wrong about 1.40C), and on the finished image before the
appends (anything the build wrote there -- a module's write the ledger
missed, a floating cave or grown table, a menu clone, an arena literal --
is refused).
"""

from __future__ import annotations


def violations(image, base: int, modules) -> list[str]:
    """One line per keep whose bytes in `image` (loaded at `base`) differ
    from its `expect`."""
    out = []
    for m in modules:
        for k in getattr(m, "keeps", ()):
            got = bytes(image[k.addr - base:k.addr - base + len(k.expect)])
            if got != k.expect:
                out.append(f"{m.key} keeps 0x{k.addr:08x} ({k.note or 'kept bytes'}): "
                           f"finds {got.hex()}, not {k.expect.hex()}")
    return out
