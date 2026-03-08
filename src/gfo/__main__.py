import sys

import gfo


def main():
    if "--version" in sys.argv:
        print(f"gfo {gfo.__version__}")
        sys.exit(0)
    print(f"gfo {gfo.__version__} — not yet implemented")
    sys.exit(1)


if __name__ == "__main__":
    main()
