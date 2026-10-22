# Developer Guide

## 1. Yêu cầu môi trường

| Công cụ | Phiên bản tối thiểu | Ghi chú |
|---------|---------------------|---------|
| Python | 3.11 | Dùng `pyenv` hoặc `conda` để quản lý |
| pip | 24+ | `pip install --upgrade pip` |
| Git | 2.40+ | |
| Docker | 24+ | Tùy chọn, để chạy container |
| g++ | 9+ (C++17) | Parity test `simulation/caar-logic/` |
| NS-3 | một tag cố định, ví dụ ns-3.48 | Chỉ Owner A — xem `simulation/README.md` |

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

File DB mặc định `cloud-service/results.db` (đổi bằng `CAAR_DB_PATH`). Bảng:
`runs`, `metrics`, `cloud_events`, `wan_trace` — schema ở [`app/db.py`](../cloud-service/app/db.py),
mô tả ở [`architecture.md`](architecture.md).

---

## 7. Sửa heuristic

1. Sửa [`app/heuristic.py`](../cloud-service/app/heuristic.py) (bản chuẩn) và thêm test vào `tests/`.
2. Sửa [`caar_logic.h`](../simulation/caar-logic/caar_logic.h) cho khớp.
3. Sinh lại test vector và chạy parity:

```bash
python scripts/gen_parity_cases.py
cd simulation/caar-logic
g++ -std=c++17 -O2 -Wall -Wextra -o test_caar_logic test_caar_logic.cpp
./test_caar_logic ../../contracts/parity_cases.json
```

4. Báo Owner A vì `scratch/caar.cc` include file này. CI chặn nếu quên sinh lại `parity_cases.json`.

---

## 8. Script của Owner B

| Script | Việc |
|---|---|
| `gen_parity_cases.py` | Sinh `contracts/parity_cases.json` |
| `gen_waypoints.py` | Sinh quỹ đạo robot `contracts/waypoints/` |
| `fit_channel.py` | Tham số kênh `contracts/channel.json` |
| `wan_probe.py` | Đo RTT/lỗi tới AWS |
| `run_batch.sh` | Chạy hàng loạt NS-3 (`--dry-run` để xem lệnh) |
| `import_ns3_results.py` | CSV → SQLite |
| `plot_results.py` | Biểu đồ mean ± CI 95%, `hypotheses.md` |

```bash
pip install -r scripts/requirements.txt
pytest scripts/tests
```

---

## 9. Docker

```bash
docker build -t caar-cloud ./cloud-service
docker run -p 8000:8000 -e CAAR_API_KEY=dev-key caar-cloud
curl http://localhost:8000/health
```

Triển khai có HTTPS: `deploy/docker-compose.yml` (xem `user-guide.md`).

---

## 10. CI/CD

GitHub Actions chạy tự động khi push lên mọi branch:
- Job `test`: `ruff` + `pytest` cho `cloud-service/` (Python 3.11, 3.12)
- Job `logic`: kiểm tra `parity_cases.json` khớp script, parity g++, `ruff` + `pytest` cho `scripts/`

Xem workflow tại [`.github/workflows/cloud-service-ci.yml`](../.github/workflows/cloud-service-ci.yml) (đường dẫn từ repo root).

---

## 11. Quy ước commit

Theo [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(cloud): network snapshot heuristic
fix(db): sửa lỗi duplicate run_id khi chạy concurrent
test(cloud): weights sum
sim(ns3): delayed RREQ forwarding
```
