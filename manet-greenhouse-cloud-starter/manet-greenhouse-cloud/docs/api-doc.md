# API Reference — CAAR Cloud Service

Base URL: `http://localhost:8000` (development)

Swagger UI: `http://localhost:8000/docs`  
ReDoc: `http://localhost:8000/redoc`

---

## Schemas

### TelemetrySnapshot (Request)

```json
{
  "node_id": "string",
  "rssi_avg": "float",
  "energy_remaining_pct": "float (0–100)",
  "hop_count": "integer",
  "last_known_weights": {
    "rssi_weight": "float",
    "energy_weight": "float",
    "hop_weight": "float"
  }
}
```

| Field | Type | Bắt buộc | Mô tả |
|-------|------|----------|-------|
| `node_id` | string | ✅ | ID của node MANET (ví dụ `"node-1"`) |
| `rssi_avg` | float | ✅ | RSSI trung bình (dBm, thường âm, ví dụ `-65.0`) |
| `energy_remaining_pct` | float | ✅ | Phần trăm năng lượng còn lại (0–100) |
| `hop_count` | int | ✅ | Số hop hiện tại tới Gateway |
| `last_known_weights` | object | ❌ | Weights đã cache; dùng cho graceful degradation |

---

## Endpoints

### GET /health

Kiểm tra service còn sống.

**Response 200**

```json
{ "status": "ok" }
```

**Ví dụ**

```bash
curl http://localhost:8000/health
```

---

### POST /optimize

Nhận telemetry snapshot từ Gateway, trả về bộ trọng số định tuyến mới.

- **Must-have (nhánh a)** — Week 3-4
- Logic hiện tại: weighted heuristic placeholder (`rssi×0.5 + energy×0.3 + hop×0.2`)
- Digital-Twin validation: stub (Week 6-7)

**Request body:** `TelemetrySnapshot`

**Response 200** — `OptimizeResponse`

```json
{
  "weights": {
    "rssi_weight": 0.5,
    "energy_weight": 0.3,
    "hop_weight": 0.2
  },
  "twin_rejected": false
}
```

| Field | Type | Mô tả |
|-------|------|-------|
| `weights` | object | Bộ trọng số mới để cập nhật vào lõi AODV |
| `twin_rejected` | bool | `true` nếu Digital-Twin dự đoán weights mới sẽ làm giảm hiệu năng → Gateway nên dùng `last_known_weights` |

**Ví dụ**

```bash
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "node-3",
    "rssi_avg": -72.0,
    "energy_remaining_pct": 45.0,
    "hop_count": 4
  }'
```

---

### POST /detect

Nhận telemetry snapshot, trả về cảnh báo bất thường.

- **Should-have (nhánh b)** — Week 6 nếu còn thời gian
- Logic hiện tại: stub, luôn trả `anomaly: false`

**Request body:** `TelemetrySnapshot`

**Response 200** — `DetectResponse`

```json
{
  "anomaly": false,
  "reason": null
}
```

| Field | Type | Mô tả |
|-------|------|-------|
| `anomaly` | bool | `true` nếu phát hiện bất thường (năng lượng cạn đột ngột, RSSI drop, ...) |
| `reason` | string \| null | Mô tả nguyên nhân nếu `anomaly: true` |

**Ví dụ**

```bash
curl -X POST http://localhost:8000/detect \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "node-5",
    "rssi_avg": -85.0,
    "energy_remaining_pct": 8.0,
    "hop_count": 6
  }'
```

---

## Mã lỗi

| HTTP Status | Mô tả |
|-------------|-------|
| `200` | Thành công |
| `422 Unprocessable Entity` | Request body không hợp lệ (thiếu field, sai kiểu) |
| `500 Internal Server Error` | Lỗi server không mong đợi |
