# Hướng dẫn sử dụng

## 1. Chạy Cloud Service

Local:

```bash
cd cloud-service
pip install -r requirements.txt
export CAAR_API_KEY=dev-key        # Windows: set CAAR_API_KEY=dev-key
uvicorn app.main:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/health  # {"status":"ok"}
```

EC2 (mục 13.3): tạo EC2 Ubuntu ở ap-southeast-1, mở cổng 22 (chỉ IP của bạn), 80, 443;
trỏ một tên miền về IP; rồi

```bash
cp deploy/.env.example deploy/.env      # điền CAAR_API_KEY, CAAR_DOMAIN
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
curl https://<tên-miền>/health
```

Tắt instance khi không đo hoặc demo.

## 2. Gọi /optimize

```bash
curl -X POST https://<tên-miền>/optimize \
  -H "Content-Type: application/json" -H "X-API-Key: $CAAR_API_KEY" \
  -d "{\"run_id\": 1, \"timestamp\": $(date +%s), \"nodes\": [
        {\"node_id\": \"r1\", \"rssi_avg\": -72, \"energy_remaining_pct\": 45, \"hop_count\": 2},
        {\"node_id\": \"r2\", \"rssi_avg\": -85, \"energy_remaining_pct\": 12, \"hop_count\": 3}]}"
# {"weights":{"hop_weight":0.2,"rssi_weight":0.3,"energy_weight":0.5},"rule":"low_battery"}
```

`timestamp` phải là thời điểm hiện tại; lệch quá 30 s bị từ chối (400).

## 3. Demo bảo mật (mục 8)

| Thử | Lệnh | Kết quả |
|---|---|---|
| Gọi trái phép | bỏ header `X-API-Key` | 401 |
| Replay | gửi lại body có `timestamp` cũ hơn 30 s | 400 |
| Replay cùng nonce | gửi cùng body có `"nonce": "abc"` hai lần | lần 2: 400 |
| Dữ liệu rác | `"energy_remaining_pct": 150` | 422 |
| Nghe lén | `curl http://<tên-miền>/health` | Caddy chuyển sang HTTPS |

## 4. Đo kênh WAN (mục 13.4)

```bash
export CAAR_API_KEY=...
python scripts/wan_probe.py --url https://<tên-miền>/optimize --interval 2 --hours 24 \
    --out contracts/wan_trace.csv
```

Chạy trên máy ở TP.HCM, không tắt máy hay đổi mạng; ghi lại nhà mạng đã dùng.

## 5. Chạy mô phỏng và phân tích

```bash
NS3_DIR=~/ns-3-dev scripts/run_batch.sh s1 s2a s2b     # tối thiểu để bảo vệ
NS3_DIR=~/ns-3-dev scripts/run_batch.sh s3 sens        # nếu còn thời gian
python scripts/import_ns3_results.py --db results/results.db --wan-trace contracts/wan_trace.csv
python scripts/plot_results.py --db results/results.db --out results/figures
```

`results/figures/hypotheses.md` ghi kết luận Q1–Q3 theo tiêu chí mục 10.5.
Truy vấn SQL mẫu ở mục 13.6 của tài liệu đồ án.

## 6. Sự kiện trong cloud_events

| `event_type` | Ý nghĩa |
|---|---|
| `param_update` | Trọng số mới (Cloud ghi mỗi lần trả lời; Gateway ghi khi áp dụng) |
| `outage_start` | Gateway gọi Cloud lỗi lần đầu, chuyển mức 2 (dùng cache) |
| `stale_detected` | Tuổi cache ≥ TTL, chuyển mức 3 (bộ cân bằng) |
| `outage_end` | Cloud trả lời lại, quay về mức 1 |
