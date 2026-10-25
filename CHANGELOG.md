# Changelog

Định dạng dựa trên [Conventional Commits](https://www.conventionalcommits.org/) và [Keep a Changelog](https://keepachangelog.com/).  
Versioning theo kế hoạch: `v0.1-alpha` → `v0.3-beta` → `v0.6` → `v1.0-final`.

---

## [Unreleased]

### Added — tích hợp NS-3 (ns-3.48)

- `simulation/aodv-patch/caar-delayed-rreq.patch`: hook thời gian chờ rebroadcast RREQ
  (`SetRreqForwardDelayCallback`) và trace `RouteDiscovery`; không gắn hook thì AODV chạy như bản gốc
- `simulation/scratch/caar.cc`: kịch bản 4 cấu hình, đọc `contracts/`, ghi CSV theo hợp đồng
  và log sự kiện Gateway; `params.pdr_window` cho Q3
- `simulation/install.sh`, `simulation/Dockerfile` (Ubuntu 24.04 + ns-3.48)
- `scripts/check_ns3.py`: kiểm tra mục 14.3; CI job `ns3` build ns-3 và chạy kiểm tra này
- `run_batch.sh` gọi chương trình `caar`, truyền `--speed`, chỉ truyền `--wan-trace` khi đã có trace
- `ruff.toml`, pin `ruff==0.17.1` trong CI
- Môi trường 1 ha theo khảo sát `docs/greenhouse-survey.md`: 100 × 100 m (bằng nhà kính đo kênh
  Cama-Pinto), lối chính ở giữa, 112 hàng ray hai phía dài 47,5 m, Gateway ở (50; 50)
- 4 cột đo cơ chế định tuyến: `loss_no_route_ratio`, `hops_avg`, `link_rssi_avg_dbm`, `weak_relay_share`;
  biểu đồ phân rã mất gói (giao / không có đường / mất trên link)
- NetAnim: `caar --netanim=<xml>` (robot đổi màu theo pin, Gateway theo mức hạ cấp); module `netanim` trong build

### Changed

- Radio mặc định WiFi 20 dBm / −88 dBm (tầm ~29 m) thay cho 16 / −82 dBm (~18 m): ở 18 m, 10 robot chỉ có
  đường về Gateway ~19 % thời gian (lý do chi tiết: `docs/testing-report.md`, mục 14.3)
- `caar` đặt ngưỡng phát hiện preamble bằng độ nhạy thu (ns-3 mặc định chặn ở −82 dBm), từ chối độ nhạy < −90 dBm

### Added — phần Owner B theo tài liệu đồ án bản cập nhật (20/10/2026)

- `/optimize` nhận `NetworkSnapshot` và chạy heuristic toàn mạng (mục 7.2) trong `app/heuristic.py`;
  so sánh ngưỡng trong miền số nguyên/dBm theo quy ước chốt 22/10
- 4 model mục 9.3 với ràng buộc miền giá trị (`NodeTelemetry`, `NetworkSnapshot`, `Weights`, `OptimizeResponse`)
- `app/security.py`: API key `X-API-Key` (fail closed), timestamp ±30 s, nonce tùy chọn
- `GET /metrics/summary`; SQLite thêm `runs.params`, `metrics.route_discovery_ms`,
  `metrics.min_energy_pct`, bảng `wan_trace`; DB cũ được bổ sung cột tự động
- Test API theo bảng 14.2 và test parity Python ↔ `contracts/parity_cases.json`
- `contracts/`: `parity_cases.json`, `channel.json`, `waypoints/` (N ∈ {6,10,16,20} × seed 1..10, biến thể 1 m/s)
- `simulation/caar-logic/caar_logic.h`: heuristic, chi phí c_i, thời gian chờ D_max·c_i, phương án dự phòng 4.5,
  máy trạng thái Gateway 3 mức + TTL; `test_caar_logic.cpp` đọc parity_cases.json (g++, không cần NS-3)
- `scripts/`: `gen_parity_cases.py`, `gen_waypoints.py`, `fit_channel.py`, `wan_probe.py`, `run_batch.sh`,
  `import_ns3_results.py`, `plot_results.py`, `caar_stats.py` (CI 95%, Welch t-test) + pytest
- `deploy/`: Docker Compose FastAPI + Caddy (HTTPS Let's Encrypt); `cloud-service/Dockerfile`
- CI: job `logic` (parity_cases.json khớp script, parity g++, lint + test scripts)

### Removed

- `app/twin.py`, `POST /detect` (cắt khỏi phạm vi, mục 16); `pandas`, `scikit-learn` khỏi requirements

### Fixed

- `.gitignore` bỏ dòng `scratch/` (đang bỏ qua `simulation/scratch/caar.cc`), cho phép `.env.example`

### Added (trước đó)

- Khởi tạo cấu trúc repo từ template
- Cloud-service skeleton: `/health` (hoạt động), `/optimize` (logic placeholder), `/detect` (stub)
- SQLite schema: bảng `runs`, `metrics`, `cloud_events`
- Digital-Twin stub module (`app/twin.py`)
- CI cho cloud-service (`.github/workflows/cloud-service-ci.yml`)
- Issue/PR templates
- Docs đầy đủ: README, architecture, api-doc, dev-guide, srs, testing-report, user-guide
- `.gitignore` cho Python + NS-3

---

## [0.1.0-alpha] — Khởi tạo (Week 1-2)

### Added

- Repo structure theo Master Plan Section 14
- FastAPI app với 3 endpoints placeholder
- pytest suite: `test_health`, `test_optimize_returns_weights`, `test_detect_stub`
- `requirements.txt`: fastapi, uvicorn, pydantic, pytest, httpx, pandas, scikit-learn

---

## Kế hoạch các phiên bản tiếp theo

| Phiên bản | Mốc | Nội dung chính |
|-----------|-----|----------------|
| `v0.2-alpha` | Week 3-4 | Logic weighted heuristic thật trong `/optimize` |
| `v0.3-beta` | Week 4-5 | NS-3: mobility model + channel model + AODV baseline |
| `v0.4-beta` | Week 5 | NS-3: cloud-assisted variant, graceful degradation |
| `v0.5-beta` | Week 6 | Chạy mô phỏng S1–S3, thu thập metrics vào SQLite |
| `v0.6` | Week 6-7 | Digital-Twin validation (sklearn), `/detect` logic thật |
| `v1.0-final` | Week 8 | Tất cả kịch bản S1–S4 hoàn chỉnh, báo cáo đầy đủ |
