from __future__ import annotations

import os
import types
from typing import Final, Mapping, Tuple

# == ENVIRONMENT VARIABLES=====================================================
# Prefer to use the resolved values instead of directly accessing env vars
ENV_LOG_LEVEL_GLOBAL: Final[str] = "DIRT_GLOBAL_LOG_LEVEL"
ENV_LOG_LEVEL_DIRT: Final[str] = "DIRT_LOG_LEVEL"

# == DEFAULTS =================================================================
DEFAULT_LOG_LEVEL: Final[str] = "WARNING"
DEFAULT_DIRT_INI_FNAMES: Final[Tuple[str, ...]] = ("dirt.ini", ".dirt.ini")
DEFAULT_PROG_NAME: Final[str] = "dirt"

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
