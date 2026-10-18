# RoCEv2 endpoint development

The newer combined version2 READ/WRITE image is now SRAM-loaded and native
CX455A READ/all-byte PCIe BAR capture plus same-image WRITE regression are
verified. See [the READ implementation](read/README.md),
[native evidence](../results/2026-10-18/rocev2-rw-native-001.json) and
[results/use guide](../docs/ROCEV2_READ_RESULTS.md). It remains a bounded IPv4
initiator, not an inbound SEND/WRITE target, READ responder or verbs provider.
The WRITE-only build003 results below are historical and remain separately
scoped; their throughput/ACK-loss evidence is not transplanted onto version2.

**An experimental FPGA RoCEv2 RC WRITE sender is hardware verified.**
Build 003 passed the full physical gate and was SRAM-loaded; CX455A verified
every byte for 64B, 65B x3 with PSN wrap, 4KiB x3 and finite 64MiB cases.
The last case measured 24.264 Gbit/s payload using the FPGA counter,
initialization/drain included. No RXE substitutes for the FPGA in these tests.
The payload source is a bounded local FPGA pattern, not general host-memory
DMA; inbound WRITE targets/READ responders and an FPGA verbs provider are not implemented.
Controlled ACK-loss retry, expected watchdog failure and subsequent clean
WRITE recovery are also hardware verified. See
[fault/recovery evidence](../results/2026-10-18/rocev2-native-retry-recovery-003.json),
[native evidence](../results/2026-10-18/rocev2-native-003.json) and
[milestones](../docs/ROCEV2_PROGRESS.md); earlier development-stage observations
below must not be confused with a complete/production RDMA implementation.

## Offline checks

Ubuntu dependencies: `build-essential libibverbs-dev python3 iverilog`.

```sh
make -C rdma check
```

`host/rc_write_peer.c` is a finite RC WRITE test with explicit device, GID,
IPv4 control address, message size/count and PSN. It registers memory with a
full 32-bit rkey / 64-bit address, exchanges QP/MR metadata via TCP, configures
INIT/RTR/RTS, posts signalled RDMA WRITEs and checks all completion statuses.
The receiver compares **every byte** with a deterministic pattern. TCP only
exchanges control/verification messages; payload is transferred by RDMA.
Every message uses a distinct memory range, not just a repeatedly overwritten
buffer whose final contents could hide missed writes. Total allocation is
capped at 64 MiB and completion/control waits are bounded. This harness is not
a high-performance benchmark or a complete verbs provider.
The receiver now starts with the bitwise complement of each expected byte,
so even an omitted single-byte WRITE cannot match a constant sentinel by
coincidence. `build/rc_write_peer --self-test` verifies initialization over
the entire 65536-byte pattern period without opening an RDMA device. The
historical M1 capture used the earlier constant sentinel; it is not rerun or
relabeled as evidence of this change.

`host/rocev2_wire.py` decodes IPv4 RoCEv2 PCAPs and supplies an independent
ICRC/WRITE_ONLY golden model for hardware tests. Its CRC masking follows the
protocol behavior visible in [Linux RXE v6.17](https://github.com/torvalds/linux/blob/v6.17/drivers/infiniband/sw/rxe/rxe_icrc.c).
Tests reproduce an actual CX455A frame byte-for-byte and validate independently
observed CX455A/RXE ACK/WRITE frames, corruption detection, invariant masking,
padding, 24-bit PSNs, full-width keys/addresses and truncated-input rejection.
It supports plain IPv4, not IPv6/options/fragments or all RDMA opcodes.

## Finite reference test on the existing machine

This **temporarily creates a software endpoint**. The FPGA continues to run
the known native25 Ethernet image, and its existing mqnic networking carries
RXE packets. Successful RXE tests are never FPGA RDMA/offload evidence.

```sh
AS02_ALLOW_REFERENCE_TEST=YES \
AS02_TEMPERATURE_GUARD=/absolute/path/to/validated/run_with_temperature_guard.sh \
  bash rdma/scripts/reference_test.sh
```

The script is intentionally tied to the audited local BDFs, netdevs and
namespaces. It refuses an existing RXE device or test interface, checks the
live 25G peer link, requires a validated temperature guard, and uses only
the existing FPGA/CX455A test connection. It does not touch the management
NIC, reset a PCIe device, change fans, install a daemon or program FPGA flash.

Linux 6.17 RXE creates UDP sockets and performs IPv4 route lookup in
`init_net` ([kernel source](https://github.com/torvalds/linux/blob/v6.17/drivers/infiniband/sw/rxe/rxe_net.c)).
Creating RXE directly on the existing namespaced FPGA netdev was observed to
fail despite valid incoming RNIC packets. The test therefore creates only a
temporary `as02rxe0` macvlan on that netdev, moves that **new virtual child**
to the root namespace, and uses the separate `198.18.11.0/30` subnet with an
additional temporary CX455A address. The physical netdev, its original
`198.18.10.2/30` address and namespace stay unchanged. Actual RoCEv2 GID slots
are discovered rather than assumed. EXIT/INT/TERM cleanup removes the owned
RXE, macvlan and extra address. A forced power loss/SIGKILL cannot run traps;
inspect those exact temporary objects before removing any stale ones.

Eight sizes (1, 63, 64, 65, 4095, 4096, 4097, 8192 bytes), 16 writes each,
both directions, check padding and 4096-byte path-MTU segmentation. Capture
uses immediate mode to avoid losing buffered packets on exit. The final
auditor requires successful memory verification, sender completions, all
expected unique WRITE PSNs/payload lengths, correct full-width RETH keys and
successful ACKs. It rejects an incomplete packet capture. Raw PCAPs/logs are
ignored by Git; sanitized aggregate evidence belongs in `results/`.

## Hardware core probe (not an adopted dependency)

Candidate: [fpgasystems/fpga-network-stack](https://github.com/fpgasystems/fpga-network-stack),
revision `75c32bae73f5c336b5c46c9de35ae0cb9cb7cc1c`. Its standalone RoCEv2
build is stale: the generated configuration/testbench are missing, shift
helper template signatures do not match transport call sites, and `crc.cpp`
contains a second malformed copy of its contents. This is **not** a drop-in
working KU3P design.

`hls/fns-compat.patch` retains upstream notices, fixes helper instance
parameters and the QP constructor's truncated key argument, and removes the
duplicated CRC source (the surviving copy retains its full license header).
The debug record also needs a default constructor for modern HLS C simulation.
Small (4..32-entry) FIFO storage is explicitly mapped to SRLs for the KU3P
probe, without reducing FIFO depths or disabling transport/retry functions.
`hls/probe/rocev2_config.hpp` bridges the missing generated configuration.
It now specifies a 4000ps transport clock for integer-ceiling retry timer
constants, shared by C simulation and synthesis. The patch bounds timer
scan skips within the eight-entry table as well. Build 008 has the corrected
clock but its generated-RTL test exposed an ACK/scan RAM hazard: an ACK's
timeout extension could be overwritten by a stale scan. The patch now also
skips the hazard window on ACK updates. A new build and actual generated-RTL
regression are required; do not treat C-model success as proof of that fix.
Build 009 still exposes a stop/new-start RAM hazard. The current AS02 adapter
instead keeps the same eight entries in resettable registers, without the
false dependency declaration or scan-skip heuristic. Build 010 has II=1,
77 BRAM18K / 24471 LUT / 63887 FF in the full HLS estimate; whole-core timing
is still estimated at 4.043ns. Generated timer reset/retry tests, full-board
timing and real RNIC verification remain separate required gates.
The Tcl probe requires the exact revision plus applied patch; it creates a
new build directory without overwriting an old one:

```sh
git -C /path/to/fpga-network-stack apply \
  /absolute/path/to/this/repository/rdma/hls/fns-compat.patch
AS02_FNS_SOURCE=/path/to/fpga-network-stack \
AS02_HLS_BUILD=/new/absolute/build-directory \
  /path/to/Vitis/bin/vitis-run --mode hls --tcl rdma/hls/probe/synth.tcl
```

Target: `xcku3p-ffvb676-1-e`, 512-bit streams, eight QP table entries, 4 ns
target period, retransmission code enabled. Even a successful probe only
estimates the HLS block, **not** the complete board design. The candidate
currently disables internal CRC calculation/checking in favor of surrounding
logic; a real integration must implement/verify both TX and RX ICRC behavior.
The selected integration now supplies Ethernet framing/routing, metadata
packing, a Corundum synchronous-app bridge and guarded MAC drain. Build003
passes the full-board physical gate and finite native WRITE tests, including
a fully verified 64MiB case at 24.264Gbit/s. This does not qualify arbitrary
concurrent PHY/clock reconfiguration, fault recovery or sustained operation.
See [native evidence](../results/2026-10-18/rocev2-native-003.json).
The upstream RX/TX "IbvCount" registers count transport stream words, not
packets; do not use them as packet counts or RDMA completion counts.

Set `AS02_HLS_ACTION=csim` with a separate new build directory to run the
included C-model RX WRITE/ACK test. This is not RTL co-simulation: stream
backpressure, finite hardware FIFO capacity, CRC/protection and route timing
still need dedicated verification.

The actual patched timer can be tested without touching hardware:

```sh
python3 rdma/hls/probe/test_timer.py --fns-source /path/to/patched/fpga-network-stack \
  --vitis-include /path/to/Vitis/include --report /new/path/timer-cmodel.json
python3 rdma/hls/probe/test_timer_rtl.py --hls-build /path/to/probe-010 \
  --report /new/path/timer-rtl.json
```

The first runs the HLS C model under ASan/UBSan with real clock intervals;
the second simulates generated timer RTL and its actual RAM under ACK
restart/stop and output FIFO backpressure. Neither proves physical timing,
full transport recovery, or successful RNIC retries on the wire.

Use the current register-table build (010) for the complete timer regression;
the older BRAM-table builds are retained as failing reference cases. Long
Icarus runs may need `--timeout 1200`, which changes only the wall-clock
limit, not the protocol clock or assertions. The optional Verilator timing
backend is experimental: Debian 5.020 crashes in its coroutine runtime for
this bench and is not accepted as successful evidence.
The selected Icarus build-010 run passes 8621166 cycles / 26 retry events,
including all ACK/stop/restart phases and warm reset. This is still a timer
sub-block result, not full transport retry recovery or measured hardware.

The first probe generated RTL but estimated 998 BRAM18K units on a device
with 720. Capacity-preserving SRL mapping reduced this to 193, then **79**
when applied to all translation units. Estimated clock is still 4.043 ns against a 4.000 ns
target. Neither result is a complete-board place-and-route pass. The initial
64-byte WRITE/ACK C-model test passes; the emitted ACK still needs its
external ICRC. See the [recorded estimates](../results/2026-10-17/rocev2-hls-probe.json).

The external candidate's individual files retain their BSD-3-Clause notices.
This project's default BSD-2-Clause-Views license does not replace them.

## Integrity RTL and generated-transport integration

`rtl/rocev2_ipv4_icrc.v` is a 128-bit, IP-only, store-and-forward stage.
TX repairs the IPv4 checksum and appends ICRC; IP/UDP lengths on TX input
already include the future four-byte ICRC. RX validates the IPv4 checksum,
packet/UDP lengths, ICRC and upstream error marker before releasing **any**
word of a valid frame. RX retains ICRC for the HLS extractor. Both modes use
a 16 KiB frame FIFO with backpressure, not a single-buffer half-rate design.
Supported framing: unfragmented IPv4 without options, UDP destination 4791,
48..8192-byte IP packets, dense keep masks and four-byte RoCE padding.
The test reports distinguish rejection of malformed input from kernel/NIC loss.

The primitive CRC/FIFO/width-adapter blocks are the pinned Corundum tree's
MIT-licensed Alex Forencich modules; their headers remain unchanged. CRC
uses a parallel reflected IEEE matrix with the masked LRH seed and invariant
fields checked against real RNIC packets. Explicit `REDUCTION` style selects
the same matrix used by upstream's AUTO simulation implementation.

`rtl/rocev2_integrity_transport.v` connects RX integrity, 128→512 adaptation,
the generated transport, 512→128 adaptation, TX padding normalization and TX
integrity. It latches HLS
diagnostics only on their valid strobes. This transport submodule is **not
itself the board app**: it has no Ethernet header classification/framing;
the application
boundary below adds peer/QP isolation for an initiator's ACK input. Protected
memory/control are bounded by the controller below. Complete-board physical
and native retry evidence is recorded separately from this submodule test.

Offline integrity tests are included in `make -C rdma check`; they exercise
source/sink stalls, output stability, partial final words, checksum repair,
CRC/payload corruption, malformed masks/headers and whole-frame rejection.
The simulated large-frame payload capacity is 31.508 Gbit/s **assuming**
250 MHz; it is not routed timing or achieved network performance.

After the pinned HLS synthesis, test actual generated RTL (not C simulation):

```sh
python3 rdma/hls/probe/test_integrity_transport.py \
  --hls-build /path/to/completed-probe --direction rx
python3 rdma/hls/probe/test_integrity_transport.py \
  --hls-build /path/to/completed-probe --direction tx
```

RX test: two 64-byte WRITEs with a CRC-corrupt frame between them; exact
memory command/data checks and independently verified wire ACKs. TX test:
SQ request → local read command → pattern source → wire WRITE with full
32-bit key / 64-bit remote address → modeled RNIC ACK → completion metadata.
Network, command and data interfaces are stalled independently. Model ACKs
are not hardware interoperability evidence. The test explicitly drives reset
before the first clock, copies generated RAM initialization assets, treats
simulator errors as failures and checks unknown/stalled output behavior.

Physical integrity-block checks are separate and never program hardware:

```sh
vivado -mode batch -source rdma/scripts/ooc_integrity.tcl \
  -tclargs /new/absolute/output-directory 1
```

Use mode `0` for RX. The script saves a synthesis checkpoint and source/mode
identity before physical steps. A matching explicit `AS02_SYNTH_CHECKPOINT`
can resume physical verification in another new directory. This out-of-context
check is not full-board timing; synthesis success alone is not timing success.
`AS02_ROUTED_CHECKPOINT` instead resumes a matching routed checkpoint and
attempts post-route hold fixing without relaxing clock/I/O constraints. The
two resume options are mutually exclusive. Both setup and hold must pass;
the selected older physical results currently **fail**, not pass.
`scripts/inspect_ooc_timing.tcl ROUTED_DCP` diagnoses internal paths versus
virtual port paths without editing the checkpoint. It does not waive any
overall timing check. RX's optimized checksum predicate is exhaustively
tested for every 21-bit sum; fresh physical checks remain necessary.

## 128-bit Ethernet/NIC application boundary

`rtl/rocev2_ethernet_rx.v` buffers complete FCS-less Ethernet frames and keeps
all 97 host RX sideband bits. When enabled, plain IPv4/UDP destination 4791
is consumed here: only the configured MAC/IP peer's ACKs for the configured
local QP, within the eight-entry table, reach the IP integrity/transport
wrapper. Bad masks, MAC errors, wrong peers/QPs and oversized candidates are
dropped. Metadata reservations/oversize handling keep the frame/route FIFOs
aligned after faults. Configuration is sampled per frame; disable leaves
RoCE available to the host. VLAN/non-RoCE frames remain host traffic.
This is not ICRC validation: its output must pass the integrity wrapper.
Inbound WRITE/READ require a protected receiver and are not admitted yet.

`rtl/rocev2_ethernet_tx.v` prepends configured Ethernet addresses/type, then
arbitrates complete frames with normal host traffic. It preserves host TX
tags and filters generated packets' tag-zero MAC completions. This relies on
the pinned Corundum TX engine's tag-MSB=1 convention for real descriptors.
It does not implement Ethernet FCS; the downstream MAC does that.
Both sides stay 128 bits wide. These modules are connected to the actual
board APP/control interface through the bounded endpoint described below;
the selected build's native WRITE path is now hardware verified.

`make -C rdma check` includes three Ethernet RTL tests: peer/QP isolation,
full-sideband ordinary traffic, short/tail/oversize behavior, frame arbitration,
completion separation, queue wrap, malformed input and independent stalls.
The TX framing block's simulated payload capacity is 31.156 Gbit/s at an
assumed 250MHz, **not** hardware throughput or a timing proof. The pinned
generic framers retain upstream width/counter lint warnings at this width.

After the same HLS probe, exercise the complete Ethernet/integrity/transport
TX path with a modeled RNIC ACK and negative QP/CRC input tests:

```sh
python3 rdma/hls/probe/test_integrity_transport.py \
  --hls-build /path/to/completed-probe --direction tx --ethernet
```

This produces a complete independently checked Ethernet RDMA WRITE, rejects
both invalid ACKs before HLS, and consumes exactly one valid ACK. Hardware
QP/MR control, retries, queued bulk transfer and actual CX455A verification
are still required for the active goal.

## Finite WRITE engine and host registers (bounded initiator)

`rocev2_write_engine.v` issues disjoint WRITE_ONLY requests (1..4096 bytes,
1..65536 requests, total <=64MiB) into an explicitly configured peer MR.
It preserves the full 64-bit remote address and 32-bit key. Local QP is
2..7; the peer QP is a full 24-bit value. A fixed hardware window defaults to
32 unacknowledged requests; cumulative/duplicate ACKs and 24-bit PSN wrap are
handled. There is no software round trip per packet and no large FPGA buffer
needed to create/replay the deterministic payload. `rocev2_pattern_source.v`
serves only 1..4096-byte non-host commands entirely within that finite range,
including unaligned addresses/tails and retransmission rereads. Invalid reads
fail closed without producing data or any host DMA.

The pinned FNS context names are reversed relative to outgoing/incoming PSN:
`state_table` initializes `req_next_psn` from `remote_psn`, and `resp_epsn`
from `local_psn`. The wrapper therefore packs its own TX PSN in bits 79:56
and peer PSN in 103:80, rather than relying on tests where both happen to be
equal. Startup resets the core, waits for its free-list initialization,
sets QP/connection records and waits before posting work.

`rocev2_control.v` provides independent AW/W AXI-Lite channels, byte strobes,
stable stalled responses, and configuration locking. Register words are
32-bit little-endian; MAC/IP *values* use conventional numeric network order.

| Offset | Meaning |
| --- | --- |
| 0x00 / 0x04 | ID `0x524f4332` / version `0x00010000` |
| 0x08 | Low-byte commands: START=1, CLEAR=2, ABORT=4; mutually exclusive |
| 0x0c | Status: busy[0], done[1], failed[2], core-reset[3], TX-quiescent[4], halt-TX[5], RX-enabled[6], state[11:8] |
| 0x10 / 0x14 / 0x18 / 0x1c | Run error / issued / cumulatively acknowledged / total payload bytes |
| 0x20 / 0x24 / 0x28 | Elapsed cycles low/high / duplicate ACK count |
| 0x2c / 0x30 / 0x34 | Pattern read commands / supplied bytes low/high, preserved at terminal reset |
| 0x38 / 0x3c | Rejected AXI writes / last rejection reason |
| 0x40 / 0x44 | Local MAC low32/high16 |
| 0x48 / 0x4c | Peer MAC low32/high16 |
| 0x50 / 0x54 | Local / peer IPv4 |
| 0x58 / 0x5c | Local / peer QPN (24 bits) |
| 0x60 / 0x64 | Own TX / peer initial PSN (24 bits) |
| 0x68 / 0x6c | Peer rkey / bytes per WRITE |
| 0x70 / 0x74 | Peer MR base low/high32 |
| 0x78 / 0x7c | Granted peer MR extent low/high32 |
| 0x80 / 0x84 | WRITE count / overall watchdog cycles (default 250,000,000) |
| 0x90..0xcc | 16 supplied diagnostic words, snapshotted before terminal core reset |

States: 0 idle, 1 reset, 2 initialize, 3 configure QP, 4 settle, 5 run,
6 quiesce, 7 done, 8 failed, 9 validate. MR extent/overflow and total-byte
validation are pipelined while the transport remains reset; the original
multiply-plus-range-comparison path failed a real 4ns physical check.
Run error codes: 1 invalid configuration, 2 watchdog timeout, 3 invalid ACK
metadata, 4 memory fault/unexpected inbound write, 5 requested abort.
Control rejection reasons: 1 bad/readonly address, 2 locked/not ready,
3 unsupported command, 4 invalid Ethernet addressing. Configuration writes
while non-idle return SLVERR; they never change the active snapshot.

**Mandatory integration condition:** `halt_tx` must stop admission of *new*
engine Ethernet frames while allowing an already admitted frame to finish.
`tx_quiescent` must prove the admitted frames and physical transmit tail have
drained, not merely that the HLS output is momentarily idle. The engine waits
in state 6 before terminal status/reset, preserving AXIS valid under stalls.
Do not tie this signal high on hardware or free the peer MR before that gate.
MAC timestamp events alone are not proof that the last frame has ended.
`rocev2_tx_guard.v` now implements that injected-only admission/drain gate
before the Ethernet framer, using whole-NIC reset rather than core reset.
It retains a stalled output beat, drains accepted frames, tracks MAC SFD
completions and waits another 1024 core clocks (4.096us at 250MHz), longer
than an 8192-byte IP frame's complete wire interval at 25G. Its counter
capacity applies backpressure rather than wrapping. Missing completions do
not become success after a timeout; unexpected completions or framing-bound
violations latch a fault. Host traffic/completions bypass the guard.
Six unit cases check these boundaries and one-word-per-clock forwarding.
The complete-path RTL test connects the actual guard with modeled early
MAC SFD completions, replacing the former hard-coded quiescence signal.
The selected board integration has now passed conditional physical review
and finite native hardware completion/quiescence checks; see the native
evidence above. This does not prove safety against arbitrary configuration
changes or an indefinitely stalled physical drain.
The additional `test_mac_drain_rtl.py` test uses the actual MAC and CDC
primitives with a representative whole-frame FIFO, checking XGMII EOF,
independent Ethernet FCS and the delayed guard permission. It passes for
48/124/8192-byte inputs. That unit test alone is not a hardware-drain claim;
the separate native evidence covers only the tested finite operating cases.
The watchdog stops new SQ work; a stuck physical drain can intentionally
keep the controller busy instead of claiming safety.

### Missing upstream RoCE padding, now normalized

The candidate serializes 65-byte and similar payloads without required 0..3
padding bytes, BTH pad count, or padding in IP/UDP lengths. The first complete
65-byte engine integration correctly failed the strict integrity gate;
64-byte operation passed. `rocev2_tx_padding.v` now normalizes that specific
unpadded candidate ABI before TX integrity: append zeros and correct both
lengths and BTH count, then let integrity repair IPv4 checksum and append
ICRC. It does not relax RX checks, heal malformed keep masks or trust an
already-padded/mismatched header. Its single registered 128-bit stage accepts
one beat per cycle. Input errors are propagated so integrity rejects the
entire frame. Dedicated tests cover all tail positions, real input/output
stalls, malformed-input recovery and >25G simulated cycle capacity.

After HLS synthesis, exercise **actual generated RTL** using AXI-Lite setup,
the finite engine, bounded pattern source, padding/integrity/Ethernet and
modeled RNIC ACKs, with different local/peer PSNs:

```sh
python3 rdma/hls/probe/test_control_transport.py \
  --hls-build /path/to/completed-probe --message-bytes 65
python3 rdma/hls/probe/test_control_transport.py \
  --hls-build /path/to/completed-probe --message-bytes 4096
python3 rdma/hls/probe/test_control_transport.py \
  --hls-build /path/to/completed-probe --initial-psn 0xfffffe --ack-every 2
```

These are finite simulated transfers, not actual CX455A memory writes or a
25G RDMA throughput claim. The separate complete-board physical and native
registered-memory evidence above must not be inferred from these simulations.

### Actual board application and guarded build

`rtl/rocev2_endpoint.v` assembles the tested blocks. The derived
`fpga/mqnic_app_block.v` connects the endpoint only to synchronous SFP2/port 1,
preserves other paths, and exposes control through BAR2. All application DMA
descriptor outputs stay disabled. Reset/idle phases flush only queued engine
ACKs; the host RX/router and TX guard use whole-NIC reset, not per-run reset.
Diagnostics 0xc8 count flushed old-run ACKs; 0xcc packs guard fault[16] and
outstanding injected frames[15:0]. Ethernet/guard counters are cumulative from
whole-NIC reset, while HLS/pattern counters are captured per run.

Test the actual app, not only its individual connected blocks:

```sh
python3 rdma/hls/probe/test_control_transport.py --boundary app \
  --hls-build /path/to/probe-010 --message-bytes 65
```

An explicit build variant preserves the existing Ethernet-only configuration:

```sh
AS02_HLS_BUILD=/path/to/probe-010 bash fpga/build_25g_rocev2.sh
```

It refuses mismatched/unverified generated HLS or stale local source/test
identities before invoking a board build. Exact HLS initialization files are
copied only into the new synthesis run. The application ID is `0x41535232`;
BAR2 register 0 is `ROC2` (`0x524f4332`). The build still needs successful
full-board physical timing/DRC/CDC review and later finite temperature-guarded
CX455A memory verification. A successful input-provenance gate is **not** a
hardware/interoperability certificate. This helper never programs a device.

### Native initiator host control (finite WRITE hardware verified)

`host/fpga_write_client.py` controls the FPGA, while `rc_write_peer` in listen
mode owns the CX455A QP and its registered receiver memory. TCP transfers
only the 256-byte QP/MR descriptors and R/D/P readiness/verification bytes;
the Python client neither generates RDMA packets nor sends payload via TCP.
Its protocol cannot attest the remote verbs provider: native mlx5/CX455A
identity must be recorded separately, never inferred from a peer's P byte.
It programs the protected local pattern source for 1..4096-byte WRITEs,
1..65536 requests and <=64MiB total, then requires receiver byte verification.

Live access requires `AS02_ALLOW_FPGA_RDMA=YES`, the exact audited
`--bdf 0000:82:00.0`, PCI IDs/subsystem/class/mqnic identity, and the ROC2
BAR2 ID/version. An exclusive local lock prevents two such controllers from
running simultaneously. The client refuses a busy/nonquiescent device and
validates all peer widths, MR range, size/count and IPv4-mapped GID before
any START. Use the current actual test-netdev MACs/IPs and verified RoCEv2
GID index, not the simulation fixture MACs or an assumed index.

MMIO uses the normal [Linux PCI sysfs resource mapping](https://docs.kernel.org/PCI/sysfs-pci.html)
on this x86_64 host, with safe-register readback after posted writes as in
the kernel's [I/O ordering guidance](https://docs.kernel.org/6.11/driver-api/io_ordering.html).
The existing network driver stays bound; no device removal, rebinding,
firmware programming or fan change is performed by this control program.

After peer QP readiness, configuration writes are read back, START is issued,
and a finite watchdog/poll waits for acknowledged counts and TX quiescence.
Only then is D sent to ask the peer to verify/free its MR; P is mandatory
for success. Hardware counter rates include initialization and final drain,
and are distinct from total control-channel wall time. On failure or a
handled SIGINT/SIGTERM the client requests abort of its own run and polls
quiescence before returning. It never resets the NIC to claim success.
SIGKILL/power loss cannot execute cleanup. If quiescence cannot be proved,
the test fails and requires inspecting/recovering the FPGA; peer teardown
destroys its QP before deregistering memory. Never relabel such a case as a
successful/verified transfer.

The ten pure host tests include malformed descriptors, full 32-bit keys /
64-bit addresses, lost readiness, mismatched counters, peer memory failure,
busy-device refusal, timeout/interrupt abort and coherent 64-bit reads.
They use a register/protocol **model**, not a physical BAR, QP or MR.
Run them with `make -C rdma check-host`. Actual live tests must wait for
physical build/CDC review and use the existing temperature guard.

### Read-only native-path preflight

```sh
python3 rdma/host/native_preflight.py --read-application \
  --report rdma/logs/native-preflight.json
```

This performs only inventory/read commands on the two audited PCI devices
and dedicated test namespaces. It checks PCI IDs/drivers, netdev-to-BDF
identity, current unicast MACs and /30 addresses, MTU 9000, native mlx5 port
identity, active Ethernet link layer, peer 25Gb full duplex/no FEC, and the
actual matching IPv4-mapped RoCEv2 GID. Its GID index is discovered, not
assumed. The CX455A's PCI class is still `0x020700` (InfiniBand controller);
that label is not its current link mode. Conversely, mqnic currently reports
link presence without a speed, so the preflight does not invent that value.
The receiver still checks active RDMA MTU >=4096 with `ibv_query_port` later;
the inventory does not claim that from nonexistent MTU sysfs attributes.

Default operation never maps a BAR. `--read-application` optionally reads
ROC2 ID/version and known non-clearing status using an O_RDONLY/PROT_READ
BAR2 mapping, after PCI identity checks. An absent BAR2 is recorded normally
for the still-running Ethernet-only image. `--require-application` instead
refuses an absent/unknown/nonquiescent app before any future test may start.
No QP, traffic, MMIO write, programming, device reset, fan adjustment or
interface modification is performed. Passing this inventory is **not**
evidence of physical timing, safe temperature, or successful FPGA RDMA.
Ten pure fixture/mocked-I/O tests exercise these distinctions in `check-host`.

### Finite native hardware runner (four native cases exercised)

Only after the physical timing/DRC/CDC review, recorded SRAM programming,
device/driver recovery and an inspected ROC2 image, run one bounded case:

```sh
AS02_ALLOW_NATIVE_FPGA_RDMA_TEST=YES \
AS02_PHYSICAL_REVIEW_COMPLETE=YES \
AS02_TEMPERATURE_GUARD=/absolute/path/to/validated/run_with_temperature_guard.sh \
python3 rdma/host/native_test.py --message-bytes 64 --count 1
```

The physical-review flag is an **operator attestation**, not an automatic
timing/CDC certificate or proof of which bitstream was programmed. Keep the
actual build reports, source manifest, bitstream hash and programming record
with the resulting test directory. Do not set the flag merely to bypass a
failed gate. This runner never programs or recovers/rebinds a PCI device.

It checks the current application before starting JTAG and rechecks it under
the guard before creating a native `mlx5_0` receiver QP. The guard must refuse
starting >=85 C and stop on >=90 C, an over-temperature flag or sensor loss.
Its exact script hash and complete console output are recorded. Do not run
concurrently with a programmer/Hardware Manager using the JTAG adapter.

Both sides use the existing dedicated namespaces/IPs. Current MACs and the
matching RoCEv2 GID are discovered, never copied from a fixture. An existing
control listener is not replaced. The controller starts the FPGA pattern
engine; TCP carries descriptors/readiness/verification only. Receiver QP/GID,
PSNs/counts, FPGA acknowledged completion and quiescence, receiver byte count,
zero mismatches and both exit statuses must agree. The outer supervisor also
requires guard exit 0 before `result.json` can claim hardware verification;
the internal `worker.json` deliberately leaves that claim false/pending.

Each invocation owns a fresh `rdma/logs/native-*` directory. Ordinary failure
cleanup stops its own controller before releasing its receiver, allowing the
controller to ABORT first. Forced termination is a failed, unverified cleanup,
never proof of FPGA quiescence. A thermal group stop can end both processes;
native QP teardown rejects late writes after MR release. No process-name kills,
RXE endpoints, interface/fan changes or management-NIC operations are used.

After the first successful small case, `--message-bytes 65 --count 3 --psn
0xfffffe` exercises a PSN wrap. The finite throughput case is at most
`--message-bytes 4096 --count 16384` (64MiB); there is no continuous load loop.
Reported hardware-counter payload rates include initialization and final
drain, so a tiny case is not a line-rate benchmark. These commands are planned
hardware tests, **not** evidence that the current image has passed them.
The twelve runner tests use modeled child processes/records only and are
included in `make -C rdma check-host` and source-check CI.

### Full transport retransmission test

`hls/probe/test_retry_transport.py` withholds the modeled peer's first ACK
until a second, actual generated-HLS transmission occurs. It checks replay
of the original 65-byte WRITE, local pattern reread, original PSN/rkey/VA,
independent checksums, one successful logical completion and safe drain.
It keeps the real 4ns clock and 1ms timer; no shortened simulation timeout
constants are used. This is a long optional generated-RTL simulation, not
actual CX455A retry interoperability. Its result must be inspected before
any retry-success claim.
The selected build-010 result passes at 255506 cycles: one 65-byte logical
WRITE, two verified wire transmissions/pattern reads, one actual HLS retry
and one successful ACK/completion; see
[the scoped simulation record](../results/2026-10-18/rocev2-transport-retry-rtl.json).
The later native fault experiment below is separate hardware evidence.

### Native ACK-loss, timeout and recovery experiments

`host/mac_rx_fault.py` wraps the unchanged native WRITE controller. It
discovers Corundum register blocks and only borrows interface1/port0's MAC
RX enable/pause writable bits. The selected build's final CDC report labels
RX enable as a two-stage ASYNC_REG synchronizer (CDC-3 Info); source tracing
connects it to MAC frame admission, not merely host RX queues. No PHY, DRP,
clock, global reset, flash, management NIC or fan controls are changed.

After TCP endpoint exchange/readiness, RX is disabled before START. In
`retry` mode it is restored only after one logical WRITE has produced at
least two pattern reads, injected transmissions and physical completions,
with zero received ACKs. The original 4ns/1ms HLS timer is unchanged. In
`watchdog` mode only the controller deadline is set to10ms: the expected
result is ERROR2 with zero acknowledged WRITEs, not transport success. Once
TX is quiescent and RX restored, the peer verifies every received byte. A
separate normal native WRITE then checks ERROR-to-IDLE-to-DONE reuse without
NIC reset or programming. Independent restoration monitoring at100ms and
exception/owned-abort cleanup provide bounded ordinary execution; they do
not guarantee recovery under SIGKILL, OS suspension, host failure or PCI
removal. Forced cleanup, restoration failure or missing retry counters fails
the experiment. Only an already-reviewed, dedicated test link is allowed.

Actual build003 cases passed: RX off1.545ms before successful retry recovery;
watchdog ERROR after2,500,002 clocks, RX off10.774ms, receiver65/65 bytes;
subsequent normal65-byte WRITE completed from the quiescent ERROR state.
All three thermal guards exited0, observed58.85–59.22C, BIOS Medium retained.
See [source-bound hardware record](../results/2026-10-18/rocev2-native-retry-recovery-003.json).
Ten fault-control and six verdict model tests are in `make -C rdma check-host`.

To reproduce one finite fault case after independently completing physical,
programming, temperature and isolated-link review (flags are attestation,
not an automatic physical gate):

```sh
AS02_ALLOW_NATIVE_FPGA_RDMA_TEST=YES AS02_PHYSICAL_REVIEW_COMPLETE=YES \
AS02_ALLOW_MAC_RX_FAULT=YES \
AS02_TEMPERATURE_GUARD=/absolute/path/to/validated/guard.sh \
python3 rdma/host/native_fault_test.py --mode retry --psn 0x456789
```

`--mode watchdog` selects the expected-failure case. Follow it with the normal
native runner to verify subsequent acknowledged WRITE recovery. These tests
do not qualify arbitrary loss, congestion, NAKs, multiple concurrent QPs or
production reliability.

### Read-only board clock diagnosis

`scripts/inspect_board_clocks.tcl` reads a completed, immutable full-board
checkpoint and writes new-prefix clock-interaction, setup/hold, four exact
GTY RX/TX pair, timing-exception and CDC reports. It verifies the part/top,
refuses an existing report prefix and never changes clocks, exceptions,
cells, routes or a saved checkpoint. For example:

```sh
vivado -mode batch -source rdma/scripts/inspect_board_clocks.tcl \
  -tclargs /absolute/path/to/completed/fpga_routed.dcp \
  /absolute/path/to/new/diagnostic-prefix
```

Successful diagnosis is not a timing/CDC pass. The original routed snapshot
still fails setup by 0.189ns and has four missing-annotation flow-control CDC
chains. See the source/checkpoint-bound
[routed diagnosis](../results/2026-10-18/rocev2-board-routed-diagnostic.json)
and the progress log. Never use positive slacks in those four clock-pair
reports as proof of asynchronous crossing safety.

`scripts/inspect_phy_cdc.tcl` independently checks the inherited PHY/DRP
controls on a full native25 checkpoint, without changing its design or
constraints. It verifies the two GTYE4 TXPDELECIDLEMODE pins are driven by
VCC, the DRP request synchronizer/direct connections and applied 8ns
max-delay-datapath-only constraints, 22 static-control bits across the two
PHYs, and the four-stage common-reset structure/preset exceptions:

```sh
vivado -mode batch -source rdma/scripts/inspect_phy_cdc.tcl \
  -tclargs /absolute/path/to/completed/fpga_routed.dcp \
  /absolute/path/to/new/phy-inspection-prefix
```

The static controls have one destination register and must remain unchanged
during communication; the inspector explicitly does **not** prove runtime
stability, waive all CDC findings, replace the final bus-skew/timing gates,
or grant hardware-test permission. The
[first completed inspection](../results/2026-10-18/rocev2-phy-cdc-inspection.json)
uses the original failed routed snapshot, not the corrected candidate.

`scripts/inspect_synth_cdc.tcl` checks VIO/LFC annotations already compiled
into a **fully linked post-opt or later board DCP**, with no extra XDC or
constraint/property edits. A standalone top synthesis DCP from this OOC-IP
project is insufficient: it leaves PCIe/GT/VIO blackboxes unresolved and
cannot prove their clocks. The reader now refuses such incomplete inputs.
It uses the same checkpoint/new-prefix command shape as the inspectors
above. Successful annotation inspection is not final physical acceptance
or hardware verification; keep the original full output gates and review.

`scripts/verify_lfc_equivalent.tcl` is a separately tested assertion revision
for the pinned board's one audited equivalent source-register merge. It
retains strict source roles, exact clocks, INIT/reset/topology, ASYNC_REG and
first/second-stage exception checks. It was not installed into the original
frozen build. After that run terminated, the canonical FPGA checker became
a thin shim to this shared implementation, explicitly included in the next
compile manifest. It must not bypass image-release provenance or physical
gates. `tests/check_lfc_source_allowlist.tcl` is a pure offline
14-case allowlist test. The actual Vivado diagnostic test driver accepts:

```sh
vivado -mode batch -source rdma/scripts/check_lfc_equivalent.tcl \
  -tclargs /absolute/path/to/linked/fpga_opt.dcp \
  /absolute/path/to/new/equivalent-check-prefix compiled 1
```

`compiled 1` expects the new candidate's single audited alias and adds no
XDC for the positive case. `annotate 0` is only for the original uncorrected
routed snapshot and applies the narrow annotation in a disposable copy.
Both modes then inject faults only in that in-memory copy to prove the
verifier refuses incorrect annotations/exceptions. They write diagnostic
reports, never a checkpoint/image, and perform no hardware access. See the
[scoped assertion tests](../results/2026-10-18/rocev2-lfc-equivalent-checks.json).

### Separately identified verification-only release

`scripts/release_routed_candidate.sh` prepares a **new** offline output
directory for the audited source-register-name assertion revision. Do not
edit/re-hash the compile manifest or verifier of an in-flight/old build.
First observe the actual original build process/session becoming terminal;
a checkpoint, stale lock or observation timeout alone is not sufficient.
Use only its preserved root `as02mc04_25g_routed.dcp`, not a placed/post-opt
snapshot. Supply the independently observed compile-manifest and DCP
SHA256 values and `AS02_BUILD_TERMINAL_CONFIRMED=YES` to the three-argument
script. This flag is an operator attestation, not an automatic liveness check.

Preparation copies the original compile manifest unchanged, archives the old
LFC verifier, and copies the **exact original physical gate and VIO checker**.
Only the gate's LFC-verifier child becomes the separately tested assertion
revision. A distinct verification manifest binds the immutable DCP, original
manifest/policy, new policy, driver, and staged copies. Both identities are
checked before/after checkpoint opening and after output generation. No
clock, XDC, routing, datapath or queue feature is altered. All original
native-clock/setup/hold/full-summary/route/38-bus-skew/DRC gates remain active.
The helper refuses an already-produced original image and does not program
JTAG/SRAM/flash or change networking/fans.

The [preparation tests](../results/2026-10-18/rocev2-release-provenance-checks.json)
use `/bin/false` instead of Vivado and an intentionally invalid checkpoint.
They verify fail-closed identity checks and byte-preserving staging, **not**
actual bitstream generation or physical acceptance. The separate real
routed-DCP attempt accepted the revised LFC checks but was rejected by the
unchanged max/setup gate; see the [corrected board diagnosis](../results/2026-10-18/rocev2-board-routed-corrected-diagnostic.json).
Even an eventual static pass still requires
review of the actual final CDC/operating conditions, recorded SRAM-only
programming, re-identification, temperature guard and bounded native RDMA.

`tests/test_metadata_backpressure_rtl.py` additionally fills the real
32-entry TX checksum FIFO (including its output pipeline) while stalling
the output. A bad UDP-destination frame reaches its final beat with that
FIFO full; all 38 good frames, including four recovery frames, still match
the independent byte/checksum/ICRC oracle. The test observes actual FIFO
backpressure without forcing DUT state or reducing its depth. It is part
of `make check-rtl`, with source-bound
[RTL evidence](../results/2026-10-18/rocev2-metadata-capacity-rtl.json), not
a physical timing or real-RNIC communication result.

The subsequently selected input-stage correction registers complete
data/keep/last/bad-frame beats together in a two-entry vendor skid stage
before the integrity frame FIFO. TX final-beat admission reserves checksum
capacity independently of current CRC/length validity; bad frames can wait
for capacity but never consume metadata or escape whole-frame rejection.
No FIFO/window depth, check, operation or clock requirement is reduced.
`scripts/test_icrc_candidate.py` and the recorded diff artifact describe the
earlier isolated qualification; current selected-source tests are rerun
separately. That recorded delta is now selected in the RTL; do not apply it
again. The old circuit's timing result is not a physical pass for this
new RTL. The full app retry test keeps its real 4ns/1ms timing and virtual
watchdog; only the host wall-time budget is extended when needed. With
`--report`, its live `.simulation.log` sidecar records every 50000 cycles
without altering stimuli or assertions.
