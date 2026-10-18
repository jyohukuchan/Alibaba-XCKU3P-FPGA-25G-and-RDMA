# READ implementation and verification

User objective: **READ機能を追加して。**

In the preceding conversation READ means the FPGA initiator reads memory
registered on the native CX455A peer, receives the returned data into a
protected FPGA-local buffer, and makes that actual data inspectable by the
host. This is not a request to replace hardware READ with host software,
only generate a request packet, or implement a full verbs provider first.

## Completion evidence required

1. Real READ requests from the FPGA to the native CX455A on the existing25G
   path, with the peer MR explicitly granting REMOTE_READ.
2. Returned data stored in bounded FPGA memory and independently read back
   by the host: all requested bytes compared, not just a counter/checksum.
   Include non-repeating per-run source data, tails, multiple operations,
   PSN wrap and at least one response segmented across the4096-byte PMTU.
3. Explicit local-range/QP/length/stream framing protection. READ completion
   must wait for payload commitment, not merely the HLS completion metadata
   that can precede data. Malformed or unsolicited traffic cannot write host
   memory; no arbitrary PCIe DMA is to be introduced.
4. Existing WRITE support retained and regression-tested in the resulting
   image, including an actual acknowledged receiver-verified WRITE case.
5. New image passes the unchanged full-board setup/hold/native-clock/routing/
   bus-skew/DRC gates, with separate CDC review and exact source/artifact
   identities. Preserve the accepted WRITE build003 as rollback.
6. Native tests are finite and temperature-supervised. Retain BIOS Medium,
   SRAM-only programming, management networking and unrelated devices; no
   sustained load/flash/global rescan or unrelated reset.

## Milestones

| ID | Step | Current state |
| --- | --- | --- |
| R0 | Trace pinned transport READ interfaces and preserve baseline | Verified; separate pinned checkout and patch reconstruction |
| R1 | READ wire oracle and actual generated-HLS request/response tests | Verified offline for13sizes1..65536; not hardware |
| R2 | Protected payload buffer, host readback and completion/control RTL | Implemented; now connected to the version2 BAR API in the combined app |
| R3 | Complete READ/WRITE app integration with real generated HLS | Verified offline for READ/WRITE, segmented/wrapped multi-READ, warm/stale/host cases |
| R4 | Full-board implementation and physical/CDC review | Completed; original final native25 gate passes; final conditional CDC/PHY review retained |
| R5 | SRAM bringup and native READ plus WRITE/error regressions | Completed;8native READ cases,2same-image WRITE regressions, all-byte zero mismatch, guarded |

## Baseline and source review

Preserved accepted WRITE003 rollback (running before this work):
`ce5151679a0aeb2442f164ba63f7d85a3e753218808d588cdd46a4c498a31f60`.
Its reports show78659/162720LUTs,119453/325440FFs,160/360BRAM tiles and
39/48URAM. These counts suggest room for a bounded BRAM receive path but do
not prove fit or timing for READ. Do not edit the frozen298-input baseline
or relabel its historical native evidence as a READ result.

Pinned FNS source75c32bae... already implements RC_READ_REQUEST0x0c and
responses0x0d..0x10. The accepted baseline outer ingress admits ACK0x11 only and the
endpoint intentionally treats memory-write outputs as a fault. READ requires
new protected connections, not simply changing the SQ opcode.

Source trace finds two details to verify in actual generated RTL before
integration: READ completion metadata uses rd=0 (WRITE's ACK uses1), and is
emitted before the payload write pipeline completes. The RX payload-length
calculation includes UDP/BTH/AETH/ICRC but appears not to subtract BTH pad
bytes. A65-byte response may therefore produce a68-byte memory command.
These were initially source observations. They are now measured in the
generated RTL probes below, but are not hardware results.

Initial receive-memory design direction: a bounded BRAM window with host
prefill/readback,64-byte-aligned per-operation slots, descriptor-authorized
writes and explicit payload-commit counters. Handle multi-PMTU responses and
up to3wire-padding bytes without treating padding as application data. No
public inbound WRITE/SEND or READ-responder memory is exposed by this step.

## READ request defect found in generated baseline RTL

The initial actual-HLS probe fails before RX: the published transport marks
all64lanes of its512-bit READ RETH word valid although the RETH is16bytes
and has no payload. The resulting IPv4 packet declares60bytes including
ICRC but emits104bytes before ICRC, including48uninitialized extra bytes.
The existing TX integrity gate correctly rejects it. Failed raw evidence is
preserved in `rdma/logs/read-hls-probe-initial-001.log` through `-003.log`;
there is no passing initial-probe report or READ hardware result.

The separate `rdma/read/hls/fns-read-fixes.patch` limits READ RETH keep to
16valid bytes when the data word is wider than the header. It does not
relax integrity checks or modify WRITE's payload/header path. Synthesis
uses a separate pinned FNS checkout and a new output directory; the
accepted WRITE build003 and HLS010 source/artifacts remain untouched.

## Current verified offline implementation

New generated READ HLS profile:
`/home/user/fpga-rocev2-research/probe-ku3p-512-8qp-read-001`.
Its138Verilog/data-file aggregate is
`7bcfddc9cb856060ccc3fbe4c8599538a03bf16105176b44f737c22fb0be55ff`.
`rocev2-read-hls-source-001.json` reconstructs the exact pinned source plus
the compatibility patch and READ keep fix, and checks every modified file
against that independent temporary reconstruction.

`rocev2-read-hls-probe-001.json` passes sizes1,2,3,4,63,64,65,4095,4096,
4097,8192,8193,65536. It uses the actual generated HLS and unchanged
integrity wrapper, verifies emitted READ request metadata/checksums and all
returned payload bytes, including segmented response PSNs wrapping at24bits.
The65-byte response produces a68-byte memory command with3padding bytes;
its transport completion occurs before data commitment under backpressure.

New RTL:

- `rdma/read/rtl/rocev2_read_buffer.v`:256KiB bounded BRAM,32descriptor
  slots,64-byte-aligned non-overlapping destinations, PMTU-aware command
  validation, QP/flags/keep/TLAST/range protection, no host DMA. Host accesses
  while capture is enabled fail closed. Host prefill and unused sentinel
  bytes survive per-run clear. RAM commit counters advance only when the
  pipelined write actually reaches RAM.
- `rdma/read/rtl/rocev2_read_engine.v`: READ-only controller with configurable
  read-resource window1..32, up to65536bytes/operation within the256KiB
  capture extent, full remote VA/rkey, reserved response PSNs, timeout/abort
  and TX-drain sequencing. DONE requires transport completion, all requested
  bytes committed, and capture idle; an early completion alone is insufficient.

`rocev2-read-capture-probe-003.json` verifies actual HLS outputs stored in
the current protected RAM, then all65/4097payload bytes read back through
the RTL host port;127unused sentinel bytes per case remain unchanged.
`rocev2-read-control-probe-001.json` repeats those two cases with the actual
READ controller driving QP/connection/SQ and deciding DONE/reset, not a
testbench-generated READ command. Physical MAC completion is still modeled;
there is no Ethernet application, PCIe transaction, or native RNIC here.

`rocev2-read-engine-rtl-002.json` records8controller tests, including
multi-operation PSN reservation/wrap, window capacity, post-START config
snapshot, late/short/non-idle capture, invalid configuration/completions,
timeout, abort, memory fault, and host-busy refusal. The controller tests
model completion/capture inputs; the separate integration probe exercises
the real generated HLS and actual capture RAM.

`rocev2-read-hls-write-regression-001.json` passes the existing full WRITE
application RTL with this new HLS:65bytes x3, initialPSN0xfffffe and
cumulative ACKs. This is not yet the required WRITE hardware regression
on a new combined READ/WRITE image.

## Physical capture-buffer probe (not board signoff)

The first buffer OOC run fails: setupWNS-4.929ns, holdWHS-0.151ns.
Its worst setup path is a wide keep-mask shift/subtract/comparison chain
driving BRAM write enables. The source is frozen with the failed evidence.
Parallel lane checks and a registered RAM write stage improve the second
run toWNS-0.026ns/WHS+0.049ns, still a failed gate. Prefetching descriptor
arithmetic removes the remaining LUTRAM/subtract/pad/compare chain.

`rocev2-read-buffer-ooc-003.json` passes the isolated buffer at4ns:
setupWNS+0.203ns, holdWHS+0.048ns,64BRAM primitives. The OOC I/O model is
explicit: inputmin0.2ns/max0.5ns, outputmin0/max0.5ns. The first run used
ideal zero-delay ports and its zero-delay external-input hold paths were
not physically routeable. This isolated model is not the final-board clock
model or a waiver of setup/hold/CDC/routing/skew/DRC gates.

Latest standalone unit evidence is `rocev2-read-buffer-rtl-004.json`
(7tests) and `rocev2-read-engine-rtl-002.json` (8tests), plus4wire-oracle
tests:19tests pass in `rdma/logs/read-wire-buffer-engine-002.log`. The
full256KiB buffer case queues four65536-byte descriptors, consumes64PMTU
commands and verifies all262144bytes by host-port readback. Its928400
simulated cycles include host prefill/readback and are not a line-rate
performance result. Legacy `make -C rdma check` and `scripts/check.sh`
also pass with the original WRITE sources/gates unchanged.

## Combined application implemented and verified offline

Separate new files preserve the frozen WRITE003 baseline:

- `rdma/read/rtl/rocev2_rw_control.v`: exclusive version2API, old WRITE
  engine/pattern source plus READ engine/capture RAM, protected32-bit BAR
  memory bridge, independent AW/W/AR buffering and single RAM-port ownership.
  A simultaneous RAM read/START cannot cancel the read or arm the engine.
- `rdma/read/rtl/rocev2_rw_ethernet_rx.v`: peer/QP/tuple/full-frame guards
  extended only to READ response opcodes in READ mode. Per-run generation
  tagging discards queued old responses; routes are frozen before presenting
  TVALID so an epoch change cannot withdraw a stalled frame. Generation
  exhaustion fails closed rather than wrapping. Inbound WRITE/SEND/READ
  requests remain disallowed; host sideband/data preservation is retained.
- `rdma/read/rtl/rocev2_rw_endpoint.v` and
  `rdma/read/fpga/mqnic_app_block.v`: real combined endpoint/app wiring,
  preserving all original MAC framing, TX admission/physical drain, other
  ports and unchanged HLS/integrity blocks. Each actual READ SQ handshake
  commits its protected descriptor; a stalled SQ is not prematurely leased.

The API is documented in `docs/ROCEV2_RW_API.md`; it is not yet deployed.

Current combined-app evidence:

- `rocev2-rw-control-rtl-001.json`:5tests covering old WRITE behavior,
  independent RAM ownership, byte enables/bounds, READ commit gating,
  busy/terminal config locking, warm READ-to-WRITE, unauthorized capture,
  abort/recovery, no generation wrap, and simultaneous AR/START.
- `rocev2-rw-ingress-rtl-001.json`:2tests covering all READ response
  opcodes, mode-at-SOP snapshot, peer/QP/error/keep/oversize guards, host
  preservation and old responses behind backpressured ordinary host traffic.
- `rocev2-rw-write-app-001.json`: actual new full app/generated HLS,
 65bytes x3 with PSNwrap/cumulative ACKs and all wire bytes checked.
- `rocev2-rw-read-app-003.json`: actual new full app/generated HLS,
 65bytes x3; all195bytes read back through BAR plus253sentinel bytes.
- `rocev2-rw-read-app-002.json`:4097bytes x3, six response packets,
  wrapped PSNs and all12291payload bytes independently BAR-read back.
- `rocev2-rw-warm-app-001.json`: two4097-byte READ runs using the same
  QP/PSNs but different source data. An old-run READ_FIRST is held behind an
  ordinary host frame until run2 transmits. It is discarded, the host frame
  is byte-exact, and both READ data sets /8194bytes are BAR-read back.
- `rocev2-rw-timer-rtl-002.json`: actual generated timer, real4ns clock /
 1ms RTO, all8QPs/restart phases, stop, backpressure and warm reset. The
  first Verilator attempt terminated with a host simulator segfault; its
  failure log remains. Icarus passed the unchanged protocol/timing assertions;
  no accelerated timer or shortened retry interval was used.
- `rocev2-rw-build-gate-002.json`:5preflight predicate/hash tests including
  incomplete READ data/protection, weakened WRITE/warm evidence and changed
  source/native gate identity negative controls. Initial validator coding
  failure is retained as build-gate001, not claimed as passing evidence.
- `rocev2-rw-build-inputs-001.json`: current source/artifact preflight passes,
  including the accepted003 native25 gates/clock/board hashes unchanged.

These tests model the remote RNIC and MAC SFD completion. They do not prove
native PCIe transactions, physical MAC EOF, full-board timing or hardware READ.

## Active full-board build

Launched via `rdma/read/fpga/build_board.sh`; build directory:
`fpga/builds/as02mc04-25g-rw-g9gbomFJ`, parent tool session9912,
Vivado process1050775 at launch. Root log:`rdma/logs/rw-board-build-001.log`.
Liveness must be rechecked through the tool handle/PID, not inferred from this
document. No board result is claimed until the process is terminal and all
actual reports are inspected. Do not edit compile/verification inputs while
it is live; documentation and new independent native-host files are separate.

At15:42UTC on2026-10-18, synth_1 was terminal and successful (zero errors,
zero critical warnings). The final synthesis report/checkpoint are present;
preliminary usage is88546/162720LUTs,130173/325440FFs,204/360BRAM tiles
and39/48URAM. These are synthesis counts, not routed signoff or proof of
timing. Parent session9912/PID1050775 continued into impl_1, whose Vivado
PID was1056655 at observation. Revalidate that process before relying on
this observation; do not restart the build merely because synth_1 ended.

The driver uses a separate source selector and exact new-app/HLS tests.
It reuses the original config, implementation strategy and final output gate:
native390.625MHz MAC clocks, full setup/hold/route/38bus-skew/DRC checks and
VIO/MAC-flow CDC assertions remain unchanged. The new isolated-buffer OOC
I/O assumptions are not loaded into the board build. Passing preflight or
buffer OOC does not imply the full-board gate passed.

The completed linked post-opt checkpoint is
`as02mc04_25g.runs/impl_1/fpga_opt.dcp` in that build, SHA256
`84de3833a9f7ea4203cad96d107c37c0f2cc6b5cc2cf2f783446b065bb26abb9`.
Read-only annotation inspection session3286 and PHY inspection session93668
both exited0. Six VIO two-stage pairs and all four LFC chains/eight destination
registers retain their compiled protection. The18critical CDC rows exactly
match accepted WRITE003 after normalizing whitespace/row numbers and including
the source/destination clocks, description, depth, exception and endpoints.
Counts remain CDC-1=7,CDC-4=4,CDC-10=1,CDC-13=6; none were waived.

Both GT asynchronous-control mode pins remain tied high;22static PHY bits,
four reset stages and24scoped8ns max-datapath paths were checked. Minimum
post-opt scoped slack is7.707ns, not final routed slack. Runtime PHY/DRP/PLL/
PRBS stability is still an operating condition, not an unconditional CDC-safety
claim. No extra XDC, property changes or checkpoint writes were used by these
inspections. Final routed physical/CDC review remains mandatory. See
`rocev2-rw-postopt-cdc-001.json` and its source/raw-report hashes.

A read-only JTAG observation of the still-loaded WRITE003 image measured
59.94..60.46C over10samples, maximum recorded61.12C, OT=0; configuration
status stayed0x009079fc before/after. No fan changes were made. This is not
the new image's temperature or permission to skip fresh pre-program/test
thermal checks.

## Placed checkpoint and additional full-buffer verification

The immutable placed checkpoint SHA256 is
`14916ac6128392d27d6b9b8eb24b2f48a77cf5aac373ae687625d222f59226cc`.
Read-only clock/path inspection session98877 exited0; its diagnostic is
`rocev2-rw-placed-diagnostic-001.json`, not a physical pass. Worst placed setup
was-0.014ns on the existing Corundum completion-queue URAM/control path;
worst hold was-0.597ns on PCIe CC data[191]. The original implementation then
continued through AggressiveExplore physical optimization into routing.
Intermediate positive setup estimates do not waive the final hold/setup,
native-clock, routing, skew, DRC or CDC requirements.

The additional full-app65536-byte x4/window2 Icarus run (session78502) ended
with command exit1 because the simulator exceeded its1200-second wall limit.
The original runner did not preserve partial simulator stdout in that exception;
no full-buffer pass or absence of RTL deadlock can be inferred. Its raw failure
log and `rocev2-rw-read-app-004-timeout.json` remain; the normal app004 pass
report does not exist. Existing standalone256KiB and smaller combined-app
results are not relabeled as this missing full-app result.

Separate experimental compiled-simulation files use the unchanged original
testbench,4ns clock,250000-cycle device timeout and source RTL. System
Verilator5.020 compiled a known65-byte x3 case but its executable crashed
(SIGSEGV), including with a64MiB stack. GDB reproduces the failure in
`std::coroutine_handle::destroy` / `VlCoroutineHandle` during evaluation,
before any passing result. The exact failed executable/fixtures are retained
in `rdma/read/build/simulator-failure-o56u30xi`; this is not a READ failure/pass
classification. Upstream issue5906 and the5.036 release describe a related
fork-coroutine use-after-free fix; matching the exact root cause remains an
inference until a controlled version comparison succeeds.

A private Verilator5.036 checkout at upstream commit
`eca2b4c9603554a6a4596befd485c3dd4f550769` is being built outside the board
inputs at `/home/user/fpga-rocev2-research/verilator-v5.036`, targeting the
separate `verilator-v5.036-install` prefix. Initial build session31507 failed
for missing FlexLexer.h; dependencies were supplied and session28042 resumed
the build. Revalidate live processes; do not infer liveness from these names.
The system Verilator is unchanged. GDB and build dependencies were newly
installed with no package upgrades/removals or service restarts. Once built,
first cross-check the known65-byte case against Icarus, then the same full
256KiB case. A two-state result cannot be claimed as four-state verification
or as a native FPGA/PCIe result. No FPGA image was programmed in this work.

The resumed private simulator build (session28042) subsequently completed
with exit0. Installed5.036 is separate from the unchanged system5.020;
the upstream checkout has no tracked source diff. With the exact original
bench/RTL, known65bytes x3/window2 now passes
(`rocev2-rw-read-app-compiled-003.json`, session12689 exit0). Generated HLS,
request/completion counts, all195payload bytes,253sentinels and the payload
digest exactly match the Icarus app003 case. The old5.020 crash remains
recorded; a larger process stack did not fix it. This controlled version
comparison resolves the executable-crash obstacle but does not prove that
upstream issue5906 is the exact sole root cause.

The additional65536bytes x4/window2 full-buffer case now also passes in
compiled simulation (`rocev2-rw-read-app-compiled-004.json`, session84324
exit0):64response packets, PSN wrap,4READ completions, all262144BAR payload
bytes compared;65555AXI writes and65563AXI reads over1466041simulated cycles.
All4transport completions can arrive before RAM commitment; DONE still waits
for protected RAM. The entire requested extent was complement-prefilled.
This exact-full case has0extra sentinel bytes because all256KiB are payload;
tail/sentinel protection remains separately covered by the smaller cases.
Same4ns clock,250000-cycle device timeout and unchanged generated HLS were
used. The33.62-second simulator execution is CPU runtime, not FPGA latency or
throughput. This is explicitly a two-state RTL result, not an Icarus pass or
actual RNIC/PCIe proof. Its source/tool/executable/bench hashes are recorded.

## Native tools prepared (before the subsequent SRAM bringup)

Independent files under `rdma/read/host/` are outside the active CAD manifest:

- `rc_read_peer.c` registers a native mlx5_0/CX455A REMOTE_READ-only source
  MR. It uses a fresh32-byte kernel nonce and SHAKE256-derived data, retains
  an independent source copy and checks every source byte at completion.
  TCP carries endpoint/nonce metadata and controls, never the source payload.
- `fpga_rw_client.py` retains the audited PCI identity/shared lock, requires
  version2 and the exact capture layout, prefills payload complements and
  sentinels, requires real capture/commit counters and compares every BAR
  byte. Existing WRITE still uses the original all-byte native receiver path.
- `native_rw_preflight.py` reuses the original read-only network/native-GID
  audit but never calls its version1 BAR interpreter. Unknown/v1 images stop
  after ID/version; they cannot start a version2 operation.
- `native_rw_test.py` pins the validated temperature guard and read-only
  JTAG sensor hashes, supervises only owned finite child processes, checks
  the native source MR/QP/nonce/provider against actual BAR results and
  cannot claim a native result until thermal supervision also succeeds.

Current native-tool evidence is33offline tests:13client,6preflight,
8supervisor and6error/recovery tests, plus the C/Python byte-exact self-test.
Reports are `rocev2-rw-native-client-unit-002.json`,
`rocev2-rw-native-preflight-unit-003.json`,
`rocev2-rw-native-supervisor-unit-003.json` and
`rocev2-rw-native-recovery-unit-001.json`; raw passing log is
`rdma/logs/rw-native-host-suite-002.log`. The first combined invocation's
assertions passed but its relative report path was wrong under `make -C`;
that failed log remains as `rw-native-host-suite-001.log`.
The full READ/RW suite now passes64tests in10suites, including the original
31RTL/wire/gate tests and these33native-tool models. Its terminal command
exit status was0 (`rdma/logs/rw-read-suite-003.log`).

`--probe-config-error` keeps the peer MR/QP and BAR ownership for a
one-byte-short remote extent rejection, app-local CLEAR and the following
valid native READ. It checks zero READ SQ/authorization/capture progress,
quiescence, monotonic generations and unchanged cumulative RoCE TX/completion
counters across the rejected run. No global/NIC reset is requested.
`rocev2-rw-recovery-app-001.json` verifies the same flow with the actual
combined app/generated HLS:65bytes x3 with PSN wrap;1303invalid-probe cycles
with zero QP/connection/SQ/network valid cycles; ERR_CONFIG=1; no post-boot
global reset; all448prefill bytes survive ERROR/CLEAR; all195returned bytes
and253sentinels are BAR-read back. RNIC/physical MAC remain models.

At that stage read-only real-device checks showed the accepted version1
WRITE003 app and dedicated native25G/RoCEv2 path. Version2 preflight correctly
refused it. No READ hardware operation/programming had yet taken place;
the subsequent actual SRAM bringup and native results follow below.

## Final board and native acceptance (2026-10-18)

The build finished with exit0 at16:38:42UTC. Final original physical gates
pass: setup+0.052ns, hold+0.010ns,206064/206064nets fully routed, all38bus
skews (minimum+1.743ns), all12check-timing categories zero, all four native
GT clocks2.560ns and0Error/Critical in DRC (35ordinary warning checks).
Final routed CDC/PHY inspections both exited0; all18Critical rows exactly
match accepted WRITE003, with the documented static PHY/DRP/reset operating
conditions retained rather than waived. Source manifest has766lines/
600unique inputs, all hashes rechecked. Exact new bitstream:
`226c48c7756f311d511798c42435a438f20228eb313b909553638b12c3a58e0a`.
See [final physical/CDC record](../results/2026-10-18/rocev2-rw-board-build-001.json).

After a fresh58.89..59.41°Ccheck, only the audited FPGA endpoint was removed,
the exact serial-selected JTAG adapter programmed SRAM (exit0), and only its
exclusive bridge was rescanned. Actual version2/256KiB layout/quiescence and
the restored dedicated native25G/RoCEv2 path passed read-only preflight.
No flash/global rescan/bridge reset, fan change or management-network change.
See [SRAM bringup](../results/2026-10-18/rocev2-rw-sram-bringup-001.json).

Native READ then passed1x1,65x3,4097x3,8193x3,65536x4,4096x64,1x4096 and
65x1after one-byte-short configuration rejection/CLEAR. Each READ used an
independent fresh nonce/source MR and actual PCIe BAR all-byte readback,
not a software substitute. Total565515payload bytes and259061sentinels
match. Segmentation,3-byte wire padding, PSN wrap, full256KiB and windows1/2
are covered. Same-image native WRITE65x3/wrap and4096x3 verify12483receiver
bytes. All mismatches zero; peer MRs retained until verified quiescence.
The11generations (10valid runs plus1invalid configuration) end in quiescent
WRITE DONE; all owned helpers stopped/control port free.

All10cases were thermally supervised (20samples53.59..56.07°C); post-test
current56.60..56.86°C, OT0. BIOS Medium was independently read back active;
management address/routes/MAC/MTU/flags remain unchanged. No sustained load,
commit or push. Final offline READ suite:64tests/10suites plus C self-test,
exit0; source checks also exit0. Historical simulator timeout/crashes and
failed buffer OOC runs remain correctly labeled, not converted to passes.

See [native aggregate](../results/2026-10-18/rocev2-rw-native-001.json),
[results/use guide](ROCEV2_READ_RESULTS.md) and
[six-requirement completion audit](../results/2026-10-18/rocev2-read-completion-audit-001.json).
The capability is the originally requested bounded FPGA READ initiator with
protected local capture and retained WRITE, not a full verbs provider,
inbound SEND/WRITE target/READ responder, arbitrary host DMA or sustained
performance/reliability qualification. Configuration remains SRAM-only.
