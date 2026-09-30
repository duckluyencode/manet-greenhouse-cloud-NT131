# Kiến trúc hệ thống CAAR

## 1. Tổng quan

Kiến trúc **Cloud-Assisted Adaptive Routing (CAAR)** tách biệt hai mặt phẳng:

- **Mặt phẳng biên (Edge Plane):** Lõi AODV gọn nhẹ chạy tự chủ trên từng nút MANET, đảm bảo tiết kiệm năng lượng tối đa.
- **Mặt phẳng điều phối (Cloud Plane):** Bộ tối ưu hóa trên đám mây tổng hợp telemetry từ toàn mạng, tính lại trọng số định tuyến định kỳ và đẩy xuống Gateway.

Cơ chế **graceful degradation** đảm bảo mạng không sụp đổ khi mất kết nối cloud — các nút tự động dùng bộ tham số đã cache cục bộ.

---

## 2. Các thành phần

### 2.1 MANET Node (Edge)

- **Giao thức:** AODV mở rộng với metric đa tiêu chí (RSSI + hop-count + năng lượng còn lại).
- **Di chuyển:** Row-constrained mobility — robot bám theo luống cây cố định (không random waypoint).
- **Kênh truyền:** Mô hình suy hao có xét khung kim loại nhà kính và tán lá.
- **Triển khai:** NS-3 (xem `simulation/`).

### 2.2 Gateway Node

- Cầu nối duy nhất giữa mạng MANET và cloud.
- Thu thập telemetry từ các nút → gửi lên `POST /optimize`.
- Nhận `weights` từ cloud → phân phát lại cho các nút.
- **Graceful degradation:** Nếu không nhận được phản hồi từ cloud trong `timeout_ms`, Gateway dùng `last_known_weights` đã cache và đánh dấu trạng thái `degraded`.

### 2.3 Cloud Service (FastAPI)

Xem [`docs/api-doc.md`](api-doc.md) để biết chi tiết endpoint.

```
cloud-service/
└── app/
    ├── main.py     ← /health, /optimize, /detect
    ├── db.py       ← SQLite (runs, metrics, cloud_events)
    ├── models.py   ← TelemetrySnapshot, OptimizeResponse, DetectResponse
    └── twin.py     ← Digital-Twin validation (Week 6-7)
```

**Luồng `/optimize`:**

```
Gateway → POST /optimize {TelemetrySnapshot}
              ↓
    _compute_candidate_weights()
    [RSSI×0.5 + energy×0.3 + hop×0.2]   ← placeholder, Week 3-4
              ↓
    [Digital-Twin validation]            ← stub, Week 6-7
    predict_effect(telemetry, weights)
    if worse_than_current → reject, trả weights cũ
              ↓
    → OptimizeResponse {weights, twin_rejected}
              ↓
Gateway ← nhận weights mới → phân phát cho MANET nodes
```

### 2.4 Digital-Twin (stub → Week 6-7)

- Mô hình hồi quy nhẹ (sklearn `LinearRegression` hoặc `DecisionTreeRegressor`).
- Dự đoán PDR/delay từ `(telemetry hiện tại + weights ứng viên)`.
- Dùng để quyết định `twin_rejected` trong `/optimize`.
- Dữ liệu huấn luyện: bảng `metrics` trong SQLite (thu thập từ Week 6).

### 2.5 SQLite Database

| Bảng | Mô tả |
|------|-------|
| `runs` | Metadata mỗi lần chạy mô phỏng: config_type, scenario, seed, node_count |
| `metrics` | Kết quả đo lường: PDR, delay, overhead, energy, cloud_latency |
| `cloud_events` | Log sự kiện: param_update, outage_start/end, twin_rejected |

---

## 3. Luồng dữ liệu tổng thể

```
[NS-3 Simulation]
    │ telemetry (RSSI, energy, hop_count)
    ▼
[Gateway Node]  ──── timeout? ────→ [Graceful Degradation]
    │                                    └─ dùng cached weights
    │ POST /optimize
    ▼
[Cloud Service]
    │ _compute_candidate_weights()
    │ Digital-Twin validation (Week 6-7)
    ▼
[OptimizeResponse {weights}]
    │
    ▼
[Gateway] → phân phát weights → [MANET Nodes]
    │
    ▼
[SQLite DB] ← log cloud_events
```

---

## 4. Cấu hình thí nghiệm

Ba cấu hình được so sánh trực tiếp:

| `config_type` | Mô tả |
|---------------|-------|
| `no_cloud` | AODV thuần — baseline phân tán |
| `local_optimized` | AODV với metric đa tiêu chí, không dùng cloud |
| `cloud_assisted` | Kiến trúc CAAR đầy đủ |

---

## 5. Graceful Degradation — cơ chế chi tiết

```
Cloud available?
    ├─ YES → dùng weights từ /optimize response
    └─ NO  → dùng last_known_weights (cached tại Gateway)
               └─ Không có cache? → dùng default weights [0.5, 0.3, 0.2]
```

Mục tiêu (Kịch bản S2): hiệu năng khi degraded ≥ hiệu năng `no_cloud` baseline.

---

## 6. Môi trường mô phỏng (NS-3)

- **Topology:** Nhà kính 100×50 m, grid 3×N luống cây.
- **Nút:** 6–20 MANET nodes (robot) + 1 Gateway.
- **Mobility:** Row-constrained (bám theo luống, rẽ góc vuông).
- **Channel:** Suy hao đặc trưng nhà kính (khung kim loại + tán lá); tham số hóa theo giai đoạn sinh trưởng.
- **Metrics thu thập:** PDR, E2E delay, routing overhead, energy consumption, cloud bandwidth.
