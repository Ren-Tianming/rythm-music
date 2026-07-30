from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from uuid import uuid4

from app.core.config import get_settings
from app.core.errors import AppError


@dataclass(frozen=True)
class QueueLease:
    initial_position: int


class AnalysisQueue:
    """FIFO admission control for CPU and memory intensive audio analysis."""

    def __init__(
        self,
        *,
        max_concurrency: int,
        max_queue_size: int,
        wait_seconds: int,
    ) -> None:
        self.max_concurrency = max_concurrency
        self.max_queue_size = max_queue_size
        self.wait_seconds = wait_seconds
        self._active = 0
        self._waiting: deque[str] = deque()
        self._condition = threading.Condition()

    @property
    def active_count(self) -> int:
        with self._condition:
            return self._active

    @property
    def waiting_count(self) -> int:
        with self._condition:
            return len(self._waiting)

    @contextmanager
    def acquire(self) -> Iterator[QueueLease]:
        ticket = str(uuid4())
        deadline = time.monotonic() + self.wait_seconds
        with self._condition:
            if self._active >= self.max_concurrency and len(self._waiting) >= self.max_queue_size:
                raise AppError(
                    429,
                    "ANALYSIS_QUEUE_FULL",
                    "解析待ち行列が満杯です。しばらくしてから再試行してください。",
                    headers={"Retry-After": "30"},
                )
            initial_position = len(self._waiting) + (
                1 if self._active >= self.max_concurrency else 0
            )
            self._waiting.append(ticket)
            while (
                self._waiting[0] != ticket
                or self._active >= self.max_concurrency
            ):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._waiting.remove(ticket)
                    self._condition.notify_all()
                    raise AppError(
                        503,
                        "ANALYSIS_QUEUE_TIMEOUT",
                        "解析待ち時間が上限を超えました。もう一度お試しください。",
                        headers={"Retry-After": "30"},
                    )
                self._condition.wait(timeout=remaining)
            self._waiting.popleft()
            self._active += 1

        try:
            yield QueueLease(initial_position=initial_position)
        finally:
            with self._condition:
                self._active -= 1
                self._condition.notify_all()


@lru_cache
def get_analysis_queue() -> AnalysisQueue:
    settings = get_settings()
    return AnalysisQueue(
        max_concurrency=settings.analysis_max_concurrency,
        max_queue_size=settings.analysis_queue_max_size,
        wait_seconds=settings.analysis_queue_wait_seconds,
    )
