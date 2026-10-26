# contracts/ — dữ liệu đầu vào và định dạng kết quả (mục 12.3)

Đổi định dạng file nào phải báo người kia trong nhóm trước. File sinh tự động thì sửa script
sinh, không sửa tay.

| File | Sinh bởi | Dùng để |
|---|---|---|
| `parity_cases.json` | `scripts/gen_parity_cases.py` | Kiểm bản C++ (`simulation/caar-logic/test_caar_logic.cpp`) |
| `channel.json` | `scripts/fit_channel.py` | Kênh truyền trong `caar` |
| `waypoints/<N>_<seed>[_<tag>].csv` | `scripts/gen_waypoints.py` | Quỹ đạo robot (`WaypointMobilityModel`) |
| `waypoints/layout.json` | `scripts/gen_waypoints.py` | Kích thước nhà kính, hàng ray, vị trí Gateway |

## parity_cases.json

- `weight_table`: bộ trọng số của 3 luật.
- `heuristic_cases[]`: `nodes` (`rssi_avg`, `energy_remaining_pct`) → `expected` (`rule`,
  3 trọng số). Ca biên của bảng 14.2 + 200 ca ngẫu nhiên.
- `cost_cases[]`: `weights`, `rssi_avg`, `energy_frac` → `expected_cost` (c_i, mục 4.1).
- `gateway_cases[]`: `ttl_s` và chuỗi `steps` (`t`, `result` = `ok` | `timeout` | `invalid`)
  → `expected_level`, `expected_events`, `expected_weights` (mục 7.3).

## channel.json

| Trường | Giá trị | Ý nghĩa |
|---|---|---|
| `n`, `sigma_db` | 4,63; 5,15 dB | Số mũ suy hao và độ lệch shadowing, anten 0,5 m (Cama-Pinto et al. 2019, mục 5.3) |
| `ref_loss_db`, `ref_dist_m` | 40,05 dB; 1 m | Suy hao tham chiếu theo Friis ở 2,4 GHz |
| `tx_power_dbm` | 20 | Công suất phát WiFi của robot |
| `tx_gain_dbi`, `rx_gain_dbi` | 3; 3 | Anten omni (không bắt buộc, mặc định 0) |
| `rx_sensitivity_dbm` | −82 | Ngưỡng thu, bằng ngưỡng phát hiện preamble mặc định của ns-3 |
| `link_range_m` | 29,35 | Tầm liên kết suy ra (ngân sách 108 dB) |

Có bảng số đo (cột `distance_m, path_loss_db`) thì chạy `fit_channel.py --measurements <csv>`
để fit lại `n`, `sigma_db`. `fit_channel.py` từ chối ngưỡng thu dưới −82 dBm (PHY của ns-3.48
có lúc dừng với "Invalid WifiPhy state RX").

## waypoints/

Cột `node_id, t_s, x_m, y_m`; `node_id` = 1..N (robot `r<node_id>`). Gateway không có trong file,
vị trí cố định trong `layout.json`: (50; 50). Nhà kính 1 ha (100 × 100 m), lối chính ở giữa,
112 hàng ray hai phía (nguồn số liệu: `docs/greenhouse-survey.md`). Một lần dừng là hai dòng
liên tiếp cùng tọa độ. Quỹ đạo kéo dài ít nhất 900 s.

Có sẵn: N ∈ {6, 10, 16, 20} × seed 1..10 (ray 0,2 m/s), và `10_<seed>_v1.csv` (1 m/s) cho kịch
bản độ nhạy tốc độ.

## Kênh Gateway–Cloud

`caar` mô phỏng mỗi lần gọi Cloud bằng RTT hằng số 40 ms (`--wan-rtt-ms`), không lỗi; mất kết
nối được mô phỏng riêng bằng `--outage-start` / `--outage-end`. Cơ sở cho 40 ms (TP.HCM → AWS
Singapore):

| Nguồn | RTT |
|---|---|
| Ước tính của nhà cung cấp hosting tại Singapore cho khách ở TP.HCM ([MintServers](https://mintservers.com/locations/singapore), [Space-Node](https://space-node.net/blog/minecraft-server-hosting-vietnam-2026), [Nodecraft](https://nodecraft.com/locations/singapore-game-server-hosting)) | 25–50 ms |
| 10 lần `POST /optimize` qua HTTPS từ TP.HCM tới EC2 ap-southeast-1, gồm TLS và xử lý trên server (26/10/2026) | 60–230 ms, trung bình 78 ms |

Các giá trị này rất nhỏ so với chu kỳ gọi Cloud T = 5 s và timeout 2 s.

## Kết quả mô phỏng

`results/raw/<config>_<scenario>[_<biến thể>]_<seed>.csv`, một dòng, cột:

```
config_type,scenario,seed,node_count,mobility_speed,params,
pdr,avg_delay_ms,p95_delay_ms,overhead_ratio,route_discovery_ms,min_energy_pct,cloud_bandwidth_bytes,
loss_no_route_ratio,hops_avg,link_rssi_avg_dbm,weak_relay_share
```

| Cột | Ý nghĩa |
|---|---|
| `config_type` | `no_cloud` \| `local_optimized` \| `gateway_heuristic` \| `cloud_assisted` |
| `scenario` | `baseline` (S1) \| `outage` (S2a) \| `stale` (S2b) \| `scale` (S3) \| `sensitivity` \| `destonly` (chẩn đoán) |
| `mobility_speed` | Tốc độ trên ray (m/s) |
| `params` | JSON: `dmax_ms`, `jitter_ms`, `ttl_s`, `period_s`, `outage_start_s`/`outage_end_s` (khi có), `destination_only`, `fixed_weights`, `wan_model`, `window_s`, `pdr_window` (PDR của gói gửi trong cửa sổ, mặc định 300–600 s, dùng cho Q3) |
| `loss_no_route_ratio` | Gói dữ liệu bị bỏ vì không có / mất đường ÷ gói gửi; `1 − pdr − loss_no_route_ratio` là mất trên link |
| `hops_avg` | Số hop trung bình của gói tới Gateway (từ TTL) |
| `link_rssi_avg_dbm` | RSSI trung bình các link đã chở dữ liệu |
| `weak_relay_share` | Tỷ lệ lượt chuyển tiếp gói dữ liệu do robot có pin < 30 % |

Kèm theo (cấu hình có Gateway): `<cùng tên>_events.csv` với cột `ts, event_type, payload`.
`import_ns3_results.py` đọc thông tin run từ nội dung file; tên file chỉ để không trùng.
Tham số dòng lệnh của `caar`: `simulation/README.md`.
