# Developer Guide

## 1. Yêu cầu môi trường

| Công cụ | Phiên bản tối thiểu | Ghi chú |
|---------|---------------------|---------|
| Python | 3.11 | Dùng `pyenv` hoặc `conda` để quản lý |
| pip | 24+ | `pip install --upgrade pip` |
| Git | 2.40+ | |
| Docker | 24+ | Tùy chọn, để chạy container |
| NS-3 | 3.42 | Chỉ cần cho `simulation/` — xem `simulation/README.md` |

---

## 2. Clone & setup

```bash
git clone https://github.com/duckluyencode/manet-greenhouse-cloud-NT131.git
cd manet-greenhouse-cloud-NT131

# Tạo virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Cài dependencies
cd cloud-service
pip install -r requirements.txt
```

---

## 3. Chạy server cục bộ

```bash
cd cloud-service
uvicorn app.main:app --reload --port 8000
```

Truy cập:
- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 4. Chạy tests

```bash
cd cloud-service
pytest tests/ -v
```

Chạy với coverage:

```bash
pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## 5. Lint & format

Dự án dùng `ruff` để lint và format:

```bash
pip install ruff
ruff check cloud-service/
ruff format cloud-service/
```

---

## 6. Cấu trúc database (SQLite)

File DB tạo tự động tại `cloud-service/results.db` khi server khởi động.

```
runs          → metadata mỗi lần chạy mô phỏng
metrics       → kết quả đo PDR, delay, overhead, energy
cloud_events  → log sự kiện cloud (param_update, outage, twin_rejected)
```

Xem schema chi tiết tại [`app/db.py`](../cloud-service/app/db.py).

---

## 7. Thêm logic thật vào `/optimize` (Week 3-4)

Tìm hàm `_compute_candidate_weights()` trong [`app/main.py`](../cloud-service/app/main.py):

```python
def _compute_candidate_weights(telemetry: TelemetrySnapshot) -> dict:
    # Thay placeholder bằng weighted heuristic thật:
    # RSSI (normalize về 0-1) × w_rssi
    # + energy_remaining_pct / 100 × w_energy
    # + 1 / hop_count × w_hop
    ...
```

Sau khi thêm logic, chạy lại tests để đảm bảo response vẫn đúng schema.

---

## 8. Huấn luyện Digital-Twin (Week 6-7)

1. Chạy ≥ 50 lần mô phỏng NS-3, lưu kết quả vào `results.db`.
2. Mở [`app/twin.py`](../cloud-service/app/twin.py) và thay `predict_effect()` bằng model thật:

```python
from sklearn.linear_model import LinearRegression
# Đọc từ results.db, train model, lưu vào twin_model.joblib
```

3. Bỏ comment khối Digital-Twin trong `app/main.py::optimize()`.

---

## 9. Docker

```bash
# Build image
docker build -t caar-cloud ./cloud-service

# Chạy container
docker run -p 8000:8000 -v $(pwd)/cloud-service:/data caar-cloud

# Kiểm tra health
curl http://localhost:8000/health
```

---

## 10. CI/CD

GitHub Actions chạy tự động khi push lên mọi branch:
- Lint bằng `ruff`
- Chạy `pytest`

Xem workflow tại [`.github/workflows/cloud-service-ci.yml`](../.github/workflows/cloud-service-ci.yml) (đường dẫn từ repo root).

---

## 11. Quy ước commit

Theo [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(cloud): thêm weighted heuristic thật vào /optimize
fix(db): sửa lỗi duplicate run_id khi chạy concurrent
test(cloud): thêm test case optimize với energy thấp
docs: cập nhật api-doc thêm ví dụ detect
```
