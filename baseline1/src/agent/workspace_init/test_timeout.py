from __future__ import annotations

import time

from timeout_tools import fail_after_timeout


def main() -> int:
    with fail_after_timeout(1, "test timeout triggered"):
        time.sleep(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
