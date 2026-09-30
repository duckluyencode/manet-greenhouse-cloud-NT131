# Changelog

Định dạng dựa trên [Conventional Commits](https://www.conventionalcommits.org/) và [Keep a Changelog](https://keepachangelog.com/).  
Versioning theo kế hoạch: `v0.1-alpha` → `v0.3-beta` → `v0.6` → `v1.0-final`.

---

## [Unreleased]

### Added

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
