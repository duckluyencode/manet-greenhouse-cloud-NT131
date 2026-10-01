# Cloud Service — CAAR

Backend FastAPI cho kiến trúc **CAAR (Cloud-Assisted Adaptive Routing)** —
nhận telemetry từ Gateway Node dưới edge, trả về trọng số định tuyến tối
ưu, và (giai đoạn sau) phát hiện bất thường qua Digital-Twin validation.

Xem tổng quan kiến trúc toàn hệ thống tại [`../README.md`](../README.md)
và [`../docs/architecture.md`](../docs/architecture.md).

## Cấu trúc thư mục

```
cloud-service/
├── app/
│   ├── __init__.py
│   ├── main.py       # FastAPI app, 3 endpoint: /health, /optimize, /detect
│   ├── models.py      # Pydantic request/response schema
│   ├── db.py           # SQLite schema (runs, metrics, cloud_events)
│   └── twin.py          # Digital-Twin validation (stub, Should-have)
├── tests/
│   ├── __init__.py
│   └── test_health.py
└── requirements.txt
```

## Yêu cầu môi trường

- Python 3.11+

## Cài đặt

```bash
cd cloud-service
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Chạy service

```bash
uvicorn app.main:app --reload --port 8000
```

Service chạy tại `http://127.0.0.1:8000`. Xem tài liệu Swagger UI tự
sinh tại `http://127.0.0.1:8000/docs`.

## Chạy test

```bash
pytest
```

## Endpoints

| Method | Path | Mô tả | Trạng thái |
|---|---|---|---|
| GET | `/health` | Kiểm tra service còn sống | ✅ Hoạt động |
| POST | `/optimize` | Nhận telemetry, trả trọng số định tuyến mới | ⚠️ Placeholder — chờ công thức thật (Week 3-4) |
| POST | `/detect` | Nhận telemetry, trả cảnh báo bất thường | ⚠️ Placeholder — Should-have, làm nếu còn thời gian (Week 6) |

Chi tiết request/response schema xem [`../docs/api-doc.md`](../docs/api-doc.md).

## Database

SQLite, file `results.db` tự tạo tại thư mục `cloud-service/` khi service
khởi động lần đầu (qua `init_db()` trong `app/db.py`). Không commit file
này lên git — đã có trong `.gitignore`.

3 bảng chính:
- `runs` — metadata mỗi lần chạy mô phỏng (config_type, scenario, seed...)
- `metrics` — kết quả đo lường (PDR, delay, overhead, energy...)
- `cloud_events` — log sự kiện trên kênh cloud (param_update, outage, twin_rejected...)

## TODO đang mở (xem thêm comment TODO trong code)

- **Week 3-4** — `_compute_candidate_weights()` trong `main.py`: thay công
  thức placeholder bằng weighted heuristic thật (RSSI + hop-count + năng
  lượng còn lại)
- **Week 6-7** — `predict_effect()` trong `twin.py`: huấn luyện model hồi
  quy nhẹ (sklearn) từ dữ liệu bảng `metrics`, bật lại đoạn code Digital-Twin
  validation đang comment trong `main.py::optimize()`
- **Week 6** (nếu còn thời gian) — `/detect` endpoint: logic phát hiện bất
  thường thật thay vì luôn trả `anomaly: false`
