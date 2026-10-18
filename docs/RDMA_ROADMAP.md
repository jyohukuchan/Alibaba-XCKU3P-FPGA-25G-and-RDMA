# RDMA research roadmap

An experimental FPGA IPv4 RoCEv2 RC WRITE sender is now hardware verified
against CX455A: finite 64 MiB receiver-verified payload at 24.264 Gbit/s
(FPGA time counter, initialization/drain included), plus tail and PSN-wrap
cases. Controlled ACK-loss retry, timeout and subsequent WRITE recovery also
pass on hardware. A newer combined image now also performs FPGA-initiated
native READ into protected256KiB local RAM, with actual all-byte PCIe BAR
readback, segmentation/tails/wrap/error-CLEAR recovery and same-image WRITE
regressions. See [READ results](ROCEV2_READ_RESULTS.md).
Native InfiniBand, inbound WRITE targets/READ responders and a general FPGA
verbs provider are not implemented.
See [the native evidence](../results/2026-10-18/rocev2-native-003.json) and
[fault/recovery evidence](../results/2026-10-18/rocev2-native-retry-recovery-003.json).
This roadmap is a development proposal, not a committed delivery schedule.

Active incremental work and its evidence are tracked separately in
[ROCEV2_PROGRESS.md](ROCEV2_PROGRESS.md). A successful host-software RXE
reference is not an FPGA RDMA capability claim.

The bounded WRITE/25G experimental milestone is now demonstrated, using the
pinned FPGA Network Stack transport and the documented integrity/control/
Corundum integration. Possible **future scope**, not currently promised:

1. Add protected inbound WRITE and an RDMA READ responder, with explicit memory isolation
   and wire/error tests rather than exposing arbitrary host DMA.
2. Design a host-facing DMA/verbs integration and expand beyond the current
   bounded FPGA-local pattern source.
3. Test multiple concurrent QPs, NAK/protection failures, congestion and more
   loss patterns; controlled ACK suppression is not full reliability coverage.
4. Investigate remaining MTU1500/TCP behavior. Sustained thermal or long
   bidirectional qualification requires a separate cooling/test decision;
   it was explicitly not part of the current finite hardware experiments.
5. Treat native InfiniBand as a separate, substantially different project;
   it is not enabled by renaming a RoCEv2/Ethernet build or changing one flag.

Future milestones should carry reproducible tests and precise claims. Do
not advertise an RDMA-capable release until an RDMA engine and corresponding
software/interoperability tests actually exist.
