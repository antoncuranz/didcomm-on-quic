package thesis.simulations.wireless_emulation;

import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import inet.networklayer.ipv4.RoutingTableRecorder;
import inet.node.ethernet.EthernetSwitch;
import inet.node.ethernet.EthernetLink;
import inet.node.ethernet.*;
import inet.node.inet.Router;
import inet.node.inet.StandardHost;
import inet.node.inet.WirelessHost;
import inet.node.inet.AdhocHost;
import inet.node.wireless.AccessPoint;
import ned.DatarateChannel;
import inet.physicallayer.wireless.ieee80211.packetlevel.Ieee80211ScalarRadioMedium;
import inet.physicallayer.wireless.common.contract.packetlevel.IRadioMedium;
import inet.visualizer.canvas.integrated.IntegratedCanvasVisualizer;
import inet.environment.common.PhysicalEnvironment;




network WirelessEmulation
{
    parameters:
        @display("bgb=706.428,339.264");
        bool enableIndy = default(false);
        int numIntermediates = default(0);
    submodules:
        indy1: Router if enableIndy {
            @display("p=350,124;i=device/accesspoint");
        }
        agent1: Router {
            @display("p=150,250;i=device/wifilaptop");
        }
        intermediates[numIntermediates]: Router {
            @display("p=350,250;i=device/wifilaptop");
        }
        agent2: Router {
            @display("p=550,250;i=device/wifilaptop");
        }
        radioMedium: Ieee80211ScalarRadioMedium {
            @display("p=60,40");
        }
        visualizer: IntegratedCanvasVisualizer {
            @display("p=60,110");
        }
        configurator: Ipv4NetworkConfigurator {
            @display("p=60,180");
        }
        physicalEnvironment: PhysicalEnvironment {
            @display("p=200,40");
        }
    connections allowunconnected:
}
