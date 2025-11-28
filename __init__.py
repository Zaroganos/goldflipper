"""
Top-level package shim so legacy imports like `goldflipper.database`
continue to work even though the real code lives inside
`goldflipper.goldflipper`.
"""

from importlib import import_module
import sys as _sys

_INNER_PACKAGE = import_module("goldflipper.goldflipper")

def __getattr__(name):
    return getattr(_INNER_PACKAGE, name)

def _alias(subpkg: str) -> None:
    full_name = f"{__name__}.{subpkg}"
    if full_name not in _sys.modules:
        _sys.modules[full_name] = import_module(f"goldflipper.goldflipper.{subpkg}")

for _subpackage in ("database", "config", "core", "alpaca_client"):
    try:
        _alias(_subpackage)
    except ModuleNotFoundError:
        # Not every environment has every optional sub-package (e.g., alpaca_client)
        continue
