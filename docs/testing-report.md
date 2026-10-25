# Báo cáo kiểm thử

Theo mục 14 của tài liệu đồ án. Cập nhật 22/10/2026.

## Các tầng kiểm thử

| Tầng | Công cụ | Chạy khi | Trạng thái |
|---|---|---|---|
| Unit/API cloud | pytest + TestClient (`cloud-service/tests/`) | CI mỗi push | 34 test pass |
| Parity Python ↔ C++ | `contracts/parity_cases.json` + `simulation/caar-logic/test_caar_logic.cpp` | CI mỗi push | 704 kiểm tra pass |
| Script phân tích | pytest (`scripts/tests/`) | CI mỗi push | 17 test pass |
| Tính đúng mô phỏng | `scripts/check_ns3.py` trên ns-3.48 | CI job `ns3` mỗi push | 6 nhóm kiểm tra pass (Docker, 23/10) |
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

## Kiểm tra tính đúng của mô phỏng (mục 14.3) — `scripts/check_ns3.py`

- [x] w_h = 1: PDR local_optimized nằm trong CI 95% của no_cloud (5 seed).
- [x] Tầm liên kết từ cấu hình radio: 29,35 m với WiFi 20 dBm + anten 3 dBi mỗi đầu, ngưỡng thu −82 dBm (`contracts/channel.json`).
  Đã đổi khỏi mốc 18–20 m của bản tài liệu: cặp 16 dBm / −82 dBm là của radio 802.15.4 đã đo,
  còn robot dùng WiFi (mục 1.1, 5.4). Ở 18 m, với 10 robot chỉ ~19 % thời gian robot có đường
  về Gateway (PDR mô phỏng 0,14–0,23), nên Q1–Q3 gần như không đo được. Ở 29 m là ~82 %.
  Lần đầu đạt tầm này bằng ngưỡng thu −88 dBm, nhưng hạ ngưỡng phát hiện preamble dưới mức
  mặc định −82 dBm làm PHY của ns-3.48 dừng với "Invalid WifiPhy state RX" ở 9/280 run (mạng
  dày; 6/6 run ở −94 dBm). Giờ giữ −82 dBm và đạt cùng ngân sách 108 dB bằng anten 3 dBi ở mỗi
  đầu; cả 9 trường hợp từng crash đều chạy được. `caar` và `fit_channel.py` từ chối ngưỡng < −82 dBm.
- [x] Mọi waypoint nằm trên lối chính hoặc hàng ray, trong nhà kính 1 ha 100 × 100 m
  (`gen_waypoints.validate`, test). Lý do chọn 1 ha: `docs/greenhouse-survey.md`.
- [x] Log mất cloud theo thứ tự outage_start → stale_detected (357 s, TTL 60 s) → outage_end;
  không có param_update trong lúc mất cloud.
- [x] Cùng seed chạy hai lần cho kết quả giống hệt.
- [x] 4 cấu hình chạy được, CSV đúng hợp đồng, nhập được vào SQLite; NetAnim ghi đủ 3 mức Gateway.
- [x] Phép đo cơ chế hợp lệ: mất gói do không có đường ≤ tổng mất gói, số hop ≥ 1,
  RSSI link chở dữ liệu ≥ độ nhạy thu.

## Chạy test

```bash
cd cloud-service && pytest
pytest scripts/tests
cd simulation/caar-logic && g++ -std=c++17 -O2 -o test_caar_logic test_caar_logic.cpp && ./test_caar_logic
```
