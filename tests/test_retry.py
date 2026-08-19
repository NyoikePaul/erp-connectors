import pytest

from erp_connectors.exceptions import TransientError
from erp_connectors.retry import with_retry


def test_with_retry_succeeds_after_failures():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError("temp")
        return "ok"

    assert with_retry(flaky, max_attempts=3, base_delay=0.01) == "ok"
    assert calls["n"] == 3


def test_with_retry_raises_after_exhaustion():
    def always_fail():
        raise TransientError("nope")

    with pytest.raises(TransientError):
        with_retry(always_fail, max_attempts=2, base_delay=0.01)
