# Cloud Service — CAAR

Backend FastAPI cho **CAAR (Cloud-Assisted Adaptive Routing)**: control plane
nhận `NetworkSnapshot` từ Gateway và trả 3 trọng số định tuyến cho toàn mạng
(tài liệu đồ án mục 7–9).

## Cấu trúc thư mục

```
cloud-service/
├── app/
│   ├── main.py        # /health, /optimize, /metrics/summary
│   ├── models.py      # NodeTelemetry, NetworkSnapshot, Weights, OptimizeResponse
│   ├── heuristic.py   # hàm thuần chọn trọng số (mục 7.2) — bản chuẩn cho parity C++
│   ├── security.py    # API key, kiểm tra timestamp/nonce
│   └── db.py          # SQLite: runs, metrics, cloud_events, wan_trace
├── tests/             # pytest: test_api.py (bảng 14.2), test_heuristic.py (+ parity)
├── Dockerfile
└── requirements.txt
```

## Chạy local

```bash
cd cloud-service
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
set CAAR_API_KEY=dev-key          # macOS/Linux: export CAAR_API_KEY=dev-key
uvicorn app.main:app --reload --port 8000
# Swagger: http://localhost:8000/docs
```

Không đặt `CAAR_API_KEY` thì `/optimize` trả 503 (fail closed).

## Test

```bash
pytest
```

## Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `CAAR_API_KEY` | (không có) | Khóa client phải gửi trong `X-API-Key` |
| `CAAR_DB_PATH` | `cloud-service/results.db` | File SQLite (Docker: `/data/results.db`) |

## Deploy

Xem `deploy/` (Docker Compose + Caddy, HTTPS tự động) và mục 13.3 của tài liệu.

Chi tiết schema và mã lỗi: [`../docs/api-doc.md`](../docs/api-doc.md).
