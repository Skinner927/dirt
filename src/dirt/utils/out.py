"""Wrapper around `rich.console` to facilitate any changes."""
from __future__ import annotations

import functools
import logging
import platform
import types

import rich.status
from rich.console import Console, RenderableType
from rich.logging import RichHandler

from dirt import const

__all__ = ["console", "setup_basic_logging"]

_SPINNER = "bouncingBar" if platform.system() == "Windows" else "dots"


def setup_basic_logging() -> None:
    # https://rich.readthedocs.io/en/latest/logging.html
    logging.basicConfig(
        level=const.LOG_LEVEL_GLOBAL,
        handlers=[RichHandler(rich_tracebacks=True)],
        format="%(message)s",
        datefmt="[%X]",
    )


# markup=True is on by default. Use rich.markup.escape to escape inputs.
console = Console()


# Patch console's status method to change default spinner
def _patch_status(
    self, status: RenderableType, *, spinner: str = _SPINNER, **kwargs
) -> rich.status.Status:
    """Override default spinner."""
    return Console.status(self, status, spinner=spinner, **kwargs)


# Do the patch
setattr(
    console,
    "status",
    types.MethodType(functools.wraps(Console.status)(_patch_status), console),
)
