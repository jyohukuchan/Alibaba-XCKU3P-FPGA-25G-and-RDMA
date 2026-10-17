# Hardware and safe bring-up

## Tested setup

| Component | Tested configuration |
| --- | --- |
| FPGA card | Alibaba AS02MC04 / R1291-F9003-02 family |
| FPGA target | `xcku3p-ffvb676-1-e`, JTAG ID `0x04a63093` |
| FPGA host interface | PCIe Gen3 x8, Corundum mqnic |
| Reference clock | Fixed 156.25 MHz GTY reference |
| Peer | ConnectX-4 CX455A, HPE OEM firmware 12.24.1000 |
| Connection | CX455A QSFP28 → QSA28 → 1 m passive SFP28 DAC → FPGA SFP2 |
| Ethernet | Forced 25,000 Mb/s, full duplex, autoneg off, FEC off |
| Test OS | Ubuntu 24.04.4, Linux 6.17.0-1033-oem |
| Host | Dell Precision T7610, dual Xeon E5-2650 v2, 192 GB RAM |

Only the connected FPGA port was traffic-tested. This is not evidence that
both ports, every cable, FEC mode or every board speed grade are supported.
The board's exact device marking should be checked; do not assume a card
sold under a similar listing has the same pinout or speed grade.

## Programming is deliberately not automated

The recorded experiment used a Digilent-compatible FTDI JTAG adapter and
openFPGALoader at 1 MHz, with the explicit **`--write-sram`** option. Its
`-f` option selects flash programming and must not be substituted.

Before any SRAM reconfiguration:

1. Stop traffic and identify the exact FPGA PCIe BDF and its upstream bridge
   using `lspci -Dnnk`, `lspci -t`, sysfs and driver/netdev associations.
2. Verify that removing/rescanning that device and bridge cannot affect your
   management NIC, storage or another PCIe endpoint. Do not guess addresses.
3. Keep a known-good image and restoration notes locally. Quiesce the FPGA
   driver/netdev and remove only that FPGA endpoint before programming.
4. Select the exact JTAG adapter by serial and verify JTAG ID `0x04a63093`.
   Program SRAM only. Check DONE/EOS and configuration/CRC status.
5. Rescan only the verified exclusive bridge, then verify Ethernet class
   `020000`, mqnic binding, BARs, PCIe speed/width and AER before traffic.
6. Restore the intended test namespaces, addresses and MTUs; verify peer
   25G link speed and actual FPGA clock counters before load.

This procedure was performed without a host reboot in the recorded setup.
It is not a guarantee that hot reconfiguration is safe on another topology.
Power loss discards the SRAM image; the card loads whatever was already in
its flash, which is not guaranteed to be a particular fallback image.

**Do not run the dependency's `tools/drp_gty_tuning.py` as-is.** Its hardcoded
PCIe target can identify an unrelated device on another host. Likewise, the
dependency Makefile contains flash assumptions that must not be applied to
this card without a separate review. No speculative DRP tuning was needed.

## Proving native 25G

In this mqnic driver version, `ethtool` on the FPGA does not expose a speed
field. Use independent evidence:

- peer `ethtool` reports `25000Mb/s` and link detected;
- connected-port TX/RX clocks measure approximately 390.625 MHz;
- actual packet transfers exceed 10 Gbit/s.

For the recorded connected interface, those clock counters were CH2/CH3.
An unused RX clock is not evidence of link speed. Determine channel mapping
on your own design before changing the test configuration.

## Cooling and temperature

The initial 10G configuration was around 83°C with the workstation's original
fan policy. Setting the Dell T7610's BIOS fan-speed option to High through
Dell's official libsmbios tools reduced the observed temperature substantially.
The native-25G finite load test then remained below approximately 55°C.
This does not isolate power consumption, measure ambient temperature, or
certify a different design/load/host. Maintain adequate airflow and monitor.

`scripts/read_temperature.sh` takes read-only SYSMONE4 samples via OpenOCD.
Set `AS02_JTAG_SERIAL` explicitly; optionally set `OPENOCD_BIN` to a supported
OpenOCD executable. The adapter profile is specifically Digilent-compatible
FTDI `0403:6014`, channel 0, using the recorded wiring. It is not universal.

```bash
AS02_JTAG_SERIAL=YOUR_ADAPTER_SERIAL bash scripts/read_temperature.sh
```

The reader can require USB permissions or passwordless sudo. Do not run it
concurrently with programming, Vivado Hardware Manager or another JTAG client.
It checks the TAP ID and limits SYSMON accesses to approved status addresses.
JTAG scans are not FPGA configuration writes, but still require exclusive
access to the cable. The one-shot reader is not a monitoring service or an
automatic thermal shutdown mechanism.

The original experiment used a temporary test guard with an 85°C preflight
limit and 90°C cutoff. Those were conservative experiment controls, not
manufacturer ratings. Public traffic-test helpers do not replace a properly
reviewed thermal supervisor and must not be run without monitoring.
