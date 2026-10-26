# Software Requirements Specification (SRS)

**Dự án:** MANET Nhà Kính — CAAR · **Môn học:** NT131 · **Nhóm:** 06 · **Phiên bản:** 0.3 (theo tài liệu đồ án bản cập nhật 20/10/2026)

## 1. Phạm vi

CAAR giữ AODV gọn nhẹ trên robot, đưa việc chọn trọng số định tuyến lên Gateway hoặc Cloud,
và tự hạ cấp an toàn khi mất Cloud. Kiểm chứng bằng NS-3 với kênh truyền và quỹ đạo robot lấy
từ số đo trong nhà kính thật.

**Ngoài phạm vi (mục 16):** Digital-Twin, endpoint `/detect`, kịch bản DoS trong mô phỏng,
mô hình suy hao riêng cho kim loại và độ ẩm, bảo mật định tuyến giữa các robot (SAODV),
phần cứng robot thật.

## 2. Giả định

- Mỗi nhà kính 1 ha (100 × 100 m, lối chính ở giữa) có đúng 1 Gateway ở giữa lối chính
  ([`greenhouse-survey.md`](greenhouse-survey.md)).
- Robot chạy trên ray 0,2 m/s, dừng 15–24 s mỗi điểm làm việc (mục 6).
- Kênh log-distance n = 4,63, σ = 5,15 dB (Cama-Pinto et al. 2019, mục 5).
- Kênh Gateway–Cloud (TP.HCM → AWS ap-southeast-1) có RTT hằng số 40 ms
  ([`contracts/README.md`](../contracts/README.md)); mất kết nối mô phỏng riêng bằng khoảng outage.

## 3. Yêu cầu chức năng

| ID | Yêu cầu | Mục | Cài ở |
|---|---|---|---|
| FR-01 | `GET /health` trả `{"status": "ok"}` | 9.2 | `app/main.py` |
| FR-02 | `POST /optimize` nhận `NetworkSnapshot`, trả `weights` + `rule` theo heuristic 3 luật | 7.2, 9.3 | `app/main.py`, `app/heuristic.py` |
| FR-03 | `GET /metrics/summary`: PDR, độ trễ trung bình theo cấu hình và kịch bản | 9.2 | `app/main.py` |
| FR-04 | Ghi `param_update` / `outage_start` / `stale_detected` / `outage_end` vào `cloud_events` | 7.3 | Cloud ghi `param_update`; Gateway trong NS-3 xuất các sự kiện hạ cấp, `import_ns3_results.py` nhập vào SQLite |
| FR-05 | Gateway hạ cấp 3 mức theo TTL; mức 3 dùng bộ cân bằng 0,4/0,3/0,3 | 7.3 | `caar::GatewayState`, dùng trong `caar.cc` |
| FR-06 | Delayed RREQ forwarding: chờ D_max·c_i + U(0, J) trước khi rebroadcast RREQ | 4 | Patch AODV + `caar.cc` |
| FR-07 | 4 cấu hình: no_cloud, local_optimized, gateway_heuristic, cloud_assisted | 10.1 | `caar.cc` |
| FR-08 | Xem mô phỏng bằng NetAnim: vị trí robot, pin, mức hạ cấp của Gateway, gói tin | 13 | `caar.cc --netanim`, `simulation/vm/demo.sh` |

## 4. Yêu cầu phi chức năng

| ID | Yêu cầu |
|---|---|
| NFR-01 | Bảo mật kênh 4 lớp: TLS, API key, miền giá trị, độ mới (mục 8.2) |
| NFR-02 | Bản C++ của heuristic cho kết quả giống hệt bản Python trên `parity_cases.json` |
| NFR-03 | Mỗi điểm dữ liệu chạy 10 seed, báo cáo mean ± CI 95%; cùng seed cho cùng kết quả |
| NFR-04 | CI xanh: ruff + pytest cloud, parity g++, test script, build ns-3.48 và `check_ns3.py` |
| NFR-05 | Khóa bí mật chỉ nằm trong biến môi trường / `.env`, không commit |

## 5. Ràng buộc thiết kế

Python 3.11+ / FastAPI / SQLite; C++17 / ns-3.48 (profile `release`); NetAnim 3.109;
Docker Compose + Caddy trên EC2; GitHub Actions.
