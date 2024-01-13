from __future__ import annotations

__all__ = ["print"]
_print = print


def print(
    *values: object, sep: str | None = " ", end: str | None = "\n", flush: bool = False
) -> None:
    # Placeholder for the moment
    _print(*values, sep=sep, end=end, flush=flush)
