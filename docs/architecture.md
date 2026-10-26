# Kiến trúc CAAR

Nguồn: tài liệu đồ án mục 4, 7, 9. Tài liệu này mô tả phần đã cài trong repo.

## 3 tầng

| Tầng | Chạy ở | Vai trò |
|---|---|---|
| Robot | NS-3 (`simulation/scratch/caar.cc`, Owner A) | AODV mở rộng: delayed RREQ forwarding theo chi phí c_i |
| Gateway | NS-3, logic trong `simulation/caar-logic/caar_logic.h` | Gom telemetry, gọi Cloud mỗi T = 5 s, máy trạng thái hạ cấp 3 mức |
| Cloud | FastAPI trên EC2 (`cloud-service/`) | Control plane: chọn 3 trọng số (w_h, w_r, w_e) cho toàn mạng |

Logic chọn đường nằm hoàn toàn ở robot, nên mất cloud thì mạng vẫn chạy.
Dữ liệu cảm biến không đi qua kênh Gateway–Cloud; kênh này chỉ mang telemetry định tuyến.

## Delayed RREQ forwarding (mục 4)

Mỗi node chuyển tiếp chờ `D_i = D_max · c_i + U(0, J)` trước khi rebroadcast RREQ, với

```
r_i = clamp((RSSI_i + 90) / 50, 0, 1)      e_i = pin còn lại / pin ban đầu
c_i = w_h + w_r (1 − r_i) + w_e (1 − e_i)
```

Nhờ duplicate suppression, RREQ đến đích đầu tiên là bản có Σc_i nhỏ nhất. Không đổi
định dạng gói, không đụng sequence number. `caar::BaseForwardDelay()` tính phần
`D_max · c_i`; jitter lấy từ bộ sinh số NS-3 để tái tạo theo seed.

## Luồng mỗi chu kỳ (mục 9.1)

```
Robot ──pin, RSSI──▶ Gateway ──POST /optimize (HTTPS, X-API-Key)──▶ Cloud
                       ▲                                              │
                       └──────── weights + rule ◀──────────────────────┘
Gateway kiểm tra trọng số (≥ 0, tổng = 1) rồi phát cho mọi robot.
Timeout 2 s / lỗi / trọng số sai → hạ cấp.
```

## Heuristic (mục 7.2) — `app/heuristic.py`, `caar::ChooseWeights`

| Điều kiện (luật đúng đầu tiên thắng) | w_h | w_r | w_e | rule |
|---|---|---|---|---|
| `10 × số robot pin < 20% ≥ 3 × số robot` | 0,2 | 0,3 | 0,5 | low_battery |
| `2 × trung vị(RSSI kẹp [−90; −40]) < −150` | 0,3 | 0,5 | 0,2 | poor_signal |
| còn lại | 0,4 | 0,3 | 0,3 | balanced |

Bản Python là chuẩn; bản C++ phải khớp tuyệt đối trên `contracts/parity_cases.json`.

## Graceful degradation (mục 7.3) — `caar::GatewayState`

| Mức | Điều kiện | Gateway dùng | Sự kiện |
|---|---|---|---|
| 1 | Cloud trả lời hợp lệ | trọng số mới | `param_update` (+ `outage_end` nếu vừa phục hồi) |
| 2 | Lỗi, tuổi cache < TTL | trọng số cache | `outage_start` |
| 3 | Lỗi, tuổi cache ≥ TTL (hoặc chưa có cache) | bộ cân bằng 0,4/0,3/0,3 | `stale_detected` |

Tuổi cache tính từ lần cập nhật thành công cuối, chỉ kiểm tra ở mỗi lần gọi Cloud.

## Bảo mật kênh (mục 8.2)

| Lớp | Cài ở |
|---|---|
| TLS | Caddy (`deploy/Caddyfile`), chứng chỉ Let's Encrypt |
| API key | `app/security.py::require_api_key` |
| Miền giá trị | `app/models.py` (Pydantic) và `caar::ValidWeights` ở Gateway |
| Độ mới | `app/security.py::check_freshness` (±30 s, nonce tùy chọn) |

## Dữ liệu (mục 9.4) — `app/db.py`

| Bảng | Cột chính |
|---|---|
| `runs` | id, config_type, scenario, seed, node_count, mobility_speed, params (JSON), created_at |
| `metrics` | run_id, pdr, avg_delay_ms, p95_delay_ms, overhead_ratio, route_discovery_ms, min_energy_pct, cloud_bandwidth_bytes, loss_no_route_ratio, hops_avg, link_rssi_avg_dbm, weak_relay_share |
| `cloud_events` | run_id, ts, event_type, payload |
