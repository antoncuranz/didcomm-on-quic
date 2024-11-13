package thesis.simulations.wireless_emulation;

import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import inet.networklayer.ipv4.RoutingTableRecorder;
import inet.node.ethernet.EthernetSwitch;
import inet.node.ethernet.EthernetLink;
import inet.node.ethernet.*;
import inet.node.inet.Router;
import inet.node.inet.StandardHost;
import inet.node.inet.WirelessHost;
import inet.node.wireless.AccessPoint;
import ned.DatarateChannel;
import inet.physicallayer.wireless.ieee80211.packetlevel.Ieee80211ScalarRadioMedium;
import inet.physicallayer.wireless.ieee80211.packetlevel.Ieee80211ScalarRadioMedium;
import inet.physicallayer.wireless.common.contract.packetlevel.IRadioMedium;
import inet.visualizer.canvas.integrated.IntegratedCanvasVisualizer;



network WirelessEmulation
{
    parameters:
        @display("bgb=706.428,339.264");
    types:
        channel ethline extends Eth100M
        {
            delay = 0 ms;
            //datarate = 50 Mbps;
        }
    submodules:
        indy1: Router {
            @display("p=350,50;i=device/smallrouter");
        }
        agent1: Router {
            @display("p=150,250;i=device/wifilaptop");
        }
        agent2: Router {
            @display("p=550,250;i=device/wifilaptop");
        }
        switch1: EthernetSwitch {
            @display("p=350,150");
        }
        ap1: AccessPoint {
            @display("p=230,210");
        }
        ap2: AccessPoint {
            @display("p=470,210");
        }
        radioMedium: Ieee80211ScalarRadioMedium {
            @display("p=75,50");
        }
        visualizer: IntegratedCanvasVisualizer {
            @display("p=75,118");
        }
    connections allowunconnected:
        indy1.ethg[1] <--> ethline <--> switch1.ethg++;
        ap1.ethg++ <--> ethline <--> switch1.ethg++;
        ap2.ethg++ <--> ethline <--> switch1.ethg++;
}
