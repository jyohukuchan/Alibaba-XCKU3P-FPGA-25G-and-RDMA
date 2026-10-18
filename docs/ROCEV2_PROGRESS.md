# Active RoCEv2 / native-25G development

This file records the initial WRITE003 milestone. The subsequent READ goal
has separate [progress](ROCEV2_READ_PROGRESS.md), [native results/use guide](ROCEV2_READ_RESULTS.md)
and [READ/WRITE evidence](../results/2026-10-18/rocev2-rw-native-001.json).
Historical statements below about unsupported READ describe WRITE003,
not the later combined version2 image.

User objective: **RoCEv2・25Gb通信を最終目標としつつ、細かい目標に分けながら進めて。**

This file records milestones toward the full objective; none of the smaller
milestones alone completes it. The existing 25GbE image remains the rollback
baseline. BIOS Fan Speed stays Medium; finite hardware tests require temperature
monitoring and must stop if unsafe. No flash programming or unrelated NIC resets.

## Intended end-state evidence

- The AS02MC04 FPGA itself implements RoCEv2 transport over its native 25GbE
  link and interoperates with the existing CX455A hardware RNIC.
- Actual RDMA memory transfers have verified contents, valid protocol state,
  and observable completion/acknowledgement/error behavior.
- A controlled finite large-transfer test records payload throughput on the
  25G link and demonstrates a datapath sized for 25G-class operation. Ethernet
  link speed, TCP iperf results or a single packet alone do not establish this.
- Hardware validation is performed without a software RoCE endpoint standing
  in for the FPGA RDMA engine. Temporary reference endpoints are identified
  explicitly and removed before the FPGA-engine completion audit.
- Source, fixed dependencies, build reports, programming identity and actual
  measurements distinguish tested images from untested variants.

This is an experimental scoped RoCEv2 endpoint, not a claim of every verbs
operation, native InfiniBand, production reliability or all congestion modes.

## Milestones

| ID | Goal | Evidence required | State |
| --- | --- | --- | --- |
| M0 | Revalidate baseline and toolchain | Current 25G link, PCIe/driver identity, resources, tools | Complete |
| M1 | Establish peer/control and wire reference | CX455A RoCEv2 GID/QP/MR setup; finite verified transfer/reference packets | Complete (software reference only) |
| M2 | Simulate and size the FPGA endpoint | Chosen implementation, license/provenance, correct packet/state tests, synthesis/resource results | Complete, build 003 full physical gate |
| M3 | First real FPGA RDMA WRITE | Native25 image, valid ACK and verified CX455A-side memory, no software substitute | Complete, native CX455A all-byte verification |
| M4 | Queued/reliable transfers | Larger transfers, PSN/ACK/retry/error checks, data integrity | Complete for controlled finite cases: queue/tail/wrap, ACK-loss retry, watchdog/error/recovery |
| M5 | 25G-class communication audit | Finite receiver-verified throughput, PHY/PCIe/temperature evidence and reproducible artifact | Complete: finite64MiB at24.264Gbit/s, artifact/thermal/PCI evidence; not sustained qualification |

## Initial revalidation: 2026-10-18 JST

- Host T7610, Linux 6.17.0-1033-oem; Vivado Standard 2025.2 is present.
- FPGA endpoint remains `1234:1001` class020000 on mqnic; existing namespace
  and link are preserved. CX455A reports 25000 Mb/s, full duplex, FEC off.
- Existing namespaces are `fpga10g-fpga` / `fpga10g-cx4` despite their 25G link.
- CX455A mlx5_0 is ACTIVE; original IPv4 `198.18.10.1` uses RoCEv2 GID 3.
- Existing utilization report: 51939/162720 LUTs, 118/360 BRAM tiles,
  **39/48 URAM**. These are baseline figures, not a proposed RDMA core's fit.
- FPGA external DRAM is absent in this board reference; avoid assuming an
  Alveo-sized memory subsystem. One QP / small buffers is an initial milestone,
  not a substitute for the eventual queued 25G-class datapath.
- Reference code under evaluation: fpgasystems/fpga-network-stack, whose
  published RoCEv2 wrapper is 512-bit/HLS/QDMA-oriented. No adoption/fit claim
  yet; the existing Corundum synchronous application path is a possible bridge.

## Reference-test boundary

A temporary Linux RXE endpoint on the FPGA Ethernet interface may be used to
validate the peer and generate known-good RoCEv2 packets. That endpoint runs
the RDMA protocol in host software. Such a result is **M1 reference evidence
only**, never evidence of M3/M5 hardware RDMA completion or offload throughput.

No goal-completion claim is made by this document or by source-check CI.

## M1 evidence: 2026-10-17 UTC / 2026-10-18 JST

Implemented a libibverbs RC WRITE/data-integrity peer and offline wire oracle
under [rdma/](../rdma/README.md). Build with warnings-as-errors and nine
offline wire-model tests pass, including byte-exact reproduction of a real
CX455A WRITE, independent RXE/CX455A ACKs, full-width RETH keys, padding and
corruption checks. These are protocol-test tools, not FPGA RTL completion.

The final finite reference run used a temporary root-namespace macvlan/RXE
endpoint and a temporary CX455A secondary IP. Linux 6.17 RXE's init_net socket
and route implementation prevents the straightforward namespaced setup;
the isolated workaround preserves both original physical interfaces. It was
removed after testing, along with the extra IP and RXE device. Management
networking and original `198.18.10.0/30` configuration are unchanged.

- Actual native link: 25000 Mb/s; no new FPGA image was loaded.
- Sizes: 1, 63, 64, 65, 4095, 4096, 4097, 8192; 16 writes per size/direction.
- **256 RDMA writes, 661536 receiver-verified bytes, zero mismatches**.
- All signalled sender completions successful; receiver confirmation returned.
- Complete capture: 320 unique WRITE packets + 248 ACKs = **568 packets**.
- All 568 independently recomputed ICRCs valid; no captured repeated WRITE
  PSNs or non-success AETH. ACK coalescing means ACK count need not equal
  request count. Both full-width rkeys and all expected WRITE PSNs audited.
- Temperature guard: preflight **58.30 C**, observed samples **58.19..58.30 C**;
  no thermal trip. BIOS Medium retained. This is not a sustained-load result.
- Raw local capture SHA256:
  `8b7bb5027429e295b9c89dacf1b87fbb80b4407543168bfa12603ca483c127bc`.
- Aggregate: [rocev2-reference.json](../results/2026-10-17/rocev2-reference.json).

Earlier captures without immediate mode omitted buffered packets despite
successful transfers; they are not used for complete-wire claims. The final
auditor rejects such incomplete captures. Raw captures remain local/ignored.

M1 proves the CX455A peer, host control and known-good protocol vectors. The
RDMA transport on the other side is still **Linux RXE in host software**.
No FPGA offload or 25G RDMA throughput is claimed.

## M2 work underway

Installed local CMake, Icarus Verilog and Verilator; Vitis 2025.2's modern
`vitis-run --mode hls --tcl` is available. The pinned public FNS candidate's
standalone configuration is missing and its shift templates/duplicated CRC
source did not compile unchanged. Compatibility fixes and a reproducible
KU3P/512-bit/eight-table-entry/4ns/retransmit-enabled probe are isolated under
`rdma/hls/`. The first compiling probe generated RTL, but estimated **998
BRAM18K units / 720 available**, 23482 LUTs, 65069 FFs, zero URAM and
**4.043 ns vs 4.000 ns target**. Exit zero is not a fit/timing pass. Large
width but shallow FIFOs account for most of the waste. Capacity-preserving
SRL mapping is being tested; fit and actual route timing remain unproven.
See [initial estimate](../results/2026-10-17/rocev2-hls-probe.json).
Internal CRC checking is disabled in this candidate: explicit verified CRC
integration is required before hardware testing. This is not a selected,
validated dependency or a completed RDMA core.

### Further M2 evidence / next work

- `probe-ku3p-512-8qp-006` completed with capacity-preserving small-FIFO SRL
  mapping in the configuration-header translation units. Standalone estimate
  fell from **998 to 193 BRAM18K**, with 24082 LUTs, 63969 FFs, zero URAM.
  No queue depth, RDMA function or retransmission feature was removed.
  This is a promising *standalone estimate*, not an integrated physical fit.
- Timing estimate is still **4.043 ns**, not a 250MHz timing pass.
- `csim-ku3p-512-8qp-004` exited zero: the public C-model consumed a valid
  WRITE_ONLY and produced exactly one 64-byte, byte-verified memory write
  and one ACK with correct QPN/PSN/success AETH. The full 32-bit key constructor
  probe passes. RX/TX diagnostic registers count **words (2/1)**, not packets;
  an earlier test incorrectly assumed packet counts and was corrected after
  inspecting both source and observed values.
- C-model ACK is **44 bytes before external ICRC**, while IPv4/UDP lengths
  account for the eventual CRC. External checksum/ICRC completion and RX CRC
  checking must be implemented; the bare C-model output is not wire-ready.
- C simulation leaves unused retransmission free-list entries at exit. This
  is recorded, not waived as an RTL deadlock pass. C simulation does not model
  finite FIFO/backpressure behavior or prove timing/retry correctness.
- `probe-ku3p-512-8qp-007` completed with small-FIFO SRL defined globally,
  including standalone IPv4/UDP compilation: **79 BRAM18K**, 24126 LUTs,
  63869 FFs, zero URAM. Estimated period remains 4.043 ns. The generated
  RTL from this exact probe is used in the integration tests below.
- Next: finish sizing, verify generated RTL under stalls, add/check the CRC
  and protected memory/control wrapper, then integrate with Corundum's sync
  application path. No new FPGA programming has occurred during M0/M1/M2.

### Integrity and generated-RTL evidence: 2026-10-17 UTC

Added `rdma/rtl/rocev2_ipv4_icrc.v` and
`rdma/rtl/rocev2_integrity_transport.v`. These are IP-only streams around the
HLS transport, not a full Ethernet/PCIe application. The integrity stage
uses 128-bit beats and a complete-frame FIFO: invalid RX packets are dropped
before *any* word is visible to the transport/memory path. TX repairs IPv4
checksum and appends ICRC. FIFO widths/capacity preserve overlap between
packet input and output; the design is not a single-buffer half-rate path.

Verified against current source hashes in the machine-readable records:

- Integrity RTL tests: **93 valid frames, 15 deliberately invalid frames**.
  Observed RNIC/RXE vectors, varying payload/padding, malformed headers/masks,
  upstream error flags, corruption of payload/ICRC and IPv4 checksum were
  checked. Thousands of source/sink stall cycles verify stable outputs and
  recovery after rejected frames. No unexpected FIFO overflow.
- A 32 × 4096-byte simulation has 8320 output beats in 8320 output cycles:
  **31.508 Gbit/s simulated payload capacity assuming 250MHz**. This is only
  the integrity sub-block's cycle capacity. It is not routed timing, full
  RDMA throughput or actual 25GbE communication.
- Generated-RTL RX integration: two 64-byte WRITEs with one CRC-corrupt frame
  inserted between them. Correct memory commands and **128 exact data bytes**;
  two wire ACKs with independently validated IPv4 checksums, ICRCs,
  QPN/PSN/MSN and success AETH. Network/command/data stalls: 1759/804/1294
  cycles. The corrupt packet never entered HLS; core transport RX words=4.
- Generated-RTL TX integration: SQ command → one 64-byte memory-read command
  → pattern source → correctly serialized WRITE → modeled RNIC ACK → valid
  successful-WRITE acknowledgement metadata. Full **32-bit rkey and 64-bit
  remote address** verified on the wire. Network/read-command stalls: 360/93
  cycles. The remote address is an offline width test, not a registered live MR.
- The initial integrated simulation stopped because a declaration-time
  constant reset did not trigger generated combinational reset inversion;
  FIFO occupancy/state became unknown before initialization. The test now
  drives a real reset transition before the first clock, copies generated RAM
  initialization files, and rejects simulator errors and unknown counters.
  This was a testbench initialization issue, not evidence of a core fix or a
  proof of every warm-reset scenario.
- HLS metadata ABI verified by the RTL tests: QP/connection ports 184 bits,
  SQ 240 bits, memory command 96 bits, ACK metadata 40 bits (including AXIS
  byte rounding). HLS diagnostics are latched only on their valid strobes.

Records: [integrity RTL](../results/2026-10-17/rocev2-icrc-rtl.json),
[transport RX](../results/2026-10-17/rocev2-transport-rx-rtl.json),
[transport TX](../results/2026-10-17/rocev2-transport-tx-rtl.json).
All are **simulation**, never FPGA hardware interoperability evidence.

The initial physical-step Tcl used an unsupported collection command. The
fixed helper saves a source/mode-identified checkpoint before physical work.
Both `icrc-{rx,tx}-ooc-002` runs completed routing but **failed the overall
timing gate**, with TX/RX WNS +0.084/+0.020 ns and WHS -0.077/-0.072 ns.
Post-route hold-fix attempts `*-004` also fail: TX +0.159/-0.077 ns,
RX -0.126/-0.072 ns. The first checkpoint-resume attempt `*-003` stopped
before physical work because `read_checkpoint` did not open a design; the
helper now uses `open_checkpoint`. These are not fit/timing successes.

Diagnosis from the actual routed checkpoints: all failing hold paths are
from virtual OOC input ports (49 TX / 235 RX). No surrounding launch registers
or real top-level clock tree were modelled. This does **not** waive hold
checking or prove board timing. Internal register-to-register WHS is
+0.040/+0.036 ns, but RX has a real **-0.126 ns internal setup** path from
header sum through checksum folding into the bad-frame flag. Physical
resource estimates are TX 1631 LUT / 520 FF / 4.5 BRAM36 tiles, RX
1463 LUT / 423 FF / 4.5 BRAM36; zero URAM in both. See the explicitly failed
[OOC record](../results/2026-10-17/rocev2-icrc-ooc.json).

The RX checksum-valid predicate now compares the low 16 bits of the raw sum
with the complement of the upper five, avoiding two end-around-carry adders
on that path. The test calls the actual RTL function on **all 2,097,152
21-bit sums** against independent integer one's-complement arithmetic.
Current functional regression/source hashes are recorded separately from the
older OOC reports. `icrc-rx-ooc-005` has finished: overall WNS +0.023 ns,
WHS -0.052 ns, so its strict overall gate still fails. Its internal paths
have WNS/WHS +0.023/+0.034 ns; all 198 failing hold endpoints are virtual
input-port paths. These diagnostics do not waive complete-board timing.

### Ethernet application boundary

Added 128-bit `rocev2_ethernet_rx.v` / `rocev2_ethernet_tx.v`, using the pinned
MIT Ethernet framers and frame-locked round-robin AXIS mux, not a 64-bit
250MHz link bottleneck. Ordinary RX/TX traffic keeps its bytes and all NIC
sideband metadata. Engine-disabled RX passes RoCE to the host too. Enabled
RX consumes plain IPv4/UDP/4791 and admits only configured source/destination
MAC/IP, in-range local QP and ACK opcode into the downstream integrity stage.
Inbound WRITE/READ are intentionally blocked until protected receive-memory
handling exists. This is an initiator WRITE path, not arbitrary inbound DMA.

- RX component test: 56 host frames preserved, 20 ACKs stripped correctly,
  19 rejected frames, including MAC/IP/QP mismatch, QP 8 outside an eight-entry
  table, unsupported WRITE opcode, keep holes, errors on early/late beats,
  truncation and oversize. Two frames exceeding FIFO capacity are dropped
  without orphaning route metadata. Valid traffic recovers after each fault.
- Full 97-bit host RX sideband, disabled-engine routing, configuration
  snapshot across mid-frame changes, queue wrap and 3113 input stall cycles
  are checked. VLAN/non-RoCE traffic remains unmodified host traffic.
- TX test: 24 host frames coexist with 37 injected frames, including every
  short-packet tail boundary and real ACK/WRITE vectors. No beat interleaving
  under thousands of independent stall cycles. Three injected completions
  are filtered; three host tag/timestamp completions are unchanged.
- Corundum's pinned TX engine sets the completion tag MSB for real NIC
  descriptors. Injected frames use tag zero and are filtered by that bit,
  not by a potentially desynchronizing per-packet ownership FIFO.
- A 32 x 4096-byte TX-framing simulation has **31.156 Gbit/s payload cycle
  capacity assuming 250MHz**, including framing/arbitration gaps. This is
  not implemented clock timing, a complete endpoint benchmark or real traffic.
- Generated-HLS-RTL integration now supports `--direction tx --ethernet`:
  SQ -> modeled local read -> 64 exact WRITE bytes -> complete Ethernet/IP/
  RoCE frame, independently verified addresses/keys/checksums. A valid-CRC
  ACK for wrong QP and a CRC-damaged correct-QP ACK are rejected before HLS;
  only the good ACK enters the core (one RX word) and completes the WRITE.
  This is a modeled RNIC, **not** actual CX455A RDMA interoperability.

[Ethernet component evidence](../results/2026-10-17/rocev2-ethernet-rtl.json)
and [Ethernet/transport evidence](../results/2026-10-17/rocev2-ethernet-transport-tx-rtl.json)
bind the tested sources and testbench by SHA256. Source-check CI rejects
stale integrity/Ethernet/transport test identities. Generic upstream framers
still emit width/ascending-counter lint warnings at 128 bits; no lint-clean
claim is made. The exercised behavior passes the actual RTL tests.

Still required before hardware claims: Corundum synchronous-app/control
integration, integrated MAC/drain and retry/error tests, complete-board
timing/DRC, then actual CX455A registered-memory verification and finite
25G-class tests. The following sections record subsequent control/timer work.
No FPGA image was changed. At this earlier check the native25 link was up;
readonly SYSMON
sample was **59.84..60.09 C**, over-temperature clear, STAT `0x009079fc`, BIOS
Medium still active. No fan change, flash write, NIC reset or public push.

### Finite engine, AXI-Lite and padding

Added `rocev2_write_engine.v`, `rocev2_pattern_source.v`, and
`rocev2_control.v`: a finite, windowed initiator, protected peer-MR bounds,
arbitrarily byte-aligned deterministic payload generation, independent
AXI-Lite AW/W handshakes, write masks, busy-state configuration locking,
abort/watchdog handling and preserved terminal diagnostic counters. The
current endpoint generates data locally; it does not expose arbitrary host
DMA or accept inbound remote WRITEs into host memory.

- Engine unit regression covers 19 scenarios, cumulative/duplicate ACKs,
  24-bit PSN wrap, queue stalls, invalid metadata/configuration, overflow,
  watchdog, abort and memory faults. A valid 64MiB configuration is admitted
  then aborted: this is **not** a 64MiB data-transfer result.
- Pattern tests verify 12545 exact bytes from eight reads, arbitrary offsets,
  tails and replay, plus five rejected out-of-bounds/invalid commands.
- AXI-Lite unit test performs 48 reads / 28 writes, three 65-byte WRITEs,
  response/data stalls, five rejected control writes, invalid MR rejection
  and clear/restart counter behavior.
- A real generated-HLS 65-byte test uncovered missing upstream TX padding.
  `rocev2_tx_padding.v` now inserts 0..3 pad bytes, updates IP/UDP lengths
  and BTH pad count **before** strict checksum/ICRC generation. Invalid
  lengths/masks/pre-existing padding stay invalid, rather than being healed.
  Three unit tests cover 38 valid tail variants, seven malformed frames
  with recovery, and a 4095-byte cycle-capacity run. No real throughput claim.
- Five complete controller/generated-HLS/Ethernet cases check 1, 65 and 4096
  bytes, distinct local/peer PSNs, full rkey/remote VA, PSN wrap and cumulative
  ACKs: **15 simulated wire WRITEs / 12876 bytes / 14 success ACK events**.
  The selected record identifies the exact generated build and all local
  sources. This is a modeled RNIC, never actual CX455A interoperability.
- `control-ooc-001` fails setup/hold (-1.085/-0.077 ns). Registered validation
  with legal operand-width multiplication preserves the full 64MiB legal
  range and improves `control-ooc-002` to +0.445/-0.077 ns. Internal paths
  have +0.445/+0.019 ns. The worst 1000 failing hold endpoints sampled are
  virtual input-port paths; this sample is not a complete endpoint census.
  The strict overall timing gate remains **failed**, not waived.

Selected evidence: [engine](../results/2026-10-17/rocev2-write-engine-rtl.json),
[control](../results/2026-10-17/rocev2-control-rtl.json),
[padding](../results/2026-10-17/rocev2-padding-rtl.json),
[complete simulated path](../results/2026-10-17/rocev2-control-transport-rtl.json),
[failed control OOC gates](../results/2026-10-17/rocev2-control-ooc.json).

### Resumed work: 2026-10-18 UTC

The previous goal run ended with a Codex `server_overloaded` error, not a
physical FPGA failure. Existing builds and test evidence survived. Readonly
revalidation found mqnic still bound at `82:00.0` and the CX455A link still
25000 Mb/s / full duplex / up. No current temperature is inferred from an
old SYSMON sample. No new bitstream or fan setting was applied.

The pinned FNS timer used 6.4ns despite a 4ns target. The compatibility
patch now uses integer-picosecond, round-up clock/scan constants; the AS02
adapter selects 4000ps in both synthesis and C simulation. It also bounds
the scan hazard skip modulo the QP table and avoids unsigned subtraction
underflow. ASan/UBSan tests of the actual patched timer pass for all eight
QP slots: a nominal 1ms timeout takes 250004 C-model clock steps. ACK restart,
stop, simultaneous clear/set priority and small-table boundary accesses
are checked. This C-model result is not generated-RTL or wire evidence.

Fresh `probe-ku3p-512-8qp-008` finishes RTL generation using the clock-correct
timer: 79 BRAM18K, 24080 LUT, 63805 FF, zero URAM/DSP, timer pipeline II=1.
Estimated clock is still **4.043 ns**, so this is **not** a 4ns timing pass
or an integrated-board fit. Original build 007 remains preserved for the
historical transport-only tests; new complete-path tests select 008.

Added `rocev2_tx_guard.v` before the injected Ethernet framer. It closes
new-frame admission on halt, drains an already accepted frame without
withdrawing stalled AXIS VALID, counts outstanding injected MAC completions,
then waits an additional conservative 1024 core cycles after SFD completion.
Host traffic/completions must bypass this injected-only guard. The guard
must use whole-NIC reset, **not** the transport's per-run core reset. Six
unit cases cover mid-frame halt/backpressure, 8192-byte tails, outstanding
capacity/recovery, missing/unsolicited completions, oversized frames, and
one-word-per-cycle forwarding. These unit checks do **not** prove the full
MAC/CDC path or the physical wire is drained; integration remains required.

The complete-path test now uses this real guard and modeled early SFD
completions, rather than a testbench shortcut for quiescence. All five wire
cases pass again on build 008. However the independent generated-timer test
**fails** on build 008: QP 0 retries 150006 clocks after an ACK, instead of
waiting at least 250000. A following BRAM scan can read stale pre-ACK state
and later overwrite the extension despite the C-model passing. These short
complete-path tests therefore do not establish retry-timer correctness.

The compatibility patch now applies the bounded scan-hazard skip on ACK
updates too. Fresh `probe-ku3p-512-8qp-009` finished RTL generation and passes
all eight ACK-extension phases, but the next test still fails: stopping QP 0
immediately before a new WRITE retries after 150008 clocks rather than a full
250000. The scan skip alone does not resolve update-to-update RAM hazards. The
timer RTL regression is also extended to cover a stop ACK immediately
followed by a new start in each QP slot. The fix is unproven until that
actual generated-RTL test passes. Nothing from these builds is programmed.

The complete current `make -C rdma check` regression, including the new
guard cases, passes. `bash scripts/check.sh` also passes with refreshed
source-bound evidence. These do not require the external HLS tools and do
not include the still-running, licensed-tool/generated-timer regression.

### Resettable timer registers and real app boundary

The AS02 adapter now requests complete partitioning of the same eight timer
entries and explicit per-run reset. The false inter-iteration dependency
directive and heuristic scan skips are not used on this register-table path.
This changes storage/dependency handling, **not** the QP count, clock target
or enabled retry features. See AMD's [array partitioning](https://docs.amd.com/r/en-US/ug1399-vitis-hls/Array_partition)
and [explicit reset](https://docs.amd.com/r/2025.2-English/ug1399-vitis-hls/pragma-HLS-reset)
documentation for those directives; the actual generated RTL is the evidence
for this implementation, not an assumption based on a pragma.

`probe-ku3p-512-8qp-010` finishes HLS generation: **77 BRAM18K, 24471 LUT,
63887 FF, zero URAM/DSP**. The timer achieves pipeline II=1 / depth=3, with
reset assignments visible on the generated entry registers. Its estimated
clock is 3.489ns; the **whole HLS block remains 4.043ns**, still not a 4ns
timing pass. Full-board physical timing remains required.

The full generated timer regression now includes all eight QPs, ACK extension
at every scan phase, stop/immediate-restart at every slot, missing ACK,
output FIFO backpressure/recovery and resetting an armed timer. Icarus's
first complete-register-table run exceeded the 240s wall limit and was
terminated by the harness, without a protocol assertion failure. The same
tests **pass** with a 1200s wall limit: **8621166 cycles, 26 retry events**,
first retries at 250002..250007 clocks. The 4ns clock, protocol-cycle
deadlines and all test cases are unchanged. A faster Verilator 5.020 timing
attempt crashes in its coroutine runtime (ASan reports a double-free), so
it is **not** used as passed evidence. The selected successful run is Icarus
with its ordinary four-state simulation and unchanged zero-delay semantics.
See [generated timer evidence](../results/2026-10-18/rocev2-timer-rtl.json).

Added `rocev2_endpoint.v` and a Corundum-template-derived
`rdma/fpga/mqnic_app_block.v`. The endpoint joins the actual control, bounded
pattern source, generated HLS, padding/integrity, ACK classifier, TX guard and
Ethernet arbitration. The app attaches it to synchronous port 1 (SFP2),
preserves port 0, disables application DMA and leaves direct/interface paths
as passthroughs. Queued ACKs are discarded during inactive/reset phases,
without resetting the ordinary host RX path. A startup reset-arm register
provides a real HLS reset transition; the unarmed simulation otherwise timed
out with error 2, as opposed to producing valid transfer evidence.

All five full-app cases on build 010 pass: 1/65/4096-byte payloads, independent
peer/local PSNs, wrap and cumulative ACKs, **15 modeled wire WRITEs / 12876
verified bytes / 14 success ACK events**. These test the real app wiring,
not a duplicate hand-connected datapath. They still model the RNIC and MAC
completions, do not test actual MAC/CDC drain, and do not establish transport
retry recovery or hardware throughput. The selected record has been refreshed
and the source-identity checks pass.

The explicit optional build `fpga/build_25g_rocev2.sh` enables APP_ID
`0x41535232`, application control BAR2 and synchronous interception, without
changing the normal Ethernet-only build or PHY clocks. `check_build.py`
requires matching successful timer and full-app regressions and source hashes
before a board build can begin. That gate now passes and the first complete
native25 RoCE board build has started; check the actual process/log before
replacing it. No bitstream has been loaded, no flash/fan/
management interface has been changed, and no new commit or push was made.

First native-board build directory:
`fpga/builds/as02mc04-25g-rocev2-ZpxYXdHv`; live console is
`rdma/logs/native25-board-build-001.log`. Preflight resolves **257 HDL,
12 constraints, 3 IP generators**. Vivado has configured application BAR2
as a 16MiB aperture; that is a build-time setting, not an assertion that
Linux has assigned resources to a newly programmed card. Check completion,
physical reports and actual state before any SRAM programming decision.

A separate [real-MAC drain simulation](../results/2026-10-18/rocev2-mac-drain-rtl.json)
uses the pinned `axis_xgmii_tx_64`, actual async FIFO/width-adapter primitives,
a representative **whole-frame 16KiB test FIFO**, 250MHz core and 390.625MHz
MAC clocks. Three 48/124/8192-byte opaque IP inputs yield exact Ethernet
frames and independently verified FCS, with no MAC underflow or FIFO loss.
For the largest frame, core-cycle SFD completion / actual XGMII terminator /
guard permission are **3323 / 3975 / 4347**. Thus the guard waits beyond real
wire EOF, not merely beyond a modeled timestamp. This verifies that tested
MAC/CDC composition, **not** the exact full `mqnic_port_tx` buffering topology,
integrated board timing, actual hardware or RoCE wire interoperability.

### Host control and ACK-loss integration work

Added `rdma/host/fpga_write_client.py`: exact-BDF/PCI/mqnic/ROC2 checks,
exclusive control lock, fixed-length/strict QP/MR parsing, full 32-bit rkey /
64-bit VA register packing/readback, peer-ready handshake, bounded hardware
START/watchdog, counter/quiescence checks and receiver P confirmation.
Handled timeout/SIGINT/SIGTERM requests only its own run's abort and records
whether safe quiescence was actually established. No auto NIC reset, flash
write, fan change or arbitrary host DMA is exposed. Tests use a fake register
bank/peer, never MMIO or a registered MR: [ten host-control tests](../results/2026-10-18/rocev2-host-control-unit.json).
This is implementation/test progress, **not** evidence of a real FPGA WRITE.

Full-board build `ZpxYXdHv` has advanced beyond its dependency IP runs into
top-level synthesis. The previous full offline `make -C rdma check` run
finished successfully, and the updated host-only checks also pass.

An independent full-app/generated-HLS replay test **passes**, recorded in
[transport retry RTL evidence](../results/2026-10-18/rocev2-transport-retry-rtl.json).
It withholds the first modeled
ACK, waits for actual retransmission at the real timer interval, and checks
the reread/replayed bytes, key/address/PSN, completion and guard counters.
No timer/clock is shortened and no DUT internals are forced. It finishes at
**255506 cycles**, one original and one retransmitted 65-byte payload
(130 wire payload bytes), two bounded pattern reads, exactly one successful
logical ACK/completion, and one actual HLS retransmission. Both wire packets'
PSN/full rkey/full VA/payload/IPv4 checksum/ICRC and preserved terminal
counters pass. This is **RTL retry recovery**, not native RNIC/hardware
retry evidence or a 25G throughput result.

Next: finish generated timer/path regressions, integrate the actual app
bridge/guard and MAC completions, then run fresh complete-board physical
gates. No native FPGA RDMA operation or 25G RDMA throughput is claimed.

## Read-only native-path audit and full-board synthesis

On 2026-10-18 the original full-board build
`fpga/builds/as02mc04-25g-rocev2-ZpxYXdHv` completed synthesis and entered
implementation (Vivado logged `synth_1 finished` / `Launched impl_1` at
04:05:01 UTC). Its synthesis report contains 77903/162720 LUTs (47.88%),
109590/325440 FFs (33.67%), 138/360 BRAM tiles (38.33%), 39/48 URAM
(81.25%) and one DSP. These are **synthesis**, not final routed utilization
or a timing pass. The original implementation process is being followed;
it must not be restarted just because a polling call times out.

Added `rdma/host/native_preflight.py` and ten pure tests for the dedicated
FPGA/CX455A path. Live read-only inventory at 04:09 UTC verified the audited
PCI IDs/drivers and namespace/netdev binding, MTU 9000 and /30 IPs, native
`mlx5_0` port 1 / PCI `03:00.0`, 25000Mb/s full duplex, active Ethernet /
RoCEv2 GID index 3, and no FEC. Current MACs were read from the real devices:
FPGA `d6:b9:fb:83:a4:51`, CX455A `b8:83:03:67:c5:d0`. Simulation MACs must
not be copied into live tests. PCI class `020700` does not imply the CX455A
is in InfiniBand wire mode; `link_layer` and actual GID type are checked.

The loaded Ethernet-only FPGA image has no application BAR2, as expected.
The optional application-required preflight **refused** it before creating
a QP, sending traffic or writing any MMIO. Raw records:
`rdma/logs/native-preflight-001.json` and
`rdma/logs/native-preflight-require-app-001.json`. No FPGA image or fan
setting changed. This is inventory/test-readiness evidence only: M3 actual
FPGA-to-CX455A WRITE, M4 hardware reliability and M5 native25 RDMA throughput
remain unproven, pending physical timing/CDC review and guarded finite tests.
Portable scoped summaries are in
`results/2026-10-18/rocev2-native-preflight.json` and
`results/2026-10-18/rocev2-board-synthesis.json`; raw local reports are hashed
there without publishing installer files, build trees or packet captures.

## Prepared finite native hardware runner

`rdma/host/native_test.py` now orchestrates one bounded native FPGA -> CX455A
WRITE case. It requires explicit traffic opt-in, operator attestation that
physical review/programming/recovery are complete, the existing validated
temperature guard, and an actual quiescent ROC2 app before starting. This
attestation does not replace build reports or identify the programmed image.

Each owned log directory records current preflight, exact commands, source
and native peer-binary hashes, native receiver events, FPGA-control result
and the thermal supervisor's output/script hash. An existing listener is not
replaced. Native GID/QP/PSNs and transfer counts must match, all receiver
bytes must verify, and TX must be quiescent. Internal worker success is still
marked hardware-unverified/pending; only the outer supervisor can promote a
successful transfer after the actual temperature guard exits successfully.
On ordinary failure, owned client stop/ABORT precedes receiver release;
forced cleanup is explicitly unverified. No software RXE, management-network
operation, flash programming or fan change was added.

Twelve pure tests cover request bounds (up to 64MiB), native-vs-RXE identity,
actual-MAC/dynamic-GID arguments, memory/count/PSN mismatches, guard failure,
explicit-opt-in/refused-start ordering, modeled worker execution and modeled
client-before-peer cleanup. All pass, together with the previous 29 Python
host checks and C pattern self-test. These tests do **not** create a QP,
access MMIO, execute JTAG or verify real RDMA memory. The first native test
remains 64B x 1, followed by finite boundary/PSN-wrap cases and only then a
guarded finite large transfer. Physical implementation is still being
followed under the original board-build handle; no device was programmed.
The source-bound model-test record is
`results/2026-10-18/rocev2-native-runner-unit.json`; all hardware/traffic/
registered-memory/temperature-execution flags are explicitly false there.

## Pre-programming topology/rollback review; physical result still pending

Read-only checks on 2026-10-18 reconfirmed the FPGA sysfs parent as
`pci0000:80/0000:80:03.0/0000:82:00.0`. The exclusive `80:03.0` bridge has
only the FPGA endpoint downstream. Management `enp7s0` instead resolves to
`0000:07:00.0` under `00:1c.1`; the default route remains on that interface.
Nothing was removed, reset, rescanned or reconfigured by these checks.

The existing bridge prefetchable window is 513MiB and the running FPGA uses
a 16MiB prefetchable 64-bit BAR0. The new configuration also requests a 16MiB
prefetchable 64-bit BAR2, so the existing window has sufficient capacity in
principle. Actual resource assignment after programming must still be checked;
this observation does not prove Linux has assigned the future application BAR.
Both endpoint/bridge links currently report Gen3 x8. The connected port's
CH2/CH3 clock counters read 390.623232 / 390.631424 MHz on the old image.
The unused CH1 RX clock is not used as connected-port speed evidence.

Both rollback files still hash to their recorded values:
25G `83ab714e93a7279d179d773df2ef3787d752cd466cdbf5f48176f395838c14d3`,
10G `4a944e18a41b88e310efffc1fe742e3aebdb2248c20f9727b5f8ad43ed84b606`.
The installed openFPGALoader supports explicit `--write-sram`, adapter serial
selection and frequency. No JTAG client/programmer was running at this check.
The present RDMA devices are only `hfi1_0` and `mlx5_0`; no temporary RXE is
present. The unrelated hfi1 device is untouched.

Important baseline distinction: upstream `80:03.0` already shows raw SDES+
and DevSta FatalErr+ status, while the endpoint's corresponding status is
clear and all six endpoint/bridge Linux AER counter files report zero.
RootCmd CERptEn/NFERptEn/FERptEn are disabled. These observations alone do
not date or establish the cause of the latched status, nor prove no hardware
errors occurred. The kernel journal has no new matching PCIe/AER events
since 03:00 UTC. Do not clear status simply to produce a clean report.
Record raw status, link and counter baselines after deliberate programming,
then compare them across the finite RDMA test. Linux documents that AER
statistics count captured reports and that OS/firmware reporting control
matters: https://docs.kernel.org/PCI/pcieaer-howto.html .

The original implementation remains live. Its first pre-route/post-placement
optimization estimate is WNS -0.647ns / TNS -498.243ns. This is a failing
**intermediate estimate**, not a final physical result or permission to load
the image. Final route/setup/hold/DRC/CDC evidence remains required; continue
the same build handle and inspect the eventual critical paths before choosing
any source or physical optimization. The original clocks/speed grade are not
relaxed to turn this estimate into a pass.

## Fully-placed critical-path diagnosis (not a final timing result)

The original build completed placement, saved `fpga_placed.dcp`, and continued
its own AggressiveExplore physical optimization. A separate read-only Vivado
invocation of `rdma/scripts/inspect_ooc_timing.tcl` read that completed board
checkpoint (the helper is not restricted to OOC netlists). It exited 0 at
04:33:32 UTC. That exit means **diagnosis completed**, not timing passed.
Source-bound checkpoint/report identities and results are in
`results/2026-10-18/rocev2-board-placed-diagnostic.json`.

The actual worst setup path in this saved, fully-placed design has slack
-0.465ns at the original 4ns requirement: padding output `m_axis_tkeep[15]`
passes through the TX-integrity dense-mask/bad-frame/metadata-final gate,
then ready feedback to padding `offset[15]` CE. Its 4.260ns data delay includes
15 logic levels (three CARRY8s), 1.473ns logic and 2.787ns estimated routing.
This identifies a local packet-validation/backpressure path, not evidence
that the generated HLS core is the worst bottleneck. Only the sampled worst
paths were inspected; all violations are not yet classified. The same placed
checkpoint has -0.609ns hold on the PCIe completion-to-hard-IP path. Routing
and the final strict setup/hold gate must handle it; no waiver was added.

If the final route still fails on this mask path, a source-local candidate is
to replace popcount/variable-shift dense-mask validation with adjacent-bit
prefix validation. Python exhaustively checked all 65536 binary keep masks:
`keep==0 || keep!=((1<<popcount(keep))-1)` equals
`keep==0 || ((keep>>1)&~keep)!=0`. This is **predicate equivalence only**,
not a new RTL or physical pass. It can remove the serial mask construction
without weakening malformed-mask rejection or lowering the required clock.
Do not change the live build inputs. After the original run reaches a terminal
state, inspect its final critical paths before choosing a fix; any RTL change
requires refreshed wire/RTL/full generated-HLS transport evidence and a new
full-board physical run. The active build has already improved its current
pre-route estimate to -0.371ns but has not met the final gate.

## Read-only feasibility review for a later hardware retry case

While the unchanged board implementation continues, the pinned Corundum
source confirms that a dedicated-port RX-enable control reaches the physical
MAC: `mqnic_port.v` RX control bit 0 crosses two flops in `rx_clk`, is exported
through the core's `eth_rx_enable`, and `Nexus_K3P_S/fpga_25g/rtl/fpga_core.v`
connects it to MAC `cfg_rx_enable`. `axis_xgmii_rx_64.v` only admits a new frame
at `xgmii_start_d1 && cfg_rx_enable`. This is before the synchronous application
ACK filter, not merely a host receive-queue pause. Disabling it should suppress
new ACK frames without intentionally resetting the PHY/link. This is a source
trace, **not** a hardware-tested fault-injection result; no control was changed.

The register address must be discovered, not copied from a guessed BAR offset.
The port header `C002` version `00000200` points to a child port-control header
`C003` version `00000300`. RX_CTRL is +0x14 **relative to that child**, equivalent
to port-module RBB+0x24, not RBB+0x14. The library's `mqnic_port_open()` already
enumerates and checks that child block. RX_ENABLE is bit 0; RX_PAUSE is bit 8.
An eventual test must preserve/restore both writable bits, verify exact FPGA
BDF/driver/interface 1/port 0 and ownership, bound the disable interval, and
restore RX on ordinary failure/interrupt before controller teardown.

Only after a first normal native WRITE has passed, a possible M4 case is to
disable the dedicated FPGA MAC RX after peer readiness but before START,
restore it shortly after the real 1ms retransmission timeout, then require
actual FPGA retransmission/pattern reread/TX-completion counters and one
successful native receiver memory verification. TCP control shares this port,
so ordering and restoration must be tested explicitly; disabling before QP
metadata/readiness exchange would be incorrect. No helper/hook implementing
this is enabled yet, no MMIO was written, and M4 remains unverified. The
management NIC and unrelated hfi1 device must never be targets.

## Original board build entered routing

Following the same live process (not restarting on observation timeouts),
pre-route AggressiveExplore physical optimization completed successfully.
Its final **estimated** WNS/TNS were -0.036 / -1.543ns and WHS/THS were
-0.463 / -410.610ns. These still fail timing; successful completion of the
optimizer is not a timing pass. The original process then started
`route_design -directive Explore -tns_cleanup` and reached Build RT Design
at about 48m40s implementation elapsed time. Final routing, post-route
optimization, strict setup/hold/DRC/clock/bus-skew gates and CDC review remain
pending. No candidate predicate fix was applied to the live HDL and no image
was programmed. Continue session 80227 / the authoritative live process/log;
do not start another implementation solely because a poll yields no output.

## Configuration-status readback readiness

The existing local `fpga-led-blink/read_status.cfg` selects FTDI serial
210251019420, 1MHz, the exact 04a63093 TAP, `reset_config none`, and OpenOCD
`virtex2 read_stat`; it returns to BYPASS and exits. It is the status reader,
not `fpga-led-blink/program_sram.sh` (the latter hardcodes an unrelated LED
image and must **not** be used to load the RoCE image). No JTAG command was
executed during this review.

AMD [UG570 STAT register](https://docs.amd.com/r/en-US/ug570-ultrascale-configuration/Status-Register-00111)
confirms DONE pin/internal bits 14/13, EOS bit 4, CRC error bit 0, IDCODE error
bit 15, security violation bit 16, over-temperature bit 17, authentication
error bit 27 and bad-packet error bit 29. Use these family-specific meanings,
not a copied decoder for a different FPGA generation. The documented old-image
status `0x009079fc` decodes to DONE/EOS set and those error bits clear; this
decode is **not** a new hardware read or proof that a future image is loaded.
After an approved SRAM load, keep the first actual raw STAT/readback log and
its decoded flags with the exact bitstream hash/programmer log. JTAG access
must remain exclusive and separate from the temperature monitor.

The unchanged live board run has now started global/initial routing. Its
clock-routed intermediate WNS/TNS reached +0.083 / 0ns, while hold remained
negative (-0.257ns initially, -0.452ns after bus-skew timing update). None of
these intermediate reports is the final setup/hold gate. Routing/post-route
optimization and the complete reports are still pending; no new image was
programmed and no native FPGA RDMA transfer is yet verified.

## Routed-path and MAC flow-control CDC diagnosis

The original run completed routing and its post-route optimizer reported the
same -0.189ns WNS / -79.927ns TNS, with no hold violations. The parent build
then reopened the implementation to write its final reports and enforce the
strict output gate; do not mistake the implementation child exiting for the
entire build being terminal. Keep following session 80227 / parent Vivado
PID 481292 until the authoritative exit status is known. No HDL/HLS or
late-sourced build recipes were changed while it was live.

The completed, separately read checkpoint diagnosis is recorded in
`results/2026-10-18/rocev2-board-routed-diagnostic.json`. It confirms 901 setup
failing endpoints at the original 4ns requirement. The sampled worst path
is padding `m_axis_tkeep[5]` through integrity dense-mask/bad-frame/ready
feedback to the width adapter's synchronous data reset (`FDRE/R`), 13 logic
levels / three CARRY8s, 3.992ns data delay (1.504ns logic, 2.488ns routing).
This remains a real setup failure, not a virtual OOC-port artifact.

The default routed DRC has 29 Warning checks and no Error/Critical Warning.
This does **not** mean every other report is clean: the separate methodology
report has four TIMING-7 Critical Warnings on the two ports' RX/TX clock pairs.
The new read-only `rdma/scripts/inspect_board_clocks.tcl` completed successfully,
with full clock interaction, scoped max/min paths, timing exceptions and CDC
reports. Each warned direction has exactly one timed cross-clock path.

Actual source and CDC evidence identify all four as MAC link-flow-control
crossings: `tx_lfc_req_sync_reg_1` -> `_2` -> `_3`, and
`rx_lfc_ack_sync_reg_1` -> `_2` -> `_3`, on each port. Stage 1 is a source-domain
preregister; stages 2/3 are the existing two destination-domain flops. Each
is CDC-2 Warning, depth two, missing ASYNC_REG, with no timing exception.
It is incorrect to dismiss the warnings merely because the code is upstream.

After the original parent build is terminal, the intended correction is to
mark only the eight destination registers (stages 2/3 across four chains),
except only the four asynchronous first-capture D pins, and verify direct
connections, correct clocks and fully timed second-stage paths. No blanket
RX/TX clock false path, data-path timing waiver, frequency reduction or flow
control feature removal is intended. AMD's
[2025.2 synchronizer guidance](https://docs.amd.com/r/2025.2-English/ug903-vivado-using-constraints/CDC-Synchronizers-and-ASYNC_REG-Property)
explains why the annotation affects preservation and placement, not just
report cosmetics. The other 18 Critical CDC findings remain separately
reviewable (DRP handshake, static GT controls, reset and hard GT pins); this
diagnosis does not universally waive them or assert hardware safety.

The mask predicate equivalence candidate remains unimplemented until the
original build exits. Any correction still requires refreshed functional
evidence, a new complete physical build and finite native hardware tests.

## First board build terminal; setup-path correction implemented

The original full-board run (session 80227) exited **1** at 2026-10-18
05:24:04 UTC. Its final strict setup gate refused bitstream output at
WNS -0.189ns / TNS -79.927ns. No RoCE bitstream was generated or programmed.
The earlier sections above describe historical live observations, not the
current job state. The old checkpoint/reports remain unchanged as failed
physical evidence; they must not be relabeled with the new source hashes.

After that authoritative exit, `rocev2_ipv4_icrc.v` replaced the dense-keep
popcount/variable-shift/subtract validation with a nonzero LSB-prefix check:
there is no adjacent 1-above-0 in the 16-bit keep mask. The byte count, ICRC,
frame-length and non-final/full-word requirements remain intact. This
removes the identified carry-heavy predicate from ready/bad-frame feedback;
it does not lower the 250MHz requirement or waive the real setup failure.
The current RTL hash is
`2231fdad5e3ccb701e1d716f891f8f1a049819b105ccc9273541ead442a195d7`.

Fresh tests invoke the actual DUT predicate on **all 65,536 masks** in each
of the three integrity testbenches, against the independent old arithmetic
reference. All three pass, including the existing 2,097,152 checksum-sum
values and malformed-frame/backpressure/recovery coverage. Padding and the
generated-HLS RX/TX/Ethernet integration regressions also pass. The selected
result records now bind these real reruns to the new source and test hashes.

The five full-app/generated-HLS cases (1, 65 and 4096-byte payloads, PSN
wrap and cumulative ACK) were rerun and pass: 15 WRITE frames / 12,876
payload bytes / 14 successful ACK events. The full-app ACK-loss/replay test
also passes with the unchanged 4ns clock and real 1ms timer: 255,506 cycles,
one withheld ACK, one actual transport retransmission, two pattern reads,
and exact replayed key/address/PSN/payload/ICRC. This remains **RTL evidence,
not native RNIC hardware or physical MAC-drain verification**. Raw local
logs use `icrc-prefix-001`, `padding-prefix-001`, `integrity-prefix-*`,
`app-prefix-*` and `app-prefix-retry-001`. The source checks complete with
exit 0 (`rdma/logs/source-check-prefix-001.log`).

The optional RoCE build now adds `fpga/mac_flow_control_cdc.xdc` only for
the four existing MAC LFC chains. It annotates the eight destination
registers, with false paths only to their four first-capture D pins.
The Ethernet-only build is unchanged. A separate disposable in-memory
annotation check initially rejected a returned timing-path object, but
the detailed report proves that object is already a **False Path** with
infinite slack. AMD's
[get_timing_paths specification](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/get_timing_paths)
distinguishes user-ignored paths from analyzed paths. The verifier now
requires an explicit user-ignored False Path to the expected first D pin,
and a finite, non-excepted, normally analyzed max/min path through the
second destination stage. It retains clock, direct-connectivity and
ASYNC_REG checks. This changes the verifier's interpretation of actual
tool evidence, not the scope of the timing exceptions.

The new board input manifest includes HDL, memory initialization,
constraints, IP generators and build/verification Tcl; the final RoCE
output gate must rehash those exact files and refuse changed inputs.
The corrected candidate still needs the annotation check, a fresh full
placement/routing pass, review of the other inherited CDC findings, and
temperature-guarded finite native hardware tests. No flash, fan, PCIe,
network or hardware programming changes were made in this correction.

### Corrected candidate now building

The corrected annotation check completed with **exit 0** in session 36786
(`rdma/logs/mac-flow-cdc-check-003.log`). All four LFC chains have verified
max/min first-D False Paths and finite, non-excepted second-stage timing.
Their CDC classification changes from CDC-2 to CDC-3 (depth two); the four
TIMING-7 Critical Warnings are absent from the fresh methodology report.
The remaining 18 inherited Critical CDC findings are **not** waived by this
result. This is a disposable in-memory constraint/structure check, not a
new placement/routing result. A further actual-Vivado check with deliberate
missing-cut and over-broad-cut negative controls completed with **exit 0**
(session 54966, `rdma/logs/mac-flow-cdc-check-004.log`, 05:45:50 UTC).
The verifier rejects an annotated chain whose first-D exception is missing,
accepts the complete correction for all four chains, and rejects an extra
false path to a second-stage D. Clean annotation reports are written before
the deliberately wrong second-stage cut; the disposable copy is discarded
without writing a checkpoint or bitstream. Both negative controls passed.

New full-board session **61132** is running in
`fpga/builds/as02mc04-25g-rocev2-YZB6xDCr`, with console
`rdma/logs/native25-board-build-002.log`. It uses the unchanged source-bound
HLS build 010, the new dense-keep predicate and narrowly scoped MAC LFC
annotations. Source checks passed before launch (session 45146 / exit 0,
`rdma/logs/source-check-prefix-002.log`). Preserve its exact input files
while this run is live. There is no current routed result or native FPGA
RoCEv2 hardware transfer from this candidate; follow the actual job before
deciding the next step. No hardware was programmed.

### Initial disposition of the other 18 Critical CDC findings

The old routed and annotation-only reports contain the same 18 remaining
Critical findings. Reviewing the actual endpoints against pinned source
classifies all of them; this is **not** an unconditional CDC waiver or
permission to program the current candidate before its physical review.

- One CDC-1 is `rb_drp.rb_we_reg` -> `drp_we_reg`. `rb_we` is bundled data,
  held with address/data until the round-trip flag handshake completes.
  The destination captures it only after the two-flop request synchronizer.
  `common/syn/vivado/rb_drp.tcl` supplies max-delay-datapath-only and bus-skew
  constraints for that bundle. Check their actual coverage and the final
  38 bus-skew results on the new routed checkpoint; a CDC-1 label alone
  neither disproves this handshake nor proves its physical implementation.
- Six CDC-1 and four CDC-4 findings are the two PHYs' TX inhibit/polarity,
  RX polarity and 4-bit TX/RX PRBS selection controls. The wrapper uses
  **one** destination register for these controls, not a generic safe
  two-flop synchronizer. They are initialized configuration, updated by
  specific DRP writes/reset; they must remain stable during communication.
  Do not claim arbitrary runtime reconfiguration is safe. No DRP accesses
  were found in the pinned mqnic driver C/headers, and the finite native
  runner/client do not perform DRP writes. A bounded test must keep this
  stable-configuration condition and separately check link/reset/error
  observations; the fresh physical review remains necessary.
- One CDC-10 is the OR of `drp_rst` and `xcvr_ctrl_rst` ahead of the first
  asynchronous PRE of a four-stage reset synchronizer. Both source reset
  generation and the wrapper's four-stage async-assert/sync-release chain
  were inspected. It is reset distribution, not RoCE payload data; still
  verify the actual reset structure/constraints and ensure no PHY reset
  or clock switching occurs during a finite native test.
- Six CDC-13 findings terminate at the two GTYE4 hard channels'
  TXELECIDLE / TXPD[1:0] ports. The common wrapper explicitly ties
  `txpdelecidlemode_in` to 1 for every GTY variant. AMD
  [UG578 v1.4, Table 3-39](https://docs.amd.com/api/khub/documents/BY7rRWkUQliMvNvosLhSZA/content)
  defines that value as asynchronous TXELECIDLE/TXPD operation. This is
  relevant hard-primitive behavior, not an inferred fabric synchronizer.
  Confirm that both final GTYE4 pins retain this constant before accepting
  these endpoints; source inspection alone is not the final netlist check.

The inspected unchanged source hashes are:

```text
fca16c7e298a6cb18ca23faeb5e40a903cd3a23633f98dc2ad6f22839a3bd1c3  common/rtl/rb_drp.v
2a698b1d9be8a9a2f8dbdd3da3da9f25cc005d0f3bbeed5f6eb547c3613bf4fa  common/syn/vivado/rb_drp.tcl
eb95d9fdb0bd05cf4a76d2aceb71ee43ca46a7bd28952bf772c888570d3dc70f  common/rtl/eth_xcvr_phy_10g_gty_wrapper.v
5d01d10ffaf18d07fc13c8fb3227b6bd5e57e7be1c4f725dc5542e322ba3384e  common/syn/vivado/eth_xcvr_phy_10g_gty_wrapper.tcl
a6701ef1a7412be2615592c2db70a7cebc07baa208ffba79e34ecaedf0289a91  lib/axis/rtl/sync_reset.v
```

Paths above are relative to `external/corundum/fpga/`. Do not remove these
findings by lowering severity, adding whole-clock false paths, or marking
one-stage/bus controls as safe synchronizers without a real RTL change.

### Old-checkpoint PHY/DRP structural inspection completed

`rdma/scripts/inspect_phy_cdc.tcl` completed against the original immutable
routed DCP (session 49514 / exit 0, 2026-10-18 05:56:09 UTC), with no design
or constraint changes. The DCP SHA256 remains
`fdfae51f4a5f9357f896cd61126237929132be218453c310aa7fa9be428ab455`.
See the source/checkpoint-bound
[inspection record](../results/2026-10-18/rocev2-phy-cdc-inspection.json).

- Both physical GTYE4 mode pins have a real VCC driver, not merely a
  source-code parameter assumption: X0Y15 and X0Y14 each use asynchronous
  TXELECIDLE/TXPD operation.
- The DRP request's two destination flops have the expected ASYNC_REG,
  clocks and direct connections. The WE bundle path and first request
  capture each retain the exact 8.000ns max-delay-datapath-only exception,
  with 7.419ns and 7.317ns scoped slack respectively.
- All 22 bits of the ten grouped static-control findings have direct
  register connections, the expected 8ns/2.56ns clocks, zero INIT on source
  and destination, and met 8ns max-delay-datapath-only bounds. Their single
  destination stage is explicitly reported, not relabeled as two-stage
  synchronization. Runtime stability is still an operating condition.
- The common-reset path has four actual directly connected ASYNC_REG
  flops, all INIT=1, a GND first D, shared asynchronous PRE pins, the
  expected 8ns destination clock and the exact PRE False Path at every
  stage from the SFP reset source.

The first inspector attempt (session 35977) correctly stopped without
changing the design because it compared EXCEPTION against report_cdc's
short category label. The detailed path property spells the actual command
as `MaxDelay Path 8.000ns -datapath_only`; the inspector now checks that
exact string and the numeric requirement/slack. Both raw attempts remain
preserved. A successful scoped structural check is **not** a full-board
timing pass, an unconditional CDC safety claim, or new hardware evidence.
The corrected YZB6xDCr candidate is still in whole-board synthesis; repeat
this inspection on its completed physical result before finite SRAM tests.

## Corrected candidate synthesis complete; implementation started

The corrected YZB6xDCr synthesis run completed successfully at 2026-10-18
06:25:14 UTC, with its `.vivado.end.rst` present, completed `fpga.dcp` and
utilization report, and the main build advancing to `impl_1`. This is not
an overall build exit: parent session 61132 remains active, with new
implementation PID 640072 observed generating debug cores during opt_design.
Do not restart it merely because the synthesis child PID 636467 exited.

Synthesis reports 0 errors / 0 Critical Warnings. Its top-level resource
counts are 77,897 LUTs (47.87%), 109,657 FFs (33.69%), 1,523 CARRY8s,
138 BRAM tiles (38.33%), 39 URAMs (81.25%) and one DSP. **Four OOC IPs are
still black boxes in this top synthesis report**: PCIe, both GTY variants
and VIO. These counts do not include all of their linked contents and are
not final implementation utilization. See the
[corrected synthesis evidence](../results/2026-10-18/rocev2-board-synthesis-corrected.json).

The complete synth_design summary reports 646 warnings in both old and new
runs; sorted printed warning lines match exactly. The intermediate phase
summary says 526 rather than 491, so do not silently conflate that counter
with the complete synth_design summary. The reason for that intermediate
counter difference is not independently established. No warning has been
removed, lowered in severity or presented as a clean physical pass.

The new top synthesis DCP hash is
`ae0d052edcec8ff0f51363d9d5163058c70bdda60e0fa729e10f772b4ae79d57`.
The input manifest remains unchanged at 297 bound files. An initial
read-only compiled-CDC check against this standalone top DCP exited 1
(session 91533): the four unresolved OOC IPs prevent VIO/PCIe/GT clock
proof. That is an inappropriate incomplete inspection artifact, not a
failure of the continuing linked implementation or permission to waive
the clock checks. Its raw log remains `rdma/logs/synth-cdc-inspect-001.log`.

`rdma/scripts/inspect_synth_cdc.tcl` now explicitly refuses unresolved
blackboxes and requires a **fully linked post-opt or later** board DCP.
It sources only the existing VIO/LFC assertions and writes reports; it
does not read corrective XDC, set properties/exceptions, write a DCP/image
or access hardware. Use the completed new candidate's linked checkpoint
when available, keeping the live build inputs untouched. Full physical
setup/hold/routing/DRC/bus-skew gates, fresh CDC review and finite native
FPGA-to-CX455A memory verification remain incomplete. No FPGA was programmed.

### Linked post-opt checkpoint available; fixed-name CDC assertion unresolved

The new run completed opt_design and saved a fully linked `impl_1/fpga_opt.dcp`,
SHA256 `20cd9ed332cd2db9c544cd199ff0c45d442df07ddad9a233f030fa36b8766431`.
Placement is now running in the same parent session 61132 / implementation
PID 640072. The frozen 297-file input manifest still verifies unchanged.

The read-only linked inspection (session 30705,
`rdma/logs/compiled-cdc-inspect-002.log`) exited **1**, not a CDC pass.
VIO's six pairs pass. All eight LFC destination registers are present;
port 0's two chains have the expected clocks, ASYNC_REG, first-D False Paths
and finitely timed second stages. Their pre-placement estimated min slack
is -0.055ns, which is not a final physical hold result. The inspection then
stops because the fixed source-preregister name
`core_inst/mac[1].eth_mac_inst/mac_ctrl.tx_lfc_req_sync_reg_1_reg` is missing
after opt_design. A merge/rename is a hypothesis, **not yet demonstrated**;
do not waive this assertion or infer missing/dangerous circuitry solely
from the register name.

The diagnostic reader now preserves a failed assertion status while also
reporting the actual leaf drivers of each destination D, plus utilization,
CDC, methodology and timing reports. No corrective XDC, property or design
changes are made. A new read-only attempt is running as session **93812**,
prefix `rdma/logs/compiled-cdc-inspect-003`; inspect its actual handle and
output before claiming the source-driver diagnosis or annotation check
passed. The main build's final verifier and manifest are untouched; it
will still reject an unresolved fixed-name assertion. Resolve that from
actual connectivity evidence, without editing live frozen build inputs
or silently weakening the structural/clock/exception requirements.

The driver-reporting attempt (session 93812) has now finished with exit **1**
and all diagnostic reports written. The actual port-1 source is
`core_inst/core_inst/core_pcie_inst/core_inst/iface[1].interface_inst/port[0].port_inst/rx_lfc_req_sync_1_reg_reg/Q`,
an FDCE clocked by `gtwiz_userclk_rx_srcclk_out[0]_1`. Pinned source shows
that this port register and the missing MAC preregister have the same
external `rx_lfc_req`, RX clock, async reset and zero INIT, because this
board explicitly sets `MAC_CTRL_ENABLE(0)`. The core/PCIe/interface wrappers
route the same per-port signal. Actual connectivity and source behavior
therefore support an equivalent-register merge, not disappearance of the
required first destination synchronizer. Independent formal post-synthesis
equivalence has not been performed. See the source/checkpoint-bound
[compiled diagnosis](../results/2026-10-18/rocev2-compiled-cdc-diagnosis.json).

The compiled CDC report already classifies all four LFC chains as CDC-3,
depth two, with first-D False Paths; the four TIMING-7 Critical Warnings
are absent. The other 18 Critical CDC findings remain separately qualified.
The linked post-opt utilization is 80,933 LUTs (49.74%) and 118,497 FFs
(36.41%), including linked IPs; it is still not final routed utilization.

The fixed-name verifier still fails and must be repaired/tested to recognize
the **specific audited equivalent source** while retaining all topology,
clock, ASYNC_REG and timing-exception checks. Do not edit the live build's
frozen verifier/manifest or generate a bitstream by bypassing that failure.
Continue the physical run for its required final timing evidence, then
resolve verifier/provenance before any qualified image release or SRAM test.

## Audited equivalent-source assertion revision tested separately

The live run's original verifier remains frozen and unchanged. A separate
candidate, `rdma/scripts/verify_lfc_equivalent.tcl`, now resolves the actual
first-capture D leaf driver and accepts only the four original source names
plus the **one** audited port-1 TX-LFC source alias identified above. The
allowlist admits no arbitrary source, no other port/signal role and no
constant driver. All source/destination flops must be FDCE with INIT=0;
exact per-port native RX/TX clock names and 2.56ns periods are checked,
along with direct Q-to-D chains, shared destination resets, eight ASYNC_REG
destination stages, first-D-only False Paths and finite non-excepted max/min
second-stage timing. It does not claim pre-placement negative hold slack
is a final physical pass. Source identity must retain the audited board
MAC_CTRL_ENABLE=0 condition; this is not a generic alias waiver.

Pure Tcl allowlist tests pass **14 cases**. Actual Vivado positive and
negative checks also completed on disposable copies, both with exit 0:

- Session 58165 / `lfc-equivalent-compiled-001`: the new linked post-opt
  candidate passes all four chains with one audited source alias, with no
  corrective XDC loaded for that positive check. Removing ASYNC_REG and
  over-cutting the second stage are both rejected.
- Session 22480 / `lfc-equivalent-original-001`: the old routed snapshot
  remains compatible with zero aliases after applying the narrow annotation
  in memory. Missing the first-D exception, removing ASYNC_REG and
  over-cutting the second stage are each rejected.

These are five negative-control executions covering three fault types,
not five distinct fault classes. Positive reports precede deliberate faults;
all disposable copies are discarded without checkpoint/image writes.
The source/test/pinned-assumption-bound
[assertion evidence](../results/2026-10-18/rocev2-lfc-equivalent-checks.json)
is now checked by source CI for stale provenance. This fixes/tests the
assertion logic separately; it has **not** changed the live build's final
verifier or qualified a hardware image. Promote only after preserving the
frozen run's truthful input provenance, and recheck the final routed design
with every original setup/hold/routing/DRC/bus-skew requirement intact.

The physical run completed placement. The placed estimate is WNS -0.221ns
/ TNS -40.042ns at the start of the additional optimizer: **still unmet,
not the final routed result**. A read-only placed-path diagnosis is running
as session 15789, prefix `rdma/logs/board-placed-corrected-001`, on immutable
`impl_1/fpga_placed.dcp` SHA256
`da3d917bffe676a99c5f60f962aac1874c57bf02fc910d9ffa76e1ace331c5f8`.
Follow its actual exit and the original main build session 61132 rather
than restarting either merely because an observation yields no output.

The placed-path diagnosis above has now completed with **exit 0** (session
15789, 06:54:11 UTC), without changing the checkpoint or constraints. The
[corrected placed diagnosis](../results/2026-10-18/rocev2-board-placed-corrected-diagnostic.json)
records the actual worst sample: interface 1's host-NIC TX queue URAM ->
active-operation-table lookup / consumer pointer -> 64-bit dequeue address.
It is URAM288 CLK to `m_axis_dequeue_resp_addr_reg[63]/D`, at the unchanged
4ns PCIe user-clock requirement: WNS -0.221ns, 3.935ns data delay (1.922ns
logic / 2.013ns estimated route), 14 logic levels including seven CARRY8s,
five LUT6s, one LUT3 and one RAMD32. This sample is not the old ICRC dense-
mask path; it does not prove every other ICRC path is nonnegative. The
sampled placed hold estimate is -0.652ns on the MSI-X header-to-PCIe hard
port path. Both remain **pre-route estimates**, not final acceptance.

Do not change live inputs or waive the host-NIC path merely because RoCE
payload injection bypasses parts of the host descriptor path. The full
design must still pass. Continue the current optimizer/routing and use the
actual final paths to decide whether a real data-path/pipeline correction
is required. The source-alias verifier revision and all physical gates
remain separate requirements before native SRAM testing.

### Corrected compiled PHY review and verification-release preparation

The corrected fully linked post-opt checkpoint has now independently passed
the same read-only PHY/DRP inspector (session 14062, **exit 0**), without
changing the source manifest or saved checkpoint. The
[corrected inspection](../results/2026-10-18/rocev2-phy-cdc-corrected-inspection.json)
binds raw `phy-cdc-corrected-001` reports to DCP SHA256 `20cd9ed332cd2db9c544cd199ff0c45d442df07ddad9a233f030fa36b8766431`.
It verifies both GT mode pins high, the two-stage DRP request, 24 scoped
8ns max-delay paths, all 22 static control bits and the four-stage common
reset topology. Minimum scoped **estimated** slack is 7.707ns. This is not
routed acceptance or proof of runtime configuration stability: keep the
previously reviewed no-DRP/no-PRBS/no-reset-during-traffic condition, and
repeat/inspect the final routed evidence before hardware testing.

The original run remains live as session 61132 / implementation PID 640072.
It completed pre-route physical optimization at estimated WNS -0.042ns,
then entered routing (Explore). One early router estimate was WNS +0.034ns
with hold -0.278ns; **neither is final acceptance**. Do not restart or modify
any of the frozen 297 inputs while that process is active.

For the known fixed-source-name assertion issue, added an explicit separate
verification-only release path, rather than altering the original build's
manifest or backdating its verifier. `release_routed_candidate.sh` requires
the independently checked original compile/DCP hashes and a manual
terminal-process attestation. It stages the original physical gate and VIO
checker byte-for-byte, archives the old name-based verifier, uses only the
tested LFC source-role assertion revision, and binds all original/revised
inputs in an additive verification manifest. It changes no HDL/XDC/clocks,
does no synthesis/route and never accesses hardware. The unchanged setup,
hold, full timing summary, native GT clocks, complete route, all 38 bus-skew
requirements and DRC gates still must pass.

Seven [offline preparation tests](../results/2026-10-18/rocev2-release-provenance-checks.json)
passed with `/bin/false` standing in for Vivado and an intentionally invalid
checkpoint fixture. They cover explicit identities, terminal attestation,
stale original source, original-image preservation, pinned assumptions,
unchanged original gate/manifest and separately bound revised staging;
tampering the staged verifier is rejected before checkpoint opening.
**The real routed-DCP release qualification and image generation have not
run.** Wait for the live run's actual terminal result first. Final CDC and
operating-condition review remains required even after physical gates pass.

### Actual checksum-metadata capacity/drop/recovery regression

Added `rdma/tests/test_metadata_backpressure_rtl.py`, without editing any
frozen build input or the already selected integrity testbench. Its first
run (session 57258, **exit 0**) uses the actual 32-entry TX checksum FIFO
and output pipeline, not a shortened/forced-state model. Output is stalled
until cycle 6000. The test observes 5848 cycles with metadata backpressure,
including a malformed frame's final beat while full. All **38** good
packets match the independent byte/checksum/ICRC oracle; the one bad UDP-
destination frame is wholly dropped and four subsequent good packets
recover correctly. Exactly 38 checksum entries are pushed, with no orphan
metadata or deadlock; input/output stalls are 5834/6065 cycles.
The [source-bound result](../results/2026-10-18/rocev2-metadata-capacity-rtl.json)
still uses integrity RTL SHA256 `2231fdad5e3ccb701e1d716f891f8f1a049819b105ccc9273541ead442a195d7`.
This is a functional RTL regression, not physical or hardware acceptance.
It is now included in `make check-rtl` and compact source checks.

The main implementation remains live, now in its explicit post-route
physical optimization. The intermediate routed timing report (before that
last optimizer) is WNS -0.304ns / TNS -147.139ns / hold 0ns, not the final
result. Its worst sample is RX integrity `offset_reg[15]` -> CRC masking /
parallel CRC -> bad-frame comparison -> packet-FIFO BRAM `DINADIN[1]`,
14 logic levels including two CARRY8s; data delay 4.072ns (1.530ns logic /
2.542ns route). This differs from the placed host-queue path and from the
original dense-keep TX-ready path. Do not decide on a queue-pipeline change
or waive this path based on the earlier placed sample. Follow the real
post-route result and exact final paths. No hardware programming occurred.

### Corrected board run terminal: real timing failure, not a blocked goal

The main run is now actually terminal: session 61132 returned **exit 1**,
parent PID 633571 and implementation PID 640072 are absent, and the parent
ended at **07:41:24 UTC**. The final root checkpoint was preserved as
`as02mc04_25g_routed.dcp`, SHA256 `87b4e04d21479890e2799b12e543acfde2383fc45392b8ee5ba9c5ba0cb5f2c9`.
Final setup is **WNS -0.183ns / TNS -65.700ns / 967 failing endpoints**;
hold violations are zero and all 38 bus-skew entries are MET. The actual
worst final path is TX padding `keep[6]` -> byte-count/length/bad-frame logic
-> metadata admission/ready -> width-adapter data-register CE, 14 levels
including two CARRY8s, data delay 3.988ns (1.567 logic / 2.421 route).
The earlier RX-to-BRAM and placed host-queue samples are not this final worst
path. Linked resources are 78467 LUTs / 118989 registers / 160 BRAM tiles /
39 URAM / 1 DSP; resource fit is not timing closure.

The original output gate first rejected its legacy fixed source-register
name, as predicted. The separately identified verification revision was
then actually exercised on this immutable final checkpoint (session 84459,
**exit 1**, ended 07:44:44 UTC). It accepted all six VIO pairs and four LFC
chains/eight destination registers, including exactly the one audited alias;
minimum LFC second-stage setup/hold are 2.159/0.066ns. The exact original
physical gate then rejected **max/setup timing**, so neither directory
produced a bitstream. Both compile and additive verification manifests were
checked unchanged at this rejection. See the
[final corrected diagnostic](../results/2026-10-18/rocev2-board-routed-corrected-diagnostic.json).
This is a real engineering failure to fix, not a reason to mark the goal
complete/blocked, skip the gate or program the failed circuit.

### Unselected input-stage candidate tested separately

While preserving all 297 original build inputs, staged a separate integrity
RTL copy (`rdma/build/icrc-stage-candidate-U3zWwBt5`, SHA256
`f8cea29d8980e00835694cd0808f849b4eb8bcb0c9326deb7cf505f03a89def3`).
The unapplied `rdma/patches/rocev2-icrc-input-stage.patch` records its exact
diff. It reserves a TX metadata slot for every final beat independently of
the combinational bad-frame result (bad frames may backpressure but still
never push metadata) and places the full data/keep/last/bad sideband through
a two-entry vendor skid register before the frame FIFO. No checksum/error
check, FIFO depth, operation, clock requirement or queue/window is removed.

The explicit unselected-source test driver replaces exactly the ICRC source
in four Icarus compilations; no board source or selected evidence is edited.
Both sessions 33113 and 1681 completed **exit 0**. The latest
[candidate evidence](../results/2026-10-18/rocev2-icrc-input-stage-candidate.json)
passes RX whole-frame rejection/checksum tests, TX golden/stall/rejection,
all 65536 keep masks (and 2097152 RX checksum sums), real metadata-capacity
drop/recovery and simulated 31.507692Gb/s payload capacity at assumed 250MHz.
The candidate metadata-full bad-final beat waits 5842 cycles, then all 38
good frames and exactly 38 checksum entries recover correctly. This is
**not a selected board image, full-HLS application test, physical acceptance
or hardware throughput**. Only after the old run/revision are terminal can
the patch and tested LFC assertion revision be selected with fresh source
identity, complete generated-HLS regressions and a new board build.

### Input-stage correction selected after terminal audits

After both the main build and separate release attempt were confirmed
terminal, selected the exact tested input-stage RTL SHA256
`f8cea29d8980e00835694cd0808f849b4eb8bcb0c9326deb7cf505f03a89def3`.
The canonical FPGA LFC assertion file is now a compatibility shim to the
tested shared checker; `fpga/build_25g.tcl` explicitly adds that helper to
the **new** compile identity (expected 298 inputs). The old 297-file
manifest was not rewritten: its identity records the previous source at
the time of that failed build. Its checksums will now appropriately differ
from the deliberately changed worktree. New bitstream acceptance needs the
fresh compile identity and full physical result, not the old diagnostics.

Updated Icarus/generated-HLS/OOC file lists for the already pinned vendor
`axis_register.v`. Current-source RX/TX/Ethernet generated-RTL integration,
integrity/mask/checksum/stall tests, real checksum-capacity regression,
padding tests, and five full-app WRITE/PSN-wrap/coalesced-ACK cases have
completed exit 0. Selected compact records are being refreshed only from
these actual runs; the full-app aggregate awaits the current retry result.
The old real-1ms retry attempt reached the host's explicit **300-second**
simulation limit and emitted no passing JSON (session 21569, exit 1;
Python/VVP PIDs absent). That is not a native hardware failure or a retry
pass. After actual termination, reran with a **900-second host wall limit**,
unchanged 4ns clock, 1ms timer, virtual watchdog and all replay assertions.
Added live log/50000-cycle progress messages only. Current progress is at
least 100000 virtual cycles, one original wire frame and zero ACKs, which
is expected before the 250000-cycle real timer. No clock/timer was shortened.

The newly selected canonical assertion shim itself was also tested on the
previous immutable final DCP by the read-only inspector (session 33575,
**exit 0**, 07:53:45 UTC). It verifies six VIO pairs and four LFC chains,
eight destination registers, one audited alias, and timed second stages,
without adding XDC or modifying the design. See
[canonical checker evidence](../results/2026-10-18/rocev2-canonical-lfc-check.json).
The checkpoint does not contain the new input stage and remains physically
unmet. Its other 18 critical CDC findings were not waived. No new board
build, programming or native traffic has started at this point.

### Current-source real retry passed; fresh full-board synthesis launched

The extended host-wall-time retry run is now actually terminal: session
34998 returned **exit 0**, with **255507** real 4ns virtual cycles, one
withheld ACK, two byte/key/address/PSN/CRC-verified wire transmissions,
one success ACK, one actual HLS retransmission and two pattern reads. Live
progress reached the original real 1ms timer; neither it nor the virtual
watchdog/assertions was shortened. The initial 300-second host timeout is
preserved as a failed/unproven attempt, not included as a pass.

All selected integrity/padding/RX/TX/Ethernet/full-app/retry/metadata records
have now been refreshed from the actual new-source exit-0 results. The five
full-app cases verify 15 WRITEs / 12876 payload bytes / 14 success ACK events,
including wrap/coalescing. Source checks (session 35779) and the unchanged
138-file HLS provenance validator both returned **exit 0**. All remain RTL
or offline evidence, not native RNIC or physical timing acceptance.

Started fresh full-board build **003**, session **30358**, parent PID
**790077**, directory `fpga/builds/as02mc04-25g-rocev2-XnWXCJXt`, log
`rdma/logs/native25-board-build-003.log`. Synthesis and its OOC IP dependency
jobs were launched at **08:07:19 UTC**. At this observation the parent is
live; top `synth_1/runme.log` can be absent while OOC IP dependencies run.
That absence is not evidence the build stopped and does not justify a
restart. Follow the actual session/PID and run logs.

The new **298-input** manifest SHA256 is
`284e278b37a0dd56239874e399c65c4bb648fa27ba26cfdc6f31c47ea20d3648`;
all entries were checked unchanged after launch, including selected input-
stage RTL `f8cea29d...`, canonical LFC shim `d850262f...` and shared checker
`acb5a830...`. Keep **all 298** frozen until the actual build is terminal.
The two vendor AXIS-library copies used by the standalone/full-app/board
flows were also rehashed: `axis_register.v` is identically `599fde2d...`
and `axis_fifo.v` identically `7d1ea178...` in both trees. See the
[selected correction/build record](../results/2026-10-18/rocev2-input-stage-correction.json).

Full-board synthesis/placement/route/setup/hold/native-clock/38-bus-skew/DRC
and actual final CDC/operating-condition review remain pending. Do not use
the old failed checkpoint or simulated capacity as a native RoCE/25G-rate
claim. No FPGA programming, traffic test, flash/fan/network change, commit
or push occurred in this correction. M3/M4/M5 still require actual native
FPGA-to-CX455A memory verification, finite retry/error/queued tests and
receiver-verified 25G-class throughput under the temperature guard.

### Read-only native-driver readiness while build 003 synthesizes

With build 003 still live (parent PID 790077, top synthesis PID 792235),
checked the resident `mqnic` module's `srcversion` against the saved 6.17
module. Both report `2B7846A14E770BA5B472258`; the saved module also has the
current kernel's vermagic. This is consistent build identity, **not a
cryptographic measurement of the resident binary**. The corresponding
existing source has generic BAR2 mapping and APP_ID auxiliary-device
registration; base probe does not require a separately matching application
driver. Nothing reviewed indicates a need to replace the driver before
trying the new image. This is not an FPGA kernel verbs provider.

A read-only mapping of the existing image's BAR0 read only DWORDs 0 and 4:
`0xffffffff` / `0x100`. These are the expected Corundum FW_ID register-block
type/version, **not an all-ones PCI read failure**. BAR2 is still absent.
The actual `--require-application` preflight therefore refused before
creating a QP or generating traffic, as intended. No existing driver was
unloaded/reinstalled and no device register was written.

Separately queried native `mlx5_0` port 1 via `ibv_devinfo` in the dedicated
peer namespace: active Ethernet, max/active RDMA MTU **4096**. The ordinary
preflight confirms 25Gb/full, FEC Off and actual IPv4-mapped RoCEv2 GID index
3; its own implementation does not check active MTU, so the separate query
must not be represented as new automated preflight coverage. BAR2 identity,
mapping, application registration and all link/GID details must still be
checked again after the eventual gated SRAM load. These observations do not
prove native FPGA RDMA or physical closure. See
[pre-program readiness evidence](../results/2026-10-18/rocev2-preprogram-driver-readiness.json).

At **08:34:47 UTC**, a separate five-sample read-only SYSMON/JTAG query
returned **59.71..60.30 C**, over-temperature flag 0, with unchanged
configuration status `0x009079fc` before/after and exit 0. The recorded
maximum since the unknown SYSMON-reset time was 62.33 C, not a new RoCE-load
maximum. The host was compiling build 003; no network load, reset,
programming or fan adjustment was performed. This is a current old-image
temperature observation only. Recheck immediately before programming/tests
and retain the finite traffic guard; it does not qualify a new image or
sustained traffic cooling. See
[pre-program temperature evidence](../results/2026-10-18/rocev2-preprogram-temperature.json).

### Build 003 synthesis complete; full-board implementation running

Top synthesis PID 792235 is now terminal. Its log says `synth_design
completed successfully`, the normal `.vivado.end.rst` is present without an
error marker, and Vivado exited at **08:49:32 UTC**. The command elapsed time
was **37m19s**, with 0 Errors / 0 Critical Warnings. Final command accounting
reports **646 Warnings** (the earlier synthesis-optimization-only summary
reports 503; these are different scopes). The 645 actually emitted
`WARNING:` lines, sorted with multiplicity, are byte-identical to the
previous build's log; both final command totals are 646. This warning
comparison does not waive final DRC, methodology, timing or CDC findings.

The completed standalone `synth_1/fpga.dcp` SHA256 is
`97186fb7e8a3d466ca835de0c0f5d9431f4c1c7d51703a691baa844a292c9054`.
Do not use this OOC-IP top checkpoint alone to prove native clocks, CDCs or
full-board resource totals. Implementation PID **795454** started at
**08:49:38 UTC**, joining the four OOC IPs and loading board/IP constraints.
The original parent PID 790077 and session 30358 remain live; no build was
restarted. The 298-entry source identity remains unchanged. Inspect a
completed, fully linked post-opt checkpoint before early CDC review, then
the actual final routed design before any hardware acceptance. Setup/hold,
38 bus-skew checks, route/DRC, final CDC/operating review and native
FPGA-to-CX455A traffic are still pending. See
[build 003 synthesis evidence](../results/2026-10-18/rocev2-board-synthesis-003.json).

### Build 003 fully linked post-opt CDC inspections complete

Implementation completed `opt_design`, wrote `impl_1/fpga_opt.dcp`, closed
its `.opt_design.end.rst`, then started `place_design -directive Explore`.
The stable checkpoint SHA256 is
`8ce162cc1a93ee73b7531c07cab5ebfd230f7ad6dfe46616eeefc90fd1294ad5`.
Unlike the standalone top synthesis file, this checkpoint joins all four
OOC IPs. Ran the existing read-only inspectors on it without additional
XDC, property changes, checkpoint writes or hardware access; the main
implementation continued concurrently, with all 298 inputs unchanged.

The annotation inspector (session **42630**) returned **exit 0** at
**08:58:15 UTC**: six VIO pairs and four LFC chains/eight destination flops,
one previously audited source alias, exact clocks/resets/ASYNC_REG and
first-D-only cuts verified. The second stages remain timed, not excepted.
Their unplaced minimum setup/hold estimates are **2.087 / -0.055 ns**.
The negative hold is **not waived** by the structural assertion passing.
The unplaced global estimate is setup WNS **0.028 ns**, hold WHS
**-0.661 ns** with **194554 hold-failing endpoints**; the actual report
says timing constraints are not met. This is not post-route timing.

The PHY inspector (session **49314**) returned **exit 0** at **08:57:17 UTC**:
two GT asynchronous-mode pins tied high, 22 static-control bits, four reset
stages and 24 scoped 8ns datapath-only checks (minimum unplaced slack
7.707ns). The CDC report still has the same **18 Critical findings**:
CDC-1 7 / CDC-4 4 / CDC-10 1 / CDC-13 6. None are blanket-waived. Runtime
stability of the single-capture static controls is not proved by this
inspection; the eventual finite test must keep PHY/DRP/PRBS/reset/clock
configuration stable. Final routed structure, all timing/bus-skew/DRC gates
and operating-condition review remain mandatory. Main PID **795454** is
still placing; no image was generated or programmed. See
[new post-opt CDC evidence](../results/2026-10-18/rocev2-postopt-003-cdc.json).

### Build 003 placement complete; new worst path is the receive timestamp enable

The same main process completed `place_design` in **17m51s**, closed its
normal end marker, saved `fpga_placed.dcp` (SHA256
`72c5f31cad8cfeb15800ab4601da0b4fca3fd3fd83914619be70cc56853bd3c9`),
then entered `phys_opt_design -directive AggressiveExplore`. A separate
read-only inspector on that immutable placed file (session **97307**) returned
**exit 0** at **09:17:57 UTC**; no additional XDC, design/property/route edits
or checkpoint/image writes were made.

The actual sampled worst placed setup path is now **-0.069ns** at **2.56ns**:
SFP1/port0 RX decoder `xgmii_rxd_reg[7]` to the MAC receive timestamp
`ptp_ts_reg[14]/CE`. It contains three LUT levels, 2.262ns data delay
(0.502ns logic / 1.760ns estimated route), and -0.288ns clock skew. This is
not the previous integrity mask/metadata-ready worst path; it does not prove
that every integrity path or final routing passes. Keep the unused physical
port and all original clocks/features enabled, rather than changing the
acceptance scope. Worst placed hold remains **-0.618ns**, PCIe CC data[81]
to the PCIe hard IP, with its already compiled setup-2/hold-1 multicycle
constraint. No exception was changed and neither violation is waived.

The current separate main physical optimization has reached an estimated
WNS/TNS of **-0.025 / -0.025ns**; this is a newer in-progress estimate, not the
placed diagnostic file's result and not final closure. The existing main
PID 795454/session 30358 remains active with the 298 inputs unchanged.
Continue through routing and the unchanged complete setup/hold/native-clock/
38-bus-skew/DRC gate, then final CDC/operating review. No image was programmed
and no native FPGA RDMA result exists yet. See
[placed build 003 diagnosis](../results/2026-10-18/rocev2-board-placed-003-diagnostic.json).

### Build 003 pre-route optimization completed; router active

The same main process completed `phys_opt_design -directive AggressiveExplore`
in **7m23s**, with 0 Errors / 0 Critical Warnings (38 ordinary Warnings),
closed the normal step marker and wrote `fpga_physopt.dcp` SHA256
`0ff0d7ca1e335c003c8e43d18436f18841cb2bd04d96c352384e1ea7a90c1e65`.
Its final **pre-route estimate** is setup WNS/TNS **0.015 / 0.000ns**, hold
WHS/THS **-0.583 / -422.719ns**. The tool optimized 1007 of 1067 candidate
hold nets and inserted 800 buffers. Positive setup alone is not full timing
acceptance; the remaining negative hold is not waived.

`route_design -directive Explore -tns_cleanup` is now live in the unchanged
session 30358/PID 795454. Saved an immutable prefix of the implementation
log ending *before* the route command so this completed-step evidence can
be hash-bound while the original log continues growing. All 298 compile
inputs remain unchanged. Route/hold cleanup, post-route optimization and
the complete final setup/hold/clock/38-bus-skew/DRC gate, followed by actual
final CDC/operating review, remain mandatory. No FPGA image was programmed,
and native RDMA/throughput are still unverified. See
[pre-route build 003 evidence](../results/2026-10-18/rocev2-preroute-003.json).

### Build 003 passed the original full physical gate; conditional review complete

The actual full build session **30358 returned exit 0**. Vivado exited at
**09:53:35 UTC**, after the unchanged output gate and completed bitstream/
debug-probe writes. Final setup WNS/TNS is **0.027 / 0.000ns**, hold WHS/THS
**0.010 / 0.000ns**, with zero failing endpoints. All 12 `check_timing`
categories are zero; all **184184** routable nets are fully routed, zero
routing errors; all **38** bus-skew checks are MET. Four native Ethernet GT
output clocks are 2.56ns, six VIO pairs and four LFC chains pass. Final DRC
has 29 ordinary Warning checks, no Errors/Critical Warnings. No clocks,
exceptions, window/capacity or physical ports were removed/relaxed.

Selected generated bitstream SHA256:
`ce5151679a0aeb2442f164ba63f7d85a3e753218808d588cdd46a4c498a31f60`.
Final routed DCP SHA256:
`5ac0fb9fb13bba440c831b753f152604bf6a7e50e767c4b9f1a78b30b52e4bad`.
The exact 298-file compile manifest remains unchanged after terminal exit.
The final DCP was independently inspected without new XDC or design edits:
annotation reader **51173 exit 0**, **09:56:27 UTC**; PHY reader **34674 exit
0**, **09:54:49 UTC**. LFC second-stage minima are setup **1.867ns** / hold
**0.066ns**. All 24 scoped 8ns PHY/DRP datapath checks pass, minimum routed
slack **6.626ns**, two GT mode pins tied high, 22 static control bits and
four reset stages checked. Normalized Critical CDC rows exactly match the
reviewed post-opt checkpoint (18 in each), not merely the same total.

This does **not** assert unconditional CDC safety. The 18 findings remain
visible/unwaived. The controlled finite WRITE trial must keep PHY/DRP/PRBS/
polarity/PLL/rate/global clock/reset configuration stable after startup.
[AMD UG578 v1.4, Table 3-39](https://docs.amd.com/api/khub/documents/BY7rRWkUQliMvNvosLhSZA/content)
confirms the asynchronous-control meaning of the actual high GT mode pins.
The final methodology report has 63 Warning / 3 Advisory checks and no
Error/Critical checks; its 11 async-reset warnings are five debug-hub,
five vendor PCIe and one 125MHz-reset instances. Do not operate Hardware
Manager, reprogram or hot/reset PCIe while transferring. The VIO generator
has six inputs/zero outputs; thermal supervision uses read-only SYSMON
JTAG operations. Reviewed existing `mqnic` link-status polling calls only
status-read getters; the finite native client maps/writes only ROC2 BAR2,
not PHY BAR0 controls. These are explicit operating conditions, not waived
timing or a proof against arbitrary concurrent configuration changes.

**Not yet programmed.** Before the first SRAM load, freshly recheck
temperature, exact PCI identity/exclusive bridge, management isolation and
rollback-image hashes. After programming, rediscover actual MAC/GID and
verify ROC2 BAR2 identity/quiescence before creating the native peer QP/MR.
Keep BIOS Medium and all finite thermal/deadline guards. Native M3/M4/M5
memory verification, retry/boundary/queued cases and 25G-class RDMA
throughput remain undone; RTL/simulation/static acceptance is not a native
RDMA claim. See [accepted build 003 static evidence](../results/2026-10-18/rocev2-board-build-003.json).

## Build003 SRAM bringup and first native RoCEv2 results — 2026-10-18

The preceding "not yet programmed" status describes the static-review
checkpoint, not the later hardware state. After fresh temperature, PCI
identity, exclusive-bridge and rollback-image checks, accepted build003
(`ce5151679a0aeb2442f164ba63f7d85a3e753218808d588cdd46a4c498a31f60`)
was loaded into **SRAM only**, programmer session60137, terminal exit0.
Only FPGA endpoint82:00.0 was removed and its exclusive bridge80:03.0
rescanned. No host reboot, bridge reset or global rescan was required. The
existing mqnic driver returned with ROC2 BAR2. Dedicated interface1/port0
was restored to its test namespace/IP/MTU; actual new MAC is
`ea:09:19:ea:b1:ea`. Management interface/address/default route, hfi1, CX mode,
flash and BIOS Medium fan settings were preserved. Fresh five-sample
temperature ranges were 59.18–59.51C before and 55.35–55.58C after loading,
OT=0 and configuration status unchanged.

Four native FPGA bounded-pattern WRITE cases then passed to CX455A
mlx5_0 (03:00.0), IPv4 RoCEv2 GID3, actual path MTU4096, Ethernet25G/FECOff:

| Payload × messages | Verified bytes | Local initial PSN | Payload Gbit/s |
| --- | ---: | --- | ---: |
| 64 × 1 | 64 | 0x123456 | 0.0242 |
| 65 × 3 | 195 | 0xfffffe (wraps through zero) | 0.0734 |
| 4096 × 3 | 12,288 | 0x234567 | 3.9410 |
| 4096 × 16,384 | 67,108,864 | 0x345678 | 24.2640 |

Every receiver MR byte was complement-prefilled then verified: **16,391
WRITEs / 67,121,411 bytes / zero mismatches** in total. FPGA issued/ACK/read
counts, TX completion activity and terminal core/TX quiescence passed. The
64MiB case used5,531,559 hardware cycles at250MHz, **22.126236ms** including
initialization/drain. Its read-only thermal guard finished exit0 with observed
60.32C preflight /60.62C final temperature. This single finite case is **not**
sustained thermal or production reliability qualification. TCP carried only
control/verification, no payload; no software RXE device was created.

Endpoint and bridge remain Gen3x8. Their PCI status dumps before the64MiB
case and after all cases are byte-identical. The bridge already had sticky
FatalErr+/SDES+; these were not cleared. Root AER reporting is disabled, so
zero Linux error counters alone cannot prove complete error reporting.

Current scope is experimental IPv4 RC WRITE_ONLY initiation from a bounded
FPGA-local pattern through the custom BAR2 controller, **not** a general FPGA
verbs provider, inbound WRITE/READ, or native InfiniBand. Controlled ACK-loss
retry and error/recovery hardware cases remain M4 work. The conditional CDC
operating restrictions remain in force; no blanket waiver or timing/capacity
relaxation was introduced. Per-case `fpga_programmed:false` describes only the
native test harness (which did not program), not the preceding SRAM bringup.

Durable records: [SRAM bringup](../results/2026-10-18/rocev2-sram-bringup-003.json)
and [four native cases](../results/2026-10-18/rocev2-native-003.json). Their raw
record hashes and controller/receiver identities were revalidated against
the existing logs and current unchanged baseline source.

## M4 native ACK-loss retry, expected timeout and recovery — 2026-10-18

The unchanged accepted build003 now passes actual controlled fault tests,
not just the earlier RTL model. Ten new RX-control/cleanup and six verdict
model tests pass (57 Python host tests in all); no hardware is accessed by
those unit tests. The final routed CDC report explicitly labels the selected
RX-enable crossing CDC-3 Info, two stages with ASYNC_REG and first-stage false
path. Pinned source traces it through `eth_rx_enable` to MAC `cfg_rx_enable`.
The live BAR0 register chain discovers interface1/port0's C003 child and
RX_CTRL at0x840024. Only its enable/pause writable bits are borrowed/restored.
No PHY/DRP/clock/global-reset changes are made. This separately reviewed fault
control is distinct from the baseline BAR2-only operating condition; all other
conditional-CDC restrictions remain, with no new waiver or bitstream change.

| Finite hardware case | Observed outcome |
| --- | --- |
| ACK loss, 65B ×1 | RX off1.545ms; before restoring, issued1/ACK0, two reads/130 bytes and two injected TX/completions. After restoring: ACK1, all65 MR bytes correct, DONE/quiescent. Three total reads due to continued retry. |
| Expected watchdog, 65B ×1 | HLS1ms timer unchanged; only controller timeout10ms. ERROR2 after2,500,002 clocks (10.000008ms), issued1/ACK0, four reads/260 bytes. RX restored after10.774ms; TX quiescent and all65 receiver bytes correct. **Not an acknowledged WRITE success.** |
| Normal65B ×1 after error | New native QP/MR; starts from quiescent ERROR0x83c and reaches DONE0x73a/ACK1 with65/65 bytes correct, using the existing CLEAR-to-IDLE path. No NIC reset or reprogramming. |

All three guards exited0, observed58.85–59.22C; BIOS Medium was retained.
Read-only postchecks confirm ROC2 DONE/core-reset/TX-quiet/halt, MAC RX writable
bits restored to1, both test links up, native mlx5_0 with no RXE, management
IPv4/MAC/MTU/default route unchanged. Domain-formatted PCI dumps are byte
identical to before the64MiB case, including retained bridge FatalErr+/SDES+
and disabled Root AER reporting. These are finite controlled cases, not full
loss/congestion/protection-NAK coverage or production qualification.

An independent100ms restoration thread supplements ordinary exception/abort
restoration. Deadline expiry or unverified restoration fails the test; this
is not a hard real-time guarantee against SIGKILL, OS suspension, host failure
or device removal. TCP metadata is exchanged before disabling RX, and MR
verification/release is allowed only after RX restoration and TX quiescence.

Evidence: [offline fault tests](../results/2026-10-18/rocev2-mac-rx-fault-unit.json)
and [actual native retry/timeout/recovery](../results/2026-10-18/rocev2-native-retry-recovery-003.json).
The raw logs, baseline controller, new fault helpers/tests and receiver binary
are hash-bound; retries did not alter the HLS timer or accepted298-file manifest.

## End-state audit

All six incremental milestones now have the required finite experimental
evidence: actual FPGA/native25 RoCEv2 transport, native CX455A registered-memory
verification, queue/tail/PSN-wrap, ACK-loss retry, observable watchdog/error and
subsequent recovery, plus receiver-verified25G-class payload throughput. The
goal has not been replaced by a software reference, Ethernet-only link test,
single-packet demonstration or simulation-only claim. The original objective
is retained verbatim in the [requirement-by-requirement audit](../results/2026-10-18/rocev2-completion-audit-003.json).

Final offline regression: `make -C rdma check` terminal exit0, **73 Python
host/RTL tests** across14 suites plus the C peer self-test. Source-check CI
also passes. These are separate from the actual native hardware records;
offline tests do not by themselves certify hardware. The selected138 HLS
files match aggregate24866cb7..., and all298 board-build inputs remain
unchanged. Static/programming/native/fault records bind127 artifact/source/
raw-log hashes, independently rechecked before the final audit.

The delivered capability remains the documented experimental IPv4 RC WRITE
initiator with a bounded local pattern and custom BAR2 control. Inbound
WRITE/READ, a general FPGA host-memory verbs provider, native InfiniBand,
arbitrary congestion/protection/failure modes and sustained thermal/production
qualification are **not implemented or established**. These are possible
subsequent projects, not capabilities inferred from this experiment. BIOS
Medium, SRAM-only operation and management/unrelated-device isolation were
preserved. The resulting code/records are local worktree changes, not a claim
that these new changes have been committed or pushed.
