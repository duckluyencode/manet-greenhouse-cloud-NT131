# Testing Report

**Dự án:** MANET Nhà Kính — CAAR  
**Cập nhật:** (cập nhật liên tục theo tiến độ)

---

## 1. Chiến lược kiểm thử

### 1.1 Các tầng kiểm thử

| Tầng | Công cụ | Vị trí | Chạy tự động |
|------|---------|--------|--------------|
| Unit test (API) | pytest + httpx | `cloud-service/tests/` | CI (mỗi push) |
| Integration test | pytest | `cloud-service/tests/` | CI (mỗi push) |
| Simulation test (NS-3) | NS-3 test suite | `simulation/test/` | Thủ công (Week 3) |
| End-to-end | Manual | — | Thủ công |

### 1.2 Định nghĩa "Done" cho kiểm thử (DoD-Test)

- Mỗi endpoint có ít nhất 1 test happy-path và 1 test edge-case.
- CI xanh trước khi merge vào `main`.
- Simulation test: mỗi kịch bản S1–S4 phải có ít nhất 3 seed khác nhau.

---

## 2. Test suite hiện tại

### 2.1 `cloud-service/tests/test_health.py`

| Test | Mô tả | Kết quả |
|------|-------|---------|
| `test_health` | GET /health trả `{"status":"ok"}` với HTTP 200 | ✅ Pass |
| `test_optimize_returns_weights` | POST /optimize trả `weights` và `twin_rejected=false` | ✅ Pass |
| `test_detect_stub` | POST /detect trả `anomaly=false` | ✅ Pass |

---

## 3. Kế hoạch kiểm thử theo tuần

### Week 3-4 — Sau khi thêm logic /optimize thật

- [ ] `test_optimize_high_energy`: node năng lượng cao → rssi_weight giảm, energy_weight tăng
- [ ] `test_optimize_low_hop`: hop_count=1 → hop_weight ảnh hưởng thế nào?
- [ ] `test_optimize_sum_weights`: tổng weights phải = 1.0 (hoặc trong khoảng cho phép)
- [ ] `test_optimize_invalid_rssi`: rssi_avg = 0 (không hợp lệ) → 422

### Week 5 — Graceful Degradation

- [ ] `test_gateway_timeout_fallback`: mock cloud timeout → Gateway dùng `last_known_weights`
- [ ] `test_gateway_no_cache_fallback`: không có cache → dùng default weights

### Week 6-7 — Digital-Twin

- [ ] `test_twin_rejected_flag`: khi twin dự đoán tệ hơn → `twin_rejected=true`, trả weights cũ
- [ ] `test_twin_accepted_flag`: khi twin dự đoán tốt hơn → `twin_rejected=false`

---

## 4. Các kịch bản mô phỏng NS-3

| Kịch bản | `config_type` | Điều kiện | Metrics thu thập |
|----------|---------------|-----------|-----------------|
| S1-baseline | tất cả 3 | Kết nối cloud ổn định | PDR, delay, overhead |
| S2-outage | `cloud_assisted` | Ngắt cloud hoàn toàn | PDR so với `no_cloud` |
| S2-degraded | `cloud_assisted` | Cloud latency tăng dần | PDR theo latency |
| S3-scale | `cloud_assisted` | node_count: 6→20 | Cloud bandwidth |
| S3-quality | `cloud_assisted` | Packet loss 0→30% | Tại điểm nào cost > benefit? |
| S4-mitm | `cloud_assisted` | MITM attack trên kênh cloud | Hiệu năng thay đổi thế nào? |
| S4-gateway-spof | `cloud_assisted` | Gateway fail | Fallback hoạt động? |

---

## 5. Báo cáo kết quả (cập nhật sau khi chạy)

> Phần này sẽ được điền sau khi hoàn thành mô phỏng (Week 5-6).

### 5.1 Kịch bản S1 — Hiệu năng

| Metric | `no_cloud` | `local_optimized` | `cloud_assisted` | Cải thiện |
|--------|-----------|-------------------|------------------|-----------|
| PDR (%) | — | — | — | — |
| Avg delay (ms) | — | — | — | — |
| Overhead ratio | — | — | — | — |

### 5.2 Kịch bản S2 — Graceful Degradation

| Điều kiện | PDR `cloud_assisted` | PDR `no_cloud` | Kết luận |
|-----------|---------------------|----------------|---------|
| Cloud offline | — | — | — |

---

## 6. Bảo mật (Kịch bản S4)

Bề mặt tấn công mới do kênh cloud:

| Bề mặt | Mô tả | Biện pháp đề xuất |
|--------|-------|------------------|
| MITM trên kênh Gateway↔Cloud | Kẻ tấn công inject weights giả | HTTPS/TLS + xác thực request |
| Replay attack | Gửi lại telemetry cũ để khai thác | Timestamp + nonce trong TelemetrySnapshot |
| Gateway SPOF | Mất Gateway → mạng cô lập | Multi-gateway topology (future work) |
| Stale params | Cloud offline dài, params lỗi thời | TTL cho cached weights |
