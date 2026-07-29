from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


_request_counts: defaultdict[tuple[str, str, int], int] = defaultdict(int)
_request_duration_sum: defaultdict[tuple[str, str], float] = defaultdict(float)
_request_duration_count: defaultdict[tuple[str, str], int] = defaultdict(int)


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


def record_http_metric(request: Request, status_code: int, duration_seconds: float) -> None:
    method = request.method
    path = _route_path(request)
    _request_counts[(method, path, status_code)] += 1
    _request_duration_sum[(method, path)] += duration_seconds
    _request_duration_count[(method, path)] += 1


def metrics_text() -> str:
    lines = [
        "# HELP aas_http_requests_total HTTP リクエスト総数。",
        "# TYPE aas_http_requests_total counter",
    ]
    for (method, path, status), value in sorted(_request_counts.items()):
        lines.append(
            f'aas_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {value}'
        )
    lines.extend(
        [
            "# HELP aas_http_request_duration_seconds HTTP リクエスト処理時間の集計。",
            "# TYPE aas_http_request_duration_seconds summary",
        ]
    )
    for (duration_method, duration_path), duration_value in sorted(_request_duration_sum.items()):
        count = _request_duration_count[(duration_method, duration_path)]
        labels = f'method="{duration_method}",path="{duration_path}"'
        lines.append(f"aas_http_request_duration_seconds_sum{{{labels}}} {duration_value:.6f}")
        lines.append(f"aas_http_request_duration_seconds_count{{{labels}}} {count}")
    return "\n".join(lines) + "\n"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        token = request_id_var.set(request_id)
        started_at = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration = time.perf_counter() - started_at
            record_http_metric(request, status_code, duration)
            logging.getLogger("audio_analysis_system.http").info(
                "%s %s はステータス %s で %.4f 秒以内に完了しました",
                request.method,
                request.url.path,
                status_code,
                duration,
            )
            request_id_var.reset(token)
