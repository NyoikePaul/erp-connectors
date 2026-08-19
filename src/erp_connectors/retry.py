from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

from .exceptions import TransientError

T = TypeVar("T")


def with_retry(
    fn: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    retry_on: tuple[type[Exception], ...] = (TransientError, ConnectionError, TimeoutError),
) -> T:
    last: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except retry_on as exc:
            last = exc
            if attempt == max_attempts:
                break
            delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.25)
            time.sleep(delay)
    assert last is not None
    raise last
