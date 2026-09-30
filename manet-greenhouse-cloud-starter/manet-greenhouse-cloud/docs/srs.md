# Software Requirements Specification (SRS)

**Dự án:** MANET Nhà Kính — CAAR  
**Môn học:** NT131  
**Nhóm:** 06  
**Phiên bản:** 0.1

---

## 1. Giới thiệu

### 1.1 Mục đích

Tài liệu này đặc tả yêu cầu phần mềm cho hệ thống Cloud-Assisted Adaptive Routing (CAAR), bao gồm Cloud Service (FastAPI), module mô phỏng NS-3, và cơ chế graceful degradation.

### 1.2 Phạm vi

Hệ thống CAAR bao gồm:
- Cloud Service: nhận telemetry, tính toán trọng số định tuyến, phát hiện bất thường.
- Module NS-3: mô phỏng mạng MANET trong nhà kính với row-constrained mobility.
- Gateway: cầu nối MANET ↔ Cloud, xử lý graceful degradation.

**Ngoài phạm vi:** Phần cứng robot thực tế, hệ thống điều khiển nhà kính, giao diện người dùng web.

---

## 2. Mô tả tổng quan hệ thống

### 2.1 Bối cảnh

Mạng MANET trong nhà kính phải đối mặt với:
- Suy hao tín hiệu do khung kim loại và tán lá
- Nút di động (robot) chuyển động theo luống cây cố định
- Ràng buộc năng lượng nghiêm ngặt

### 2.2 Giả định

- Mỗi nhà kính có đúng 1 Gateway kết nối cloud.
- Robot di chuyển với tốc độ ≤ 1 m/s.
- Kết nối cloud có độ trễ ≤ 200 ms trong điều kiện bình thường.
- NS-3 được dùng cho mô phỏng; không dùng phần cứng thực tế trong đồ án này.

---

## 3. Yêu cầu chức năng

### FR-01: Endpoint /health

**Mô tả:** Cloud Service phải cung cấp endpoint kiểm tra sức sống.  
**Input:** GET request.  
**Output:** `{"status": "ok"}` với HTTP 200.  
**Ưu tiên:** Must-have.

### FR-02: Endpoint /optimize — Tính trọng số định tuyến

**Mô tả:** Nhận telemetry snapshot từ Gateway, trả về bộ trọng số định tuyến.  
**Input:** `TelemetrySnapshot` (node_id, rssi_avg, energy_remaining_pct, hop_count).  
**Output:** `OptimizeResponse` (weights, twin_rejected).  
**Logic (Week 3-4):** Weighted heuristic: RSSI × 0.5 + energy × 0.3 + hop × 0.2 (placeholder → thay bằng công thức thật).  
**Ưu tiên:** Must-have.

### FR-03: Graceful Degradation

**Mô tả:** Gateway phải tiếp tục hoạt động khi cloud không phản hồi.  
**Điều kiện:** Timeout `/optimize` > ngưỡng cấu hình.  
**Hành vi:** Dùng `last_known_weights` đã cache; nếu không có → dùng default `[0.5, 0.3, 0.2]`.  
**Ưu tiên:** Must-have.

### FR-04: Ghi log cloud events

**Mô tả:** Mọi sự kiện trên kênh cloud phải được ghi vào bảng `cloud_events`.  
**Loại sự kiện:** `param_update`, `outage_start`, `outage_end`, `stale_detected`, `twin_rejected`.  
**Ưu tiên:** Must-have.

### FR-05: Endpoint /detect — Phát hiện bất thường

**Mô tả:** Phát hiện các mẫu bất thường trong telemetry (năng lượng cạn đột ngột, RSSI drop).  
**Input:** `TelemetrySnapshot`.  
**Output:** `DetectResponse` (anomaly, reason).  
**Ưu tiên:** Should-have (Week 6, nếu còn thời gian).

### FR-06: Digital-Twin Validation

**Mô tả:** Trước khi trả weights mới, dự đoán hiệu năng. Nếu tệ hơn hiện tại → `twin_rejected = true`.  
**Model:** sklearn regression huấn luyện từ dữ liệu `metrics` trong SQLite.  
**Ưu tiên:** Should-have (Week 6-7).

### FR-07: Mô phỏng NS-3

**Mô tả:** Module simulation phải hỗ trợ 3 cấu hình: `no_cloud`, `local_optimized`, `cloud_assisted`.  
**Mobility:** Row-constrained (không dùng Random Waypoint).  
**Channel:** Mô hình suy hao nhà kính (khung kim loại + tán lá).  
**Output:** Log files CSV với PDR, E2E delay, overhead, energy, cloud_latency.  
**Ưu tiên:** Must-have.

---

## 4. Yêu cầu phi chức năng

### NFR-01: Hiệu năng API

- `/health` phải phản hồi trong < 50 ms.
- `/optimize` phải phản hồi trong < 200 ms với payload tiêu chuẩn.

### NFR-02: Độ tin cậy

- Cloud Service phải xử lý graceful degradation mà không crash.
- Tests phải đạt 100% pass trên CI.

### NFR-03: Khả năng bảo trì

- Code Python phải pass `ruff check` (không có lỗi lint).
- Mỗi module phải có docstring mô tả mục đích.

### NFR-04: Khả năng mở rộng

- Hệ thống phải hoạt động với 6–20 MANET nodes mà không thay đổi kiến trúc.

### NFR-05: Bảo mật (Kịch bản S4)

- Phân tích bề mặt tấn công mới do kênh cloud tạo ra (MITM, replay attack, gateway SPOF).
- Ghi lại trong `docs/testing-report.md`.

---

## 5. Ràng buộc thiết kế

- Ngôn ngữ backend: Python 3.11+, FastAPI.
- Ngôn ngữ simulation: C++ (NS-3 module).
- Database: SQLite (không dùng PostgreSQL để đơn giản hóa setup).
- CI: GitHub Actions.
