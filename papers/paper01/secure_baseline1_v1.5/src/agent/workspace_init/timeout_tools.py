from __future__ import annotations

import signal
from contextlib import contextmanager
from types import FrameType
from typing import Iterator


class TimeoutError(RuntimeError):
    pass


@contextmanager
def fail_after_timeout(seconds: int, message: str) -> Iterator[None]:
    def _timeout_handler(signum: int, frame: FrameType | None) -> None:
        del signum, frame
        raise TimeoutError(message)

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])
