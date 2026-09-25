# MANET Nhà Kính — Cloud-Assisted Adaptive Routing (CAAR)

Đồ án NT131: MANET trong nhà kính, tích hợp kiến trúc Cloud-Assisted Adaptive
Routing (CAAR) với Dual-Horizon tracking và Digital-Twin validation.

manet-greenhouse-cloud/
├── simulation/          # NS-3 (C++) — Owner A — xem simulation/README.md
├── cloud-service/         # FastAPI (Python) — Owner B — ĐÃ CÓ SKELETON CHẠY ĐƯỢC
│   ├── app/                # main.py, models.py, db.py, twin.py
│   └── tests/               # pytest
├── scripts/reports/        # (Week 6+) script pandas/matplotlib xuất bảng/biểu đồ tĩnh
├── docs/                     # SRS, Architecture, API, guides — placeholder, điền dần theo Section 14
├── .github/                   # CI, issue templates, PR template
├── .gitignore
└── CHANGELOG.md
-------------------------------------------------------------------------------------------------------------
