// CAAR logic — C++ thuần, không phụ thuộc NS-3 (Owner B).
//
// Gồm 3 phần, mỗi phần khớp với một mục của tài liệu đồ án:
//   1. Heuristic chọn trọng số toàn mạng (mục 7.2) — bản sao của
//      cloud-service/app/heuristic.py; parity kiểm bằng contracts/parity_cases.json.
//   2. Chi phí node c_i và thời gian chờ cơ sở D_max * c_i (mục 4.1, 4.2).
//      Jitter U(0, J) KHÔNG nằm ở đây: scratch/caar.cc lấy từ bộ sinh số của
//      NS-3 để giữ tái tạo theo seed.
//   3. Máy trạng thái Gateway 3 mức + TTL (mục 7.3).
//
// Cách dùng trong NS-3: #include "caar_logic.h" (header-only, C++17).
#ifndef CAAR_LOGIC_H
#define CAAR_LOGIC_H

#include <algorithm>
#include <cmath>
#include <limits>
#include <string>
#include <vector>

namespace caar {

// ---------------------------------------------------------------------------
// Trọng số và heuristic (mục 7.2)
// ---------------------------------------------------------------------------

struct Weights {
  double hop = 0.4;
  double rssi = 0.3;
  double energy = 0.3;
};

constexpr double kWeightSumTolerance = 0.001;

// Kiểm tra trọng số Gateway nhận từ Cloud: mỗi giá trị >= 0, tổng = 1 (sai số 0.001).
inline bool ValidWeights(const Weights& w) {
  if (!std::isfinite(w.hop) || !std::isfinite(w.rssi) || !std::isfinite(w.energy)) {
    return false;
  }
  if (w.hop < 0 || w.rssi < 0 || w.energy < 0) return false;
  return std::fabs(w.hop + w.rssi + w.energy - 1.0) <= kWeightSumTolerance;
}

enum class Rule { kLowBattery, kPoorSignal, kBalanced };

inline const char* RuleName(Rule r) {
  switch (r) {
    case Rule::kLowBattery: return "low_battery";
    case Rule::kPoorSignal: return "poor_signal";
    case Rule::kBalanced:   return "balanced";
  }
  return "balanced";
}

inline Weights WeightsFor(Rule r) {
  switch (r) {
    case Rule::kLowBattery: return {0.2, 0.3, 0.5};
    case Rule::kPoorSignal: return {0.3, 0.5, 0.2};
    case Rule::kBalanced:   return {0.4, 0.3, 0.3};
  }
  return {0.4, 0.3, 0.3};
}

// Bộ cân bằng: trọng số cố định của local_optimized và mức hạ cấp 3.
inline Weights BalancedWeights() { return WeightsFor(Rule::kBalanced); }

struct NodeSample {
  double rssi_avg;              // dBm
  double energy_remaining_pct;  // 0..100
};

struct Decision {
  Rule rule;
  Weights weights;
};

constexpr double kLowBatteryPct = 20.0;
constexpr double kRssiMinDbm = -90.0;
constexpr double kRssiMaxDbm = -40.0;
constexpr double kPoorSignalTwiceMedianDbm = -150.0;

inline double ClampRssi(double rssi_dbm) {
  return std::min(kRssiMaxDbm, std::max(kRssiMinDbm, rssi_dbm));
}

// 2 × trung vị; số phần tử chẵn thì là tổng hai giá trị giữa (không chia 2).
inline double TwiceMedian(std::vector<double> values) {
  std::sort(values.begin(), values.end());
  const size_t mid = values.size() / 2;
  if (values.size() % 2 == 1) return 2.0 * values[mid];
  return values[mid - 1] + values[mid];
}

// Luật đúng đầu tiên thắng: pin -> sóng -> cân bằng. So sánh trong miền
// số nguyên và dBm để khớp tuyệt đối với bản Python (quy ước 6, mục 7.2).
inline Decision ChooseWeights(const std::vector<NodeSample>& nodes) {
  Rule rule = Rule::kBalanced;
  if (!nodes.empty()) {
    long weak = 0;
    std::vector<double> rssi;
    rssi.reserve(nodes.size());
    for (const NodeSample& n : nodes) {
      if (n.energy_remaining_pct < kLowBatteryPct) ++weak;
      rssi.push_back(ClampRssi(n.rssi_avg));
    }
    const long total = static_cast<long>(nodes.size());
    if (10 * weak >= 3 * total) {
      rule = Rule::kLowBattery;
    } else if (TwiceMedian(rssi) < kPoorSignalTwiceMedianDbm) {
      rule = Rule::kPoorSignal;
    }
  }
  return {rule, WeightsFor(rule)};
}

// ---------------------------------------------------------------------------
// Chi phí node và thời gian chờ rebroadcast RREQ (mục 4.1, 4.2)
// ---------------------------------------------------------------------------

// r_i = min(1, max(0, (RSSI + 90) / 50))
inline double NormalizeRssi(double rssi_dbm) {
  return std::min(1.0, std::max(0.0, (rssi_dbm + 90.0) / 50.0));
}

// c_i = w_h + w_r (1 - r_i) + w_e (1 - e_i), e_i = pin còn lại / pin ban đầu.
inline double NodeCost(const Weights& w, double rssi_dbm, double energy_frac) {
  const double r = NormalizeRssi(rssi_dbm);
  const double e = std::min(1.0, std::max(0.0, energy_frac));
  return w.hop + w.rssi * (1.0 - r) + w.energy * (1.0 - e);
}

// Phần tất định của D_i = D_max * c_i + U(0, J); cộng jitter ở phía NS-3.
inline double BaseForwardDelay(double dmax_s, const Weights& w, double rssi_dbm,
                               double energy_frac) {
  return dmax_s * NodeCost(w, rssi_dbm, energy_frac);
}

// Phương án dự phòng (mục 4.5): node pin < 20% không rebroadcast RREQ,
// trừ khi chính nó là đích.
inline bool FallbackShouldForward(double energy_frac, bool is_destination) {
  return is_destination || energy_frac >= 0.2;
}

// ---------------------------------------------------------------------------
// Máy trạng thái Gateway (mục 7.3)
// ---------------------------------------------------------------------------

enum class Level { kNormal = 1, kShortOutage = 2, kStale = 3 };

// Tên sự kiện giống cột event_type của bảng cloud_events.
constexpr const char* kParamUpdate = "param_update";
constexpr const char* kOutageStart = "outage_start";
constexpr const char* kStaleDetected = "stale_detected";
constexpr const char* kOutageEnd = "outage_end";

// Gateway gọi Cloud mỗi T giây; mỗi lần gọi kết thúc bằng OnReply (Cloud trả
// trọng số) hoặc OnFailure (timeout / lỗi). Tuổi cache tính từ lần cập nhật
// thành công cuối, và chỉ được kiểm tra ở mỗi lần gọi; tuổi >= TTL -> mức 3.
class GatewayState {
 public:
  explicit GatewayState(double ttl_s) : ttl_s_(ttl_s) {}

  // Cloud trả lời. Trọng số sai miền bị coi như lỗi.
  std::vector<std::string> OnReply(double now_s, const Weights& w) {
    if (!ValidWeights(w)) return OnFailure(now_s);
    std::vector<std::string> events;
    if (level_ != Level::kNormal) events.emplace_back(kOutageEnd);
    events.emplace_back(kParamUpdate);
    level_ = Level::kNormal;
    cache_ = w;
    has_cache_ = true;
    last_success_s_ = now_s;
    return events;
  }

  // Timeout hoặc lỗi khi gọi Cloud.
  std::vector<std::string> OnFailure(double now_s) {
    std::vector<std::string> events;
    if (level_ == Level::kNormal) {
      events.emplace_back(kOutageStart);
      level_ = Level::kShortOutage;
    }
    if (level_ == Level::kShortOutage && CacheAge(now_s) >= ttl_s_) {
      events.emplace_back(kStaleDetected);
      level_ = Level::kStale;
    }
    return events;
  }

  // Trọng số Gateway phát cho robot: cache ở mức 1–2, bộ cân bằng ở mức 3
  // hoặc khi chưa từng nhận được trọng số.
  Weights Active() const {
    if (level_ != Level::kStale && has_cache_) return cache_;
    return BalancedWeights();
  }

  Level level() const { return level_; }
  double ttl_s() const { return ttl_s_; }

  double CacheAge(double now_s) const {
    if (!has_cache_) return std::numeric_limits<double>::infinity();
    return now_s - last_success_s_;
  }

 private:
  double ttl_s_;
  Level level_ = Level::kNormal;
  Weights cache_{};
  bool has_cache_ = false;
  double last_success_s_ = 0.0;
};

}  // namespace caar

#endif  // CAAR_LOGIC_H
