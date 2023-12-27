from __future__ import annotations

import logging
import os
from typing import Final

import dirt.session

# == DEFAULTS ====================================================
DEFAULT_LOG_LEVEL: Final[str] = "WARNING"
DEFAULT_DIRT_NAME: Final[str] = "Dirt"

# == ENVIRONMENT VARIABLES ====================================================
# Not to be used outside this module.
_ENV_DIRT_NAME: Final[str] = "DIRT_NAME"
_NAME: Final[str] = os.getenv(_ENV_DIRT_NAME) or DEFAULT_DIRT_NAME
"""Dirt's public name; influences other environment variables."""

_ENV_LOG_LEVEL_GLOBAL: Final[str] = f"{_NAME.upper()}_GLOBAL_LOG_LEVEL"
"""Set global logging level."""
_ENV_LOG_LEVEL_DIRT: Final[str] = f"{_NAME.upper()}_LOG_LEVEL"
"""Set Dirt's logging level."""


def main() -> None:
    """Entrypoint for Dirt cli."""
    # Resolve envs
    global_ll = os.getenv(_ENV_LOG_LEVEL_GLOBAL) or DEFAULT_LOG_LEVEL
    dirt_ll = os.getenv(_ENV_LOG_LEVEL_DIRT) or global_ll

    # Configure logging
    logging.basicConfig(level=global_ll)
    # Ensure global level is correct if logging was already configured (idk)
    logging.getLogger().setLevel(global_ll)
    # Set dirt logger's level
    dirt_logger = logging.getLogger(_NAME.lower())
    dirt_logger.setLevel(dirt_ll)

    # Create and start the runner
    runner = dirt.session.Runner.bootstrap(name=_NAME)
    runner.run()
