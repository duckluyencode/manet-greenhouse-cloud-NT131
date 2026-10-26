# Kiểm chứng giả thuyết (mục 10.5)

Khác nhau có ý nghĩa: CI 95% không chồng nhau hoặc Welch t-test p < 0,05 (mục 10.4).

| Câu | Giả thuyết | A | B | Welch p | Kết luận |
|---|---|---|---|---|---|
| Q1 | PDR local_optimized > no_cloud | local_optimized: 0.5226 ± 0.0418 (n=10) | no_cloud: 0.5181 ± 0.0425 (n=10) | 0.867 | Bác bỏ |
| Q2a | PDR gateway_heuristic > local_optimized | gateway_heuristic: 0.5234 ± 0.0371 (n=10) | local_optimized: 0.5226 ± 0.0418 (n=10) | 0.975 | Bác bỏ |
| Q2b | cloud_assisted ≈ gateway_heuristic | cloud_assisted: 0.5236 ± 0.0374 (n=10) | gateway_heuristic: 0.5234 ± 0.0371 (n=10) | 0.991 | Xác nhận |
| Q3 | Mất cloud: pdr_window cloud_assisted (S2a) không thấp hơn no_cloud (S1) | cloud_assisted S2a: 0.5914 ± 0.0944 (n=10) | no_cloud S1: 0.5482 ± 0.1133 (n=10) | 0.516 | Xác nhận |

Ghi chú: Q3 so sánh PDR của các gói gửi trong cửa sổ mất cloud (params.window_s).
Mọi kết quả, kể cả bác bỏ giả thuyết, được báo cáo trung thực.

## Cơ chế định tuyến — S1 (10 robot, 1 ha)

| Cấu hình | PDR | Mất do không có đường | Số hop | RSSI link chở dữ liệu (dBm) | Chuyển tiếp bởi robot pin < 30 % |
|---|---|---|---|---|---|
| no_cloud | 0.518 ± 0.042 | 0.165 ± 0.035 | 1.48 ± 0.05 | -74.3 ± 0.3 | 0.213 ± 0.090 |
| local_optimized | 0.523 ± 0.042 | 0.186 ± 0.043 | 1.47 ± 0.06 | -74.5 ± 0.2 | 0.208 ± 0.088 |
| gateway_heuristic | 0.523 ± 0.037 | 0.186 ± 0.040 | 1.47 ± 0.04 | -74.5 ± 0.2 | 0.215 ± 0.081 |
| cloud_assisted | 0.524 ± 0.037 | 0.187 ± 0.040 | 1.47 ± 0.04 | -74.5 ± 0.2 | 0.222 ± 0.088 |

## S3 — lợi ích của metric theo mật độ robot

| Robot / 1 ha | PDR no_cloud | PDR local_optimized | Welch p | Mất do không có đường (no_cloud) |
|---|---|---|---|---|
| 6 | 0.392 ± 0.065 | 0.382 ± 0.073 | 0.822 | 0.418 ± 0.078 |
| 10 | 0.518 ± 0.042 | 0.523 ± 0.042 | 0.867 | 0.165 ± 0.035 |
| 16 | 0.501 ± 0.059 | 0.525 ± 0.045 | 0.477 | 0.035 ± 0.009 |
| 20 | 0.483 ± 0.042 | 0.519 ± 0.029 | 0.125 | 0.020 ± 0.006 |

## Chẩn đoán Q1 — chỉ Gateway trả lời RREQ (AODV DestinationOnly)

Giả thuyết kiểm tra: mặc định AODV cho node trung gian đã có đường trả lời RREQ ngay,
nên delayed RREQ ít khi quyết định đường đi. Kịch bản này buộc RREQ phải tới Gateway;
nếu PDR vẫn không khác, giả thuyết bị bác bỏ.

| Robot | Cấu hình | PDR | Số hop | Chuyển tiếp bởi robot pin < 30 % | Thời gian tìm đường (ms) |
|---|---|---|---|---|---|
| 10 | no_cloud | 0.543 ± 0.027 | 1.42 ± 0.03 | 0.221 ± 0.093 | 721 ± 54 |
| 10 | local_optimized | 0.550 ± 0.036 | 1.42 ± 0.04 | 0.202 ± 0.089 | 724 ± 60 |
| 10 | Welch p (PDR) | 0.756 | | | |
| 20 | no_cloud | 0.649 ± 0.035 | 1.67 ± 0.04 | 0.240 ± 0.079 | 413 ± 44 |
| 20 | local_optimized | 0.665 ± 0.039 | 1.68 ± 0.05 | 0.211 ± 0.070 | 433 ± 43 |
| 20 | Welch p (PDR) | 0.499 | | | |

Hook delayed RREQ có tác dụng (10 robot, local_optimized, chỉ Gateway trả lời RREQ): D_max dài hơn thì robot chờ lâu hơn trước khi chuyển tiếp RREQ, nên thời gian tìm đường tăng.

| D_max | Thời gian tìm đường (ms) | PDR |
|---|---|---|
| 20 ms | 724 ± 60 | 0.550 ± 0.036 |
| 500 ms | 1098 ± 54 | 0.544 ± 0.029 |
| Welch p | < 0.001 | |

## Độ nhạy — D_max và tốc độ robot (10 robot)

Welch p so PDR của local_optimized với no_cloud ở S1 (cùng tốc độ 0,2 m/s); ở tốc độ khác
không có no_cloud để so.

| Biến thể | PDR local_optimized | PDR cloud_assisted | Thời gian tìm đường local_optimized (ms) | Welch p (local_optimized so với no_cloud S1) |
|---|---|---|---|---|
| D_max 5 ms | 0.536 ± 0.046 | 0.538 ± 0.049 | 434 ± 28 | 0.535 |
| D_max 10 ms | 0.522 ± 0.040 | 0.521 ± 0.042 | 424 ± 48 | 0.893 |
| D_max 20 ms | 0.523 ± 0.042 | 0.524 ± 0.037 | 433 ± 45 | 0.867 |
| 1 m/s (D_max 20 ms) | 0.549 ± 0.046 | 0.558 ± 0.056 | 454 ± 59 | — |
