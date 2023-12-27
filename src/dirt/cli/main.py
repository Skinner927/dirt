import logging
import os
import sys

import dirt.bootstrap
from dirt import const


def main():
    # Configure logging
    logging.basicConfig()
    # Ensure global level is correct if logging was already configured
    logging.getLogger().setLevel(
        os.getenv(const.ENV_DIRT_GLOBAL_LOG_LEVEL) or const.DEFAULT_LOG_LEVEL
    )

    boot = dirt.bootstrap.Bootstrapper()
    boot.start(sys.argv)
