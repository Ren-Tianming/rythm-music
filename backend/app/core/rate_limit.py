from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
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
        self._login_failures: dict[str, tuple[int, float, float]] = {}
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

    @staticmethod
    def _private_key(key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def check_login_backoff(self, key: str) -> LimitResult:
        private_key = self._private_key(key)
        if self._redis is not None:
            try:
                ttl = int(self._redis.ttl(f"login:block:{private_key}"))
                return LimitResult(allowed=ttl <= 0, retry_after_seconds=max(0, ttl))
            except Exception as exc:  # pragma: no cover - Redis outage path
                logger.error("Redis login backoff failed; using process-local state: %s", exc)
        now = time.monotonic()
        with self._memory_lock:
            _, reset_at, blocked_until = self._login_failures.get(private_key, (0, now, 0))
            if now >= reset_at:
                self._login_failures.pop(private_key, None)
                return LimitResult(allowed=True, retry_after_seconds=0)
        if blocked_until > now:
            return LimitResult(
                allowed=False,
                retry_after_seconds=max(1, int(blocked_until - now)),
            )
        return LimitResult(allowed=True, retry_after_seconds=0)

    def register_login_failure(self, key: str, window_seconds: int = 600) -> int:
        private_key = self._private_key(key)
        if self._redis is not None:
            try:
                count = int(self._redis.incr(f"login:failures:{private_key}"))
                if count == 1:
                    self._redis.expire(f"login:failures:{private_key}", window_seconds)
                redis_delay = int(min(60, 2 ** max(0, count - 1)))
                self._redis.set(f"login:block:{private_key}", "1", ex=redis_delay)
                return redis_delay
            except Exception as exc:  # pragma: no cover - Redis outage path
                logger.error("Redis login failure tracking failed; using process-local state: %s", exc)
        now = time.monotonic()
        with self._memory_lock:
            count, reset_at, _ = self._login_failures.get(
                private_key,
                (0, now + window_seconds, 0),
            )
            if now >= reset_at:
                count, reset_at = 0, now + window_seconds
            count += 1
            memory_delay = int(min(60, 2 ** max(0, count - 1)))
            self._login_failures[private_key] = (count, reset_at, now + memory_delay)
        return memory_delay

    def clear_login_failures(self, key: str) -> None:
        private_key = self._private_key(key)
        if self._redis is not None:
            try:
                self._redis.delete(
                    f"login:failures:{private_key}",
                    f"login:block:{private_key}",
                )
            except Exception as exc:  # pragma: no cover - Redis outage path
                logger.error("Redis login failure reset failed: %s", exc)
        with self._memory_lock:
            self._login_failures.pop(private_key, None)

    def _check_redis(self, key: str, limit: int, window_seconds: int) -> LimitResult:
        redis_client = self._redis
        if redis_client is None:
            return self._check_memory(key, limit, window_seconds)
        bucket = f"rate:{self._private_key(key)}:{int(time.time() // window_seconds)}"
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
        private_key = self._private_key(key)
        now = time.monotonic()
        with self._memory_lock:
            count, reset_at = self._memory.get(private_key, (0, now + window_seconds))
            if now >= reset_at:
                count, reset_at = 0, now + window_seconds
            count += 1
            self._memory[private_key] = (count, reset_at)
        if count > limit:
            return LimitResult(allowed=False, retry_after_seconds=max(1, int(reset_at - now)))
        return LimitResult(allowed=True, retry_after_seconds=0)


@lru_cache
def get_rate_limiter() -> RateLimiter:
    from app.core.config import get_settings

    return RateLimiter(get_settings())
