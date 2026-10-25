// Parity test: bản C++ phải cho cùng kết quả với bản Python trên
// contracts/parity_cases.json (sinh bởi scripts/gen_parity_cases.py).
//
// Build và chạy (không cần NS-3):
//   g++ -std=c++17 -O2 -Wall -Wextra -o test_caar_logic test_caar_logic.cpp
//   ./test_caar_logic ../../contracts/parity_cases.json
#include "caar_logic.h"

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <map>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

// --- JSON tối giản, đủ cho parity_cases.json (không cần thư viện ngoài) ---

struct Json {
  enum Type { kNull, kBool, kNumber, kString, kArray, kObject } type = kNull;
  bool b = false;
  double num = 0;
  std::string str;
  std::vector<Json> arr;
  std::map<std::string, Json> obj;

  const Json& operator[](const std::string& key) const {
    auto it = obj.find(key);
    if (type != kObject || it == obj.end()) throw std::runtime_error("missing key: " + key);
    return it->second;
  }
  bool Has(const std::string& key) const { return type == kObject && obj.count(key) > 0; }
};

class Parser {
 public:
  explicit Parser(const std::string& s) : s_(s) {}

  Json Parse() {
    Json v = Value();
    Ws();
    if (i_ != s_.size()) Fail("trailing data");
    return v;
  }

 private:
  [[noreturn]] void Fail(const std::string& msg) {
    throw std::runtime_error("JSON parse error at " + std::to_string(i_) + ": " + msg);
  }
  void Ws() {
    while (i_ < s_.size() && (s_[i_] == ' ' || s_[i_] == '\n' || s_[i_] == '\r' || s_[i_] == '\t')) ++i_;
  }
  bool Eat(char c) {
    Ws();
    if (i_ < s_.size() && s_[i_] == c) { ++i_; return true; }
    return false;
  }
  void Expect(char c) { if (!Eat(c)) Fail(std::string("expected ") + c); }

  Json Value() {
    Ws();
    if (i_ >= s_.size()) Fail("unexpected end");
    char c = s_[i_];
    Json v;
    if (c == '{') {
      ++i_;
      v.type = Json::kObject;
      if (Eat('}')) return v;
      do {
        Ws();
        std::string key = String();
        Expect(':');
        v.obj[key] = Value();
      } while (Eat(','));
      Expect('}');
    } else if (c == '[') {
      ++i_;
      v.type = Json::kArray;
      if (Eat(']')) return v;
      do { v.arr.push_back(Value()); } while (Eat(','));
      Expect(']');
    } else if (c == '"') {
      v.type = Json::kString;
      v.str = String();
    } else if (s_.compare(i_, 4, "true") == 0) {
      i_ += 4; v.type = Json::kBool; v.b = true;
    } else if (s_.compare(i_, 5, "false") == 0) {
      i_ += 5; v.type = Json::kBool;
    } else if (s_.compare(i_, 4, "null") == 0) {
      i_ += 4;
    } else {
      size_t end = i_;
      while (end < s_.size() && std::string("+-0123456789.eE").find(s_[end]) != std::string::npos) ++end;
      if (end == i_) Fail("unexpected character");
      v.type = Json::kNumber;
      // strtod đọc số thập phân về double gần nhất, giống json.loads của Python.
      v.num = std::strtod(s_.substr(i_, end - i_).c_str(), nullptr);
      i_ = end;
    }
    return v;
  }

  std::string String() {
    if (i_ >= s_.size() || s_[i_] != '"') Fail("expected string");
    ++i_;
    std::string out;
    while (i_ < s_.size() && s_[i_] != '"') {
      char c = s_[i_++];
      if (c == '\\') {
        char e = s_[i_++];
        switch (e) {
          case 'n': out += '\n'; break;
          case 't': out += '\t'; break;
          case 'u': i_ += 4; out += '?'; break;  // không cần unicode escape cho test
          default: out += e;
        }
      } else {
        out += c;
      }
    }
    ++i_;
    return out;
  }

  const std::string& s_;
  size_t i_ = 0;
};

// --- Test harness ---

int g_failures = 0;
int g_checks = 0;

void Check(bool ok, const std::string& what) {
  ++g_checks;
  if (!ok) {
    ++g_failures;
    std::fprintf(stderr, "FAIL: %s\n", what.c_str());
  }
}

caar::Weights WeightsFromJson(const Json& j) {
  return {j["hop_weight"].num, j["rssi_weight"].num, j["energy_weight"].num};
}

bool SameWeights(const caar::Weights& a, const caar::Weights& b) {
  // Trọng số là hằng trong bảng nên phải khớp tuyệt đối.
  return a.hop == b.hop && a.rssi == b.rssi && a.energy == b.energy;
}

caar::Weights RuleWeights(const Json& table, const std::string& rule) {
  return WeightsFromJson(table[rule]);
}

void RunHeuristicCases(const Json& root) {
  for (const Json& c : root["heuristic_cases"].arr) {
    std::vector<caar::NodeSample> nodes;
    for (const Json& n : c["nodes"].arr) {
      nodes.push_back({n["rssi_avg"].num, n["energy_remaining_pct"].num});
    }
    caar::Decision d = caar::ChooseWeights(nodes);
    const Json& exp = c["expected"];
    const std::string name = c["name"].str;
    Check(exp["rule"].str == caar::RuleName(d.rule),
          name + ": rule " + caar::RuleName(d.rule) + " != " + exp["rule"].str);
    Check(SameWeights(d.weights, WeightsFromJson(exp)), name + ": weights differ");
  }
}

void RunCostCases(const Json& root) {
  for (const Json& c : root["cost_cases"].arr) {
    caar::Weights w = WeightsFromJson(c["weights"]);
    double cost = caar::NodeCost(w, c["rssi_avg"].num, c["energy_frac"].num);
    double expected = c["expected_cost"].num;
    Check(std::fabs(cost - expected) <= 1e-12,
          c["name"].str + ": cost " + std::to_string(cost) + " != " + std::to_string(expected));
  }
}

void RunGatewayCases(const Json& root) {
  const Json& table = root["weight_table"];
  for (const Json& c : root["gateway_cases"].arr) {
    caar::GatewayState gw(c["ttl_s"].num);
    for (const Json& step : c["steps"].arr) {
      const double t = step["t"].num;
      const std::string& result = step["result"].str;
      std::vector<std::string> events;
      if (result == "ok") {
        events = gw.OnReply(t, RuleWeights(table, step["weights"].str));
      } else if (result == "invalid") {
        events = gw.OnReply(t, caar::Weights{0.5, 0.3, 0.3});  // tổng 1.1
      } else {
        events = gw.OnFailure(t);
      }

      const std::string where = c["name"].str + " @t=" + std::to_string(static_cast<int>(t));
      std::vector<std::string> expected_events;
      for (const Json& e : step["expected_events"].arr) expected_events.push_back(e.str);
      Check(events == expected_events, where + ": events differ");
      Check(static_cast<int>(gw.level()) == static_cast<int>(step["expected_level"].num),
            where + ": level " + std::to_string(static_cast<int>(gw.level())));
      Check(SameWeights(gw.Active(), WeightsFromJson(step["expected_weights"])),
            where + ": active weights differ");
    }
  }
}

// Các tính chất của mục 4.3 không nằm trong file JSON.
void RunPropertyChecks() {
  // w_h = 1: mọi node có cùng thời gian chờ -> hành vi AODV gốc.
  caar::Weights hop_only{1.0, 0.0, 0.0};
  Check(caar::BaseForwardDelay(0.02, hop_only, -40, 1.0) ==
            caar::BaseForwardDelay(0.02, hop_only, -90, 0.0),
        "w_h = 1 must give equal delays");
  // w_e lớn: node pin yếu chờ lâu hơn node pin khỏe.
  caar::Weights energy_heavy{0.2, 0.3, 0.5};
  Check(caar::BaseForwardDelay(0.02, energy_heavy, -60, 0.1) >
            caar::BaseForwardDelay(0.02, energy_heavy, -60, 0.9),
        "weak battery must wait longer");
  // Thời gian chờ không vượt D_max và mỗi hop tốn ít nhất w_h * D_max.
  caar::Weights balanced = caar::BalancedWeights();
  double worst = caar::BaseForwardDelay(0.02, balanced, -120, 0.0);
  double best = caar::BaseForwardDelay(0.02, balanced, -20, 1.0);
  Check(worst <= 0.02 + 1e-15, "delay must not exceed D_max");
  Check(std::fabs(best - 0.02 * balanced.hop) <= 1e-15, "best delay must be w_h * D_max");
  // Phương án dự phòng mục 4.5.
  Check(!caar::FallbackShouldForward(0.19, false), "fallback: weak relay must not forward");
  Check(caar::FallbackShouldForward(0.19, true), "fallback: destination always answers");
  Check(caar::FallbackShouldForward(0.2, false), "fallback: 20% still forwards");
}

}  // namespace

int main(int argc, char** argv) {
  const char* path = argc > 1 ? argv[1] : "../../contracts/parity_cases.json";
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    std::fprintf(stderr, "cannot open %s\n", path);
    return 2;
  }
  std::stringstream buf;
  buf << in.rdbuf();
  const std::string text = buf.str();

  try {
    Json root = Parser(text).Parse();
    RunHeuristicCases(root);
    RunCostCases(root);
    RunGatewayCases(root);
    RunPropertyChecks();
  } catch (const std::exception& e) {
    std::fprintf(stderr, "error: %s\n", e.what());
    return 2;
  }

  std::printf("%d checks, %d failures\n", g_checks, g_failures);
  return g_failures == 0 ? 0 : 1;
}
