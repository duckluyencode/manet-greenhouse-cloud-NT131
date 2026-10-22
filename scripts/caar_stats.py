"""
Thống kê cho mục 10.4, không cần scipy:
- khoảng tin cậy 95%: x̄ ± t_{0.975, n-1} · s / √n
- Welch t-test hai phía.

Phân phối Student t tính qua hàm beta không đầy đủ chính quy hóa
(liên phân số Lentz, Numerical Recipes §6.4).
"""
import math
from dataclasses import dataclass


def _betacf(a: float, b: float, x: float) -> float:
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Hàm beta không đầy đủ chính quy hóa I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    ln_front = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log1p(-x)
    )
    front = math.exp(ln_front)
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_sf_two_sided(t: float, df: float) -> float:
    """P(|T| >= |t|) với T ~ Student t bậc tự do df."""
    return betainc(df / 2, 0.5, df / (df + t * t))


def t_quantile(p: float, df: float) -> float:
    """Phân vị t_p (p > 0.5) bằng chia đôi trên hàm phân phối."""
    target = 2 * (1 - p)  # xác suất hai phía tương ứng
    lo, hi = 0.0, 1e3
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_sf_two_sided(mid, df) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


@dataclass(frozen=True)
class Summary:
    n: int
    mean: float
    sd: float
    ci_half: float  # nửa độ rộng khoảng tin cậy 95%

    @property
    def low(self) -> float:
        return self.mean - self.ci_half

    @property
    def high(self) -> float:
        return self.mean + self.ci_half


def summarize(values: list[float]) -> Summary:
    n = len(values)
    if n == 0:
        raise ValueError("no values")
    mean = sum(values) / n
    if n == 1:
        return Summary(1, mean, 0.0, float("nan"))
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
    return Summary(n, mean, sd, t_quantile(0.975, n - 1) * sd / math.sqrt(n))


@dataclass(frozen=True)
class WelchResult:
    t: float
    df: float
    p: float


def welch_t_test(a: list[float], b: list[float]) -> WelchResult:
    """Welch t-test hai phía cho hai mẫu độc lập (phương sai có thể khác nhau)."""
    sa, sb = summarize(a), summarize(b)
    va, vb = sa.sd**2 / sa.n, sb.sd**2 / sb.n
    if va + vb == 0:
        # Hai mẫu đều hằng số: khác giá trị là khác hẳn, trùng là không khác.
        same = sa.mean == sb.mean
        return WelchResult(0.0 if same else math.inf, float(sa.n + sb.n - 2), 1.0 if same else 0.0)
    t = (sa.mean - sb.mean) / math.sqrt(va + vb)
    df = (va + vb) ** 2 / (va**2 / (sa.n - 1) + vb**2 / (sb.n - 1))
    return WelchResult(t, df, t_sf_two_sided(t, df))


def significantly_different(a: list[float], b: list[float], alpha: float = 0.05) -> bool:
    """Tiêu chí mục 10.4: CI 95% không chồng nhau hoặc Welch p < alpha."""
    sa, sb = summarize(a), summarize(b)
    disjoint = sa.high < sb.low or sb.high < sa.low
    return disjoint or welch_t_test(a, b).p < alpha
