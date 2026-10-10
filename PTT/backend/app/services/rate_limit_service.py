import os
from urllib.parse import urlsplit

from fastapi import HTTPException, status
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

REPORT_PDF_LIMIT = 5
REPORT_PDF_WINDOW_SECONDS = 60

_INCREMENT_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {count, redis.call('TTL', KEYS[1])}
"""

_settings = get_settings()
_redis_options = {
    "socket_connect_timeout": 1,
    "socket_timeout": 1,
}
if os.name == "nt" and urlsplit(_settings.REDIS_URL).hostname == "localhost":
    _redis_options["host"] = "127.0.0.1"

redis_client = Redis.from_url(_settings.REDIS_URL, **_redis_options)


def enforce_report_pdf_limit(user_id: int) -> None:
    try:
        count, retry_after = redis_client.eval(
            _INCREMENT_LIMIT_SCRIPT,
            1,
            f"rate-limit:report-pdf:user:{user_id}",
            REPORT_PDF_WINDOW_SECONDS,
        )
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El control de frecuencia no esta disponible",
        ) from exc

    if int(count) > REPORT_PDF_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Limite de exportaciones alcanzado; intente mas tarde",
            headers={"Retry-After": str(max(int(retry_after), 1))},
        )