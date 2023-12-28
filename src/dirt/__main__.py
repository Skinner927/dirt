import logging

from dirt import const


def main():
    logging.basicConfig(level=const.LOG_LEVEL_GLOBAL)
    root = logging.getLogger("dirt")  # because __main__ doesn't look good :D
    root.setLevel(const.LOG_LEVEL_DIRT)

    log = root.getChild(main.__name__)
    log.debug("hi")
    pass


if __name__ == "__main__":
    main()
