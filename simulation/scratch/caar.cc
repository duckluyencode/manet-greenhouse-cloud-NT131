// CAAR — kịch bản NS-3 cho 4 cấu hình (tài liệu đồ án mục 4–7, 10).
//
//   no_cloud           AODV gốc (jitter U(0, 10) ms khi rebroadcast RREQ)
//   local_optimized    delayed RREQ forwarding, trọng số cố định 0,4 / 0,3 / 0,3
//   gateway_heuristic  Gateway tự chạy heuristic mục 7.2 mỗi T giây, không qua WAN
//   cloud_assisted     Cloud chạy heuristic mỗi T giây qua kênh WAN (RTT hằng số,
//                      mặc định 40 ms); Gateway hạ cấp 3 mức + TTL khi mất cloud (mục 7.3)
//
// Cài vào ns-3.48 bằng simulation/install.sh (áp patch AODV và chép vào scratch/caar/).
//   ./ns3 run "caar --config=cloud_assisted --seed=1 --nodes=10
//       --waypoints=contracts/waypoints/10_1.csv --channel=contracts/channel.json
//       --out=results/raw/cloud_assisted_baseline_1.csv"
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
// --netsimulyzer=<file.json> ghi cảnh 3D cho NetSimulyzer (cần contrib/netsimulyzer): nhà kính
// với lối đi và ray, đường AODV của từng robot về Gateway, biểu đồ PDR / pin / mức Gateway và
// log sự kiện Gateway. Cả hai chỉ đọc trạng thái mô phỏng nên CSV kết quả không đổi.
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

#if __has_include("ns3/netsimulyzer-module.h")
#include "ns3/netsimulyzer-module.h"
#define CAAR_HAS_NETSIMULYZER 1
#else
#define CAAR_HAS_NETSIMULYZER 0
#endif

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
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
// Ngưỡng thu thấp nhất chấp nhận: ngưỡng phát hiện preamble mặc định của ns-3 (-82 dBm).
constexpr double kMinRxSensitivityDbm = -82.0;
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
std::ostringstream g_animPositions; // bản ghi <nu p="p"> tự ghi, chèn vào file NetAnim khi kết thúc
std::vector<Vector> g_animLastPos;

std::vector<Ptr<Node>> g_nodes; // 0 = Gateway, 1..N = robot
std::vector<Ipv4Address> g_ip;
std::map<Mac48Address, uint32_t> g_macToIdx;
std::map<Ipv4Address, uint32_t> g_ipToIdx;
std::vector<std::map<uint32_t, LinkRssi>> g_rssi;
std::vector<double> g_energyPct;
std::vector<Ptr<Socket>> g_robotSockets;
std::vector<uint32_t> g_seq;
std::map<uint32_t, Telemetry> g_telemetry;

Ptr<UniformRandomVariable> g_jitterRv;

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

// Như JsonNumber nhưng trả giá trị mặc định khi thiếu khóa.
double
JsonNumberOr(const std::string& text, const std::string& key, double fallback)
{
    return text.find("\"" + key + "\"") == std::string::npos ? fallback : JsonNumber(text, key);
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
// Cảnh 3D NetSimulyzer (--netsimulyzer). Chỉ đọc trạng thái: không tạo biến ngẫu nhiên, không
// gửi gói hay đổi bảng định tuyến (in bảng AODV làm trên bản sao), nên CSV kết quả giữ nguyên.
// ---------------------------------------------------------------------------

#if CAAR_HAS_NETSIMULYZER

constexpr uint32_t kNoRoute = std::numeric_limits<uint32_t>::max();
constexpr double kVizPdrBucketS = 10;

struct Viz
{
    Ptr<netsimulyzer::Orchestrator> orchestrator;
    std::vector<Ptr<netsimulyzer::NodeConfiguration>> node; // 0 = Gateway
    std::vector<Ptr<netsimulyzer::LogicalLink>> route;      // robot i -> hop kế tiếp về Gateway
    std::vector<uint32_t> nextHop;
    std::vector<uint64_t> sent;      // gói dữ liệu theo khung 10 s của thời điểm gửi
    std::vector<uint64_t> delivered; // ... tới Gateway
    Ptr<netsimulyzer::XYSeries> pdr;
    Ptr<netsimulyzer::XYSeries> routed;
    Ptr<netsimulyzer::XYSeries> minBattery;
    Ptr<netsimulyzer::XYSeries> level; // chỉ có ở gateway_heuristic và cloud_assisted
    Ptr<netsimulyzer::LogStream> gatewayLog;
    Ptr<netsimulyzer::LogStream> routeLog;
};

std::unique_ptr<Viz> g_viz;

netsimulyzer::Color3
BatteryColor(double pct)
{
    double e = pct / 100.0;
    return {uint8_t(220 * (1 - e)), uint8_t(180 * e + 20), 40};
}

// Mức 1 xanh dương, mức 2 cam (dùng cache), mức 3 đỏ (bộ cân bằng), như NetAnim.
netsimulyzer::Color3
LevelColor(int level)
{
    return level == 1 ? netsimulyzer::BLUE : level == 2 ? netsimulyzer::ORANGE : netsimulyzer::RED;
}

std::string
SecondsLabel(double t)
{
    std::ostringstream os;
    os << std::fixed << std::setprecision(1) << t << " s";
    return os.str();
}

// Hop kế tiếp của robot về Gateway theo bảng AODV (route UP), hoặc kNoRoute.
uint32_t
NextHopToGateway(uint32_t robot)
{
    Ptr<aodv::RoutingProtocol> routing =
        DynamicCast<aodv::RoutingProtocol>(g_nodes[robot]->GetObject<Ipv4>()->GetRoutingProtocol());
    std::ostringstream table;
    routing->PrintRoutingTable(Create<OutputStreamWrapper>(&table), Time::S);
    std::ostringstream gateway;
    gateway << g_ip[0];
    std::istringstream in(table.str());
    std::string line;
    while (std::getline(in, line))
    {
        std::istringstream fields(line);
        std::string dst;
        std::string hop;
        std::string iface;
        std::string flag;
        if (fields >> dst >> hop >> iface >> flag && dst == gateway.str() && flag == "UP")
        {
            auto it = g_ipToIdx.find(Ipv4Address(hop.c_str()));
            return it == g_ipToIdx.end() ? kNoRoute : it->second;
        }
    }
    return kNoRoute;
}

std::string
HopName(uint32_t idx)
{
    return idx == 0 ? "Gateway" : "r" + std::to_string(idx);
}

// Mỗi giây: vẽ lại đường robot -> hop kế tiếp (xanh dương: thẳng tới Gateway, cam: qua robot khác).
void
VizRoutes()
{
    Viz& v = *g_viz;
    uint32_t routed = 0;
    for (uint32_t i = 1; i <= g_nRobots; ++i)
    {
        uint32_t hop = NextHopToGateway(i);
        if (hop != kNoRoute)
        {
            ++routed;
        }
        if (hop == v.nextHop[i])
        {
            continue;
        }
        if (hop == kNoRoute)
        {
            v.route[i]->Deactivate();
            v.routeLog->Write(SecondsLabel(Simulator::Now().GetSeconds()) + "  r" + std::to_string(i) +
                              " mất đường\n");
        }
        else
        {
            netsimulyzer::Color3 color = hop == 0 ? netsimulyzer::BLUE : netsimulyzer::ORANGE;
            if (!v.route[i])
            {
                v.route[i] = CreateObject<netsimulyzer::LogicalLink>(v.orchestrator,
                                                                     g_nodes[i]->GetId(),
                                                                     g_nodes[hop]->GetId(),
                                                                     color);
            }
            else
            {
                v.route[i]->SetNodes(g_nodes[i]->GetId(), g_nodes[hop]->GetId());
                v.route[i]->SetColor(color);
                v.route[i]->Activate();
            }
            v.routeLog->Write(SecondsLabel(Simulator::Now().GetSeconds()) + "  r" + std::to_string(i) +
                              " -> " + HopName(hop) + "\n");
        }
        v.nextHop[i] = hop;
    }
    v.routed->Append(Simulator::Now().GetSeconds(), routed);
    Simulator::Schedule(Seconds(1), &VizRoutes);
}

// Mỗi 5 s: màu và nhãn robot theo pin, điểm "pin thấp nhất".
void
VizRobots()
{
    Viz& v = *g_viz;
    double minEnergy = 100;
    for (uint32_t i = 1; i <= g_nRobots; ++i)
    {
        v.node[i]->SetBaseColor(BatteryColor(g_energyPct[i]));
        v.node[i]->SetName("r" + std::to_string(i) + " " + std::to_string(std::lround(g_energyPct[i])) +
                           "%");
        minEnergy = std::min(minEnergy, g_energyPct[i]);
    }
    v.minBattery->Append(Simulator::Now().GetSeconds(), minEnergy);
    Simulator::Schedule(Seconds(5), &VizRobots);
}

// Mỗi 10 s: PDR của gói gửi trong khung 10 s trước đó (chờ thêm 10 s cho gói tới nơi).
void
VizPdr()
{
    Viz& v = *g_viz;
    double now = Simulator::Now().GetSeconds();
    long bucket = std::lround(now / kVizPdrBucketS) - 2;
    if (bucket >= 0 && size_t(bucket) < v.sent.size() && v.sent[bucket] > 0)
    {
        v.pdr->Append((bucket + 1) * kVizPdrBucketS, double(v.delivered[bucket]) / v.sent[bucket]);
    }
    Simulator::Schedule(Seconds(kVizPdrBucketS), &VizPdr);
}

void
VizOnSend(uint32_t robot)
{
    if (!g_viz)
    {
        return;
    }
    size_t bucket = size_t(Simulator::Now().GetSeconds() / kVizPdrBucketS);
    if (bucket < g_viz->sent.size())
    {
        ++g_viz->sent[bucket];
    }
    g_viz->node[robot]->Transmit(MilliSeconds(300), 2.0, netsimulyzer::GRAY_30);
}

void
VizOnDelivered(Time txTime)
{
    if (!g_viz)
    {
        return;
    }
    size_t bucket = size_t(txTime.GetSeconds() / kVizPdrBucketS);
    if (bucket < g_viz->delivered.size())
    {
        ++g_viz->delivered[bucket];
    }
}

void
VizOnGatewayEvents(const std::vector<std::string>& events, const std::string& payload)
{
    if (!g_viz || events.empty())
    {
        return;
    }
    Viz& v = *g_viz;
    double now = Simulator::Now().GetSeconds();
    int level = static_cast<int>(g_gateway->level());
    for (const std::string& e : events)
    {
        v.gatewayLog->Write(SecondsLabel(now) + "  " + e +
                            (e == caar::kParamUpdate ? "  " + payload : std::string()) + "  (L" +
                            std::to_string(level) + ")\n");
    }
    if (v.level)
    {
        v.level->Append(now, level);
    }
    v.node[0]->SetName("Gateway L" + std::to_string(level));
    v.node[0]->SetBaseColor(LevelColor(level));
}

// Đặt tên/màu ban đầu ở t = 0, sau khi Orchestrator dựng xong cảnh.
void
VizStart()
{
    g_viz->node[0]->SetName("Gateway L1");
    g_viz->node[0]->SetBaseColor(LevelColor(1));
    VizRobots();
}

Ptr<netsimulyzer::XYSeries>
VizSeries(const std::string& name,
          const std::string& yAxis,
          netsimulyzer::Color3 color,
          netsimulyzer::XYSeries::ConnectionType connection,
          double yMax,
          double duration)
{
    auto s = CreateObject<netsimulyzer::XYSeries>(g_viz->orchestrator);
    s->SetAttribute("Name", StringValue(name));
    s->SetAttribute("Legend", StringValue(name));
    s->SetAttribute("Color", netsimulyzer::Color3Value(color));
    s->SetAttribute("Connection", EnumValue(connection));
    s->GetXAxis()->SetAttribute("Name", StringValue("Thời gian (s)"));
    s->GetXAxis()->SetAttribute("BoundMode", EnumValue(netsimulyzer::ValueAxis::BoundMode::Fixed));
    s->GetXAxis()->SetAttribute("Minimum", DoubleValue(0));
    s->GetXAxis()->SetAttribute("Maximum", DoubleValue(duration));
    s->GetYAxis()->SetAttribute("Name", StringValue(yAxis));
    s->GetYAxis()->SetAttribute("BoundMode", EnumValue(netsimulyzer::ValueAxis::BoundMode::Fixed));
    s->GetYAxis()->SetAttribute("Minimum", DoubleValue(0));
    s->GetYAxis()->SetAttribute("Maximum", DoubleValue(yMax));
    return s;
}

void
VizArea(const Rectangle& bounds,
        netsimulyzer::Color3 fill,
        double z,
        const std::string& name,
        bool border)
{
    auto a = CreateObject<netsimulyzer::RectangularArea>(g_viz->orchestrator, bounds);
    a->SetAttribute("Fill", EnumValue(netsimulyzer::RectangularArea::DrawMode::Solid));
    a->SetAttribute("FillColor", netsimulyzer::Color3Value(fill));
    a->SetAttribute("Height", DoubleValue(z));
    a->SetAttribute("Name", StringValue(name));
    if (border)
    {
        a->SetAttribute("BorderColor", netsimulyzer::Color3Value(netsimulyzer::GRAY_60));
    }
    else
    {
        a->SetAttribute("Border", EnumValue(netsimulyzer::RectangularArea::DrawMode::Hidden));
    }
}

void
SetupViz(const std::string& path, const std::string& layout, double duration, bool gatewayLevels)
{
    g_viz = std::make_unique<Viz>();
    Viz& v = *g_viz;
    v.orchestrator = CreateObject<netsimulyzer::Orchestrator>(path);
    v.orchestrator->SetAttribute("MobilityPollInterval", TimeValue(MilliSeconds(500)));

    // Nhà kính 1 ha theo layout.json: nền, lối đi giữa (trục x) và ray hai bên lối đi.
    auto [width, depth] = JsonPair(layout, "greenhouse_m");
    double aisleMin = JsonNumber(layout, "y_min");
    double aisleMax = JsonNumber(layout, "y_max");
    double firstX = JsonNumber(layout, "first_x");
    double spacing = JsonNumber(layout, "spacing_m");
    int perSide = int(JsonNumber(layout, "per_side"));
    VizArea(Rectangle(0, width, 0, depth), {196, 228, 182}, 0, "Nhà kính", true);
    VizArea(Rectangle(0, width, aisleMin, aisleMax), {205, 200, 190}, 0.02, "Lối đi giữa", false);
    for (int k = 0; k < perSide; ++k)
    {
        double x = firstX + k * spacing;
        VizArea(Rectangle(x - 0.15, x + 0.15, aisleMax, depth), {110, 110, 110}, 0.04, "Ray", false);
        VizArea(Rectangle(x - 0.15, x + 0.15, 0, aisleMin), {110, 110, 110}, 0.04, "Ray", false);
    }

    netsimulyzer::NodeConfigurationHelper gateway(v.orchestrator);
    gateway.Set("Model", netsimulyzer::models::CELL_TOWER_POLE_VALUE);
    gateway.Set("Height", netsimulyzer::OptionalValue<double>(4));
    gateway.Install(g_nodes[0]);

    netsimulyzer::NodeConfigurationHelper robot(v.orchestrator);
    robot.Set("Model", netsimulyzer::models::LAND_DRONE_VALUE);
    robot.Set("Height", netsimulyzer::OptionalValue<double>(0.8));
    robot.Set("EnableMotionTrail", BooleanValue(true));
    for (uint32_t i = 1; i <= g_nRobots; ++i)
    {
        robot.Install(g_nodes[i]);
    }
    for (uint32_t i = 0; i <= g_nRobots; ++i)
    {
        v.node.push_back(g_nodes[i]->GetObject<netsimulyzer::NodeConfiguration>());
    }
    v.route.resize(g_nRobots + 1);
    v.nextHop.assign(g_nRobots + 1, kNoRoute);
    size_t buckets = size_t(std::ceil(duration / kVizPdrBucketS)) + 1;
    v.sent.assign(buckets, 0);
    v.delivered.assign(buckets, 0);

    using Conn = netsimulyzer::XYSeries::ConnectionType;
    v.pdr = VizSeries("PDR (khung 10 s)", "PDR", netsimulyzer::DARK_GREEN, Conn::Line, 1, duration);
    v.routed = VizSeries("Robot có đường AODV về Gateway",
                         "Số robot",
                         netsimulyzer::BLUE,
                         Conn::StepFloor,
                         g_nRobots,
                         duration);
    v.minBattery =
        VizSeries("Pin thấp nhất (%)", "Pin (%)", netsimulyzer::DARK_RED, Conn::Line, 100, duration);
    v.gatewayLog = CreateObject<netsimulyzer::LogStream>(v.orchestrator);
    v.gatewayLog->SetAttribute("Name", StringValue("Gateway"));
    v.routeLog = CreateObject<netsimulyzer::LogStream>(v.orchestrator);
    v.routeLog->SetAttribute("Name", StringValue("Định tuyến AODV"));
    if (gatewayLevels)
    {
        v.level = VizSeries("Mức hạ cấp Gateway",
                            "Mức",
                            netsimulyzer::DARK_ORANGE,
                            Conn::StepFloor,
                            3,
                            duration);
        v.level->Append(0, 1);
    }

    Simulator::Schedule(Seconds(0), &VizStart);
    Simulator::Schedule(Seconds(1), &VizRoutes);
    Simulator::Schedule(Seconds(2 * kVizPdrBucketS), &VizPdr);
}

#else

void
VizOnSend(uint32_t)
{
}

void
VizOnDelivered(Time)
{
}

void
VizOnGatewayEvents(const std::vector<std::string>&, const std::string&)
{
}

void
SetupViz(const std::string&, const std::string&, double, bool)
{
    NS_ABORT_MSG("--netsimulyzer needs the NetSimulyzer module in ns-3 contrib/netsimulyzer "
                 "(simulation/vm/setup-ubuntu.sh --netsimulyzer)");
}

#endif

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
    VizOnSend(r);
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
        VizOnDelivered(txTime);
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
    VizOnGatewayEvents(events, payload);
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
        Time rtt = MilliSeconds(g_wanConstantRttMs);
        if (outage || rtt >= g_cloudTimeout)
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

// Vị trí robot cho NetAnim, mỗi giây trong cả lượt chạy. AnimationInterface chỉ ghi vị trí trong
// cửa sổ --netanim-start..stop, và cả trong cửa sổ cũng bỏ sót phần lớn: mỗi lần node gửi gói nó
// cập nhật vị trí đã lưu mà không ghi ra file.
void
RecordAnimPositions()
{
    for (uint32_t i = 1; i <= g_nRobots; ++i)
    {
        Vector p = g_nodes[i]->GetObject<MobilityModel>()->GetPosition();
        if (Simulator::Now().IsZero() || CalculateDistance(p, g_animLastPos[i]) > 0.01)
        {
            g_animPositions << "<nu p=\"p\" t=\"" << Num(Simulator::Now().GetSeconds(), 7) << "\" id=\""
                            << g_nodes[i]->GetId() << "\" x=\"" << Num(p.x) << "\" y=\"" << Num(p.y)
                            << "\" />\n";
            g_animLastPos[i] = p;
        }
    }
    Simulator::Schedule(Seconds(1), &RecordAnimPositions);
}

// Chèn các bản ghi vị trí vào file NetAnim, sau khi AnimationInterface đã ghi </anim> và đóng file.
void
WriteAnimPositions(const std::string& path)
{
    std::ifstream in(path);
    std::stringstream buf;
    buf << in.rdbuf();
    in.close();
    std::string xml = buf.str();
    std::size_t end = xml.rfind("</anim>");
    NS_ABORT_MSG_IF(end == std::string::npos, "incomplete NetAnim file " << path);
    xml.insert(end, g_animPositions.str());
    std::ofstream(path) << xml;
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
    std::string outPath;
    std::string fixedWeights;
    std::string netanimPath;
    std::string netsimulyzerPath;
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
    cmd.AddValue("wan-rtt-ms", "RTT Gateway–Cloud (ms)", g_wanConstantRttMs);
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
    cmd.AddValue("netsimulyzer",
                 "Ghi cảnh 3D NetSimulyzer ra file JSON (trống = tắt)",
                 netsimulyzerPath);
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
    double txGainDbi = JsonNumberOr(channel, "tx_gain_dbi", 0);
    double rxGainDbi = JsonNumberOr(channel, "rx_gain_dbi", 0);

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

    std::string wanModel = g_config == SimConfig::kCloudAssisted ? "constant" : "none";

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
    phy.Set("TxGain", DoubleValue(txGainDbi));
    phy.Set("RxGain", DoubleValue(rxGainDbi));
    phy.Set("RxSensitivity", DoubleValue(rxSensDbm));
    // ns-3 bỏ mọi khung dưới ngưỡng phát hiện preamble (mặc định -82 dBm), bất kể
    // RxSensitivity; đặt cùng ngưỡng để độ nhạy trong channel.json có hiệu lực. Ngưỡng dưới
    // -82 dBm làm PHY của ns-3.48 có lúc dừng với "Invalid WifiPhy state RX", nên muốn tầm
    // xa hơn thì tăng công suất hoặc độ lợi anten.
    NS_ABORT_MSG_IF(rxSensDbm < kMinRxSensitivityDbm,
                    "rx_sensitivity_dbm " << rxSensDbm << " is below " << kMinRxSensitivityDbm
                                          << " dBm (ns-3 preamble detection threshold)");
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
    stream++; // stream này để trống, giữ nguyên số stream của các biến phía sau (results/ tái tạo được)
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
        g_animLastPos.assign(nodes + 1, Vector());
        RecordAnimPositions();
    }
    if (!netsimulyzerPath.empty())
    {
        SetupViz(netsimulyzerPath,
                 ReadFile(layoutPath),
                 duration,
                 g_config == SimConfig::kGatewayHeuristic || g_config == SimConfig::kCloudAssisted);
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

    Simulator::Destroy(); // NetSimulyzer ghi file JSON tại đây
#if CAAR_HAS_NETSIMULYZER
    g_viz.reset();
#endif
    if (anim)
    {
        anim.reset(); // ghi </anim> và đóng file
        g_anim = nullptr;
        WriteAnimPositions(netanimPath);
    }
    return 0;
}
