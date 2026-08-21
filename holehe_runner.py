#!/usr/bin/env python3
"""Run holehe against the Vanyshr high-value allowlist only.

Stock holehe 1.61 imports every module and probes 121 sites. This wrapper
keeps using that package, but:

  - skips niche modules so we never touch dominos.fr / forum boards / porn
  - catches modules that raise (github, snapchat, pinterest, …) and reports
    them as refused instead of letting core.py label the exception "Rate limit"
    or drop the line as [!]

Does not pass -T/--timeout: in 1.61 that flag makes every module fail.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python holehe_runner.py` from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from holehe_allowlist import ALLOWED_MODULES, HIGH_VALUE_TARGETS  # noqa: E402


def _refuse(name: str, out: list) -> None:
    domain = HIGH_VALUE_TARGETS.get(name, f"{name}.com")
    out.append(
        {
            "name": name,
            "domain": domain,
            "rateLimit": True,
            "exists": False,
            "emailrecovery": None,
            "phoneNumber": None,
            "others": None,
        }
    )


def _wrap(fn):
    name = fn.__name__

    async def wrapped(email, client, out):
        try:
            await fn(email, client, out)
        except Exception:
            # Do not key off len(out): 37 modules share one list.
            _refuse(name, out)

    # holehe's launch_module parses str(fn) via __qualname__, not __name__.
    wrapped.__name__ = name
    wrapped.__qualname__ = name
    return wrapped


def _install() -> None:
    from holehe import core

    _orig = core.get_functions

    def get_functions(modules, args=None):
        kept = []
        for fn in _orig(modules, args):
            name = getattr(fn, "__name__", "")
            if name in ALLOWED_MODULES:
                kept.append(_wrap(fn))
        return kept

    core.get_functions = get_functions
    core.check_update = lambda: None


def main() -> None:
    _install()
    from holehe.core import main as holehe_main

    holehe_main()


if __name__ == "__main__":
    main()
