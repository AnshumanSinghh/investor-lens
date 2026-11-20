"""Vendor-neutral request pacing and retries, shared by every outbound adapter."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from investor_lens.domain.exceptions import DataFetchError, DataUnavailableError

LOGGER = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 2.0  # exponential backoff: base * 2**(attempt-1)


class RequestGovernor:
    """Spaces outbound requests and retries failures with exponential backoff.

    One governor shared by several gateways keeps the spacing global: a news call and a price call
    are both "requests" and are separated by the same delay. The first request is not delayed.
    """

    def __init__(
        self,
        delay_seconds: float,
        retry_policy: RetryPolicy,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.delay_seconds = delay_seconds
        self.retry_policy = retry_policy
        self._sleep = sleeper
        self._requests_made = 0

    def run(self, call: Callable[[], T], label: str) -> T:
        self._throttle()
        return self._with_retries(call, label)

    def _throttle(self) -> None:
        if self._requests_made > 0:
            LOGGER.debug("Rate limiting: sleeping %.1fs", self.delay_seconds)
            self._sleep(self.delay_seconds)
        self._requests_made += 1

    def _with_retries(self, call: Callable[[], T], label: str) -> T:
        policy = self.retry_policy
        last_exc: BaseException | None = None
        for attempt in range(1, policy.max_attempts + 1):
            try:
                return call()
            except DataUnavailableError:
                raise
            except Exception as exc:
                last_exc = exc
                LOGGER.warning("%s failed (attempt %d/%d): %r", label, attempt, policy.max_attempts, exc)
                if attempt < policy.max_attempts:
                    self._sleep(policy.base_delay_seconds * (2 ** (attempt - 1)))
        raise DataFetchError(
            f"{label} failed after {policy.max_attempts} attempts: {last_exc!r}"
        ) from last_exc
