from __future__ import annotations

import logging
import os
from typing import Final, Optional

# == GLOBAL NAME ==============================================================
NAME: Final[str] = os.getenv("DIRT_NAME") or "Dirt"
"""Dirt's public name.

`.lower()` version used for Dirt's root logger. `.upper()` versions used for other ENV
variables.

Change with environment variable "DIRT_NAME".
"""
LOWER_NAME: Final[str] = NAME.lower()
UPPER_NAME: Final[str] = NAME.upper()

# == ENVIRONMENT VARIABLES=====================================================
# Privates not to be used outside this module.
# Use the resolved values from this module instead of accessing directly.
_ENV_LOG_LEVEL_GLOBAL: Final[str] = f"{UPPER_NAME}_GLOBAL_LOG_LEVEL"
_ENV_LOG_LEVEL_DIRT: Final[str] = f"{UPPER_NAME}_LOG_LEVEL"

# == DEFAULTS =================================================================
DEFAULT_LOG_LEVEL: Final[str] = "WARNING"

# == RESOLVED CONSTANTS =======================================================
LOG_LEVEL_GLOBAL: Final[str] = os.getenv(_ENV_LOG_LEVEL_GLOBAL) or DEFAULT_LOG_LEVEL
"""Override global logging level."""
LOG_LEVEL_DIRT: Final[str] = os.getenv(_ENV_LOG_LEVEL_DIRT) or LOG_LEVEL_GLOBAL
"""Override dirt's logging level."""

# == LOGGING =================================================================
_root_logger_name: Final[str] = LOWER_NAME
_dirt_root_logger: Optional[logging.Logger] = None
_pkg_name: Final[str] = (
    "dirt" if ("__main__" == __name__) else (__name__.split(".")[0])
)


def child_logger(name: str = "") -> logging.Logger:
    """Get a properly named child logger from the root Dirt logger.

    Will initialize logging level on first call.
    :param name: Can be a fully-qualified name or a name that should branch off
     the root Dirt logger. If name starts with 'dirt' or `LOWER_NAME` value,
     a child logger will be created from the "root" Dirt logger. Empty string
     returns the "root" Dirt logger.
    :return: Logger
    """
    global _dirt_root_logger
    if _dirt_root_logger is None:
        # Create dirt logger
        _dirt_root_logger = logging.getLogger(_root_logger_name)
        _dirt_root_logger.setLevel(LOG_LEVEL_DIRT)

    # Fixup name
    if name is None:
        # Safer than sorry
        name = ""
    elif name.startswith(_pkg_name):
        # name is fully-qualified using 'dirt' package name. Pop the root node
        # off so we're dealing with a name relative to the Dirt root logger.
        name = name.lstrip(_pkg_name).lstrip(".")
    elif name.startswith(_root_logger_name):
        # Similar to above, but using _root_logger_name instead of 'dirt'.
        name = name.lstrip(_root_logger_name).lstrip(".")
    elif name.startswith("__main__"):
        # Strip __main__ prefix from any names
        name = name.lstrip("__main__").lstrip(".")

    # Resolve
    if not name:
        # Root dirt logger
        return _dirt_root_logger

    return _dirt_root_logger.getChild(name)
