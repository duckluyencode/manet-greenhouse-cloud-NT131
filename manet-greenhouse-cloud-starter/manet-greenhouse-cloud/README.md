# MANET Nhà Kính — Cloud-Assisted Adaptive Routing (CAAR)

Đồ án NT131: MANET trong nhà kính, tích hợp kiến trúc Cloud-Assisted Adaptive
Routing (CAAR) với Dual-Horizon tracking và Digital-Twin validation.

Repo này là **điểm khởi đầu thực thi** — bản dựng sẵn khung sườn theo đúng
`master-plan-8-tuan-manet-cloud-nha-kinh.md` (Section 11.1) để bạn không phải
tự gõ lại cấu trúc từ đầu.

## Tài liệu liên quan (không nằm trong repo này, đối chiếu khi cần)
- `master-plan-8-tuan-manet-cloud-nha-kinh.md` — kế hoạch 8 tuần chi tiết, ai làm gì ngày nào
- `ieee-paper-draft.md` — Abstract, Research Questions, bảng kịch bản thí nghiệm
- `bao-ve-thu-qa-workflow-topology.md` — giải thích workflow/topology kiểu hỏi-đáp bảo vệ

## Cấu trúc repo

```
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
```

## BẮT ĐẦU TỪ ĐÂU — Ngày 1

### Bước 1 — Đẩy repo này lên GitHub

```bash
cd manet-greenhouse-cloud
git init
git add .
git commit -m "chore: khoi tao cau truc repo (Master Plan Week 1 Day 5)"
git branch -M main
git remote add origin <link-repo-github-cua-ban>
git push -u origin main
git checkout -b develop
git push -u origin develop
```

Sau đó vào **Settings → Branches** trên GitHub, bật branch protection cho
`main` (yêu cầu PR + ít nhất 1 review trước khi merge) — đúng Section 11.2.

### Bước 2 — Chạy thử Cloud-service (đã có skeleton chạy được ngay)

```bash
cd cloud-service
python3 -m venv .venv && source .venv/bin/activate    # hoặc conda tùy bạn
pip install -r requirements.txt --break-system-packages
uvicorn app.main:app --reload
```

Mở tab khác, kiểm tra:
```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{"node_id":"node-1","rssi_avg":-65,"energy_remaining_pct":80,"hop_count":3}'
```

Chạy test:
```bash
pytest -v
```

**Nếu chạy được tới đây → bạn đã hoàn thành phần kỹ thuật của Day 5 (Week 1)
trong Master Plan.** `/optimize` hiện trả về trọng số placeholder cố định —
đây chính là việc của Day 18/24 (Week 3-4): thay `_compute_candidate_weights()`
trong `app/main.py` bằng công thức thật.

### Bước 3 — Cài NS-3 (không làm được trong sandbox này, xem hướng dẫn riêng)

Xem `simulation/README.md` — có lệnh cài đặt đầy đủ và bảng việc cần làm theo
từng Day trong Master Plan.

### Bước 4 — Việc đầu tiên nên mở Issue

Vào GitHub Issues, tạo 3 issue đầu tiên (dùng template có sẵn trong
`.github/ISSUE_TEMPLATE/`) khớp Daily Plan Week 1-2:
1. `[Day 8-9] Workshop kiến trúc tổng thể` (`type:docs`, `area:docs`)
2. `[Day 15-16] Mobility model row-constrained` (`type:feature`, `area:simulation`)
3. `[Day 18] Weighted metric cho AODV` (`type:feature`, `area:cloud`)

Kéo cả 3 vào GitHub Projects board (cột `Backlog`) — đây chính là Progress
Dashboard nói ở Master Plan Section 16.

## Quy tắc làm việc (tóm tắt — chi tiết ở Master Plan Section 11)

- **Branch:** `main` (bảo vệ) ← `develop` ← `feature/*`, `fix/*`, `docs/*`
- **Commit:** `feat(cloud-service): ...`, `fix(simulation): ...` (Conventional Commits)
- **PR:** cần ≥1 review từ người còn lại trong nhóm 2 người, CI phải xanh
- **DoD mặc định:** merge qua PR + CI xanh + có test kèm — xem legend đầy đủ ở
  Master Plan Section 5

## Việc KHÔNG nên làm ở bước này

- Đừng vội viết Dashboard React — hiện đang xếp Could-have, xem Master Plan Section 1
- Đừng huấn luyện Digital-Twin model thật ngay (`app/twin.py`) — cần dữ liệu từ
  ma trận thí nghiệm Week 6 trước, làm sớm sẽ không có gì để huấn luyện
