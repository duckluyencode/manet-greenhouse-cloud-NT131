# Báo cáo kiểm thử

Theo mục 14 của tài liệu đồ án.

## Các tầng kiểm thử

| Tầng | Công cụ | Chạy khi | Kết quả |
|---|---|---|---|
| Unit/API cloud | pytest + TestClient (`cloud-service/tests/`) | CI mỗi push | 34 test pass |
| Parity Python ↔ C++ | `contracts/parity_cases.json` + `simulation/caar-logic/test_caar_logic.cpp` | CI mỗi push | 704 kiểm tra pass |
| Script phân tích | pytest (`scripts/tests/`) | CI mỗi push | 18 test pass |
| Tính đúng mô phỏng | `scripts/check_ns3.py` trên ns-3.48 | CI job `ns3` mỗi push | 7 nhóm kiểm tra pass |
| Đầu-cuối | HTTPS tới EC2 ap-southeast-1 | Trước demo | 4/4 pass (bảng dưới) |

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
- Tính chất mục 4.3: w_h = 1 cho thời gian chờ như nhau; pin yếu chờ lâu hơn; phương án dự phòng 4.5.
- Độ nhạy của bộ test: đổi `>=` thành `>` ở ngưỡng f_low làm test báo 10 lỗi.

## Tính đúng của mô phỏng (mục 14.3)

| Kiểm tra | Kiểm bằng |
|---|---|
| w_h = 1: PDR local_optimized nằm trong CI 95 % của no_cloud (5 seed) | `check_ns3.py` nhóm 4 |
| Mất cloud: log theo thứ tự outage_start → stale_detected (357 s, TTL 60 s) → outage_end; không có param_update trong lúc mất cloud | `check_ns3.py` nhóm 3 |
| Cùng seed chạy hai lần cho kết quả giống hệt | `check_ns3.py` nhóm 2 |
| 4 cấu hình chạy được, CSV đúng hợp đồng, nhập được vào SQLite | `check_ns3.py` nhóm 1, 5 |
| Phép đo cơ chế hợp lệ: mất gói do không có đường ≤ tổng mất gói, số hop ≥ 1, RSSI link chở dữ liệu ≥ ngưỡng thu | `check_ns3.py` nhóm 1 |
| NetAnim ghi đủ 3 mức Gateway và gói tin | `check_ns3.py` nhóm 6 |
| Hook delayed RREQ có tác dụng: D_max 500 ms làm thời gian tìm đường dài hơn D_max 20 ms (766 → 1.141 ms ở seed 1) | `check_ns3.py` nhóm 7 |
| Tầm liên kết 29,35 m với WiFi 20 dBm, anten 3 dBi mỗi đầu, ngưỡng thu −82 dBm | `contracts/channel.json`, `test_contract_channel_json` |
| Mọi waypoint nằm trên lối chính hoặc hàng ray, trong nhà kính 100 × 100 m | `test_committed_waypoint_files_are_valid` |
| Kết nối hình học: robot có đường về Gateway 31 / 51 / 80 / 90 % thời gian với 6 / 10 / 16 / 20 robot | `scripts/connectivity.py` |

## Đầu-cuối trên AWS

Cloud service trên EC2 t3.micro (ap-southeast-1), HTTPS qua Caddy, gọi từ TP.HCM:

| Kiểm tra | Kết quả |
|---|---|
| `GET /health` | 200 `{"status":"ok"}` |
| `POST /optimize` không có API key | 401 |
| `POST /optimize` có API key | 200, `low_battery`, trọng số 0,2 / 0,3 / 0,5 |
| Timestamp lệch 120 s | 400 |

## Kết quả thí nghiệm

290 run (S1, S2a, S2b, S3, chẩn đoán), mỗi điểm 10 seed; ns-3.48 profile `release`; nhà kính
1 ha; kênh cloud RTT 40 ms. Bảng đầy đủ: `results/figures/hypotheses.md`; biểu đồ trong
`results/figures/`; CSV từng run trong `results/raw/`.

| Câu | Kết quả | Ghi chú |
|---|---|---|
| Q1 | Bác bỏ (p = 0,87) | PDR 0,523 so với 0,518; số hop, RSSI link, tỷ lệ chuyển tiếp của robot yếu pin không đổi |
| Q2a | Bác bỏ (p = 0,98) | Heuristic toàn mạng không thêm lợi ích so với trọng số cố định |
| Q2b | Xác nhận (p = 0,99) | Kênh cloud không lỗi, RTT 40 ms |
| Q3 | Xác nhận | PDR trong khoảng mất cloud 0,59 so với 0,55 của no_cloud |

- Mất gói đổi bản chất theo mật độ (S3): 6 robot/ha mất 42 % vì không có đường; 16–20 robot/ha
  gần như luôn có đường nhưng mất 46–50 % trên link (tranh chấp kênh, flood RREQ/HELLO).
- Ở 20 robot/ha có xu hướng local_optimized cao hơn no_cloud (0,519 so với 0,483, p = 0,125),
  chưa có ý nghĩa thống kê.
- Chẩn đoán: chỉ cho Gateway trả lời RREQ cũng không tạo khác biệt (p = 0,76 và 0,50). Hook
  delayed RREQ có tác dụng: với 10 robot, D_max 500 ms làm thời gian tìm đường tăng từ 724 lên
  1.098 ms (p < 0,001) mà PDR không đổi (0,550 và 0,544). Đường đi trung bình chỉ 1,4–1,7 hop
  nên ít khi có đường thay thế để chọn.

## Chạy test

```bash
cd cloud-service && pytest
pytest scripts/tests
cd simulation/caar-logic && g++ -std=c++17 -O2 -o test_caar_logic test_caar_logic.cpp && ./test_caar_logic
python3 scripts/check_ns3.py --ns3 ~/ns-3-dev --out /tmp/caar-check --seeds 5
```
