# contracts/ — hợp đồng dữ liệu giữa Owner A và Owner B (mục 12.3)

Đổi định dạng file nào phải báo người kia trước. File sinh tự động thì sửa
script sinh, không sửa tay.

| File | Sinh bởi | A dùng để |
|---|---|---|
| `parity_cases.json` | `scripts/gen_parity_cases.py` | Kiểm bản C++ (`simulation/caar-logic/test_caar_logic.cpp`) |
| `channel.json` | `scripts/fit_channel.py` | `LogDistancePropagationLossModel` + `RandomPropagationLossModel` |
| `waypoints/<N>_<seed>[_<tag>].csv` | `scripts/gen_waypoints.py` | `WaypointMobilityModel` |
| `waypoints/layout.json` | `scripts/gen_waypoints.py` | Vị trí Gateway, kích thước nhà kính, hàng ray |
| `wan_trace.csv` | `scripts/wan_probe.py` (đo thật tới AWS) | Độ trễ/lỗi link cloud trong NS-3 |

## parity_cases.json

- `weight_table`: bộ trọng số của 3 luật.
- `heuristic_cases[]`: `nodes` (`rssi_avg`, `energy_remaining_pct`) → `expected`
  (`rule`, 3 trọng số). Ca biên của bảng 14.2 + 200 ca ngẫu nhiên.
- `cost_cases[]`: `weights`, `rssi_avg`, `energy_frac` → `expected_cost` (c_i, mục 4.1).
- `gateway_cases[]`: `ttl_s` và chuỗi `steps` (`t`, `result` = `ok` | `timeout` |
  `invalid`) → `expected_level`, `expected_events`, `expected_weights` (mục 7.3).

## channel.json

`n`, `sigma_db`, `ref_loss_db`, `ref_dist_m` (bắt buộc) và `link_range_m`,
`tx_power_dbm`, `rx_sensitivity_dbm`, `source`. Mặc định dùng n = 4,63,
σ = 5,15 dB như tài liệu ghi; khi đã nhập Bảng 2 của Cama-Pinto (2019) vào CSV
thì chạy lại `fit_channel.py --measurements <csv>` để fit lại. Nhớ thay
`--tx-power` / `--tx-gain` / `--rx-gain` / `--rx-sensitivity` khi đổi radio. Mặc định là
WiFi 20 dBm + anten 3 dBi mỗi đầu, ngưỡng thu −82 dBm (tầm ~29 m); `tx_gain_dbi`, `rx_gain_dbi` không bắt buộc (mặc định 0);
lý do đổi khỏi 16 / −82 dBm ghi ở `docs/testing-report.md` (mục 14.3).

## waypoints/

Cột `node_id, t_s, x_m, y_m`; `node_id` = 1..N (robot `r<node_id>`), Gateway
không có trong file (vị trí cố định trong `layout.json`: (50; 50)). Nhà kính 1 ha
(100 × 100 m), lối chính ở giữa, 112 hàng ray hai phía; lý do và nguồn số liệu ở
`docs/greenhouse-survey.md`. Một lần
dừng là hai dòng liên tiếp cùng tọa độ. Quỹ đạo kéo dài ít nhất 900 s.

Có sẵn: N ∈ {6, 10, 16, 20} × seed 1..10 (tham số mặc định), và `10_<seed>_v1.csv`
(ray và lối chính 1 m/s) cho kịch bản độ nhạy tốc độ.

## wan_trace.csv

`ts, rtt_ms, http_status, timeout` — chưa có, chờ đo 24 giờ trên EC2
(`scripts/wan_probe.py`, mục 13.4). `timeout = 1` khi quá 2 s; `http_status = 0`
khi không nhận được phản hồi.

## Kết quả mô phỏng (A xuất, B nhập)

`results/raw/<config>_<scenario>[_<biến thể>]_<seed>.csv`, một dòng, cột:

```
config_type,scenario,seed,node_count,mobility_speed,params,
pdr,avg_delay_ms,p95_delay_ms,overhead_ratio,route_discovery_ms,min_energy_pct,cloud_bandwidth_bytes,
loss_no_route_ratio,hops_avg,link_rssi_avg_dbm,weak_relay_share
```

4 cột cuối đo cơ chế định tuyến (có thể trống ở kết quả cũ):

| Cột | Ý nghĩa |
|---|---|
| `loss_no_route_ratio` | Gói dữ liệu bị bỏ vì không có / mất đường (AODV tìm đường thất bại) ÷ gói gửi. Phần mất còn lại `1 − pdr − loss_no_route_ratio` là mất trên link |
| `hops_avg` | Số hop trung bình của gói tới Gateway (từ TTL) |
| `link_rssi_avg_dbm` | RSSI trung bình các link đã chở dữ liệu (khung unicast nhận thành công) |
| `weak_relay_share` | Tỷ lệ lượt chuyển tiếp gói dữ liệu do robot đang có pin < 30 % |

- `config_type`: `no_cloud` | `local_optimized` | `gateway_heuristic` | `cloud_assisted`
- `scenario`: `baseline` (S1) | `outage` (S2a) | `stale` (S2b) | `scale` (S3) | `sensitivity`
- `params`: chuỗi JSON, tối thiểu `{"dmax_ms": 20, "ttl_s": 60}`, thêm
  `outage_start_s`, `outage_end_s` khi có. `plot_results.py` đọc `ttl_s` và `dmax_ms` từ đây.
- `mobility_speed`: tốc độ trên ray (m/s).

Tùy chọn: `<cùng tên>_events.csv` với cột `ts, event_type, payload` (log Gateway).

`import_ns3_results.py` đọc thông tin run từ nội dung file, tên file chỉ để không trùng.

## Chương trình NS-3 `caar`

`simulation/scratch/caar.cc` (cài bằng `simulation/install.sh`) đọc các file trên và ghi
đúng định dạng kết quả ở mục trước. `params` do `caar` ghi gồm `dmax_ms`, `jitter_ms`,
`ttl_s`, `period_s`, `outage_start_s`/`outage_end_s` (khi có), `wan_model`
(`none` | `constant` | `trace`), `window_s` và `pdr_window` (PDR của gói gửi trong cửa sổ,
mặc định 300–600 s, dùng cho Q3). Danh sách tham số dòng lệnh: `simulation/README.md`.
