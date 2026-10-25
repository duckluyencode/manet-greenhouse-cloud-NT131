"""
Bảo mật kênh Gateway–Cloud ở tầng ứng dụng (tài liệu đồ án, mục 8.2).

- Lớp 2 (xác thực): API key trong header X-API-Key, so với biến môi trường
  CAAR_API_KEY. Chưa cấu hình khóa thì từ chối mọi request (fail closed).
- Lớp 4 (độ mới): timestamp lệch quá 30 s bị từ chối; nonce (tùy chọn) chỉ
  được dùng một lần trong cửa sổ đó.

Lớp 1 (TLS) do Caddy đảm nhận (deploy/Caddyfile); lớp 3 (miền giá trị) nằm
trong models.py.
"""
import hmac
import os
import threading
import time

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from .models import NetworkSnapshot

API_KEY_ENV = "CAAR_API_KEY"
# Độ lệch tối đa giữa timestamp của snapshot và đồng hồ cloud, theo cả hai chiều.
MAX_CLOCK_SKEW_SECONDS = 30
# Giới hạn cache nonce để tránh dùng hết bộ nhớ khi nhận quá nhiều request.
MAX_SEEN_NONCES = 100_000
# Tần suất quét nonce hết hạn trong bộ nhớ.
NONCE_CLEANUP_INTERVAL_SECONDS = 5

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Cache nonce trong tiến trình hiện tại; triển khai nhiều worker cần kho dùng chung.
SEEN_NONCES: dict[str, float] = {}
# Khóa đảm bảo thao tác kiểm tra và ghi nonce không bị race trong cùng tiến trình.
_NONCE_LOCK = threading.Lock()
# Mốc thời gian lần gần nhất đã dọn nonce hết hạn.
_last_nonce_cleanup = 0.0


def require_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    """Dependency FastAPI: chỉ cho qua request mang đúng API key."""
    expected = os.environ.get(API_KEY_ENV)
    if not expected:
        raise HTTPException(status_code=503, detail="API key is not configured")
    if api_key is None or not hmac.compare_digest(
        api_key.encode(), expected.encode()
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def check_freshness(snapshot: NetworkSnapshot, now: float | None = None) -> None:
    """Từ chối snapshot lệch giờ quá 30 s và nonce đã dùng (chống replay)."""
    global _last_nonce_cleanup

    now = time.time() if now is None else now
    if abs(now - snapshot.timestamp) > MAX_CLOCK_SKEW_SECONDS:
        raise HTTPException(
            status_code=400,
            detail="Request timestamp is outside the allowed time window",
        )

    if snapshot.nonce is None:
        return

    with _NONCE_LOCK:
        if now - _last_nonce_cleanup >= NONCE_CLEANUP_INTERVAL_SECONDS:
            expired = [n for n, exp in SEEN_NONCES.items() if exp < now]
            for nonce in expired:
                del SEEN_NONCES[nonce]
            _last_nonce_cleanup = now

        expires_at = SEEN_NONCES.get(snapshot.nonce)
        if expires_at is not None and expires_at >= now:
            raise HTTPException(
                status_code=400, detail="Duplicate nonce replay detected"
            )

        if len(SEEN_NONCES) >= MAX_SEEN_NONCES:
            raise HTTPException(
                status_code=503,
                detail="Replay protection is temporarily at capacity",
            )

        # Giữ nonce tới khi timestamp của nó không còn qua được kiểm tra độ mới.
        SEEN_NONCES[snapshot.nonce] = snapshot.timestamp + MAX_CLOCK_SKEW_SECONDS
