"""
Biểu đồ mean ± CI 95% và kết luận giả thuyết Q1–Q3 (mục 10.3–10.5).

Đọc SQLite do import_ns3_results.py tạo, ghi vào results/figures/:
- s1_<metric>.png      : S1, so sánh 4 cấu hình theo từng metric
- s2b_pdr_vs_ttl.png   : S2b, PDR theo TTL
- s3_<metric>.png      : S3, metric theo số robot
- sens_pdr_vs_dmax.png : độ nhạy theo D_max
- summary.csv          : mean, CI cho mọi (kịch bản, cấu hình, biến)
- hypotheses.md        : Q1, Q2a, Q2b, Q3 theo tiêu chí mục 10.5

Kịch bản thiếu dữ liệu thì bỏ qua biểu đồ đó.

Chạy: python scripts/plot_results.py --db results/results.db --out results/figures
"""
import argparse
import csv
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from caar_stats import significantly_different, summarize, welch_t_test  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

CONFIGS = ["no_cloud", "local_optimized", "gateway_heuristic", "cloud_assisted"]
# Màu theo thực thể (cấu hình), thứ tự cố định — 4 slot đầu của bảng màu phân loại.
COLORS = {
    "no_cloud": "#2a78d6",
    "local_optimized": "#eb6834",
    "gateway_heuristic": "#1baf7a",
    "cloud_assisted": "#eda100",
}
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_MUTED = "#52514e"
GRID = "#e4e3df"

METRICS = {
    "pdr": ("PDR", ""),
    "avg_delay_ms": ("Độ trễ trung bình", "ms"),
    "p95_delay_ms": ("Độ trễ p95", "ms"),
    "overhead_ratio": ("Overhead", "tỷ lệ"),
    "route_discovery_ms": ("Độ trễ tìm đường", "ms"),
    "min_energy_pct": ("Pin thấp nhất cuối run", "%"),
    "cloud_bandwidth_bytes": ("Băng thông cloud", "byte"),
    "loss_no_route_ratio": ("Mất gói do không có đường", "tỷ lệ"),
    "hops_avg": ("Số hop trung bình", "hop"),
    "link_rssi_avg_dbm": ("RSSI link chở dữ liệu", "dBm"),
    "weak_relay_share": ("Chuyển tiếp bởi robot pin < 30 %", "tỷ lệ"),
}


def load_runs(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT r.*, m.* FROM runs r JOIN metrics m ON r.id = m.run_id"
    ).fetchall()
    conn.close()
    runs = []
    for row in rows:
        d = dict(row)
        d["params"] = json.loads(d["params"] or "{}")
        runs.append(d)
    return runs


def values(runs: list[dict], metric: str, **where) -> list[float]:
    out = []
    for r in runs:
        matches = all(
            (r["params"].get(k[2:]) if k.startswith("p_") else r[k]) == v for k, v in where.items()
        )
        if matches and r[metric] is not None:
            out.append(float(r[metric]))
    return out


def style_axes(ax, title: str, ylabel: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, color=TEXT, loc="left", fontsize=12)
    ax.set_ylabel(ylabel, color=TEXT_MUTED)
    ax.tick_params(colors=TEXT_MUTED)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)


def new_figure():
    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    return fig, ax


def label_for(metric: str) -> tuple[str, str]:
    name, unit = METRICS[metric]
    return name, f"{name} ({unit})" if unit else name


def bar_chart(runs, scenario, metric, out: Path, summary_rows) -> bool:
    data = {c: values(runs, metric, scenario=scenario, config_type=c) for c in CONFIGS}
    data = {c: v for c, v in data.items() if v}
    if not data:
        return False
    fig, ax = new_figure()
    name, ylabel = label_for(metric)
    for i, (config, vals) in enumerate(data.items()):
        s = summarize(vals)
        summary_rows.append([scenario, config, "", metric, s.n, s.mean, s.ci_half])
        ax.bar(i, s.mean, width=0.6, color=COLORS[config], edgecolor=SURFACE, linewidth=2)
        if s.n > 1:
            ax.errorbar(i, s.mean, yerr=s.ci_half, color=TEXT, capsize=4, linewidth=1.2)
        ax.annotate(f"{s.mean:.3g}", (i, s.mean), xytext=(0, 6), textcoords="offset points",
                    ha="center", va="bottom", color=TEXT_MUTED, fontsize=8)
    ax.set_xticks(range(len(data)), list(data), color=TEXT_MUTED)
    n_per = ", ".join(str(len(v)) for v in data.values())
    style_axes(ax, f"S1 – {name} theo cấu hình (mean ± CI 95%, n = {n_per})", ylabel)
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    return True


def line_chart(runs, scenario, metric, xkey, xlabel, configs, title, out: Path, summary_rows) -> bool:
    """xkey: tên cột của runs, hoặc 'p_<khóa>' để lấy từ params."""
    def xval(r):
        return r["params"].get(xkey[2:]) if xkey.startswith("p_") else r[xkey]

    series = {}
    for config in configs:
        xs = sorted({xval(r) for r in runs if r["scenario"] == scenario
                     and r["config_type"] == config and xval(r) is not None})
        points = []
        for x in xs:
            vals = values(runs, metric, scenario=scenario, config_type=config, **{xkey: x})
            if vals:
                s = summarize(vals)
                points.append((x, s))
                summary_rows.append([scenario, config, f"{xkey}={x}", metric, s.n, s.mean, s.ci_half])
        if points:
            series[config] = points
    if not series:
        return False
    fig, ax = new_figure()
    _, ylabel = label_for(metric)
    for config, points in series.items():
        xs = [p[0] for p in points]
        means = [p[1].mean for p in points]
        errs = [p[1].ci_half if p[1].n > 1 else 0 for p in points]
        ax.errorbar(xs, means, yerr=errs, color=COLORS[config], linewidth=2, marker="o",
                    markersize=6, markeredgecolor=SURFACE, markeredgewidth=2, capsize=3, label=config)
    ax.set_xlabel(xlabel, color=TEXT_MUTED)
    style_axes(ax, f"{title} (mean ± CI 95%)", ylabel)
    if len(series) > 1:
        ax.legend(frameon=False, labelcolor=TEXT_MUTED, fontsize=8)
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    return True


# Phần của tổng: giao được / mất vì không có đường / mất trên link (gồm cả va chạm, hàng đợi).
LOSS_PARTS = [
    ("Giao tới Gateway", "#008300"),
    ("Mất: không có đường", "#e87ba4"),
    ("Mất trên link", "#6250d6"),
]


def loss_breakdown_chart(runs, groups, title, out: Path) -> bool:
    """Cột chồng 100 %: mỗi nhóm là (nhãn, điều kiện lọc runs)."""
    labels, parts = [], []
    for label, where in groups:
        pdr = values(runs, "pdr", **where)
        no_route = values(runs, "loss_no_route_ratio", **where)
        if not pdr or len(no_route) != len(pdr):
            continue
        p, nr = summarize(pdr).mean, summarize(no_route).mean
        labels.append(label)
        parts.append((p, nr, max(0.0, 1 - p - nr)))
    if not labels:
        return False
    fig, ax = new_figure()
    bottoms = [0.0] * len(labels)
    for k, (name, color) in enumerate(LOSS_PARTS):
        heights = [part[k] for part in parts]
        ax.bar(range(len(labels)), heights, bottom=bottoms, width=0.6, color=color,
               edgecolor=SURFACE, linewidth=2, label=name)
        for i, h in enumerate(heights):
            if h >= 0.06:
                ax.text(i, bottoms[i] + h / 2, f"{h:.0%}", ha="center", va="center",
                        color=SURFACE, fontsize=8)
        bottoms = [b + h for b, h in zip(bottoms, heights)]
    ax.set_xticks(range(len(labels)), labels, color=TEXT_MUTED)
    ax.set_ylim(0, 1)
    style_axes(ax, title, "Tỷ lệ gói gửi")
    ax.legend(frameon=False, labelcolor=TEXT_MUTED, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.12), ncol=3)
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    return True


def verdict_line(qid, claim, a_name, a, b_name, b, expect) -> str:
    """expect: 'greater' (a > b có ý nghĩa), 'not_lower' (a không thấp hơn b), 'same'."""
    if not a or not b:
        return f"| {qid} | {claim} | thiếu dữ liệu | | | |"
    sa, sb = summarize(a), summarize(b)
    w = welch_t_test(a, b) if sa.n > 1 and sb.n > 1 else None
    diff = significantly_different(a, b) if w else False
    if expect == "greater":
        ok = diff and sa.mean > sb.mean
    elif expect == "not_lower":
        ok = not (diff and sa.mean < sb.mean)
    else:
        ok = not diff
    p = f"{w.p:.3g}" if w else "—"
    return (
        f"| {qid} | {claim} | {a_name}: {sa.mean:.4f} ± {sa.ci_half:.4f} (n={sa.n}) | "
        f"{b_name}: {sb.mean:.4f} ± {sb.ci_half:.4f} (n={sb.n}) | {p} | "
        f"{'Xác nhận' if ok else 'Bác bỏ'} |"
    )


def hypotheses(runs) -> str:
    def pdr(scenario, config):
        return values(runs, "pdr", scenario=scenario, config_type=config)

    def pdr_window(scenario, config):
        return [float(r["params"]["pdr_window"]) for r in runs
                if r["scenario"] == scenario and r["config_type"] == config
                and r["params"].get("pdr_window") is not None]

    # Q3 xét PDR trong khoảng mất cloud; caar.cc ghi số này vào params.pdr_window.
    if pdr_window("outage", "cloud_assisted") and pdr_window("baseline", "no_cloud"):
        q3, q3_metric = pdr_window, "pdr_window"
        q3_note = "PDR của các gói gửi trong cửa sổ mất cloud (params.window_s)"
    else:
        q3, q3_metric = pdr, "PDR"
        q3_note = "PDR của cả run vì kết quả không có params.pdr_window"

    lines = [
        "# Kiểm chứng giả thuyết (mục 10.5)",
        "",
        "Khác nhau có ý nghĩa: CI 95% không chồng nhau hoặc Welch t-test p < 0,05 (mục 10.4).",
        "",
        "| Câu | Giả thuyết | A | B | Welch p | Kết luận |",
        "|---|---|---|---|---|---|",
        verdict_line("Q1", "PDR local_optimized > no_cloud", "local_optimized",
                     pdr("baseline", "local_optimized"), "no_cloud", pdr("baseline", "no_cloud"), "greater"),
        verdict_line("Q2a", "PDR gateway_heuristic > local_optimized", "gateway_heuristic",
                     pdr("baseline", "gateway_heuristic"), "local_optimized",
                     pdr("baseline", "local_optimized"), "greater"),
        verdict_line("Q2b", "cloud_assisted ≈ gateway_heuristic", "cloud_assisted",
                     pdr("baseline", "cloud_assisted"), "gateway_heuristic",
                     pdr("baseline", "gateway_heuristic"), "same"),
        verdict_line(
            "Q3", f"Mất cloud: {q3_metric} cloud_assisted (S2a) không thấp hơn no_cloud (S1)",
            "cloud_assisted S2a", q3("outage", "cloud_assisted"),
            "no_cloud S1", q3("baseline", "no_cloud"), "not_lower",
        ),
        "",
        f"Ghi chú: Q3 so sánh {q3_note}.",
        "Mọi kết quả, kể cả bác bỏ giả thuyết, được báo cáo trung thực.",
    ]
    lines += mechanism_section(runs)
    return "\n".join(lines) + "\n"


def _cell(vals: list[float], fmt: str = ".3f") -> str:
    if not vals:
        return "—"
    s = summarize(vals)
    ci = "" if s.n < 2 else f" ± {s.ci_half:{fmt}}"
    return f"{s.mean:{fmt}}{ci}"


def _p(a: list[float], b: list[float]) -> str:
    return f"{welch_t_test(a, b).p:.3f}" if len(a) > 1 and len(b) > 1 else "—"


def mechanism_section(runs) -> list[str]:
    """Bằng chứng cơ chế: gói mất vì đâu, đường đi ra sao, ai chuyển tiếp (S1, S3, chẩn đoán)."""
    cols = [("pdr", ".3f"), ("loss_no_route_ratio", ".3f"), ("hops_avg", ".2f"),
            ("link_rssi_avg_dbm", ".1f"), ("weak_relay_share", ".3f")]
    out = [
        "",
        "## Cơ chế định tuyến — S1 (10 robot, 1 ha)",
        "",
        "| Cấu hình | PDR | Mất do không có đường | Số hop | RSSI link chở dữ liệu (dBm) "
        "| Chuyển tiếp bởi robot pin < 30 % |",
        "|---|---|---|---|---|---|",
    ]
    for config in CONFIGS:
        cells = [_cell(values(runs, c, scenario="baseline", config_type=config), f) for c, f in cols]
        if any(c != "—" for c in cells):
            out.append(f"| {config} | " + " | ".join(cells) + " |")

    scale_ns = sorted({r["node_count"] for r in runs if r["scenario"] == "scale"})
    if scale_ns:
        out += [
            "",
            "## S3 — lợi ích của metric theo mật độ robot",
            "",
            "| Robot / 1 ha | PDR no_cloud | PDR local_optimized | Welch p | Mất do không có đường (no_cloud) |",
            "|---|---|---|---|---|",
        ]
        for n in scale_ns:
            a = values(runs, "pdr", scenario="scale", config_type="no_cloud", node_count=n)
            b = values(runs, "pdr", scenario="scale", config_type="local_optimized", node_count=n)
            nr = values(runs, "loss_no_route_ratio", scenario="scale", config_type="no_cloud", node_count=n)
            out.append(f"| {n} | {_cell(a)} | {_cell(b)} | {_p(b, a)} | {_cell(nr)} |")

    diag_ns = sorted({r["node_count"] for r in runs if r["scenario"] == "destonly"})
    if diag_ns:
        out += [
            "",
            "## Chẩn đoán Q1 — chỉ Gateway trả lời RREQ (AODV DestinationOnly)",
            "",
            "Giả thuyết kiểm tra: mặc định AODV cho node trung gian đã có đường trả lời RREQ ngay,",
            "nên delayed RREQ ít khi quyết định đường đi. Kịch bản này buộc RREQ phải tới Gateway;",
            "nếu PDR vẫn không khác, giả thuyết bị bác bỏ.",
            "",
            "| Robot | Cấu hình | PDR | Số hop | Chuyển tiếp bởi robot pin < 30 % | Thời gian tìm đường (ms) |",
            "|---|---|---|---|---|---|",
        ]
        for n in diag_ns:
            for config in ("no_cloud", "local_optimized"):
                w = {"scenario": "destonly", "config_type": config, "node_count": n}
                out.append(
                    f"| {n} | {config} | {_cell(values(runs, 'pdr', **w))} | "
                    f"{_cell(values(runs, 'hops_avg', **w), '.2f')} | "
                    f"{_cell(values(runs, 'weak_relay_share', **w))} | "
                    f"{_cell(values(runs, 'route_discovery_ms', **w), '.0f')} |"
                )
            a = values(runs, "pdr", scenario="destonly", config_type="no_cloud", node_count=n)
            b = values(runs, "pdr", scenario="destonly", config_type="local_optimized", node_count=n)
            out.append(f"| {n} | Welch p (PDR) | {_p(b, a)} | | | |")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Biểu đồ mean ± CI 95% và kiểm chứng giả thuyết")
    parser.add_argument("--db", type=Path, default=ROOT / "results" / "results.db")
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "figures")
    args = parser.parse_args()

    runs = load_runs(args.db)
    if not runs:
        raise SystemExit(f"no runs in {args.db}")
    args.out.mkdir(parents=True, exist_ok=True)
    summary_rows: list[list] = []
    made: list[str] = []

    for metric in METRICS:
        if bar_chart(runs, "baseline", metric, args.out / f"s1_{metric}.png", summary_rows):
            made.append(f"s1_{metric}.png")
    if line_chart(runs, "stale", "pdr", "p_ttl_s", "TTL (s)", ["cloud_assisted"],
                  "S2b – PDR theo TTL", args.out / "s2b_pdr_vs_ttl.png", summary_rows):
        made.append("s2b_pdr_vs_ttl.png")
    if loss_breakdown_chart(runs, [(c, {"scenario": "baseline", "config_type": c}) for c in CONFIGS],
                            "S1 – Gói tin đi đâu (trung bình 10 seed)", args.out / "s1_loss_breakdown.png"):
        made.append("s1_loss_breakdown.png")
    if loss_breakdown_chart(runs, [(f"{n} robot", {"scenario": "scale", "config_type": "no_cloud",
                                                   "node_count": n}) for n in (6, 10, 16, 20)],
                            "S3 – Gói tin đi đâu theo số robot (AODV gốc)",
                            args.out / "s3_loss_breakdown.png"):
        made.append("s3_loss_breakdown.png")
    for metric in ("pdr", "cloud_bandwidth_bytes", "loss_no_route_ratio", "hops_avg", "weak_relay_share"):
        name, _ = METRICS[metric]
        if line_chart(runs, "scale", metric, "node_count", "Số robot", CONFIGS,
                      f"S3 – {name} theo số robot", args.out / f"s3_{metric}.png", summary_rows):
            made.append(f"s3_{metric}.png")
    if line_chart(runs, "sensitivity", "pdr", "p_dmax_ms", "D_max (ms)",
                  ["local_optimized", "cloud_assisted"], "Độ nhạy – PDR theo D_max",
                  args.out / "sens_pdr_vs_dmax.png", summary_rows):
        made.append("sens_pdr_vs_dmax.png")

    with (args.out / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "config_type", "variable", "metric", "n", "mean", "ci95_half"])
        w.writerows(summary_rows)
    (args.out / "hypotheses.md").write_text(hypotheses(runs), encoding="utf-8")

    by_scenario = defaultdict(int)
    for r in runs:
        by_scenario[r["scenario"]] += 1
    print(f"runs per scenario: {dict(by_scenario)}")
    print(f"figures: {', '.join(made) or 'none'}")
    print(f"wrote {args.out / 'summary.csv'} and {args.out / 'hypotheses.md'}")


if __name__ == "__main__":
    main()
