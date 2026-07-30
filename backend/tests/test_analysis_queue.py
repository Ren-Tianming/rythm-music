import threading
import time
from collections.abc import Callable

import pytest
from app.core.errors import AppError
from app.services.analysis_queue import AnalysisQueue


def wait_for(predicate: Callable[[], bool], timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("Condition was not reached before timeout")


def test_analysis_queue_runs_one_job_at_a_time_in_fifo_order() -> None:
    queue = AnalysisQueue(max_concurrency=1, max_queue_size=2, wait_seconds=2)
    release_holder = threading.Event()
    entered: list[str] = []

    def run(name: str, hold: bool = False) -> None:
        with queue.acquire():
            entered.append(name)
            if hold:
                release_holder.wait(timeout=2)

    holder = threading.Thread(target=run, args=("holder", True))
    first = threading.Thread(target=run, args=("first",))
    second = threading.Thread(target=run, args=("second",))
    holder.start()
    wait_for(lambda: queue.active_count == 1)
    first.start()
    wait_for(lambda: queue.waiting_count == 1)
    second.start()
    wait_for(lambda: queue.waiting_count == 2)
    release_holder.set()

    for thread in (holder, first, second):
        thread.join(timeout=2)
        assert not thread.is_alive()
    assert entered == ["holder", "first", "second"]


def test_analysis_queue_rejects_only_when_bounded_waiting_room_is_full() -> None:
    queue = AnalysisQueue(max_concurrency=1, max_queue_size=1, wait_seconds=2)
    release_holder = threading.Event()

    def hold() -> None:
        with queue.acquire():
            release_holder.wait(timeout=2)

    holder = threading.Thread(target=hold)
    waiting = threading.Thread(target=lambda: next_job(queue))
    holder.start()
    wait_for(lambda: queue.active_count == 1)
    waiting.start()
    wait_for(lambda: queue.waiting_count == 1)

    with pytest.raises(AppError) as exc_info, queue.acquire():
        pass
    assert exc_info.value.code == "ANALYSIS_QUEUE_FULL"

    release_holder.set()
    holder.join(timeout=2)
    waiting.join(timeout=2)


def next_job(queue: AnalysisQueue) -> None:
    with queue.acquire():
        return
