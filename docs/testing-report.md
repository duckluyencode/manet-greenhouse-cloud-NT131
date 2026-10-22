# Báo cáo kiểm thử

Theo mục 14 của tài liệu đồ án. Cập nhật 22/10/2026.

## Các tầng kiểm thử

| Tầng | Công cụ | Chạy khi | Trạng thái |
|---|---|---|---|
| Unit/API cloud | pytest + TestClient (`cloud-service/tests/`) | CI mỗi push | 34 test pass |
| Parity Python ↔ C++ | `contracts/parity_cases.json` + `simulation/caar-logic/test_caar_logic.cpp` | CI mỗi push | 704 kiểm tra pass |
| Script phân tích | pytest (`scripts/tests/`) | CI mỗi push | 17 test pass |
| Tính đúng mô phỏng | NS-3 (Owner A) | Thủ công | Chưa có |
| Đầu-cuối | curl, Swagger trên AWS | Trước demo | Chưa có (chưa deploy EC2) |

## Test case cloud (bảng 14.2) — `tests/test_api.py`

| Test | Đầu vào | Kỳ vọng | Test |
|---|---|---|---|
| Snapshot hợp lệ | 2 node hợp lệ | 200, có weights, rule | `test_valid_snapshot` |
| Pin ngoài miền | energy = 150 | 422 | `test_invalid_node_rejected[energy_150]` |
| Danh sách rỗng | nodes = [] | 422 | `test_empty_nodes_rejected` |
| Hop không hợp lệ | hop_count = 0 | 422 | `test_invalid_node_rejected[hop_0]` |
| node_id là số | "node_id": 1 | 422 | `test_invalid_node_rejected[node_id_int]` |
| Ngưỡng f_low | 10 robot, 3 pin < 20% | low_battery | `test_heuristic_rules[f_low_threshold]` |
| Pin đúng 20% | 3 robot 20%, 7 robot 80% | balanced | `test_heuristic_rules[energy_exactly_20]` |
| Thứ tự luật | 2/4 pin 10%, RSSI −85 | low_battery | `test_heuristic_rules[rule_order]` |
| Trung vị chẵn | RSSI −85, −80, −75, −60 | poor_signal | `test_heuristic_rules[even_median]` |
| Kẹp RSSI | RSSI −100 và −60 | balanced | `test_heuristic_rules[rssi_clamp]` |
| Bình thường | pin và sóng tốt | balanced 0,4/0,3/0,3 | `test_heuristic_rules[normal]` |
| Tổng trọng số | mọi trường hợp trên | tổng = 1, ≥ 0 | `assert_weights_valid` trong mỗi test |
| Thiếu API key | không header | 401 | `test_missing_api_key` |
| Timestamp cũ | lệch > 30 s | 400 | `test_stale_or_future_timestamp` |
| Parity C++ | toàn bộ parity_cases.json | cùng rule, trọng số | `test_caar_logic.cpp` |

Thêm: sai key (401), server chưa cấu hình key (503), nonce gửi lại (400), nonce tùy chọn,
`/metrics/summary` và ghi `param_update` vào `cloud_events`.

## Parity C++ — `simulation/caar-logic/test_caar_logic.cpp`

- 215 ca heuristic (15 ca biên viết tay + 200 ngẫu nhiên, nửa RSSI nguyên, nửa số thực).
- 24 ca chi phí c_i (sai số 1e-12).
- 5 kịch bản máy trạng thái Gateway, gồm ví dụ mục 7.3 (TTL 300 s, stale ở giây 595).
- Kiểm tra tính chất mục 4.3: w_h = 1 cho thời gian chờ như nhau; pin yếu chờ lâu hơn;
  phương án dự phòng 4.5.

Đã thử đổi `>=` thành `>` ở ngưỡng f_low: test báo 10 lỗi, tức bộ test bắt được sai lệch này.

## Kiểm tra tính đúng của mô phỏng (mục 14.3) — việc của Owner A

- [ ] w_h = 1: PDR local_optimized nằm trong CI của no_cloud.
- [ ] Tầm liên kết từ cấu hình radio cỡ 18–20 m (`contracts/channel.json`: 17,85 m với 16 dBm / −82 dBm).
- [x] Mọi waypoint nằm trên lối chính hoặc hàng ray, trong 100 × 50 m (`gen_waypoints.validate`, test).
- [ ] Log mất cloud theo thứ tự outage_start → stale_detected → outage_end.
- [ ] Cùng seed chạy hai lần cho kết quả giống hệt.

## Chạy test

```bash
cd cloud-service && pytest
pytest scripts/tests
cd simulation/caar-logic && g++ -std=c++17 -O2 -o test_caar_logic test_caar_logic.cpp && ./test_caar_logic
```
