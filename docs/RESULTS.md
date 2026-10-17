# Native 25GbE experiment: 2026-10-17 UTC

These results describe the historical **ECO image**, not a fresh build from
this publication. See [the build distinction](BUILD.md). Test times are UTC;
the hardware audit completed at 14:43:17 UTC (23:43:17 JST).

## Physical link and packets

- CX455A reports 25,000 Mb/s, full duplex, link detected, AN off and FEC off.
- Connected FPGA TX/RX clocks: 390.625280 / 390.633472 MHz at initial link;
  390.623232 / 390.633472 MHz after load.
- PCIe retrained/enumerated as Gen3 x8; Ethernet class `020000`, mqnic driver.
- Each direction: 100 pings transmitted, 100 received, 0% loss.
- At MTU 1500 and 9000: ten ordinary pings per direction, all received.
- Full-MTU DF ping: ICMP payload 1472 and 8972 bytes respectively, three
  packets per direction at each MTU, all received without fragmentation.

## TCP throughput

iperf3 TCP, four parallel streams, 20 measured seconds plus three omitted
seconds. Receiver throughput is reported. Directions were measured
**sequentially**, not simultaneously.

| MTU | Direction | Receiver Gbit/s | TCP retransmissions |
| --- | --- | ---: | ---: |
| 1500 | CX455A → FPGA | 21.6096258164 | 1442 |
| 1500 | FPGA → CX455A | 12.8803721393 | 45 |
| 9000 | CX455A → FPGA | 24.7513834786 | 56 |
| 9000 | FPGA → CX455A | 24.5438610817 | 0 |

All four client JSON records had no error. The machine-readable
[TCP summary](../results/2026-10-17/tcp-summary.json) is derived from those
original records, retaining test parameters and sender/receiver aggregates.
The original full local logs are not uploaded wholesale.

CX4 `rx_crc_errors_phy`, `rx_symbol_err_phy`, `rx_pcs_symbol_err_phy` and
`tx_errors_phy` were zero both before and after the complete benchmark.
Final FPGA PCIe AER totals were zero for correctable, nonfatal and fatal errors.
Final FPGA netdev RX/TX errors and TX drops were zero; RX drops were **5**.
Port/queue counters can reset on MTU changes, so this is not a whole-run
aggregate drop count. Zero ping loss does **not** imply zero packet loss under
TCP load. Retransmissions and the MTU1500 bottleneck have not been isolated.

## Temperature

Dell BIOS Fan Speed was High, using Dell's official libsmbios tools; CPU
fans were approximately 4500 RPM and two other fans approximately 3300 RPM.
The earlier 10G state was around 83°C before this change. Native25 preflight
was around 52.7°C. During the finite guarded benchmark:

- 112 one-second temperature samples, minimum **52.55°C**, maximum **54.59°C**;
- last supervised sample **54.01°C**;
- post-test SYSMON maximum since reconfiguration **54.94°C**, current **53.25°C**;
- over-temperature flag 0; configuration STAT unchanged at `0x009079fc`.

The temporary guard rejected starting at ≥85°C and stopped its own load at
≥90°C or on sensor failure. It was stopped after the test, not installed as
a persistent service. Cooling for every future design/load is not certified.

## Static implementation

- Vivado Standard 2025.2; target **`xcku3p-ffvb676-1-e`**.
- Primary GTY 25.78125 Gbaud, reference 156.25 MHz, fractional QPLL feedback
  82.5; secondary 10.3125 Gbaud remains configured; core Ethernet width 128.
- All four native PHY TX/RX clocks constrained to 2.560 ns.
- Six independent two-stage VIO status synchronizers, `ASYNC_REG` present.
- Complete final timing summary passed: WNS **0.000 ns**, WHS **+0.008 ns**;
  zero setup/hold/pulse-width failing endpoints.
- All **113838/113838** routable nets fully routed, zero route errors.
- All **38** bus-skew checks passed; minimum reported slack **+1.478 ns**.
- Current DRC report: no Error/Critical Warning, **26 warnings** from generated
  IP/debug logic. No severity downgrades or functional false-path workaround.
- CDC report still contains 18 inherited Critical structures; [review](CDC.md).

Selected final report excerpts are in `results/2026-10-17/`. A cached
`report_methodology` section in the timing summary contains earlier warnings
and explicitly says it may be stale; it is not a fresh zero-warning
methodology result. Do not conflate passing final STA/DRC with a claim that
every tool advisory or CDC finding disappeared.

## Image identity and limits

Tested bitstream SHA-256:

```text
83ab714e93a7279d179d773df2ef3787d752cd466cdbf5f48176f395838c14d3
```

This identifies a retained local artifact; the binary is not distributed here.
It was programmed into volatile SRAM only. Configuration DONE/EOS were set,
CRC error was clear, and only the identified FPGA endpoint and its exclusive
bridge were removed/rescanned. Management networking was not changed.

Not established by this experiment: simultaneous full-duplex line rate,
dual-port performance, minimum-frame packet rate, long-duration reliability,
BER margin across temperature/cables, all FEC/AN modes, PTP accuracy, RDMA,
RoCEv2 or InfiniBand. No boot-time setup or flash update was installed.
