// CAAR — kịch bản NS-3 cho 4 cấu hình (tài liệu đồ án mục 4–7, 10).
//
//   no_cloud           AODV gốc (jitter U(0, 10) ms khi rebroadcast RREQ)
//   local_optimized    delayed RREQ forwarding, trọng số cố định 0,4 / 0,3 / 0,3
//   gateway_heuristic  Gateway tự chạy heuristic mục 7.2 mỗi T giây, không qua WAN
//   cloud_assisted     Cloud chạy heuristic mỗi T giây; kênh WAN theo trace đo thật,
//                      Gateway hạ cấp 3 mức + TTL khi lỗi (mục 7.3)
//
// Cài vào ns-3.48 bằng simulation/install.sh (áp patch AODV và chép vào scratch/caar/).
//   ./ns3 run "caar --config=cloud_assisted --seed=1 --nodes=10
//       --waypoints=contracts/waypoints/10_1.csv --channel=contracts/channel.json
//       --wan-trace=contracts/wan_trace.csv --out=results/raw/cloud_assisted_baseline_1.csv"
//
// Đầu ra: một dòng CSV theo hợp đồng contracts/README.md, và <out>_events.csv với
// log Gateway (param_update, outage_start, stale_detected, outage_end).
//
// Mô hình hóa:
// - Node 0 là Gateway (vị trí cố định trong layout.json), robot là node 1..N.
// - Mỗi robot gửi UDP 128 B mỗi giây tới Gateway. Gói mang pin và RSSI trung bình
//   của robot, nên Gateway dựng NetworkSnapshot từ gói nhận được (robot báo telemetry).
// - RSSI theo từng hàng xóm: trung bình trượt (EWMA) trên trace MonitorSnifferRx.
// - Pin: biến theo node, hao hằng số khi di chuyển và một lượng nhỏ mỗi gói IP phát.
// - Trọng số Gateway nhận được áp dụng ngay cho mọi robot (không mô phỏng gói phát lại).
//
// Hiển thị: --netanim=<file.xml> ghi trace NetAnim (mở bằng trình xem NetAnim). Robot đổi
// màu theo pin (xanh -> đỏ), Gateway đổi màu theo mức hạ cấp (xanh dương / cam / đỏ).
#include "caar_logic.h"

#include "ns3/aodv-helper.h"
#include "ns3/aodv-routing-protocol.h"
#include "ns3/core-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/netanim-module.h"
#include "ns3/network-module.h"
#include "ns3/propagation-module.h"
#include "ns3/wifi-module.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("Caar");

namespace
{

// ---------------------------------------------------------------------------
// Tham số và trạng thái toàn cục của một run
// ---------------------------------------------------------------------------

enum class SimConfig
{
    kNoCloud,
    kLocalOptimized,
    kGatewayHeuristic,
    kCloudAssisted
};

constexpr uint16_t kDataPort = 9;
constexpr uint16_t kAodvPort = 654;
constexpr uint32_t kPayloadBytes = 128;
constexpr double kRssiEwmaAlpha = 0.1;
// Liên kết không nghe thấy trong khoảng này coi như không còn (cho RSSI telemetry).
constexpr double kRssiFreshSeconds = 10.0;
// RSSI dùng khi chưa từng nghe thấy hàng xóm: biên dưới của chuẩn hóa (r = 0).
constexpr double kUnknownRssiDbm = -90.0;
// Độ nhạy thu thấp nhất chấp nhận: nhiễu nền kênh 22 MHz (~-94 dBm) + 4 dB SNR preamble.
constexpr double kMinRxSensitivityDbm = -90.0;
// Ngưỡng "robot yếu pin" khi đo ai chuyển tiếp gói (weak_relay_share).
constexpr double kWeakBatteryPct = 30.0;
// TTL robot gắn cho gói dữ liệu; Gateway suy ra số hop = kDataTtl + 1 - TTL nhận được.
constexpr uint8_t kDataTtl = 64;

struct LinkRssi
{
    double avgDbm = 0;
    Time last;
    bool seen = false;
};

struct Telemetry
{
    double energyPct;
    double rssiDbm;
    Time received;
};

struct WanSample
{
    double rttMs;
    int httpStatus;
    bool timeout;
};

struct GatewayEvent
{
    double ts;
    std::string type;
    std::string payload;
};

SimConfig g_config = SimConfig::kNoCloud;
uint32_t g_nRobots = 0;
Time g_dmax = MilliSeconds(20);
Time g_jitter = MilliSeconds(2);
Time g_period = Seconds(5);
Time g_cloudTimeout = Seconds(2);
Time g_appStart = Seconds(10);
Time g_appStop;
Time g_interval = Seconds(1);
double g_outageStart = -1;
double g_outageEnd = -1;
double g_windowStart = 300;
double g_windowEnd = 600;
double g_drainMovePctPerS = 0.02;
double g_drainTxPct = 0.001;
double g_wanConstantRttMs = 40;

caar::Weights g_activeWeights = caar::BalancedWeights();
caar::GatewayState* g_gateway = nullptr;
AnimationInterface* g_anim = nullptr;

std::vector<Ptr<Node>> g_nodes; // 0 = Gateway, 1..N = robot
std::vector<Ipv4Address> g_ip;
std::map<Mac48Address, uint32_t> g_macToIdx;
std::map<Ipv4Address, uint32_t> g_ipToIdx;
std::vector<std::map<uint32_t, LinkRssi>> g_rssi;
std::vector<double> g_energyPct;
std::vector<Ptr<Socket>> g_robotSockets;
std::vector<uint32_t> g_seq;
std::map<uint32_t, Telemetry> g_telemetry;
std::vector<WanSample> g_wan;

Ptr<UniformRandomVariable> g_jitterRv;
Ptr<UniformRandomVariable> g_wanRv;

// Bộ đếm cho metric
uint64_t g_ipTx = 0;
uint64_t g_aodvTx = 0;
uint64_t g_dataTxWindow = 0;
uint64_t g_dataRxWindow = 0;
uint64_t g_cloudBytes = 0;
std::vector<double> g_delaysMs;
std::vector<double> g_routeDiscoveryMs;

// Phép đo cơ chế định tuyến (vì sao mất gói, đường được chọn ra sao, ai chuyển tiếp)
uint64_t g_dataNoRouteDrops = 0; // gói dữ liệu bị bỏ vì không tìm được / mất đường
std::vector<uint32_t> g_hops;    // số hop của gói dữ liệu tới Gateway
double g_dataLinkRssiSum = 0;    // RSSI các khung dữ liệu unicast nhận thành công
uint64_t g_dataLinkFrames = 0;
uint64_t g_dataForwards = 0; // lượt robot chuyển tiếp gói dữ liệu
uint64_t g_weakForwards = 0; // ... trong lúc pin robot dưới kWeakBatteryPct
std::vector<Mac48Address> g_mac;
std::vector<GatewayEvent> g_events;

// ---------------------------------------------------------------------------
// Đọc file hợp đồng
// ---------------------------------------------------------------------------

std::string
ReadFile(const std::string& path)
{
    std::ifstream in(path, std::ios::binary);
    NS_ABORT_MSG_IF(!in, "cannot open " << path);
    std::stringstream buf;
    buf << in.rdbuf();
    return buf.str();
}

// Lấy giá trị số của một khóa trong JSON phẳng (channel.json).
double
JsonNumber(const std::string& text, const std::string& key)
{
    size_t pos = text.find("\"" + key + "\"");
    NS_ABORT_MSG_IF(pos == std::string::npos, "missing key " << key);
    pos = text.find(':', pos);
    return std::strtod(text.c_str() + pos + 1, nullptr);
}

// Lấy mảng 2 số, ví dụ "gateway_xy": [50.0, 2.5].
std::pair<double, double>
JsonPair(const std::string& text, const std::string& key)
{
    size_t pos = text.find("\"" + key + "\"");
    NS_ABORT_MSG_IF(pos == std::string::npos, "missing key " << key);
    pos = text.find('[', pos);
    char* end = nullptr;
    double a = std::strtod(text.c_str() + pos + 1, &end);
    double b = std::strtod(std::strchr(end, ',') + 1, nullptr);
    return {a, b};
}

std::vector<std::string>
SplitCsv(const std::string& line)
{
    std::vector<std::string> out;
    std::stringstream ss(line);
    std::string cell;
    while (std::getline(ss, cell, ','))
    {
        if (!cell.empty() && cell.back() == '\r')
        {
            cell.pop_back();
        }
        out.push_back(cell);
    }
    return out;
}

// contracts/waypoints/<N>_<seed>.csv: node_id, t_s, x_m, y_m
std::map<uint32_t, std::vector<Waypoint>>
ReadWaypoints(const std::string& path)
{
    std::ifstream in(path);
    NS_ABORT_MSG_IF(!in, "cannot open " << path);
    std::map<uint32_t, std::vector<Waypoint>> tracks;
    std::string line;
    std::getline(in, line); // header
    while (std::getline(in, line))
    {
        if (line.empty())
        {
            continue;
        }
        auto c = SplitCsv(line);
        NS_ABORT_MSG_IF(c.size() < 4, "bad waypoint line: " << line);
        uint32_t id = std::stoul(c[0]);
        tracks[id].emplace_back(Seconds(std::stod(c[1])),
                                Vector(std::stod(c[2]), std::stod(c[3]), 0.0));
    }
    return tracks;
}

// contracts/wan_trace.csv: ts, rtt_ms, http_status, timeout
std::vector<WanSample>
ReadWanTrace(const std::string& path)
{
    std::ifstream in(path);
    NS_ABORT_MSG_IF(!in, "cannot open " << path);
    std::vector<WanSample> rows;
    std::string line;
    std::getline(in, line);
    while (std::getline(in, line))
    {
        auto c = SplitCsv(line);
        if (c.size() < 4)
        {
            continue;
        }
        rows.push_back({std::stod(c[1]), std::stoi(c[2]), c[3] == "1"});
    }
    NS_ABORT_MSG_IF(rows.empty(), "empty WAN trace " << path);
    return rows;
}

// ---------------------------------------------------------------------------
// RSSI, pin, overhead
// ---------------------------------------------------------------------------

void
OnSnifferRx(uint32_t self,
            Ptr<const Packet> packet,
            uint16_t /*channelFreqMhz*/,
            WifiTxVector /*txVector*/,
            MpduInfo /*aMpdu*/,
            SignalNoiseDbm signalNoise,
            uint16_t /*staId*/)
{
    WifiMacHeader hdr;
    if (packet->PeekHeader(hdr) == 0 || !hdr.IsData())
    {
        return;
    }
    auto it = g_macToIdx.find(hdr.GetAddr2());
    if (it == g_macToIdx.end() || it->second == self)
    {
        return;
    }
    LinkRssi& link = g_rssi[self][it->second];
    double sample = signalNoise.signal;
    link.avgDbm = link.seen ? (1 - kRssiEwmaAlpha) * link.avgDbm + kRssiEwmaAlpha * sample : sample;
    link.seen = true;
    link.last = Simulator::Now();

    // Link thật sự chở dữ liệu: khung unicast gửi cho chính node này, mang gói UDP cổng dữ liệu.
    if (hdr.GetAddr1() == g_mac[self])
    {
        Ptr<Packet> copy = packet->Copy();
        copy->RemoveHeader(hdr);
        LlcSnapHeader llc;
        Ipv4Header ip;
        UdpHeader udp;
        if (copy->RemoveHeader(llc) && llc.GetType() == Ipv4L3Protocol::PROT_NUMBER &&
            copy->RemoveHeader(ip) && ip.GetProtocol() == UdpL4Protocol::PROT_NUMBER &&
            copy->PeekHeader(udp) && udp.GetDestinationPort() == kDataPort)
        {
            g_dataLinkRssiSum += sample;
            ++g_dataLinkFrames;
        }
    }
}

// Gói (không còn header IP) có phải gói dữ liệu robot -> Gateway không.
bool
IsDataPayload(const Ipv4Header& ip, Ptr<const Packet> payload)
{
    UdpHeader udp;
    return ip.GetProtocol() == UdpL4Protocol::PROT_NUMBER && payload->PeekHeader(udp) &&
           udp.GetDestinationPort() == kDataPort;
}

// Gói dữ liệu bị IPv4 bỏ vì không có đường: AODV tìm đường thất bại, hàng đợi chờ
// đường quá hạn, hoặc node trung gian mất đường (đều đi qua DROP_ROUTE_ERROR / NO_ROUTE).
void
OnIpDrop(const Ipv4Header& ip,
         Ptr<const Packet> payload,
         Ipv4L3Protocol::DropReason reason,
         Ptr<Ipv4> /*ipv4*/,
         uint32_t /*iface*/)
{
    if ((reason == Ipv4L3Protocol::DROP_NO_ROUTE || reason == Ipv4L3Protocol::DROP_ROUTE_ERROR) &&
        IsDataPayload(ip, payload))
    {
        ++g_dataNoRouteDrops;
    }
}

void
OnIpForward(uint32_t self, const Ipv4Header& ip, Ptr<const Packet> payload, uint32_t /*iface*/)
{
    if (self == 0 || !IsDataPayload(ip, payload))
    {
        return;
    }
    ++g_dataForwards;
    if (g_energyPct[self] < kWeakBatteryPct)
    {
        ++g_weakForwards;
    }
}

// RSSI trung bình của các liên kết robot còn nghe thấy (giá trị rssi_avg của telemetry).
double
RobotRssiAvg(uint32_t self)
{
    double sum = 0;
    uint32_t n = 0;
    for (const auto& [neighbor, link] : g_rssi[self])
    {
        if (link.seen && Simulator::Now() - link.last <= Seconds(kRssiFreshSeconds))
        {
            sum += link.avgDbm;
            ++n;
        }
    }
    return n > 0 ? sum / n : kUnknownRssiDbm;
}

void
Drain(uint32_t self, double pct)
{
    if (self != 0)
    {
        g_energyPct[self] = std::max(0.0, g_energyPct[self] - pct);
    }
}

void
OnIpTx(uint32_t self, Ptr<const Packet> packet, Ptr<Ipv4> /*ipv4*/, uint32_t /*iface*/)
{
    ++g_ipTx;
    Drain(self, g_drainTxPct);
    Ptr<Packet> copy = packet->Copy();
    Ipv4Header ip;
    copy->RemoveHeader(ip);
    if (ip.GetProtocol() == UdpL4Protocol::PROT_NUMBER)
    {
        UdpHeader udp;
        copy->PeekHeader(udp);
        if (udp.GetDestinationPort() == kAodvPort || udp.GetSourcePort() == kAodvPort)
        {
            ++g_aodvTx;
        }
    }
}

void
DrainMovement()
{
    for (uint32_t i = 1; i <= g_nRobots; ++i)
    {
        Vector v = g_nodes[i]->GetObject<MobilityModel>()->GetVelocity();
        if (std::hypot(v.x, v.y) > 1e-9)
        {
            Drain(i, g_drainMovePctPerS);
        }
    }
    Simulator::Schedule(Seconds(1), &DrainMovement);
}

// ---------------------------------------------------------------------------
// Delayed RREQ forwarding (mục 4): D_i = D_max · c_i + U(0, J)
// ---------------------------------------------------------------------------

Time
RreqForwardDelay(uint32_t self, Ipv4Address /*receiver*/, Ipv4Address prevHop)
{
    double rssi = kUnknownRssiDbm;
    auto it = g_ipToIdx.find(prevHop);
    if (it != g_ipToIdx.end())
    {
        auto link = g_rssi[self].find(it->second);
        if (link != g_rssi[self].end() && link->second.seen)
        {
            rssi = link->second.avgDbm;
        }
    }
    double base = caar::BaseForwardDelay(g_dmax.GetSeconds(),
                                         g_activeWeights,
                                         rssi,
                                         g_energyPct[self] / 100.0);
    return Seconds(base) + Seconds(g_jitterRv->GetValue(0, g_jitter.GetSeconds()));
}

void
OnRouteDiscovery(Ipv4Address /*dst*/, Time duration)
{
    g_routeDiscoveryMs.push_back(duration.GetSeconds() * 1000);
}

// ---------------------------------------------------------------------------
// Lưu lượng robot -> Gateway (gói mang telemetry)
// ---------------------------------------------------------------------------

void
PutU32(uint8_t* p, uint32_t v)
{
    for (int i = 0; i < 4; ++i)
    {
        p[i] = (v >> (8 * i)) & 0xff;
    }
}

uint32_t
GetU32(const uint8_t* p)
{
    return uint32_t(p[0]) | uint32_t(p[1]) << 8 | uint32_t(p[2]) << 16 | uint32_t(p[3]) << 24;
}

bool
InWindow(double t)
{
    return t >= g_windowStart && t < g_windowEnd;
}

// Bố cục payload: robot id, seq, thời điểm gửi (ns, 64 bit), pin (‰ %), RSSI (0,01 dBm).
void
SendTelemetry(uint32_t r)
{
    if (Simulator::Now() >= g_appStop)
    {
        return;
    }
    uint8_t buf[kPayloadBytes] = {};
    int64_t nowNs = Simulator::Now().GetNanoSeconds();
    PutU32(buf, r);
    PutU32(buf + 4, g_seq[r]++);
    PutU32(buf + 8, uint32_t(uint64_t(nowNs) & 0xffffffff));
    PutU32(buf + 12, uint32_t(uint64_t(nowNs) >> 32));
    PutU32(buf + 16, uint32_t(int32_t(std::lround(g_energyPct[r] * 1000))));
    PutU32(buf + 20, uint32_t(int32_t(std::lround(RobotRssiAvg(r) * 100))));
    g_robotSockets[r]->Send(Create<Packet>(buf, kPayloadBytes));
    if (InWindow(Simulator::Now().GetSeconds()))
    {
        ++g_dataTxWindow;
    }
    Simulator::Schedule(g_interval, &SendTelemetry, r);
}

void
OnGatewayRecv(Ptr<Socket> socket)
{
    Ptr<Packet> packet;
    Address from;
    while ((packet = socket->RecvFrom(from)))
    {
        if (packet->GetSize() < 24)
        {
            continue;
        }
        uint8_t buf[24];
        packet->CopyData(buf, 24);
        uint32_t robot = GetU32(buf);
        int64_t txNs = int64_t(uint64_t(GetU32(buf + 8)) | uint64_t(GetU32(buf + 12)) << 32);
        double energy = int32_t(GetU32(buf + 16)) / 1000.0;
        double rssi = int32_t(GetU32(buf + 20)) / 100.0;
        Time txTime = NanoSeconds(txNs);
        g_delaysMs.push_back((Simulator::Now() - txTime).GetSeconds() * 1000);
        SocketIpTtlTag ttl;
        if (packet->RemovePacketTag(ttl))
        {
            g_hops.push_back(kDataTtl + 1 - ttl.GetTtl());
        }
        if (InWindow(txTime.GetSeconds()))
        {
            ++g_dataRxWindow;
        }
        g_telemetry[robot] = {energy, rssi, Simulator::Now()};
    }
}

// ---------------------------------------------------------------------------
// Gateway và kênh Cloud (mục 7.3, 7.4, 9.1)
// ---------------------------------------------------------------------------

void
LogEvents(const std::vector<std::string>& events, const std::string& payload)
{
    for (const std::string& e : events)
    {
        g_events.push_back({Simulator::Now().GetSeconds(), e, e == caar::kParamUpdate ? payload : ""});
    }
    g_activeWeights = g_gateway->Active();
    if (g_anim)
    {
        // Gateway: mức 1 xanh dương, mức 2 cam (dùng cache), mức 3 đỏ (bộ cân bằng).
        static const uint8_t kLevelColor[3][3] = {{30, 90, 220}, {240, 150, 20}, {210, 40, 40}};
        int level = static_cast<int>(g_gateway->level());
        const uint8_t* c = kLevelColor[level - 1];
        g_anim->UpdateNodeColor(g_nodes[0], c[0], c[1], c[2]);
        g_anim->UpdateNodeDescription(g_nodes[0], "Gateway L" + std::to_string(level));
    }
}

std::vector<caar::NodeSample>
BuildSnapshot()
{
    std::vector<caar::NodeSample> nodes;
    for (const auto& [robot, t] : g_telemetry)
    {
        if (Simulator::Now() - t.received <= 3 * g_period)
        {
            nodes.push_back({t.rssiDbm, t.energyPct});
        }
    }
    return nodes;
}

// Kích thước JSON của NetworkSnapshot gửi lên /optimize (mục 9.3).
uint32_t
SnapshotBytes(const std::vector<caar::NodeSample>& nodes)
{
    std::string json = "{\"run_id\":0,\"timestamp\":1761000000.000,\"nonce\":"
                       "\"00000000000000000000000000000000\",\"nodes\":[";
    for (size_t i = 0; i < nodes.size(); ++i)
    {
        char item[160];
        std::snprintf(item,
                      sizeof(item),
                      "%s{\"node_id\":\"r%zu\",\"rssi_avg\":%.2f,\"energy_remaining_pct\":%.2f,"
                      "\"hop_count\":1}",
                      i ? "," : "",
                      i + 1,
                      nodes[i].rssi_avg,
                      nodes[i].energy_remaining_pct);
        json += item;
    }
    return json.size() + 2;
}

constexpr uint32_t kResponseBytes =
    sizeof("{\"weights\":{\"hop_weight\":0.4,\"rssi_weight\":0.3,\"energy_weight\":0.3},"
           "\"rule\":\"balanced\"}") -
    1;

void
OnCloudReply(double callTime, caar::Decision decision)
{
    g_cloudBytes += kResponseBytes;
    LogEvents(g_gateway->OnReply(callTime, decision.weights), caar::RuleName(decision.rule));
}

void
OnCloudFailure(double callTime)
{
    LogEvents(g_gateway->OnFailure(callTime), "");
}

WanSample
SampleWan()
{
    if (g_wan.empty())
    {
        return {g_wanConstantRttMs, 200, false};
    }
    return g_wan[g_wanRv->GetInteger(0, g_wan.size() - 1)];
}

void
GatewayTick()
{
    double t = Simulator::Now().GetSeconds();
    std::vector<caar::NodeSample> snapshot = BuildSnapshot();
    caar::Decision decision = caar::ChooseWeights(snapshot);

    if (g_config == SimConfig::kGatewayHeuristic)
    {
        LogEvents(g_gateway->OnReply(t, decision.weights), caar::RuleName(decision.rule));
    }
    else
    {
        g_cloudBytes += SnapshotBytes(snapshot);
        bool outage = t >= g_outageStart && t < g_outageEnd;
        WanSample s = SampleWan();
        Time rtt = MilliSeconds(s.rttMs);
        if (outage || s.timeout || s.httpStatus != 200 || rtt >= g_cloudTimeout)
        {
            Simulator::Schedule(g_cloudTimeout, &OnCloudFailure, t);
        }
        else
        {
            Simulator::Schedule(rtt, &OnCloudReply, t, decision);
        }
    }
    Simulator::Schedule(g_period, &GatewayTick);
}

// Robot đổi màu theo pin: 100 % xanh lá -> 0 % đỏ; nhãn ghi tên và % pin.
void
UpdateAnimation()
{
    for (uint32_t i = 1; i <= g_nRobots; ++i)
    {
        double e = g_energyPct[i] / 100.0;
        g_anim->UpdateNodeColor(g_nodes[i], uint8_t(220 * (1 - e)), uint8_t(180 * e + 20), 40);
        std::ostringstream label;
        label << "r" << i << " " << std::lround(g_energyPct[i]) << "%";
        g_anim->UpdateNodeDescription(g_nodes[i], label.str());
    }
    Simulator::Schedule(Seconds(5), &UpdateAnimation);
}

// ---------------------------------------------------------------------------
// Kết quả
// ---------------------------------------------------------------------------

std::string
CsvQuote(const std::string& s)
{
    std::string out = "\"";
    for (char c : s)
    {
        out += c;
        if (c == '"')
        {
            out += '"';
        }
    }
    return out + "\"";
}

std::string
Num(double v, int precision = 6)
{
    std::ostringstream os;
    os << std::setprecision(precision) << v;
    return os.str();
}

double
Percentile(std::vector<double> v, double p)
{
    if (v.empty())
    {
        return NAN;
    }
    std::sort(v.begin(), v.end());
    size_t rank = size_t(std::ceil(p * v.size()));
    return v[std::max<size_t>(rank, 1) - 1];
}

std::string
NumOrEmpty(double v)
{
    return std::isnan(v) ? "" : Num(v);
}

} // namespace

int
main(int argc, char* argv[])
{
    std::string config = "no_cloud";
    std::string scenario = "baseline";
    uint32_t seed = 1;
    uint32_t nodes = 10;
    double dmaxMs = 20;
    double jitterMs = 2;
    double ttl = 60;
    double period = 5;
    double cloudTimeout = 2;
    double duration = 900;
    double speed = 0.2;
    std::string waypointsPath;
    std::string layoutPath;
    std::string channelPath;
    std::string wanTracePath;
    std::string outPath;
    std::string fixedWeights;
    std::string netanimPath;
    bool destinationOnly = false;
    double netanimStart = 0;
    double netanimStop = -1;

    CommandLine cmd(__FILE__);
    cmd.AddValue("config", "no_cloud | local_optimized | gateway_heuristic | cloud_assisted", config);
    cmd.AddValue("scenario", "Tên kịch bản ghi vào kết quả (baseline, outage, stale, ...)", scenario);
    cmd.AddValue("seed", "Số run của bộ sinh ngẫu nhiên (RngRun)", seed);
    cmd.AddValue("nodes", "Số robot (phải khớp file waypoints)", nodes);
    cmd.AddValue("dmax", "D_max mỗi hop (ms)", dmaxMs);
    cmd.AddValue("jitter", "J của jitter U(0, J) (ms)", jitterMs);
    cmd.AddValue("ttl", "TTL của trọng số cache (s)", ttl);
    cmd.AddValue("period", "Chu kỳ Gateway gọi Cloud T (s)", period);
    cmd.AddValue("cloud-timeout", "Timeout gọi Cloud (s)", cloudTimeout);
    cmd.AddValue("outage-start", "Bắt đầu mất cloud (s), âm = không mất", g_outageStart);
    cmd.AddValue("outage-end", "Kết thúc mất cloud (s)", g_outageEnd);
    cmd.AddValue("window-start", "Bắt đầu cửa sổ đo pdr_window (s)", g_windowStart);
    cmd.AddValue("window-end", "Kết thúc cửa sổ đo pdr_window (s)", g_windowEnd);
    cmd.AddValue("wan-trace", "contracts/wan_trace.csv; bỏ trống = RTT hằng số", wanTracePath);
    cmd.AddValue("wan-rtt-ms", "RTT hằng số khi không có trace (ms)", g_wanConstantRttMs);
    cmd.AddValue("waypoints", "contracts/waypoints/<N>_<seed>.csv", waypointsPath);
    cmd.AddValue("layout", "layout.json (mặc định: cạnh file waypoints)", layoutPath);
    cmd.AddValue("channel", "contracts/channel.json", channelPath);
    cmd.AddValue("out", "File CSV kết quả", outPath);
    cmd.AddValue("duration", "Thời gian mô phỏng (s)", duration);
    cmd.AddValue("speed", "Tốc độ trên ray ghi vào cột mobility_speed (m/s)", speed);
    cmd.AddValue("fixed-weights", "Ghi đè trọng số local_optimized, ví dụ 1,0,0", fixedWeights);
    cmd.AddValue("drain-move", "Hao pin khi di chuyển (%/s)", g_drainMovePctPerS);
    cmd.AddValue("drain-tx", "Hao pin mỗi gói IP phát (%)", g_drainTxPct);
    cmd.AddValue("netanim", "Ghi trace NetAnim ra file XML (trống = tắt)", netanimPath);
    cmd.AddValue("destination-only",
                 "Chỉ đích trả lời RREQ (AODV DestinationOnly); mặc định node trung gian có đường cũng trả lời",
                 destinationOnly);
    cmd.AddValue("netanim-start", "Bắt đầu ghi gói tin cho NetAnim (s)", netanimStart);
    cmd.AddValue("netanim-stop", "Dừng ghi gói tin cho NetAnim (s), âm = tới cuối", netanimStop);
    cmd.Parse(argc, argv);

    if (config == "no_cloud")
    {
        g_config = SimConfig::kNoCloud;
    }
    else if (config == "local_optimized")
    {
        g_config = SimConfig::kLocalOptimized;
    }
    else if (config == "gateway_heuristic")
    {
        g_config = SimConfig::kGatewayHeuristic;
    }
    else if (config == "cloud_assisted")
    {
        g_config = SimConfig::kCloudAssisted;
    }
    else
    {
        NS_ABORT_MSG("unknown --config " << config);
    }
    NS_ABORT_MSG_IF(waypointsPath.empty() || channelPath.empty(),
                    "--waypoints and --channel are required");
    NS_ABORT_MSG_IF(duration <= g_appStart.GetSeconds() + 10, "--duration too short");

    RngSeedManager::SetSeed(20261022);
    RngSeedManager::SetRun(seed);

    g_nRobots = nodes;
    g_dmax = MilliSeconds(dmaxMs);
    g_jitter = MilliSeconds(jitterMs);
    g_period = Seconds(period);
    g_cloudTimeout = Seconds(cloudTimeout);
    g_appStop = Seconds(duration - 10);

    if (!fixedWeights.empty())
    {
        NS_ABORT_MSG_IF(g_config != SimConfig::kLocalOptimized,
                        "--fixed-weights only applies to local_optimized");
        double wh = 0;
        double wr = 0;
        double we = 0;
        NS_ABORT_MSG_IF(std::sscanf(fixedWeights.c_str(), "%lf,%lf,%lf", &wh, &wr, &we) != 3,
                        "--fixed-weights expects wh,wr,we");
        g_activeWeights = {wh, wr, we};
        NS_ABORT_MSG_IF(!caar::ValidWeights(g_activeWeights), "invalid --fixed-weights");
    }

    // --- Đầu vào hợp đồng ----------------------------------------------------
    std::string channel = ReadFile(channelPath);
    double pathLossExp = JsonNumber(channel, "n");
    double sigmaDb = JsonNumber(channel, "sigma_db");
    double refLossDb = JsonNumber(channel, "ref_loss_db");
    double refDist = JsonNumber(channel, "ref_dist_m");
    double txPowerDbm = JsonNumber(channel, "tx_power_dbm");
    double rxSensDbm = JsonNumber(channel, "rx_sensitivity_dbm");

    if (layoutPath.empty())
    {
        size_t slash = waypointsPath.find_last_of("/\\");
        layoutPath = (slash == std::string::npos ? std::string(".") : waypointsPath.substr(0, slash)) +
                     "/layout.json";
    }
    auto gatewayXy = JsonPair(ReadFile(layoutPath), "gateway_xy");

    auto tracks = ReadWaypoints(waypointsPath);
    NS_ABORT_MSG_IF(tracks.size() != nodes,
                    "waypoints file has " << tracks.size() << " robots, --nodes=" << nodes);

    std::string wanModel = "none";
    if (g_config == SimConfig::kCloudAssisted)
    {
        if (wanTracePath.empty())
        {
            wanModel = "constant";
            NS_LOG_UNCOND("WARNING: no --wan-trace, using constant RTT " << g_wanConstantRttMs << " ms");
        }
        else
        {
            g_wan = ReadWanTrace(wanTracePath);
            wanModel = "trace";
        }
    }

    // --- Node, mobility -------------------------------------------------------
    NodeContainer all;
    all.Create(nodes + 1);
    for (uint32_t i = 0; i <= nodes; ++i)
    {
        g_nodes.push_back(all.Get(i));
    }

    Ptr<ConstantPositionMobilityModel> gwMobility = CreateObject<ConstantPositionMobilityModel>();
    gwMobility->SetPosition(Vector(gatewayXy.first, gatewayXy.second, 0));
    all.Get(0)->AggregateObject(gwMobility);
    for (uint32_t i = 1; i <= nodes; ++i)
    {
        NS_ABORT_MSG_IF(!tracks.count(i), "waypoints file has no robot " << i);
        Ptr<WaypointMobilityModel> m = CreateObject<WaypointMobilityModel>();
        for (const Waypoint& w : tracks[i])
        {
            m->AddWaypoint(w);
        }
        all.Get(i)->AggregateObject(m);
    }

    // --- Kênh và WiFi ad hoc (mục 5) -------------------------------------------
    YansWifiChannelHelper channelHelper;
    channelHelper.SetPropagationDelay("ns3::ConstantSpeedPropagationDelayModel");
    channelHelper.AddPropagationLoss("ns3::LogDistancePropagationLossModel",
                                     "Exponent",
                                     DoubleValue(pathLossExp),
                                     "ReferenceDistance",
                                     DoubleValue(refDist),
                                     "ReferenceLoss",
                                     DoubleValue(refLossDb));
    std::ostringstream shadow;
    shadow << "ns3::NormalRandomVariable[Mean=0.0|Variance=" << sigmaDb * sigmaDb << "]";
    channelHelper.AddPropagationLoss("ns3::RandomPropagationLossModel",
                                     "Variable",
                                     StringValue(shadow.str()));
    Ptr<YansWifiChannel> wifiChannel = channelHelper.Create();

    YansWifiPhyHelper phy;
    phy.SetChannel(wifiChannel);
    phy.Set("TxPowerStart", DoubleValue(txPowerDbm));
    phy.Set("TxPowerEnd", DoubleValue(txPowerDbm));
    phy.Set("RxSensitivity", DoubleValue(rxSensDbm));
    // Mặc định ns-3 bỏ mọi khung dưới -82 dBm ở bước phát hiện preamble, bất kể
    // RxSensitivity; đặt cùng ngưỡng để độ nhạy trong channel.json có hiệu lực.
    // Ngưỡng sát nhiễu nền (~-94 dBm với kênh 22 MHz) làm PHY của ns-3.48 dừng với
    // "Invalid WifiPhy state RX", nên chặn ở nhiễu nền + 4 dB (ngưỡng SNR preamble).
    NS_ABORT_MSG_IF(rxSensDbm < kMinRxSensitivityDbm,
                    "rx_sensitivity_dbm " << rxSensDbm << " is below " << kMinRxSensitivityDbm
                                          << " dBm (noise floor + 4 dB)");
    phy.SetPreambleDetectionModel("ns3::ThresholdPreambleDetectionModel",
                                  "MinimumRssi",
                                  DoubleValue(rxSensDbm));

    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211b);
    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                 "DataMode",
                                 StringValue("DsssRate1Mbps"),
                                 "ControlMode",
                                 StringValue("DsssRate1Mbps"));
    WifiMacHelper mac;
    mac.SetType("ns3::AdhocWifiMac");
    NetDeviceContainer devices = wifi.Install(phy, mac, all);

    // --- IP + AODV ---------------------------------------------------------------
    AodvHelper aodv;
    aodv.Set("DestinationOnly", BooleanValue(destinationOnly));
    InternetStackHelper stack;
    stack.SetRoutingHelper(aodv);
    stack.Install(all);
    Ipv4AddressHelper address;
    address.SetBase("10.1.0.0", "255.255.0.0");
    Ipv4InterfaceContainer ifaces = address.Assign(devices);

    int64_t stream = 1000;
    stream += wifi.AssignStreams(devices, stream);
    stream += channelHelper.AssignStreams(wifiChannel, stream);
    stream += aodv.AssignStreams(all, stream);
    g_jitterRv = CreateObject<UniformRandomVariable>();
    g_jitterRv->SetStream(stream++);
    g_wanRv = CreateObject<UniformRandomVariable>();
    g_wanRv->SetStream(stream++);
    Ptr<UniformRandomVariable> energyRv = CreateObject<UniformRandomVariable>();
    energyRv->SetStream(stream++);
    Ptr<UniformRandomVariable> startRv = CreateObject<UniformRandomVariable>();
    startRv->SetStream(stream++);

    g_rssi.resize(nodes + 1);
    g_energyPct.assign(nodes + 1, 100.0);
    g_seq.assign(nodes + 1, 0);
    g_robotSockets.resize(nodes + 1);
    for (uint32_t i = 0; i <= nodes; ++i)
    {
        g_ip.push_back(ifaces.GetAddress(i));
        g_ipToIdx[ifaces.GetAddress(i)] = i;
        g_mac.push_back(Mac48Address::ConvertFrom(devices.Get(i)->GetAddress()));
        g_macToIdx[g_mac.back()] = i;
        if (i > 0)
        {
            g_energyPct[i] = energyRv->GetValue(20, 100); // mục 6.3: đều 20–100 %
        }

        Ptr<WifiNetDevice> dev = DynamicCast<WifiNetDevice>(devices.Get(i));
        dev->GetPhy()->TraceConnectWithoutContext("MonitorSnifferRx",
                                                  MakeBoundCallback(&OnSnifferRx, i));
        Ptr<Ipv4L3Protocol> ipv4 = all.Get(i)->GetObject<Ipv4L3Protocol>();
        ipv4->TraceConnectWithoutContext("Tx", MakeBoundCallback(&OnIpTx, i));
        ipv4->TraceConnectWithoutContext("Drop", MakeCallback(&OnIpDrop));
        ipv4->TraceConnectWithoutContext("UnicastForward", MakeBoundCallback(&OnIpForward, i));

        Ptr<aodv::RoutingProtocol> routing =
            DynamicCast<aodv::RoutingProtocol>(all.Get(i)->GetObject<Ipv4>()->GetRoutingProtocol());
        NS_ABORT_MSG_IF(!routing, "AODV routing protocol not found on node " << i);
        routing->TraceConnectWithoutContext("RouteDiscovery", MakeCallback(&OnRouteDiscovery));
        if (i > 0 && g_config != SimConfig::kNoCloud)
        {
            routing->SetRreqForwardDelayCallback(MakeBoundCallback(&RreqForwardDelay, i));
        }
    }

    // --- Ứng dụng: robot -> Gateway ------------------------------------------------
    Ptr<Socket> sink = Socket::CreateSocket(all.Get(0), UdpSocketFactory::GetTypeId());
    sink->Bind(InetSocketAddress(Ipv4Address::GetAny(), kDataPort));
    sink->SetRecvCallback(MakeCallback(&OnGatewayRecv));
    sink->SetIpRecvTtl(true); // để đếm số hop của gói tới Gateway
    for (uint32_t i = 1; i <= nodes; ++i)
    {
        g_robotSockets[i] = Socket::CreateSocket(all.Get(i), UdpSocketFactory::GetTypeId());
        g_robotSockets[i]->SetIpTtl(kDataTtl);
        g_robotSockets[i]->Connect(InetSocketAddress(g_ip[0], kDataPort));
        Simulator::Schedule(g_appStart + Seconds(startRv->GetValue(0, 1)), &SendTelemetry, i);
    }
    Simulator::Schedule(Seconds(1), &DrainMovement);

    caar::GatewayState gateway(g_config == SimConfig::kCloudAssisted ? ttl : 1e18);
    g_gateway = &gateway;
    if (g_config == SimConfig::kGatewayHeuristic || g_config == SimConfig::kCloudAssisted)
    {
        Simulator::Schedule(g_period, &GatewayTick);
    }

    std::unique_ptr<AnimationInterface> anim;
    if (!netanimPath.empty())
    {
        anim = std::make_unique<AnimationInterface>(netanimPath);
        g_anim = anim.get();
        anim->SetMobilityPollInterval(Seconds(1));
        anim->SetMaxPktsPerTraceFile(50'000'000);
        anim->SetStartTime(Seconds(netanimStart));
        anim->SetStopTime(Seconds(netanimStop < 0 ? duration : netanimStop));
        anim->UpdateNodeDescription(g_nodes[0], "Gateway L1");
        anim->UpdateNodeColor(g_nodes[0], 30, 90, 220);
        anim->UpdateNodeSize(g_nodes[0]->GetId(), 3, 3);
        for (uint32_t i = 1; i <= nodes; ++i)
        {
            anim->UpdateNodeSize(g_nodes[i]->GetId(), 2, 2);
        }
        UpdateAnimation();
    }

    FlowMonitorHelper flowHelper;
    Ptr<FlowMonitor> monitor = flowHelper.InstallAll();

    Simulator::Stop(Seconds(duration));
    Simulator::Run();

    // --- Metric (mục 10.3) ---------------------------------------------------------
    monitor->CheckForLostPackets();
    auto classifier = DynamicCast<Ipv4FlowClassifier>(flowHelper.GetClassifier());
    uint64_t txPackets = 0;
    uint64_t rxPackets = 0;
    double delaySumS = 0;
    for (const auto& [id, st] : monitor->GetFlowStats())
    {
        if (classifier->FindFlow(id).destinationPort == kDataPort)
        {
            txPackets += st.txPackets;
            rxPackets += st.rxPackets;
            delaySumS += st.delaySum.GetSeconds();
        }
    }
    double pdr = txPackets ? double(rxPackets) / txPackets : NAN;
    double avgDelayMs = rxPackets ? delaySumS / rxPackets * 1000 : NAN;
    double p95DelayMs = Percentile(g_delaysMs, 0.95);
    double overhead = g_ipTx ? double(g_aodvTx) / g_ipTx : NAN;
    double routeDiscoveryMs = NAN;
    if (!g_routeDiscoveryMs.empty())
    {
        double s = 0;
        for (double v : g_routeDiscoveryMs)
        {
            s += v;
        }
        routeDiscoveryMs = s / g_routeDiscoveryMs.size();
    }
    double minEnergy = *std::min_element(g_energyPct.begin() + 1, g_energyPct.end());
    double pdrWindow = g_dataTxWindow ? double(g_dataRxWindow) / g_dataTxWindow : NAN;
    double lossNoRoute = txPackets ? double(g_dataNoRouteDrops) / txPackets : NAN;
    double hopsAvg = NAN;
    if (!g_hops.empty())
    {
        double s = 0;
        for (uint32_t h : g_hops)
        {
            s += h;
        }
        hopsAvg = s / g_hops.size();
    }
    double linkRssi = g_dataLinkFrames ? g_dataLinkRssiSum / g_dataLinkFrames : NAN;
    double weakRelayShare = g_dataForwards ? double(g_weakForwards) / g_dataForwards : NAN;

    std::ostringstream params;
    params << "{\"dmax_ms\": " << Num(dmaxMs) << ", \"jitter_ms\": " << Num(jitterMs)
           << ", \"ttl_s\": " << Num(ttl) << ", \"period_s\": " << Num(period);
    if (g_outageStart >= 0)
    {
        params << ", \"outage_start_s\": " << Num(g_outageStart)
               << ", \"outage_end_s\": " << Num(g_outageEnd);
    }
    if (!fixedWeights.empty())
    {
        params << ", \"fixed_weights\": \"" << fixedWeights << "\"";
    }
    if (destinationOnly)
    {
        params << ", \"destination_only\": true";
    }
    params << ", \"wan_model\": \"" << wanModel << "\"";
    params << ", \"window_s\": [" << Num(g_windowStart) << ", " << Num(g_windowEnd) << "]";
    params << ", \"pdr_window\": " << (std::isnan(pdrWindow) ? "null" : Num(pdrWindow)) << "}";

    std::ostringstream row;
    row << config << "," << scenario << "," << seed << "," << nodes << "," << Num(speed) << ","
        << CsvQuote(params.str()) << "," << NumOrEmpty(pdr) << "," << NumOrEmpty(avgDelayMs) << ","
        << NumOrEmpty(p95DelayMs) << "," << NumOrEmpty(overhead) << ","
        << NumOrEmpty(routeDiscoveryMs) << "," << NumOrEmpty(minEnergy) << "," << g_cloudBytes << ","
        << NumOrEmpty(lossNoRoute) << "," << NumOrEmpty(hopsAvg) << "," << NumOrEmpty(linkRssi) << ","
        << NumOrEmpty(weakRelayShare);
    const std::string header =
        "config_type,scenario,seed,node_count,mobility_speed,params,pdr,avg_delay_ms,p95_delay_ms,"
        "overhead_ratio,route_discovery_ms,min_energy_pct,cloud_bandwidth_bytes,"
        "loss_no_route_ratio,hops_avg,link_rssi_avg_dbm,weak_relay_share";

    if (outPath.empty())
    {
        std::cout << header << "\n" << row.str() << "\n";
    }
    else
    {
        std::ofstream out(outPath);
        NS_ABORT_MSG_IF(!out, "cannot write " << outPath);
        out << header << "\n" << row.str() << "\n";
        if (g_config == SimConfig::kGatewayHeuristic || g_config == SimConfig::kCloudAssisted)
        {
            std::string eventsPath = outPath.substr(0, outPath.rfind(".csv")) + "_events.csv";
            std::ofstream ev(eventsPath);
            ev << "ts,event_type,payload\n";
            for (const GatewayEvent& e : g_events)
            {
                ev << Num(e.ts, 9) << "," << e.type << "," << e.payload << "\n";
            }
        }
    }
    std::cout << config << " seed=" << seed << " pdr=" << Num(pdr, 4) << " delay_ms="
              << Num(avgDelayMs, 4) << " overhead=" << Num(overhead, 4)
              << " route_discovery_ms=" << Num(routeDiscoveryMs, 4) << " no_route=" << Num(lossNoRoute, 3)
              << " hops=" << Num(hopsAvg, 3) << " weak_relay=" << Num(weakRelayShare, 3)
              << " events=" << g_events.size()
              << std::endl;

    Simulator::Destroy();
    return 0;
}
