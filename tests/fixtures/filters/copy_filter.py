"""External filter fixture that copies stdin to stdout."""

import sys


def main() -> int:
    sys.stdout.buffer.write(sys.stdin.buffer.read())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
