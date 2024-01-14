import logging
import sys

from dirt import bootstrap, const, utils


def main() -> None:
    utils.out.setup_basic_logging()
    root = logging.getLogger("dirt")  # because __main__ doesn't look good :D
    root.setLevel(const.LOG_LEVEL_DIRT)
    sys.exit(bootstrap.bootstrap())


if __name__ == "__main__":
    main()
