# RC64 Atomic candidate execution

Progress081 adds a real **responder memory execution** feature, not complete
native Atomic support. Default native RTL and `IB_ATOMIC_NONE` are unchanged.
The original protected responder, legacy images, clocks and all timing/drain
gates are untouched. Nothing is programmed, installed or loaded.

Explicit publication (2026-10-21) includes progress152/153 and the unfinished
remote-WRITE MR guard (syntax-only, not functionally/native qualified).
Successful and failed evidence is retained; no Atomic advertisement,
hardware/default change or original timing waiver accompanies this push.
Local/unpushed descriptions below preserve historical checkpoint states.

Progress153 adds separate segmented incoming WRITE/Immediate HLS and late
notification-RQ source. ALL65 actual C++ modes include every44 old mode,
including Atomic compatibility; ALL62 RQ component cases retain all48 old.
This does not update the current native core or qualify Atomic/WRITE
Immediate hardware: new native MR/DMA/HLS/MAC/CQ integration, synthesis,
matched software and original timing/physical work remain. Atomic_NONE and
all default/hardware settings stay unchanged.
[Separate component scope](../results/2026-10-18/rocev2-rnic-segmented-write-receive-diagnostics-001.json).

Progress152: corrected receive-native004 now PASSES ALL34, including both
8193-byte incoming cases and every old Atomic/READ/WRITE/SEND/zero case.
Matched separate profile7 kernel source builds against real headers;170
callback-model cases,2442 IO cases,all8 provider identities and90 actual
unedited-native SQ/RQ/CQ snapshot cases pass. These retain old Atomic paths
but do NOT qualify Atomic hardware or advertise it: IB_ATOMIC_NONE remains.
Linux/MMIO/pin/DMA/completion boundaries remain modeled; original4ns timing,
live kernel/RTL coupling and physical proof remain unmet/unverified.
[Native/software scope](../results/2026-10-18/rocev2-rnic-segmented-receive-native-software-diagnostics-001.json).
All11 requirements remain incomplete; this addition is not automatically pushed.

Publication after progress151: full-native003 fails at the second incoming
SEND packet; it is NOT an Atomic or large receive pass. Read-only original
object diagnosis identifies a held-group raw-reference admission stall.
A separate narrow continuation fix passes nine gate cases/old-gate negative
control and complete actual-HLS native elaboration002. Its full34-case
runtime, including Atomic regressions, has NOT run. Prior all32 compatibility
results apply to the prior uncorrected graph only. Original4ns timing,
IB_ATOMIC_NONE, installed/default profile and all11 requirements remain.
[Fixed-graph compile only](../results/2026-10-18/rocev2-rnic-segmented-receive-native-elaboration-002.json).
The following progress entries are historical snapshots.

Progress150 passes ALL32 exact old native cases on the new receive core,
including Atomic compatibility, not new large incoming runtime. New actual
8193-byte receive plus all32 old cases (34 total) is now building003 after
full bench elaboration; no pass inferred yet. Original004 HLS7200s timeout
and new fixture001/002 failures remain. [Native regression audit](../results/2026-10-18/rocev2-rnic-segmented-receive-native-regressions-diagnostics-001.json).

Progress149 produces actual new receiver HLS and passes complete native
elaboration plus real descriptor-PCIe/MR/RQ posting tests. HLS estimate15.571ns
misses original4ns; fresh all32 old native regression build is live, not yet
passed. No large incoming native payload or Atomic hardware qualification is
inferred. [Current audit](../results/2026-10-18/rocev2-rnic-segmented-receive-generated-diagnostics-001.json).

The progress147 publication additionally includes the 1 MiB posted-RECV
codec/typed adapter and real MR-to-RQ component tests, plus a separately
regressed KEEP checker. These do not enable native Atomic or qualify a new
hardware/software profile. [Publication scope](../results/2026-10-18/rocev2-rnic-segmented-receive-publication-diagnostics-001.json).

## Large incoming SEND/Immediate source and actual RQ/ACK/CQ components (146)

The separate new receiver passes44 HLS C++ modes and real message-RQ/ACK/
CQ-publisher component coupling, including8193 bytes/3 packet releases/one
actual event and complete AXI owner/actual-length/Immediate/host-ACK guard
checks. MR/backend/PHY/host and HLS proof producers remain models in those
component tests; no live native/Linux/physical proof is claimed. New source
65535/255/13/31 coordinates15 changed leaves/40 bodies, while actual new HLS
generation is still running. Its syntax-only check ignores missing leaves,
not complete elaboration. Existing profile6 incoming RQ4096/Atomic_NONE and
all original11 requirements remain. [Current component evidence](../results/2026-10-18/rocev2-rnic-receive-message-native-components-diagnostics-001.json).

## Actual native large Immediate and matched software source (143)

[Fresh complete-native001](../results/2026-10-18/rocev2-rnic-segmented-immediate-native-full-001.json)
PASSES ALL32 cases:8193 SEND/WRITE Immediate and ALL30 previous cases. Actual
new generated HLS and source graph, not a reused executable. Compile633.005s;
runtimes4.125..6.430s, new6.229/6.429s, original1200s/30s limits retained.
Each new WR has one actual full-range local MR grant,3 child source reads/
shared unique physical nonces/statuses,3 packet expectations/real board-MAC
FCS/SFD/CDC frames,2 replay-cache advances,one whole HLS receipt and CQ. Six
paged descriptors/68 read TLPs; no source data writes/fences. Independent
full-wire/Immediate-LAST-only/PSN wrap/C128/748-owner and all16384 source/
sentinel bytes pass. Final actual MAC receipt is withheld so memory/ACK
cannot prematurely complete CQ. Physical host/root/peer/PHY/PTP remain
MODELS; ordinary READ retains its explicit previous MAC-pin model. Small
SEND_IMM now uses retained source ownership and actual board MAC as well.

New separate exact32767/127/profile6 kernel/provider source extends profile5
without changing any old/default selection. Actual standard WR adapter safely
accesses extended RDMA objects only for WRITE_WITH_IMM; base SEND_WITH_IMM is
ASan guarded. Full source ranges/keys/network-order Immediate and actual MR/
PD/ref/SQ replay/CQ/failure retention remain. [Full real-header build001](../results/2026-10-18/rocev2-rnic-segmented-immediate-kernel-build-001.json)
PASSES10.242s, gated by all32 current native results. [Adapter002](../results/2026-10-18/rocev2-rnic-segmented-immediate-verbs-adapter-002.json)
PASSES real-header5.138s/ASan-UBSan0.012s,48 new large/22 compatibility/22
negative cases plus unchanged old READ/WRITE/SEND/Atomic/zero assertions.
[Standard C callbacks001](../results/2026-10-18/rocev2-rnic-segmented-immediate-kernel-post-001.json)
ALL134 PASS (44 new/all90 old), including mixed tuple/geometry refusals,
full-MR ranges/source-read permission, unknown producer retention, wrong
Immediate/full CQ owner, CQ pressure, zero and1MiB modeled source operations.
[Native snapshot integration001](../results/2026-10-18/rocev2-rnic-segmented-immediate-kernel-native-cq-001.json)
ALL80 PASS:16 unedited real native SQ/CQ pairs/four negative mutations each;
every128 posted byte and actual C CQ/MR-ref retirement match. [Provider001](../results/2026-10-18/rocev2-rnic-provider-segmented-immediate-001.json)
ALL7 identities PASS, all6 old retained,4097/8193/1MiB Immediate/SGE/full keys/
standard chain/second bad-WR/WC marshalling through actual libibverbs/private
provider. ONLY fake-fd syscalls/WC replies are modeled on that provider path.

[Audit001](../results/2026-10-18/rocev2-rnic-segmented-immediate-native-software-diagnostics-001.json)
verifies2586 new/103 historical/1665 old native bindings; strict fixture-count
and test-main/indentation failures/preimages are preserved, no gates relaxed.
Linux/MMIO/pins/DMA/CQ completion boundaries remain models and snapshot
executions are separate, not live Linux/RTL or matching physical page tables.
Native1MiB, large inbound receive/Immediate, multi-SGE, recovery/congestion/
interop/original full-board timing and physical qualification remain open;
HLS13.885ns still misses4ns/default1.08ns. RQ4096/single SGE/defaults/Atomic_NONE
unchanged; all11 scope remains. No install/load/program/network/fan/BIOS/
flash/reboot/automatic Git change.

## Segmented Immediate requester, actual HLS and whole native wiring (142, historical)

New `hls/segmented_immediate_transport.py` extends the same real READ-capable
transport. True SEND/WRITE FIRST/MIDDLE/LAST, not independent ONLY requests;
only LAST carries the full network-order Immediate. One748-bit trusted owner,
exact per-fragment replay metadata/PSN and actual ACK/pointer/pool/timer/common
state consumers precede the next fragment and final whole-WR receipt.
[C++001](../results/2026-10-18/rocev2-rnic-segmented-immediate-hls-001.json)
PASSES ALL21 modes (all11 previous READ/WRITE/SEND/zero/Atomic modes retained).
Each new op6 whole WRs/284 packets/13 real stored first/middle/LAST replays,
sizes4097/8192/8193/12289/65537/1MiB, values0/ffffffff/high values, PSN wrap,
poisoned invalid source lanes, independent complete wire/zero-pad oracles.
Withheld ACK/timer/PSN consumers block progress. Maximum new runtime5.469s,
unchanged30s bounds. [Compatibility001](../results/2026-10-18/rocev2-rnic-segmented-immediate-compat-001.json)
retains actual Atomic service RTL and Immediate TX/RX assertions.

[Actual HLS generation001](../results/2026-10-18/rocev2-rnic-segmented-immediate-generated-hls-001.json)
PASSES374.863s with original frozen-source/ports/1500MiB guard/4ns/default
1.08ns/8QP/2000.81375 LUT/99264 FF/209 BRAM18K/0 DSP; estimate13.885ns FAILS
original timing. Separate `fpga/derive_segmented_immediate.py` changes14
coordinated native leaves for full-range admission/source ownership, actual
LAST-Immediate header/pad/replay/whole-PSN joins and distinct32767/127 identity.
Its [complete native elaboration001](../results/2026-10-18/rocev2-rnic-segmented-immediate-native-elaboration-001.json)
PASSES3.510s, strict port widths/module multiplicities/shared HLS/PSN/MSN/MR/PTE
domains and both global drains0 preserved. This is compilation, NOT new
Immediate native payload/DMA/MAC/CQ execution or original timing proof.

Actual private C128 codec26 methods (all20 old) PASS; real MR/HLS-SQ61 cases,
source/unchanged native child19, wire/cache/MAC/CQ17, exact register/CQ27 cases
with20 publications, padding/ICRC9 methods PASS. Backend/RX/ACK/CQ/MAC-pin and
control endpoints are MODELS; six actual HLS C++ captures through ICRC are
separate snapshot executions, not live HLS RTL. The MR tests distinguish
source reads from READ-result local writes, including valid read-only source,
stale full key/PD/full range and no authorization from raw command addresses.
[Audit001](../results/2026-10-18/rocev2-rnic-segmented-immediate-diagnostics-001.json)
verifies4513 current/648 historical bindings. Every failed batch/preimage is
kept; only wrong macro/helper/record container/MR fixture/metadata anchors
were corrected. All checks, full-owner gates and original limits remain.

No new matched kernel/provider profile or standard API support is claimed.
Receive buffers remain4096; large inbound receive/Immediate, multi-SGE,
recovery/congestion/interop, native new Immediate and physical/timing work
remain. Old/default/profile5 sources and IB_ATOMIC_NONE are unchanged; all11
original requirements remain open, no hardware/program/load/network/fan/BIOS/
flash/reboot/Git action. Next integrate genuine native runtime and software,
not a capability advertisement or reuse of an old native binary as proof.

## Matched large READ kernel/provider source and actual C integration (140)

New `kernel/derive_segmented_read_kernel.py` adds explicit software profile5
only for exact RNC16383/CQC63/SQC13/RQC15/stride128 and full existing geometry.
Mixed old/new tuples refuse before queues. New Linux READ adapter, source-only
`verbs_segmented_read_wqe.c/.h`, selects the already checked full-range codec
for READ>4096, with safe extended-WR access only after proving READ kind.
Old WRITE/SEND/zero/short/Immediate/Atomic use unchanged adapters. Actual SQ
encode/decode/replay/CQ comparisons use READ codec only for this profile; full
MR/PD/local-write/range/refs/rings/uncertain-producer/CQ lifetime gates remain.
The new uninstalled source returns its1MiB port message limit only after
profile5 binding ([standard port attribute](https://raw.githubusercontent.com/linux-rdma/rdma-core/v50.0/libibverbs/man/ibv_query_port.3));
single SGE and4KiB receive/Immediate policies remain explicitly enforced.
Old profiles/defaults and IB_ATOMIC_NONE stay unchanged.

[Full real-header kernel build001](../results/2026-10-18/rocev2-rnic-segmented-read-kernel-build-001.json)
PASSES9.989s, actual new symbols linked, no install/load. [WR adapter001](../results/2026-10-18/rocev2-rnic-segmented-read-verbs-adapter-001.json)
also builds actual headers4.482s and runs ASan/UBSan0.012s: all54 positive/14
negative original cases plus24 large READ,15 compatibility positives and14
new negatives, full64 fields/ranges and base-only SEND allocation guarded.
[Standard C posting003](../results/2026-10-18/rocev2-rnic-segmented-read-kernel-post-003.json)
PASSES ALL90 cases, all65 old plus25 new. Full READ permission/range/key,
mixed geometry, wrong CQ, backpressure, ambiguous publication and no premature
MR release are checked. [Native snapshot integration001](../results/2026-10-18/rocev2-rnic-segmented-read-kernel-native-cq-001.json)
PASSES70 cases:14 actual unedited SQ/CQ operation pairs, including8193 READ,
with four labeled in-memory negative mutations each; all128 posted bytes and
actual C MR-ref/CQ retirement match. Linux/MMIO/pins/DMA/peer are MODELS or
separate executions, NOT live kernel/RTL or physically matching page tables.

New provider derivation adds only exact FW16383 identity, retaining all5 old
and the standard kernel-owned verbs/uverbs path. [Provider001](../results/2026-10-18/rocev2-rnic-provider-segmented-read-001.json)
PASSES all6 identities with actual installed libibverbs and private provider
C:4097/8193/1MiB READ+SEND chains, full64 addresses/keys/SGE serialization,
exact second bad-WR, registered MR handles and correct READ WC lengths.
Only fake-fd syscall/WC replies are models; no direct user BAR/DMA/C128 path.
All C/provider cases remain<10s (observed maxima0.015/0.016/0.018s).
[Software audit001](../results/2026-10-18/rocev2-rnic-segmented-read-software-diagnostics-001.json)
verifies626 successful bindings plus84/90 historical and1665 native139 bindings.
Failed startup/indentation/wrong allocated-SQ-count fixture oracles remain
separate with exact preimages; no failed batch relabeled or kernel gate relaxed.

This is a new matched SOURCE feature, not installed/live Linux/standard API/
hardware/timing qualification. Native1MiB READ, large receive/Immediate,
multi-SGE/recovery/interoperability remain incomplete; all11 scope and original
HLS13.885ns>4ns/default1.08ns/board gates remain. No hardware/module/network/
fan/BIOS/program/flash/reboot or automatic Git changes.

## Actual complete-native8193 READ and all29 regressions PASS (139)

[Full-native001](../results/2026-10-18/rocev2-rnic-segmented-read-command-queue-native-full-001.json)
PASSES ALL30 cases: new8193-byte READ plus ALL29 prior cases, unchanged inputs/
independent oracles/1200s compilation/30s runtime. Fresh -O1 host compile takes
623.025s; cases4.175..6.279s, large READ6.078s. This confirms the two-entry
owner-checked metadata lookahead resolves the actual generated-HLS command/
payload wait, without bypassing serial data/status/fence/whole-owner joins.

Large READ uses genuine coherent SQ fetch, actual MR/PTE/protected RX/MSN/
generated HLS/child DMA/common nonreusing nonce/backend statuses/host visibility
fences/board FIFO-FCS-SFD-CDC-MAC/CQ RTL. It has3 actual commands/statuses/
fences,3 RX packets,one protected placement/HLS full receipt/aggregate memory
event/CQ and8193 placed bytes.4read/67write TLPs and one real SFD/MAC receipt
are required. HLS receipt binds the full owner and response spanfffffe->000001.
Withheld real MAC receipt still prevents early HLS/WR/CQ release. Every16384
host byte/padding/sentinel and whole READ owner/status/ABI63 CQ were independently
rechecked from preserved C128 input and captures; no observations normalized.
[Audit001](../results/2026-10-18/rocev2-rnic-segmented-read-command-queue-native-diagnostics-001.json)
verifies ALL1665 bindings (1449 source/214 artifact/2 RAM) unchanged. Failed
configuration/timeout/functional-stall/fixture attempts stay separate and intact.

Physical host/root/peer/PHY/PTP endpoints are MODELS. Old ordinary READ and
Immediate cases keep their original MAC-pin completion models; the new large
READ uses actual board-TX receipt RTL. This is no actual Linux/standard API/
physical or native1MiB READ proof. Experimental source profile16383/63 admits
1MiB; old/default8191/31/kernel/provider READ4096 and Atomic_NONE stay unchanged.
Exact matched new kernel/provider binding is the next coarse functional step.
All11 original scope remains; HLS13.885ns still fails4ns/default1.08ns and board
fit/CDC/routing/DRC/timing remain unproved. No hardware/module/network/fan/BIOS/
program/flash/reboot or automatic Git change.

## Bounded READ command lookahead for the observed payload wait (138)

[Optimized native002](../results/2026-10-18/rocev2-rnic-segmented-read-route-o1-native-full-002.json)
compiles620.672s and reaches the original cycle deadline in9.436s. This is NOT
the earlier30s host timeout: first4096-byte fragment/status/fence completes,
but second child waits for2176 bytes while data_ready1/data_valid0 and the next
command is blocked. State is stable18000..28000cycles; RX3/commands2/status1/
event0/fenced4096. All1510 bindings and exact source preimages/model/binary/log
are preserved; no full native READ/CQ/regression success is claimed.

`derive_segmented_read_command_queue.py` extends the exact route candidate,
changing ONLY the READ mux. Two96-bit future metadata entries are independently
checked against the genuine full saved owner and queued extent, after accepted
protected placement and with a live guard. Existing bounded child checks the
same metadata again before actual DMA. Data/status/fences remain serial and
all original full-owner/CQ joins stay, additionally requiring an empty queue
and full queued extent at retirement. No HLS/default/clock/geometry changes.
This is intended to break command/data producer dependency, not to invent a
memory grant or completion; actual generated-HLS verification remains pending.

[Component001](../results/2026-10-18/rocev2-rnic-segmented-read-command-queue-001.json)
PASSES12 methods/23 cases, keeping all17 prior mux cases. New cases cover a
coupled producer requiring next metadata before the prior payload finishes
(8193 bytes), full two-entry backpressure/five fragments(16385 bytes), and four
malformed/unknown future-command refusals. Child/unpad/mux/common nonce are
real RTL; HLS/owner/placement/backend status/fences/CQ are MODELS. Maximum
case0.342s; original10s per-case bound. Initial source-anchor failure retains
exact preimages and zero compiled/runtime cases. [Native elaboration001](../results/2026-10-18/rocev2-rnic-segmented-read-command-queue-native-elaboration-001.json)
PASSES3.418s/1422 bindings, same45 module-kind/domain counts. All23 unit mux
bodies equal selected native bytes;37 other generated RTL files are identical.
[Audit001](../results/2026-10-18/rocev2-rnic-segmented-read-command-queue-diagnostics-001.json)
also rechecks372 unit bindings and preserves original functional failure.

Fresh actual HLS/native compilation is live with all30 original cases/oracles,
1200s compile/30s runtime, -O1 HOST simulation and read-only queue snapshots.
No successful native large READ/DMA/host visibility/CQ, matched kernel/provider
or physical/timing qualification yet. All11 requirements and original timing
13.885ns>4ns/default1.08ns remain; no hardware/fan/BIOS/module/network/reboot/Git
changes. Old/default8191/31 keeps READ4096 and Atomic_NONE.

## Genuine native READ issue/DMA progress, unresolved30s timeout (137)

[Corrected-route full-native001](../results/2026-10-18/rocev2-rnic-segmented-read-route-native-full-001.json)
passes Icarus elaboration and fresh Verilator/C++ compilation433.696s, then
passes the previous actual QP_TX setup failure. Real coherent SQ/MR work
issues one real READ request through board-faithful MAC/FCS/SFD/CDC. First
4096-byte paged writes (3+4093) and one-byte visibility-fence read descriptors
are observed. The first LARGE_READ runtime reaches the original30s wall bound
and TIMES OUT. No completed case is recorded; the old29 cases are NOT run in
this batch. Host visibility/whole READ/CQ success is NOT established.

[Same-binary diagnostic001](../results/2026-10-18/rocev2-rnic-segmented-read-route-native-timeout-diagnostic-001.json)
uses the exact failed frozen binary and copied identical .hex/.dat inputs in
a fresh directory. Only stdout/stderr line buffering changes; original30s
limit remains. It reaches24000 cycles,33 write TLPs and the same first fence
without fault lines, but no second physical write descriptor. This does NOT
exclude a functional deadlock, manufacture success, or relabel the failed
batch. All1508 original and47 diagnostic bindings were verified unchanged;
failed run/source preimages and binary/model/log/report remain intact.

New `probe_segmented_read_route_o1_native_full.py` changes only HOST C++
optimization from -O0 to -O1 and selects read-only progress snapshots. Actual
RTL/inputs/independent data, descriptor, nonce, PSN, MSN, MAC and CQ oracles,
all30 cases, original1200s compile/30s runtime and FPGA clocks/geometry stay
unchanged. `segmented_read_route_progress_native_fixture.py` inherits the
entire previous bench and adds actual child/unpad/status/nonce/backend prints;
it cannot supply a status, grant, owner or CQ. First O1 attempt fails Icarus
before C++ compilation because seven observation paths omitted the actual
native_endpoint.datapath hierarchy segment. Its1499 bindings and exact fixture
preimage were saved before correcting ONLY those paths. Fresh002 compilation
is live; no optimized runtime pass yet. [Audit002](../results/2026-10-18/rocev2-rnic-segmented-read-route-native-diagnostics-002.json)
records these limits/failures without relaxing them.

This is progress past configuration into real native issue/first DMA, not
finished large READ or a green regression. Unqualified16383/63 source keeps
1MiB admission; old/default/kernel/provider8191/31 READ4096 and Atomic_NONE
remain unchanged. Original HLS13.885ns still fails4ns/default1.08ns/full-board
timing. All11 scope retained; no hardware/module/network/fan/BIOS/program/
flash/reboot or automatic Git changes.

## Preserve effective routes across actual QP_TX acceptance (136)

The real `rocev2_mr_control.v` requires all peer/IP/RX_PSN fields to be zero
for QP_TX, and requires an existing matching normal QP/QPN/PD. It changes only
TX PSN. The original MSN observer nevertheless copied those empty fields as a
new valid route. New `derive_segmented_read_route.py` extends the unchanged
qualified READ profile and changes ONLY two observer lines: update route on
accepted non-TX-only configuration, preserve it across accepted QP_TX. The
actual controller/HLS PSN path, predictor rules, configuration guards, source
identities/capacity/clocks and default/kernel/provider selections are intact.

[Component003](../results/2026-10-18/rocev2-rnic-segmented-read-config-route-003.json)
PASSES six short four-state cases. Exact original observer plus actual MR
controller/MR/PTE/predictor reproduce route erasure and fault0xa2. Same actual
command under corrected observer preserves peer196/IPs and accepts TX_PSN
0x89abcd without fault. Before-QP/wrong QPN/PD/12 forbidden-field mutations
remain rejected; stalled commands cannot update observation; normal reapply
and reset remain checked. Decoded host input/QP apply/quiescence/parent drain
are MODELS; SQC identity is explicitly absent, NO WR is issued. This isolates
configuration, not data/identity/HLS/DMA/CQ or physical operation.

First probes001/002 retain their first three passing observations but FAIL:
001's varied-field loop used undeclared i;002's deliberate slot1 mutation was
correctly rejected and echoed slot1, while the reused reply helper expected
only slot0. Exact failed source/artifacts/preimages are preserved before
declaring a dedicated loop index and independently expecting slot1 for just
that mutation. Exact slot equality/all other reply and route checks remain.
[Audit003](../results/2026-10-18/rocev2-rnic-segmented-read-config-route-diagnostics-003.json)
verifies130/132 historical,140 fresh component,1419 complete-native elaboration
and1503 original failed-native bindings. Changed historical probe hashes
resolve ONLY to exact preimages.37 common native RTL files are byte-identical;
only the two controlled-responder observer lines differ.

[Corrected complete-native elaboration001](../results/2026-10-18/rocev2-rnic-segmented-read-route-native-elaboration-001.json)
PASSES3.436s with every original READ-profile module/domain/identity/width/
drain gate plus the new component source gate. A fresh full-native build is
live, retaining the actual8193 READ and all29 old cases/independent oracles,
1200s compile/30s runtime limits. A fixture wrapper only prints actual faults
before the unchanged original fatal assertion. NO corrected native READ
payload/DMA/visibility/CQ or regression pass is claimed yet. The old failed
native model/log/report are unchanged. Original timing still fails13.885ns;
no hardware/default/module/network/fan/BIOS/flash/reboot or Git change.

## Full native READ runtime attempt: build PASS, setup FAIL (135)

The new `tests/segmented_read_native_fixture.py` and
`tests/probe_segmented_read_native_full.py` add one8193-byte READ before ALL29
prior native cases, keeping their original checks and30s runtime limits.
The actual C128 descriptor, generated READ HLS, coherent SQ fetch, real
MR/PTE/DMA/common nonce, protected RX/MSN, retained owner, MAC and CQ are
connected. Host/root/peer/PHY/PTP are models; this is not Linux or hardware.
The new fixture independently checks expected8193 payload bytes, full64-bit
scattered addresses, PSN wrap, three logical placement commands, page splits,
posted-write fences and one final whole-owner CQ. These are test expectations,
NOT successful observed transfers.

[Fixture startup001](../results/2026-10-18/rocev2-rnic-read-native-fixture-startup-001.json)
retains an oracle-clone source-anchor failure before RTL compilation.
[Full-native001](../results/2026-10-18/rocev2-rnic-segmented-read-native-full-001.json)
retains an elaboration failure: a read-only observer used a nonexistent root
alias for the executor's memory-event READY. Its1492 bindings and exact source
preimages were preserved before changing only that observation to the actual
executor port. Production RTL and all original assertions remain unchanged.

[Full-native002](../results/2026-10-18/rocev2-rnic-segmented-read-native-full-002.json)
passes complete Icarus elaboration and fresh Verilator/C++ compilation in
436.743s, under the original1200s bound. The first LARGE_READ runtime then
**FAILS** in16.398s during QP setup, before SQ fetch/READ data, with
`main native RNIC fault 00`. None of the remaining29 cases ran in this batch.
The cause is not confirmed; the TX-only configuration/route observer needs
diagnosis. No data, MR grant, DMA completion, MSN or CQ success is injected or
inferred from compilation. [Audit002](../results/2026-10-18/rocev2-rnic-segmented-read-native-diagnostics-002.json)
verifies all1503 recorded source/artifact/RAM bindings and preserves the
terminal excerpt. Failed reports/models/logs are unchanged, not relabeled.

The new profile is still unqualified for native large-READ execution, matched
kernel/provider APIs or physical operation. The old8191/31/default profiles
keep READ4096. HLS13.885ns still misses original4ns/default1.08ns; no timing,
CDC/DRC/routing gate is waived. This is a user-requested WIP source publication,
not a green release or a hardware/default/module/fan/BIOS/network change.

## Distinct READ-capable admission profile and real MR/SQ/CQ components (134)

`fpga/derive_segmented_read_profile.py` creates a separately named experimental
RNC16383/CQC63 graph from the complete133 candidate. Only actual WQE admission,
HLS-SQ staging, CQ limit and control identity leaves change. READ/WRITE/SEND
allow<=1MiB; Immediate/receive retain4096 and Atomic retains8-byte policies.
Old8191/31/default/kernel/provider selection remains unchanged and cannot
silently claim this new profile. No native runtime is inferred from opening
the gates; kernel/provider matching and standard API execution are NOT added.

New `kernel/wqe_segmented_read.c/.h` explicitly validate the real whole READ
range/fields before bounded serialization reuse; no MR grant, PD, DMA offset
or post operation is created. Original codecs stay unchanged and reject large
READ. [Actual C/UBSan codec001](../results/2026-10-18/rocev2-rnic-segmented-read-wqe-001.json)
PASSES20 methods: ALL15 original zero/Atomic/WRITE/SEND methods plus five new
READ methods. Independent128-byte oracles cover1..1MiB, full remote keys,
full64 local/remote ranges/top byte/overflow, epoch/sequence/flags/operands/
Immediate/reserved bytes, overlapping buffers/nulls and zeroed error outputs.
This is serialization, not Linux driver/device capability or authorization.

[Actual MR/SQ admission001](../results/2026-10-18/rocev2-rnic-segmented-read-admission-001.json)
PASSES11 methods/26 four-state cases, keeping all8 old Atomic admission methods.
Actual C128 records feed the actual SQ bridge/WQE admission and REAL local MR
table configured through its management ports. Large4097..1MiB READs query
full range/key/PD/local-write permission; wrong key/PD/read-only/range deny,
malformed length/epoch/sequence/operands/reserved fields refuse before query.
Wrong/unknown external MR replies and stalled work retain original safeguards.
Raw fetched-record source/consumer are MODELS, not actual PCIe SQ fetch/HLS/
DMA/CQ. No software grant or internal force supplies MR success.

Its two initial import attempts have separate
[startup001](../results/2026-10-18/rocev2-rnic-segmented-read-admission-startup-001.json)/
[startup002](../results/2026-10-18/rocev2-rnic-segmented-read-admission-startup-002.json)
and exact preimages: a class method's indentation could not be dedented because
its literal multiline Verilog has zero-indent lines. It is now compiled inside
a temporary Python class, preserving every original literal/oracle; ONLY the
C codec entry point changes. Those attempts compiled/executed ZERO RTL cases.

[Actual HLS-SQ staging001](../results/2026-10-18/rocev2-rnic-segmented-read-hls-sq-001.json)
PASSES8 methods/21 four-state cases, keeping all5 original Atomic methods.
Full748 owner MUST hand off under the real downstream guard before the exact
408-bit READ SQ appears. Large lengths/keys, noncanonical/unknown metadata,
denied work, missing/late-lost guard and held-SQ stability remain checked.
Work/executor/HLS endpoints are MODELS, not actual HLS execution or CQ proof.

[Register/CQ profile001](../results/2026-10-18/rocev2-rnic-segmented-read-profile-001.json)
FAILS before compilation because its negative-fixture builder tried to replace
an ABI assertion already removed by the original reject fixture's initial
block replacement. [Diagnostic001](../results/2026-10-18/rocev2-rnic-segmented-read-profile-diagnostics-001.json)
verifies133 bindings and exact preimage BEFORE reusing the unchanged negative
fixture directly. Positive CQ still explicitly requires ABI63 and12 real
immutable publications/ACKs; no original invalid-owner assertion is weakened.
[Fresh profile002](../results/2026-10-18/rocev2-rnic-segmented-read-profile-002.json)
PASSES ALL27 cases: all6 controller scenarios, dependency-fatal controls,
old8 CQ owners plus4 large READ owners,11 invalid owners including READ>1MiB.
Control/ticket/commit/retire endpoints are models; real register/CQ logic runs.

New `segmented_read_profile_native_sources.py` and native elaboration checker
require ALL codec/MR/HLS-SQ/profile and prior RX/MSN/memory/lifetime/HLS gates.
[Complete native001](../results/2026-10-18/rocev2-rnic-segmented-read-profile-native-elaboration-001.json)
PASSES3.448s/1415 bindings with READ admission OPEN only in this distinct1MiB
candidate. All parent module/shared HLS/PSN/MSN/RX/Atomic/MR/PTE/physical nonce
counts match, no width mismatch/stub and both global drains0. Original clocks/
geometry/capacity and all strict source/artifact gates remain unchanged.
[Audit002](../results/2026-10-18/rocev2-rnic-segmented-read-profile-diagnostics-002.json)
reverifies14 C codec/218 MR/150 HLS-SQ/133 failed/241 fresh profile/1415 native
bindings; only the exact historical probe preimage resolves changed source.
All52 MR leaf copies,21 HLS-SQ bodies and2 RNC/CQC bodies equal selected native
bytes. Startup preimages are independently hash verified; no report relabeling.

This is component RUNTIME plus complete-native COMPILE, NOT execution of a
genuinely fetched large READ through native MR/RX/generated-HLS/DMA/status/
host visibility/CQ. Next fresh native runtime must add large READ and retain
all29 old cases/oracles/<=30s bounds; old executables or rewritten observations
are not new-source proof. Old software profiles/defaults/Atomic_NONE remain,
and there is no matched kernel/provider/API/physical qualification. Mid-READ
retry, large receive/Immediate/multiSGE/recovery and all11 scope remain open.
HLS13.885ns still fails original4ns/default1.08ns and full-board fit/CDC/routing/
DRC/timing is unproved. No hardware/module/install/load/network/fan/BIOS/program/
flash/reboot or automatic Git changes.

## Actual protected READ RX/MSN/memory/whole-WR lifetime wiring (133, historical)

New `fpga/derive_segmented_read_lifetime.py` extends the exact132 candidate,
not any default/source RTL. The request stays one whole READ/RETH. Its actual
post-integrity TX first PSN is retained, while an independent READ response
index checks FIRST/MIDDLE/LAST and each consecutive/wrapping PSN. FIRST and
MIDDLE cannot set whole-RX complete, rotate the outbound request cache or
produce CQ. LAST alone completes RX and ACKs retained replay. Final HLS ACK
must carry LAST PSN (READ_ONLY still uses first); the816-bit producer receipt
must match full748 owner, first PSN, next PSN=first+response span, READ opcode
and clear status. The actual shared-HLS consumer uses the same response span.
Existing actual aggregate memory, replay/MAC/SFD/EOF/unchanged1024-cycle tail
and exact CQ commit/drain joins remain separate mandatory witnesses.

The exact protected segmented RX is selected and receives actual
`expected_remote_msn` from the genuine accepted-QP/SQC observer, never a
constant/RX-learned AETH/local incoming MSN. Its single whole placement token
continues into the existing actual READ-memory selector/unpad/controller and
common MR/PTE/physical nonce/backend. The outer lifetime independently checks
packet ordering; existing READ-fragment metadata outputs are explicitly unused
at the native boundary, not substituted for aggregate DMA/visibility/CQ proof.
MAC owner allows a whole large READ context but still frames ONE short READ
request. WRITE/SEND per-packet source/cache advance logic is unchanged.

[Lifetime001](../results/2026-10-18/rocev2-rnic-segmented-read-lifetime-001.json)
records19 successful new READ cases but FAILS the full suite: all five inherited
WRITE/SEND methods error before compilation because the new Python generator
omitted the existing `helpers` export. [Diagnostic001](../results/2026-10-18/rocev2-rnic-segmented-read-lifetime-diagnostics-001.json)
verifies222 bindings, preserves exact generator/test preimages and all20
uncompiled inherited hardware leaves BEFORE correction. Exporting the existing
checked helper changes no hardware body or original test/oracle/gate.

[Fresh lifetime002](../results/2026-10-18/rocev2-rnic-segmented-read-lifetime-002.json)
PASSES10 methods/29 four-state cases: all19 READ and all10 original WRITE/SEND.
Positive READs65/4097/8193/1MiB use one byte-exact actual framed READ request
and1/2/3/256 MODELED response events, each with one whole CQ commit. The actual
retained replay/lifetime/MAC composition runs; full748 identity, final ACK and
first->next PSN wrap are checked. Withholding LAST, HLS ACK, aggregate memory
or producer receipt prevents CQ. FIRST/MIDDLE leave cache unacknowledged even
with memory/final ACK models supplied early. Wrong response PSN/class/syndrome,
foreign/unknown owner and wrong full producer first/next/opcode/unknown fields
quarantine the owner. Legacy first-PSN ACK cannot stand in for final READ ACK.
READ runtimes0.041..0.123s; largest original1MiB WRITE28.919s. Every original
30s runtime bound remains. RX events/HLS/memory/CQ/MAC completion pins are
MODELS:1MiB READ here is metadata/lifetime coverage, NOT1MiB protected RX
payload, generated-HLS, native MR/PTE/DMA/host visibility or physical runtime.

New `tests/segmented_read_lifetime_native_sources.py` requires the exact new
29 cases plus ALL60 original protected RX cases and all parent native/HLS/
MSN/memory gates. Only six native leaves change: lifetime, TX lifetime, MAC
owner admission, shared HLS receipt join, protected RX and root wiring. SQ
admission/HLS-SQ/CQ capability limits intentionally stay unchanged, so a large
READ is still rejected upstream rather than falsely advertised as working.

[Complete native elaboration001](../results/2026-10-18/rocev2-rnic-segmented-read-lifetime-native-elaboration-001.json)
PASSES3.508s/1409 bindings: one new protected RX replacing old guard, exactly
one actual generated READ HLS/shared PSN/MSN/RX/Atomic domain, one common MR/
PTE/physical nonce/backend, no width mismatch/stub and both global drains0.
[Audit002](../results/2026-10-18/rocev2-rnic-segmented-read-lifetime-diagnostics-002.json)
reverifies222 failed/462 fresh unit/1409 native bindings, with only the exact
old generator preimage used for historical source identity. All116 unit leaf
copies (29x4) and ALL60 tested protected RX guard bodies equal the selected
native bytes; all20 uncompiled001 hardware leaves are also unchanged. Failed
reports are not relabeled as current-source passes.

This is component RUNTIME plus complete-native COMPILE evidence. It does NOT
prove a genuinely admitted large READ executes through native SQ/MR/RX/HLS/
DMA/status/visibility/CQ. Next is a distinct matched capability/admission
profile and that runtime, retaining all original regressions; simply opening
length limits or reusing an old native executable is not proof. READ remains
4096, RNC8191/CQC31/kernel/provider/default/Atomic_NONE unchanged. Mid-response
READ retry, Linux/provider/API/physical and all11 original scope remain open.
Original HLS13.885ns still fails4ns/default1.08ns; no board fit/CDC/routing/DRC/
timing/drain gate waived. No hardware, module, network, fan, BIOS, program,
flash, reboot or automatic Git changes.

## Genuine SQC multi-QP expected remote MSN and complete wiring (132, historical)

The predictor's source is genuine accepted outgoing QP configuration,
including TX-only, plus actual SQC cookie/epoch/PD. It is NOT received AETH,
local incoming MSN, packet count or posted sequence number. A newly verified
SQC epoch initializes the fresh-peer history; repeated route/epoch does not.
Every authorized full748-bit logical owner increments its QP once, including
READ/WRITE/SEND/Immediate/Atomic; packet expectations/replays do not recount.
One global active full owner remains held until identical actual CQ retirement,
with separate configuration and per-QP queue guards. This is serialized WR
processing across up to8 route/history slots, not8 concurrent active WRs.
Fresh remote RC QPs are required; existing-peer takeover is unsupported.

[003 diagnostic](../results/2026-10-18/rocev2-rnic-expected-remote-msn-diagnostics-003.json)
verifies80 bindings before fixture correction. The fixture now selects the
required `IMMEDIATE_ENABLE(1)` SQC and actual matching128-byte fetch. No DMA
producer is published, unused old64-byte backend removed, unexpected DMA is
fatal; the production mandatory-profile assertion is not weakened.
[004](../results/2026-10-18/rocev2-rnic-expected-remote-msn-004.json)
then fails the immediate post-capture assertion. Its
[unchanged-RTL diagnostic](../results/2026-10-18/rocev2-rnic-expected-remote-msn-diagnostics-004.json)
verifies86 bindings/preimages and preserves an exact original fixture copy
with only displays/#1 added BEFORE the unchanged strict assertion. MSN1,
busy1, fault0 are stable; guardff becomes80 after combinational delta settling.
The original foreign-expectation quarantine passes. This corrects fixture
sampling, not a production RTL gate or weaker predicate.

[005](../results/2026-10-18/rocev2-rnic-expected-remote-msn-005.json)
PASSES6 methods/11 cases. [Audit005](../results/2026-10-18/rocev2-rnic-expected-remote-msn-diagnostics-005.json)
verifies116 unit and1404 first-native bindings and saves exact preimages before
adding two-QP coverage. [006](../results/2026-10-18/rocev2-rnic-expected-remote-msn-006.json)
FAILS the new two-QP case while retaining all11 passes: genuine QP7 and QP6
allocate/configure and issue their first messages, but QP7 cannot issue again
without reapplying its route because old lookup selects only the latest QP6.
[Audit006](../results/2026-10-18/rocev2-rnic-expected-remote-msn-diagnostics-006.json)
verifies122 bindings and preserves exact preimages BEFORE RTL correction.

The predictor now retains each accepted route independently and queries actual
SQC using the offered/held full-owner QPN. Counters/epoch/sequence stay per QP;
new-QP setup cannot erase another QP's route/history. Changed route during a
held WR, stale/unknown owner, foreign expectation/CQ or parent fault quarantine
without release. [Fresh007](../results/2026-10-18/rocev2-rnic-expected-remote-msn-007.json)
PASSES7 methods/12 four-state cases. Two genuinely allocated/configured QPs
interleave READ/WRITE/SEND without route reconfiguration and independently
advance MSN1->2. All prior logical operations, retry/packet non-recount,
actual guarded SQC retirement/mailbox lookup continuity and new-epoch reset
remain checked. Runtimes0.0293..0.0389s, original10s bounds. Route configuration
acceptance, WR authorization, TX expectation and CQ endpoints are MODELS in
these unit cases; real SQC allocation/lookup is not forced or reconstructed.

New `tests/expected_remote_msn_native_sources.py` and
`tests/check_expected_remote_msn_native_elaboration.py` keep every parent
HLS/profile/memory gate. Only actual controlled/DualEthernet/native/SQ/RNIC
configuration/query/owner/CQ hookups and the new predictor are substituted.
TX-only setup is observed independently of incoming Atomic binding; actual
configuration ready/child-valid both share the separate guard. Genuine SQC
lookup uses stored full cookie/epoch/PD and has no mailbox-IDLE gap. SQ only
gets the real read port; the RQ instance's unused read port is explicitly
disconnected. No second MR table/physical nonce/transport/MSN state domain.

[Complete native002](../results/2026-10-18/rocev2-rnic-expected-remote-msn-native-elaboration-002.json)
PASSES3.447s/1404 bindings: one predictor, all previous HLS/shared PSN/MSN/RX/
Atomic domains and parent module counts unchanged, no width mismatch/stub,
both global drains0. [Audit007](../results/2026-10-18/rocev2-rnic-expected-remote-msn-diagnostics-007.json)
reverifies116 historical005/122 failed006/122 fresh007/1404 first-native/
1404 fresh-native bindings. Historical changed source hashes resolve ONLY to
saved exact preimages, never a relabeled current-source execution.

This is component RUNTIME plus complete-native COMPILE evidence. The actual
expected-MSN output is NOT yet connected to protected segmented RX; genuine
full-native runtime, READ final-response/whole-WR lifecycle/CQ/mid-response
recovery and Linux/provider/API/physical qualification remain. The current
CQ publisher admits positive lifetime tickets only; future error-CQ/recovery
must not reuse advanced MSN after uncertain/no-wire work as normal success.
READ admission4096, RNC8191/CQC31/kernel/provider/default and Atomic_NONE stay
unchanged. Original HLS13.885ns still fails4ns/default1.08ns; fit/CDC/routing/
DRC/timing/drain gates are not waived. All11 scope retained. No hardware,
module/install/load/network/fan/BIOS/program/flash/reboot/automatic Git writes.

## Publication checkpoint131: expected remote MSN was unvalidated WIP (historical)

`rtl/rocev2_expected_remote_msn.v`,
`fpga/derive_expected_remote_msn_native.py` and
`tests/test_expected_remote_msn_rtl.py` are included at the user's explicit
progress-publication request, not as a qualified feature. The intended
source is genuine accepted outgoing-QP configuration (including TX-only)
plus a dedicated read-only SQC cookie/epoch/PD lookup, not received AETH,
local incoming-request MSN, per-packet counts or posted sequence numbers.
It assumes a freshly established remote RC QP, not takeover of an existing
peer QP. Genuine WR/TX/CQ joins and separate configuration/queue guards are
authored in the derivation but have not passed complete-native checks.

[Attempt001](../results/2026-10-18/rocev2-rnic-expected-remote-msn-001.json)
failed before compilation because the fault-code anchor had changed to the
zero-service prefix. [Attempt002](../results/2026-10-18/rocev2-rnic-expected-remote-msn-002.json)
also failed before compilation: a single-pin expectation anchor matched both
the new observer and the old RX guard. Exact preimages and separate
[diagnostic001](../results/2026-10-18/rocev2-rnic-expected-remote-msn-diagnostics-001.json)/
[diagnostic002](../results/2026-10-18/rocev2-rnic-expected-remote-msn-diagnostics-002.json)
remain; checked uniqueness was retained by using the adjacent valid/ready pair.

[Attempt003](../results/2026-10-18/rocev2-rnic-expected-remote-msn-003.json)
reaches compilation for six cases, but ALL terminate at simulation time zero
on `matched128-byte Immediate-header profile required`. The reused fixture
does not select the derived SQC's required profile. This is a fixture-startup
failure, NOT a runtime MSN/lease/epoch pass or evidence against the FPGA's
capacity. All50 current source bindings were reverified before publication.
No tests or source gates were relaxed and no failed report was rewritten.
No new native elaboration/runtime/physical/timing claim accompanies this WIP.

The passing130 READ memory cohort below is unchanged. Protected segmented RX,
trusted expected-MSN qualification, final-response/whole-WR lifetime joins
and mid-READ recovery remain incomplete; READ admission remains4096. Default
kernel/provider/Atomic capability, original timing/drain gates and hardware
remain unchanged. This explicit push does not authorize future automatic
publication. No device, module, network, fan, BIOS, flash or reboot changes.

## Actual native READ memory routing; admission remains closed (130)

NEW `fpga/derive_segmented_read_memory_native.py` keeps the full passing8191
parent and adds a separately named executor selector/external-unpad route.
A stable large-READ role selects the new retained controller and its actual
bounded unpad/executor, without double-unpadding through the old external
stage. Ordinary source, Atomic, zero and small READ still use the unchanged
source/legacy executor; small READ still uses its original external unpad.
Full response-token fanout remains an atomic two-consumer handshake. Actual
memory command/data/status ports connect to the parent's SAME common physical
nonce/MR/PTE/backend path; no new memory authority/table or fabricated receipt.
Whole READ role/guards persist until identical genuine CQ readiness/commit.
The original full-owner CQ offer join remains, including refusal of foreign,
unknown or non-atomic retire offers. Faults force the extra READY known-zero.

[Mux001](../results/2026-10-18/rocev2-rnic-segmented-read-memory-mux-001.json)
FAILED before new READ runtime because fixture alias pins lacked explicit
wire/reg widths; all11 old cases passed. All269 bindings were verified and
exact test/generator preimages saved BEFORE fixing only fixture declarations.
[Mux002](../results/2026-10-18/rocev2-rnic-segmented-read-memory-mux-002.json)
FAILED the short-READ fixture: its reused standalone assertion incorrectly
required the retained READ-specific CQ barrier on a legacy path whose outer
TX/lifetime actually owns CQ. The genuine no-memory-event-before-status check
remains; only that extra-ready assertion is conditional on the retained role.

[Diagnostic002](../results/2026-10-18/rocev2-rnic-segmented-read-memory-diagnostics-002.json)
also executes the UNCHANGED unknown-route case: real fault/quarantine assert,
but READY is X. Its earlier `if(signal)` predicate did not reject X, so this
was NOT proof of known-zero READY. All299 bindings and exact preimages were
preserved before adding the real fault/foreign-offer READY gate and strict
four-state assertions. No failed report was relabeled or original legacy
CQ responsibility changed. [Initial diagnostic001](../results/2026-10-18/rocev2-rnic-segmented-read-memory-diagnostics-001.json)
records the earlier fixture-declaration error separately.

[Fresh Mux003](../results/2026-10-18/rocev2-rnic-segmented-read-memory-mux-003.json)
PASSES ALL9 methods/17 four-state cases, retaining all11 prior same-instance
legacy/source/replay/Atomic/zero cases. New large READ uses real unpad bypass,
internal bounded children and the actual common physical nonce: A001/A002
logical child tags become genuine1/2 backend identities, one aggregate event
and exact CQ retirement; external unpad never captures that READ twice.
Small READ still captures the original unpad once. Wrong direction/foreign
or non-atomic CQ and unknown route refuse DMA/release. Each case retains
its original10s runtime limit.299 bindings reverified.

[Complete native elaboration001](../results/2026-10-18/rocev2-rnic-segmented-read-memory-native-elaboration-001.json)
PASSES3.459s with1400 source/artifact/RAM bindings verified. The real hierarchy
selects exact generated READ HLS instead of the old request core, while all
parent source/profile/HLS gates remain mandatory. Counts prove one new READ
selector/controller/unpad route, unchanged source/legacy path, two bounded
executor instances and one actual MR table/page table/physical nonce/backend.
Each actual native HLS state-table/MSN/RX/Atomic-commit domain occurs once;
all checked ports/748-owner/408-SQ/816-receipt and original clocks/capacity
match. Both global HLS drain certificates stay0. No HLS stub is selected.
[Audit003](../results/2026-10-18/rocev2-rnic-segmented-read-memory-diagnostics-003.json)
reverifies269/299 failed,299 fresh mux and1400 full-graph bindings, using only
exact historical authoring preimages where needed.

This is component RUNTIME plus full-native COMPILE evidence, NOT full-native
large READ runtime or Linux/API/physical qualification. Large READ admission
intentionally remains4096: protected segmented RX, trusted expected REMOTE
MSN and final-response/whole-WR PSN/lifetime/CQ joins are not yet selected.
RNC8191/CQC31 and kernel/provider/default capabilities are unchanged. The
new memory role must become reachable through the genuine checked SQ/MR/RX
pipeline before runtime support can be claimed; source wiring alone is not
that proof. No register poke, modeled MR success or relaxed validator is used
to open it. Native tests must eventually exercise the newly admitted path.

For the next MSN integration, Linux6.17 RXE initializes/resets responder MSN
to0. Its responder advances MSN before READ replies, advances Atomic only
outside replay, advances SEND/WRITE on message end, and writes responder MSN
into AETH. This motivates a trusted per-QP/epoch logical-message predictor,
NOT the local incoming-request counter, per-packet count or RX-learned value.
That predictor and its genuine accepted-QP initialization are still unproved
here; no constant-MSN success path is installed. [RXE responder](https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/infiniband/sw/rxe/rxe_resp.c),
[QP initialization/reset](https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/infiniband/sw/rxe/rxe_qp.c).

All11 original requirements and large RX/Immediate/multi-SGE/recovery remain.
HLS13.885ns still fails original4ns/default1.08ns; full-board fit/CDC/routing/
DRC/timing/drain gates are unchanged. No hardware/default/install/load/network/
fan/BIOS/program/flash/reboot/automatic Git changes accompany this wiring.

## Retained READ fragment memory controller and actual C++ snapshot integration (129, historical)

NEW `rtl/rocev2_segmented_read_executor.v` and checked child-source helper
`fpga/derive_segmented_read_executor.py` add real large-READ memory staging,
not a length-limit-only change. The outer controller keeps the full748-bit
authorized WR and one identical protected placement token. Each bounded
context derives full64 VA/relative offset, key and length ONLY from that
saved owner. Original post-origin-router96-bit commands must match every
field, including exact padded count/address and per-fragment whole-WR ctl.
Only AFTER this check is ctl normalized to1 for a complete bounded child.

The unchanged private <=4096 executor and unpad are reused; only the unpad
module name changes. Actual unpad removes0..3 wire bytes before actual child
placement, never copies them beyond the authorized MR subrange. A001..Afff
logical child tags never wrap. Physical identity MUST still use the shared
nonreusing command-nonce domain (or an explicitly reserved namespace); this
standalone component does not implement or replace that native translator.
Queued next-packet commands/data wait for the previous actual child status,
without confusing them with extra bytes of the completed unpad transaction.
An early correct status cannot bypass data transfer. One aggregate memory
event follows ALL fragments; its consumption does not free the outer lease.
Only identical genuine whole-WR CQ retirement can do so. Backend error,
unknown metadata, stale tags, lost downstream lease or foreign retirement
quarantine the owner/all queue guards. Already-offered command/data/event
remain stable under stalls and late faults. Reset is NOT cancellation/unpin.

[Executor001](../results/2026-10-18/rocev2-rnic-segmented-read-executor-001.json)
initially PASSES12 methods/33 four-state cases. No RTL correction was needed.
[Executor002](../results/2026-10-18/rocev2-rnic-segmented-read-executor-002.json)
retains ALL33 and adds two actual lifetime controls: pending early correct
status waits for genuine data, and a late parent fault retains the pending
whole event without permitting CQ release. All14 methods/35 cases PASS,
each<30s. Full1MiB is four-state here:256 fragments,1048576 exact destination
bytes, one memory event/CQ release, runtime15.942s. This is a MEMORY COMPONENT
test, not a four-state full1MiB RX/HLS/native graph claim. Tails4097..12289,
all pad counts, command/data stalls, withheld statuses, stale/unknown status,
bad placement/command/keep/TLAST/owner, overflow, tag exhaustion, backend
errors and lost/unknown lease are also covered.319 bindings reverified.

[C++-snapshot integration001](../results/2026-10-18/rocev2-rnic-segmented-read-dma-hls-001.json)
freezes the passing source003 fixture and adds ONLY command/owner tracing
to its copy; original assertions and HLS body remain byte-identical. Actual
memCmd fields (including origin2) and actual padded destination bytes from
four READs4097/8193/65537/1MiB are recorded, not reconstructed as success
inputs from the WR. Independent request/PSN/every-byte oracles still run.
Compile60.067s/C++ execution4.830s PASS. The frozen unmodified snapshots then
drive real four-state `rocev2_memory_origin_router`, new READ controller,
unchanged bounded unpad and executor. The real router validates origin and
ordered byte credits, removes ONLY origin bits and preserves the lower94.
The controller then validates all96 post-router bits, not an assumed origin.
Runtime12.775s PASS:4 exact full owners,278 actual commands,1126403 placed
payload bytes,9 pad bytes removed and4 whole-owner memory/CQ releases.
Child tags remain nonreusing across all four WRs in the SAME controller.
Two explicit corrupt-copy controls (origin0, wrong routed address) PASS
<0.134s with no DMA/event. The actual snapshot files remain unchanged.

This is SEPARATE actual C++ and RTL executions, NOT cycle-coupled HLS, actual
generated-HLS RTL runtime, protected RX/native MR/PTE/DMA/physical nonce/
visibility/fence/CQ/Linux/provider or physical qualification. Placement,
backend statuses/visibility/fences and CQ are MODELS; neither a modeled
status nor component memory event proves physical host visibility/unpin.

[Audit001](../results/2026-10-18/rocev2-rnic-segmented-read-dma-diagnostics-001.json)
verified first307 unit/338 snapshot bindings BEFORE adding the two new unit
methods and preserved the exact old fixture. [Audit002](../results/2026-10-18/rocev2-rnic-segmented-read-dma-diagnostics-002.json)
reverifies307/338/319 bindings, resolving historical fixture hashes only to
that exact preimage. Every snapshot file regenerates byte-identically from
the genuine C++ log, tracing is the only fixture change, and actual bounded
children match between both unit batches and snapshot test. No historical
report is relabeled as execution of the expanded current fixture.

Next is actual native executor/unpad routing and whole-WR lifetime integration
with the common MR/PTE/nonce/backend/CQ, strict protected segmented RX and
trusted expected REMOTE MSN source; simply widening the old executor/unpad
is not sufficient. Mid-READ retry, Linux/provider/API/physical integration,
large receive/Immediate/multi-SGE/recovery and original board timing remain
open. Default READ stays4096 and Atomic_NONE remains. New HLS13.885ns fails
original4ns/default1.08ns; no fit/CDC/routing/DRC/timing/drain gate is waived.
All11 requirements remain; no hardware/default/install/load/network/fan/BIOS/
program/flash/reboot/automatic Git writes accompany this component advance.

## True segmented READ HLS C++, compatibility and generation PASS (128, historical)

[Unchanged-timer diagnostic001](../results/2026-10-18/rocev2-rnic-segmented-read-hls-diagnostics-001.json)
executes the failed cohort's real timer: an owned nonterminal update faults,
while a terminal update passes. Failed001's302 bindings and all three authoring
preimages were verified before correction. The new private source adds a
trusted response opcode/progress bit AFTER issued READ-plan/common-PSN/class
validation. The actual timer only accepts nonterminal READ_FIRST progress or
terminal ACK/Atomic_ACK/READ_ONLY/READ_LAST with the opposite stop semantics.
The whole-WR join separately checks the FIRST and final receipt classes,
token and exact PSN. No arbitrary `stop=false` update becomes a release.

[Corrected C++002](../results/2026-10-18/rocev2-rnic-segmented-read-hls-002.json)
PASSES all11 modes after compile60.489s; READ4.816s, prior7.949s, negatives
<0.071s. A fresh source003 adds only provenance/feature manifest fields,
with all derived hardware bytes IDENTICAL to002. [C++003](../results/2026-10-18/rocev2-rnic-segmented-read-hls-003.json)
also PASSES all11 modes after compile60.752s; READ4.801s, prior8.028s,
negatives<0.072s. Each mode retains its original30s runtime limit.

The new positive workload executes four whole READs4097/8193/65537/1048576
bytes,278 FIRST/MIDDLE/LAST response packets, four actual stored request
replays before FIRST, and one genuine final748-bit-owner/816-bit receipt per
WR. Independent wire/RETH/PSN and every destination-byte/pad/order oracle
passes. Actual payload, pointer/pool release, timers and common-state queries
must all complete; withholding payload/timers/final state blocks completion.
All old Atomic/zero/RQ/service/WRITE/SEND cases and291 independent wire/replay
oracles remain. Four original negative controls cover bad first PSN/class/
length/keep; five new controls cover missing progress class, false terminal
stop, wrong progress opcode/token and a corrupt copy of the actual timer
receipt. Each retains the request without whole-WR success.

[Compatibility001](../results/2026-10-18/rocev2-rnic-segmented-read-compat-001.json)
PASSES after compile25.488s/runtime0.964s with the unchanged30s runner/oracles:
real owned Atomic/MR/paged-memory RTL supplies nine replies/receipts and11
wire packets; Immediate TX/RX each has eight cases/receipts. Only the fixture's
internal RX descriptor type/continuation ports adapt to the actual new core.
Peer, connection, normal payload/host boundaries remain MODELS, not native DMA.

[Binding/provenance audit002](../results/2026-10-18/rocev2-rnic-segmented-read-hls-diagnostics-002.json)
reverifies all302 failed001,311 corrected002,311 fresh003 and310 compatibility
bindings. Historical generator/probe/test hashes resolve ONLY to their exact
saved preimages; reports are not rewritten or labeled as current-source runs.

`build_native_segmented_read.py` synthesizes exact003 while
retaining the unchanged parent builder's1500MiB guard,4ns/default1.08ns,
8QP/2000 metadata entries, source/frozen-input/compatibility/port-width gates.
The wrapper's report view only flattens actual prior summaries/hashes verbatim
and separately requires every new READ mode/oracle.
[Generated HLS001](../results/2026-10-18/rocev2-rnic-segmented-read-generated-hls-001.json)
PASSES365.892s, with259 frozen inputs/171 generated files and all15 checked
port widths exact. Resources are81862LUT/98926FF/209BRAM18K/0DSP; this is not
a placed/routed fit report. Estimate13.885ns FAILS original4ns/default1.08ns.
[Exact generated-RTL elaboration001](../results/2026-10-18/rocev2-rnic-segmented-read-hls-elaboration-001.json)
PASSES1.732s with all703 input/source/frozen/generated/report bindings plus
the compile log/RAM model (705 total) verified. It is compile-only, NOT actual
generated-RTL runtime/native/physical or board-timing qualification.
Two inactive object caches were losslessly moved
to RAM with persistent compressed backups and every original/archive/RAM
file hash matched; both must be restored before any reboot. No reboot needed.

Default READ remains4096. Trusted expected REMOTE MSN wiring, mid-response
retry recovery, native per-fragment unpadding/fresh command nonce/status/
visibility aggregation, whole-WR CQ, actual Linux/provider and physical proof
remain incomplete. The inspected native executor/unpad currently accept only
one bounded response token/command: they cannot be made large-READ-safe merely
by raising a length limit. A new retained-owner fragment controller and actual
native integration are next. All11 original requirements remain; no hardware,
default, module, network, fan, BIOS, flash, reboot or automatic Git writes.

## Publication checkpoint: segmented READ HLS candidate was NOT passing (historical)

NEW `hls/segmented_read_transport.py`, `hls/test_segmented_read.cpp` and
`tests/probe_segmented_read_hls.py` add a separate, unselected true READ
transport candidate. One READ request carries the complete length; its
FIRST/MIDDLE/LAST response plan retains the whole request owner. The new
source includes actual receive payload extent checks, incremental destination
commands, same-entry retransmission progress and a whole-request retirement
join. These are development source changes, NOT qualified large-READ support.

[HLS001](../results/2026-10-18/rocev2-rnic-segmented-read-hls-001.json)
is FAILED: actual C++ compile/link57.298s and prior regressions7.9998s PASS,
including old Atomic/zero/RQ/service/segmented WRITE/SEND and291 independent
wire/replay oracles. In the copied fixture only, the intended new READ maximum
changes the over-limit test from4097 to1048577; the original tests are untouched.
The new4097-byte READ emits one complete request and its stored replay, accepts
FIRST at PSN0xfffffe, advances actual retransmission metadata and copies the
first4096 destination bytes correctly. Runtime then aborts in the real
endpoint's combined fault assertion when timers resume, before LAST. The
four new negative modes did NOT run. All302 bound source/artifact/RAM hashes
were reverified; failed source, binary, logs and pre-fix authoring inputs
remain unchanged locally. No failed batch is presented as passing.

The unchanged external replay timer rejects request-owned updates with
`stop=false`, whereas a nonterminal READ FIRST produces such an update.
This is a concrete candidate cause, not a completed runtime diagnosis/fix.
No timer guard was removed to obtain a pass. HLS synthesis, trusted REMOTE
MSN source/wiring, mid-READ retry recovery, native unpadding/nonce/status/
memory visibility/whole-WR CQ and Linux/provider/physical integration remain
unqualified. The default READ limit remains4096, `IB_ATOMIC_NONE` stays set,
and no hardware, module, network, fan, BIOS or reboot change accompanies
this explicitly requested source publication. Future automatic Git writes
are not authorized by this checkpoint.

## New protected segmented READ-response RX candidate (127; completed at publication)

NEW `fpga/derive_segmented_read_response.py` creates a separately named
`rocev2_segmented_read_response_guard`, leaving the passing8191 graph/defaults
untouched. READ up to1MiB uses FIRST/MIDDLE/LAST with exact PMTU, remaining
length, pad count, per-packet complete ICRC/peer/IP/QPN/PSN/class/positive-AETH
checks and a captured trusted expected REMOTE response MSN. One full748-bit
owner and first placement token remain across all fragments. Offset/bytes/last
and AETH-presence metadata accompany each packet event; MIDDLE payload is not
interpreted as AETH. Rejected/CRC-bad packets do not advance offset/PSN or
issue another token. Lost downstream placement lease quarantines the owner.
Existing ordinary/Atomic/zero behavior is retained under the new leaf name.

Packet events are NOT whole-WR CQ/DMA-visibility certificates. The downstream
owner must survive the final replay/event until actual memory/HLS/CQ joins.
This candidate is NOT selected in native RTL, HLS, Linux or the provider;
the incremental RNIC READ limit remains4096. Large READ still needs actual
memory-command/status/nonce aggregation, HLS request/response/retransmission/
common-PSN retirement, trusted MSN wiring, CQ/kernel/API/native/physical proof.

Protocol rationale: Linux v6.17 RXE increments responder MSN before READ
replies and populates AETH from that state. This motivates the strict single-
active-WR candidate's captured expected remote MSN, not a general multi-WR
interoperability claim. It MUST NOT be the local inbound MSN counter or a
value learned from arriving packets; actual trusted-common-state integration
is still missing. [Primary Linux source](https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/infiniband/sw/rxe/rxe_resp.c).

[Component001](../results/2026-10-18/rocev2-rnic-segmented-read-response-001.json)
is FAILED, not a passing suite:16of17 methods/59four-state cases PASS, each
<=12.44s, retaining all eight prior Atomic and two zero methods. New READ
4097/4098/4099/4100/8192/8193/12289 cover tails and PSN wrap; wrong first/
middle/last MSN/peer/QPN/PSN/class/length, bad ICRC, lost lease and unknown
trusted MSN fail closed with recovery/retained state. The full1MiB Verilator
case compiled179.48s but the new harness incorrectly classified arithmetic
operand-width warnings as port mismatches and refused to run its binary.
All8518 bindings/612 unique files were verified BEFORE correction; the
failed report/model/binary/log and exact probe/generator preimages remain.

[Diagnostic001](../results/2026-10-18/rocev2-rnic-segmented-read-response-diagnostics-001.json)
separately runs that SAME UNMODIFIED full1MiB TWO-STATE model:1.442s,
256accepted packets/events, one placement token, zero faults/rejects/drops,
321979 cycles, complete independent byte/offset/PSN/stall/lease oracles PASS.
This diagnostic does not relabel failed component001 or prove four-state1MiB,
actual HLS, native DMA/placement, whole-WR CQ, Linux or physical operation.

Fresh component002 keeps ALL17 methods/60 cases, same180s compile/30s runtime
bounds and unchanged DUT/ICRC. Explicit Icarus/Verilator port/pin diagnostics
still fail and have negative self-tests; arithmetic warnings stay in logs.
Its identical256-packet1MiB workload uses a procedural loop rather than a
huge compiler-expanded coroutine, preserving all checks and finite bounds.
[Component002](../results/2026-10-18/rocev2-rnic-segmented-read-response-002.json)
is now terminal PASS, ALL17 methods/60 cases. Its first1MiB case compiles
62.042s and runs1.423s with identical DUT/packet input bytes and321979 cycles:
256 accepted packets/events, one placement token, zero faults/rejects/CRC
drops. All59 other four-state cases PASS, retaining all eight Atomic and two
zero methods. All8500 bindings/594 unique files were reverified. This is
component evidence, not native DMA/HLS/whole-WR CQ or physical qualification.
No installation/load/hardware/network/fan/BIOS/reboot/program/flash changes;
all11 requirements remain.

## Matched native29 and actual kernel/native SQ-CQ integration65 (126, historical)

[Matched8191 native-full001](../results/2026-10-18/rocev2-rnic-segmented-profile-native-full-001.json)
is terminal PASS: compile427.49s, ALL29 cases18.05..26.61s. Both8193-byte
WRITE/SEND plus ALL27 old regressions ran; no case/gate/deadline waiver.
All1443 source/artifact/RAM bindings were reverified. This is the actual
RNC8191/SQC13/RQC15/CQC31 graph, not transferred4095 evidence. Its actual
large source/DMA/HLS/wire/CQ/retirement oracles and all physical-model limits
remain as below. No launcher/compiler/runtime job remains for this batch.

NEW `kernel_segmented_native_cq.c` and checked runner consume the successful
native graph's UNEDITED per-case SQ/CQ files with the actual frozen profile4
kernel cohort. The real standard post_send callback, coherent SQ serialization,
full-key/range/ref handling, actual CQC31/748/0xa0 decoder, full-owner comparison,
CQ polling and MR-reference retirement run. All128 bytes of each C-produced
first posted SQ entry match the native input record AND actual coherent ring.
No positive event/profile field is normalized or fabricated.

[Kernel/native CQ001](../results/2026-10-18/rocev2-rnic-segmented-kernel-native-cq-001.json)
PASSES65 ASan/UBSan cases after real C compile6.59s, each<0.015s;172 bound
hashes reverified plus ALL1443 native bindings before/after consumption.
There are13 genuine positive snapshot pairs: CAS/FADD, ordinary READ/SEND_IMM,
small WRITE/SEND,8193-byte WRITE/SEND and five zero operations. Positive cases
publish the exact standard WC once and release actual saved MR work refs
only after matching CQ consumption. Zero operations never acquire an unused
local MR reference.52 EXPLICIT in-memory negative mutations cover Atomic
operand, reserved extension, whole length and local offset; wrong owners
retain CQ/queue/MR ownership with no ACK/publication/free. Actual native
snapshot files remain byte-identical. Existing four ordinary/Atomic operations
and both original mutation categories remain, not just new large cases.

Linux primitives, pins, coherent-DMA allocation, MMIO, peer and teardown are
still userspace MODELS. Native and C page tables remain separate; this is not
a proof of identical physical mappings, live kernel/RTL coupling, actual
Linux callback execution, standard-provider end-to-end runtime or hardware.
This is stronger byte-level integration evidence, not a replacement for those
requirements. Up to1MiB still has only HLS/component/C/provider-serialization
evidence; full-native large runtime here is8193 bytes.

[Consumer diagnostics001](../results/2026-10-18/rocev2-rnic-segmented-kernel-native-cq-diagnostics-001.json)
preserves a startup generator anchor mistake (two mandatory before/after hash
loops, not one) and a manual syntax-only diagnostic's wrong include origin.
Only the launcher anchor/diagnostic invocation changed; actual C and native
inputs were not changed to obtain PASS. Both full-native hash audits remain.

All11 original requirements remain OPEN except preserved exclusions. Large
RX/READ/Immediate/multi-SGE/recovery, actual Linux/provider/API/native/physical
integration and original full-board timing are unfinished. HLS11.180ns still
fails4ns/default1.08ns; historical scripts/check.sh SHA mismatch remains.
Default sources/Atomic_NONE/install/load/hardware/network/fan/BIOS/reboot/
program/flash/Git publication are unchanged. No automatic push is authorized.

## Matched8191 native large WRITE/SEND pass; regression still live (125, historical)

The SAME native-full001 build finished and has PASSED8193-byte WRITE26.61s
and SEND26.31s. Their immutable case logs and saved CQ events were independently
rechecked against all original complete data/wire/nonce/owner/receipt oracles.
Each has one MR grant,3 real source commands,6 read descriptors/68 read TLPs
(33three-DW/35four-DW),3 full MAC frames/EOF-ordered ACKs, wrapped PSNs,
one actual generated HLS whole-WR receipt and one full748-bit final CQ.
Actual source/HLS/dispatcher owners retire exactly once with no remaining
owners/fault or source/sentinel changes. Both actual CQ snapshots expose31.
Actual native AXI profile capture is8191/13/15/31 (RNC/SQC/RQC/CQC), matching
the new kernel tuple. No observed event/profile field was rewritten.

This is partial live-batch evidence, NOT an all29 pass: the same launcher
continues ALL27 old regressions under unchanged30s bounds. Final report and
whole-batch source/artifact/RAM verification are still pending. Compiler is
terminal; do not mistake its missing PID for a stopped launcher or restart it.
All frozen inputs remain unchanged. Physical host/root/peer/PHY/PTP are models;
ordinary READ/SEND_IMM retain prior MAC-receipt models. This does not execute
standard libibverbs into actual Linux callbacks or qualify a physical image.
All11 requirements, large RX/READ/Immediate/multi-SGE/recovery and original
timing remain open; HLS11.180ns still fails4ns/default1.08ns. No hardware,
installation/load/network/fan/BIOS/reboot/program/flash or automatic Git changes.

## Matched large identity and standard-provider integration (124, historical)

NEW private `provider/derive_segmented_provider.py` accepts exact8191 firmware
identity alongside511/1023/2047/4095. All operations still use genuine standard
uverbs serialization; no BAR mapping, exposed DMA address, private user C128
ABI, payload transport copy or completion is added to the provider. Kernel
remains responsible for full RNC/SQC/RQC/CQC tuple/geometry/MR/lifetime checks.

[Provider002](../results/2026-10-18/rocev2-rnic-segmented-provider-002.json)
PASSES all FIVE profiles with actual installed libibverbs/PABI34 and pinned
rdma-core50 headers, ASan/UBSan, each<0.018s. All four old Atomic/access/zero
profiles remain;8191 also runs the full zero and Atomic cases. New standard
WRITE/SEND two-WR chains cover4097/8193/1MiB, full64-bit VAs/remote addresses/
keys/lengths, exact second bad-WR pointer, standard zero-byte send WCs and
a distinct1MiB MR handle/key, registration and deregistration. Each profile
also refuses wrong firmware identity before objects. Actual C serializer and
public API run; fake-fd syscall and WC replies are MODELS, not actual Linux
callbacks, DMA or physical completions.28 source/upstream/library/artifact
bindings reverified; original provider/default kernel/Atomic_NONE unchanged.

[Four-state identity/CQ RTL001](../results/2026-10-18/rocev2-rnic-segmented-profile-rtl-001.json)
PASSES27 cases/290 bound hashes. Actual AXI reads expose RNC8191 and CQC31,
full748-bit owner and0xa0 operand aperture; all six original controller mailbox
scenarios and four original CQ owners remain. Four large WRITE/SEND owners
(8193/1MiB) commit/retire/publish/ACK with immutable full-context backpressure.
Eight incomplete prerequisite combinations trigger the actual dependency
fatal; disabling Immediate exposes a nonmatching value, not8191. Eleven
invalid Atomic/extension/large-op/length owners cannot obtain CQ authority.
Controller and upstream CQ ticket/commit/retire producers are MODELS.
Only two identity leaves differ from the prior padding graph; no data gate
or default selection changes. The new tuple agrees with actual kernel headers.

NEW `segmented_profile_native_sources.py` gates that component proof and all
parent HLS/owner proofs before selecting exactly those two changes.
[Whole graph elaboration002](../results/2026-10-18/rocev2-rnic-segmented-profile-native-elaboration-002.json)
PASSES3.17s/1220 hashes/no width warnings with unchanged module counts, one
padding instance and both global drains0. COMPILE ONLY. NEW exact-profile
fixture changes ONLY expected identity fields, never observed snapshots;
all independent wire/data/CQ/owner/receipt/nonce/tail oracles and29 cases remain.
Fresh matched8191/31 native-full001 is COMPILING under the same1200s build/
30s per-case bounds. No matched8191 native runtime pass is claimed yet.

[Diagnostics001](../results/2026-10-18/rocev2-rnic-segmented-profile-diagnostics-001.json)
preserves two launcher startup mistakes (syntax, nonexistent virtual input),
wrong-HLS-report elaboration001 (guard correctly refused), and provider001's
successful runtime before adding a missing parent-template provenance binding.
All five actual provider C/header bodies are identical001/002. No failed report
was relabeled, DUT changed to hide a fixture error, or test/guard waived.

All11 original requirements remain. This is not actual Linux/provider/native
end-to-end execution or physical/timing qualification. Up to1MiB remains
HLS/component/C/provider-serialization evidence, not full-native runtime;
large RX/READ/Immediate/multi-SGE/recovery remain open. HLS11.180ns still fails
original4ns/default1.08ns. No installation/load/hardware/network/fan/BIOS/
reboot/program/flash or automatic commit/push. Exact authenticated same-thread/
active-goal restore is unproven, and no reboot is needed.

## Publication checkpoint: large native29 and private kernel65 (2026-10-21, historical)

[Padding-native-full001](../results/2026-10-18/rocev2-rnic-segmented-padding-native-full-001.json)
is terminal PASS: compilation431.52s, ALL29 runtimes18.15..27.12s. Both8193-byte
ordinary WRITE/SEND and ALL27 old cases ran; no case/deadline/oracle was waived.
All1438 source/artifact/RAM records were reverified. Each large case has one
whole8721-byte registered range at offset528, three real source commands,
six read descriptors,68 actual PCIe requests (33three-DW/35four-DW), three
complete independently checked wire frames and one final full748-bit CQ.
Actual generated HLS/MR/PTE/DMA/shared-nonce/board-TX-FIFO/CDC/XGMII/FCS/SFD/
MAC/owner retirement paths execute. Three ACKs follow actual wire EOFs;
PSNs wrap fffffe/ffffff/0. Final genuine MAC receipt is withheld beyond the
original1024-cycle tail. Source/HLS/dispatcher retire exactly once with no
remaining owners/fault and no host source/sentinel changes.

This is TWO-STATE simulation with modeled physical host/root/peer/PHY/PTP,
not actual Linux/physical/timing qualification. Ordinary READ/SEND_IMM retain
their previous MAC-receipt models. Runtime identity is still RNC4095/CQC15
with the explicitly private large simulator codec; it does NOT qualify the
new8191 Linux cohort. Up to1MiB remains separate HLS/component evidence.
Earlier native001/002/003 failures remain unchanged, with their diagnoses.

NEW `kernel/derive_segmented_kernel.py` and `build_segmented.py` freeze a
private matched RNC8191/CQC31/profile4 cohort, still128-byte SQ/RQ/full748-bit
owners. Only ordinary WRITE/SEND gain up to1MiB. Exact identity and geometry
must be reread before queue binding; mixed old/new tuples fail closed.
Actual standard post_send/MR/PD/full-range/full-key/ref/coherent-ring/producer/
CQ/full-owner/backpressure/quarantine code remains, selecting the typed large
adapter only in profile4. READ/RQ/Immediate remain<=4096, old profiles retain
their limits and `IB_ATOMIC_NONE` remains unchanged. No default file is replaced.

[Actual running-header kernel build001](../results/2026-10-18/rocev2-rnic-segmented-kernel-001.json)
PASSES9.59s, GCC13/W=1, both modules link with matching6.17.0-1033-oem vermagic
and required real symbols;122 source/frozen/artifact hashes reverified.
[Actual C post003](../results/2026-10-18/rocev2-rnic-segmented-kernel-post-003.json)
PASSES all65 ASan/UBSan cases, each<0.016s,143 hashes reverified:18 new large
and ALL47 old cases. New coverage includes8193/1MiB WRITE/SEND, ASan base-only
SEND, wrong range/key/old profile/large READ refusal, mixed identity/four
geometry failures, corrupt full CQ owner, CQ backpressure and ambiguous
producer timeout retaining MR/queue refs. Linux primitives/MMIO/pins/DMA/
completion are explicit MODELS, not actual kernel callback execution.
Failed post001 is model compilation (indentation and nonexistent macro);
post002's first15 new cases pass before a fixture improperly tries to return
an errno from void MMIO write. Their frozen inputs/logs/preimages are retained.
Post003 instead withholds real ACK visibility and requires exact timeout/
uncertain/quarantine behavior. Actual derived kernel bodies are unchanged.

NEW `fpga/derive_segmented_profile.py` is an UNQUALIFIED private RTL identity
helper for8191/31. It is not selected in the passing29-case graph, independently
RTL-read-tested, or standard-provider/physical-qualified. No module installation,
load, hardware/network/fan/BIOS/reboot/program/flash operation was performed.
All11 original requirements remain: real Linux/provider/API/physical integration,
large RX/READ/Immediate/multi-SGE/recovery and original full-board timing are
still open. HLS11.180ns still fails original4ns/default1.08ns. `scripts/check.sh`
still stops at the historical TX-padding SHA mismatch; no historical evidence
or strict gate was rewritten to obtain a green release.

## Actual pre-padded LAST integration and fresh all29 native build (122, historical)

[Native003](../results/2026-10-18/rocev2-rnic-segmented-wire-native-full-003.json)
compiled421.59s, then FAILED first large WRITE24.16s; the other28 cases were
NOT RUN. Both first4170-byte and middle4154-byte actual MAC frames match their
complete independent RETH/PSN/payload/ICRC/FCS/SFD/tag/EOF oracles. Three source
commands were accepted and the retained source reached offset8193, but the
last frame was dropped and no HLS whole-WR receipt or CQ committed.

[Frozen-model owner inspection001](../results/2026-10-18/rocev2-rnic-segmented-native-fault-diagnostic-001.json)
and [padding diagnosis001](../results/2026-10-18/rocev2-rnic-segmented-native-padding-diagnostics-001.json)
isolate the ACTUAL cause without DUT rebuild/state writes: core TX bad1,
RX bad0/overflow0 and guard ERR_UNEXPECTED35. The retained actual HLS BTH is
`0870ffff000000c480000000` (WRITE_LAST, pad3, PSN0). The old unpadded-only
normalizer overwrote that pad with0 and marked the second beat bad. Its
rejected FIFO frame retains IP length48/UDP28/payload1/three zero pad bytes,
but BTH `0840...`. Unchanged ICRC correctly discarded the bad-user frame.
Generic HLS ap_sync write strobes are NOT fault-data values; this is not an
HLS receive-fault diagnosis. All1290 failed bindings were reverified and all
original models/logs/binaries/preimages remain. A failed observer of a consumed
width-adapter shifter is preserved separately; it is not byte evidence.

NEW `rtl/rocev2_segmented_tx_padding.v` handles the matched HLS LAST contract
under a NEW module name. LAST opcodes02/08 must already have aligned complete
lengths, nonempty payload and literal-zero declared pad bytes. The adapter
preserves BTH pad count and never adds their padding twice or heals invalid
LAST input. Other ordinary packets retain existing unpadded normalization.
`fpga/derive_segmented_padding.py` selects it ONLY inside the new private
atomic-request/segmented-HLS integrity wrapper. The original/default
`rocev2_tx_padding.v`, old initiator paths, checksum/ICRC, HLS generation,
owner/lifetime/drain/tail/clock gates and capability declarations are unchanged.

[Padding/integrity component002](../results/2026-10-18/rocev2-rnic-segmented-padding-002.json)
PASSES six methods, all51 bound records reverified. ALL three old padding
tests and exact workloads/oracles remain. New LAST WRITE/SEND cover every
pad count and many payload tails; zero SEND44 and ordinary normalization
remain compatible. Nonzero pad bytes, wrong class/length/UDP/masks/user/error
and unpadded LAST are refused, with real FIFO backpressure and recovery.
Five methods use four-state Icarus, each<=17.67s. The unchanged32-frame
capacity workload uses explicit TWO-STATE Verilator0.071s to remain within
the SAME30s runtime bound; its original byte/stall/cycle/rate checks remain.
This is not an all-four-state or hardware/timing claim. Failed component001
timed out that unchanged workload in Icarus and lacked actual backpressure
in a small new negative batch. Only simulation engine/pressure prefix changed;
RTL is identical between failed001/pass002. No assertion/case/deadline waiver.

[Complete new-graph elaboration001](../results/2026-10-18/rocev2-rnic-segmented-padding-native-elaboration-001.json)
PASSES3.20s, all1216 records reverified/no width warnings and exactly one
new padding instance. Among35 private parent RTL files ONLY the integrity
wrapper's module selection changes; one new leaf is added. All previous
MR/PTE/HLS/source/nonce/CQ domains and exact root fanout remain singular.
This is COMPILE-ONLY. Fresh padding-native-full001 is COMPILING the two8193
cases FIRST plus ALL27 prior cases with identical fixtures/oracles and
1200s build/30s per-case bounds; inputs remain frozen while live. No new
native runtime pass yet.

Linux large-profile/geometry negotiation and real SQ/MR/CQ lifetimes still
must be integrated before selecting the private typed large adapter; old
4095 alone is not authority to enable it. All11 requirements, large RX/READ/
Immediate/multi-SGE/Linux/provider/API/physical/recovery/full-board timing
remain open. HLS11.180ns still fails original4ns/default1.08ns. No hardware,
installation/network/fan/BIOS/reboot/flash or automatic Git publication changes.

## Large native first-frame proof, full64 PCIe model and verbs adapter (121, historical)

The [board-faithful native002](../results/2026-10-18/rocev2-rnic-segmented-wire-native-full-002.json)
compiled426.98s, then FAILED its first large WRITE after20.55s. It does NOT
pass29 cases: the other28 were NOT RUN. Its first4170-byte MAC frame now
matches the independent complete FIRST/RETH/payload/ICRC oracle, real FCS,
SFD/tag2001 and actual XGMII TERM; the peer ACK follows that real EOF.
The next actual DMA descriptor reaches sealed third page0000000012345000,
where Corundum correctly emits a3DW MemRd. The inherited root model incorrectly
required every read to be4DW and decoded every address as64-bit-in-header.
[Diagnostics001](../results/2026-10-18/rocev2-rnic-segmented-native-dma3dw-diagnostics-001.json)
preserves the failed1288 bindings/model/binary/log and exact fixture/probe
preimages; all1288 were reverified using those preimages after correction.

NEW `tests/segmented_pcie_request_fixture.py` adds real3DW low-page decoding
ONLY for new large-source reads to the exact sealed third page. All prior
scenarios still require4DW; type/requester/TC/attributes/unused-DW/PH/range
checks remain. No page is substituted and no hardware force-64bit parameter
changes. An additional independent observer joins EVERY enabled TLP byte to
the actual accepted full64-bit physical descriptor in order, requires exact
length before status and rejects high-address truncation/reorder/excess/
missing bytes. Repeated test payload patterns cannot hide a wrong DMA page.
[Four-state PCIe-request001](../results/2026-10-18/rocev2-rnic-segmented-pcie-request-001.json)
PASSES four methods/14 cases in1.64s: actual top64-bit last-byte/low/high
address decoding and all negative header/range controls. These are root-model
component checks, NOT native-DMA/Linux/physical qualification.

Fresh native-full003 has passed complete bench/width elaboration and is
COMPILING the two8193-byte cases FIRST plus ALL27 regressions. All35 private
generated RNIC RTL files remain byte-identical to failed002. The new wire
oracle also requires exactly33 actual3DW and35 actual4DW read requests,
besides all prior host/wire/owner/CQ/tag/nonces/ACK/EOF checks. Same1200s build,
30s per-case limits, original clocks/tails/global drains0. No runtime pass yet.

NEW `kernel/verbs_segmented_wqe.c/.h` adds a PRIVATE correctly typed Linux WR
adapter for ordinary WRITE/SEND up to1MiB. Base SEND is never cast as an
extended RDMA WR. Exactly one SGE, full address/range/key/sequence/epoch and
signaled flag serialization are checked; zero/Atomic/READ/Immediate/small
operations delegate unchanged old adapters. It does not post, read payloads,
pin/register memory, acquire MR/PD/SQ refs or advertise capabilities, and is
NOT selected by the default Makefile/callbacks. Matched large-profile
negotiation and actual full-range posting/lifetime integration remain required.

[Adapter003](../results/2026-10-18/rocev2-rnic-segmented-verbs-adapter-003.json)
PASSES real running-kernel-header module compile/link3.68s, matching vermagic
and actual adapter/codec symbols, plus actual C under explicit Linux WR type
models/ASan/UBSan0.012s:54 positive and14 negative cases. Independent128-byte
oracles cover large lengths/keys/flags, top64-bit ranges, malformed/unsupported
requests, null/zeroed errors, zero/small/Atomic delegation and ASan-guarded
base-only SEND allocation. No module is installed/loaded and no real Linux
callback/SQ/CQ/standard API/native DMA is executed by this test.
[Adapter diagnostics001](../results/2026-10-18/rocev2-rnic-segmented-verbs-adapter-diagnostics-001.json)
preserves two failed user fixtures: recursive errno stubbing, then swapped
expected sequence/epoch offsets. Real header builds passed all three; all8
actual adapter/codec C leaves are identical across failures and successful003.
Read-only O0 debug relink confirms actual sequence at8/epoch at56; no C gate
or negative test was removed.

All11 requirements remain open: large RX/READ/Immediate/multi-SGE, real host/
Linux/provider/API/recovery/physical and full-board timing. HLS11.180ns still
fails original4ns/default1.08ns. No hardware/install/network/fan/BIOS/reboot/
flash, default capability or automatic Git publication changes.

## Board-faithful large-source MAC path and new native build (120, historical)

[Frozen-model diagnostic001](../results/2026-10-18/rocev2-rnic-segmented-native-fifo-diagnostic-001.json)
isolates the previous fatal without rebuilding or changing DUT state. The
actual inherited1KiB whole-frame TX FIFO overflow bit is1; bad-frame,
MAC-underflow, timestamp-overflow and DUT fault are0. There is one full MR
query/grant and source command, one framer frame, no MAC SFD/CQ and no packet
advance. All1276 original bindings were checked BEFORE correction. The
original model/log/binary and both changed Python preimages remain preserved.
This diagnostic is not a successful native run.

NEW `tests/segmented_board_tx_fixture.py` follows the real board parameter
chain and instantiates unchanged Corundum `tx_fifo`:32768-byte synchronous
frame queue,128-bit input/output, RAM pipeline2. It feeds the actual512-byte
128-to64-bit CDC with `mqnic_port_tx`'s cut-through/no-oversize-drop policy,
RAM pipeline0 and the same250MHz/390.625MHz clocks. This is NOT simply an
arbitrary larger FIFO. Real board config/width/port/pipeline propagation and
all new RTL inputs are checked/hash-bound. Old shared fixtures are untouched.
Overflow/bad-frame/underflow assertions remain; synchronous queue errors
and malformed actual XGMII START/TERM now have additional fatal observers.

[Four-state board-TX component001](../results/2026-10-18/rocev2-rnic-segmented-board-tx-001.json)
PASSES four methods in17.21s, each simulation<=5.15s; all39 bound records
reverified. Slow-source4170/4154/62-byte frames, small frames and9214-byte
jumbo retain exact wire bytes/FCS/SFD/tags and withheld genuine completions.
The synchronous queue cannot emit an incomplete frame. Bad frames and
32769-byte oversize frames still fail closed at the REAL FIFO with their
expected separate fatal flags and no MAC SFD. These are component tests,
not native RNIC/Linux/physical qualification.

The new large native fixture additionally waits for actual observed XGMII
TERM before injecting each peer ACK, rather than acknowledging a frame only
accepted by the upstream framer. Full actual wire/FCS and per-ACK EOF oracles
remain independent. All35 private generated RNIC RTL files are byte-identical
to failed001; no transport/range/identity/drain/tail/clock/deadline gate changed.
Fresh native-full002 has passed bench/width elaboration and is COMPILING both
8193-byte cases FIRST plus ALL27 regressions on this same board-faithful path.
No runtime pass yet. Same1200s build/30s per-case limits and global drains0.
Inputs remain frozen while live; no automatic commit/push or hardware changes.

All11 requirements, large RX/READ/Immediate/multi-SGE/Linux/API/physical/
recovery/full-board timing remain open. HLS11.180ns still fails the original
4ns/default1.08ns clocks. Exact authenticated thread/goal restoration is still
unproven; no reboot is required or attempted.

## Publication checkpoint: large-source native failure preserved (2026-10-20, historical)

The [new 29-case native run001](../results/2026-10-18/rocev2-rnic-segmented-wire-native-full-001.json)
has finished, NOT passed. Compilation succeeded in424.65s. The first
8193-byte WRITE stopped after19.60s at `real MAC/FIFO error`, following the
first4170-byte frame's accepted final beat. The other28 cases were NOT RUN;
there is no new-graph large WRITE/SEND runtime or CQ success claim. The
failed report, original log, generated model and frozen binary are retained
locally; all1276 bound source/artifact records were reverified for publication.

The inherited small-packet fixture has a1024-byte whole-frame TX FIFO,
whereas the board uses a32768-byte synchronous TX FIFO followed by a small
cut-through CDC FIFO. This mismatch is under investigation; the exact fatal
flag/root cause has not yet been isolated. The new fixture must model the
actual board path before rerunning, with overflow/underflow assertions,
original clocks,1024-cycle tails, identity checks and deadlines retained.
No FIFO correction or new native runtime has been performed in this snapshot.

The prior27-case pass below belongs to the PRE-large-wire graph, not this
failed candidate. Component004 still passes10 cases including1MiB, and the
private C128 codec passes15 real-C/UBSan methods; neither substitutes for a
complete native large-transfer pass. Linux/API/physical/full-board timing and
all11 original requirements remain open; HLS11.180ns still fails the original
4ns/default1.08ns targets. This is a work-in-progress publication, not a release
or programmed image. No hardware/network/fan/BIOS/installation/reboot changes.

## Actual large-source codec, MR/DMA/peer fixture and29-case build (119, historical)

NEW `kernel/wqe_segmented.c/.h` is an explicitly opt-in private C128 codec,
not an installed post path or device capability. Ordinary WRITE/SEND accepts
up to1MiB after REAL full64-bit last-byte range checks. Existing canonical
sequence/epoch/flags/Immediate/operand/reserved-byte policies remain; other
operations delegate to the unchanged zero/Atomic/4096-byte codecs. Only byte
serialization uses a bounded local surrogate AFTER full-range validation;
no MR/PD/DMA authorization is acquired or bypassed. Error outputs are fully
zeroed and overlapping input/output remains supported.

[Real C/UBSan codec002](../results/2026-10-18/rocev2-rnic-segmented-wqe-002.json)
PASSES all15 methods, including inherited zero/Atomic, independent128-byte
oracles,1MiB boundaries/top64-bit byte/wrap/canonical/padding/alias/null cases.
Old codecs still refuse large WRs and default `IB_ATOMIC_NONE` remains.
[Diagnostics001](../results/2026-10-18/rocev2-rnic-segmented-native-codec-diagnostics-001.json)
preserves failed001: a size-negative RECV/SEND_IMM fixture also had forbidden
remote fields and correctly returnedEINVAL before its expectedEMSGSIZE. Only
the size fixture was canonicalized; no C validation or malformed-field test
was removed. Checked generator/digest/AST development failures are separate
from native runtime evidence.

NEW `tests/segmented_wire_native_fixture.py` adds actual8193-byte WRITE/SEND
while retaining ALL27 previous scenarios. It genuinely registers8721 bytes
from the existing MR base/first offset and seals THREE scattered64-bit DMA
pages, including the page ending at the maximum64-bit address. The complete
8193-byte local MR query/grant must occur once. Retained source commands must
be exactly4096/4096/1 at offsets0210/1210/2210 and logicalC001/C002/C003, with
fresh genuine physical backend nonces/statuses. Actual PCIe page descriptors,
TLP bytes/addresses/tags, untouched source/sentinels/SQ128 ring and no host
writes/fences are checked independently.

The peer model supplies three real CRC-valid ACK frames through actual RX;
the issued PSNs must befffffe/ffffff/000000. Actual HLS packets, per-packet
expectations/cache advances, full816-bit first/next receipt and ONE immutable
748-bit CQ are checked. Final real MAC tag2003 is withheld past1024 cycles;
aggregate memory/producer completion cannot release the full source first.
The exact output wire oracle includes FIRST/MIDDLE/LAST/whole first RETH,
all8193 source bytes, final padding/ICRC and actual XGMII/FCS/SFD/CDC frames.

`probe_segmented_wire_native_full.py` freezes a checked extension of the exact
27-case runner, adding both large cases FIRST:29 cases total, unchanged1200s
build/30s per-case deadlines and all old assertions. Complete bench
elaboration/width checks have passed and native-full001 is now COMPILING;
no new-graph runtime success is claimed. Inputs/probes/fixtures/RTL/HLS remain
frozen while that exact job is live. Physical host/root/peer/PHY/PTP remain
models; no Linux/physical/timing signoff follows a future simulation pass.

All11 requirements, large RX/READ/Immediate/multi-SGE/Linux/provider/API/
recovery/physical and board timing work remain. HLS11.180ns still fails
original4ns/default1.08ns. No hardware/install/network/BIOS/fan/reboot/flash,
default capability or automatic Git publication changes.

## Coordinated large packet ownership and native wiring (118, historical)

NEW `fpga/derive_segmented_wire.py` extends the same private native graph with
ordinary WRITE/SEND admission up to1MiB, true FIRST/MIDDLE/LAST header checks,
whole-message first RETH, bounded per-packet lengths and consecutive24-bit PSNs
including wrap. The full748-bit WR remains unchanged across every packet.
READ/Immediate remain4096 bytes; Atomic/zero/RQ/default sources and the bounded
source-DMA child remain unchanged. No default selection or capability changes.

Each packet joins its exact full-owner RX event, HLS ACK and actual framer/tag/
accepted EOF/own-receipt/1024-tail proof. The replay cache advances through an
explicit persistent full-owner/PSN/index token only after those witnesses and
actual packet MAC/cache drain. It never uses a fake CQ commit or global idle
as packet retirement. Late faults preserve the offered token and whole-owner
quarantine. The next real HLS packet may legally stall while the prior MAC
receipt is held. Final CQ STILL requires whole memory/producer/transport drain,
both observed last-PSN+1 and full first/next-PSN span, and exact whole owner.

Retry-budget reload after a successful packet follows the behavior checked
in the [Linux v6.17 RXE completer](https://github.com/torvalds/linux/blob/v6.17/drivers/infiniband/sw/rxe/rxe_comp.c).
No implementation was copied. Policy is read from the same retained QP table;
this is not recovery/interoperability qualification.

[Four-state component004](../results/2026-10-18/rocev2-rnic-segmented-wire-004.json)
PASSES five methods/10 cases, all240 bound records verified. WRITE4097,
SEND8192, WRITE/SEND8193 and WRITE1048576 execute byte-exact true segmented
Ethernet frames with actual lifetime/cache/framer/tag/EOF/tail RTL. The1MiB
case has256 packets,255 genuine cache advances,256 MAC proofs and ONE final
WR commit in29.17s; every DUT tail remains1024 cycles, including middle
packets. First/last receipts are withheld past the tail; intermediate bulk
receipts still stall. Missing HLS ACK, valid-CRC wrong first RETH/later PSN/
opcode and wrong whole-WR receipt are refused without CQ/owner release.
HLS/IP source, RX/HLS-ACK, memory, CQ and physical MAC receipt pins are MODELS:
this is NOT actual generated-HLS/MR/DMA/XGMII native large runtime or hardware.

[Diagnostics001](../results/2026-10-18/rocev2-rnic-segmented-wire-diagnostics-001.json)
preserves both failed initial fixtures, compiled models/logs and source
preimages. A just-deasserted physical receipt VALID was sampled before its
combinational delta settled: cycle2152 was below limit3352, actual receipt1
was present and tail1024 had just started. A#1 fixture settle, consistent with
existing MAC tests, fixes observation only; all four DUT leaves are byte-exact
between failed002 and pass003. No assertion/tail/drain/clock/deadline waiver.

The coordinated source/HLS-SQ/shared-HLS/lifetime/MAC/RX/CQ range gates and
full-WR receipt checks are now wired in ONE actual graph.
[Whole-native elaboration001](../results/2026-10-18/rocev2-rnic-segmented-wire-native-elaboration-001.json)
PASSES3.23s, all1211 source/artifact records verified, no port-width warnings,
same module/domain multiplicities and byte-identical qualified root source/
CQ fanout. This is COMPILE-ONLY; the prior27-case runtime pass below is the
PRE-large-wire graph. Actual new-graph large WRITE/SEND and all27 regressions
still need runtime verification with genuine full-range MR/descriptor/DMA,
real HLS packets/ACK/PSN readbacks and exact source/per-packet/final CQ oracles.
The current standard/kernel codec still refuses>4096; a matched private test
codec/profile is required, not an unchecked descriptor shortcut.

Large RX/READ/Immediate, multi-SGE, Linux/provider/API, physical/recovery and
full-board timing remain open; all11 requirements retained. HLS11.180ns still
fails original4ns/default1.08ns. Both global drains0 and all board/CDC gates
remain unchanged. No hardware/install/network/BIOS/fan/reboot/flash or
automatic Git publication changes.

## Retained-source native integration: ALL27 scenarios passed (117, historical)

[Dispatcher native-full001](../results/2026-10-18/rocev2-rnic-segmented-executor-native-full-001.json)
PASSES414.61s compilation and ALL27 scenarios, each17.95..24.76s. All1398
bound source/artifact records were reverified after terminal success. The
previously pending ordinary nonzero65-byte WRITE/SEND now execute through
actual trusted SQ/C128 decoding, MR/PTE/paged PCIe DMA, retained source, shared
physical command nonce, generated HLS, replay and CQ. Their XGMII/FCS/SFD/two
CDC FIFOs/MAC EOF/tail are actual RTL; second genuine MAC receipt is withheld
past1024 cycles, not manufactured by the test. Physical host/root/peer/PHY/PTP
endpoints remain two-state models; normal READ/SEND_IMM retain their existing
physical-MAC receipt model. This is not Linux, physical or timing signoff.

Each ordinary source case observes exactly one full748-bit source owner,
aggregate event, same genuine CQ/HLS/dispatcher retirement, and two actual
MAC SFD receipts. Source authority/guard persists continuously through final
event and withheld MAC completion until that exact whole-owner CQ handshake.
The independent CQ oracle equals the retained source owner. LogicalC001 is
actually translated to fresh physical1; only the real backend's matching
status/error maps back. No active source or nonce owner/fault remains.

ALL25 prior service/RQ/RNR/requester/Atomic/permission cases also PASS on this
SAME dispatcher/HLS/shared-MR/PTE/physical-nonce graph. No case, original
1200s compile/30s runtime limit, identity/CRC/byte/deadline assertion or global
drain gate was dropped. [Completed-source audit002](../results/2026-10-18/rocev2-rnic-segmented-executor-native-source-002.json)
independently reexecutes the two finished cases' Python wire/CQ/owner/nonce
oracles against archived inputs/logs/CQ snapshots;53 bound records verified.
It records the earlier partial-batch state, NOT a new DUT run or27-case pass.
A malformed first audit export was preserved under the build directory;
only its truncated JSON observation was regenerated, without DUT/test edits.

Native large admission remains CLOSED at4096 bytes. Remaining coordinated
work includes full-range admission/HLS/CQ owner checks; true FIRST/MIDDLE/LAST
header/RETH-total/fragment-offset validation; consecutive24-bit PSNs including
wrap; per-packet exact response/HLS-ACK/MAC/tail/replay ownership and rearming;
full-WR first/next-PSN receipt; and one final genuine CQ. The current one-frame
replay cache must rotate only after real packet ownership transfer while the
whole WR/source lease remains held, not simulated CQ or global idle signals.
Do not merely raise length limits, relax PSN+1 or send child WRITE_ONLY verbs.

Large RX/READ/Immediate, multi-SGE, real registered host memory/queues,
Linux/provider/API, physical/recovery and full-board timing remain open.
All11 original requirements are retained. HLS11.180ns still FAILS original
4ns/default1.08ns; full-board setup/hold/pulse/skew/routing/DRC/check_timing/CDC
gates and both global drains0 remain unchanged. No hardware/install/network/
BIOS/fan/reboot/flash or automatic Git publication changes.

## Retained-source ordinary WRITE/SEND native integration (116, historical)

NEW `tests/segmented_executor_native_fixture.py` observes the ACTUAL dispatcher,
trusted full748-bit source owner, source aggregate event and genuine CQ/HLS
retirement. All local CQ, HLS-retire and dispatcher-retire handshakes must be
identical; a retained source must keep its whole owner/guard continuously until
that same genuine handshake. No observer drives a producer receipt or drain.

The new dispatcher full-native001 now BUILDS ALL27 cases: both nonzero local
ordinary WRITE/SEND plus all25 prior service/RQ/RNR/Atomic/permission cases.
The ordinary cases switch to actual XGMII/FCS/SFD/CDC/MAC at the same drained
boundary as the existing Atomic/zero cases. Their second actual MAC receipt
is withheld beyond the1024-cycle tail, preserving the exact old wire/replay/
source-byte/CQ checks. The logical command must be exactlyC001; the common
nonce must actually translate it to physical1 and translate its real status
back. The independent CQ-owner oracle must equal the retained source owner.

Complete bench elaboration/width checks have passed and the new model is
COMPILING under unchanged1200s build/30s per-case limits. No runtime pass is
claimed yet. The previous25-case pass below remains the PRE-dispatcher graph;
it is not substituted for this run. Large native admission/per-packet wire/
whole-WR CQ, Linux/provider/physical/recovery/multi-SGE/full-board timing and
all11 requirements remain open. Original4ns/default1.08ns and both global
drains0 remain; no hardware, configuration, reboot or automatic push changes.

## Publication snapshot: segmented source and native regression (115, historical)

[Segmented-HLS/shared-nonce native-full001](../results/2026-10-18/rocev2-rnic-segmented-native-full-001.json)
PASSES ALL25 existing scenarios after415.90s compilation, each at most23.91s.
All1380 bound source/artifact records were reverified before publication.
The actual generated HLS, shared MR/PTE/paged backend, physical command nonce,
XGMII/FCS/SFD/CDC/MAC/CQ run together. Mixed Atomic executes five genuine
backend commands with four actual logical/physical tag translations. Every
prior zero-service/RQ/RNR/requester/permission oracle remains. Physical host,
root, peer, PHY and PTP endpoints remain models: no Linux or hardware signoff.

NEW `fpga/derive_segmented_executor.py` wires the actual retained-source
controller alongside the unchanged legacy executor, using ONE common native
MR/PTE/backend/physical-nonce domain. All ordinary nonzero WRITE/SEND retain
their full748-bit source owner through fragment reads/replays and the final
memory event until an identical genuine whole-WR CQ retirement. READ/Atomic
placement, Immediate and zero-length work keep the legacy path. The actual CQ
handshake releases HLS and retained source atomically; a raw CQ offer is also
identity-checked even when the other consumer withholds ready.

[Source007](../results/2026-10-18/rocev2-rnic-segmented-source-007.json)
PASSES seven methods/11 cases1.63s;48 records reverified.
[Dispatcher003](../results/2026-10-18/rocev2-rnic-segmented-executor-mux-003.json)
PASSES five methods/11 cases2.51s;72 records reverified. These include small
WRITE/SEND,8193-byte fragmentation, initial/final replay, mixed legacy and
retained-source traffic, global nonreusing physical tags, withheld genuine CQ
and foreign raw CQ offers. Backend/CQ/trusted MR grants in these units remain
MODELS. [Latest complete-graph elaboration002](../results/2026-10-18/rocev2-rnic-segmented-executor-native-elaboration-002.json)
PASSES3.25s with1206 bound records reverified. It checks actual dispatcher/
source/legacy/HLS/MR/PTE/backend wiring and dual CQ fanout, but is compile-only,
not a runtime pass.

The25-case native pass above is the PRE-dispatcher graph. Those cases contain
no nonzero local ordinary WRITE/SEND, so they do NOT qualify the new source
path. The new full-native dispatcher probe is an unexecuted development
candidate; add ordinary WRITE/SEND runtime cases and read-only exact CQ/source
observations before relying on it. Native admission still limits work to4096
bytes. Large admission, per-packet wire/MAC/PSN span and one final CQ must be
extended coherently; C++1MiB success alone is not native1MiB support.

READ/Immediate>4096, multi-SGE, Linux/provider, physical/recovery and full-board
timing remain open. HLS11.180ns STILL fails original4ns/default1.08ns. All11
requirements and both global drains0 remain; no new device capability, board
image, hardware/install/network/BIOS/fan/reboot/flash changes. This publication
is explicitly user-requested; it does not authorize future automatic pushes.

Publication checks parse all17 new Python modules and27 new JSON records;
`git diff --check` passes. A fresh `bash scripts/check.sh` still exits1 at the
known historical `rocev2_tx_padding.v` SHA mismatch in the2026-10-17 transport
record, after Tcl/allowlist/source checks pass. That provenance gate is NOT
waived or relabeled; this is not an all-tests-green release.

## Shared physical DMA-command identity in actual native graph (114, historical)

NEW `rocev2_memory_command_nonce` sits AFTER every normal/local/Atomic memory
client and BEFORE the one actual shared paged backend. It captures the whole
immutable write/offset/length/full-key/logical-tag tuple, assigns each backend
command a fresh nonwrapping physical nonce, and translates ONLY that genuine
matching backend status back to the retained logical tag/error. Overlapping
or reused client tags such asf123/c001 no longer imply physical identity.
Data, EOF, page/DMA/descriptor/fence semantics stay with the ACTUAL backend;
the translator does not manufacture them or grant memory authority.

[Four-state nonce001](../results/2026-10-18/rocev2-rnic-memory-command-nonce-001.json)
PASSES four methods/eight cases in0.13s, with all27 source/artifact records
verified: reused/overlapping logical tags, command/status stalls, premature/
stale/unknown/duplicate statuses, late fault with held offers, unchanged real
error7 and nonwrapping exhaustion. Adjacent clients/backend remain MODELS.
The final allocated nonce may complete; new commands are blocked at exhaustion.

`fpga/derive_segmented_native.py` connects this translator into the SAME actual
native graph and selects the real new segmented HLS generation. Physical tags
reach the actual paged backend; real statuses return through the translator.
Its busy/fault/configuration guard participates in real idle/drained/fault and
MR/PTE/QP management gates. Default sources and both global drains0 remain.
[Whole-native elaboration002](../results/2026-10-18/rocev2-rnic-segmented-native-elaboration-002.json)
PASSES3.23s, with all1162 source records current and no port-width warnings:
one actual new HLS, MR/PTE/PSN/MSN domain, common nonce and paged backend.
[Diagnostic](../results/2026-10-18/rocev2-rnic-memory-nonce-integration-diagnostics-001.json)
preserves the first duplicate-port derivation failure; existing connections
are now uniquely replaced, not appended, with no policy or width waiver.

Fresh native-full001 is RUNNING all25 prior zero-service/RQ/RNR/requester/
Atomic/permission scenarios against this new HLS+nonce graph. Its first
`SERVICE_AFTER_WRITE` case PASSES21.50s, including one actual admitted/issued/
backend-completed/logical-completed transaction and no nonce fault/held owner;
the remaining24 cases are pending. Added read-only
observers check the ACTUAL full command tuple/physical sequence/backend status/
logical error mapping and lifetime cardinality, without driving DUT receipts.
Original1200s compile/30s per-case limits and every prior case oracle remain.
No whole-batch success is inferred yet. Large native admission, retained source
dispatcher, per-packet wire and whole-WR CQ wiring are STILL OPEN: the new
source DMA component is not selected as a working large native datapath.
READ/Immediate>4096, multi-SGE, Linux/provider/recovery/physical/full-board
timing and all11 requirements remain. HLS11.180ns still fails original clocks.
No hardware/default/install/load/network/BIOS/fan/reboot/flash or auto-push.

## Segmented HLS generated; retained whole-WR source DMA component (113, historical)

[Actual new-top HLS001](../results/2026-10-18/rocev2-rnic-segmented-request-synth-001.json)
PASSES351.54s generation with all696 source/frozen/generated records reverified.
The selected top is `rocev2_native_segmented_request_top`; every old external
ABI width remains exact. Resources:75,548LUT/98,051FF/209BRAM18/0DSP.
Original4ns/default1.08ns,8QP/2000entries are unchanged. Estimated11.180ns
STILL FAILS original timing; no full-board, bitstream or physical claim.

NEW `rocev2_segmented_source_executor` retains one trusted748-bit large WRITE/
SEND owner across ordered bounded reads, the most recent fragment's replays,
and the aggregate memory event. Every child subrange/VA/offset/key/PD/identity
comes from that saved full owner. A fresh nonwrapping logical DMA tag is used
for EVERY read/re-read; the real HLS ctl bit is checked before translating it
to the bounded child's complete-transaction ctl. The actual prior native
child executor, unchanged except its module name, still checks every command,
data byte/keep/EOF and matching status. Its downstream ownership transfer goes
to this still-held actual whole-WR owner, not an idle or constant drain flag.
One aggregate memory event does NOT release the source: final-fragment replays
remain possible until an identical genuine whole-WR CQ retirement is received.

[Four-state source006](../results/2026-10-18/rocev2-rnic-segmented-source-006.json)
PASSES six methods/nine cases in1.39s. WRITE/SEND8193-byte WRs split into
4096/4096/1-byte reads; initial and final replays, stalled real data and whole
event, early/foreign retirement, stale status during the next unique tag,
actual child backend error7, nonwrapping tag exhaustion and late faults are
checked. All40 bound source/run-artifact records and all nine exact child
clones were verified against full-native004's actual executor. Backend and CQ
endpoints are MODELS, not actual MR/page/DMA/native HLS/MAC/CQ integration.
[Diagnostics](../results/2026-10-18/rocev2-rnic-segmented-source-diagnostics-001.json)
preserve failed fixtures and a real implicit-function-dependency RTL defect.
The saved WR/length/QPN are now explicit function inputs; no identity assertion
was removed. Historical source004 pass is not substituted for current006.

Logical source tagsC001..ffff still require global backend namespace isolation
or a shared nonreusing physical-command nonce translator AFTER all memory
clients. That adapter and whole-native large memory/wire/CQ wiring remain
OPEN; this component is not selected as a working large native datapath yet.
READ/Immediate>4096, multi-SGE, Linux/provider, recovery, physical operation and
all11 original requirements remain. No hardware/default/install/load/network/
BIOS/fan/reboot/flash or automatic Git publication changes.

## Whole-native zero-service pass; real multi-packet WRITE/SEND source (112, historical)

[Fresh full-native004](../results/2026-10-18/rocev2-rnic-zero-service-native-full-004.json)
PASSES410.44s compilation and ALL25 scenarios, each17.00..22.66s. Four new
ordinary zero WRITE/READ/mixed/after-normal-WRITE scenarios each execute two
services through actual privileged QP binding, generated HLS, XGMII/FCS/SFD,
two CDC FIFOs, MAC EOF/tail and exact400-bit retirement. All21 old zero-RQ,
RNR, requester, Atomic and permission cases also pass on this SAME graph.
All1207 bound source/artifact records were reverified. Physical host/root/
peer/PHY/PTP remain TWO-STATE MODELS: this is NOT Linux or physical signoff.

NEW `hls/segmented_request_transport.py` extends the SAME complete source
with genuine multi-packet ordinary WRITE and SEND up to1MiB. One748-bit WR
owner remains retained through FIRST/MIDDLE/LAST and one final816-bit receipt;
these are NOT multiple independent WRITE_ONLY verbs. Each next fragment waits
for its real previous ACK, exact singleton replay pointer/pool release,
consumed timer and SAME common-PSN readback. FIRST WRITE retains full-message
RETH length/key/VA but fetches only4096 bytes; actual stored FIRST replay does
the same. Terminal zero padding and BTH pad count are exact, including dirty
unused source-memory lanes. Whole-message first/next PSN and wrap are retained.

[Fresh C++003](../results/2026-10-18/rocev2-rnic-segmented-request-csim-003.json)
PASSES51.23s compilation/8.06s runtime: six WRs,284 fresh packets, seven actual
stored replays, independent Python reconstruction of all291 complete wire
records,4097/8192/12289/8193/65537/1048576-byte transfers, withheld real ACK/
timer/common-state consumers, and five actual pre-issue rejection cases.
All previous Atomic/zero-requester/zero-RQ/ordinary-zero cases repeat on this
new source. [Compatibility001](../results/2026-10-18/rocev2-rnic-segmented-request-compat-001.json)
PASSES25.25s/1.01s: actual owned Atomic/MR/paged-memory RTL supplies nine jobs,
and unchanged Immediate TX/RX assertions pass. Peer/connection/source-memory
endpoints remain models. [Diagnostics](../results/2026-10-18/rocev2-rnic-segmented-request-diagnostics-001.json)
preserve the first failed JSON/hex-output batch and exact preimages; later
source metadata only documented inherited ports, leaving all9 derived HLS
files unchanged and freshly retested. Failed001 is not relabeled.

Actual new-top HLS generation001 is RUNNING, using all original parent
consumer/ABI/frozen-source gates and1500MiB/4ns/default1.08ns/8QP/2000entries.
The run-directory prefix is inherited from the unchanged parent builder;
the actual selected top is `rocev2_native_segmented_request_top`, NOT the old
zero-service top. No generated-RTL or timing success is inferred yet. An
inactive old object cache alone was losslessly archived, all106 files verified
against persistent compressed backup and RAM, with the original path kept.
No source/evidence/binary bytes were discarded.

Large-transfer native MR/DMA/MAC/CQ, kernel/provider and physical integration
remain open. READ/Immediate remain4096 bytes; multi-SGE is NOT implemented.
The prior zero-service13.568ns estimate STILL FAILS original timing; full-board
setup/hold/pulse/skew/routing/DRC/check_timing/CDC and all11 requirements remain.
No hardware/install/load/network/BIOS/fan/reboot/flash or automatic Git changes.

## Ordinary zero-service native validation (111, historical)

[Full-native003](../results/2026-10-18/rocev2-rnic-zero-service-native-full-003.json)
compiled421.03s, then stopped19.40s into its first `SERVICE_AFTER_WRITE`
case. Unlike002, a genuine zero WRITE reaches its actual HLS400-bit receipt,
real tagged4001 XGMII/FCS/SFD transmission, accepted MAC EOF and the complete
1024-cycle tail. The batch is STILL FAILED; the other24 cases did not run.

[Frozen-model diagnostic004](../results/2026-10-18/rocev2-rnic-zero-service-native-diagnostics-004.json)
reverified all1085 bound records before correction. At the genuine fatal,
full owner/core match, MAC-done/own-receipt/tail-started are1, tail-left is0,
retire-valid/ready are1, actual tag is4001 and DUT fault is0. The monitor's
task loop-control variable unexpectedly still reads0; the frozen generated
C++ contains no first store1, although stores2/3 remain. This is an observation
of this exact model, not a general diagnosis of the compiler.

Only the fixture's expected tag now uses its INDEPENDENT accepted-retirement
counter: exact4001+count, with count strictly below2. Full wire/tag/owner/core,
accepted EOF/genuine SFD/tail and all no-data-authority checks remain. No DUT,
HLS, clock, drain, deadline or tag policy changed; all47 derived RTL/HLS-data
files match003. Full-native004 is now COMPILING all25 cases under the unchanged
1200s/30s limits, NOT a pass. No hardware or automatic publication changes.
The open Linux/provider/physical/large/multi-SGE/recovery/timing requirements
below are unchanged; original HLS timing still fails13.568ns.

## Publication snapshot: ordinary zero-service validation (109, historical)

The current zero-service source is a development candidate, NOT a completed
native runtime pass. [Full-native002](../results/2026-10-18/rocev2-rnic-zero-service-native-full-002.json)
compiled412.05s, then stopped15.75s into its first `SERVICE_AFTER_WRITE`
case at the host-byte oracle; the other24 cases did not run. No zero-service
owner/HLS/core/retirement event had executed. The genuine normal8-byte WRITE
did execute through MR/PTE/PCIe, with no DUT fault.

[Frozen-model diagnostic003](../results/2026-10-18/rocev2-rnic-zero-service-native-diagnostics-003.json)
preserves the failed binary/input hashes and exact debugger observations.
The new standalone normal-WRITE prelude reused an oracle that expected a
previous Atomic update which this scenario never performed. Actual sentinel
bytes correctly retained their initial values, and the normal8-byte WRITE
held the expected data. Only the scenario-specific expected-byte selection
was corrected: all surrounding bytes, written bytes and posted-valid bits
remain checked. No DUT/HLS/clock/drain/deadline change was made; all47 derived
RTL/HLS-data files match the failed run byte for byte.

Fresh full-native003 is IN PROGRESS at this publication, with all25 cases
and the original1200s compile/30s per-case limits. Its eventual result is
outside this snapshot; neither the correction nor the running job is a pass.
The prior zero-RQ21-case pass and the new source/unit/HLS-generation evidence
below remain distinct. Original timing still fails13.568ns; full-board,
Linux/provider and physical qualification remain open. This checkpoint is
published at the user's explicit request; future automatic push is not
authorized. No hardware/install/load/network/BIOS/fan/reboot/flash changes.

## Ordinary zero WRITE/READ native owner and MAC integration (108, historical)

[Fresh actual HLS generation001](../results/2026-10-18/rocev2-rnic-zero-service-synth-001.json)
PASSES340.46s with all old ABIs and distinct344-bit service-owner/400-bit
core-receipt ports verified. Resources:67,767LUT/92,925FF/209BRAM18/0DSP.
All source/frozen/generated hashes match. Original4ns/default1.08ns,8QP/
2000entries remain; estimated13.568ns STILL FAILS timing. Generation is
not full-board routing/timing/CDC signoff, a bitstream or physical proof.

`fpga/derive_zero_service_native.py` integrates ordinary zero WRITE/READ
into the SAME33-file native derivative plus separate padding/owner/MAC RTL.
Actual full-IP integrity, tuple/full-QPN/expected-PSN/RETH checks precede
admission. The real privileged SQC-bound QP access/PD/epoch/cookie and raw
RX-context reference supply the immutable service owner and Ethernet route.
It issues no MR lookup/zero command/data/status and takes no RQ or CQ.
The actual packet lease stays held until its own HLS and wire retirement.

New `rocev2_zero_service_owner` reserves the actual MAC owner FIRST, then
delivers the same344-bit owner to the actual generated HLS. New
`rocev2_zero_service_mac` is OUTSIDE existing Atomic/native tag policies:
it captures only its owned normal response, checks full Ethernet/IP/BTH/
AETH identity against the400-bit core receipt, and transmits with fresh
4001..5fff tags. ONLY the exact genuine SFD receipt is translated back to
the inner normal4000 drain guard; old/unknown/duplicate/premature receipts
fault without retiring. Actual accepted MAC EOF and unchanged1024-cycle
tail are also mandatory. No Atomic owner alias, fake RQ, quiet/global drain
certificate, timing/CRC waiver or default-graph change is introduced.

[Owner002](../results/2026-10-18/rocev2-rnic-zero-service-owner-002.json)
PASSES five four-state methods: ordered reservation, both downstream stalls,
immutable data, late faults and bad/unknown owners.
[MAC001](../results/2026-10-18/rocev2-rnic-zero-service-mac-001.json)
PASSES five methods/15 four-state cases in1.04s: actual mux/wire bytes,
withheld core/SFD/EOF/tail, stable stalled output/retirement, exact owner,
bad wire/core and stale/unknown/duplicate/legacy receipt quarantine.
Adjacent producers/physical MAC endpoints remain MODELS in these unit tests.
[Whole-native elaboration003](../results/2026-10-18/rocev2-rnic-zero-service-native-elaboration-003.json)
PASSES2.95s without port-width warnings, exactly one new owner/MAC instance
and one actual HLS/MR/PTE/PSN/MSN/RQ/CQ domain. Both global drains remain0.

Source review found that a previously admitted ordinary response may still
own the normal4000 MAC tag AFTER its IP handoff. Full-native001 was stopped
at294.25s compilation before runtime, using only its verified own compiler
process group; all1074 bound inputs/artifacts and preimages were preserved.
This was a concrete source-review correction, NOT an observed runtime
failure or an expired observation. New zero admission now waits for the
EXISTING `response_tx_quiescent` drain condition before taking its owner;
CRC/tuple/PSN/access/context gates remain. [Drain diagnostic](../results/2026-10-18/rocev2-rnic-zero-service-native-diagnostics-002.json).

Fresh full-native002 now COMPILING: four ordinary zero WRITE/READ/mixed
scenarios (two services each), no SQ/RQ/CQ/data-memory work for the ZERO
services, actual privileged
QP binding/HLS/XGMII/FCS/SFD/two CDC FIFOs/MAC/tail and independent full
wire/344-owner/400-core/host-sentinel oracles, plus ALL21 prior native cases
(25 total). The added AFTER_WRITE case first performs a genuine normal
8-byte WRITE through the unchanged MR/PTE/PCIe path, withholds its actual
legacy MAC receipt, verifies zero admission waits, then releases the old
real receipt/drain and completes mixed zero WRITE/READ. Zero-service traffic
counters are explicitly scoped AFTER that real data prelude; no globally
zero DMA or unchanged-initial-host claim is made for the whole mixed case.
Original1200s compilation and30s per-case deadlines remain. No runtime
success is inferred from elaboration or unit tests. [Diagnostic record](../results/2026-10-18/rocev2-rnic-zero-service-native-diagnostics-001.json)
preserves the ambiguous legacy/shared child derivation failure and an
initial malformed report trailer; real RTL assertions were not relaxed.
Actual Linux/provider/physical operation, large/multi-SGE, recovery and
all11 original requirements remain. No hardware/install/load/network/BIOS/
fan/reboot/flash or automatic commit/push changes.

## Whole-native zero RQ pass; ordinary zero WRITE/READ source (107, historical)

[Fresh full-native RX004](../results/2026-10-18/rocev2-rnic-zero-rq-native-full-004.json)
PASSES404.90s compilation and ALL21 cases, each15.94..21.91s. Six zero RX
cases cover SEND/SEND_IMM/WRITE_IMM with actual posted0/128-byte RQ buffers,
two receives each. Two empty-RQ/RNR cases and all13 prior Atomic/normal/
permission/zero-requester cases also pass. Actual RQ128/PCIe fetch, complete
generated zero-RQ HLS, shared MR/PTE/PSN/MSN, XGMII/FCS/SFD/CDC/MAC and exact
CQ/host-ACK lifetimes execute together; independent wire/CQ oracles pass.
All1182 bound source/artifact records were reverified. This is still
TWO-STATE host/root/peer/PHY/PTP modeling, not Linux or physical operation.
It does NOT test the newer ordinary zero-service graph described below.

`hls/zero_service_transport.py` adds ordinary zero WRITE_ONLY and READ_REQUEST
to the SAME full core. A distinct344-bit trusted outer service owner binds
QPN/PD/epoch/cookie/lease/PSN/opcode/full remoteVA/key/length0. Neither
operation consumes a posted RQ, aliases Atomic work, grants memory access,
issues a zero memory command, nor synthesizes a data/status completion.
The actual raw16-byte RETH/keep/EOF must be consumed; then the SAME RX MSN
write/readback, real ACK or AETH-only READ-response header consumer, and
SAME RX PSN write/readback join produce a400-bit core receipt. This receipt
is explicitly NOT physical MAC/SFD/EOF/tail lifetime or native retirement.
The outer owner/protection source is still a model at this stage.

[C++003](../results/2026-10-18/rocev2-rnic-zero-service-csim-003.json)
PASSES44.43s compilation/2.53s runtime: four alternating zero WRITE/READ
services, same-domain PSN wrap, independently withheld real owner/RETH/MSN/
TX/PSN consumers, exact full owner/wire and16 owner/RETH/sequence negatives.
All prior Atomic/zero requester/zero-RQ cases repeat on this new source.
[Compatibility001](../results/2026-10-18/rocev2-rnic-zero-service-compat-001.json)
PASSES23.58s/0.93s with the actual owned Atomic/MR/paged-memory RTL service
and unchanged prior Immediate TX/RX assertions. Peer/connection/outer QP
and physical memory/MAC boundaries remain MODELS. [Diagnostics](../results/2026-10-18/rocev2-rnic-zero-service-diagnostics-001.json)
preserve the first compile signature error and second missing fixture event
merger, exact preimages and failed evidence; no failed batch is relabeled.

At107 HLS generation001 for `rocev2_native_zero_service_top` was RUNNING;
it subsequently PASSES generation at108 above, but fails original timing.
The original1500MiB guard,4ns/default1.08ns,8QP/2000entries and
all prior proof gates remain. An inactive old compiled-object cache alone
was losslessly archived, all176 files roundtrip-verified, then moved to RAM
with its original path retained as a symlink and a persistent backup.
No evidence/source/binary bytes were deleted. New native zero-service
ownership/MAC integration, large/multi-SGE, actual Linux/provider/physical
operation/recovery and all11 original requirements remain. The prior
zero-RQ estimate13.568ns STILL fails original timing; the new estimate is
also13.568ns, and neither graph has full-board signoff. No hardware, install,
load, network, BIOS/fan, reboot/flash or automatic commit/push changes.

## Publication snapshot: native zero RX partial passes (106, historical)

[Full-native RX003](../results/2026-10-18/rocev2-rnic-zero-rq-native-full-003.json)
compiled402.94s and PASSES SEND, SEND_IMM and WRITE_IMM into posted zero-byte
buffers, each20.50..20.71s with two consecutive receives. Actual coherent
RQ128 fetch, generated HLS EOF/PSN/MSN, XGMII/FCS/SFD/CDC ACK receipts,
full620-bit CQ ownership and exact host ACK execute together. Independent
Python wire/CQ checks pass; there are no data MR queries/DMA/status writes.
Physical host/root/peer/PHY/PTP remain MODELS, not Linux or board operation.

The entire batch is STILL FAILED: RX_SEND into a128-byte posted buffer
reaches two actual HLS/MAC/CQ receipts, then fails the final counter check;
the remaining17 cases did not run. The fixture incorrectly labels the
shared MR-table output as wire-only queries, although that output also
carries local posted-buffer authorization. The correction counts the real
RX client separately and additionally checks exact local/RQ/table totals
and the actual posted-buffer PD/key/address/length/operation. No DUT/HLS,
wire/CQ/sentinel oracle, deadline, ownership or drain gate is changed.
All1102 failed-run source/artifact hashes were reverified using preserved
fixture/launcher preimages. Fresh21-case RX004 is RUNNING at publication,
not a pass; all47 derived RTL/HLS-data files match RX003 byte for byte.
See [observer diagnostics](../results/2026-10-18/rocev2-rnic-zero-rq-native-diagnostics-004.json).

Ordinary incoming zero WRITE/READ, large/multi-SGE, actual Linux/provider/
physical operation, recovery and all original full-goal gates remain open.
Estimated13.568ns still misses4ns/default1.08ns; no board timing signoff.
This commit/push is explicitly user-requested; no hardware/default/install/
network/BIOS/fan/reboot/flash changes are made.

## Whole-native zero RX fixture and minimum-frame ingress (105, historical)

`tests/zero_rq_native_fixture.py` keeps all13 requester/Atomic/permission
cases and adds actual independent coherent RQ128 fetch, two consecutive
receives, posted zero/128-byte buffers, SEND/SEND_IMM/WRITE_IMM, empty-RQ RNR,
no data DMA, real generated HLS EOF/PSN/MSN, actual XGMII/FCS/SFD/CDC ACK
receipts, full620-bit CQ snapshots and exact/stale host-ACK checks. Adjacent
physical host/root/peer/PHY/PTP remain MODELS. Eight receiver/RNR scenarios
plus13 old cases form the fresh21-case batch, each bounded30s.

[First full-native RX001](../results/2026-10-18/rocev2-rnic-zero-rq-native-full-001.json)
compiled406.98s, then FAILED its first RX_SEND/capacity0 case at22.71s;
the other20 cases did not run. The genuine failed-model debugger shows
one posted RQ, zero taken/core receipts, `request_drop_count=1`, and
`rxgood=rxbad=0`. This was an Ethernet-steering drop BEFORE IP integrity:
the old minimum62 assumes Ethernet14+IP48, but empty SEND_ONLY is IP44
and a legitimate minimum60-byte Ethernet frame with two Ethernet pad bytes.

A checked PRIVATE ingress derivative now admits60 ONLY for request-mode
SEND_ONLY/IP44/BTH-pad0; response mode, configured tuple/MAC, dense keep,
error and other minimum checks remain. The separate new
`rtl/rocev2_zero_rx_padding.v` removes EXACTLY the two Ethernet pad bytes
from this complete shape AFTER Ethernet stripping and BEFORE the unchanged
whole-IP checksum/ICRC stage. It does not waive IP length/CRC validation.
An independent actual-IP-RTL reproduction also confirmed the second gap:
untrimmed46 bytes fail while the exact44-byte IP frame recovers. This
component diagnosis must NOT be mislabeled as the initial native drop.

[Router001](../results/2026-10-18/rocev2-rnic-zero-rx-router-001.json) PASSES
two four-state methods/12 frames in0.20s: exact short request, unchanged
response-mode minimum and host sidebands, malformed length/pad/keep/error
and recovery, with real FIFO/Ethernet stripping/backpressure.
[Padding001](../results/2026-10-18/rocev2-rnic-zero-rx-padding-001.json)
PASSES two four-state simulations, each<=15.19s:21 good/10 bad whole-IP
frames, actual strict checksum/ICRC/FIFO and backpressure. Both original
65536-keep-mask and21-bit RX-checksum exhaustive predicate oracles remain.
[Actual whole-native elaboration004](../results/2026-10-18/rocev2-rnic-zero-rq-native-elaboration-004.json)
PASSES2.78s without width warnings, one new adapter and one native HLS/MR/
PTE/PSN/MSN/RQ/ACK/CQ/fetch domain; both global HLS drain inputs remain0.
HLS source/generated bytes are unchanged from104, not a stub or old
requester-only executable substituted for the changed native graph.

Fresh [full-native RX002](../results/2026-10-18/rocev2-rnic-zero-rq-native-full-002.json)
compiled408.68s but FAILED the first case at21.71s. The frozen-model debugger
now proves `request_drop_count=0`, `rxgood=1`, `rxbad=0`, byte_count44,
frame_bad0 and ERR_FORMAT16 in PARSE/REJECT. The two Ethernet fixes really
reach and pass actual IP integrity, but the private parser still inherited
`send_header_bytes+4` as its minimum, erroneously requiring four payload
bytes. It now requires the exact complete SEND header (including ICRC),
while retaining the exact final length/pad/class/owner/PSN checks and the
full receive-retirement/CQ profile requirement for zero payloads. Normal
incoming zero WRITE/READ remain refused. [Elaboration005](../results/2026-10-18/rocev2-rnic-zero-rq-native-elaboration-005.json)
PASSES2.87s on this current graph; [router002](../results/2026-10-18/rocev2-rnic-zero-rx-router-002.json)
repeats the unchanged actual routing cases successfully. The subsequent
[full-native RX003](../results/2026-10-18/rocev2-rnic-zero-rq-native-full-003.json)
has three partial passes but FAILS the batch; see106 above. Exact failed reports, source preimages, binaries
and actual diagnostic evidence are preserved in [Ethernet diagnostics](../results/2026-10-18/rocev2-rnic-zero-rq-native-diagnostics-002.json)
and [parser diagnostics](../results/2026-10-18/rocev2-rnic-zero-rq-native-diagnostics-003.json).
Remaining native RX runtime, ordinary incoming zero WRITE/READ without fictitious RQ,
large/multi-SGE, actual Linux/provider/hardware/recovery and original timing
still remain. Estimated13.568ns still fails4ns/default1.08ns. No hardware,
install/load/network/BIOS/fan/reboot/flash or automatic publication changes.

## Zero RQ native candidate and actual HLS generation (104)

`fpga/derive_zero_rq_native.py` extends the SAME private native graph with
canonical zero posted RECV admission, zero placement/core receipt, ACK-owner
and CQ support. Empty SEND/SEND_IMM/WRITE_IMM takes the ACTUAL coherent RQ
owner. A no-data lease grants no MR/DMA authority and invents no command,
data or backend status; its command/data/status-complete bits remain0.
Wire ACK handoff is STILL not HLS EOF/PSN retirement, actual MAC receipt or
CQ commit/retire. Normal posted buffers receiving0 retain their whole owner.
Zero local key/VA/offset must be canonical0 when posted capacity is0.
Ordinary incoming zero WRITE/READ are STILL refused, not assigned a fake RQ.

[Native units003](../results/2026-10-18/rocev2-rnic-zero-rq-native-units-003.json)
PASSES25 four-state methods in3.78s, including previous Atomic/Immediate/
permission/CQ cases, canonical zero RECV with no MR query, six zero RX
placement/receipt/CQ profiles, bad owner/PSN/notification/length cases, and
the actual ACK owner's exact wire/PSN/MSN/fresh-tag/backpressure/1100-cycle
withheld-MAC/tail/CQ checks across six profiles. Adjacent proof producers,
host and physical MAC pins are MODELS, not generated-HLS/native runtime.

[Fresh HLS generation001](../results/2026-10-18/rocev2-rnic-zero-rq-synth-001.json)
PASSES321.30s from the exact103 C++/owned-service-tested complete source,
not a stub or second PSN/MR domain. Top `rocev2_native_zero_rq_top` preserves
all requester748/SQ408/done816 and receive620/680/752 ABIs. Resources are
64,489LUT/86,950FF/189BRAM18/0DSP. Original4ns/default1.08ns,8QP/2000entries
are unchanged; estimated13.568ns STILL FAILS timing. This is generation,
not full-board signoff, a bitstream, or physical qualification.

[Actual whole-native elaboration002](../results/2026-10-18/rocev2-rnic-zero-rq-native-elaboration-002.json)
PASSES2.88s with no port-width warnings and exactly one native HLS/RQ/ACK/
CQ/MR/PTE/PSN/MSN/fetch domain. The private SEND44 integrity helper is used
in actual incoming admission and both native bridge directions (three
instances); original integrity/protected definitions are unchanged.
Both original global HLS-drain inputs remain0. This compile-only result
does NOT establish runtime zero reception, Linux coupling or safe unpin.

Independent requester full-native003/004 FAILED generated-C++ coroutine
scope compilation before runtime. Exact failures/preimages are preserved;
all45 generated bench/RTL/data files and common non-launcher inputs match
full002. A fresh005 retry changes only compiler partition size, retaining
the full timed coroutine while partitioning the giant reset function. Its
original1200s compile/30s per-case deadlines and all RTL/oracles/gates remain.
See [compiler diagnostics](../results/2026-10-18/rocev2-rnic-zero-native-diagnostics-004.json).
The launcher now owns its compiler process group on timeout; [four mocked
ownership cases](../results/2026-10-18/rocev2-rnic-zero-native-compiler-001.json)
pass, not an actual long timeout or DUT proof.

[Fresh whole-native005](../results/2026-10-18/rocev2-rnic-zero-native-full-005.json)
now PASSES422.29s compilation and ALL13 cases, each15.54..19.20s: the eight
prior Atomic/normal/permission cases plus all five zero requester operations
(WRITE/READ/SEND/SEND_IMM/WRITE_IMM). Actual generated zero REQUESTER HLS,
coherent SQ128 fetch, protected responses, stored replay, XGMII/FCS/SFD/CDC,
MAC completion, full748-bit CQ and exact host ACK execute together. All
five zero cases prove no local data MR query/command/data/status/fence,
exactly one real SQ-fetch PCIe read, and unchanged host/sentinel bytes.
The minimum-padded SEND44 now passes the complete path. Source hashes stay
unchanged throughout. This remains TWO-STATE physical host/root/peer/PHY/PTP
MODELING, NOT actual Linux or hardware. It tests `rocev2_native_zero_request_top`,
NOT the newer zero-RQ graph; do not substitute it for native zero RX runtime.

Native zero RQ runtime, normal zero responder WRITE/READ, large/multi-SGE,
actual Linux/provider/physical operation, recovery and all11 original goal
requirements remain. No install/load/programming/hardware/network/BIOS/fan/
reboot/flash or automatic publication occurs. Completed cache files alone
were losslessly archived, individually verified and relocated to RAM with
original-path symlinks; persistent backups retain all bytes across reboot.

## Same-core zero RQ receive source (103, historical source checkpoint)

`hls/zero_rq_transport.py` extends the SAME complete zero requester/Atomic/
Immediate core, preserving request748/SQ408/done816 and receive620/680/752
ABIs. Incoming empty SEND/SEND_IMM/WRITE_IMM uses the ACTUAL posted receive
owner, not a fake WQE or an anonymous ACK. A posted zero buffer must have
zero local key/VA/offset. A normal nonzero posted buffer can also receive0
bytes and keeps its full owner. WRITE_IMM still uses independent RETH data
authority when nonzero, never the RQ buffer as the remote-write destination.

No zero data-memory command or data beat is produced. The actual RX header
parser/stripper emits a real empty EOF; a new guarded consumer requires
that precise EOF and matching zero receive owner BEFORE the actual receipt
join can advance. It STILL needs actual ACK/MSN consumption and the SAME
PSN-table fence. Empty stream/quiet interfaces are not receipt substitutes.
Wrong local fields/QPN or malformed nonempty/nonfinal EOF quarantines the
operation without memory or receive completion. No extra PSN/MR domain.

[RQ C++003](../results/2026-10-18/rocev2-rnic-zero-rq-csim-003.json) PASSES
36.86s fresh full-top C++ compilation and1.40s execution: six actual zero RX
cases across all three operations/both posted buffer types, six owner/EOF
negatives, PSN wrap, immutable620-bit owners and actual wire Immediate,
withheld real EOF/ACK/state consumers, exact ACK QPN/PSN/MSN and no duplicate
receipt. All nine prior Atomic/normal requester cases and five zero requester
requests/stored replays/negatives run AGAIN on this SAME changed source.
[Compatibility001](../results/2026-10-18/rocev2-rnic-zero-rq-compat-001.json)
PASSES22.19s compilation/0.91s runtime with unchanged earlier Immediate TX/RX
assertions and actual owned Atomic/MR/paged-memory RTL service: nine Atomic
jobs, shared PSN/MSN, withheld real service/state consumers and replay/drop.
Peer/RQ/connection/physical memory boundaries remain explicit models.
Prefilled/quarantined test FIFOs and HLS-library warnings remain in logs;
no global FIFO-empty/drain or safe-unpin claim follows these component tests.

This SOURCE cohort is `rocev2_native_zero_rq_top`; it has NOT been HLS-
generated, integrated into native RQ/guard/CQ, installed or programmed.
Ordinary incoming zero WRITE/READ remain REQUIRED separate work: they must
not consume a fictitious RQ to obtain completion. Large/multi-SGE, actual
Linux/physical/timing/recovery and all11 goal requirements remain.
See [preserved fixture diagnostics](../results/2026-10-18/rocev2-rnic-zero-rq-diagnostics-001.json).

Publication checkpoint (2026-10-20): the independent102 requester
[full-native002](../results/2026-10-18/rocev2-rnic-zero-native-full-002.json)
reached its original1200s compile execution limit. It FAILED with
`TimeoutExpired`; ZERO runtime cases executed. A422.6MB generated C++
slow/reset function was the observed compiler bottleneck at -O0. This is
not a passing native run or an observed DUT runtime fault. Its original
report-bound log was preserved before stopping only the verified leftover
build children. See [timeout diagnostics](../results/2026-10-18/rocev2-rnic-zero-native-diagnostics-003.json).
No retry or new long build was started for publication. A future compiler-
output-function-splitting retry must preserve RTL/HLS/timing/CRC/oracles
and original1200s compile/30s per-test limits.

Publication checks freshly PASS14 staging methods/49 four-state cases in
3.88s ([staging003](../results/2026-10-18/rocev2-rnic-zero-native-staging-003.json))
and11 zero-WQE codec methods in0.40s. These are component regressions, not
a replacement for the failed whole-native run. Source/artifact hashes in
six selected current reports were rechecked:2663 records match, using the
exact preserved compile-log preimage for the timeout report.

## Zero native runtime / SEND44 and matched provider (102)

[Whole-native001](../results/2026-10-18/rocev2-rnic-zero-native-full-001.json)
completed456.73s fresh compilation and PASSED all eight099 normal/Atomic/
permission regressions, then actual zero WRITE and READ, each15.39..19.05s.
The two zero cases use actual generated HLS/SQ128 fetch, real stored replay,
protected ACK/AETH, actual XGMII/FCS/SFD/CDC and full CQ/host-ACK ownership.
There are ZERO local MR queries/data-memory commands/statuses/writes/fences;
the ONE PCIe read is the genuine SQ fetch. All host/sentinel bytes stay exact.
This is still TWO-STATE simulation with physical host/root/peer/PHY/PTP inputs
modeled, NOT actual Linux or hardware qualification. The BATCH IS FAILED:
ZERO_SEND stopped at14.29s and its final two zero Immediate cases did not run.
No partial result is relabeled as a complete five-operation native pass.

The preserved failed model and debugger show actual `core_tx_bad=1`, not a
missing/delayed MAC completion. Original integrity RTL assumes minimum IP48;
empty SEND_ONLY legitimately has IPv4/UDP/BTH/ICRC20+8+12+4=44 bytes. A NEW
named `rocev2_zero_ipv4_icrc` checked clone permits44 ONLY for opcode04 with
pad0, retaining all original whole-frame/UDP/checksum/ICRC/mask checks.
Only the actual native bridge's two RX/TX instances select this helper;
legacy/default and incoming protected-admission integrity remain ORIGINAL.
One native HLS/MR/PTE/PSN/MSN domain remains; no timing/drain gate changes.
The same change corrects the new fixture's expected SEND/Immediate-SEND
remote key to canonical0, without altering the already-correct actual C WQE.

[Integrity002](../results/2026-10-18/rocev2-rnic-zero-integrity-002.json)
PASSES3 methods/five four-state simulations, each10.56..15.31s:47 good and25
bad frames with actual FIFO backpressure, exact zero SEND44 TX/RX and
ordinary ACK/WRITE/padding/4096-byte cases, short wrong op/pad/truncated
BTH, invalid ICRC/IP checksum/UDP/keep/final length and recovery. Original
65536-mask and RX21-bit checksum-predicate oracles are retained. This is
actual integrity RTL, NOT full native execution. [Full elaboration003](../results/2026-10-18/rocev2-rnic-zero-native-elaboration-003.json)
PASSES2.74s without width warnings, including EXACTLY two private integrity
instances and zero global-drain overrides. Fresh whole-native002 compilation
was IN PROGRESS at102 and later timed out before any of its13 cases ran
(see publication checkpoint above). The unchanged11 tested
requester leaves are byte-identical to101's frozen component RTL, but no old
whole-native executable/result is substituted for this changed active graph.

`provider/derive_zero_provider.py` adds a PRIVATE future4095 context alongside
511/1023/2047, without a new user WQE ABI or any payload-copy/direct-BAR path.
[Provider001](../results/2026-10-18/rocev2-rnic-zero-provider-001.json) PASSES
the actual installed public libibverbs/serializer/provider in four exact
contexts, each<0.018s, ASan/UBSan. All prior CAS/FADD/full64 operands/MR15/
QP6,14/bad-second-WR/WC cases remain. New4095 runs six zero operations
(WRITE/READ/SEND/SEND_IMM/WRITE_IMM/RECV), both num_sge0 with unused pointer1
and one zero SGE with unused VA/key all-ones. Actual standard command bytes,
Immediate/remote fields,24 posts including exact bad-WR errors, and12 empty
WCs are checked. ONLY syscall replies are modeled; kernel/native completion
or physical zero reception is not proved and no provider is installed.

[Diagnostics102](../results/2026-10-18/rocev2-rnic-zero-native-diagnostics-002.json)
binds preserved model/binary/source preimages and debugger evidence, including
the malformed-short-packet fixture correction; no original validator was
weakened to encode an invalid packet. Incoming zero responder/RQ/native API
coupling, large/multi-SGE, Linux/physical operation, original timing/CDC and
all11 goal requirements remain. No hardware/install/load/network/BIOS/fan/
reboot/flash or automatic Git publication occurs.

## Zero requester native integration candidate (101, runtime pending)

`fpga/derive_zero_native.py` extends the SAME29-module Atomic-access graph,
selecting actual `rocev2_native_zero_request_top` rather than adding another
HLS/MR/PTE/PSN/MSN domain. Canonical zero WRITE/READ/SEND/Immediate owners
keep all748 bits through SQ408, response/lifetime/MAC and CQ; Atomic stays
8 bytes and posted zero RECV is STILL refused. The PRIVATE RNC4095 cohort
is not an installable/qualified complete zero RNIC or a default selection.

Zero admission validates the actual fetched descriptor, context, sequence,
epoch and opcode, but makes NO MR query and grants no data address. The
executor cannot issue any zero command/data/status transaction. A no-data
WRITE/SEND memory event only hands off the genuine owner; READ additionally
waits for the actual identical protected response token. The result-pad
staging lease can end without payload only AFTER that real token, while
the actual executor/HLS/wire/CQ owners independently retain the operation.
No fabricated backend status, fake HLS receipt, quiet-based WR completion,
global drain override, or local key/address/offset on zero work is allowed.

[Complete elaboration002](../results/2026-10-18/rocev2-rnic-zero-native-elaboration-002.json)
PASSES2.92s: real generated zero HLS, no port-width warnings, one native
requester/PSN/MSN/MR/PTE/fetch domain, full requester/receive ABIs unchanged,
and both original global HLS drain inputs remain0. [Staging002](../results/2026-10-18/rocev2-rnic-zero-native-staging-002.json)
PASSES14 methods/49 four-state cases, including all previous Atomic staging
cases, five exact zero SQs and five actual Ethernet-framer/lifetime cases.
The zero cases withhold MAC completion for1100 cycles and still require the
full816-bit HLS receipt and actual CQ commit. HLS/memory/protected-response/
physical MAC pins/CQ endpoints in these component tests remain MODELS.
These are not generated-HLS/full-native zero runtime or Linux evidence.

`tests/test_zero_native_leaves.py` separately runs actual admission/MR,
executor, RX integrity/response-token and CQ tests, including prior Atomic
regressions. [Fresh002](../results/2026-10-18/rocev2-rnic-zero-native-leaves-002.json)
PASSES39 methods/155 four-state cases in361.98s total, each simulation
bounded30s. Zero ACK/AETH frames traverse actual integrity and protected
token replay; malformed nonempty/wrong-class/negative AETH cannot retire
zero READ. The first001 is a preserved failed fixture run, not a pass.
`zero_native_fixture.py` and
`probe_zero_native_full.py` prepare a fresh whole-native13-case executable:
all eight099 regressions and five actual zero requester/replay/MAC/CQ cases.
Compilation/runtime are IN PROGRESS, NOT successful evidence yet. Expected
zero data DMA/MR effects are independently zero; the actual coherent SQ128
fetch is still a genuine PCIe read, and every host/sentinel byte must remain
unchanged. SEND0 additionally requires real MAC minimum padding/FCS.

See [diagnostics101](../results/2026-10-18/rocev2-rnic-zero-native-diagnostics-001.json)
for preserved initial source-key/shared-VA/test-template/fixture-anchor
failures. No old source/result is overwritten or relabeled. Incoming zero
responder/RQ, matched4095 provider, large/multi-SGE, actual Linux/hardware,
original timing/CDC and all11 original goal requirements still remain.
No install/load/programming/network/BIOS/fan/reboot/flash or automatic push.

## Zero-length requester/source extension (100, native integration remains)

`hls/zero_request_transport.py` extends the SAME full Atomic/Immediate core,
not an independent transport. Five normal zero-length requester operations
(WRITE, READ, SEND, SEND_IMM, WRITE_IMM) issue real packets, retain full owners
and actual stored replay entries, and retire only through actual ACK/parser,
pointer/pool, timer and common-state consumers. Neither fresh nor replayed
zero work emits a data-memory command. Header-only SEND uses an internal EOF
marker, never a fake memory-data transaction. A zero READ consumes one PSN
and its ACTUAL four-byte AETH response through the guarded real RAW consumer;
there is no zero-length memory command, fabricated payload receipt or assumed
quiet completion. Malformed zero response framing quarantines the owner.

The canonical zero descriptor has no local address/key/offset or operands.
Remote READ/WRITE VA/rkey remain exact wire fields but are not dereferenced
for zero bytes, consistent with [Linux RXE's C9-88 handling](https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/+/5b10ff013e8a57f8845615ac2cc37edf7f6eef05/drivers/infiniband/sw/rxe/rxe_resp.c).
Atomic STILL requires an8-byte result. This is a new checked cohort, not a
change to default/099 proof inputs or an installed firmware feature.

[Requester C++002](../results/2026-10-18/rocev2-rnic-zero-request-csim-002.json)
PASSES27.50s compilation/0.92s execution: all nine prior mixed requester
cases/four Atomic replays plus five zero requests/five actual stored replays,
PSN wrap, exact byte oracles, seven canonical/Atomic/response negatives,
withheld actual header/timer/state consumers, and nonzero READ after zero on
the SAME domain. [Compatibility001](../results/2026-10-18/rocev2-rnic-zero-request-compat-001.json)
PASSES21.65s compilation/0.89s runtime with previous Immediate TX/RX consumers
and the actual owned Atomic/MR/paged-memory RTL service. Peer, connection,
host/physical memory endpoints remain models. No zero native MAC/CQ proof.

[Fresh HLS001](../results/2026-10-18/rocev2-rnic-zero-request-synth-001.json)
PASSES318.05s code generation: `rocev2_native_zero_request_top`, unchanged
request owner748/SQ408/done816 and receive/service ABIs. The independently
tested source is frozen before synthesis. Actual port widths and original
8QP/2000-entry capacity are checked. Resources are63,274LUT/86,265FF/
189BRAM18/0DSP. Estimated13.568ns STILL misses the original4ns/default1.08ns
constraints; no timing/CDC gate is relaxed. Generated RTL zero execution and
whole native integration are NOT tested by successful synthesis.

`kernel/wqe_zero.c`, `verbs_zero_wqe.c` and `derive_zero_kernel.py` add a
PRIVATE future RNC4095/bit2048 source cohort over099. Exact Atomic128 geometry
must bind before zero posting is enabled; old1023/2047 refuse zero work.
Actual num_sge0/one zero-length SGE adapters canonicalize unused local memory
fields, including invalid unused pointers/keys, without dereferencing them.
The actual SQ/RQ shadow can retain a zero work slot with NO MR reference;
full128-byte saved-WR/operand/offset/proof/CQ comparison and actual queue
ownership remain mandatory before WC publication. Zero RQ completions use
the distinct actual RQC cookie, not the SQ cookie. Empty WC byte_len is not
confused with a missing work/event. Full-CQ backpressure and bad offset
retain the genuine queue owner; no timeout or fake unpin/cancellation proof.

[Running-header build001](../results/2026-10-18/rocev2-rnic-zero-kernel-build-001.json)
PASSES9.19s/GCC13/W=1 with both complete modules linked. [Post002](../results/2026-10-18/rocev2-rnic-zero-kernel-post-002.json)
PASSES47 fresh ASan/UBSan cases: ten zero SQ/RQ/CQ/no-MR/legacy-denial cases
plus all37 previous cases. These are actual C bodies in USERSPACE with
explicit Linux/pin/coherent-DMA/MMIO/completion models, not Linux runtime
or a live kernel/HLS/native link. [Codec001](../results/2026-10-18/rocev2-rnic-zero-wqe-001.json)
PASSES11 UBSan methods including all seven prior Atomic methods and
independent full128-byte zero/alias/null/padding/local-authority oracles.

This does NOT yet implement/qualify the complete native zero admission,
executor/response/lifetime/CQ path, zero incoming responder/RQ semantics,
matched4095 user provider, physical Linux operation or original timing.
Large/multi-SGE work and all11 full-goal requirements remain. Default and
generated device Atomic capability stay NONE; no module/provider is loaded,
installed or programmed. See [preserved diagnostics](../results/2026-10-18/rocev2-rnic-zero-diagnostics-001.json)
for the genuine replay ACK-request fix and rejected wrong-cookie fixture.
One completed719MiB compiler cache was losslessly compressed, verified,
moved to RAM and symlinked, retaining a persistent archive and all182 files;
the original1500MiB synthesis guard is unchanged. No source/evidence deletion,
hardware/network/BIOS/fan/reboot/flash or automatic Git write occurs.

## Per-QP AND MR Atomic receive authority (099)

`fpga/derive_atomic_access_native.py` generates29 checked private module
replacements. NEW RNC feature1024/full2047 distinguishes this cohort from
the earlier Atomic128 graph. The actual privileged21-word controller saves
QP access with its accepted command: live READ/WRITE6 or READ/WRITE/Atomic14,
TX-only0 and inaccessible PD0 tombstone0. Noncanonical/unknown QP access
cannot become a route. The real SQC cookie/epoch/PD binding saves access
ONLY at the drained actual configuration handshake; TX-only preserves it.

General trusted RX admission is NOT gated by the Atomic bit: a QP with
access6 must still receive normal WRITE/READ and requester responses.
All four access bits extend the real raw-RX immutable snapshot to356 bits,
captured even at FIRST OFFER before ready. No lower context field changes.
The actual Atomic executor captures this saved access with the accepted
owned request, not a live software/current-head lookup. After actual identity
and shape checks, anything other than canonical14 returns RemoteAccess
NAK0x62 BEFORE replay, memory lock or MR query. Allowed QPs still require
the SAME actual MR op4 Atomic permission before any paged-memory RMW.
There is no synthetic successful MR response, additional MR/PSN namespace,
global drain tie-high or HLS512/392/144/224 ABI change.

[Binding001](../results/2026-10-18/rocev2-rnic-atomic-access-binding-001.json)
PASSES11 methods/25 four-state cases against actual SQC/mailbox/fetch owner
arrays: all prior ownership/epoch/lease checks, access6 general admission,
accepted-only permission snapshot, canonical/unknown rejection, TX preservation
and tombstone revocation. Downstream lease/network/DMA endpoints are modeled.
[RX refs001](../results/2026-10-18/rocev2-rnic-atomic-access-refs-001.json)
PASSES9 methods/16 four-state cases: all six prior reference/accounting/fault
methods plus permission first-offer capture, RW-only admission, live-reference
permission-change quarantine and unknown denial. Checker/binding/network
endpoints are modeled. [Responder001](../results/2026-10-18/rocev2-rnic-atomic-access-responder-001.json)
PASSES19 actual MR/exclusive/paged-memory RTL cases, each<0.203s: all14 prior
RMW/replay/failure cases plus QP denied/unknown, immutable captured permission
in both directions, and QP denial BEFORE cached replay. This component uses
the original private PSN/MSN mode and modeled trusted/physical boundaries,
not actual native HLS or hardware execution.

`kernel/derive_atomic_access.py` adds a matched PRIVATE source cohort over097.
RNC2047 must negotiate exact SQC13/RQC15/CQC15 and128/748/0xa0 geometry
before enabling standard `IB_ACCESS_REMOTE_ATOMIC` MR/QP registration.
The real QP route retains access, actual privileged QP snapshots carry6/14,
TX-only carries0 without replacing the saved RX owner, and drained teardown
carries PD0/access0. Old1023 still refuses remote-Atomic MR and QP flags.
Local-write pins remain necessary for remote Atomic MR registration.
[Running-header build001](../results/2026-10-18/rocev2-rnic-atomic-access-kernel-build-001.json)
PASSES8.84s GCC13/W=1 with both complete modules linked, never installed or
loaded. [Callback post002](../results/2026-10-18/rocev2-rnic-atomic-access-kernel-post-002.json)
PASSES37 ASan/UBSan cases, each<0.017s: eight new access/canonical/lifetime
cases plus all29 prior Atomic/geometry/legacy cases. Actual standard C bodies
and CSR transports execute in USERSPACE; Linux/pins/DMA/MMIO/completion
remain explicit models, not callbacks executing inside Linux.

`provider/derive_atomic_access.py` produces a private provider accepting
2047 as well as511/1023; generic uverbs remains unchanged, with no128-byte
user ABI. [Provider002](../results/2026-10-18/rocev2-rnic-atomic-access-provider-002.json)
PASSES actual public libibverbs/installed serializer/checked provider with
three EXACT511/1023/2047 contexts, each<0.019s. New2047 checks MR access15
and both QP INIT access14/6 in standard serialized commands, alongside all
full64 Atomic operands/bad-WR/WC checks. Only fake-fd kernel replies are
modeled. The default provider is unchanged and nothing is installed.

[Complete elaboration001](../results/2026-10-18/rocev2-rnic-atomic-access-native-elaboration-001.json)
PASSES2.63s with no port-width warnings and one actual native requester
HLS/PSN/MSN/MR/PTE domain. [Fresh whole-native002](../results/2026-10-18/rocev2-rnic-atomic-access-native-full-002.json)
PASSES465.97s new compilation, then eight actual TWO-STATE RTL cases:
CAS18.85s, FADD18.80s, READ18.80s, SEND_IMM19.00s, mixed responder/WRITE18.75s,
CAS with no incoming Atomic permission18.90s, QP denial15.44s and MR denial
15.59s. All existing complete-native requester/result/replay/MAC/CQ and mixed
responder regressions run fresh against this SAME selected graph; no older
result/executable is substituted. Atomic request/reply uses actual MAC RTL;
ordinary requester MAC pins remain modeled, as in096.

Both denial cases FIRST complete a normal WRITE, then accept a real incoming
FADD without posting any fake WQE/RQ/CQ. The QP-denied path issues ZERO
Atomic MR queries; the permitted-QP/denied-MR path issues exactly one actual
MR query. Neither issues Atomic memory commands or modifies the Atomic
target/neighbor bytes. The only host DMA write and readback fence belong to
the preceding normal WRITE. Independent whole Ethernet/IP/UDP/BTH/AETH/ICRC
and actual XGMII/FCS/SFD/CDC oracles check normal ACK then RemoteAccess NAK62.
The actual owned HLS/core/MAC retirement preserves EPSN/MSN on that NAK and
retires exactly once. The separate CAS/access6 case proves incoming Atomic
permission is not incorrectly required for outgoing CAS or its AtomicACK
response/result/CQ. No post-NAK general-QP recovery/RC-wide error behavior is
claimed from these two denial cases. Physical host/root/peer/PHY/PTP remain
models; no live Linux or hardware execution is implied.

The original/default/096--098 proof inputs are untouched. Both default and
generated device code still advertise `IB_ATOMIC_NONE`. The tests above are
not a live syscall/kernel/RTL/PCIe coupling, physical atomicity, complete
RC-wide error/recovery behavior, Linux pin/unpin or original timing/CDC
qualification. All11 original requirements remain; no hardware/network/BIOS/
fan/reboot/flash or automatic publication action occurs.
Exact initial derivation/fixture/compile failures and preimages, including
provider001's ambiguous inherited profile label, are preserved in
[diagnostics001](../results/2026-10-18/rocev2-rnic-atomic-access-diagnostics-001.json).
No failed report is overwritten or reclassified and no successful result is
substituted for a fresh changed-source test.

## Public provider transport and native/kernel SQ-CQ compatibility (098)

Inspection of the ACTUAL existing provider and pinned rdma-core50 serializer
shows no new user-visible128-byte protocol is needed: `as02.c` already uses
standard `ibv_cmd_post_send`. The128-byte hardware descriptor stays INSIDE
the matched kernel queue path. [Provider002](../results/2026-10-18/rocev2-rnic-atomic-provider-002.json)
PASSES real public `ibv_post_send`/`ibv_poll_cq`, unchanged provider and actual
installed libibverbs under ASan/UBSan, with pinned PABI34 headers. Both511
and1023 context checks run fresh in<0.017s each. Six serialized CAS/FADD
submissions per context check zero/high-bit/all-one64-bit compare/add/swap,
full remote VA/rkey/result SGE, exact second bad-WR pointer, and Atomic WC
metadata. ONLY fake-fd ioctl/write replies model the kernel; no real NIC is
opened, no result DMA is modeled as a provider success and no capability is
advertised (`IBV_ATOMIC_NONE` remains). The legacy kernel still refuses
Atomic; generic serialization is not permission or an installed backend.

Provider001 failed compilation after reusing the original test main under
a different function name: its implicit C main return0 no longer applied.
The generated private fixture now has an explicit return0. Production
provider/original fixture, `-Werror`, sanitizers and deadlines are unchanged.
The failed report/log/private copy and exact launcher preimage are preserved.

[Kernel/native CQ001](../results/2026-10-18/rocev2-rnic-atomic128-kernel-native-cq-001.json)
PASSES12 fresh ASan/UBSan cases after6.11s compilation. Actual097 standard
post_send/SQ/MR/CQ bodies reproduce ALL128 coherent descriptor bytes from
the096 complete-native CAS/FADD/READ/SEND_IMM inputs. They consume each
UNEDITED35-word actual RTL-produced CQ snapshot, including cookie/epoch/
PD/QPN, legacy padding, independent notification and both full operands.
The real CQ/WR comparison publishes the appropriate WC and releases exactly
the corresponding work reference; a second poll does not duplicate it.
Eight explicitly labeled operand/padding MUTATIONS instead retain owners,
publish nothing and do not ACK. Those altered copies are not represented
as unedited native evidence. The complete096 sources/artifacts/RAM executable
are verified before/after, not rerun or relabeled as a new native test.

This closes the prior ABI-data compatibility gap between the096 RTL and097
kernel model, NOT a live syscall/kernel/RTL/PCIe link. Linux primitives,
pins/coherent DMA/MMIO, peer and teardown remain models. No module/provider
is installed and no callbacks execute inside Linux. Actual permission
propagation, standard/live physical operation and original timing/CDC remain.
In particular the current MR contract understands remote-Atomic bit8, but
verbs registration still permits only7 and QP INIT only remote READ/WRITE6.
The privileged controller retains a four-bit access field, yet the current
Atomic QP binding has no saved per-QP Atomic permission. The next feature
must propagate and retain that authority with the accepted QP/SQC identity,
and require BOTH QP and MR permission, before widening the standard checks.
Merely accepting another flag or advertising Atomic is not sufficient.

## Matched kernel requester/SQ/CQ source cohort (097)

`kernel/derive_atomic128.py` now generates a checked, PRIVATE full kernel
cohort without rewriting the default64-byte files or096 proof inputs.
`atomic_profile.h` defines negotiated profile3: the existing Immediate header
plus Atomic operands. Actual SQ/RQC MMIO adapters accept exact features13/15
ONLY with descriptor-size128. Actual CQ feature15 additionally requires
owner-size748 and operand-base0xa0. The real transport binder re-reads the
entire RNC1023/SQC13/RQC15/CQC15 tuple and geometry under the existing locks
BEFORE creating any queue. Mixed formats/changed geometry are not adopted.

The SAME actual SQ pool allocates BOTH coherent rings with128-byte stride,
alignment and extent; no second MR or queue namespace is introduced.
`verbs_atomic_wqe.c` maps genuine `ib_atomic_wr` CAS/FADD operands explicitly
to the C128 codec. Signal-all handling copies the correctly typed Atomic WR,
not a base SEND or an `ib_rdma_wr` cast. Actual standard post_send retains
the two operands in its shadow, acquires local RESULT-write MR permission,
executes `dma_wmb()` and uses the existing actual producer transport. Normal
READ/WRITE/SEND/Immediate/RECV use zero-extended records in this format.

Actual CQ IO reads complete operands separately from legacy context padding
and receive notification. Full128-byte re-encoding compares the saved WR,
both operands and decoded owner before publishing `IB_WC_COMP_SWAP` or
`IB_WC_FETCH_ADD` with byte_len8 and releasing a work reference. Proof-only
legacy completion cannot release profile3 work. CQ backpressure, changed
operands and ambiguous ACK retain the corresponding owners/metadata rather
than rewinding a posted queue or delivering a second WC.

[Kernel build001](../results/2026-10-18/rocev2-rnic-atomic128-kernel-build-001.json)
PASSES8.49s against the ACTUAL running6.17.0-1033-oem headers with GCC13/W=1.
Both complete modules link the actual adapters, standard callbacks, SQ/MR/CQ
and graph/publication entry points. This is compile/link ONLY: neither
module is installed/loaded and no callback is executed in Linux.
[Post002](../results/2026-10-18/rocev2-rnic-atomic128-kernel-post-002.json)
PASSES29 fresh ASan/UBSan cases after6.20s compilation, each<0.015s:
CAS/FADD exact operands, signal-all and exact bad-WR tail, dual128 rings,
LOCAL_WRITE denial, malformed request rejection, CQ-full ring reuse,
operand-mismatch quarantine, forbidden proof-only release, ambiguous ACK
without duplicate delivery, normal READ/SEND_IMM, legacy Atomic refusal,
four geometry mismatches before queues and ALL15 previous verbs cases.
All Linux primitives/pins/coherent DMA/MMIO/peer completion are EXPLICIT
USERSPACE MODELS; these are real C bodies, not actual Linux/RTL execution.
The097 modeled callback graph and096 actual RTL graph remain separate.

Diagnostic post001 passed its first three cases, then LeakSanitizer found
the caller's56-byte MR wrapper unreachable at process exit in an intentionally
quarantined case.002 keeps that real caller-owned wrapper in an explicit
test-global quarantine root. No driver body, sanitizer option, deadline,
reference-release check or cleanup proof was weakened. Failed binary/log/
report/exact body preimage remain preserved;002 freshly runs all29 cases.

The new cohort is NOT selected by the default Makefile or an installed
provider. `IB_ATOMIC_NONE` remains in BOTH default and generated device code.
User-provider128 posting, actual Linux/RTL coupling and runtime pin/unpin,
remote-Atomic MR/QP receive-permission negotiation, physical operation and
all original timing/CDC requirements remain. Existing reg_user_mr and QP
receive-access checks still refuse standard remote-Atomic permission; the
requester source support must not be advertised as full RNIC Atomic support.
No hardware/network/BIOS/fan/reboot or automatic push occurs.

## Full native requester execution and queue ABI (096)

`derive_atomic128_native.py` now generates24 matched native replacements.
The first checked SQC-anchor mismatch is fixed against the actual source;
its exact preimage remains preserved. The selected graph connects the actual
128-byte fetch/admission,748-bit requester owner/408-bit SQ/816-bit core
receipt, generated requester HLS, protected result executor, MAC/lifetime
and CQ parents. Receive owners remain620, with explicit receive-only slices;
the owned Atomic responder service ABI and original protected source stay.

[Complete elaboration003](../results/2026-10-18/rocev2-rnic-atomic128-native-elaboration-003.json)
PASSES2.61s, with NO port truncation/padding warnings. Actual elaborated
instances include ONE native requester HLS/PSN/MSN/RX domain, ONE MR table,
ONE PTE table and the complete real response/executor/replay/MAC/CQ path.
The unchanged legacy HLS is ALSO present, not mistaken for a duplicated
native domain. SQ/RQ share ONE actual fetch/DMA engine through the existing
arbiter, while retaining their separate admission/ownership paths.
Diagnostic001 incorrectly expected two fetch engines;002 counted legacy
and native HLS instance names together. Both failed reports/verifiers are
preserved;003 freshly elaborates the same RTL with explicit native types.
This is COMPILE-ONLY, not actual requester result DMA/CQ execution.

Both SQC/RQC use128-byte stride/alignment and a read-only descriptor-size
register at0x20, with exact feature values13/15. CQ feature15 retains the
lower620-bit context window at0x40..0x8c with its original zero padding,
separate receive notification0x90, owner-size748 at0x94, extension base0xa0
at0x98, and complete compare/swap-add words at0xa0..0xac. Existing exact-
feature kernel negotiators correctly refuse these NEW unmatched formats;
no old64-byte ring allocation/posting is silently used for this candidate.
[SQC001](../results/2026-10-18/rocev2-rnic-atomic128-sqc-001.json)
PASSES9 methods/36 four-state cases with actual AXI/SQC/two-beat fetch:
allocation, ring/sequence bounds, ownership, guards, faults and retirement.
Backend/guards remain MODELS. [CQ001](../results/2026-10-18/rocev2-rnic-atomic128-cq-001.json)
PASSES2 methods/6 cases: four successive CAS/FADD/READ/RECV events preserve
complete operands, original context padding and separate notification;
five malformed-owner runs cannot publish. Upstream lifetime owners remain
MODELS, not new host visibility/CQ completion evidence.

`probe_atomic128_native_full.py` now PASSES a FRESH full executable in
[full-native001](../results/2026-10-18/rocev2-rnic-atomic128-native-full-001.json):
447.86s feature compilation, then CAS18.80s, FADD19.00s, READ18.90s,
SEND_IMM18.85s and mixed Atomic responder/WRITE18.65s. Its complete testbench
also elaborates without port-width mismatches. This is actual TWO-STATE
compiled RTL, not a cached result or behavioral HLS. Physical host/root/peer/
PHY/PTP inputs remain models; ordinary READ/SEND_IMM retain the prior
physical-MAC-pin model, while Atomic requester/responder use real MAC RTL.

Both CAS/FADD traverse actual C128-byte encoding, coherent SQ fetch, ONE
real MR/PTE domain, guarded748-bit ownership, generated HLS and real response
integrity/peer/issued-PSN protection. The AtomicACK old value is written as
LE8 bytes through actual protected result DMA, split3+5 across two sealed
DMA64 pages, with two posted write TLPs and one readback fence. The tested
TX-sequence and readback delays cannot be replaced by quiet/count models.
No Atomic operand-source DMA occurs: the only two read TLPs are SQ fetch
and result-write readback. Every host result/sentinel/ring byte is checked.

The native replay path sends two byte-identical72-byte IP Atomic requests
under fresh tags0x2001/0x2002. Independent oracles check ALL operands/wire
bytes, IPv4/ICRC and actual XGMII preamble/FCS/SFD/CDC. Withholding the second
REAL MAC receipt for1100 core cycles retains the complete owner/HLS receipt
and prevents CQ publication. Actual result memory status, MAC/EOF/tail,
816-bit producer receipt, CQ commit, shared-core retirement and host CQ ACK
join in the real parent graph; neither original global drain is tied high.
The independent host CQ snapshot checks all lower620 bits/padding, separate
notification and all128 operand bits. Existing READ/SEND_IMM, duplicate
Atomic responder suppression and mixed normal WRITE continue to pass on the
SAME selected graph. This is still modeled host memory, NOT Linux pin/unpin.

Each runtime stays below30s and feature compilation below1200s. Standard
kernel/provider128 negotiation/posting, physical execution and original
timing/CDC gates remain incomplete; `IB_ATOMIC_NONE` and both original
global zero drains are unchanged. No driver is installed/loaded and no
hardware, network, BIOS, fan, clock or reboot action is taken.

## Generated requester execution and native proof leaves (095)

[Generated requester003](../results/2026-10-18/rocev2-rnic-atomic-request-generated-003.json)
PASSES the SAME full synthesized HLS/integrity bridge in1.77s after502.94s
feature compilation. Two successive CAS/FADD requests produce actual72-byte
IPv4/UDP/AtomicETH/ICRC packets, two exact LE8-byte result commands/data offers
and two816-bit core receipts, including PSN wrap. Independent Python checks
all wire bytes/operands and checksum/ICRC; RTL checks full owner/command/data
and retained offers under backpressure. No Atomic source-read DMA occurs.
This is TWO-STATE compiled RTL, NOT the earlier C++ producer model.

QP/connection/owner/SQ/peer/physical-memory boundaries remain models. The
HLS receipt is producer/bookkeeping evidence, NOT protected host-DMA memory
visibility, safe unpin or a WR/CQ completion. In particular an exported core
receipt can be offered while its result data is buffered; native parents
must independently join actual result-DMA and memory lifetime proofs.
Diagnostic001's four-state run failed a sink fixture that demanded command
and data offers simultaneously BEFORE accepting the command.002 orders the
sink correctly but reaches the30s Icarus runtime cap.003 uses faster Verilator
without changing HLS RTL or the30s cap. Failed reports, frozen binaries,
fixtures and exact source preimages remain preserved; no result is relabeled.

New `derive_atomic128_response.py` extends the ACTUAL native response guard:
full748-bit immutable owner, real whole-packet integrity, trusted peer/QPN/
issued PSN, ACK syndrome TYPE and exact56-byte AtomicACK/no-pad shape. A real
result-placement token must be accepted under a held downstream queue guard
BEFORE ANY HLS beat. Both operands/keys/PD/ranges stay bound to that owner;
ordinary READ/WRITE/SEND/Immediate policies remain. Control NAK can retain
the same owner without inventing result/positive completion authority.
[Response002](../results/2026-10-18/rocev2-rnic-atomic-request-response-002.json)
PASSES8 methods/32 four-state cases, each<10s.001's test incorrectly awaited
a later parser rejection for a bad UDP port already dropped by the real
earlier integrity checker.002 verifies that actual earlier drop separately;
guard RTL is unchanged and all eight methods are freshly rerun.

`derive_atomic128_executor.py` extends the SAME protected memory executor:
CAS/FADD are8-byte local RESULT writes, never operand-source reads. Both the
full748-bit placement token and exact96 post-origin-router command must match
before issuing saved full MR key/offset/length/tag authority. Actual data EOF,
tagged backend status and guarded downstream handoff remain necessary; DMA
errors quarantine ownership. [Executor002](../results/2026-10-18/rocev2-rnic-atomic-request-executor-002.json)
PASSES7 methods/53 four-state cases, including prior normal/Immediate paths.

`derive_atomic128_lifetime.py` extends native lifetime/MAC/replay/result-pad
leaves. The TX observer captures FIVE128-bit header words: Atomic compare's
wire bytes60..67 do not fit in the previous64-byte window. It checks EVERY
swap/add and compare bit, the actual issued PSN/peer and exact72-byte frame.
Atomic ACK-kind bookkeeping is READ-like; the816-bit HLS receipt must match
the entire748-bit owner, PSN/next/opcode/error. Actual Ethernet framer/tag/
accepted EOF/tail proofs still join independent memory/RX/ACK/core/CQ proofs,
never a constant global drain. [Lifetime001](../results/2026-10-18/rocev2-rnic-atomic-request-lifetime-001.json)
PASSES3 methods/16 four-state cases; actual MAC output bytes/tags/tail are
checked. Physical completion pins and memory/RX/ACK/core/CQ endpoints remain
models. The retained replay-enabled family is elaborated, NOT runtime-tested.
[Result-pad001](../results/2026-10-18/rocev2-rnic-atomic-request-result-pad-001.json)
PASSES3 methods/9 cases: CAS/FADD8-byte result and ordinary READ65-byte padding,
canonical extended ownership and held offers after late guard loss.

These are necessary native LEAVES, not a completed matched native requester
graph. Actual128-byte SQC/driver/provider negotiation, complete parent routing
and owner widths, SAME MR/PTE/sealed-page result DMA, actual CQ/MAC retirement
and short whole-native runtime remain. The earlier128-byte PCIe/MR/staging and
new generated HLS execution are still separate graphs. No hardware/driver/
BIOS/network/reboot or automatic publication occurs. Original13.568ns HLS
estimate still misses4ns/1.08ns; full-board/CDC gates and `IB_ATOMIC_NONE` stay.

## Same-core Atomic requester transport (094)

`hls/atomic_request_transport.py` adds opt-in CAS/FADD requester execution to
the SAME complete owned Atomic/Immediate transport. It preserves the existing
PSN/MSN tables, real retransmission entries/pointer pool, timers and retirement
join. Both64-bit operands survive actual stored-entry replay and its readback
receipt. SQ408 explicitly retains the original seven zero padding bits BEFORE
the appended operands; receive owners remain620, independent of requester748.
The requester completion is816 bits, retaining the complete immutable owner.

[Requester C++001](../results/2026-10-18/rocev2-rnic-atomic-request-HLS-001.json)
PASSES0.47s after a22.78s complete-top compile. Nine fresh CAS/FADD/WRITE/READ/
SEND/Immediate operations and four genuine stored-record replays check exact
wire bytes and common PSN wrap. Atomic emits28-byte AtomicETH with no source
memory read. Actual BTH/EXH parsing consumes AtomicACK's AETH4+oldvalue8;
the existing memory-data consumer emits an8-byte LE result and only THEN its
real result-consumed receipt. Pausing that consumer, timer bookkeeping and
the same common-state readback independently prevents successful completion.
Mismatched operands/padding, response class, framing, syndrome and UDP length
cannot fabricate a result or successful completion. Peer/connection/physical
memory endpoints remain MODELS; the raw command's legacy48-bit address still
requires native binding to the full64-bit authorized MR owner/sealed pages.

[Same-core compatibility003](../results/2026-10-18/rocev2-rnic-atomic-request-compat-003.json)
PASSES0.88s after21.49s compilation: prior Immediate TX8/receive8 operations,
normal SEND/WRITE, and nine owned Atomic responder jobs using the ACTUAL
protected Atomic/MR/paged-memory RTL service. It retains withheld-service,
MSN/PSN-readback, replay/drop and two-QP assertions. Diagnostic001/002 retain
a launcher formatting failure: C++'s `0x` prefix was sent verbatim to Verilog
`%h`. Canonical128-hex-digit input fixes the launcher; service RTL, deadlines
and all actual assertions are unchanged. Both failed launchers/logs/binaries
and exact preimages remain locally preserved;003 is a fresh complete run.

Atomic ACK accepts only the ACK syndrome TYPE, not RNR/NAK/reserved types;
its low credit bits need not equal0x1f. BE wire old-value decoding and local
result-write semantics follow the primary Linux RXE
[header definitions](https://github.com/torvalds/linux/blob/master/drivers/infiniband/sw/rxe/rxe_hdr.h)
and [Atomic completion consumer](https://github.com/torvalds/linux/blob/master/drivers/infiniband/sw/rxe/rxe_comp.c).

`build_native_atomic_request.py` freezes the exact tested complete source and
requires both requester and compatibility evidence before HLS synthesis.
Original4ns/default1.08ns uncertainty,8QP/2000entries and1500MiB guard remain.
[Fresh synthesis001](../results/2026-10-18/rocev2-rnic-atomic-request-synth-001.json)
completes in318.01s with61,986LUT/85,982FF/189BRAM18/0DSP. Actual generated
ports are SQ408, requester owner752 (748+4zero AXIS padding), done816;
receive680/done752 and Atomic service512/reply392/owner144/done224 stay exact.
Estimated13.568ns STILL FAILS the original4ns/1.08ns requirement: generation
success is not timing closure or a deployable board image. Capacities are
not reduced and no physical timing/CDC gate is waived.

`derive_atomic_request_bridge.py` only
matches the new SQ/requester geometry while preserving actual integrity and
the existing receive/owned-service ABIs.
[Actual HLS+bridge elaboration002](../results/2026-10-18/rocev2-rnic-atomic-request-elaboration-002.json)
PASSES1.12s with ONE actual HLS/state-table/MSN/RX/Atomic-commit domain, not
an unreachable default-disabled generate branch. Diagnostic001 omitted the
existing `axis_register.v` compilation dependency; adding that real dependency
requires no RTL edits. This is compile-only, not packet execution or a native
profile. Protected result DMA, actual executor/MAC/CQ lifetimes,
128-byte SQC/kernel/provider and physical/timing qualification remain open.
Default hardware, `IB_ATOMIC_NONE` and both original zero drains are unchanged.

## Atomic requester MR admission and guarded SQ pipeline (093)

`derive_atomic128_admission.py` adds checked replacements for actual WQE
admission, the SQ-result bridge and owner-before-HLS-SQ staging. Atomic op7/8
requires the REAL local MR validator's LOCAL_WRITE permission for its8-byte
result, not REMOTE_ATOMIC permission or a CPU physical-address shortcut.
Full key/PD/range, trusted queue/sequence/epoch and remote alignment are checked.
All128 descriptor bytes must be known/canonical. Both64-bit operands remain
independent and immutable; denied/failed fetches zero all operand authority.
Normal/Immediate/RECV admission remains supported, including RECV-only refusal
of Atomic TX. The original64-byte modules are unchanged.

New [admission001](../results/2026-10-18/rocev2-rnic-atomic-request-admission-001.json)
PASSES8 methods/23 four-state simulations in1.39s with actual C descriptors,
the actual SQ bridge/frontend and ONE actual MR table. It covers permissions,
keys/PD/ranges, unknown headers/operands/reserved bytes, all15 DMA error codes,
stalls/disable and uncertain response ownership. Raw fetch/consumer endpoints
remain models; this component result alone is not a PCIe or requester proof.

The extended immutable owner is748 bits: existing Immediate620, compare64 at
bits683:620, swap/add64 at747:684. SQ408 keeps the COMPLETE lower280-bit ABI,
including its seven zero padding bits; compare is343:280, swap/add407:344.
CAS/FADD map to wire opcodes0x13/0x14. Actual guarded staging passes5 methods/
13 four-state simulations in0.30s: exact full-width fields, normal/Immediate
compatibility, denied/no-SQ behavior and ownership before SQ, including late
guard loss without retracting an already offered word. HLS/executor are
explicit endpoint models. The future packed C++ `txMeta` must preserve those
seven padding bits BEFORE the appended operands to match this explicit ABI.

The [complete front-end pipeline001](../results/2026-10-18/rocev2-rnic-atomic-request-pipeline-001.json)
and [UR-error pipeline002](../results/2026-10-18/rocev2-rnic-atomic-request-pipeline-002.json)
now connect actual Corundum PCIe/RAM/mux/128-byte SQ fetch -> the SAME actual
MR table -> actual immutable-owner/SQ staging, not separate elaborations.
Positive6 records yield6 real guarded owners/SQ offers in0.38s. The error case
has4 fetched/error owners but ONLY3 SQ offers in0.33s: UR retains trusted
identity while zeroing all data/operand authority, halts its queue and needs
actual parent drain plus a fresh epoch for recovery. Independent Python
checks all128 fetched bytes, every748 owner bit and every408 SQ bit.
Physical host/root/trusted config and downstream executor/HLS sinks remain
models; their staging release is NOT a WR completion/unpin certificate.
There is no test-produced MR reply, DMA descriptor/status/RAM data shortcut
or SQ word. Unchanged old admission/Immediate/owner suites pass23 methods.

This closes the requester FETCH/MR/STAGING portion only. SAME-core HLS Atomic
request/ACK processing, protected BE-to-LE8-byte result placement, retransmit/
common-state retirement, real executor/MAC/CQ and matched128-byte SQC/driver/
provider remain incomplete. Existing native responder003 evidence stays
unchanged. No hardware/default profile/capability/timing/drain gate is changed.

## Full native responder runtime and requester groundwork (092)

The [full native runtime003](../results/2026-10-18/rocev2-rnic-atomic-native-full-003.json)
PASSES three FRESH cases: mixed FADD/duplicate/ordinary WRITE17.51s, ordinary
READ17.75s and SEND_IMM17.80s. The complete shared native graph uses actual
SQC route binding, one owned HLS/MR/PTE domain, exclusive memory arbitration
and the outer Atomic MAC. Mixed execution has no posted WQE/RQ/CQ shortcut.
Two FADD executions, one cached duplicate and one ordinary WRITE produce
three genuine core receipts/automatic Atomic retirements, actual MAC tags
1/2/0x4000/3, five read TLPs (including three visibility fences) and three
write TLPs. All host bytes and neighbors, exact wire/FCS/ICRC, immutable owners
and common EPSN987655/987655/987657 and MSN1/1/3 match independent oracles.
The actual SQC retirement attempt is denied while the Atomic lease is held.

This is OFFLINE simulation, not Linux/physical/timing/interop qualification.
Atomic uses actual XGMII/SFD/FCS/CDC; physical host/root, PHY/peer/PTP input
remain models. Ordinary requester cases retain their explicit MAC-pin model
but still check actual SQ/MR/DMA/replay/core-owner/CQ and full wire output.
All663 source/28 local artifact/one frozen RAM executable hashes match.

Diagnostic002's RTL assertions completed successfully, but the Python oracle
incorrectly expected Atomic ACK syndrome0x1f for the ordinary ACK too. The
immutable selected HLS source explicitly generates ordinary ACK syndrome0.
Only that expected byte was corrected; its exact old verifier is preserved.
003 verifies all prior compiled RTL/bench/executable hashes, enforces that
exact one-line Python-only diff and reruns ALL three cases. It reuses the
unchanged frozen executable, not test results;002 remains a failure record.
Its459.33s compilation is not repeated for a Python-only oracle correction.

Requester groundwork now has a separate `wqe_atomic.h/.c`128-byte codec and
checked `derive_atomic128_fetch.py` SQ/RQ DMA derivative. Bytes0..63 retain
the normal/Immediate header;64..71 are LE compare,72..79 LE swap/add and
80..127 reserved zero. Atomic op7/8 require length8, remote alignment and no
Immediate; FADD compare must zero. Normal operations require a zero extension.
The actual C codec passes7 UBSan methods, including full-width operands,
failure zeroing, overlap and old64-byte API refusal. Unchanged old C/Immediate
codec suites also pass13 methods. No default format or capability changes.

The real Corundum DMA/RAM/mux/PCIe path fetches all128 bytes of CAS/FADD and
normal/Immediate records: positive002 passes6 records/768 bytes in0.35s;
UR-error003 passes4 records/512 bytes in0.31s, including128 zero error bytes,
queue halt, real withheld-parent drain and fresh-epoch recovery. Host/root
and trusted configuration remain models; no CPU payload-copy shortcut or
host write/fence is used. The new four-state controller units002 pass6
methods/9 simulations: both halves plus actual status required, malformed/
unknown framing quarantine, held owners under disable, DMA64 ring limits,
nonwrapping tags and separate same-QPN SQ/RQ contexts. Diagnostic preflights
retain an old79-vs-current87-port fixture check and a test-only SystemVerilog
reserved identifier; current exact interfaces/assertions and RTL are retained.

These are necessary requester components, NOT an integrated Atomic requester.
128-byte SQC/driver negotiation, actual local-MR result admission, immutable
operand propagation into the SAME shared HLS, Atomic request/ACK processing,
replay/result placement and real MAC/CQ/kernel/provider lifetimes remain.
Default hardware, original protected responder, both global zero drains,
`IB_ATOMIC_NONE`, original4ns/1.08ns and full-board qualification gates remain.

## Integrated runtime work after snapshot090 (091 history)

New four-state native RX reference/classifier tests002 PASS9 methods/27
simulations in0.84s. They cover retained first offers during pause/query
unavailability, actual checker EOF/drop accounting (including two releases
and one acquisition together), context replacement protection, finite-count
overflow containment, malformed headers and unchanged normal/Atomic routing
under backpressure/late faults. Adjacent checker/context/endpoints are models;
this is not complete native execution or safe host unpin proof. Diagnostic001
retains a test stimulus-width failure: a seven-hex-digit literal truncated to
the legal QPN2.002 uses an actual out-of-range24-bit QPN; RTL is unchanged.
The failed fixture/binary/log and exact test preimage are retained locally.

`probe_atomic_native_full.py` builds one actual full native graph. It adds
mixed FADD/duplicate/normal WRITE and independent
whole-wire/common-state oracles, alongside the ordinary READ/SEND_IMM cases.
The Atomic case uses actual XGMII/FCS/SFD/receipt CDC; physical host/root,
PHY/peer/PTP input remain models. Runtime outcomes are not inferred from
fixture generation or compilation. Large new frozen binaries
use task-owned RAM without lowering the original fresh-native1GiB guard.

Full-native runtime001 compiled in468.52s and reached actual Atomic native
memory execution, but its first13.44s case FAILED the inherited65-byte
physical-address oracle; it is NOT a passing integrated result. Its frozen
executable/log/bench and exact launcher preimage are retained. The separate
`atomic_native_full_memory_fixture.py` preserves ordinary requester assertions
while adding exact8-byte Atomic/WRITE key/offset/direction, physical-page,
enabled-byte and ordered-fence expectations. Runtime002 is the fresh rebuild
of that fixture, not a relabel of001; its later verifier failure and successful
fresh003 runs are recorded above. No RTL safety condition was relaxed.

## Full native integration candidate (090; publication snapshot)

The opt-in checked `derive_atomic_native.py` / `derive_atomic_native_rx.py`
candidate now connects ordinary and Atomic RX in ONE complete native graph:
accepted raw-frame/context references, post-integrity Atomic dispatch, actual
SQC-backed QP binding, the same owned HLS and MR/PTE tables, normal/Atomic
memory exclusion, ordered MAC reservation and automatic hardware retirement.
The original protected responder and default native image are not replaced.

The [full native elaboration001](../results/2026-10-18/rocev2-rnic-atomic-native-full-elaboration-001.json)
PASSES structural compilation with the actual generated HLS. Module-count
checks verify one shared HLS/QP binding/MR/PTE domain and the real Atomic
execution/MAC components. This is NOT functional simulation, a timing pass,
standard verbs support or hardware validation. Unlike stage089, this candidate
selects Atomic RX, but its behavior is still unverified.

`atomic_native_full_fixture.py` is an in-progress mixed FADD/duplicate/ordinary
WRITE fixture using actual MAC RTL after bootstrap. Python syntax and fixture
generation pass; it has NOT been compiled or simulated in this snapshot, and
there is not yet a full-native functional probe/launcher. Its assertions and
planned cases must not be read as successful test evidence. Atomic requester,
kernel/provider capability, integrated runtime and original full-board timing
qualification remain open. Both global drain constants remain zero and the
driver continues to advertise `IB_ATOMIC_NONE`; no hardware is programmed.

## Native QP authority and common-core integration (089)

`rocev2_atomic_qp_binding.v` binds the SAME accepted privileged RX route to a
read-only query of the actual SQC owner epoch/cookie/PD arrays, not a packet,
CQ/current-head inference or another QP table. The checked
`derive_atomic_owner_lookup.py` adds that query without changing existing
mailbox/owner mutation/CQ/retry interfaces. Full-width aliases/unknowns and
busy/doorbell/fault conditions do not acquire new Atomic admission authority.
An already held lease survives a temporarily unavailable query during a legal
producer update; query validity is not a cancellation/retirement certificate.

Seven four-state methods/13 cases pass against the actual SQC mailbox and
fetch controller/owner arrays: accepted route snapshots, denied aliases/PD,
same QPN recreated with a new epoch (old route remains unauthorized), blocked
retirement/reconfiguration while held, producer update while held, TX-only
preservation/tombstone and deliberate fault containment. Physical DMA, network
configuration source and lease assertion are models, not complete native
Atomic execution or unpin proof. Current evidence is QP-binding002. Diagnostic
001's final generic test assertion rejected an intentionally faulted parent;
the exact pre-fix test is preserved.002 permits that expected parent-fault
status only; other unexpected SQC fatal states still fail. No RTL was relaxed.

The unchanged SQC regression suite also passes on the NEW lookup derivative:
9 methods/36 cases in2.58s, using original assertions and actual CSR/fetch.
The combined Atomic RTL suite passes33 methods/96 internal simulations in9.43s.
These are scoped offline component checks, not the broader legacy RNIC/CI
suite or a standard Linux/host-memory release qualification.

`derive_atomic_native_authority.py` connects that lookup through the actual
native/SQ/network/dual/control hierarchy and accepted route handshake, with
lease guards feeding actual SQ/RQ retirement and MR/configuration protection.
The explicit top lease input still needs actual Atomic packet/core/MAC owners;
it is not a software drain. The complete authority graph and service-only
`derive_atomic_native_bridge.py` both elaborate with real generated HLS.
The authority graph retains one native MR/PTE namespace; the bridge adds no
external MR namespace. These are TWO SEPARATE elaborations, not full
Atomic native datapath proof. Default/rollback sources are unchanged.

The new owned-core native stage selects the actual full owned HLS for ordinary
READ/WRITE/SEND/Immediate, with actual SQC route binding. Atomic packet dispatch,
service/exclusive memory/MAC is still NOT selected; normal protected admission
rejects Atomic opcodes, its Atomic input channels stay inactive, and unexpected
Atomic service/done offers fault. Its actual READ/SEND_IMM runtime composition
001 now PASSES both cases in11.44/11.39s after417.30s of feature-required
compilation (36 byte-identical compiler inputs reused, both cases rerun).
The real owned HLS is selected in the complete native graph, with actual
coherent SQ, same MR/PTE/native DMA/replay and CQ, not a behavioral HLS stub.
The test creates SQC before RX route
open, like the actual kernel verbs path; it does not repeat the unrelated old
unsafe Ethernet re-COMMIT case. All WR/MR/DMA/HLS/MAC/CQ assertions remain.
Both65-byte requests and byte-identical replay match an independent complete
wire/ICRC oracle with fresh native MAC tags0x2001/0x2002. Real HLS request
receipts retain the whole WR owner and next PSN; actual CQ commit succeeds.
Current630source/45artifact hashes match. Physical host/root/MAC pins and
peer remain modeled in this native-stage test (unlike the isolated Atomic
branch's actual XGMII/SFD test). This does NOT select Atomic native packet
execution; real dispatch/MR arbitration/exclusive memory/outer MAC lifetime
and requester/API/physical/timing qualification remain incomplete.

## Ordered MAC reservation before execution (087)

The new checked `derive_atomic_reserved_mac_bridge.py` retains086 unchanged
and replaces its independent owner fanout with
`rocev2_atomic_owner_reservation.v`. An admitted immutable328-bit owner/context
first handshakes with the actual MAC lifetime, and ONLY THEN offers its144-bit
owner to HLS. Neither FIFO readiness nor a quiet period constitutes reservation.
Both offered transfers remain stable under backpressure or late fault; fault
retains the configuration/queue guard, without duplicating a consumed offer.

New post-ICRC packet admission additionally requires actual MAC availability
and a remaining nonwrapping MAC tag. Disabling new admission after a packet's
first accepted beat does not cancel the remaining packet, its MAC reservation
or HLS owner: the packet guard drains its accepted packet and the MAC accepts
already-admitted owners independently of the new-admission enable. This is
not a reset/unpin or tag-reuse mechanism. Default hardware tag width stays13.
The short generated test uses width4 to reach its last tag in15 requests.

Five four-state reservation methods/10 simulations pass; the combined Atomic
suite passes26 methods/83 internal simulations. Endpoints in the reservation
unit are models; actual generated HLS/Atomic/MR/MAC composition is recorded
separately. Full ordinary/Atomic native admission, trusted QP epoch/PD/peer
references, shared normal-memory exclusion, standard API and requester remain
incomplete. Pending input upstream of the packet guard is NOT proof of safe
cancellation or configuration/unpin; real native integration must retain its
own accepted RX/context references. Neither global drain nor Atomic capability
advertisement is enabled. Original4ns/1.08ns and board gates are unchanged.

The current [reserved MAC generated composition002](../results/2026-10-18/rocev2-rnic-atomic-reserved-MAC-generated-002.json)
PASSES all7 cases, each3.17..10.99seconds, after770.27seconds of feature-required
compilation. Actual generated owned HLS, Atomic/MR/PTE/paged DMA/RAM/IP/ICRC,
Ethernet/XGMII/FCS/SFD and receipt CDC remain connected; no test-produced MAC
receipt or test-driven retirement. Every actual MAC reservation precedes its
matching HLS owner delivery, with independent full-byte/FCS/ICRC/common-state
and immutable-owner oracles. Source223/artifact23 SHA audit passes.

Case4 consumes15 real test tags:7 executions,6 cached replays and1 no-packet
drop yield15 consumed-core receipts/automatic retirements,14 Atomic Ethernet
frames and one unrelated native frame. The16th valid post-ICRC packet stays
upstream of admission; no16th owner/service/DMA/retirement occurs. This pending
input is NOT an unpin/configuration certificate. Cases5/6 disable new admission
after the actual first packet beat / while its owner is offered for MAC
reservation, respectively: each admitted request genuinely completes, then
re-enable permits its cached duplicate (2 retirements,1 execution,1 replay).
The other four cases retain positive/drop, MR-denial, failed-fence and corrupt
returned-nonce checks. Hardware default tag width13 and all older evidence
remain unchanged. PHY/PTP input and physical host descriptors/order remain
models; full native/Linux/physical/timing qualification is still incomplete.

## Atomic MAC lifetime and automatic retirement (086)

`rocev2_atomic_mac_tx.v` adds an unposted Atomic packet lifetime, not a fake
receive WQE/CQ. It joins the immutable144-bit packet owner, actual392-bit
service reply,224-bit same-table consumed-core receipt and generated IP
response. This is important for replay: the wire can contain cached OLD MSN
while the consumed-core receipt reports CURRENT common MSN. Packet bytes must
match the real service reply and independently snapshotted peer identity;
fresh advancement/NAK/drop must match actual core flags and readbacks.

The real Ethernet framer and frame arbiter sit OUTSIDE existing native WQE
MAC routing. Atomic uses fresh nonzero low13-bit tags1..8191, disjoint from
legacy0, WQE0x2000 class, responder0x4000, receiveACK0x6000 class and MSB1
host tags. The corresponding actual SFD receipt never enters the inner
native policy. Unknown/stale/duplicate/premature Atomic receipts quarantine
the lease. Positive retirement additionally requires accepted final MAC beat,
framer completion and1024 core cycles AFTER both SFD receipt and final beat.
Drop requires actual no-packet core/service consumption and no offered IP;
it invents neither a MAC receipt nor an RQ. Tags do not wrap, including drops;
exhaustion fails closed. Whole-parent reset is not cancellation/unpin proof.
An already offered frame/retirement stays stable under disable/late fault;
fault still retains its aggregate configuration/queue guard.

`derive_atomic_mac_bridge.py` is a checked new **Atomic-only branch**; it does
not replace normal native admission. It snapshots trusted MAC/IP/peerQPN on
the SAME accepted post-ICRC first beat as the existing QPN/epoch packet guard.
Actual registered AXIS broadcasters carry owner and service response to HLS
and MAC consumers independently under backpressure. The MAC lifetime directly
drives the packet guard's exact retirement; no external test/CPU release.
Existing ordinary Ethernet frames/completions can pass this final mux, but
full shared normal/Atomic native QP/MR/memory integration is not yet selected.

Nine four-state methods/25 simulations cover missing core/SFD, SFD without
EOF, positive/NAK/replay/PSN wrap, drop then next positive, all native tag
classes, unknown/stale identity/body and completion rejection. One case uses
actual Corundum128-to64 asynchronous frame FIFO,25Gb/s XGMII TX/FCS/SFD-tag
RTL and actual timestamp CDC FIFO, with250MHz core/390.625MHz MAC. Independent
Python decodes actual START/SFD/TERM and checks Ethernet bytes/FCS plus IP/ICRC.
Physical PHY pins, clock/time source and HLS/service inputs in this unit case
remain models. Full generated-HLS composition is recorded separately after
its feature-required compile; no board/native/Linux/timing claim follows from
this unit result. Both global HLS drain inputs remain0; `IB_ATOMIC_NONE` stays.

Generated MAC composition002 now PASSES4 actual-RTL cases, taking8.78/3.22/
3.17/3.18seconds. The main case uses the unchanged complete owned HLS, real
Atomic/MR/PTE/paged DMA/RAM and actual IP/ICRC stages, plus the real MAC path
above. Eleven service requests yield11 consumed-core receipts and11 automatic
packet retirements;10 actual Atomic response Ethernet frames and one unrelated
native tag0x9234 frame leave the real XGMII TX. Actual SFD tags1..9/11 correspond
to Atomic frames; drop consumes nonce/tag10 but emits no frame, and tag11's
fresh FADD succeeds. Independent Python checks every HLS wire/core receipt and
actual MAC preamble/SFD/TERM/FCS/bytes. No test/CPU writes a retirement or
produces positive MAC receipt. Native completion0x9234 is forwarded, never
miscounted as Atomic. The25G name describes the functional MAC clock/width,
not a new physical throughput measurement or GTY/PHY qualification.

Case1 sends actual no-DMA MR-denial NAK through MAC and retires normally;
case2 failed visibility fence yields no service/core/wire completion and holds
both packet/MAC guards;case3 flips one real returned owner nonce and HLS/MAC
reject it without packet/core completion or release. Host DMA descriptors/
ordering, physical PHY pins and PTP clock input remain modeled. Full normal/
Atomic native admission/control/MR/ordinary-payload exclusion and requester/
kernel/API runtime remain open. The next integration must also gate fresh
admission on finite MAC tag exhaustion: the current MAC refuses that owner
and retains/quarantines later work, not a successful execution/retirement.

Diagnostic001 ran the main case successfully but strict result verification
refused its accidentally retained old `MAC_boundary_model` labels. The exact
pre-fix fixture, binary and logs remain.002 fixes only that checked label
generation, freshly translates the entire RTL, reuses only exact identical
compiler inputs, rebuilds changed files and reruns all4 cases. Its source/
artifact SHA audit passes. No HDL/protection/check condition was weakened.
No HLS/Vivado/board synthesis or programming is performed in086; unchanged
owned raw HLS still estimates13.568ns against original4.00ns/1.08ns.

## Owned consumed-core completion (084)

`atomic_owned_transport.py` adds a checked full-core derivative, retaining the
082 source/raw core and083 composition as rollback. The actual packet guard's
immutable144-bit `{nonce32,requestPSN24,epoch64,QPN24}` now enters RX-IBH and
travels through RX-EXH, the512-bit request, actual protected RTL service and
392-bit response. The new registered owned adapter preserves the whole token
and execution/reply offers under disable/backpressure. It does not look up a
mutable current packet at service time. Four-state tests cover registered
offers, full/unknown/stale identity and executor response rejection.

Both RX consumers keep their existing owners. RX-EXH writes MSN only on fresh
execution, then queries and reads back the SAME table on its existing ordered
channel. RX-IBH similarly writes and reads back the SAME responder EPSN before
exporting a224-bit completion: owner144,originalOpcode8,actualEPSN24,
actualMSN24,flags8,error8,reserved8. Flags0/1/2 prove service consumption and
the two readbacks; flag3 means a response is expected,4 fresh advancement,
5 a proven no-packet drop. No new PSN/MSN table or fake RQ/native owner exists.
A cached replay can send an old AETH MSN while this receipt correctly reports
the current unchanged common MSN.

Actual complete HLS C++ plus actual Atomic/MR/PTE/paged DMA/RAM RTL PASSES9
Atomic jobs, normal SEND/two WRITEs and two QPs in0.293seconds. Stopping the MSN
consumer, then PSN consumer, withholds all completions until their real reads
finish. Drop emits a real core receipt and permits later normal/Atomic work.
Both unchanged Immediate TX/RX consumers also PASS on this complete new source.
These C++/RTL results alone are not generated-RTL/native/physical completion
claims; the separate generated-core results follow below.

Complete owned HLS synthesis001 PASS confirms512/392/144/224-bit service,
owner and done ports alongside unchanged existing native owner ports. It uses
59092LUT/84144FF/166BRAM18K/0DSP. The original4.00ns target and1.08ns
uncertainty are verified in generated XML; estimate13.568ns still MISSES the
target, so this is not board timing signoff or permission to program hardware.

Generated composition002 now PASSES4 actual-RTL cases in2.72/1.92/2.17/2.17s.
Case0 processes11 owned service requests on2QPs, emits11 genuine core receipts
and10 actual IP/UDP/checksum/ICRC packets, executes7/replays2/sequence-NAKs1/
drops1, and accepts all11 modeled-boundary retirements. The drop produces no
packet, reads back currentEPSN3/MSN5 with its own nonce10, then the next FADD
nonce11 advancesEPSN4/MSN6 and succeeds. Independent Python checks every
response and every actual owner/current-state completion, including cached
old wire MSN versus current readback MSN. Case1 denies MR with no DMA;case2
failed memory fence yields no service/core/wire completion;case3 flips one
actual returned nonce bit and actual HLS refuses it, preserving the packet
lease and producing no core/wire completion. Positive MAC/physical descriptor/
host ordering boundaries remain explicit MODELS, not actual native or board
proof. The raw per-case fixture capability flag for drop is constant; only
case0 actually exercises/proves the drop branch.

Diagnostic001 failed because the test scoreboard's previous `core_seen` flag
was still set before the next owner arrived; this was not a core receipt for
the drop. Clearing it on the preceding explicit retirement fixes that test
wait, without relaxing any proof. Exact pre-fix fixture/launcher, failed run,
binary and logs are retained.002 freshly translates RTL and reruns every case;
only byte-identical generated compiler inputs may reuse objects, never test
results. Its source/artifact SHA audit passes.

The matched `derive_atomic_owned_bridge.py` binds the actual guard owner
directly to HLS and exposes consumed-core receipts. It remains **Atomic-only**,
not a replacement for normal/native admission. Positive responses still need
their own real native MAC SFD/EOF/tail receipt joined before release; no MAC
idle heuristic or FIFO ready substitutes for that boundary. The full native
ordinary/Atomic memory exclusion integration and requester/standard API remain
unfinished. `IB_ATOMIC_NONE` and both zero global HLS drain inputs remain.

## Generated packet path and ownership (083)

`rocev2_atomic_packet_guard.v` is an **Atomic branch component**, not a
replacement for existing normal native traffic admission. The matched
`derive_atomic_bridge.py` places it after the actual whole-packet IPv4/ICRC
stage and before the real HLS width adapter. It snapshots trusted full QPN,
nonzero64-bit epoch and local/peer IP from management context, not the packet.
It validates the complete72-byte IPv4/UDP/BTH/AtomicETH request before any
byte or owner reaches HLS. Atomic is unposted: no RQ is required or invented.
PSN/MSN and MR permission decisions remain the common HLS and real MR service;
no independent sequence/protection table is added.

A nonwrapping32-bit packet tag distinguishes each accepted packet, including
duplicate PSNs. The guard retains its snapshot and packet ownership until an
explicit matching QPN/epoch/PSN/tag retirement is accepted. A stale tag cannot
release a new retry with the same protocol identity. Native integration must
provide real owned core/MAC retirement, not a user release knob. Already
offered packet/owner beats finish under disable/fault while the lease stays
held; reset is not safe cancellation/unpin proof. Four four-state methods
pass13 simulations. The first implementation's hidden global-header function
dependency was not updated by event-driven simulation; explicit data arguments
fixed it. Positive packet tests, unknown data/epoch/QPN rejection and exact
stale-tag tests now pass without weakening admission.

The full generated fixture connects the actual synthesized HLS top, the new
guard, real typed service adapter, Atomic engine, same MR/PTE/paged backend
and public segmented RAM ports to existing RX/TX IP/checksum/ICRC stages.
Peer packets and output bytes use an independent Python checksum/ICRC/Atomic
oracle. Physical descriptors/host write ordering and AXIS-to-native-MAC
retirement are explicit **models**; actual native queues, host pins/kernel,
physical MAC/tail and board operation are not established.

Composition003 PASSES all3 cases, taking2.77/1.87/2.17seconds respectively.
The main case sends four invalid requests first: one actual CRC rejection,
then three actual peer/QPN/format rejections before any service or DMA.
Ten admitted two-QP service requests exercise CAS success/mismatch, FADD
overflow/zero, cached replies across another QP's update, expected-PSN NAK
and an evicted drop. Six execute, two replay, one sequence-NAKs and one drops;9 packets leave
the real IP/checksum/ICRC pipeline. The independent Python oracle checks
every BTH/AETH/old-value field, IPv4 checksum and ICRC. Packet tags1..10 are
unique, including same-PSN retries. The drop deliberately retains its lease.
The other cases prove actual no-DMA MR denial and failed-fence retention
without a service result/wire reply. All memory bytes pass real RAM ports;
neighbor bytes remain unchanged. This is still two-state **modeled-boundary**
RTL execution, not physical/kernel/native publication or routed timing.

Diagnostic001 ran the main two-QP operation/replay path, a no-DMA MR denial
and a failed-fence ownership-retention case, but its source-change guard
correctly rejected the result after the
four-state fix. Its exact pre-fix guard/launcher are preserved with its logs.
The new translation consumes current RTL; only byte-identical compiler
inputs can reuse verified task-owned RAM objects. Every runtime is repeated;
no test result or producer proof is reused.002 retains a launcher Path-type
error before translation, not a device/protocol failure.

### Retirement boundary in the retained083 baseline

A valid service result accepted by an AXIS FIFO is **not** proof that the
shared RX PSN/MSN consumer has finished with it. A response packet passing the
actual pipeline is not physical MAC SFD/EOF/tail proof either. In particular,
an old unretained request may return a real `drop` result and emit no packet.
The fixture deliberately keeps that packet lease; it does not release on a
delay/quiet-time heuristic or pretend an RQ/core receipt exists.

Before full native publication, carry the immutable per-packet identity
through actual HLS admission/service consumption and export a genuine
post-consumption/shared-state readback receipt (implemented in the084 owned
derivative above, not backported into this rollback baseline). Join it to the matching real
MAC ownership (or proven no-packet drop) before native retirement. Then
integrate the existing single MR/PTE and all ordinary/Atomic memory clients
under the same exclusion domain. Requester descriptors/result placement,
standard kernel/provider capabilities and full physical/error qualification
are still required. This is the next major functional integration, not a
redefinition of completion around the currently passing subset.

## Shared sequencing and typed service (082)

`rdma/rnic/hls/atomic_transport.py` derives a complete matched
`rocev2_native_atomic_top` from the existing Immediate core without editing
the original source. AtomicETH is28bytes; its internal extended-header
container becomes224bits, while actual RETH/Immediate wire geometry and the
full620-bit immutable request context remain unchanged.

The **existing** receive PSN consumer reads the same QP table as SEND/WRITE/
READ and holds its owner until an Atomic service completion. The existing
MSN consumer supplies the current MSN. A successful new execution updates
these same tables; replay/NAK/drop does not. No independent HLS Atomic
sequence table is introduced. Replies use the existing connection/BTH/EXH/
packet assembly path, preserving the saved original MSN for replay.

The hardware-facing scalar AXIS ABI is explicit:

| Word | Fields, least-significant first |
| --- | --- |
| Request368 | Normalized BTH+AtomicETH320, authoritative expectedPSN24, currentMSN24 |
| Reply248 | BTH+AETH+old-value192, localQPN24, original requestPSN24, bytes6, advance1, drop1 |

`rocev2_atomic_service_adapter.v` checks the service request against an
independent trusted QPN/nonzero64-bit epoch, not packet-supplied authority.
It validates executor response identity and registers the exact typed reply,
retaining ownership through downstream backpressure. The actual native wire
owner must eventually provide this trusted context and honor its guard; a
testbench doing so is not evidence of real native admission.

`rocev2_atomic_responder.v` now has `SHARED_SEQUENCE_ENABLE=1`: it uses the
supplied **shared HLS** expectedPSN/MSN instead of its standalone private
tables. Trusted PD/peer/epoch configuration and actual MR/memory authority
remain protected. Every accepted service request returns a completion, even
if the operation is dropped without a packet; this releases the HLS sequence
owner without falsely advancing it. Default mode0 keeps the standalone tests.

Current evidence is `rocev2-rnic-atomic-shared-005.json` in the results folder.
Two live processes run actual HLS C++ consumers and actual adapter/Atomic/MR/
paged DMA/segmented RAM RTL. The HLS-emitted word goes unedited to RTL, and
the actual RTL-generated word returns unedited to HLS. A separate Python
network-byte/arithmetic oracle checks those transfers. The service's private
PSN/MSN are intentionally configured differently, proving shared mode does
not accidentally use them. One SEND and two WRITEs advance the real common
HLS tables between9 Atomic jobs on two QPs. The test verifies withheld-service
no-advance, wrap, replay after a different QP changes memory, CAS mismatch,
FADD overflow, sequence NAK and an evicted drop followed by ordinary traffic.
It finishes in0.279seconds. Existing Immediate TX/RX consumers pass eight
operations each on the new complete source. Four adapter methods additionally
check full/unknown QPN/epoch, stale/orphan response and registered ownership.

Host/physical descriptor/visibility behavior, trusted wire owner/peer admission
and ordinary SEND/WRITE payload sinks are explicit **models**. The HLS tests
execute real consumer C++ and compile the full top, but are NOT generated HLS
RTL, IP/UDP/ICRC/MAC/CQ, actual native/board/kernel/verbs or physical atomicity
proof. Full HLS generation001 completed in301.6seconds with original4ns/default
1.08ns uncertainty,8QP/2000entries and unchanged1500MiB free-space guard.
The actual generated top has368/248-bit service ports and unchanged existing
typed owner ports. It estimates58162LUT/82957FF/166BRAM18K/0DSP and13.568ns:
still a **4ns timing failure**, not physical timing/board qualification.
Exact source/frozen/generated hashes are in `rocev2-rnic-atomic-hls-001.json`.
The actual153-module hierarchy also passes Icarus elaboration with exactly
one PSN table, MSN table and RX-IBH/RX-EXH consumer each, recorded in
`rocev2-rnic-atomic-core-elaboration-002.json`. This is compile-only evidence,
not a generated-HLS packet execution result.

## Implemented path

`rdma/rnic/rtl/rocev2_atomic_responder.v` accepts a normalized, integrity/peer-
qualified40-byte BTH+AtomicETH. Low byte is first on the interface; multi-byte
wire fields are network order. Trusted management supplies PD, peer QPN and a
fresh64-bit epoch; none of them is supplied by the remote request. It executes
RC_COMPARE_SWAP(0x13) and RC_FETCH_ADD(0x14), both64-bit and8-byte aligned.

The operation uses the existing MR table's operation4, requiring the complete
key, PD, range and remote-atomic access. Only local-write plus remote-atomic
permission is needed; remote-read/write permissions are not substituted.
An MR-relative offset can be unaligned even though the full target VA and
translated physical address must be aligned. Full keys and offsets, not
packet-supplied physical addresses, reach the existing sealed-page backend.

`rocev2_atomic_memory_bridge.v` reserves the **same** existing memory arbiter
and backend across MR lookup,8-byte read, comparison/addition, writeback,
actual backend write-visibility status and response handoff. All other clients
in this atomicity domain must pass through client0; Atomic is client1. There
is one MR/PTE/backend/staging RAM, not a separate Atomic memory namespace.
Ordinary traffic waits until an already-accepted Atomic transaction finishes.
CAS mismatch returns the original value without writing. FADD wraps modulo2^64.
Memory lanes are native little-endian; the AtomicACK original value is wire
big-endian. The actual existing backend performs its write readback fence
before success; a submitted or acknowledged write descriptor is not enough.

One replay resource per candidate QP retains the full semantic request and
the original AtomicACK **before** exposing a response. A duplicate replies
with the cached old value without re-executing or incrementing MSN/PSN.
ACK-request changes do not change operation identity. A changed operand at
the same cached PSN is rejected; older evicted requests are dropped, never
re-executed. Future requests produce a sequence NAK naming the expected PSN.
PSN and MSN wrap independently at24 bits. Rebinding a candidate QP requires a
strictly newer epoch and discards the old replay resource. This is one
outstanding responder resource per QP, not arbitrary read/atomic concurrency.

MR denials produce a remote-access NAK before any DMA and quarantine that QP
until a fresh epoch. DMA/readback/status/ownership faults retain the reservation
and inhibit configuration/completion. Reset does **not** prove safe drain,
unpin or recovery. CPU and other-device writes are outside this exclusion
domain; **no global atomicity claim** is made.

## Bounded evidence

Run:

```sh
python3 rdma/rnic/tests/probe_atomic_responder.py --report /absolute/new-report.json
```

The14 cases connect actual new responder/bridge RTL to the existing actual MR
table, arbiter, page table/splitter, DMA backend and Corundum segmented staging
RAM. Every returned/updated byte passes through public stream/RAM ports; no
DUT memory/state is forced. Tests use a full high64-bit VA, nonzero MR base
offset, non-contiguous64-bit DMA pages, full keys/PD and unchanged-neighbor
sentinels. They cover CAS success/mismatch, overflow FADD, duplicate replay,
two independent QPs, competing ordinary DMA, key/PD/access/range/alignment
denial, sequence NAK, stale/fresh epochs, replay eviction and read/write/fence/
wrong-status failures. Response backpressure and held configuration leases
are checked. A separate Python `struct.pack` oracle checks emitted BTH/AETH/
AtomicACK bytes, including old-value byte order. Each simulation is <=30s.

Current standalone positive record: `results/2026-10-18/rocev2-rnic-atomic-responder-007.json`.
Earlier002–006 passed earlier source snapshots;001 retains a test-only assertion
that mistakenly checked exclusion after the Atomic response lease had already
been released. It was corrected; production exclusion was not weakened.

These are four-state RTL composition tests. The physical descriptor engine,
host bytes and readback ordering are explicit **models**, not physical PCIe
ordering/pinning evidence. Input integrity/peer admission is a modeled upstream
contract, not a tested integrated network front door. This test is not an
FPGA test, native HLS test, Linux/verbs test or timing pass.

## Required integration, still open

Mode0 owns a private PSN/MSN table for standalone tests; mode1 now uses the
same actual HLS PSN/MSN consumers, as shown above. Before native publication,
select the actual generated core/service in the complete native graph,
including true QP epoch/configuration/replay ownership, actual integrity/peer
admission and IP/UDP/ICRC/MAC response
ownership. Add requester descriptors with separate64-bit compare and swap/add
operands, protected local8-byte result placement, request retransmission and
true core/MAC/CQ retirement. Bind the resulting capability through the real
kernel/provider/standard API only when this entire path is present. CPU copies,
BRAM counters or a capability bit alone are not an acceptable replacement.
Native integration, physical lifetime/ordering, original4ns/1.08ns timing and
full-board DRC/check_timing/conditional CDC qualification remain unproven.

For build capacity, archive082 losslessly compresses15 exactly validated,
terminal old Verilator-generated C++ cache files (923302562raw bytes to
30436243compressed bytes). Each decompressed SHA matched before raw-cache
removal. Authored sources, raw HLS, inputs, logs, reports and executables are
retained. `results/2026-10-18/rocev2-rnic-cache-archive-082.json` lists exact
targets and hashes; recover any with `gzip -dk /absolute/file.cpp.gz`.

Wire layout and replay design were checked against the primary Linux RXE
implementation: [AtomicETH fields](https://github.com/torvalds/linux/blob/master/drivers/infiniband/sw/rxe/rxe_hdr.h),
[execution and replay](https://github.com/torvalds/linux/blob/master/drivers/infiniband/sw/rxe/rxe_resp.c).
This is protocol-reference use, not a claim that Linux RXE is the hardware
implementation or that this candidate already implements every RC requirement.
