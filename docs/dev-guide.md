# Developer Guide

## 1. Yêu cầu môi trường

| Công cụ | Phiên bản | Dùng cho |
|---|---|---|
| Python | 3.11+ | Cloud service, script phân tích |
| g++ | 9+ (C++17) | Parity test `simulation/caar-logic/` |
| ns-3 | 3.48, profile `release` | Mô phỏng ([`simulation/README.md`](../simulation/README.md)) |
| NetAnim | 3.109 | Xem trace mô phỏng |
| Docker | 24+ | Tùy chọn: image ns-3 (`simulation/Dockerfile`), deploy cloud |

Trên Ubuntu 24.04, `bash simulation/vm/setup-ubuntu.sh` cài ns-3 và NetAnim.

## 2. Clone và cài

```bash
git clone https://github.com/duckluyencode/manet-greenhouse-cloud-NT131.git
cd manet-greenhouse-cloud-NT131
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r cloud-service/requirements.txt -r scripts/requirements.txt ruff==0.17.1
```

## 3. Chạy server cục bộ

```bash
cd cloud-service
export CAAR_API_KEY=dev-key            # Windows: set CAAR_API_KEY=dev-key
uvicorn app.main:app --reload --port 8000
```

Swagger UI: `http://localhost:8000/docs`; ReDoc: `http://localhost:8000/redoc`.

## 4. Test và lint

```bash
cd cloud-service && pytest tests/ -v
pytest scripts/tests -v
ruff check cloud-service/ scripts/     # cấu hình trong ruff.toml
```

## 5. Database (SQLite)

File mặc định `cloud-service/results.db` (đổi bằng `CAAR_DB_PATH`). Bảng `runs`, `metrics`,
`cloud_events`; schema ở [`app/db.py`](../cloud-service/app/db.py), mô tả ở
[`architecture.md`](architecture.md). DB cũ được thêm cột mới khi mở.

## 6. Sửa heuristic

1. Sửa [`app/heuristic.py`](../cloud-service/app/heuristic.py) (bản chuẩn) và thêm test vào `tests/`.
2. Sửa [`caar_logic.h`](../simulation/caar-logic/caar_logic.h) cho khớp.
3. Sinh lại test vector và chạy parity:

```bash
python scripts/gen_parity_cases.py
cd simulation/caar-logic
g++ -std=c++17 -O2 -Wall -Wextra -o test_caar_logic test_caar_logic.cpp
./test_caar_logic ../../contracts/parity_cases.json
```

4. Chạy lại `simulation/install.sh` và `./ns3 build` vì `scratch/caar.cc` include file này.
   CI chặn nếu quên sinh lại `parity_cases.json`.

## 7. Sửa kịch bản NS-3

Sửa `simulation/scratch/caar.cc`, rồi:

```bash
simulation/install.sh ~/ns-3-dev && (cd ~/ns-3-dev && ./ns3 build)
python3 scripts/check_ns3.py --ns3 ~/ns-3-dev --out /tmp/caar-check --seeds 5
```

Thêm cột kết quả thì cập nhật cùng lúc `contracts/README.md`, `METRIC_COLUMNS` trong
`app/db.py`, `import_ns3_results.py` và `check_ns3.py`.

## 8. Script

| Script | Việc |
|---|---|
| `gen_parity_cases.py` | Sinh `contracts/parity_cases.json` |
| `gen_waypoints.py` | Sinh quỹ đạo robot và `layout.json` trong `contracts/waypoints/` |
| `fit_channel.py` | Tham số kênh `contracts/channel.json` |
| `run_batch.sh` | Chạy hàng loạt NS-3 (`--dry-run` để xem lệnh) |
| `check_ns3.py` | Kiểm tra tích hợp NS-3 (mục 14.3) |
| `import_ns3_results.py` | CSV kết quả → SQLite |
| `caar_stats.py` | CI 95 %, Welch t-test (không cần scipy) |
| `plot_results.py` | Biểu đồ mean ± CI 95 %, `hypotheses.md` |

## 9. Docker

```bash
docker build -t caar-cloud ./cloud-service
docker run -p 8000:8000 -e CAAR_API_KEY=dev-key caar-cloud
docker build -f simulation/Dockerfile -t caar-ns3 .
```

Triển khai cloud có HTTPS: `deploy/docker-compose.yml` ([`user-guide.md`](user-guide.md)).

## 10. CI

GitHub Actions ([`.github/workflows/cloud-service-ci.yml`](../.github/workflows/cloud-service-ci.yml))
chạy trên mọi branch:

| Job | Việc |
|---|---|
| `test` | `ruff` + `pytest` cho `cloud-service/` (Python 3.11, 3.12) |
| `logic` | `parity_cases.json` khớp script, parity g++, `ruff` + `pytest` cho `scripts/` |
| `ns3` | Build ns-3.48 (profile `release`, ccache) với CAAR, chạy `check_ns3.py` 5 seed |

## 11. Quy ước commit

Theo [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(cloud): network snapshot heuristic
fix(sim): keep the ns-3 -82 dBm receive threshold
test(scripts): welch t-test properties
docs: update testing report
```
