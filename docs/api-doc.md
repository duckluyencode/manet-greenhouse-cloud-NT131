# API Reference — CAAR Cloud Service

Base URL: `http://localhost:8000` (dev) · `https://<tên-miền>` (EC2, sau Caddy)

Swagger UI: `/docs` (nút **Authorize** để nhập `X-API-Key`) · ReDoc: `/redoc`

Đặc tả gốc: tài liệu đồ án mục 7.2 (heuristic), 8 (bảo mật), 9.2–9.3 (API, model).

---

## Xác thực và độ mới

| Kiểm tra | Cách làm | Lỗi |
|---|---|---|
| API key | Header `X-API-Key` phải bằng biến môi trường `CAAR_API_KEY` của server | `401` sai/thiếu key; `503` server chưa cấu hình key |
| Timestamp | `abs(now - timestamp) <= 30 s` | `400` |
| Nonce (tùy chọn) | Mỗi nonce dùng một lần trong cửa sổ 30 s | `400` khi gửi lại |
| Miền giá trị | Pydantic, bảng dưới | `422` |

`/health` không cần key. `/optimize` và `/metrics/summary` cần key.

---

## Schemas

### NodeTelemetry

| Field | Kiểu | Ràng buộc |
|---|---|---|
| `node_id` | string | Bắt buộc là chuỗi (ví dụ `"r1"`); gửi số → 422 |
| `rssi_avg` | float (dBm) | `[-120; 0]` |
| `energy_remaining_pct` | float | `[0; 100]` |
| `hop_count` | int | `>= 1` |

### NetworkSnapshot (request của `/optimize`)

| Field | Kiểu | Ràng buộc |
|---|---|---|
| `run_id` | int | ID run (0 khi đo trace) |
| `timestamp` | float | Unix time hiện tại, lệch ≤ 30 s |
| `nonce` | string \| null | Tùy chọn, 1–128 ký tự |
| `nodes` | list[NodeTelemetry] | Ít nhất 1 node |

### Weights

`hop_weight`, `rssi_weight`, `energy_weight`: mỗi giá trị ≥ 0, tổng = 1 (sai số 0,001).

### OptimizeResponse

| Field | Kiểu | Mô tả |
|---|---|---|
| `weights` | Weights | Bộ trọng số Gateway phát cho mọi robot |
| `rule` | `low_battery` \| `poor_signal` \| `balanced` | Luật heuristic đã chọn |

---

## Endpoints

### GET /health

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### POST /optimize

Chọn trọng số theo luật đúng đầu tiên (mục 7.2):

| Điều kiện | w_h | w_r | w_e | rule |
|---|---|---|---|---|
| ≥ 30% robot có pin < 20% | 0,2 | 0,3 | 0,5 | `low_battery` |
| Trung vị RSSI (kẹp [−90; −40] dBm) < −75 dBm | 0,3 | 0,5 | 0,2 | `poor_signal` |
| Còn lại | 0,4 | 0,3 | 0,3 | `balanced` |

Mỗi lần gọi thành công ghi một sự kiện `param_update` vào bảng `cloud_events`.

```bash
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $CAAR_API_KEY" \
  -d "{\"run_id\": 1, \"timestamp\": $(date +%s),
       \"nodes\": [
         {\"node_id\": \"r1\", \"rssi_avg\": -72, \"energy_remaining_pct\": 45, \"hop_count\": 2},
         {\"node_id\": \"r2\", \"rssi_avg\": -85, \"energy_remaining_pct\": 12, \"hop_count\": 3}
       ]}"
# {"weights":{"hop_weight":0.2,"rssi_weight":0.3,"energy_weight":0.5},"rule":"low_battery"}
```

### GET /metrics/summary

PDR và độ trễ trung bình theo cấu hình và kịch bản, từ các run đã nhập bằng
`scripts/import_ns3_results.py`.

```json
[
  {"config_type": "no_cloud", "scenario": "baseline", "runs": 10,
   "pdr_mean": 0.85, "avg_delay_ms_mean": 12.3}
]
```

---

## Mã lỗi

| HTTP | Khi nào |
|---|---|
| `200` | Thành công |
| `400` | Timestamp lệch > 30 s hoặc nonce bị gửi lại |
| `401` | Thiếu hoặc sai `X-API-Key` |
| `422` | Body sai kiểu / ngoài miền giá trị / `nodes` rỗng |
| `503` | Server chưa đặt `CAAR_API_KEY`, hoặc cache nonce đầy |
