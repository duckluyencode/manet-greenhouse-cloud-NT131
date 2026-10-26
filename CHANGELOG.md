# Changelog

Định dạng theo [Keep a Changelog](https://keepachangelog.com/); commit theo
[Conventional Commits](https://www.conventionalcommits.org/).

## [Unreleased]

### Cloud service
- `POST /optimize` nhận `NetworkSnapshot`, chọn trọng số bằng heuristic toàn mạng (mục 7.2,
  `app/heuristic.py`); so sánh ngưỡng trong miền số nguyên/dBm để khớp tuyệt đối với bản C++
- 4 model mục 9.3 với ràng buộc miền giá trị; `GET /metrics/summary`
- Bảo mật: API key `X-API-Key` (từ chối khi chưa cấu hình), timestamp ±30 s, nonce tùy chọn;
  HTTPS qua Caddy (`deploy/`)
- SQLite: `runs` (có `params` JSON), `metrics` (gồm 4 cột đo cơ chế định tuyến), `cloud_events`

### Mô phỏng (ns-3.48)
- Patch AODV `simulation/aodv-patch/caar-delayed-rreq.patch`: hook thời gian chờ rebroadcast RREQ
  và trace `RouteDiscovery`; không gắn hook thì AODV chạy như bản gốc
- `simulation/scratch/caar.cc`: 4 cấu hình, kênh log-distance + shadowing, WiFi 802.11b,
  quỹ đạo từ `contracts/waypoints`, máy trạng thái Gateway, kênh cloud RTT 40 ms, mất cloud,
  4 phép đo cơ chế (mất gói do không có đường, số hop, RSSI link, chuyển tiếp bởi robot yếu pin),
  `--destination-only`, xuất NetAnim
- `simulation/caar-logic/caar_logic.h`: heuristic, chi phí c_i, máy trạng thái Gateway; parity với
  bản Python qua `contracts/parity_cases.json`
- Môi trường: nhà kính 1 ha, 112 hàng ray, radio WiFi 20 dBm + anten 3 dBi, ngưỡng −82 dBm (tầm ~29 m)
- Cài đặt: `simulation/install.sh`, `simulation/Dockerfile`, `simulation/vm/` (Ubuntu 24.04 không Docker)

### Phân tích
- `scripts/`: sinh quỹ đạo, kênh, test vector; `run_batch.sh` (S1, S2a, S2b, S3, sens, diag);
  `check_ns3.py` (mục 14.3); nhập SQLite; biểu đồ mean ± CI 95 % và `hypotheses.md`
- `results/`: 280 run (S1, S2a, S2b, S3, chẩn đoán), biểu đồ và kết luận Q1–Q3

### CI
- Job `test` (ruff + pytest cloud), `logic` (parity C++, test script), `ns3` (build ns-3.48 và
  chạy `check_ns3.py`); `ruff.toml` với `ruff==0.17.1`

### Removed
- Digital-Twin (`app/twin.py`) và `POST /detect` (ngoài phạm vi, mục 16)

## [0.1.0-alpha]

- Khung repo, FastAPI với `/health`, CI cloud-service, tài liệu ban đầu
