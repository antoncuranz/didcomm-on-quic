package thesis.simulations.wired_emulation;

import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import inet.networklayer.ipv4.RoutingTableRecorder;
import inet.node.ethernet.EthernetSwitch;
import inet.node.ethernet.EthernetLink;
import inet.node.ethernet.*;
import inet.node.inet.Router;
import inet.node.inet.StandardHost;
import ned.DatarateChannel;


network WiredEmulation
{
    types:
        channel ethline extends Eth100M
        {
            delay = 0 ms;
        }
    submodules:
        router1: Router {
            @display("p=350,50;i=device/smallrouter");
        }
        router2: Router {
            @display("p=150,250;i=device/smallrouter");
        }
        router3: Router {
            @display("p=550,250;i=device/smallrouter");
        }
        switch1: EthernetSwitch {
            @display("p=350,150");
        }
    connections allowunconnected:
        router1.ethg[1] <--> ethline <--> switch1.ethg++;
        router2.ethg[1] <--> ethline <--> switch1.ethg++;
        router3.ethg[1] <--> ethline <--> switch1.ethg++;
}
