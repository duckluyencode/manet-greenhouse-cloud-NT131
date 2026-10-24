#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/aodv-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/energy-module.h"

using namespace ns3;

NS_LOG_COMPONENT_DEFINE ("CaarSimulation");

int main (int argc, char *argv[])
{
  uint32_t numRobots = 3;
  double simTime = 300.0;
  uint32_t seed = 1;
  std::string config = "no_cloud";

  CommandLine cmd;
  cmd.AddValue ("nodes", "Number of robot nodes", numRobots);
  cmd.AddValue ("seed", "Random seed", seed);
  cmd.AddValue ("config", "Configuration (no_cloud, local_optimized)", config);
  cmd.Parse (argc, argv);

  SeedManager::SetSeed(seed);

  // 1. Tạo node (1 Gateway + N Robots)
  NodeContainer gatewayNode;
  gatewayNode.Create (1);
  NodeContainer robotNodes;
  robotNodes.Create (numRobots);
  NodeContainer allNodes = NodeContainer (gatewayNode, robotNodes);

  // 2. Kênh truyền (Nhà kính: n = 4.63, sigma = 5)
  YansWifiChannelHelper channel = YansWifiChannelHelper::Default ();
  channel.AddPropagationLoss ("ns3::LogDistancePropagationLossModel",
                              "Exponent", DoubleValue (4.63),
                              "ReferenceDistance", DoubleValue (1.0),
                              "ReferenceLoss", DoubleValue (40.05));
  channel.AddPropagationLoss ("ns3::RandomPropagationLossModel",
                              "Variable", StringValue ("ns3::NormalRandomVariable[Mean=0.0|Variance=25.0]"));
  channel.SetPropagationDelay ("ns3::ConstantSpeedPropagationDelayModel");

  YansWifiPhyHelper phy;
  phy.SetChannel (channel.Create ());
  WifiMacHelper mac;
  mac.SetType ("ns3::AdhocWifiMac");
  WifiHelper wifi;
  wifi.SetStandard (WIFI_STANDARD_80211g);
  NetDeviceContainer devices = wifi.Install (phy, mac, allNodes);

// 3. Mobility (Gateway cố định, Robot dùng Waypoint)
  MobilityHelper mobility;
  mobility.SetMobilityModel ("ns3::ConstantPositionMobilityModel");
  mobility.Install (gatewayNode);
  
  mobility.SetMobilityModel ("ns3::WaypointMobilityModel");
  mobility.Install (robotNodes);

  Ptr<UniformRandomVariable> pauseTime = CreateObject<UniformRandomVariable> ();
  pauseTime->SetAttribute ("Min", DoubleValue (15.0));
  pauseTime->SetAttribute ("Max", DoubleValue (24.0));

  for (uint32_t i = 0; i < robotNodes.GetN (); ++i) {
    Ptr<WaypointMobilityModel> waypoints = robotNodes.Get (i)->GetObject<WaypointMobilityModel> ();
    double y_row = 3.3 * (i + 1); // Chia đều 3 hàng ray trong nhà kính 10m

    // T = 0s: Xuất phát
    waypoints->AddWaypoint (Waypoint (Seconds (0.0), Vector (0.0, y_row, 0.0)));
    
    // T = 100s: Đi 20m với vận tốc 0.2 m/s
    waypoints->AddWaypoint (Waypoint (Seconds (100.0), Vector (20.0, y_row, 0.0)));
    
    // Dừng làm việc 15-24s
    double pTime = pauseTime->GetValue();
    waypoints->AddWaypoint (Waypoint (Seconds (100.0 + pTime), Vector (20.0, y_row, 0.0)));
    
    // Quay lại gốc
    waypoints->AddWaypoint (Waypoint (Seconds (200.0 + pTime), Vector (0.0, y_row, 0.0)));
  }

// 4. Pin (Phân phối đều 20% - 100%)
  ns3::energy::EnergySourceContainer sources;
  Ptr<UniformRandomVariable> uv = CreateObject<UniformRandomVariable> ();
  uv->SetAttribute ("Min", DoubleValue (20.0));
  uv->SetAttribute ("Max", DoubleValue (100.0));

  BasicEnergySourceHelper basicSourceHelper;
  for (uint32_t i = 0; i < robotNodes.GetN (); ++i) {
    basicSourceHelper.Set ("BasicEnergySourceInitialEnergyJ", DoubleValue (uv->GetValue ()));
    sources.Add (basicSourceHelper.Install (robotNodes.Get (i)));
  }

  // 5. Định tuyến AODV
  AodvHelper aodv;
  InternetStackHelper stack;
  stack.SetRoutingHelper (aodv);
  stack.Install (allNodes);

  Ipv4AddressHelper address;
  address.SetBase ("10.0.0.0", "255.255.255.0");
  Ipv4InterfaceContainer interfaces = address.Assign (devices);

  // 6. Traffic (Robot -> Gateway, UDP 128B mỗi 1s)
  uint16_t port = 9;
  UdpServerHelper server (port);
  ApplicationContainer serverApp = server.Install (gatewayNode.Get (0));
  serverApp.Start (Seconds (1.0));
  serverApp.Stop (Seconds (simTime));

  for (uint32_t i = 0; i < numRobots; ++i) {
    UdpClientHelper client (interfaces.GetAddress (0), port);
    client.SetAttribute ("MaxPackets", UintegerValue (900));
    client.SetAttribute ("Interval", TimeValue (Seconds (1.0)));
    client.SetAttribute ("PacketSize", UintegerValue (128));
    
    ApplicationContainer clientApp = client.Install (robotNodes.Get (i));
    clientApp.Start (Seconds (2.0 + i * 0.1)); 
    clientApp.Stop (Seconds (simTime));
  }

  // 7. FlowMonitor
  FlowMonitorHelper flowmon;
  Ptr<FlowMonitor> monitor = flowmon.InstallAll ();

  Simulator::Stop (Seconds (simTime));
  Simulator::Run ();
  monitor->SerializeToXmlFile ("caar-flowmon.xml", true, true);
  
  // Lọc FlowMonitor để chỉ tính luồng dữ liệu UDP của ứng dụng
  monitor->CheckForLostPackets ();
  Ptr<Ipv4FlowClassifier> classifier = DynamicCast<Ipv4FlowClassifier> (flowmon.GetClassifier ());
  std::map<FlowId, FlowMonitor::FlowStats> stats = monitor->GetFlowStats ();
  
  uint32_t txUdp = 0, rxUdp = 0;
  for (auto const &stat : stats) {
    Ipv4FlowClassifier::FiveTuple t = classifier->FindFlow (stat.first);
    // Chỉ đếm các gói có đích đến là cổng UDP 9, bỏ qua AODV spam
    if (t.destinationPort == port) { 
      txUdp += stat.second.txPackets;
      rxUdp += stat.second.rxPackets;
    }
  }
  
  std::cout << "--- KẾT QUẢ MÔ PHỎNG (Luồng UDP - Cấu hình " << config << ") ---\n";
  std::cout << "Tổng gói UDP gửi (Tx): " << txUdp << "\n";
  std::cout << "Tổng gói UDP nhận (Rx): " << rxUdp << "\n";
  std::cout << "PDR: " << (txUdp > 0 ? (rxUdp * 100.0 / txUdp) : 0) << " %\n";
  
  Simulator::Destroy ();
  
  return 0;
}