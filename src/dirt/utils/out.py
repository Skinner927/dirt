"""Wrapper around `rich.console` to facilitate any changes."""
from __future__ import annotations

import logging
from typing import List

import rich
import rich.console
import rich.progress
import rich.status
from rich.logging import RichHandler

from dirt import const

__all__ = ["console", "setup_basic_logging"]

# DEFAULT_SPINNER = "bouncingBar" if platform.system() == "Windows" else "dots"


def setup_basic_logging() -> None:
    # https://rich.readthedocs.io/en/latest/logging.html
    logging.basicConfig(
        level=const.LOG_LEVEL_GLOBAL,
        handlers=[RichHandler(rich_tracebacks=True)],
        format="%(message)s",
        datefmt="[%X]",
    )
    logging.getLogger("dirt").setLevel(const.LOG_LEVEL_DIRT)
    logging.getLogger("nox").setLevel(const.LOG_LEVEL_DIRT)
    logging.getLogger("sh").setLevel(const.LOG_LEVEL_DIRT)


# TODO: Progress doesn't properly eat stdout for nox's virtualenv create().
def progress(
    *,
    spinner: None | str = "dots",
    bar: bool = False,
    transient: bool = True,
    console: None | rich.console.Console = None,
) -> rich.progress.Progress:
    # Columns are basically rich.progress.Progress.get_default_columns()
    # with some toggles.
    cols: List[rich.progress.ProgressColumn] = []
    if spinner:
        cols.append(rich.progress.SpinnerColumn(spinner_name=spinner))
    cols.append(rich.progress.TextColumn("[progress.description]{task.description}"))
    if bar:
        cols.append(
            rich.progress.BarColumn(),
        )
    cols += [
        rich.progress.TaskProgressColumn(),
        rich.progress.TimeRemainingColumn(),
    ]

    if console is None:
        console = _console

    return rich.progress.Progress(
        *cols,
        console=console,
        transient=transient,
        redirect_stdout=True,
        redirect_stderr=True,
    )


console = _console = rich.get_console()
