"""Test các script của Owner B (không cần NS-3, không cần mạng ngoài)."""
import csv
import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

import caar_stats
import connectivity
import fit_channel
import gen_waypoints

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parent


# --- caar_stats -------------------------------------------------------------

def test_t_quantile_matches_table() -> None:
    # Mục 10.4: n = 10 -> t_{0.975, 9} = 2,262.
    assert caar_stats.t_quantile(0.975, 9) == pytest.approx(2.262, abs=1e-3)
    assert caar_stats.t_quantile(0.975, 1) == pytest.approx(12.706, abs=1e-3)
    assert caar_stats.t_quantile(0.975, 1000) == pytest.approx(1.962, abs=1e-3)


def test_two_sided_p_value() -> None:
    assert caar_stats.t_sf_two_sided(2.262, 9) == pytest.approx(0.05, abs=1e-4)
    assert caar_stats.t_sf_two_sided(0.0, 5) == pytest.approx(1.0)


def test_summarize_ci() -> None:
    s = caar_stats.summarize([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert s.mean == 5.5
    assert s.ci_half == pytest.approx(2.262 * s.sd / math.sqrt(10), rel=1e-3)


def test_welch_equal_variance_reduces_to_student() -> None:
    # Cùng n, cùng phương sai: Welch trùng Student t, df = 2n - 2.
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [x + 2.5 for x in a]
    r = caar_stats.welch_t_test(a, b)
    s = caar_stats.summarize(a)
    expected_t = -2.5 / math.sqrt(2 * s.sd**2 / 5)
    assert r.t == pytest.approx(expected_t)
    assert r.df == pytest.approx(8)
    assert r.p == pytest.approx(caar_stats.t_sf_two_sided(expected_t, 8))
    assert caar_stats.welch_t_test(b, a).t == pytest.approx(-r.t)


def test_significance_rule() -> None:
    assert caar_stats.significantly_different([0.9] * 5 + [0.91] * 5, [0.7] * 5 + [0.71] * 5)
    assert not caar_stats.significantly_different([0.8, 0.9, 0.85, 0.82], [0.81, 0.88, 0.86, 0.83])


# --- fit_channel ------------------------------------------------------------

def test_friis_reference_loss() -> None:
    assert fit_channel.friis_loss_db(2.4e9) == pytest.approx(40.05, abs=0.01)


def test_fit_recovers_exponent() -> None:
    rng = random.Random(1)
    d = [2.6 + 0.5 * i for i in range(40)]
    pl = [40 + 10 * 4.6 * math.log10(x) + rng.gauss(0, 0.5) for x in d]
    n, sigma = fit_channel.fit_log_distance(d, pl)
    assert n == pytest.approx(4.6, abs=0.15)
    assert sigma == pytest.approx(0.5, abs=0.2)


def test_link_range_section_5_4() -> None:
    # 16 dBm, -82 dBm, n = 4,63 -> khoảng 18 m (mục 5.4).
    assert fit_channel.link_range_m(16, -82, 40.05, 4.63) == pytest.approx(17.85, abs=0.05)


def test_contract_channel_json() -> None:
    channel = json.loads((ROOT / "contracts" / "channel.json").read_text(encoding="utf-8"))
    assert {"n", "sigma_db", "ref_loss_db", "ref_dist_m"} <= set(channel)
    # Radio WiFi 20 dBm + anten 3 dBi mỗi đầu, ngưỡng -82 dBm: tầm cỡ vài chục mét (mục 1.1), ~29 m.
    assert 25 <= channel["link_range_m"] <= 35
    assert channel["rx_sensitivity_dbm"] >= fit_channel.MIN_RX_SENSITIVITY_DBM


# --- gen_waypoints ----------------------------------------------------------

def test_rail_strips_cover_all_rails() -> None:
    for n in (6, 10, 16, 20):
        strips = gen_waypoints.rail_strips(n)
        assert sorted(i for s in strips for i in s) == list(range(gen_waypoints.RAIL_COUNT))
        assert max(map(len, strips)) - min(map(len, strips)) <= 1


@pytest.mark.parametrize("n", [6, 20])
def test_tracks_valid_and_reproducible(n) -> None:
    p = gen_waypoints.Params()
    tracks = gen_waypoints.generate(n, 3, p)
    gen_waypoints.validate(tracks, p)
    again = gen_waypoints.generate(n, 3, p)
    assert {k: v.points for k, v in tracks.items()} == {k: v.points for k, v in again.items()}


def test_stops_last_15_to_24_seconds() -> None:
    p = gen_waypoints.Params()
    track = gen_waypoints.generate(10, 1, p)[1]
    stops = [
        b[0] - a[0]
        for a, b in zip(track.points, track.points[1:])
        if (a[1], a[2]) == (b[1], b[2])
    ]
    assert stops
    assert all(15 <= s <= 24 for s in stops)


def test_rail_speed_is_respected() -> None:
    p = gen_waypoints.Params()
    track = gen_waypoints.generate(10, 2, p)[1]
    for a, b in zip(track.points, track.points[1:]):
        dist = math.hypot(b[1] - a[1], b[2] - a[2])
        # Đoạn trên ray: cùng x, hai đầu cùng một phía và không vào trong lối chính.
        da, db = a[2] - gen_waypoints.AISLE_Y, b[2] - gen_waypoints.AISLE_Y
        half = gen_waypoints.AISLE_WIDTH / 2 - 1e-9
        on_rail = a[1] == b[1] and da * db > 0 and min(abs(da), abs(db)) >= half
        if dist > 0 and on_rail:
            assert dist / (b[0] - a[0]) == pytest.approx(p.rail_speed)


def test_committed_waypoint_files_are_valid() -> None:
    files = sorted((ROOT / "contracts" / "waypoints").glob("*_*.csv"))
    assert len(files) >= 40
    for path in files:
        with path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            assert gen_waypoints.on_layout(float(r["x_m"]), float(r["y_m"])), path.name


# --- connectivity -------------------------------------------------------------

def test_connectivity_counts_multi_hop_paths() -> None:
    # Gateway (0, 0), tầm 10 m: r1 cách 8 m, r2 nối qua r1, r3 ở xa.
    tracks = {1: [(0.0, 8.0, 0.0)], 2: [(0.0, 16.0, 0.0)], 3: [(0.0, 40.0, 0.0)]}
    assert connectivity.connectivity(tracks, (0.0, 0.0), 10.0, duration_s=5) == pytest.approx(2 / 3)


def test_connectivity_interpolates_between_waypoints() -> None:
    # Robot đi từ x = 5 tới x = 25 trong 10 s: còn trong tầm 10 m khi t <= 2,5 s.
    tracks = {1: [(0.0, 5.0, 0.0), (10.0, 25.0, 0.0)]}
    assert connectivity.connectivity(tracks, (0.0, 0.0), 10.0, duration_s=10) == pytest.approx(0.3)


# --- import + plot ------------------------------------------------------------

def _write_result(path: Path, config, scenario, seed, pdr, params) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "config_type", "scenario", "seed", "node_count", "mobility_speed", "params",
            "pdr", "avg_delay_ms", "p95_delay_ms", "overhead_ratio", "route_discovery_ms",
            "min_energy_pct", "cloud_bandwidth_bytes",
            "loss_no_route_ratio", "hops_avg", "link_rssi_avg_dbm", "weak_relay_share",
        ])
        w.writerow([config, scenario, seed, 10, 0.2, json.dumps(params),
                    pdr, 12.0, 30.0, 0.1, 45.0, 22.0, 1000, 0.05, 1.8, -70.0, 0.1])


def test_import_and_plot_pipeline(tmp_path) -> None:
    """Dữ liệu tổng hợp chỉ để kiểm tra pipeline, không phải kết quả mô phỏng."""
    raw = tmp_path / "raw"
    raw.mkdir()
    rng = random.Random(0)
    base_pdr = {"no_cloud": 0.80, "local_optimized": 0.86,
                "gateway_heuristic": 0.88, "cloud_assisted": 0.88}
    for seed in range(1, 11):
        for config, mean in base_pdr.items():
            _write_result(raw / f"{config}_baseline_{seed}.csv", config, "baseline", seed,
                          round(mean + rng.uniform(-0.01, 0.01), 4), {"dmax_ms": 20, "ttl_s": 60})
        _write_result(raw / f"cloud_assisted_outage_{seed}.csv", "cloud_assisted", "outage", seed,
                      0.85, {"dmax_ms": 20, "ttl_s": 60, "outage_start_s": 300})
        for ttl in (15, 60, 300):
            _write_result(raw / f"cloud_assisted_stale_ttl{ttl}_{seed}.csv", "cloud_assisted",
                          "stale", seed, 0.85, {"dmax_ms": 20, "ttl_s": ttl})
    (raw / "cloud_assisted_outage_1_events.csv").write_text(
        "ts,event_type,payload\n300,outage_start,\n360,stale_detected,\n600,outage_end,\n",
        encoding="utf-8",
    )

    db_path = tmp_path / "results.db"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    cmd = [sys.executable, str(SCRIPTS / "import_ns3_results.py"), "--raw", str(raw), "--db", str(db_path)]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env).stdout
    assert "80 imported" in out
    # Nhập lại không tạo bản trùng.
    out = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env).stdout
    assert "0 imported, 80 already" in out

    figs = tmp_path / "figures"
    subprocess.run(
        [sys.executable, str(SCRIPTS / "plot_results.py"), "--db", str(db_path), "--out", str(figs)],
        capture_output=True, text=True, check=True, env=env,
    )
    assert (figs / "s1_pdr.png").stat().st_size > 0
    assert (figs / "s2b_pdr_vs_ttl.png").exists()
    hyp = (figs / "hypotheses.md").read_text(encoding="utf-8")
    assert "| Q1 |" in hyp and "Xác nhận" in hyp
    with (figs / "summary.csv").open(encoding="utf-8") as f:
        assert any(r["scenario"] == "baseline" for r in csv.DictReader(f))
