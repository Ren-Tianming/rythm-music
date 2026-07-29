from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings

logger = logging.getLogger("audio_analysis_system.rate_limit")


@dataclass
class LimitResult:
    allowed: bool
    retry_after_seconds: int


class RateLimiter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._memory: dict[str, tuple[int, float]] = {}
        self._memory_lock = threading.Lock()
        self._redis: Any | None = None
        if settings.redis_url:
            try:
                from redis import Redis

                self._redis = Redis.from_url(settings.redis_url, socket_connect_timeout=0.3, socket_timeout=0.3)
                self._redis.ping()
            except Exception as exc:  # pragma: no cover - ローカル Redis の可用性に依存
                logger.warning("Redis レート制限を利用できないため、プロセス内レート制限へ切り替えます: %s", exc)
                self._redis = None

    def check(self, key: str, limit: int, window_seconds: int) -> LimitResult:
        if limit <= 0:
            return LimitResult(allowed=True, retry_after_seconds=0)
        if self._redis is not None:
            return self._check_redis(key, limit, window_seconds)
        return self._check_memory(key, limit, window_seconds)

    def ping_redis(self) -> bool:
        if not self.settings.redis_url:
            return True
        if self._redis is None:
            return False
        try:
            return bool(self._redis.ping())
        except Exception:
            return False

    def _check_redis(self, key: str, limit: int, window_seconds: int) -> LimitResult:
        redis_client = self._redis
        if redis_client is None:
            return self._check_memory(key, limit, window_seconds)
        bucket = f"rate:{key}:{int(time.time() // window_seconds)}"
        try:
            count, ttl = redis_client.eval(
                """
                local count = redis.call('INCR', KEYS[1])
                if count == 1 then
                    redis.call('EXPIRE', KEYS[1], ARGV[1])
                end
                return {count, redis.call('TTL', KEYS[1])}
                """,
                1,
                bucket,
                window_seconds,
            )
            count = int(count)
            ttl = int(ttl)
        except Exception as exc:  # pragma: no cover - Redis outage path
            logger.error("Redis rate limiter failed; using process-local limiter: %s", exc)
            return self._check_memory(key, limit, window_seconds)
        if count > limit:
            return LimitResult(allowed=False, retry_after_seconds=max(1, int(ttl)))
        return LimitResult(allowed=True, retry_after_seconds=0)

    def _check_memory(self, key: str, limit: int, window_seconds: int) -> LimitResult:
        now = time.monotonic()
        with self._memory_lock:
            count, reset_at = self._memory.get(key, (0, now + window_seconds))
            if now >= reset_at:
                count, reset_at = 0, now + window_seconds
            count += 1
            self._memory[key] = (count, reset_at)
        if count > limit:
            return LimitResult(allowed=False, retry_after_seconds=max(1, int(reset_at - now)))
        return LimitResult(allowed=True, retry_after_seconds=0)
