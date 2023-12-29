import logging

from dirt import bootstrap, const


def main():
    logging.basicConfig(level=const.LOG_LEVEL_GLOBAL)
    root = logging.getLogger("dirt")  # because __main__ doesn't look good :D
    root.setLevel(const.LOG_LEVEL_DIRT)
    bootstrap.bootstrap()


if __name__ == "__main__":
    main()
