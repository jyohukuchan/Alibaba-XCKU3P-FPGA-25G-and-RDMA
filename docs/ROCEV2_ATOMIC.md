# RC64 Atomic candidate execution

Progress081 adds a real **responder memory execution** feature, not complete
native Atomic support. Default native RTL and `IB_ATOMIC_NONE` are unchanged.
The original protected responder, legacy images, clocks and all timing/drain
gates are untouched. Nothing is programmed, installed or loaded.

## Full native requester integration draft (096, not validated)

`derive_atomic128_native.py` is an IN-PROGRESS generator for a single matched
128-byte requester/responder graph, including parent context widths, SQC/RQC
descriptor stride, CQ operand registers and Atomic request routing. Its first
derivation attempt stops at the checked SQC anchor `initial if(MAX_QPS` with
`ValueError: source derivation anchor changed`. No complete output graph,
elaboration or runtime result exists for this draft. It is included as a work
checkpoint, not a usable native profile; the verified leaf/component evidence
below does not validate this integration. Default RTL, driver negotiation and
`IB_ATOMIC_NONE` remain unchanged.

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
