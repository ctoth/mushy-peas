"""External filter fixture that fails with stderr."""

import sys


def main() -> int:
    sys.stderr.write("intentional filter failure\n")
    return 7


if __name__ == "__main__":
    raise SystemExit(main())
