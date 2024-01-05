from __future__ import annotations

import os
import re
import sys
import types
from pathlib import Path
from typing import Final, Mapping, Tuple

# TODO: Add doc strings to all these

# == PYTHON VERSION CHECK ====================================================
PY_GE_39: Final[bool] = sys.version_info >= (3, 9)
PY_GE_310: Final[bool] = sys.version_info >= (3, 10)

# == CONST STRINGS ============================================================
DIRT_INI_FNAMES: Final[Tuple[str, ...]] = ("dirt.ini", ".dirt.ini")
XDG_CONFIG_HOME: Final[Path] = (
    Path(os.getenv("XDG_CONFIG_HOME") or "~/.config").expanduser().resolve()
)
USER_DIRT_INI: Final[Path] = XDG_CONFIG_HOME / "dirt.ini"
TASKS_PKG_HASH_EXTENSIONS: Final[Tuple[str, ...]] = ("py", "ini", "cfg", "txt", "toml")
DOT_DIRT_NAME: Final[str] = ".dirt"
VENV_DIR_NAME: Final[str] = "venv"

# == ENVIRONMENT VARIABLES ====================================================
# Prefer to use the resolved values instead of directly accessing env vars
ENV_LOG_LEVEL_GLOBAL: Final[str] = "DIRT_GLOBAL_LOG_LEVEL"
ENV_LOG_LEVEL_DIRT: Final[str] = "DIRT_LOG_LEVEL"

# == DEFAULTS =================================================================
DEFAULT_LOG_LEVEL: Final[str] = "WARNING"
DEFAULT_PROG_NAME: Final[str] = "dirt"
if re.search(r"^[^a-zA-Z]", DEFAULT_PROG_NAME) is not None:
    raise ValueError(f"DEFAULT_PROG_NAME must start with a letter: {DEFAULT_PROG_NAME}")
DEFAULT_PROG_NAME_SNAKE: Final[str] = re.sub(
    r"__+", "_", re.sub(r"[^a-zA-Z0-9_]", "_", DEFAULT_PROG_NAME.lower())
)
DEFAULT_TASKS_PROJECT: Final[str] = "./tasks"
DEFAULT_TASKS_MAIN: Final[str] = "tasks"

ARG_PARSE_KWARGS: Final[Mapping[str, str]] = types.MappingProxyType(
    dict(fromfile_prefix_chars="@", allow_abbrev=False)
)
"""Standard kwargs for ArgumentParsers."""

# == RESOLVED CONSTANTS =======================================================
LOG_LEVEL_GLOBAL: Final[str] = os.getenv(ENV_LOG_LEVEL_GLOBAL) or DEFAULT_LOG_LEVEL
"""Override global logging level."""
# TODO: Change this back to `or LOG_LEVEL_GLOBAL` maybe or info?
LOG_LEVEL_DIRT: Final[str] = os.getenv(ENV_LOG_LEVEL_DIRT) or "DEBUG"
"""Override dirt's logging level."""
