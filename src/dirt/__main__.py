import sys

import dirt.bootstrap


def main():
    boot = dirt.bootstrap.Bootstrapper()
    boot.start(sys.argv)


if __name__ == "__main__":
    main()
