# General RoCE functionality: incremental active work

User objective, retained verbatim:

> 長時間・多数接続の検証、その他ハードウェア構成を変えたり時間のかかるものは目標に含めず、作業を進めて。
> 再起動が必要な場合はCodex自身が再起動後に復活できる設定になっていることを確認して。

Clarification received2026-10-19JST: **機能追加に必要なビルドは可（試験は短時間のみ）**.
Evidence directory dates remain UTC. This follows the discussion of missing
MCX455A RoCE features, not a request to repeat the completed READ milestone.

## Scope and constraints

Continue closing the functional gaps: incoming WRITE/READ responses to the
peer's requests, SEND/RECV and additional operations; registered host memory,
safe PCIe DMA and protection; standard kernel/userspace RDMA interfaces and
work/completion queues; bounded concurrency, protocol error/recovery and
network compatibility/congestion handling. Individual functionality must be
explicitly implemented and verified, not inferred from transport source or
from an adapter merely appearing in `ibv_devices`. No claim of complete
MCX455A product/firmware parity is made by an intermediate component.

Excluded: prolonged/sustained-load tests, large connection-count qualification,
hardware replacement/additions/recabling and other lengthy qualification.
Feature HLS/Vivado builds ARE allowed. Functional tests use short bounded
cases with a few connections; real FPGA communication retains validated
thermal supervision. BIOS Medium, management networking, unrelated devices,
the full native clock/setup/hold/routing/skew/DRC gate and conditional CDC
review remain protected. SRAM only; no flash, global rescan or unrelated reset.
Existing WRITE003 and combined READ/WRITE001 sources/artifacts remain rollback
baselines. No automatic commit/push is implied by this new implementation goal.

## Current evidence and remaining work

Progress098 verifies that the UNCHANGED public provider already transports
standard CAS/FADD through actual installed libibverbs; hardware128 records
remain kernel-private. Provider002 PASSES both511/1023 contexts in<0.017s
with full64-bit operands, bad-WR and WC metadata; only syscall replies are
modeled. Kernel/native-CQ001 additionally PASSES12 ASan/UBSan cases: actual
097 standard callbacks reproduce all128 bytes of096 native SQ inputs and
consume its unedited CAS/FADD/READ/SEND_IMM CQ snapshots, while eight labeled
operand/padding mutations retain refs/no WC/no ACK. Linux/pins/DMA/MMIO/
teardown are modeled, so this is ABI-data compatibility, not live kernel/
RTL/hardware integration. Per-QP Atomic receive authority plus MR permission
must still be propagated before standard remote-Atomic registration is
enabled. All original scope/timing/physical/lifetime requirements remain.

Progress097 adds a checked PRIVATE kernel128 requester cohort, leaving all
default/096 proof inputs untouched. Actual standard Atomic post_send, typed
signal-all, dual128-byte coherent SQ/RQ allocation, strict live tuple/geometry
negotiation, local result-write MR refs and full-operand CQ comparison/WC
retirement are implemented. Actual running-header/GCC13/W=1 build001 PASSES
8.49s; ASan/UBSan post002 PASSES14 new Atomic/geometry and15 prior verbs
cases, each<0.015s. Linux/pins/DMA/MMIO/completion are modeled in those tests;
no actual Linux callback, installed provider or coupled RTL/kernel runtime
is claimed. Default Makefile and both device `IB_ATOMIC_NONE` stay unchanged.
Remote-Atomic MR/QP receive permission and provider128 posting remain, along
with every original physical/timing/lifetime requirement. See
[Atomic details](ROCEV2_ATOMIC.md) for exact failures and boundaries.

Progress096 generates24 matched replacements and PASSES complete native
elaboration003 in2.61s with no port-width mismatch: one actual new requester
HLS/PSN/MSN domain, one MR/PTE domain and full native parents/leaves, alongside
unchanged legacy delivery. Shared SQ/RQ fetch remains one actual engine.
New SQC/RQC128-byte stride/feature13/15 and CQ feature15/operand aperture
pass11 methods/42 four-state cases; adjacent backend/guards/lifetime are
explicit models. Fresh whole-native001 now PASSES447.86s compilation and
five bounded cases: CAS18.80s/FADD19.00s/READ18.90s/SEND_IMM18.85s/mixed
Atomic responder/WRITE18.65s. CAS/FADD use actual C128 SQ, same MR/PTE,
8-byte protected3+5 page-split result DMA/fence, real XGMII/FCS/SFD/CDC,
byte-identical native replay, withheld second MAC receipt and actual CQ
commit/core-retire/host-ACK. Physical host/root/peer/PHY/PTP are models;
ordinary requester MAC pins remain modeled. Kernel/provider128 posting,
standard API, physical operation and original timing/CDC remain incomplete.
See [Atomic status](ROCEV2_ATOMIC.md) for boundaries and failed diagnostics.

Progress095 completes the SAME live generated-requester003 build:502.94s
compile,1.77s TWO-STATE RTL runtime PASS. Two successive CAS/FADD requests
produce exact IP/UDP/ICRC/operands and8-byte LE command/data plus full816-bit
core receipts with PSN wrap. Peer/owner/SQ/connection/memory endpoints remain
MODELS; core bookkeeping is NOT protected host visibility/CQ/unpin evidence.

Actual native Atomic response/result protection leaves now pass21 methods/
110 four-state cases: response guard32 (each<10s), protected executor53,
MAC/lifetime16 and result-pad9. Full748 owner/operands and real integrity/
peer/issued-PSN protect result placement; exact96-bit command and actual data/
backend-status/guarded handoff remain required. Native lifetime checks all
wire operands across a widened80-byte header window and matches816-bit core
receipts, joining actual MAC frame/tag/EOF/tail with other proofs. Adjacent
MR/HLS/physical memory/CQ boundaries are models; replay-enabled family only
elaborates. No complete native128 profile or standard Atomic capability is
claimed. Parent/SQC/kernel/provider/result-DMA/MAC/CQ integration and all11
requirements remain, including unchanged original timing/CDC/physical gates.

Progress094 implements CAS/FADD requester TX, real stored-entry replay,
AtomicACK parsing and8-byte LE result-data production in the SAME full owned
Atomic/Immediate HLS source. Requester C++001 PASSES0.47s:9 fresh mixed
requests,4 actual stored replays, operand/padding/response-class/framing/
syndrome/length negatives, and completion held by actual result, timer and
common-state consumers. Same-source compatibility003 PASSES0.88s with prior
Immediate TX/RX and ACTUAL protected Atomic/MR/paged-memory RTL service.
Endpoint peer/connection/physical memory remain models; no actual generated
RTL/native result DMA/MAC/CQ/API/physical/timing completion is claimed.
Fresh HLS synthesis001 completes318.01s: actual SQ408/owner752/done816 and
unchanged receive/service ABIs verified,61,986LUT/85,982FF/189BRAM18/0DSP.
Actual HLS+bridge elaboration002 passes1.12s with ONE real common domain;
this is compile-only, not generated packet/runtime/native qualification.
Estimated13.568ns still misses original4ns/1.08ns; capacities8QP/2000entries
and original1500MiB free-space guard remain. No timing gate is waived.
All11 requirements remain; no automatic publication or hardware changes.

Progress093 connects actual128-byte PCIe/RAM/SQ fetch, ONE actual MR table
and real guarded748-bit owner/408-bit SQ staging. Positive6 records/6 SQ
offers PASS0.38s; UR-error4 records but only3 SQ offers PASS0.33s, with real
drain/queue-halt/fresh-epoch recovery. Independent every-byte/full-owner/SQ
oracles pass. Physical host/root/config and downstream executor/HLS sinks
remain models; no actual HLS Atomic requester/result/CQ/API claim follows.

Actual Atomic local-result MR admission passes8methods/23 four-state cases;
owner/SQ staging passes5methods/13 cases. Denied/unknown/error records cannot
carry operands or generate SQ authority. Actual LOCAL_WRITE is required for
the8-byte result. Unchanged old admission/Immediate/owner suites pass23
methods. Same-core Atomic HLS request/ACK/result/replay and matched native
executor/MAC/CQ/SQC/kernel/provider remain next. All11 requirements remain.

Progress092 completes fresh full-native runtime003: mixed FADD/duplicate/
ordinary WRITE, READ and SEND_IMM PASS17.51/17.75/17.80s. Actual common native
QP/HLS/MR/PTE/exclusive memory and Atomic MAC are connected. Mixed execution
checks all host bytes, actual XGMII/FCS/SFD/CDC, full wire/ICRC, shared EPSN/MSN
and hardware-owned retirement without fake WQE/RQ/CQ. Physical host/root/
PHY/peer/PTP input remain models; ordinary requester MAC pins remain modeled.
003 reuses an exact frozen executable with a strictly checked one-line Python
normal-ACK oracle correction and ALL cases freshly rerun;001/002 failures
remain preserved. This is not standard API, physical or timing signoff.

The next major requester stage has actual128-byte C encode/decode (7 UBSan
methods PASS) and a checked actual SQ/RAM/mux/PCIe DMA derivative. Positive/
UR-error cases pass6/4 records, every128 bytes/operands checked, with queue
halt/fresh-epoch recovery. Four-state fetch units pass6methods/9simulations;
unchanged64-byte C/Immediate tests pass13methods. These do not implement the
remaining128-byte SQC/driver negotiation, local-result MR admission, shared
HLS Atomic request/ACK/replay/data placement or MAC/CQ/kernel/provider path.
All11 requirements remain; no hardware/default profile or automatic push.

Progress091 added native RX reference/classifier
four-state tests002 PASS9 methods/27 simulations (0.84s), with adjacent
endpoints modeled. The full native functional launcher and whole-wire/state
oracle were implemented; its fresh runtime result is now recorded above.
Atomic8-byte transfer/fence expectations
are checked separately from the unchanged ordinary65-byte requester oracle.
No hardware, clock/drain gate, installed driver or automatic push changes.

Publication snapshot090 (2026-10-20) includes the opt-in complete normal/Atomic
native integration candidate. Actual raw RX/context references, Atomic dispatch,
shared owned HLS/MR/PTE, exclusive memory arbitration and outer MAC lifetime are
connected in one graph. Full-native elaboration001 PASSES with actual generated
HLS and module-count checks; functional execution of this integrated candidate
has NOT been tested. The mixed FADD/duplicate/WRITE fixture only passes Python
syntax/generation; no full-native runtime launcher/result exists yet. Earlier
087--089 runtime results below apply to their own explicitly scoped graphs.

All11 requirements remain open; requester/API, integrated runtime, hardware,
original timing and known broader legacy-CI limitations are not resolved by
structural compilation. Default/rollback RTL, both global zero drains and
`IB_ATOMIC_NONE` remain unchanged. This snapshot is committed/pushed only at
the user's explicit request; no further automatic publication is implied.

Progress089 adds real SQC-backed Atomic route epoch/cookie/PD binding:7methods/
13 four-state cases PASS against actual SQC/mailbox/fetch, including stale
same-QPN recreation, held-lease retirement/config denial and legal producer
updates. The checked full native authority graph and normal/Atomic service-only
bridge elaborate with real HLS, as TWO separate graphs, not full Atomic native
execution. New owned-core native READ/SEND_IMM runtime001 PASSES11.44/11.39s; Atomic
RX remains disabled until real dispatch/MR/memory/MAC ownership is integrated.
All11 requirements, default/rollback bytes and original timing/drain gates
remain. The selected Immediate graph uses independent duplex routing, not the
old exclusive REMOTE role; actual integration must preserve that concurrency.

The unchanged SQC regression also passes on the new lookup derivative:
9methods/36cases2.58s. Combined Atomic33methods/96simulations9.43s PASS.
Native owned stage session26967 is terminal0:417.30s compile,36 identical
compiler inputs reused, both fresh cases run. Full wire/ICRC/replay/native
HLS request-owner/PSN/CQ checks and630source/45artifact hashes pass. Physical
host/root/MAC/peer remain models; no Atomic packet execution or hardware
change is claimed from this normal-operation native staging milestone.

Progress087 adds a checked ordered-reservation Atomic branch, retaining086
sources/evidence. It gates new packet admission on real MAC availability and
finite tags, then reserves the immutable admitted MAC owner BEFORE releasing
the HLS owner. Already-admitted packets/owners drain after new-admission
disable; offered words survive backpressure/late fault, with faulted leases
retained. Five new four-state methods/10 simulations pass; combined Atomic
26 methods/83 simulations pass. The generated composition's bounded4-bit
tag test leaves the hardware default13 unchanged. This remains an Atomic-only
branch, not full native QP/MR/normal-payload integration or requester. All11
requirements and known physical/timing/API/legacy-CI limitations remain.

Progress088 finishes the actual reserved MAC generated build:002 PASSES7
cases, each<=10.99s;770.27s compilation, fresh translation and16 byte-identical
compiler inputs reused, all cases rerun. The15-tag boundary case genuinely
retires15 operations (7exec/6replay/1drop), emits14 Atomic plus1native frames,
then holds a16th post-ICRC packet outside admission without more side effects.
Both admitted-packet disable points complete and re-enable successfully.
All actual MAC-before-HLS events and full wire/core/owner oracles pass;
223 source/23 artifact hashes match. This proves the isolated reserved branch,
not full native admission/QP/MR/ordinary-memory references or safe unpin of
pending upstream input. No hardware or HLS/board timing changes occurred.

Progress086 adds operation-owned Atomic MAC lifetime and a checked new branch
composition with automatic packet retirement. It joins actual owner/service/
consumed-core/wire identity, real Ethernet framing/native frame mux and fresh
nonzero low13-bit MAC tags. Positive retirement waits for its OWN SFD receipt,
accepted EOF/framer completion and1024-cycle tail; drop uses genuine no-packet
consumption, not quiet/delay or a fake RQ. Admission-side trusted peer snapshots
and registered AXIS fanout preserve ownership through backpressure. Nine
four-state methods/25 cases cover those conditions; one uses actual25G XGMII
TX/FCS/SFD and two real CDC FIFOs rather than test-produced MAC receipts.
Full generated-HLS composition is recorded after its compile. This Atomic-only
branch is not yet full normal/Atomic native admission/MR/memory integration;
requester/standard API/physical/timing qualification and all11 requirements
remain. No automatic new commit/push or hardware changes are authorized.

Current generated MAC composition002 PASSES4 actual-RTL cases <=8.79seconds.
The11-request main case produces11 consumed-core receipts/automatic packet
retirements,10 actual Atomic XGMII/FCS/SFD responses and one independently
forwarded native frame/completion. Drop tag10 has no frame and next FADD tag11
succeeds. Independent Python validates actual wire/FCS and core ownership/
readbacks. MR denial goes through actual MAC with no DMA; failed fence or
corrupted echoed nonce cannot complete/release. Host descriptors/order and
PHY/time input remain models; actual native QP/MR/normal memory integration
is still separate work. Diagnostic001 was refused for stale scope labels;
002 uses corrected checked labels and fresh RTL translation/all4 reruns.
No new physical/HLS timing qualification; original target/uncertainty and
both global0 drains remain, owned HLS estimate still13.568ns. Finite MAC tag
exhaustion must gate future native admission; it is not successful completion.

Progress084 adds immutable packet ownership through the complete Atomic HLS
RX/service and a real consumed-core completion after SAME-table MSN/EPSN
readbacks. It reuses both ordered RX query channels, not another state table.
The owned512/392-bit service and224-bit core receipt retain full QPN/64-bit
epoch/requestPSN/32-bit nonce. Actual HLS C++/protected RTL co-simulation PASS:
9 Atomic jobs/normal SEND/two WRITEs/two QPs, with completions withheld while
either actual MSN or PSN consumer is stopped, and forward progress after drop.
Unchanged Immediate TX/RX consumers also PASS. New complete owned HLS synthesis
PASSES original4ns/1.08ns source/ABI checks, but13.568ns estimate still MISSES
timing. Generated composition002 PASSES4 cases <=2.73seconds:11requests/11real
owned core receipts/10wire packets with drop then fresh FADD; no-DMA MR denial;
failed-fence retention; and rejection of a deliberately corrupted returned
nonce without core/wire completion. The independent oracle checks actual wire
and current common-table readbacks.001 retains a test scoreboard wait failure,
fixed by clearing its previous receipt on the preceding explicit retirement;
002 freshly translates and reruns all cases. No native MAC/standard verbs/
physical/timing completion is inferred. Full native shared
admission/memory exclusion, genuine MAC join, requester and all11 requirements
remain. No hardware settings, FPGA, modules/provider or Git remote changed.

Progress083 adds a real Atomic-specific whole-packet peer/QPN/epoch admission
branch after the actual RX integrity stage and before generated HLS. It emits
a unique packet tag across duplicate PSNs, preserves trusted context under
backpressure and refuses stale retirement. Four new four-state guard methods
PASS13 simulations. The normal native operation branch is not replaced; no
extra PSN/MSN/MR table or CPU payload transport is introduced. The new matched
integrity bridge connects the actual generated Atomic top and real protected
service/MR/PTE/DMA/RAM to actual IP/UDP/checksum/ICRC RX/TX. Full composition003
PASSES3 runtime cases <=2.78seconds: the10-request two-QP path produces9 real
wire packets and a guarded no-packet drop; MR denial produces no DMA; failed
visibility-fence retains ownership without a response. Actual packet bytes/
checksum/ICRC pass an independent Python oracle.001 remains diagnostic only:
its source-change audit refused a pass after the four-state fix.
Physical descriptor/host ordering and native-MAC retirement remain MODELS.
In that retained083 rollback, no-packet drops keep their packet lease until genuine post-consumption core/
native retirement can be proven; no guessed delay, AXIS accept or global
idle is used to claim safe release. Actual full native/kernel/API/physical/
timing completeness remains open; `IB_ATOMIC_NONE` stays.

Progress082 joins Atomic to the real common HLS RX PSN/MSN and TX consumers.
The existing sequence owner waits for a typed actual RTL-service completion;
only successful new execution advances the common tables. Standalone Atomic
mode0 remains for unit compatibility; shared mode1 takes authoritative PSN/
MSN from HLS, not a private table. The368/248-bit adapter binds trusted full
QPN/epoch and retains a registered reply across downstream backpressure.
Actual HLS C++ and actual adapter/MR/paged DMA/RAM RTL exchange unedited service
words in a bounded0.279second co-simulation:9 Atomic jobs plus normal SEND/
two WRITEs on two QPs PASS. Immediate TX/RX regressions pass eight operations
each; four adapter methods and14 standalone execution cases pass too.
Physical host/descriptors/ordering, owner/peer admission and ordinary payload
sinks remain MODELS; this is not generated-HLS/native/physical/verbs evidence.
New full HLS generation001 is terminal0 after301.6seconds under the original
clock/capacity/free-space gates;58162LUT/82957FF/166BRAM18K/0DSP and exact368/
248-bit service ports. The13.568ns estimate still MISSES4ns, not a timing pass.
Default graph/`IB_ATOMIC_NONE` stay unchanged.
All eleven requirements remain; actual native wire-owner/MAC/CQ binding and
Atomic requester/standard APIs are next. Fifteen old generated compiler C++
cache files were recoverably gzip-archived; sources/logs/executables retained.

Progress081 adds a major missing operation's responder execution block:
wire-format RC64 CAS/FADD -> real same MR operation4 -> exclusive existing
shared arbiter -> sealed-page DMA/staging/readback fence -> old-value wire
AtomicACK. Per-QP cached replies prevent duplicate updates.14 four-state
composition cases pass with independent Python wire-byte checks. Physical
descriptor/host visibility and input integrity/peer admission are MODELS.
The candidate's QP table is private to this test; sharing native HLS QP
sequencing, true network/MAC ownership, requester and standard kernel/provider
integration remain open. Default `IB_ATOMIC_NONE` stays; no actual/native or
timing completion is claimed. See `ROCEV2_ATOMIC.md` and progress081 checkpoint.
This implements a new functional path, not a broad fine-bug/timing cleanup.
All eleven full-goal requirements remain, with no hardware/BIOS/network action.

Progress080 adds standard/API Immediate support in source. Actual kernel
initialization re-reads and binds the complete RNC/SQC/RQC/CQC=1023/5/7/7
capability tuple before queues. No user knob or CQC format bit alone enables
it; legacy/default profile0 still refuses Immediate. Standard post_send now
handles both new operations, separate full remote VA/key/immediate, safe base
SEND signal-all copies, linked-list failure and full CQ/reference lifetime.
Native graph/device publication and provider support the two exact reviewed
FW profiles.9 actual callback/capability cases and20 native graph model cases
PASS, including new1023 publication and normal closure; actual libibverbs/
provider command tests PASS Immediate0/nonzero/WC serialization and legacy
compatibility. C tests model Linux/MMIO/pins/DMA/completion; userspace tests
model kernel syscall replies and open no real NIC context.

Current full-generated new-profile native simulation PASSES7 requester/4
duplex receive cases, each<=15.3seconds, with actual four-controller AXI
capability capture, old READ/WRITE/SEND, exact wire/replay/native DMA/MAC/CQ
and independent WRITE remote-MR versus notification RQ. Its16 unedited CQ
records PASS the actual independent-queue C bridge. Host/root/MAC/peer remain
MODELS; native simulation is two-state. Fresh78-method checks, real running-
kernel W=1/new-export build and frozen provider build PASS. Source/API support
is not actual physical/kernel/provider runtime or original-clock signoff.
Atomic/zero/large/multi-SGE, physical/error lifetime/thermal and original
timing/DRC/CDC gates remain; HLS13.568ns still misses4ns. No module/provider
install/load, FPGA programming, BIOS/network change, commit/push or reboot.
All eleven requirements remain. Checkpoint: `results/2026-10-18/rocev2-rnic-progress-080.json`.
Six terminal generated cache/executable files were losslessly gzip-archived,
not lost; source/logs/current executables are retained and recovery hashes
are in `rocev2-rnic-cache-archive-080.json` in the same evidence directory.

Preceding full-native integration evidence (as run before capability extension):

Progress079 closes the isolated-interface gap with a complete checked opt-in
Immediate native derivative: same coherent SQ/RQ, one MR/PTE/native HLS core,
executor/replay/protected wire and actual MAC/CQ lifetimes. Full620-bit owners,
280-bit SQ,688-bit requester/752-bit receive/768-bit MAC receipts remain exact.
Wire notification is independent of immutable posted RQ context. WRITE_IMM
retains genuine full RETH/remote-MR authority independently of notification RQ;
actual empty-RQ RNR occurs before RX forwarding or receive PSN advancement.

The full actual generated requester PASS7 cases (Immediate0/nonzero plus old
READ/WRITE/SEND),12.6–12.8seconds each, with exact real wire/ICRC/replay/MAC/
core/native CQ proof. Full native duplex receive PASS4 cases, each two genuine
work pairs on independent SQ/RQ rings,14.3–15.3seconds. WRITE_IMM65-byte data goes to remote
VA...3210 while its1-byte notification RQ is at VA...3410; sentinels and exact
data placement are checked. Two cases exercise empty-RQ wire RNR. Local SEND
and peer receive are simultaneously owned, and each completes only after its
OWN memory/core/MAC proofs, not the other direction's MAC barrier. Both global
HLS drain inputs remain0. Full-native hierarchy has one native/one legacy core
and one MR/PTE, no bypass/extra namespace. Fresh78-method suite passes.

Sixteen unedited native CQ records then PASS actual kernel independent SQ/RQ/
MR/CQ C under ASan/UBSan, including eight correct Immediate receive WCs,
network byte order/value0, distinct WRITE notification opcode, exact descriptor
bytes/cookies/ring IOVAs and reference release. Physical host/root/MAC/peer and
Linux/pins/DMA/MMIO are explicit MODELS. No actual kernel/provider/board or
full-board timing qualification is claimed; native simulation is two-state.
Standard TX posting remains profile0/Immediate-denied pending trusted matching
device capability/standard posting support. The default graph/immutable
protected source are unchanged. Atomic/zero/large/multi-SGE and all eleven
requirements remain;13.568ns HLS still misses4ns. No hardware/BIOS Medium/
network/install/load/programming/commit/push/reboot/archive/deletion action.
Current checkpoint: `results/2026-10-18/rocev2-rnic-progress-079.json`.

Preceding receive-completion leaf evidence (not whole native runtime):

Progress078 adds real Immediate RQ provenance/retirement and ACK MAC binding,
an opt-in CQC620-bit owner/independent wire-notification ABI and actual kernel
IO/decode/SQ/CQ WC mapping. Posted context is immutable; wire/core/MAC values
must agree. Eight connected actual RQ/MAC/CQC notifications and their unedited
RTL snapshots pass actual kernel C, including zero-valued WITH_IMM, distinct
WRITE-with-Immediate WC, data length larger than notification RQ capacity,
CQ-full/lost-ACK/ref-lifetime and malformed-metadata retention. Wire admission,
HLS/visibility/MAC pins and Linux/DMA/MMIO remain MODELS; this is not actual
remote write placement/generated-native/physical runtime. Five four-state
provenance units, the78-method current suite, actual running-kernel W=1/new-
symbol build, device/native-graph model regressions and the unchanged-default
full-native hierarchy pass. Default ABI1/3 stays19words; explicit format7 adds
word20/notification registers. Current native parent and actual post_send
remain Immediate-disabled until full matching wire-MR/parent/core/executor/
RQ/MAC/CQ integration and original timing/DRC/CDC gates, not merely codec/ABI
support. No hardware/BIOS Medium/network/install/load/push/reboot action.
Current checkpoint: `results/2026-10-18/rocev2-rnic-progress-078.json`.

Progress077 adds actual candidate-profile host descriptor/verbs-WR encoding,
retains a separate immediate32 in fixed64 bytes, and carries it through actual
SQ-result/shared-MR authorization into a620-bit owner and280-bit HLS SQ.
Default APIs and current standard posting remain profile0/Immediate-denied.
The complete46-method short suite, four-state new operation/denial/stall/
unknown-value tests, running-kernel W=1 build (including all new exports) and
existing full-native duplex hierarchy elaboration pass. A matched integrity
bridge now selects the actual complete Immediate HLS. All8 actual generated
wire/ACK-retire cases PASS at about1.31seconds each, checking RETH/IETH/full
VA/key/notification/payload/padding/IP/ICRC and genuine620-bit request receipt.
These are two-state Verilator tests; separate leaf/default tests are four-state.
The earlier VVP30second timeout is retained. SQ fetch, payload, executor lifetime
and peer are explicit models in this leaf; full native DMA/MAC/CQ/receive-
notification/MMIO/kernel/provider matching remains. Earlier076 native runtime
is historical after these shared leaf changes; current elaboration alone is
not runtime. All eleven requirements and hardware/BIOS Medium/management/
original timing/DRC/conditional CDC constraints remain. No deployment or push.
Current checkpoint: `results/2026-10-18/rocev2-rnic-progress-077.json`.

Progress076 follows the user's feature-first priority. The same duplex core
now passes full-generated native READ/WRITE/SEND with real coherent WQE,
MR/PCIe/fences, exact wire/ICRC/replay and CQ ownership, each under12seconds;
the unedited records also pass actual kernel C with Linux/MMIO modeled.
The preceding duplex ordinary/RNR cases are rerun, not relabeled cached pass.
Immediate TX AND RX source now adds both SEND_WITH_IMM/WRITE_WITH_IMM, distinct
32-bit notification and full remote key/VA, actual wire EXH/header stripping,
independent immutable RQ owner and genuine request/receive receipts. Eight
short C++ TX→RX packet-model pairs pass, including zero/high/all-one values,
PSN wrap and write data larger than the notification RQ buffer. This is NOT
native MR authorization, PCIe/MAC/CQ, IPv4/UDP/ICRC or Linux/physical Immediate
evidence. Matched original-clock HLS synthesis passes and checks all larger
port widths, but its13.568ns estimate MISSES4ns (56678LUT/81179FF/159BRAM18K/
0DSP). No native/RTL-runtime/physical/timing pass is implied. The new ports
are not selected into the existing native graph. Next is matching native
guards/RQ/CQ/MMIO/kernel/provider integration for this feature, not another
general timing/fine-bug audit. All eleven requirements remain; no hardware,
BIOS Medium, management-network, module/provider, commit/push or reboot action.
Current checkpoint: `results/2026-10-18/rocev2-rnic-progress-076.json`.

Progress051 registers the FULL320bit same-table query without dropping any
field/reserved guard, improving HLS4.002->3.947ns; query2.542ns/all7II1.
This is nominal estimate ONLY: effective2.920ns/full physical gates still
unqualified. Fresh base00410+control00512FOUR-STATE cases pass, including
two real long-bad-frame quarantine stalls holding source127cycles; no owner /
parser/completion work. ActualC1154fullqueryvectors plus earlier exhaustive
checks and12sourceunits pass. HLS006wrong-tool-path failure retained;007current.
Only3059terminalDBexpandedduplicates became exact recoverable archives; raw138 /
delivery140/frozen/usedRTL/rollback preserved. Full11requirements/native /
effectful RX/DMA/CQ/ONEshared integration/drain0/refsheld remain. See
`ROCEV2_OWNED_WIRE_RX.md` for exact scope and incremental record format.

Progress050 splits actual count/check/commit into genuine II1 streaming tasks,
adds a private elastic guard-result register and separately checks the exact
completed320-bit descriptor. Validated LAST storage precedes parser command;
new frame fault quarantines actual pool/process. HLS5.298->intermediate5.084
->current4.002ns at SAME4ns/uncertainty/full geometry is STILL UNMET, no board
timing/CDC signoff. Source00610units and actual C0051048576frame-check beats
plus exhaustive keep/count/decoder checks pass. Expanded terminal DB/VHDL
duplicates1907files now SHA-verified recoverable archives;543older DB members
match exact049hashes, Verilog/frozen/synreports/rollback intact, guard unchanged.
Fresh base00310 and control00410FOUR-STATEcases pass each<12.746s, including
all256AETH/full65535frame; public summaries match049exceptcycles, not general
equivalence. Full11requirements/native/DMA/CQ/ONEshared /
physical gates/drain0/refsheld remain; see `ROCEV2_OWNED_WIRE_RX.md`.

Progress049 reschedules the actual wire-RX candidate without changing its
protected interfaces/capacities/4ns clock. Exact keep decode, an actual II1
beat-decoder task, registered header/lookup checks and same-table first-epoch
selection improve HLS10.256->5.678->5.298ns. Frontend3.660/process3.683ns,
but ingress5.298ns remains UNMET and no physical signoff. Nine source units
and bounded exhaustive keep/count/actual-decoder C++ checks pass. Temporary
terminal049 HLS DBs1110files are SHA-verified lossless archives; only expanded
duplicates removed, all older evidence/RTL/reports/rollback retained, disk
guard unchanged. Fresh generated FOUR-STATE base00210cases and control003
10cases pass, each<12.698s, with all256syndromes/full65535frame/stall guards;
all public summaries match048 except rescheduled cycles. Full native /
DMA/CQ/shared integration/all11requirements/drain0/refsheld remain.
See `ROCEV2_OWNED_WIRE_RX.md` for current versus historical scopes.

Progress048 connects actual FNS BTH/EXH byte parsers to the SAME lookup /
pointer8/metadata2000/process/timer/real-pool candidate, removes its external
synthetic query port, and retains full raw headers/syndrome/immutable owner.
Actual external metadata/body-last receipts gate lookup unlock and marker
closure; actual external fence transfer alone reopens parsing. Ten fresh
short FOUR-STATE cases pass, including full65535-byte retention, while
eight source units pass. Additional10 short FOUR-STATE cases cover all256
AETH values and malformed keep/header version, each<9.035s; failed original
legacy-isNAK fixture retained. HLS10.256ns UNMET at original4ns; no physical gate
waiver. Trusted admission/epoch are still caller inputs, raw body is NOT DMA
payload, and effectful RX FSM/native/MAC/DMA/CQ/shared selection remain.
All11requirements/drain0/refsheld unchanged; see `ROCEV2_OWNED_WIRE_RX.md`.

Progress047adds same-table RX owner lookup inside a new actual owned process /
timer/pointer8/metadata2000/real-pool candidate. No shadow current-QP owner
table. Full24QPN/epoch64/lease248, READrange/PSNwrap, full-length rounding,
whole-list ambiguity checks and actual result-acceptance/private receipt keep
the pointer locked without metadata write/return/CQ. A FIFTH query marker is
required for scoped boundary closure. Fresh XSIM003 SEVEN short FOUR-STATE
cases pass, each<6.779s; source0027units pass. Case8full2000live traversal is
NOT qualified: initial8case run times out at unchanged30s; diagnostic observes
normal progress, not a hardware failure. ExtraTWO-STATE convergence failure
and copied-kernel checker failure retained, not promoted. HLS0024.644ns UNMET
at original4ns/70BRAM18K/23661FF/24225LUT. Actual native packet/QP admission /
RXIBH/EXHproducer binding/MAC/DMA/CQ/shared selection remain; drain0/refsheld /
all11requirements unchanged. See `ROCEV2_RX_OWNER_LOOKUP.md` for exact scope.

Progress046replaces the actual selected EXH generic header-word carry chain
with constant-word cases while preserving full16bit index/out-of-range/partial
lanes/header/ready semantics. Actual original differential C++ checks cover
all65536indices at5widths for bothRETH/AETH (655360comparisons), each<0.298s.
Current C++00316cases/source0027units/generated RTL0035FOUR-STATE cases pass;
added actual ACK/AETH has no requester-owner contamination,12passive AXIS
hold monitors added, eachRTLcase<0.307s. HLS002estimate5.896→3.964ns, EXH3.921ns,
8651FF/5630LUT, original4ns unchanged; effective2.920ns warnings remain, NOT
fullboard timing/CDC signoff. Old045C/HLS/RTL/source fixtures retainedhistory.
Native admission/RXownerlookup/orderedmarkers/actualtimer-pool/MACSFD/DMA/CQ /
sharednative selection remain; drain0and refsheld/all11requirements intact.
See `ROCEV2_OWNED_WIRE_TX.md`. No hardware/config/reboot/commit/push action.

Progress045binds actual FNS TX local/event/BTH/EXH/insert producers to full
immutable perWR QPN/epoch/sequence and original retry lease. The actual two
independent PSN/address queues must match owners before metadata insertion;
mismatch fails closed. The actual EXH emits full owner instead of bare QP.
C++14cases0.036s, six source units0.261s and exact generated FOUR-STATE RTL
4cases<0.326s pass, including four real READ/WRITE producer requests, actual
BTH/RETH/key0/PSNwrap and independent output stalls. HLS0015.896ns at original
4ns is UNMET; original EXH generic header-word iterator is the longest path.
This new TX candidate is NOT selected in shared/native/board or connected to
actual timer/pool/native SQ; external state/MSN responders are models. RX
ownership lookup, ordered producer fences, actual MAC-SFD/DMA/CQ and physical
gates remain. Shared drain0and refs held, all11requirements intact; failed
initial C++JSON-format case retained. See `ROCEV2_OWNED_WIRE_TX.md`.

Progress044breaks the owned timer's retirement-horizon compare/select/write
path into real read/check/normalize/time/horizon/commit states; marker format
and actual resume receipt checks also registered. HLS004estimate6.894→3.613ns
(timer3.489ns) at original4ns/70BRAM18K/18814FF/20880LUT. Effective-budget
warnings remain; NOT full-board timing/CDC signoff. Original idle scan actions,
II1/4ns/31250visits/1ms/backoff/8QP/2000metadata and all protection retained.
Current C++6queries and3standalone FOUR-STATE/6coupled TWO-STATE cases pass.
NEW XSIM001runs the exact current coupled candidate in FOUR-STATE for all6
cases, including actual1ms/two-WR retry, each<21.367s with X/Z calibration;
all fields/cycles match TWO-STATE. This is NOT whole FNS wire/native/MAC/DMA/CQ
or physical qualification. Full11requirements remain, shared drain0and refs
held. Exact old timing negatives and two source-check anchor failures retained.
See `ROCEV2_OWNED_TIMER.md`. No hardware/configuration/reboot/commit/push action.

Progress043couples the ACTUAL8-entry timer producer to real insert/ACK/head /
replay controls in a new production wrapper with NO injected timer-request
port. Full248-bit oldest-head lease, actual next-head metadata after exact
pool return, retired-WR tombstones and two-phase scan-close→old-timeout-marker
→TX-marker break the cyclic fence dependency. A SIXTH actual timer response
joins the boundary fence; actual external acceptance alone resumes it.
Real mixed-WR replay keeps each record's own lease. C++6queries/250428cycles,
3standalone timer FOUR-STATE and6current coupled TWO-STATE cases pass, each
simulation<4.072s; coupled real1ms/two-WR replay uses NO timer injection.
Scopes are complementary, not full current-graph FOUR-STATE/native proof.
HLS0026.894ns at unchanged4ns is UNMET; no physical signoff/gate waiver.
Full original wire RX/TX/header-producer context/shared/native/MAC/DMA/CQ
binding remains, shared drain0and full11requirements intact. Initial simulator
internal crash retainedFAILED; exact RTL fresh recompile uses simulator-only
optimization workaround. See `ROCEV2_OWNED_TIMER.md`. Source/offline only.

Progress042adds an actual process-injected marker join across all four input
queues, real pointer twoqueue/meta2000record/pool twoqueue consumers and actual
event/RDinit handoffs. Production wrapper has NO test pool mux. Five actual
generated FOUR-STATE cases pass, each10.580..28.018s: no response with real
output held despite actual pool zero, BUSY→ACK→new clear window, missing/bad
markers, and no input-window reopen on merely buffered response. This is ONLY
the retransmission subsystem boundary, NOT shared core/MAC/DMA/native/CQ drain.
Shared drain0and WR/MR refs held. Upstream real RX/TX/timer trusted-context /
marker injection and full shared/native propagation remain. HLS003estimate
4.610→3.613ns at original4ns/70BRAM18K/11311FF/12136LUT; warnings/no physical
signoff. Four source units pass. Initial fullpool Icarus30s timeout remains
FAILED; faster additional TWO-STATE regressions do not replace four-state
scope. See `ROCEV2_OWNED_RETRANS_FENCE.md`. Full11requirements unchanged.

Progress041binds an actual FNS-derived process/8pointer/2000metadata subsystem
to the real lease allocator in a new opt-in production wrapper, not in the
shared/native/board parent. Full248-bit immutable leases survive actual READ
PSN mutation and travel on events/RDinit; exact real grant/return handshakes
guard insertion and pointer unlock. Credit0does not hide ACK processing.
Current FOUR-STATE RTL002passes six bounded cases plus the unmodified actual
wrapper, each below15s, including real full-pool release/reuse, linked records,
READ PSN wrap, stale WR ACK/retry and full QPN rejection. Real outputs remain
HELD after actual pool zero, so this is explicitly NOT core/MR/CQ retirement.
HLS005estimate4.642→3.965ns at original4ns; scheduling warnings remain, no
resulting physical/CDC signoff.70BRAM18K/9698FF/6701LUT; full geometry retained.
Four source units pass. Exact failed001/002and intermediate builds retained.
Native producer-context/marker injection, actual whole-core fence and shared
parent/native/CQ binding remain; shared drain0and all11requirements unchanged.
See `ROCEV2_OWNED_RETRANS.md`. Source/offline only, no hardware/config changes.

Progress040adds a REAL2000-slot lease-RAM/free-ring allocator candidate,
not yet the actual FNS process/free-list replacement binding. Full-WR tuple /
nonwrapping generation and FREE/OFFERED/OWNED states prevent unread grants,
duplicate/stale/wrong-owner returns or local reset from making active slots
free. Both ordered producer markers trigger an actual all-slot owner scan.
Current16case unit003passes4.171s incl all2000unique indices/full exhaustion /
reuse/reset retention/immutable lease-PSN checks and four matching
SYNTHESIS-known-signal cases.
An initial packing bug failed the full-owner scan; exact failed001retained.
Actual isolated synthesis maps14RAMB36/1640LUT/1728FF; immutableDCP replay003
verifies ALL64generation reset pins driven by GND. Prior verifier001/002remain
failed, not promoted. No post-synth replay/full-board physical/CDC signoff;
OOC estimate has missing I/O delays/clock-source binding. Lease retention is
NOT hard-reconfiguration/power-loss or safe runtime recovery. See
`ROCEV2_RETRANS_POOL.md`. Real FNS/generation/metadata/event/native/CQ/provider
binding and all11requirements/old physical negatives remain; shared drain0.

Progress039adds actual full2000entry retransmission metadata commit/readback,
not allocator/free/whole-core authority. Original ACK release leaves valid
data behind, so valid is deliberately NOT used to decide active/free.
Original clear/write/append/read actions retained; false inter-dependency
waiver removed in selected derivative. Registered stages preserve real RAW /
order/II1 and improve HLS estimate to2.812ns at unchanged4ns, no physical signoff.
Current C++003passes23readbacks/2005reads plus3independent typed codec cases;
generated FOUR-STATE RTL003passes27/6005in17.865s, checking ALL2000initialzero,
nonzero write/read and zero after simulated private-DUT reset. A real normal
response stays HELD after commit OK/VALID data, explicitly NOT allocator/core
drain or MR/CQ release.4source units pass; full profiles/old timing negatives
retained. Isolated/not selected; real free-list/process/event/producer binding
still required. See `ROCEV2_RETRANS_META_FENCE.md`. Full11requirements and
source/offline/exclusions/old physical gates remain intact.

Progress038adds actual retransmission pointer/lock consumer readback with
two ordered full168-bit producer markers and original update/request/wait
actions. Real8-entry BRAM initialization, global lock/wait, full QPN and
unchanged2000metadata-index guards are checked; the actual metadata/free-list/
process/event owners themselves are NOT instantiated or drained here.
Current C++002passes35queries0.004s; actual generated FOUR-STATE RTL003passes
39queries including simultaneous input/update priority and actual BRAM clear
after private-DUT simulated reset. A normal response remains HELD after
pointer-state OK, explicitly NOT core/WR/MR/CQ retirement.4source units pass.
HLS estimate4.152to3.347ns at unchanged4ns/II1, scheduling warnings/no physical
signoff. Isolated/not selected in shared/native/board; genuine drain stays0.
See `ROCEV2_RETRANS_POINTER_FENCE.md`. Full11requirements/exclusions/physical
negatives/source-offline boundary remain; no hardware/configuration change.

Progress037adds actual state-table RX/TX/QPI ordered-marker rendezvous, not
a shadow table or whole-core certificate. All3full168-bit tokens must match;
missing markers withhold readback, later requests cannot overtake their own
markers. Original table actions/BRAM/8entries remain; real QPI initialization
and full16-bit normal/marker QPN guards precede snapshots/indexing. Elastic
registered dispatch preserves HLS II1 and improves estimate4.618to3.158ns at
unchanged4ns, with effective-budget warnings and NO physical signoff.
Actual C++005passes32queries0.004s; generated FOUR-STATE RTL005passes59queries
including8continuous-VALID ordinary writes and real normal responses still
HELD after state-window OK.4source units
pass separately. This explicitly does NOT drain producer/retry/event/output
owners or authorize WR/MR/CQ release. Shared/native core has not selected it;
genuine drain stays0/owners held. Retained compile/counter/checker failures
and intermediate designs remain scoped history. See `ROCEV2_STATE_TABLE_FENCE.md`.
Full11requirements, exclusions/physical negatives and source/offline boundary
remain active; no programming/reboot/configuration change or automatic push.

Progress036adds actual ordered timer-state readback, an isolated opt-in
derivative of the frozen REAL eight-entry timer consumer. Same-RX-FIFO markers,
actual pending-TX updates, full tokens/QPN guards and registered sampling/
classification/emission preserve the original timer/backoff/timeout logic.
Current C++003passes26queries0.064s; actual generated FOUR-STATE RTL003passes
46queries25.432s, including output/FIFO stalls and a real250010-cycle timeout.
Timer-state OK while that actual timeout remains held proves it is NOT a
whole-core drain/MR/CQ release certificate. Shared-core role guards stay HELD;
this component is NOT yet selected/integrated. HLS estimate improves4.627to
3.911ns at unchanged4ns, with scheduling warnings and NO physical signoff.
4source-invariant units pass; historical compile/reset-bench/checker failures
and exact source snapshots remain. See `ROCEV2_TIMER_STATE_FENCE.md`. All11
requirements, physical negatives and source/offline operating boundary remain.

Progress035shares ONE actual immutable HLS core and ONE actual MR table between
protected incoming65BWRITE and an actual C/authorized local READ. Current003
passes in2.669seconds: actual guarded SQ/key0/own-TX PSN/protected wrong-QP
reject/actual HLS68raw -> checked65payload/3pad/actual MAC tag-lifetime RTL.
Memory/peer/MAC pins are models; NO native coherent SQ/PCIe/CQ/core-drain proof
is claimed. Actual guards intentionally remain HELD and MR invalidation stays
blocked at finite end. Separate four-state5methods/46runs and4derivation units
pass. Original responder/rollback are untouched, not another HLS/MR namespace.
Native PCIe trace proof and live single-core proof remain complementary,
not a completed native shared-HLS/runtime RNIC. See `ROCEV2_SHARED_HLS.md`.

Progress034adds real native-role MAC framing/arbitration/tag-to-full-owner
correlation and an atomic production MAC/lifetime binding. Separate short
four-state batches pass8methods/33simulations and5methods/20simulations.
New native integration passes1method in31.482seconds, interposes actual
Ethernet egress/completions and
retains real SQ/SAME-MR/protected RX/executor/scattered-PCIe/fence/STOP guards;
one ordinary host frame/completion is checked concurrently. MAC proof/drain
are now connected RTL, not a copied-context callback. TX remains actual-HLS
trace replay; HLS extraction/ACK/drain, physical pins and final CQ remain
models. General shared-HLS/driver/provider/runtime/physical integration is
still incomplete. Finite nonreused tag exhaustion fails closed, not recovery.
See `ROCEV2_NATIVE_MAC_LIFETIME.md`; all11requirements/exclusions remain.

Progress033confirms actual-HLS coupled protected READ replay003terminal0in
12.086seconds:68raw/65payload/3discarded pad, actual native scattered PCIe/
two posted WRITEs/fence, wrong-QP rejection, exact bytes/guards/sentinels.
Only a corrected peer-fixture generation line differs; frozen exact compiled
design/bench/other fixtures/source hashes are revalidated, no assertion/RTL
repair or failed-result promotion. Additional TWO-STATE only, host/peer/CQ
MODELS, not hardware/OS completion.
Production `rocev2_wqe_lifetime` adds actual own-TX-derived PSN/expectation and
full memory/response/HLS-ACK/MAC/drain/ticket/commit ownership;12methods/83
four-state simulations pass. Native lifetime integration checks real MR/RX/
PCIe/fence/guards but replays TX and models HLS/MAC/drain/CQ. These are distinct
scopes, not one live-HLS/real-MAC/CQ proof. See `ROCEV2_WQE_LIFETIME.md` for
retained fixture failures, invalid old pass flag and remaining real binding.

Progress032observes portable038terminal0:309methods/849.164seconds, including
source-current response-guard004(11methods/34simulations) and native-response003.
Existing actual-HLS READ emits PADDED command/data (65payload ->68wire), so new
production `rocev2_wqe_read_unpad` validates its full saved-token/96-bit ABI
before removing only wire pad;5new methods/39four-state simulations pass.
The new coupled actual-HLS protected READ/unpad/native-DMA/fence build002is LIVE
at checkpoint032, NOT a pass; independent expected-route checker correction
caused owned compile001to stop before simulation, preserved as failed evidence.
See `ROCEV2_READ_UNPAD.md`. Real issued-context/wire/MAC/CQ/provider/runtime and
all broad operations/physical/hardware gates remain incomplete; no hardware
mutation or completed-RNIC claim.

Progress031confirms previous actual-HLS native source compiled002terminal0:
one65-byte WRITE packet from actual coherent WQE/SAME-MR/HLS/executor/paged
PCIe, independently checked full authority/bytes/IPv4/ICRC in10.68seconds.
This is additional TWO-STATE proof, not hardware/peer ACK/CQ signoff.
New production `rocev2_wqe_response_guard` adds full-packet integrity and
saved-peer/QPN/PSN/opcode/AETH/length protection BEFORE a full original READ
placement token/HLS replay. Native actual-response-to-executor/PCIe/fence
passes with HLS extraction/issued context/physical host/link/CQ MODELS, not
actual-HLS READ. Final portable038is live at checkpoint031, no309-method pass
claimed yet. All full requirements/physical negatives remain; see
`ROCEV2_WQE_RESPONSE_GUARD.md` for scope, retained failures and next real binding.

Progress030adds a real full-WQE/HLS-command memory executor. Complete saved
key/offset/length/tag, not HLS's narrowed address, drive the shared backend.
Actual coherent-SQ/SAME-MR-to-executor/scattered-PCIe source and destination/
fence cases pass; raw HLS and protected READ-response/CQ remain explicit models
there. A new actual-HLS source integration has a retained four-state timeout,
then a failed compiled001new-case termination check; a corrected fresh
compiled002build is live at checkpoint030, NOT a completed HLS pass. Additional
two-state scope remains distinct. Portable037passes297methods/520.468seconds;
source-checks041passes31batches/201methods including repeated source batches.
Memory events cannot stand in for RDMA completion; downstream owner
guards remain mandatory. See `ROCEV2_WQE_MEMORY_EXECUTOR.md` and checkpoint030
for terminal evidence, remaining scope and preserved failures. The broad goal,
all physical gates/exclusions and no-hardware-mutation boundary remain intact.

Progress029adds real owner-before-HLS SQ staging in the native-SQ top. Actual
coherent WQE/SAME-MR authorization precedes a complete guarded executor tuple,
then actual248-bit per-WR metadata with explicit key-valid/host bits and full
key0/VA64. Separate actual-HLS leaves verify packet generation; these are NOT
unified native local execution/DMA/ACK/READ-placement/CQ proof. A stronger
header check also exposed an existing actual RX parser defect: MigReq0x40
was incorrectly rejected as reserved. M0/M1now pass without bypassing MR/
peer/PSN/integrity gates; actual-HLS positive/protection cases verify both
acceptance and rejection. Path migration remains unimplemented. See
`ROCEV2_HLS_SQ_SUBMISSION.md` for precise scopes and preserved failures.
Final portable036passes281methods/456.483seconds; source-checks040passes
64methods. Fresh source-bound native/shared MR/memory units, real-HLS packet
and MigReq protection cases, legacy READ006/WRITE006and default parent015
pass; these scopes do not establish unified native local execution or CQ.
Checkpoint029retains all11full requirements, old physical failures and rollback
identities. General goal stays active/incomplete, hardware untouched.

Progress028adds an optional authorized local memory client sharing the ONE
existing native PTE/payload backend through a full-tuple registered arbiter.
Actual coherent SQ/SAME-MR-to-scattered-source READ and destination WRITE/
visibility-fence paths now pass with real RAM/router/mux/generic-PCIe RTL.
Two44.498-second-total native units explicitly MODEL the local transport/
executor/final WR-CQ owner and STUB HLS. Separate10method/37case four-state
arbiter units pass. Memory result handoff is NOT RDMA completion/unpin;
true HLS command binding/READ-response protection/wire/CQ/driver/provider
and remaining general RoCE features still require implementation. See
`ROCEV2_SHARED_PAYLOAD.md` for exact evidence and limits. Broad goal remains
active; no hardware state is changed or timing/CDC gate waived.
Final portable034passes269methods/391.948seconds and source-checks037passes
64methods. Additional compiled TWO-STATE native-memory-forward001passes
the original5incoming operations/ordinary-host checks plus coherent SQ and
65-byte local-source DMA in11.82seconds. It remains explicit MODEL-backed
for local transport/executor/final WR-CQ; not a physical/native RoCE completion.
Legacy READ005/WRITE005and default parent compile013pass current-source
rechecks. Checkpoint028preserves full requirements and all historical failures.

Progress027adds a source/offline native SQ top: actual SQC1@0x402000, coherent
SQ DMA and the original paged payload backend share one full-tag router; real
fetched WQEs enter the SAME native MR table through a fail-closed bridge.
Raw SQ-ring ownership and MR leases remain distinct to avoid management/
admission deadlock. Five bridge methods/16four-state runs and two native
integration units pass; generated-HLS priority001also passes the actual
inflight-SQ-fetch/revoke/stale-key-denial case in97.03seconds.
Additional compiled TWO-STATE forward001passes in11.67seconds, preserving
the original2WRITE/3READ/wire/fence/ordinary-host assertions plus one SQ fetch;
four-state full-forward001expired at120seconds and is NOT a pass. Downstream
executor/CQ owners are explicit MODELS, not local payload execution or WR
completion. Actual mqnic board-parent selection, Linux pins/MMIO/runtime,
executor/CQ/provider/verbs and all broader operations/recovery remain open.
The older isolated failed timing inputs are frozen/preserved but two original
fetch files now differ; no timing/CDC pass is inherited. Hardware untouched.
Final portable033passes257methods/331.997seconds; source-checks036passes
7batches/64methods. Fresh27-input kernel build004links22symbols without
installation/probing; default-parent compile012also passes, but does not
select this new native-SQ graph. Failed attempts and source supersessions
remain explicit in checkpoint027; the general goal stays active/incomplete.

Progress026further propagates the default-OFF shared MR client through actual
same-port/native wrappers, with independent route/fault-gated new admission
and continuous accepted-work ownership. Enabled actual-HLS native control003
passes13local queries/results and the original5incoming paged WRITE/READs,
actual generic-PCIe/parent-guard proof and ordinary host byte/sideband checks.
Fault004blocks new work after actual outer MAC-completion fault0xf2while
retaining accepted results and a deliberately uncertain downstream owner.
Two explicit-HLS-stub portable units additionally cover native local MR/STOP/
route/fault ownership. This is actual native WRAPPER integration, not genuine
host-SQ/local payload execution, CQ/provider/Linux runtime or deployed board
functionality. The source-frozen physical OOC003remains a failed, DIFFERENT
isolated graph; no new CAD/board timing or CDC pass is claimed. See checkpoint026
and `ROCEV2_SHARED_MR.md` for scope, preserved intermediate failures and bounds.

Progress025 connects the optional SINGLE shared-MR local client through the
actual paged and exclusive AXI-controlled responders. Independent PTE
management ownership avoids guard/admission feedback while retaining MR/PTE
mutation exclusion beyond local lookup and result handoff. Four actual-C/
stub units and four actual-HLS cases pass:19local lookups/results,3modeled
downstream leases,4incoming65-byte paged WRITEs and4independently checked
wire ACKs. Native/SQ/local payload execution/CQ/verbs remain unimplemented
integration, not inferred from these model-backed cases. See
`ROCEV2_SHARED_MR.md` and checkpoint025for exact scopes and retained inputs.

The exact13-input shared-DMA isolated OOC003/session91411is terminal1, not
live: original4ns WNS-2.897ns/TNS-12549.917ns,0hold/pulse failures, all12
check_timing categories0,0DRC errors/critical warnings and24088fully-routed
nets/0routing errors. The actual RAM-WR span/fault/drain/SQ-config path still
needs a safe registered boundary. This is a preserved failed physical gate,
not timing closure or authorization to deploy. No hardware/driver/network/
fan/BIOS/reboot state is changed; the broad goal stays active/incomplete.

| Area | Verified so far | Still required |
| --- | --- | --- |
| Previous initiator | Native IPv4 READ/WRITE and all-byte BAR/receiver verification, previous milestone | Keep passing on each resulting new image |
| Remote memory protection |8-entry MR/full-key/PD/access/range/epoch and HLS paged responder; exclusive transactional MR/PTE/AXI controller blocks publication/invalidation until proof | Board/host-DMA integration, real parent drain, persistent host epoch watermark and outer abort/reset recovery |
| Responder transport |19-input actual-HLS protected sequence plus6boundary operations; invalid requests have no memory side effects; highVA/DMA64, padding, committed WRITE-before-READ, ACK gating and PSN wrap pass offline | Native protected responder, proper wire NAK/retry/error recovery; broaden the1QP/1outstanding/<=4096B subset |
| Host memory / DMA | Actual HLS/native control/same-port/generic PCIe component tests plus real concurrent SQ/paged backends, full-tag/RAM router and actual parent guard with modeled host/link; source-bound progress checkpoints record current regression. Earlier physical passes are not current signoff | Native app/board integration, persistent lifetime/abort and runtime kernel binding; no current native host DMA claim |
| Kernel/provider | Actual ib_umem lifecycle, MR callbacks, IRQ-fast MR refs and coherent SQ/work ownership compile/link against running6.17headers; same-C primitive/HW/CQ-model tests pass | Runtime bus/MMIO/pin binding, RDMA device/object lifecycle, native queue CSR/CQ callbacks, standard verbs/provider and bounded interoperability tests |
| Other operations / concurrency | Not claimed by this stage | SEND/RECV/immediate/Atomic and necessary QP/queue operation; small concurrent functional tests, not scale qualification |
| Reliability / compatibility | Earlier WRITE003 fault evidence and READ/WRITE001 config recovery remain separately scoped | Required NAK/RNR/loss/recovery and congestion/compatibility behavior on the eventual image; no silent relabeling of old results |

The new component is `rdma/rnic/rtl/rocev2_mr_table.v`, outside the immutable
verified board sources. Keys contain the complete slot generation; invalidation
does not reset it, and exhaustion refuses reuse. The table checks the trusted
PD, basic access permissions,64-bit range/overflow, contiguous DMA translation
and atomic authorization shape. Denials return zero address/offset/extent.
Management cannot mutate a pending lookup/result or a nonquiescent external
memory lease. It does NOT execute an Atomic, perform DMA, pin user pages,
generate an RDMA error packet or by itself implement `ibv_reg_mr`.

### Protected actual-HLS responder integration

`rdma/rnic/rtl/rocev2_protected_responder.v` now connects that table to actual
complete-frame integrity validation, trusted QP/PD/peer/expectedPSN context,
the unchanged HLS transport, full-width authorized backend commands and
completion-gated replies. Saved authorized context supplies DMA64; ALL94
meaningful truncated HLS command bits must match before any backend command.
Wire pad bytes are removed. No success response beat is exposed until a
matching successful backend completion; MR/QP changes remain blocked until
the response's final beat drains. Malformed command/data/completion causes
a sticky fault, not an unsafe lease release. This is one QP/one outstanding/
IPv4/WRITE_ONLY/READ_REQUEST1..4096B, not a complete RC/host-DMA implementation.
The backend is modeled RAM, not host-copy substitution or PCIe DMA.

Selected contiguous actual-HLS evidence `rocev2-rnic-protected-responder-005.json`:
19input frames,13local rejections,1ICRC drop,5authorized commands/replies;
wrong WRITE/READ key, wrong PD, read-only WRITE, below/end/overflow ranges,
wrong QP/peer/PSN, length mismatch, unsupported FIRST and stale-key-after-reuse
all refuse memory access. Correct operations recover with the same expected
PSN. VA`0xfedcba9876543210` translates to DMA`0x8123456789abc210`, retaining
all64bits. Both65-byte WRITEs and all three65-byte READs compare every byte;
MR invalidation is held off through data, delayed completion and output drain.
The first001attempt failed because Verilog constant-argument header functions
did not depend explicitly on the changing header; the functions were fixed
to take header data as an argument. Its failure log remains preserved.

`rocev2-rnic-protected-boundaries-004.json` additionally passes six actual-HLS
WRITE/READ operations at1/64/4096bytes,4161bytes compared in EACH direction,
pad guard bytes unchanged, and24-bit PSN wrap from0xfffffe through0.
All11successful actual response IPv4 checksums/ICRCs, QPN/PSN/success-AETHs
and payload bytes are independently checked. No board/native/PCIe claim.

The previous `make -C rdma/rnic check` passed32test methods: the original8MR suites,
10admission/backend-contract units (14runs including corruption subcases),
and14Corundum DMA-backend units, including the actual15-bit RAM-address geometry.
The latter explicitly stub the transport to inject bad command address/
length/host/route/QP/direction, bad read/write keep/last and failed/wrong-tag
completion, and check that pending invalidation during partial reception
cannot deadlock the frame. They are NOT HLS wire evidence; the two actual-HLS reports above
provide that separate evidence. See `ROCEV2_RESPONDER_API.md` for the backend
contract and explicit early-error/abort/reset/NAK limitations.
Selected admission unit record is`rocev2-rnic-protected-unit-008.json` (terminal0).
It now includes required epoch setup and registered packet replay; current
MR evidence003adds four epoch/config-capture suites (12MR methods total).
The earlier002run passed all18methods but failed report saving because
`make -C` changed the relative output directory; it remains a failed command.
The reporter now resolves relative output paths against the repository root.

### Protected DMA integration and source-frozen builds

`rocev2_corundum_dma_backend.v` now connects authorized commands to real
Corundum app DMA descriptors, segmented staging RAM and AXI source/sink
clients. WRITE waits for staging commit, DMA write status and a1B host-read
visibility fence before completion. Failed READs drain zero instead of stale
RAM, then an error, so the protected frontend cannot expose a success reply.
Wrong-tag or malformed-RAM faults retain outstanding DMA ownership; disable
stops only new commands. Full-address/byte-range/RAM-drain guards are tested.
See `ROCEV2_DMA_BACKEND.md` for actual engine ordering prerequisites, error
cleanup and the explicit lack of pinned-page/native/PCIe-engine verification.

Selected `rocev2-rnic-dma-backend-003.json`:14tests, actual Corundum RAM/source/
sink/ingress skid but modeled descriptor engine. Selected `rocev2-rnic-protected-dma-004.json`:
actual HLS+MR+backend+staging integrated;19inputs,13rejections,1ICRC drop,
5successful operations/7DMA descriptors including2visibility fences. Actual
65-byte WRITE staging contents and all three65-byte network READs match.
The old direct memory source/sink is removed in this integrated test. The
PCIe descriptor engine/link/host memory remains MODELED, not native DMA.
The integrated test now uses actual board RAM_ADDR_WIDTH15/segment-address9;
default16-bit geometry is separately tested. Existing config derives15from
32KiB TX/RX RAM, not the application module's16-bit default.

`rtl/responder_synth.tcl` starts a fresh isolated actual-HLS protected top
synthesis/resource estimate on`xcku3p-ffvb676-1-e`. It is NOT a full-board
route or a timing pass. Current build:
First build`responder-synth-uthdlTJ1/impl`/session18640is terminal0. Its
source-bound synthesis record`rocev2-rnic-responder-synth-001.json` has35290LUT,
67078FF/41BRAM, but isolated post-synth4ns WNS-0.508ns/WHS+0.016ns and1839setup
failures. This is NOT a timing pass. The worst path has19logic levels/8CARRY8
stages from `wire_remaining` through a variable64-bit mask shift/subtract
and HLS memory-write ready/CE feedback. Mask generation was replaced with
equivalent parallel constant-lane comparisons. Actual-HLS sequences and all
32portable tests pass on that new source; older002/001reports remain historical.

Second protected-top synthesis`responder-synth-gASoEmuF/impl`/session12642is
terminal0:35234LUT/67078FF/41BRAM, post-synth WNS-0.376ns/WHS+0.016ns,5setup
failures. The old mask path is now+0.218ns. Remaining worst path is async
frame-keep RAM replay -> second integrity gate (15logic levels).
`rocev2-rnic-responder-synth-002.json` binds this evidence. It is still an
ESTIMATE, not a physical pass or definitive physical failure.

First protected physical route`responder-route-odcgsomu/impl`/session10878
terminated1with WNS-0.704ns/WHS+0.024ns; saved record
`rocev2-rnic-responder-route-001.json` preserves that failure. Replay RAM ->
second ICRC and direct config-input ->65-bit MR-end validation paths failed.
A real replay skid register and captured/pipelined MR management now cut
those boundaries, without editing baseline HLS/integrity sources. Required
SET_EPOCH blocks registration/admission until a trusted generation floor.

Third synthesis`responder-synth-ZyFTnpv8/impl`/session46167is terminal0:
35369LUT/67782FF/41BRAM, WNS-0.097ns/WHS+0.016ns/4setup failures, now in the
first admission-integrity gate. `rocev2-rnic-responder-synth-003.json` records
all148unchanged inputs and artifacts. This remains synthesis ONLY, not a
timing pass. Same-source physical route002in
`responder-route-zLPzZFZU/impl`/session27101terminated0: isolated4ns
WNS+0.122ns/WHS+0.023ns,0setup/hold/pulse failures,32090LUT/67772FF/41BRAM,
91651routable nets all routed,0routing errors,0DRCerrors/critical,1OOC
no-routable-output-load warning. Record`rocev2-rnic-responder-route-002.json`
binds all148unchanged inputs AT TERMINAL. That is a historical pass BEFORE
new key/offset/pause ports; it is not physical signoff for the changed guard,
combined paged top or native board.

First backend physical probe`dma-ooc-PfmNQrXv`/session28370terminated1:
WNS-0.057ns/WHS+0.043ns, one input-keep -> sink status-FIFO path failed.
A validated input skid register was added; original Corundum source is
unchanged. Second backend probe`dma-ooc-obPQcKuZ`/session76164is terminal0:
isolated4ns WNS+0.027ns/WHS+0.012ns,0setup/hold/pulse failures,
3981LUT/3029FF/8BRAM,0DRCerrors/critical and1OOC no-output-load warning.
`rocev2-rnic-dma-ooc-002.json` binds all6frozen inputs and actual15-bit RAM
geometry. This historical isolated pass, before registered extents, is NOT
current full-board/native DMA signoff.
The script's explicit isolated4ns I/O timing model is applied after synthesis;
placement/routing/native clocks and the original board gates remain separate.

`rocev2-rnic-mr-rtl-001.json` records8short actual-RTL suites including an
independent integer oracle/randomized management, invalid keys/PD/permissions,
64-bit edge bounds, stale keys/exhaustion and stalled-response ownership.
`rocev2-rnic-mr-ooc-001.json` records isolated target
`xcku3p-ffvb676-1-e`/4ns WNS+0.308ns, WHS+0.050ns,0failing endpoints,
0DRC checks,1455LUTs/2558registers. Its explicit I/O model is inputmin0.2ns/
max0.5ns, outputmin0/max0.5ns. This is NOT full-board/native signoff.

The first unprotected-HLS characterization attempts are retained as failures:
001used a declaration-time reset and timed out;002/003wrongly assumed ACK
credit bits must match the CX455A's0x1f although HLS emits legal success0x00.
The corrected probe checks the actual success syndrome bits, still rejecting
NAK/RNR. None is a board/native protection pass. The deployed ingress still
rejects these incoming request opcodes; it is not exposed by the probe.

Selected characterization is `rocev2-rnic-responder-characterization-005.json`,
terminal exit0: valid-key and wrong-key WRITE each produce a68-byte memory
command carrying all65payload bytes plus3wire pad bytes and a valid ACK;
valid-key and wrong-key READ each emit a65-byte read command and return all
65reference bytes in a valid READ response. Both wrong-key requests still
cause memory side effects in the UNPROTECTED transport, proving the missing
authorization guard rather than demonstrating a protected responder.
A fifth READ to`0xfedcba9876543210` emits only the lower48address bits in
the memory command. Source`memCmd` also interprets address bits48..52as
internal routing fields. Preserve/check full virtual address/context before
this boundary; never pass the truncated output straight to host DMA.
All selected actual response IPv4 headers and ICRCs are independently
checked, with full response hex, memory-write bytes and payload digests in
the record. Earlier004 completed the initial four cases but lacks this
explicit WRITE-response IPv4 check/raw-wire evidence and is not the selected
characterization. No native responder or DMA capability is claimed.

### Required epochs, registered-page library and paged DMA

The protected MR table now requires explicit SET_EPOCH before registration
or packet admission. Captured, pipelined configuration avoids trusting fields
after their handshake and rechecks external quiescence before mutation.
The replay skid preserves accepted packet data/keep/last under stalls. Current
actual-HLS responder005/boundaries004/contiguous-DMA004 and36portable RTL
methods pass on those sources. Their wire counts/all-byte checks remain the
same; they still do NOT implement native incoming requests on the live image.

`kernel/mr.c` uses actual ib_umem pin/map/release APIs and immutable DMA page
population, with no contiguous-address or CPU-copy shortcut. Ambiguous
publish/invalidate responses quarantine pool-owned mappings rather than
unpinning. Cookie/key/epoch proof, module/device ownership and pool teardown
are explicit. The compile/link harness builds against the running6.17.0-1033-oem
kernel (W=1, matchinggcc13); no module was loaded or real pages pinned. It
does not register a dummy RDMA device. Real hardware callbacks and driver/
provider/verbs still remain. See `ROCEV2_HOST_MEMORY.md` for the lifecycle,
publication sequencing and sources.

The shared C contract passes9tests/3330queries with UBSan and an independent
integer oracle (`rocev2-rnic-mr-contract-001.json`). The new FPGA page table
passes8actual-RTL suites against that C contract
(`rocev2-rnic-page-table-001.json`):8MRs,256x4KiB pages each, DMA64, independent
user-page offset, complete-table seal, stale-key refusal and full-operation
range validation before the first page piece. This is address translation,
not execution of DMA or replacement for QP/PD/access checks.

`rocev2_paged_memory_backend.v` now connects that table, the new page splitter
and the existing actual Corundum RAM/source/sink/backend.12finite2.6s tests
pass (`rocev2-rnic-paged-backend-003.json`), including all1/31/32/63/64/65/
4095/4096B payloads, scattered DMA64 pages up to the top64-bit page, nonzero
staging offsets, exact host bytes/guards, all-piece completion then one
readback fence, partial READ/WRITE/fence errors, stale/unsealed/range denial,
wrong/colliding status, disable, held invalidate and RAM-fault halt. Any fault
retains mappings and withholds page-release proof, even after matching late
statuses. Partial WRITE errors may have unfenced posted traffic; only a real
parent-engine stop/drain cleanup can resolve it, never an FSM reset/timeout.

The descriptor engine, host memory and ordered visibility are STILL MODELED.
The separate paged-backend physical probe (`paged_backend_ooc.tcl`,
`paged-ooc-yi05KafJ/impl`/session63097) is terminal0: isolated4ns WNS+0.087ns/
WHS+0.023ns,0setup/hold/pulse failures,8835LUT/6816FF/12BRAM,0DRCerrors/
critical,1OOC no-output-load warning. Record`rocev2-rnic-paged-ooc-001.json`
binds all9unchanged inputs AT TERMINAL, before the later registered-extent
change. This historical result is not current full-board/native signoff.

### Integrated actual-HLS paged responder

`rocev2_protected_responder.v` now retains full authorized RETH key and the
MR-relative offset from the SAME successful lookup as length/tag/address.
`rocev2_paged_responder.v` connects those to the actual paged backend: no
48-bit reconstruction, second RX parser, raw-offset physical DMA or CPU-copy
shortcut. It forces the unused contiguous DMA base0 and hardcodes the real
external admission-pause feature. Pause blocks only new first checked beats;
accepted partial packets/memory/TX continue draining. MR and PTE commands,
their capture/apply pipelines and held responses are mutually exclusive,
including QP configuration. Backend faults close admission; global quiescence
requires both config paths, memory and final wire response ownership.

Selected`rocev2-rnic-paged-responder-003.json`/session2209is terminal0: actual
composite/generated HLS,19frames/13rejects/1ICRC drop/5operations. All65B
requests cross scattered DMA64 pages as3B+62B, with user first offset3565
independent of MR-relative528; full keys8/16 remain bound under stalls.
All130WRITE staging bytes,195network READ bytes, complete host guard memory
and IPv4/ICRC/QPN/PSN/AETH are checked.12physical descriptors use unique
tags1..12 (4WRITE/6payload READ/2fences). Invalidation waits for final TX.
The first direct-connection001report misserialized integer-width direction
flags; raw logs retain correct directions, but that report is not selected.

`rocev2-rnic-paged-responder-boundaries-001.json`/session86429is terminal0:
six actual-composite WRITE/READ cases at1/64/4096B,4161bytes in EACH direction,
PSN wrap0xfffffe->0, all wire checksums, host guard/pad bytes and13exact page
descriptors independently compared. User first-page offset4093makes the
64/4096B cases cross two unrelated DMA64 pages, including the top64-bit page.

Actual-HLS DMA READ-piece2, WRITE-piece2 and readback-fence errors each pass
in`rocev2-rnic-paged-responder-{read,write,fence}-error-002.json`/sessions
83189/14160/14479: one accepted command/error status reaches guard fault34,
zero successful wire beats/responses or completed operations; global
quiescence/page-release proof remain false. Their001attempts incorrectly
applied the success-only drained assertion to an error-retained lease; raw
failure logs remain preserved. Corrected tests still require drain for
success and explicitly FORBID unpin proof on each error. No timeout/reset
cleanup is invented, including unfenced partial posted WRITEs.

Full68method suite is terminal0in session93421/`rnic-all-rtl-003.log` (171.5s):
12MR/10admission/14contiguous-DMA/9Ccontract/8page-table/12paged-DMA/3composite
control methods. Current records: MR005, DMA-backend005, MR-contract003,
page-table003, paged-backend005, admission008. The3composite control methods
were rechecked on the final error-probe helper in33.7s/session86676,
`rocev2-rnic-paged-responder-unit-003.json`; no RTL changed after the full68run.
These control cases explicitly stub transport, not additional HLS wire proof.
Current source checks and `git diff --check` also pass (session72121,
`rnic-source-checks-004.log`). Read-only live preflight005remains successful:
version2WRITE-DONE/core reset/TX quiescent, run generation11, both25G test
links/namespace identities preserved; no packet/QP was created. Both previous
native source manifests remain unchanged. No exact live-bit readback claim.

The source-frozen ACTUAL PAGED top synthesized via
`rtl/paged_responder_synth.tcl`, build
`rdma/rnic/build/paged-responder-synth-uZNe1mHJ/impl`, raw log
`rdma/logs/rnic-paged-responder-synth-001.log`, session51850is terminal0:
44265LUT/74026FF/53BRAM, post-synth4ns WNS-1.253ns/WHS+0.016ns/4200setup
failures. Worst estimate is rst input -> HLS FIFO full feedback,17logic levels.
Record`rocev2-rnic-paged-responder-synth-001.json` preserves this synthesis
ONLY result; it is not physical signoff. Physical route001in
`paged-responder-route-ufqYJr8b/impl`/session93891, raw log
`rnic-paged-responder-route-001.log` terminated1with4ns WNS-0.705ns/
WHS+0.019ns/4277setup failures,41145LUT/74018FF/53BRAM,0DRCerrors/critical.
Its156inputs were unchanged AT TERMINAL; immutable record
`rocev2-rnic-paged-responder-route-001.json` preserves the failure, not signoff.
The actual worst path is read-descriptor length -> RAM-end add -> enabled-byte
range guard -> RAM-pending/drain -> backend FSM CE,15logic levels/3CARRY8.
This actual path, not the pre-synth reset estimate, determines the next fix.
No actual hardware traffic, FPGA programming,
kernel-module load, network/fan/BIOS change, commit/push or reboot occurred.

### Transactional AXI control and real kernel callback source

`rocev2_mr_control.v` now owns every raw MR/PTE/QP config port, owner cookie64,
subcommand sequence32, allocated key and building/active/tainted state. It
holds admission through BEGIN/actual MR-key allocation/PTE BEGIN/all PAGEs/
SEAL/held replies, checks actual parent drain again after epoch seed and
both invalidation replies, and never turns timeout/reset into a free proof.
Known-absent slots can issue actual absence+generation+drain certificates for
BEGIN that never queued; occupied slots still require matching owner/key.

`rocev2_control_regs.v` snapshots all21staging words atomically on doorbell,
validates reserved widths, retains stalled commands and permits response
consumption only by exact sequence ACK. This pinned Corundum AXI adapter
returns OKAY even on register timeout, so sticky MMIO_ERROR is mandatory.
`rocev2_controlled_responder.v` connects mailbox/controller/HLS paged path
and hides ALL raw config inputs. See `ROCEV2_CONTROL_ABI.md` for the actual
new ID/ABI, register map, commands/proof flags and explicit recovery limits.

Controller004passes11actual controller/MR/PTE tests (QP/parent drain modeled);
control-regs004passes6actual AXI tests against the kernel ABI, including
independent AW/W, byte strobes, backpressure, snapshot/busy/ACK/error ownership.
Controlled-responder003uses actual generated HLS AND AXI-only configuration:
20matched host commands/replies/3MRs,19frames/13rejects/1ICRCdrop/5successful
operations,130WRITE/195READ bytes; invalidation waits for an active WRITE's
memory/final-TX completion, then old key is denied and fresh key16works.
The AXI host/PCIe descriptor engine/host memory/parent drain are MODELS.

`rnic_io.c` supplies the actual shared C mailbox client, all metadata readback,
reply identity/key/flag checks, pending-before-doorbell and retained ambiguous
errors. I/O003passes10C/UBSan tests; output proof is zero on failure, error
responses have no memory proof, wrong/late/ambiguous ACK is never guessed.
`rnic_hw.c` implements real kernel readl/writel/time/sleep, BEGIN/load actual
ib_umem-mapped DMA pages/SEAL and INV callbacks, returning only hardware-derived
proof. Build005/session24404is terminal0against running6.17.0-1033-oem (W=1,
matchinggcc13, BTF skipped withoutvmlinux). An immutable .ko copy is bound in
`rocev2-rnic-kernel-mr-build-002.json`. No module is loaded or live MMIO/pins
executed, no bus driver/ib_device/provider registered. Earlier003/004builds
failed on a poll_wait helper-name collision; the namespaced fix is compiled.

Full95method suite is terminal0in session63689/`rnic-all-rtl-005.log` (173.8s):
the previous68plus11controller/6AXI/10I/O methods. Current full-suite records:
MR007/admission010/DMA-backend008/MR-contract005/page-table005/paged-backend008/
composite-unit005/controller004/control-regs004/I/O003. No long native test.
The previous004batch also passed before the extent-register change.

### Registered RAM extents and actual full control-top build

The actual failing DMA bounds path now prepares `dma_read_ram_end` in the
SAME issuing stage as descriptor RAM address/length/valid: payload-read end
is its exact length; fence end is constant fence-address+1. The rounded
WRITE-word bound is captured at authorized command acceptance. Bounds are
valid BEFORE any physical descriptor can handshake and remain owned during
stalls/faults. No byte/word range, tag, RAM-drain or completion rule was relaxed.
This removes serial extent addition from the following protection/drain path;
it is a candidate timing fix, NOT a physical pass.

Actual controlled-HLS003again passes all20CSR replies/19frames/5operations
on these sources; actual paged-HLS boundaries002passes all4161bytes each
direction/PSN wrap/13exact descriptors; each DMA error003again produces
guard fault34/no success/no page release. Standalone actual-HLS contiguous
backend regression005also passes. Full95batch005uses the same current RTL.

New physical build preparation now includes the ACTUAL AXI/controller top,
not merely the earlier paged composite. `rtl/controlled_responder_synth.tcl`
runs in`rdma/rnic/build/controlled-responder-synth-2i2PSnYr/impl`,
raw log`rnic-controlled-responder-synth-001.log`, session46864. All162inputs
remain frozen until terminal. No current synthesis/physical/full-board/CDC
pass is claimed; subsequently route that exact source-bound DCP and preserve
all native clocks/setup/hold/skew/routing/DRC/conditionalCDC gates.

Still required NEXT: resolve the actual combined physical timing gate (then
include the NEW control/CSR top in resulting gates), integrate real parent
PCIe app-DMA/TLP and a separate native board profile, bind actual bus/kernel
device/runtime pins and truthful standard RDMA interfaces. Persist host epoch
watermark and complete proven lost-ACK/hot-unplug/reset cleanup. The compiled
callbacks and model-backed tests are not a native host-memory/RNIC pass.

### Actual generic PCIe path and controlled-top physical build

`tests/probe_controlled_pcie.py` now connects the ACTUAL controlled AXI/HLS/
guard/paged/staging path through actual3-port interface/application and
2-port control/data DMA muxes into the actual generic `dma_if_pcie` read/write
engine. There are no fabricated descriptor statuses or direct RAM host agents
on this path. Parent drain is derived from actual busy/accepted-descriptor/
pending-mux/TLP/RAM signals, not tied high. PCIe hard IP/link/TX-sequence source,
root-complex/host memory and AXI host remain MODELS; runtime pins/kernel
callbacks/native PCIe are NOT exercised.

Normal005/session13833is terminal0:20AXI replies,19frames/13rejects/1ICRCdrop,
5operations,12exact physical descriptors through both actual mux levels,
8READ/4WRITE TLPs/2readback fences,130WRITE/195READ bytes and all host
padding/guard memory checked. Each posted TLP's TX acknowledgment is withheld
64simulated cycles (256total), without premature successful DMA/network
completion or parent-drained proof. DMA64/requester0x8200/TC0/attr0 and
stalled-beat ownership are checked. Actual UR completion tests READ003/
session45634and fence003/session35418are both terminal0: generic engine
reports error10, guard enters34after required zero/error drain,0success
responses/completed operations and no page-release proof. Earlier failed
testbench framing/stage-order/error-number assumptions remain in their logs;
no DUT guards were weakened. Details are in`ROCEV2_DMA_BACKEND.md`.

The native-shape mux connection exposes a necessary profile change: board
DMA tag width16leaves only13application bits after routing. The new profile
must instead use engine tag width19to retain the page engine's complete16bits;
do NOT truncate them. This offline test uses those exact widths, app RAM
select1/engine select4,15-bit RAM address/segment-address9and256-bit TLPs.
The old native config/rollback files remain untouched.

Controlled-top synthesis001/session46864is now terminal0. Its162inputs were
unchanged at terminal; record`rocev2-rnic-controlled-responder-synth-001.json`
binds all generated artifacts. Resources:45795LUT/76792FF/53BRAM. Post-synth
4ns WNS-2.267ns/WHS+0.016ns/5300setup failures, no hold/pulse failures; worst
ESTIMATE is DMA RAM address -> per-byte bounds -> pending/drain -> endpoint
quiet -> controller command-valid (21levels). This is NOT a physical pass or
a substitute for actual placement/routing. Same-source physical route001is
live in`rdma/rnic/build/controlled-responder-route-bzj5YDWa/impl`,
session76914/log`rnic-controlled-responder-route-001.log`; all162inputs and
the route script/DCP remain frozen through terminal. Do not restart it because
the log is temporarily unchanged and do not edit its RTL while it runs.

Read-only native preflight007is terminal0and still finds original version2
WRITE-DONE/core reset/TX quiet/run11and the existing25G test identities.
No packet/QP/configuration write is created. Source checks006also pass. The
previous full95batch005still binds the current unchanged production RTL/C.
No new native traffic/programming/module load/network/fan/BIOS change,
commit/push or reboot has occurred. Full broad requirements remain open.

Next native board integration must route incoming requests BEFORE the old
`rocev2_rw_ethernet_rx` (which deliberately drops unsupported RoCE requests
when enabled), retain the original initiator READ/WRITE path and its distinct
reset/drain ownership, and classify shared MAC completions without confusing
host, initiator and responder tags. The new control aperture must not alias
the original version2 registers/capture RAM. Enable actual app DMA with
full19-bit parent tags, connect real parent engine/TLP/RAM fault/drain evidence
instead of a constant, then run the resulting FULL board clock/route/skew/
DRC/conditionalCDC gate before any short thermal-supervised native test.
The offline integrated engine test does not complete any of those native gates.

### Same-port composition while the controlled physical route runs

Latest same-port integration source and finite evidence are documented in
`ROCEV2_SAME_PORT.md`. New`rocev2_dual_ethernet_endpoint.v` puts request steering
before the unchanged original initiator and merges responder Ethernet frames
with separate MAC completion ownership/real response-TX drain. Actual same-
port responder/host case001(session69023), original65-byte WRITE001(session
28507) and original65-byte READ001(session34679,65capture/127sentinel bytes)
are all terminal0. Actual protected/control/HLS and native-shape mux/generic
PCIe RTL are present, but MAC/peer/AXI/config/hard-IP/link/host remain MODELS.
Separate slave ports still need actual nonaliasing BAR decode/enforcing
Ethernet config CSR, native app/parent wiring and resulting full-board gates.
No native capability or physical signoff is inferred from these new tests.

### Native control and reset characterization

The new actual native single-AXI map/Ethernet-configuration CSR is described
in`ROCEV2_NATIVE_CONTROL.md`:6CSR +3decode units and full104batch007pass,
with old/new slave MODELS explicitly identified for the decode units.
Whole-path native-control003FAILS at first WRITE/guard35. Both diagnostic
sessions18724(native exact cause) and13883(clocked-reset same-port) are now
terminal1: actual HLS TX integrity failure, no RX integrity failure/overflow,
no duplicate memory command/data and no success/release proof. The same
failure without the new crossbar rules out native CSR corruption.
The cold-reset case32568is terminal0, with all five protected operations.
Actual generated IPv4 static-constructor flag is not reset by the old
default control-only policy, while its header write occurs later in the
pipeline. A reset interrupt can leave flag1but version/IHL0and TTL0.
Narrow actual-generated-module characterization003confirms8invalid state
observations out of88and valid cold startup; this is an expected-defect
characterization, NOT a release reset pass. No raw config bypass, internal
force, header repair or weakened integrity gate is used.
Separate source-frozen reset-all HLS candidate build6858is terminal0 under
`rdma/rnic/build/reset-all-hls-x41g7249`; all inputs unchanged,138outputs,
new aggregate SHA256`5fab3e92f5b7d08f03c3b7c0dc1d85dfbbb84faca43a2f062dd5357104ee3a96`.
The narrow new-module test passes all88observations. It does not overwrite either the
pinned READ sources or the old138-file generated baseline. Full-path reset,
protocol and physical checks of this new candidate remain required; whole-
path native004, legacy READ/WRITE002and PCIe UR read/fence004are now terminal0.
Native004uses actual24-bit AXI crossbar/config CSR/mailbox, actual same-port
HLS/protection/page/staging/mux/generic PCIe RTL:21control replies,19frames,
13denials/1ICRCdrop/5ops,130WRITE/195READ bytes,8read/4write TLPs and2fences.
Ordinary host RX/TX sidebands and MAC completion ownership also pass.
Both actual UR cases produce guard34/no success/no page-release proof.
The previous controlled physical route76914is now terminal1, WNS-1.174ns/
WHS+0.012ns/7173setup failures; its source-bound failure record is preserved.
Do NOT treat that process as live or restart it because an old checkpoint
listed it. Close actual timing and new whole-path failure before native use.

The public backend drain proof now uses registered-zero RAM pending counts
and absence of any current RAM/status offers, not address-dependent
predicted pending-after arithmetic. Actual status retirement STILL uses the
unchanged predicted proof and all exact byte/tag/range/fence checks. This
can only withhold/delay public proof, never advance release. Four new tests
check unsolicited RAM/read/write-status offers withdraw proof BEFORE the
fault clock. Backend011passes18methods; full108method batch008/session4644
is terminal0(179.038seconds) and backend012binds the same source. Native
endpoint OOC synthesis002/session35007is now running, with a frozen copy
of the full new single-AXI/dual endpoint and new HLS inputs. It still excludes
the PCIe parent/hard-IP/board and cannot provide native signoff. Attempt001
failed before synthesis because the reset-all output has no external.dat
files;002handles an empty optional data-file list. No constraint was relaxed.
No new physical timing result is inferred from this change.

### Separate native app and actual PCIe parent proof

`ROCEV2_NATIVE_PARENT.md` records the new separately patched parent/core/app/
config candidate. Original parent/app/config hashes remain unchanged. New
ASN1/app-DMA/19-bit parent tags preserve16application bits; actual busy/
descriptor/status/RAM/TLP/error proof feeds actual mux-stage/leaf quiescence.
Unused control RAM refuses commands instead of fabricating completion.
An offered-first-beat ownership module stops new frames after fatal without
withdrawing stalled valid or cancelling partial frames. Its6unit cases and
parent guard12unit cases pass. Actual parent/core/app hierarchy elaborates;
the board explicitly overrides MAC tags to16, not the lower core default6.

Parent-guard native-control001/session16744and actual UR read/fence001
sessions57134/87495are terminal0: actual guard replaces the testbench proof
expression, no model host counters feed it, original full-path assertions
remain. Whole patched parent hierarchy is separately compile-only, NOT this
functional test or a native board pass. Full130method batch010/session40553
is terminal0(172.842seconds); parent guard003/RX002reports bind current
sources. Enhanced transport002normal/session60586and UR read/fence sessions
72353/63477are terminal0and explicitly assert actual parent fault0for normal
completion and fault1at UR error10. The earlier124batch009predates the final
offered-beat/control-RAM refinement.
The original186input endpoint OOC synth35007is now terminal0with all source/
frozen inputs verified; it does NOT include this larger parent/app profile.
Reset-all estimate135454LUT(83.24%)/192514FF/168BRAM tiles; unchanged4ns
WNS-1.011ns/WHS+0.016ns/2914setup failures, unplaced timing only. A new
source-frozen STATE-reset HLS resource candidate/session40530completed0;
the following section records its separately scoped constructor, functional
and synthesis evidence. Area risk is not a proven final full-board capacity failure.
Full board physical/CDC, parent-fault driver visibility/outer reset ownership
and real kernel RDMA/provider/verbs/broad protocol requirements remain open.

### STATE candidate and actual full-board analysis

`ROCEV2_BOARD_ANALYSIS.md` records terminal STATE HLS/88constructor checks,
actual native/control/parent-guard/legacy/UR cases, original3x65/3x4097READ,
3x65WRITE,2x4097warm/stale/host routing and8QP timer phase regressions.
All selected cases pass, with their model/two-state scopes explicit; timer
Icarus001hit60second wall bound, same assertions pass compiled timer002.
STATE HLS estimate is unchanged. Same-top STATE synthesis7120completed0:
135314LUT(83.16%)/192339FF/168BRAM tiles, only140LUT/175FF less than ALL.
At unchanged4ns, unplaced WNS-1.074ns/3193setup failures, WHS+0.016ns/0hold
and0pulse failures. STATE alone does not solve area/timing. Its worst path
is reset to an HLS command FIFO; this is not a routed/full-board result.
Read-only ALL hierarchy audit001 also shows actual577SRL storage for a
nominal1024-bit packet FIFO, so apparent padding there is already eliminated.

The new fail-closed FULL-board analysis snapshot selects294actual HDL,
13unchanged constraints and3PCIe/PHY/VIO IP generators, separately patched
actual parent/core/app/config. Real source-only snapshot validation passes;
actual full board session5544was launched through IP and top synthesis.
Its driver stops at routed checkpoint/reports, with no image or programming
command. Snapshot/corruption/no-overwrite/path quoting tests join the full
136method batch011, terminal0(172.001seconds). No full-board timing/CDC/native
pass or standard kernel RDMA success is implied. Broad remaining scope stays.

The subsequent primitive audit attributes much of the rebuilt FIFO total
to absorbed resettable-RAM `written` logic. A separately frozen candidate
sequentially clears all2000metadata entries before accepting requests,
with resettable sweep index/completion and no reduced protocol capacity.
Metadata-reset HLS68644completed0,138files hash60c9a20e; HLS-only estimate
24981LUT/64294FF versus STATE32097LUT/84023FF. New candidate actual table
four-state test40654passes8024checks/16resets including interrupted sweeps;
IPv4constructor88checks also pass. Endpoint estimate69986subsequently
completed; its current result is recorded below.
Full portable139method batch012is terminal0(182.686s), source checks011also0.
New-candidate full-path Icarus cases hit60second wall limits (124, not a
protocol result). Initial compiled two-state attempts ended1at compile
deadline with generated C++ scope errors, before any simulation. Retried
checks55072/35694disable C++ function splitting but also reached the180second
compile limit, with no observed C++ scope error and no simulation outcome.
Third attempts44081/60287keep all RTL/bench assertions unchanged, use separate
C++ files/compiler-O0,600second binary-build limit and unchanged30second
simulation limit. Their exact inputs/bench hashes are saved before compilation;
their terminal results are recorded below. Owned process-group timeout
cleanup is tested.
No full-board source selection/image/hardware or broad RNIC completion is
implied by these module/area improvements; see BOARD_ANALYSIS for exact scopes.

### Serialized logical control detach

Shared `as02_ctl_detach()` now makes an attachment terminal without transport
access, reset, ACK, sequence reuse or deletion of pending/uncertain owner
metadata. Subsequent commands/reconciliation return-ENODEV and zero output,
even for a valid late drain reply. Actual kernel `as02_rnic_hw_detach()`
shares the I/O mutex, marks terminal, clears the BAR pointer and preserves
the object/reference obligation; real MMIO callbacks assert this lock and
reject terminal/NULL mappings. Identity reads also hold the lock. No existing
FPGA ABI/RTL/frozen CAD input was changed by these C/kernel edits.

Actual C/UBSan I/O007passes14cases, including four new detach cases. Full
current batch013/session37189passes143methods(190.797s), source-checks012/
session7716terminal0. Source-frozen kernel build003/session38544terminal0
withW=1/gcc13/running6.17headers, module98b2569522.., not loaded. This is not
actual auxiliary removal, ib_device/provider registration or native MMIO.
Future bus teardown must stop users and detach BEFORE parent BAR unmap,
retaining pool/hw/page/device/module lifetime on unknown DMA. Logical detach
itself NEVER supplies unpin/drain proof or resolves hot-unplug quarantine.

### Metadata candidate current full-path and board status

Actual native-meta synthesis001/session69986completed0 with186original/
frozen inputs verified:85465LUT(52.52%)/154206FF/168BRAM tiles/3DSP, a
49849LUT/38133FF reduction versus STATE. Unchanged4ns unplaced WNS-1.127ns/
3579setup failures, WHS+0.016/0hold,0pulse failures; NOT a timing/routed pass.
The STATE FULL board synthesis is now188637LUT(115.93%)/251154FF/264BRAM:
real synthesized capacity overrun, not just endpoint risk. Its driver5544
is now terminal1: pre-place DRC UTLZ-1 requires162912LUT-as-logic versus
162720compatible sites (192excess). No placer/route/image, no waiver of this
gate or relaxed part/clock/constraints. All810frozen inputs remain unchanged.
This is the older STATE comparison, not the live newer META build.

Metadata current helper four-state native002/legacyREAD002/legacyWRITE001/
actual URread001/URfence001 ALL completed0:109.44/70.76/71.51/46.80/47.97s,
all original benches/assertions and120s bounds, no forced internal state.
Parent hierarchy compile001also0, compile-only not parent traffic. Two-state
native/READ003also passed9.77/3.98s after445.51/448.81s binary builds; these
are additional scope, not substituted for the four-state results.

The board preparer now has an explicit reviewed metadata policy: exact
derived one-header/2000entry patch, all8024reset checks and current four-state
records required. Its8portable selection/snapshot/refusal tests pass. Full
current batch014/session93127passes145methods(177.240s), source-checks013/
session76953also0. Fresh actual full META snapshot `full-board-meta-analysis-001`
has1069original/1070frozen files,288HDL/13unchanged constraints/3originalIP;
source-only0/IMAGE_AUTHORIZED=0. Actual full CAD11803is live through real IP
and top synthesis. No complete full-board physical/CDC/native result yet.
No image command, hardware programming, module loading or network/fan/BIOS/
reboot/push change. The additional selected regressions below do not imply
full old13-size/large-capture/PMTU/release coverage. Broad RNIC/kernel/provider/
verbs/lifetime/protocol scope remains required.

### Exact META original-app regressions and CSR-only bus candidate

Unchanged original-app READ65and4097, WRITE65and warm/stale/host-route tests
now pass on exact60c9a20eHLS with four-state simulation and separate30scompile/
120ssimulation bounds. READ4097checks3messages/PSN wrap/12291payload and
253sentinel bytes; warm checks2x4097distinct payloads/same QP and PSNs,
8194payload+254sentinels and stale response discard with host backpressure.
The original timer bench also passes8621169cycles/26retry events/all8QP
restart-stop phases, first retry250002..250007clocks at4ns. Timer is an
additional two-state Verilator check with a30ssimulation limit, not native
or four-state timing proof. See BOARD_ANALYSIS and the source-bound reports.

`kernel/aux_control.c` adds the actual mqnic auxiliary alias and CSR-only
probe/remove scaffold, borrowing the parent's mapped app BAR. Identity is
validated before CSR reads; remove logically detaches before BAR unmap.
Default-disabled opt-in is checked BEFORE private-parent dereference, since
loaded mqnic private-layout compatibility remains unverified. No userspace
handles, ib_device, provider, WQ/CQ or verbs are exposed by this candidate.
Unknown DMA/pending state must retain ownership, never be called drained.
See `ROCEV2_AUX_CONTROL.md`; real bus/MMIO/runtime lifetime remains untested.

Source-frozen aux-build001/session50003links both actual modules withW=1/
gcc13against running6.17headers:16unchanged frozen own/parent source inputs.
No install/load/probe/MMIO/pinning/DMA/hardware action. Native-attach-unit002
passes5C/UBSan/static tests; full portable batch015/session65727passes150
methods(173.784s), source-checks014/session91239terminal0. Earlier kernel
build003remains historical after the Makefile's optional auxiliary section;
the new aux-build001was the source-bound compile/link record at that stage;
it is subsequently superseded by aux-build002after adding WQE support.

### Per-WR key and retry context: separate candidate

The pinned transport used the QP/MSN table key for every outgoing READ/WRITE
RETH. A separate fresh derivative now carries full32-bit per-WR key plus
an explicit validity bit through normal events, insertion/merged/stored
metadata, retries and partial READ updates. Key0is an exact explicit key,
not fallback. Retry also preserves the original source-host selector instead
of always forcing internal memory. This does NOT implement the missing
registered-host-source DMA frontend, local lkey authorization or verbs.

New source snapshot `wrkey-hls-p037tedt/inputs` changes only3allowlisted
transport/retransmitter files after sequential metadata initialization,
preserving full2000entries/13fields and original4ns/8QP/timer/integrity.
Logical SQ width241rounds to expected248AXIS bits; actual generation/packing
must independently pass. An explicit240-to248legacy/native-key RTL adapter
passes unit tests but is NOT yet inserted into current board wrappers.

Actual HLS C++004passes25003checks/41real RETH headers/6001metadata responses/
13actual retry events plus partial READ PSN wrap;0.049s simulation after8.83s
compile with38pre/terminal-hashed actual includes. This is C simulation,
NOT generated RTL, warm hardware reset, wire ICRC, native DMA or timing proof.
Failed serializer001and ACK fixture compile003are retained separately;
earlier successful002is historical after added constructor checks/C++17.
See `ROCEV2_PER_WR_KEY.md` for exact scopes/ABI/open requirements.

Actual per-WR HLS session79137is now terminal0 from its frozen source/launch
snapshot, separate from live full META board11803:138files hash716f5d92,
actual SQ248verified, HLS-only25114LUT/64686FF/85BRAM18K/4.043ns. This is
NOT placed/routed/full-board timing/capacity proof. Fresh four-state13-field
table001/session24485passes all8024checks/16resets/backpressure/deadlines,
100235clocks; actual metadata384/512packing verified. IPv4-reset001passes
88constructor observations. Full per-WR/legacy/protected wire/error/warm/
PMTU/board/native checks remain. Full portable batch
016/session86313passes155methods(181.184s), source-checks015/session31800also0.
No hardware/programming/module/network/fan/BIOS/reboot/commit/push changes.

Meanwhile the actual FULL META top synthesis completed, with all1070frozen/
1069original inputs unchanged:138205LUT(84.93%)/213008FF/264BRAM tiles/39URAM/
3DSP. Versus STATE it removes50432LUT/38146FF, unchanged BRAM. The synthesized
estimate is within capacity, not a physical place/route/timing/CDC pass.
0synth errors/0critical/363warnings retained; driver11803still live for
physical analysis. This is META60c9a20e, NOT the separate per-WR716f5d92.

### Per-WR transport delivery and bounded actual wire/legacy regressions

NEW delivery `wrkey-transport-profile-001` copies all138raw716f5d92files
unchanged and adds the explicit SQ adapter plus an interface-only derivative
of the original integrity bridge.140files hash569df76e. Native mode0always
uses supplied full32-bit key, including0; legacy default1retains old240bits/
QP key. Original sources, HLS instance hierarchy and full frozen META CAD are
unchanged. Delivery validation reconstructs the allowed derivation and rejects
edited self-consistent manifests/raw bytes/missing/extra files. Preparation
itself is NOT functional or physical proof.

Current four-state per-WR READ003/WRITE003and NAK-READ004/NAK-WRITE004ALL pass:
4different keys/one QP, zero/highbit/allones, full64-bit remote VA, PSN wrap,
lengths/padding/IPv4checksums/ICRC. Actual input PSN-sequence NAK triggers4real
replays after4original requests;8packet keys/PSNs/addresses/payloads remain
correct. WRITE verifies260normal/520with-replay bytes and original host bits
on both initial/retry source commands. Cases25.28..26.28s, no internal forcing
or shortened timer. Peer/memory remain MODELS, not native host WQ/verbs.

Fresh unchanged legacyREAD002/WRITE002and native-control002pass76.31/75.12/
112.69s; actual guard/CSR/HLS/generic PCIe path still checks130WRITE/195READ
bytes with model hard-IP/root-complex/host. URread002/fence002pass48.80/49.05s
without successful wire/page-release proof. Actual full patched parent/core/
app compile002also passes MAC16/64/128/tags19/16, retaining all warnings and
excluding exactly duplicate old bridge/adapter. Compile-only, no whole-parent
traffic; parent/app still uses legacy default mode.

Original-app3x65/3x4097READ,3x65WRITE/cumulativeACK and2x4097warm/stale/host
cases also all pass on the new delivery(32.45/91.19/31.92/76.70s). READ4097
checks12291payload+253sentinels; warm checks8194payload+254sentinels. Fresh
raw-HLS timer001passes all8QP phases/26retry events/8621169cycles, unchanged
4ns/1ms timer and30ssimulation bound; additional TWO-STATE scope remains.
Full current portable018/session46585passes162methods(187.559s), source
checks017/session23458also0.7new delivery units are synthetic, not wire proof.

Earlier fixture/report-assembly failures and earlier successful helper-source
revisions are preserved, not relabeled as current passes. Final delivery-
prefixed identity avoids original report keyword collisions and has a
regression test; same DUT/assertions were rerun to obtain current records.
See `ROCEV2_PER_WR_KEY.md` for exact records/scopes/open requirements.

Actual FULL META60c9a20eboard remains distinct. Post-synth UNPLACED timing
WNS-3.176ns/WHS-0.661ns,35271setup/324076hold endpoints and372unconstrained
internal endpoints are NOT passes. Worst estimated reset/config/ready→RAMCE
path is6.734ns/13levels,6.057nsestimated routing. Pre-place optimized DRC has
0errors/critical/31warnings; placer is running with original clocks/gates,
no utilization waiver. Final full-route/CDC/ownership gates remain required.
No hardware/programming/module/network/fan/BIOS/reboot/commit/push changes.

### Native WQE shape and local-MR admission building blocks

`kernel/wqe.c/.h` adds an explicit64-byte little-endian descriptor, full64-bit
local/remote addresses, full local/remote keys, epoch/sequence and reserved/
opcode/flags/length/range checks. Exact remote key0is valid; local lkey/PD/
permission is NOT authorized by encoding. Actual Linux `ib_rdma_wr`/one SGE
conversion compiles/links in `verbs_wqe.c`, refuses unsupported flags/ops and
is NOT registered/executed as a post_send callback. Current nonzero1..4096B
one-SGE READ/WRITE subset does not finish the required full queue/operations.

`rocev2_wqe_admission.v` captures trusted QP/PD/tag/expected epoch/sequence
separately from the fetched bytes. Full internal QP bounds, all record/context/
range checks precede the actual MR-table query: WRITE requires local read,
READ requires local write. Successful output preserves full IOVA/MR-relative
offset for the future actual page executor, never a truncated user/DMA address
or a fabricated contiguous translation. Clean denials zero address/key/length
outputs. Wrong response tag/extent/unknown status retains a sticky uncertain
owner with busy/config guard held and no manufactured completion/drain.
Offers/query/result remain guarded/stable through stalls and disable.

WQE-codec001passes7methods(actual shared C/UBSan/independent byte oracle/
1000seeded random records plus boundaries/null/overlap; one static kernel
adapter check). Admission001passes6actual four-state C-descriptor+MR-table
suites, including full-width key/IOVA/cross-page permissions/denials, bad
context/record rejection before lookup, top64-bit byte/key0/QP7, stalls and
uncertain response faults. Dedicated actual-MR fixture, NOT shared native
incoming/outgoing arbitration, host-SQ DMA fetch, actual pins/page DMA or CQE.

Actual frozen kernel-aux-build002/session61616links both support/control
modules and WQE APIs withW=1/GCC13/running6.17headers:17own files+2pinned
parent headers+1launcher, all20verified unchanged. No install/load/probe/
callback/MMIO/pin/DMA. Parent private ABI remains unverified/default probe off.
Old aux001is historical after Makefile change. Actual parent compile003also
passes with new frontend source uninstantiated, NOT native integration.
Full portable019/session80556passes175methods(178.598s), source-checks018/
session47276also0. See `ROCEV2_WQE_ADMISSION.md` for exact ABI and open work.
Current frozen META11803continues placement/physical optimization unchanged;
it does not contain the new WQE frontend or per-WR delivery. No hardware/
network/fan/BIOS/reboot/commit/push action. The broad RNIC goal is NOT complete.

### Shared local/incoming MR namespace, not native host WQ

`rocev2_protected_responder` now has optional/default-off `LOCAL_WQE_ENABLE`.
It connects the actual WQE frontend and incoming parser to ONE existing MR
table through the new full-width/round-robin/owner-routed query arbiter. No
unsynchronized table, truncated local key/IOVA or separate registration.
Caller/downstream lease guards block MR/QP changes beyond lookup/work handoff.
Independent tracked management-idle avoids blocking RX behind a local lease
and covers accepted commands/held responses without guard combinational loops.

Current source-bound actual-HLS shared-namespace001/lease001/overlap002pass
in37.6..41.5s each:16total local queries/results,1explicit modeled downstream
lease,7incoming operations/replies including3all-byte65B READs, stale/fresh
rekey/PD/permission/range denials, management priority, held results, disable/
pause and independent incoming progress. Raw138generated HLS files unchanged;
no transport stub in these probes. Backend memory/local executor leases are
MODELS, not native PCIe/pages/CQ. Fast shared-unit003passes3methods (explicit
transport stub); arbiter-unit001passes6four-state ownership/fairness methods.
Actual parent compile004passes with default dedicated-query mode, not enabled
native shared WQ. See `ROCEV2_SHARED_MR.md` for exact scope and failure history.

Current full portable020/session98895passes184methods in208.010s, including
the existing default-query regressions and9new shared/arbiter methods. Source
checks019/session29026passes7methods. Retained actual VVP elaborations each
contain exactly ONE MR-table instance. Fresh selected shared/kernel/descriptor
records and all1880older physical comparison frozen inputs remain SHA-bound;
this is not a current full physical/CDC/native/lifetime/RNIC release pass.

The protected-responder source now differs from the immutable META analysis
snapshot. All1070frozen inputs are retained; that older CAD outcome remains
comparison evidence only, NEVER physical signoff for the new shared/per-WR/WQE
path. Previous source-bound protected/native reports that include the old
responder are historical after this edit; their files are not rewritten.
Current selected shared probes/parent compile bind the actual new source.
No hardware/configuration/commit/push change; full RNIC objective incomplete.

### Actual SQ client/backend/generic-PCIe fetch, not native queue/verbs

`rocev2_sq_fetch.v` adds full-DMA64 trusted coherent-ring fetch for8internal
QPs, full PD/epoch/sequence, producer credits, round-robin, stable offered DMA/
held records, no tag wrap and external downstream/parent lifetime guards.
`rocev2_sq_dma_fetch.v` connects it to real existing Corundum RAM/AXIS/DMA
descriptors. Kernel coherent allocation, queue CSR/doorbell/barriers and actual
native shared-MR/work/CQ/provider connection remain unimplemented. Descriptor
consumer/result is NOT an RDMA completion or permission to release WR refs.

Current sq-fetch-unit003passes7four-state controller methods. Actual C/UBSan
descriptor + generic-PCIe/mux/RAM probes sq-pcie005/error005pass in under1s:
6normal records across2QP and ring reuse;4error-case records including actual
UR10/zeroed record, independent queue progress,40-cycle withheld parent proof,
stale-epoch refusal and fresh-epoch refetch. Physical host/link/root complex
remain MODELS. Exact16/18/19-bit tags and RAM routing12 are checked; no host
WRITE/fence, internal forcing or fake descriptor/status/RAM engine agents.

New backend `RECOVER_READ_DMA_ERROR` defaults0, preserving existing protected
payload fail-stop behavior. Only the SQ wrapper selects1; a matching terminal
READ error drains zeros and reports its real status, then requires actual
parent AND local DMA/RAM drain before reuse. WRITE/fence/protocol/unknown
ownership faults never use this recovery path. Native whole-parent sticky
fault/reset/actual pin lifetime and CQ recovery are NOT proven by the model.
See `ROCEV2_SQ_DMA_FETCH.md` for exact behavior and retained failed attempts.

Full portable022/session55473passes193methods in213.561s, including all old
default protected/backend tests and9new SQ methods (2real generic-PCIe cases).
Source-checks020/session35173passes7methods; actual parent compile005/
session28773also0 with new sources uninstantiated/default mode. Fresh13selected
component records and1880frozen old physical inputs SHA-match; old reports
containing the earlier backend are historical after this source edit. META
comparison originals now differ at both responder/backend; its frozen inputs
remain unchanged and it cannot qualify this new desired path. No actual new
queue mapping/runtime/hardware/FPGA/fan/network/BIOS/reboot/commit/push action.
The full functional/physical/standard-RDMA/native objective is incomplete.

Final SQ probe005also creates its ignored build directory for a fresh source/
CI checkout. Earlier004results are historical after this launcher-only change;
the actual DUT remains identical. Native integration must additionally share
physical tag/RAM ownership: new SQ and existing paged backend logical16-bit
tags must NOT be directly merged/aliased or truncated into spare tag bits.

### Actual kernel coherent-SQ and non-sleeping MR work ownership

`mr.c/.h` now has a separately IRQ-spinlocked published fast view, pool-client
ownership and genuine refcount_t work references. Full lkey/PD/range/local
permissions are checked before a work ref is returned. Close stops new getters
and refuses revoke/unpin while queued/in-flight refs exist; pool teardown and
epoch reset likewise wait for all clients. Existing actual ib_umem and hardware
publication/invalidation/drain contracts are retained.

New `sq.c/.h` uses real dma_alloc_coherent/free APIs, full DMA64/ring/epoch/
cookie bounds, actual Linux WR conversion/64-byte codec, shadow-owned MR refs,
dma_wmb before required atomic producer callback, and actual-memory/transport/
CQ-commit-gated retirement. Descriptor-fetch consumer never frees a WR. Callback
failure/unknown publication/invalid completion retains owned queue/MR/ring;
uncertain outstanding abort/flush is explicitly unfinished, not silently
redefined as successful permanent quarantine. Logical context is not a registered
ib_qp/ib_device lifecycle or standard post_send/provider implementation.

Kernel-sq-build002/session25494actual W=1/GCC13/running6.17headers compile/
links22inputs frozen before launch (19own+2pinned headers+1launcher),14actual
WQE/MR-ref/SQ symbols and both support/CSR-only modules. No Linux runtime
allocation/pins/MMIO/CQ/module load, and auxiliary default probe still off.
Kernel-queue-unit002passes10actual-C/ASan/UBSan/pthread cases with EXPLICIT
primitive/umem/coherent/HW/CQ models, including actual source concurrency/
barriers/CQ-full/ambiguous-owner/device-module retention; negative cases do
not fake cleanup. First001build/tests are historical after final lifecycle
flag READ_ONCE/WRITE_ONCE changes. Fresh native-attach004and codec002pass
against the current Makefile; older aux002/attach003/codec001are historical.

Full portable023/session90010passes203methods in216.264s; source checks021/
session9269passes7. See `ROCEV2_KERNEL_QUEUE.md` for exact API/callback/lifetime
scope and remaining native bind/queue CSR/physical tag-RAM routing/shared-MR/
executor/CQ/standard verbs/error-flush/physical/CDC/native requirements. None
of the new actual kernel allocator/producer/CQ callbacks executed in Linux.
No actual hardware/network/fan/BIOS/reboot/commit/push action; broad goal active.

### Shared full-tag SQ/paged DMA and terminal older physical comparison

New `rocev2_dma_client_router.v` preserves independent full16-bit logical tags
using unique physical tags and explicit per-bank/direction/span ownership.
It permits both staging banks concurrently, arbitrates all four descriptor
ports fairly, serializes actual untagged segmented RAM tokens, restores full
logical status only after RAM quiet, and preserves accepted offers/responses
under later disable/fault. Duplicate/wrong/unissued tags, illegal RAM and
unknown errors fail closed. Physical tag wrap refuses, not silent reuse;
native epoch/abort/flush remains unfinished. Router-unit002passes11methods/
22four-state simulations with explicit descriptor/RAM agents.

New `rocev2_sq_paged_dma.v` combines actual SQ and paged payload backends with
that router. Actual generic-PCIe probe002passes two concurrent clients,7real
physical descriptors/statuses,128C-encoded SQ bytes,65WRITE+65READ payload
bytes split3+62over scattered DMA64 pages, a visibility fence,128total delayed
write-sequence cycles,16319host sentinel bytes and128unchanged ring bytes.
It uses both real muxes/RAM clients and actual parent guard; no descriptor/
status/RAM agents, internal forcing or constant parent proof. Physical host/
root complex/link and trusted raw config/authorized payload source are MODELS.
This raw DMA composition has no implicit MR authorization/local WQE executor/
wire/CQ/registered driver. See `ROCEV2_SHARED_DMA.md` for exact scope and
retained initial harness failure (fixed by a tag-indexed pipeline scoreboard,
not changing DUT/asserted byte/range/ownership requirements).

Full portable024/session78441passes215methods in209.313s, including the new
actual-PCIe combined graph and all old default-path regressions. Source
checks022/session26425passes7methods; parent compile006/session78020passes
with legacy/default mode and these new sources uninstantiated, NOT enabled
native shared DMA. Current16selected component records plus terminal older
physical report and all1880frozen comparison inputs SHA-match. Old READ/WRITE
766+298identity rows and rollback image remain unchanged. No actual hardware/
network/fan/BIOS/reboot/module-load/commit/push action was performed.

Older full-board META11803now completed0at04:00:53UTC with reports/checkpoint,
no image. Original4ns final WNS-0.348/TNS-799.383/6144setup failures is NOT a
timing pass. Hold+0.008/0fail,pulse0fail,312317fully-routed nets/0errors,
38skew constraints/min+1.712,12check_timing categories0andDRC0errors/0critical/
36warnings are separately recorded;18CDCcritical paths are not yet conditionally
signed off. Worst data_remaining-to-HLS CE path traverses write keep/ready
logic. Frozen snapshot has no current per-WR/shared-MR/SQ changes and cannot
qualify this desired feature image. No constraints/gates were relaxed.

New shared-DMA-only OOC74130build freezes13inputs before reading/synthesis and
retains original4ns clocks/15-bit RAM/full16-bit tags/8queues/default RAM8192.
It is analysis only, no full native parent, generic PCIe engine, HLS transport,
board/PHY or standard RDMA runtime. Its terminal outcome is tracked separately
from the older full-board comparison; a component result can never replace
the resulting full-board original physical/CDC gates. Broad RNIC goal active.

### Actual SQ control-to-PCIe composition and real-RAM loop correction

New `rocev2_sq_control_regs.v`/`kernel/sq_regs.h` implements a distinct actual
AXI-Lite32 mailbox: immutable15-word snapshots, full QPN/PD/epoch64/cookie64/
DMA64/depth/producer64/retire-nonce64ownership, exact nonwrapping sequence/
ACKs and guarded actual allocation/publication/retirement. Real fetch capacity
errors retain ownership; cancelled unfetched tail is NOT WR completion and
cannot manufacture retirement flags. Unknown/corrupted/unsolicited responses
and ambiguous owners taint/fault, not safe free. All staging bits must be known
before mutation. Kernel SQ hardware callbacks/provider are NOT yet bound.

`rocev2_sq_controlled_dma.v` exposes NO raw SQ config bypass and connects the
real mailbox to actual shared SQ/paged/router/RAM DMA. Work|wire|completion
guards reach the real fetcher, including guard rises after snapshot. Current
SQ-control-unit004passes9methods/36four-state simulations (explicit backend/
guard models). Actual generic-PCIe controlled002passes4AXI control commands,
2C-encoded SQ records,7physical descriptors/statuses,65WRITE+65READ bytes,
128delayed write-sequence cycles,16319sentinels/128unchanged ring bytes,
both clients concurrent and actual parent guard. Host/link/software/zero
downstream owners and trusted PTE/authorized payload source remain MODELS.
See `ROCEV2_SQ_CONTROL.md`; no native MMIO, pages, executor, CQ or verbs proof.

Initial shared-DMA OOC74130finished terminal1,4ns WNS-3.088ns/TNS-13263.778ns/
9079setup failures,4combinational loops/LUTLP-1critical warnings. Hold+0.012/
0fail,pulse0fail; actual isolated18145LUT/12501FF/20BRAM. Actual reports show
router response-ready fed same-cycle command-ready, while real RAM command-
ready itself depends on response-ready. The source now accepts response only
after registered command ownership in WAIT, never sampling an unaccepted
zero-latency response. Router-unit003passes12methods/23simulations, including
that explicit no-bypass/held-response case; raw shared generic-PCIe003also
passes unchanged all-byte/range/proof assertions. Physical loop removal is
NOT assumed from these simulation results.

Fresh shared-DMA OOC002/session12328is live with13new source-frozen inputs,
original4ns/full geometry/capacity and NO loop waiver. Current OOC driver also
rejects every nonzero check_timing category and DRC error/critical warning;
its exact Tcl gate body passes18bounded fixture cases, including rejection
of the actual failed001loop report. Original001frozen sources/reports remain
unchanged; mutable router and OOC driver now differ, so001is historical
failure evidence, not current source timing. No image/native release is made.

Intermediate portable025/session21899passed225methods in215.112s BEFORE the
registered router/known-staging correction; it is retained, not relabeled as
current. Intermediate CSR001/003, failed002BRESP assumption and controlled
PCIe001likewise remain scoped to their exact source. Current full regression
and actual default-mode parent compile are separately recorded in checkpoint022.
No actual hardware/network/fan/BIOS/module-load/reboot/commit/push action.

Current portable026/session30075passes226methods in224.417s AFTER the source
corrections. Actual default-mode parent compile008/session62259also terminal0,
with original warnings retained; it does not instantiate the new CSR/shared
queue path. Fresh19selected component/gate records and2terminal physical
records bind3114unique checked files, including all1906frozen comparison/live
inputs and1064old READ/WRITE identity rows, with no mismatches. No native or
full physical pass is inferred from this evidence.

### Real kernel SQC1 callback source and physical loop removal confirmed

New `sq_io.c/.h` implements exact full15-word owner/reply/nonce/consumer/flags
validation, strict nonwrapping sequence, pre-bell readback, uncertain posted
ownership and exact ACK. Pre-bell failure does not consume sequence. Atomic
polls have both1..1000us monotonic deadline and256iteration bounds, no sleeps.
New `sq_hw.c/.h` connects actual Linux readl/writel/IRQ spinlocks/time/cpu_relax
to real coherent SQ allocate/publish/retire callbacks, with a REQUIRED actual
CQ publisher and queue-fast -> SQC-fast -> CQ locking. No default CQ success,
CPU user-payload copy, unregistered fake device or runtime model fallback.
Late transport reconcile/detach never unquarantine WRs or prove unpin.

Actual frozen kernel-sq-build003/session69064passes W=1/GCC13/running6.17headers,
27inputs frozen before compile (24own+2pinned headers+1launcher),22API symbols
and both support/CSR-only modules. No load/installation/probe/MMIO/pins/DMA/
standard callback executed; default auxiliary probe remains off/private ABI
unverified. New actual-C kernel-sq-hw-unit002passes13methods/48ASan/UBSan cases
with EXPLICIT primitive/MMIO/time/CQ/DMA/umem/proof models, including15wrong
reply positions, pre-bell strict-sequence retry, retained post/ACK timeouts,
late transport-only resync, stopped clock, CQ-full and2threads/16WRs. Native
C-to-RTL/driver/physical-host execution is NOT claimed. See the new
`ROCEV2_SQ_KERNEL_MMIO.md` for exact guarantees and open work.

Original shared-DMA002/session12328now finished terminal1due negative setup.
Actual exact13original/frozen inputs unchanged; physical check_timing ALL12
categories0including0loops; DRC0errors/0critical/1warning. Registered RAM/router
loop removal IS verified.23893nets fully route/0errors, hold+0.034/0fail,
pulse0fail. At4ns setup WNS-2.524/TNS-9878.554/8529failures remains; this is
NOT a timing pass or board/native release. Worst rst-to-SQ-producer CE path
passes arbitration/64-bit span validation/live fault/completion/drain/config
logic (29levels/5.971ns). Next source change needs a registered authorization/
configuration boundary with actual current-offer/lifetime vetoes, never just
stale drain=1, lower clocks or false-path/loop waiver. No live CAD job remains.

This kernel-only stage does not edit RTL or the exact raw shared-DMA snapshot.
Native SQC1 decode/actual ib_device/QP/CQ/provider, shared MR/PTE/local executor,
wire/fence/CQ ownership, safe abort/flush and all broad operation/reliability/
physical/CDC/native requirements remain open. No actual hardware/network/fan/
BIOS/reboot/commit/push action. Broad goal remains active.

### Registered full descriptor authorization, not stale-drain pipelining

The actual router now captures the chosen client/direction/complete descriptor
into a proposal WITHOUT accepting the client, allocating a physical tag or
issuing DMA. CHECK evaluates full65-bit DMA64end/17-bit RAM span/known shape
from registered fields; READY uses a registered approval only. Meaningful
source fields/valid must still match the original captured offer before actual
ready/valid acceptance. Other arbiter inputs cannot replace its bank/owner.
Changed/withdrawn offer faults13and retains proposal ownership, never DMA/tag.
Unknown address/length/tag and invalid shapes fail before acceptance.

This breaks the identified request-arbitration ->64-bit carry -> live-fault/
drain/config chain without storing an old drained=1. Global drain also requires
no proposal/current offered request. Disable holds an unaccepted valid proposal
but permits another issued client's complete status to drain once CHECK ends;
accepted physical/RAM offers remain stable under disable/fault. No original
clocks, tag widths, QP/table/RAM capacities, bounds or lifetime vetoes reduced.

Router-unit005passes17methods/36four-state simulations. New cases enforce no
early acceptance/tag bypass, owner preserved after competing-priority changes,
7mutations/withdrawal,3unknown fields, disable with independent old completion,
and fault during proposal. Initial004failed ONLY the prior same-next-edge
fairness timing assumption;005still checks the exact order/one-hot winner with
a finite12-cycle bound. Existing byte/range/completion guards were not relaxed.

Fresh raw shared generic-PCIe004and CSR-controlled003both pass the unchanged
full-byte/range/sentinel/parent assertions:7physical descriptors/statuses,
128C-encoded SQ bytes,65WRITE+65READ,16319sentinels/128unchanged ring bytes,
both actual clients concurrent. Raw cycles1056/controlled1658reflect the new
registered latency. Physical host/link/software/trusted configuration/authorized
payload and downstream owners remain MODELS, not native/Linux/verbs proof.

Current source is no longer the old002physical snapshot, whose13frozen files
and failed setup reports remain retained. Fresh OOC003/session91411freezes13
inputs before actual read/synthesis at original4ns/full geometry and is live.
No current-source timing/loop/DRC or full-board release is assumed. No image,
hardware/driver/network/fan/BIOS/reboot/commit/push action. General RNIC goal
and all existing native/provider/operations/recovery requirements remain open.

Current portable028/session36050passes244methods in229.941s after descriptor
pipelining. Actual default-mode parent compile009/session94815also terminal0,
original warnings retained; new path remains uninstantiated in that parent.
Fresh20selected component/gate records plus3retained terminal physical records
and the new live snapshot bind3150unique files with no mismatches, including
all1919physical frozen inputs and1064old READ/WRITE identity rows. No current
source physical/native/provider pass follows from those narrower checks.

Current portable027/session66200passes239methods in215.161s. Source checks027/
session59956also terminal0. Fresh20selected component/gate records plus3actual
terminal physical records bind3137unique checked files, including all1906
physical frozen inputs,27kernel build inputs and1064old READ/WRITE identity
rows; no mismatches. These are explicitly separated kernel compile/model,
actual RTL component and failed physical scopes, not native release proof.

## Reboot continuity gate

No reboot, service restart, kernel installation, driver loading or FPGA
programming has been performed in this stage. Current work does not need a
reboot. Read-only checks found `t3code.service` enabled/active with
`Restart=always` and user lingering enabled. However, the current Codex
app-server PID5991has PPID1and is not proven to be managed by that service.
Starting a web/app service is NOT proof that this exact thread and active
goal automatically resume. That continuity is **not yet verified**.

Official OpenAI documentation describes persisted goals/explicit resume, not
a demonstrated OS-reboot guarantee for this installation:
[Goals](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex),
[resume commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli).
If a reboot becomes necessary, first establish and verify the actual Codex
startup/authenticated thread-resume path and preserve a bounded recovery
checkpoint. Do not reboot on the assumption that a saved thread or enabled
unrelated service is sufficient. SRAM configuration/test namespace state
must also be revalidated/restored after any eventual reboot.

## Next implementation step

FULL META board11803is terminal0for analysis, but setup timing fails as
documented above. Inspect/correct the actual guard/write-ingress ready path
and qualify a NEW resulting feature image without relaxing original gates.
Per-WR HLS79137/table24485are terminal0, not live jobs.
Current selected per-WR/wire/NAK/error/legacy/warm/original-app/timer cases
now pass on explicit delivery569df76e. Complete remaining original13-size/
large-capture/PMTU/release coverage. The optional shared MR source integration
now has bounded actual-HLS evidence, but is not in the native queue path.
The SQ DMA fetch client/backend now has actual generic-PCIe model-backed
evidence and coherent-ring/MR-work-reference kernel implementations compile
and pass explicit primitive-model tests. Bind genuine native queue CSR/atomic
producer/CQ callbacks and actual ib_device/QP lifetime, never arbitrary user
DMA addresses or a default successful hardware backend. Common full physical-
tag/RAM ownership now has a separate actual SQ/paged/generic-PCIe composition;
it still must be selected and owned by the real native parent, not mistaken
for existing native integration. Initial isolated4ns74130failed with4real
RAM/router combinational loops; current source has a registered response
boundary; fresh12328is terminal1with0loops/0DRCcritical but WNS-2.524ns. Correct
the actual long span-validation/drain/config path without a stale proof or
gate waiver. The router now uses registered proposal/CHECK/READY full descriptor
authorization; OOC003/session91411is now terminal1with0loops/0DRCcritical but
WNS-2.897ns, not a pass inherited from002. Its current worst registered
RAM-WR-address/span/fault/drain/config path is recorded above. Actual SQC1
kernel callback source now exists and compiles/model-
executes, but requires native decode/bus/QP/CQ/provider runtime binding,
without exposing arbitrary
user DMA or replacing true CQ/WR completion by fetch consumer/CSR ACK.
Connect fetched records to the new WQE admission,
select its now-native/same-port/paged/controlled shared MR queries/guards in
the real board parent (never an unsynchronized duplicate table), trusted queue/QP context and actual
page-DMA/staging executor. Retain real MR/QP/queue ownership through wire/
memory/fence/CQ publication; admission is not completion. Native standard
kernel/user verbs and their runtime lifetime are still required. Then
integrate the resulting functional path into a NEW board profile, never
silently substitute model/C++/unit passes or mutate frozen analyses.
Verify/connect the
actual generic PCIe DMA engine/TX sequence/attribute/requester ordering and
protected host-page mapping/lifetime using actual hardware callbacks. Integrate the protected backend into
a separate board profile while retaining native initiator READ/WRITE and
without mutating rollback sources or weakening original gates. Complete
safe abort/drain/reset-key epochs and wire error/recovery;
only after full physical/CDC review attempt a finite thermal-supervised
native case. Continue registered host-DMA/kernel/provider/verbs functionality.
This broader goal is NOT complete because the offline protected subset passes.
