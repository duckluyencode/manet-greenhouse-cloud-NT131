"""
Đo kênh Gateway -> Cloud (mục 7.4, 13.4): gọi POST /optimize định kỳ và ghi
ts, rtt_ms, http_status, timeout vào CSV (hợp đồng contracts/wan_trace.csv).

- Gửi NetworkSnapshot hợp lệ (timestamp hiện tại, nonce ngẫu nhiên) kèm
  X-API-Key lấy từ biến môi trường CAAR_API_KEY.
- Giữ kết nối HTTPS (keep-alive) như Gateway thật; lỗi thì mở lại kết nối.
- Timeout 2 s giống Gateway; quá hạn ghi timeout = 1, http_status = 0.
- Lỗi kết nối khác (DNS, TCP reset...) cũng ghi http_status = 0, timeout = 0.
- Gọi theo nhịp cố định (không trôi dần khi RTT lớn).

Chạy trên máy ở TP.HCM, không tắt máy hay đổi mạng trong lúc đo:
    python scripts/wan_probe.py --url https://<tên-miền>/optimize \
        --interval 2 --hours 24 --out results/raw/wan_trace.csv
"""
import argparse
import csv
import http.client
import json
import os
import random
import secrets
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

TIMEOUT_S = 2.0


def make_snapshot(n_nodes: int, rng: random.Random) -> dict:
    """Snapshot giả lập kích thước giống Gateway thật (n robot)."""
    return {
        "run_id": 0,
        "timestamp": time.time(),
        "nonce": secrets.token_hex(16),
        "nodes": [
            {
                "node_id": f"r{i}",
                "rssi_avg": rng.randint(-90, -45),
                "energy_remaining_pct": rng.randint(20, 100),
                "hop_count": rng.randint(1, 4),
            }
            for i in range(1, n_nodes + 1)
        ],
    }


class Prober:
    def __init__(self, url: str, api_key: str, timeout_s: float = TIMEOUT_S) -> None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            raise ValueError("url must start with http:// or https://")
        self.scheme = parts.scheme
        self.host = parts.hostname or ""
        self.port = parts.port
        self.path = parts.path or "/"
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.conn: http.client.HTTPConnection | None = None

    def _connect(self) -> http.client.HTTPConnection:
        cls = http.client.HTTPSConnection if self.scheme == "https" else http.client.HTTPConnection
        return cls(self.host, self.port, timeout=self.timeout_s)

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def probe(self, body: dict) -> tuple[float, int, int]:
        """Gọi một lần; trả (rtt_ms, http_status, timeout)."""
        payload = json.dumps(body).encode()
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
            "Connection": "keep-alive",
        }
        if self.conn is None:
            self.conn = self._connect()
        start = time.perf_counter()
        try:
            self.conn.request("POST", self.path, body=payload, headers=headers)
            resp = self.conn.getresponse()
            resp.read()
            rtt_ms = (time.perf_counter() - start) * 1000
            if resp.getheader("Connection", "").lower() == "close":
                self.close()
            return rtt_ms, resp.status, 0
        except TimeoutError:
            self.close()
            return (time.perf_counter() - start) * 1000, 0, 1
        except (OSError, http.client.HTTPException):
            self.close()
            return (time.perf_counter() - start) * 1000, 0, 0


def run(
    prober: Prober,
    out: Path,
    interval_s: float,
    max_samples: int | None,
    duration_s: float | None,
    n_nodes: int,
) -> int:
    rng = random.Random()
    out.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out.exists() or out.stat().st_size == 0
    count = 0
    stats = {"ok": 0, "timeout": 0, "error": 0}
    start = time.time()
    with out.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["ts", "rtt_ms", "http_status", "timeout"])
        next_tick = time.monotonic()
        while True:
            ts = time.time()
            rtt_ms, status, timed_out = prober.probe(make_snapshot(n_nodes, rng))
            writer.writerow([f"{ts:.3f}", f"{rtt_ms:.2f}", status, timed_out])
            f.flush()
            count += 1
            if timed_out:
                stats["timeout"] += 1
            elif status == 200:
                stats["ok"] += 1
            else:
                stats["error"] += 1
            if count % 100 == 0:
                print(f"{count} samples: {stats}", file=sys.stderr)

            if max_samples is not None and count >= max_samples:
                break
            if duration_s is not None and time.time() - start >= duration_s:
                break
            next_tick += interval_s
            delay = next_tick - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                next_tick = time.monotonic()  # chậm hơn nhịp: bỏ nhịp lỡ, không dồn
    prober.close()
    print(f"done: {count} samples -> {out} {stats}", file=sys.stderr)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Đo RTT/lỗi kênh Gateway -> Cloud")
    parser.add_argument("--url", required=True, help="https://<tên-miền>/optimize")
    parser.add_argument("--interval", type=float, default=2.0, help="giây giữa hai lần gọi")
    parser.add_argument("--hours", type=float, help="thời gian đo (giờ)")
    parser.add_argument("--samples", type=int, help="số lần gọi tối đa (thay cho --hours)")
    parser.add_argument("--nodes", type=int, default=10, help="số robot trong snapshot")
    parser.add_argument("--timeout", type=float, default=TIMEOUT_S)
    parser.add_argument("--out", type=Path, default=Path("results/raw/wan_trace.csv"))
    args = parser.parse_args()

    api_key = os.environ.get("CAAR_API_KEY")
    if not api_key:
        parser.error("set CAAR_API_KEY in the environment")
    if args.hours is None and args.samples is None:
        parser.error("give --hours or --samples")

    prober = Prober(args.url, api_key, args.timeout)
    duration = args.hours * 3600 if args.hours is not None else None
    run(prober, args.out, args.interval, args.samples, duration, args.nodes)


if __name__ == "__main__":
    main()
