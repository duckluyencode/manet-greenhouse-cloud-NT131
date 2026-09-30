# Hướng dẫn sử dụng

## 1. Tổng quan

Hệ thống CAAR gồm hai phần chính mà người dùng tương tác:

1. **Cloud Service** — REST API tối ưu hóa định tuyến cho Gateway.
2. **NS-3 Simulation** — Công cụ mô phỏng để đánh giá hiệu năng CAAR.

---

## 2. Chạy Cloud Service

### 2.1 Cách đơn giản nhất (local)

```bash
cd cloud-service
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2.2 Chạy bằng Docker

```bash
docker build -t caar-cloud ./cloud-service
docker run -p 8000:8000 caar-cloud
```

### 2.3 Kiểm tra service

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

## 3. Gọi API từ Gateway

### 3.1 Yêu cầu tối ưu hóa

```bash
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "node-3",
    "rssi_avg": -68.5,
    "energy_remaining_pct": 62.0,
    "hop_count": 3
  }'
```

**Kết quả:**

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

### 3.2 Hiểu kết quả

| Field | Ý nghĩa |
|-------|---------|
| `weights` | Cập nhật vào bảng định tuyến AODV của tất cả nodes |
| `twin_rejected: false` | Digital-Twin xác nhận weights mới tốt hơn hoặc bằng → áp dụng |
| `twin_rejected: true` | Digital-Twin dự đoán weights mới sẽ làm giảm PDR → **không áp dụng**, giữ nguyên weights cũ |

### 3.3 Graceful Degradation

Nếu Gateway không nhận được response từ `/optimize` trong thời gian cho phép:
1. Dùng `last_known_weights` đã cache từ lần gọi thành công gần nhất.
2. Nếu không có cache → dùng default `{rssi: 0.5, energy: 0.3, hop: 0.2}`.
3. Mạng MANET tiếp tục hoạt động như AODV phân tán thuần túy.

---

## 4. Chạy mô phỏng NS-3

> Xem hướng dẫn đầy đủ tại [`simulation/README.md`](../simulation/README.md).

### 4.1 Quy trình cơ bản

```bash
# 1. Cài NS-3 (xem simulation/README.md)
# 2. Chạy kịch bản baseline
./ns3 run "caar-scenario --config=no_cloud --seed=42"

# 3. Chạy kịch bản cloud-assisted
./ns3 run "caar-scenario --config=cloud_assisted --cloud-url=http://localhost:8000 --seed=42"

# 4. Xem kết quả
cat results/no_cloud_seed42.csv
cat results/cloud_assisted_seed42.csv
```

### 4.2 So sánh kết quả

Kết quả mô phỏng lưu trong `cloud-service/results.db`. Truy vấn ví dụ:

```sql
SELECT r.config_type, AVG(m.pdr), AVG(m.avg_delay_ms)
FROM runs r JOIN metrics m ON r.id = m.run_id
GROUP BY r.config_type;
```

---

## 5. Đọc logs cloud events

```sql
SELECT * FROM cloud_events ORDER BY ts DESC LIMIT 20;
```

| `event_type` | Ý nghĩa |
|-------------|---------|
| `param_update` | Weights mới được áp dụng thành công |
| `outage_start` | Cloud bắt đầu không khả dụng |
| `outage_end` | Cloud khôi phục |
| `stale_detected` | Gateway phát hiện params quá cũ |
| `twin_rejected` | Digital-Twin từ chối weights ứng viên |

---

## 6. Câu hỏi thường gặp

**Q: Service báo lỗi `422 Unprocessable Entity`?**  
A: Kiểm tra request body — `rssi_avg` phải là số (không phải string), `energy_remaining_pct` phải trong 0–100.

**Q: Mô phỏng NS-3 chạy rất chậm?**  
A: Giảm `node_count` hoặc thời gian mô phỏng. Xem gợi ý tối ưu trong `simulation/README.md`.

**Q: `twin_rejected` luôn `false`?**  
A: Đúng — Digital-Twin hiện là stub (Week 6-7 mới có model thật). Stub luôn trả `false` để không chặn nhầm.
