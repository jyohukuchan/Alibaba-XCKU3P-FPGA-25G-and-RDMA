# Incremental RNIC implementation

This is a work-in-progress **source/offline-verification** snapshot, not a
hardware-qualified general RNIC release. Public functional reports are in
`results/2026-10-18/`. Numbered agent progress checkpoints and terminal/cache/
storage administration records referenced in the historical notes below are
local-only and intentionally excluded from source control. Build directories,
generated HLS/vendor artifacts, credentials and binaries are not published.
The repository's strict recorded-source check currently detects historical
TX-padding SHA mismatch after44-byte SEND support; the old evidence/check
remain unchanged, not retroactively declared current.
Publication checks: focused Atomic RTL12 methods PASS; the full RNIC suite
is not green (native MAC-lifetime ERROR and QP-TX FAIL observed before the
remaining run was interrupted). No all-suite or release-pass claim is made.

## Latest functional milestone (2026-10-20)

Publication snapshot090 also includes an opt-in full native normal/Atomic
integration candidate. [Full-graph elaboration001](../../results/2026-10-18/rocev2-rnic-atomic-native-full-elaboration-001.json)
PASSES with actual generated HLS, one shared MR/PTE domain and actual Atomic
memory/MAC components. This is structural verification ONLY: the integrated
candidate has no functional runtime result, no hardware/timing qualification
and no standard Atomic verbs capability. The new mixed FADD/duplicate/WRITE
fixture passes Python generation only; its launcher and simulation remain
unfinished. Default RTL and `IB_ATOMIC_NONE` are unchanged. The verified
functional milestones below retain their narrower, separate test scopes.

Progress089 adds privileged RX route binding to the actual SQC owner epoch/
cookie/PD table, without a second namespace or packet/current-head authority.
Seven methods/13 four-state cases PASS, including stale same-QPN recreation,
held-lease protection and legal producer updates. Checked native authority
and service-only owned HLS bridge elaborations pass separately; this does NOT
prove a full native Atomic datapath. The actual owned-core native READ/
SEND_IMM runtime001 now PASSES both cases in11.44/11.39s, with full native
SQ/MR/DMA/replay/core-owner/PSN/CQ and wire/ICRC checks. Host/root/MAC/peer
remain models;630source/45artifact hashes match. Atomic RX remains rejected/disabled, not
advertised; its real dispatch/shared memory/MAC lifetime integration remains.

Unchanged SQC regression on the new lookup derivative:9 methods/36 cases PASS.
Combined Atomic RTL:33 methods/96 simulations PASS. These do not replace
full native/API/runtime/physical or known broader CI qualifications.

Progress087 adds real downstream MAC reservation before Atomic HLS ownership
and new-admission gating on available nonwrapping MAC tags. A packet already
accepted by the real packet guard drains under later admission disable;
neither its MAC reservation nor its offered HLS owner is canceled/retracted.
Five new four-state reservation methods/10 simulations pass, for26 Atomic
methods/83 simulations in total. Full generated composition is recorded
separately. Production tag width13 is unchanged; its bounded test uses4 to
reach exhaustion without a long stress run. Ordinary/native QP/MR/normal
memory integration and requester/API/physical qualification remain open.

The [reserved MAC generated composition002](../../results/2026-10-18/rocev2-rnic-atomic-reserved-MAC-generated-002.json)
now PASSES7 cases <=10.99s. It connects the actual full owned HLS/Atomic/MR/
DMA/RAM/IP/ICRC and real MAC/XGMII/SFD/CDC path. The15-tag boundary case
retires15 operations then holds a16th packet outside admission, without new
side effects. Both disable-after-admission points drain and re-enable normally.
Independent every-byte/FCS/ICRC/core/owner oracles and223source/23artifact
hash audits pass. Pending upstream input is not safe unpin/configuration
proof. No physical/native/Linux/timing claim or automatic push follows.

Progress086 adds Atomic MAC lifetime and automatic guarded-packet retirement.
The actual144-bit owner/392-bit service reply/224-bit consumed-core receipt
must match the generated IP response before Ethernet transmission. Fresh
private MAC tags1..8191 sit outside existing native WQE routing; positive
retirement requires the OWN genuine SFD receipt, accepted EOF and wire tail.
Drop uses actual no-packet consumption, not a fabricated receive WQE or MAC
receipt. Existing native frame/completion classes pass independently. A new
checked Atomic-only bridge snapshots peer sideband at actual admission and
uses real AXIS fanout; hardware drives retirement directly, not a test knob.
Nine four-state methods/25 simulations include actual25G XGMII TX/FCS/SFD-tag
and timestamp CDC RTL in one case, decoded independently from actual wire
outputs. Full generated-HLS composition is recorded separately after compile.
This is not full ordinary/Atomic native MR/memory/QP integration, requester,
standard API runtime, physical PHY or timing signoff. `IB_ATOMIC_NONE` and
both0 global drains remain. No new push/install/programming/hardware changes.

Current generated MAC composition002 PASSES4 cases <=8.79s with unchanged
full owned HLS and actual Atomic/MR/PTE/DMA/RAM/IP/ICRC. The main11requests
produce11 actual core receipts/automatic retirements and10 real Atomic MAC
XGMII/FCS/SFD frames, alongside one unrelated native frame/completion. Drop
tag10 emits no frame, then fresh FADD tag11 succeeds. Independent Python
checks actual Ethernet/FCS and HLS wire/readbacks. MR denial retires through
actual MAC with no DMA; failed fence/corrupted nonce retain ownership without
completion. Physical host ordering/PHY/time input remain models.001 is retained
as diagnostic scope-label failure;002 freshly translates and reruns all cases
after checked label fix, without relaxing HDL checks. Future native admission
must honor finite tag exhaustion. No new board/HLS synthesis; original4ns/
1.08ns gates remain, owned raw HLS estimate13.568ns still misses target.

Preceding consumed-core milestone:

Progress084 implements immutable144-bit packet ownership through the actual
Atomic HLS RX/service path and exports224-bit consumed-core completions only
after real SAME-table MSN/EPSN readback on the existing ordered channels.
The new512/392-bit service echoes QPN/epoch/requestPSN/unique packet nonce;
registered execution/reply offers remain stable under disable/backpressure.
Actual full HLS C++ + actual protected Atomic/MR/PTE/paged DMA/RAM RTL PASS9
Atomic jobs with normal SEND/two WRITEs/two QPs in0.293seconds. Deliberately
stopping either table consumer prevents done; drop completes and later valid
work progresses. Existing Immediate TX/RX consumers also PASS unchanged.
Complete owned HLS synthesis001 verifies the512/392/144/224-bit ABI; timing
estimate13.568ns still misses original4ns/1.08ns. Generated composition002
PASSES4 actual-RTL cases <=2.73s:11owned core receipts/10wire packets on2QPs,
drop then next successful FADD, no-DMA MR denial, failed-fence retention and
corrupted-nonce rejection. Independent Python checks every wire response and
current table/immutable-owner receipt. Diagnostic001's stale test scoreboard
wait is fixed without weakening checks; exact pre-fix sources/logs remain.
Positive MAC/host ordering/physical descriptor boundaries are MODELS. This
Atomic-only branch is not a replacement for ordinary/native admission;
positive native MAC retirement, full native integration, requester, actual
standard APIs and physical/timing signoff remain open. `IB_ATOMIC_NONE`, zero
global drain inputs and all11 requirements remain. No hardware or Git writes.

Preceding retained packet-path milestone:

Progress083 adds the Atomic packet-admission branch and connects the actual
generated shared HLS core to the real protected Atomic/MR/PTE/paged DMA/RAM
service plus existing IP/UDP/checksum/ICRC RX/TX. The new guard snapshots
independent trusted source/destination IP, full QPN and nonzero64-bit epoch,
checks a complete72-byte Atomic request, and provides a fresh nonwrapping
packet tag even for repeated protocol PSNs. It does not duplicate PSN/MSN/MR
tables and is NOT a replacement for the native ordinary-operation guard.
Explicit matching downstream retirement is required; there is no quiet-time
or arbitrary-current-head release. Four four-state guard methods PASS13
simulations, including normal receipt, unknown/bad frames/context and stale
packet tags. The first event-driven sensitivity issue was fixed by making
header-function data inputs explicit, not weakening admission.

The current full generated composition003 PASSES3 bounded cases, <=2.78seconds
each:9 actual response packets from10 two-QP service requests (including a
no-packet drop), a no-DMA MR denial and a failed visibility-fence retention
case. Actual IP/UDP/checksum/ICRC and old-value bytes pass an independent
Python oracle. Earlier001 executed diagnostic cases but was correctly rejected
by its source-change audit after that guard fix; it is NOT current evidence.
Fresh RTL translation reuses only verified identical compiler objects, never
old test results. Full generated testing covers successful/retried/mismatched/
overflow operations, two QPs, bad integrity/peer/QP, MR denial and failed
visibility fence. Physical descriptor/host ordering and native-MAC retirement
are explicit MODELS, not actual native/kernel/board operation. No-packet
drops deliberately retain ownership because a genuine exported core-consumed
retirement receipt is still required; AXIS ready or quiet is not that proof.
Default native graph/`IB_ATOMIC_NONE`, original timing/CDC gates and all11
requirements remain unchanged. No install/load/programming/hardware/push.

Preceding shared-sequencing/HLS generation milestone:

Progress082 connects the Atomic responder to the **same HLS PSN/MSN consumers**
as existing SEND/WRITE. A new matched `rocev2_native_atomic_top` exchanges
bit-exact368-bit requests/248-bit replies with the protected RTL service.
The real receive sequence owner waits for execution; only a genuine new
execution advances the existing tables. Cached replies, sequence NAKs and
drops never advance them. The RTL service's shared mode does not use its
standalone PSN/MSN table. A registered adapter binds trusted full QPN/epoch
and holds response ownership; no fake completion or second memory namespace.

The actual HLS C++ consumers and actual adapter/Atomic/MR/paged DMA/RAM RTL
run as two live processes: each unedited emitted request goes to RTL and its
real response returns to HLS. The bounded0.279second test PASSES9 Atomic jobs,
one ordinary SEND, two ordinary WRITEs and two QPs, including PSN wrap, CAS
mismatch/FADD overflow, replay after another QP's update, sequence NAK/drop,
and no premature state advance while execution is withheld. Existing
Immediate TX and RX tests PASS eight operations each on the new source.
Four short four-state adapter methods and the standalone14-case Atomic
execution regression PASS. Physical descriptors/host ordering, trusted owner/
peer admission and ordinary SEND/WRITE payload sinks remain explicit MODELS.

This is current source/C++-RTL co-simulation, **not generated-HLS/native/physical
or verbs qualification**. Complete HLS generation001 finished in301.6seconds
at original4ns/1.08ns/full geometry and unchanged1500MiB guard:58162LUT,
82957FF,166BRAM18K,0DSP; correct368/248 service ports and unchanged original
typed owner ports. Its13.568ns estimate still MISSES4ns, not a timing pass.
Actual153-module generated hierarchy also elaborates with one shared PSN/MSN
consumer each; this is compile-only, not generated packet execution. The default
native graph and `IB_ATOMIC_NONE` stay unchanged. Next is the actual generated
core/native wire-owner/memory/MAC/CQ binding and Atomic requester/standard API,
not a broad fine-bug audit. No hardware/programming/install/load/commit/push.
Old generated C++ cache15files were losslessly gzip-archived after decompressed
SHA verification; authored sources/logs/executables preserved. See archive082,
progress082 and `docs/ROCEV2_ATOMIC.md` for exact scope/recovery/remaining work.

Preceding standalone Atomic execution milestone:

Progress081 starts the next major operation group: a CAS/Fetch-and-Add
responder memory execution candidate. Actual RTL checks wire BTH/AtomicETH,
authorizes the full key/PD/remote-atomic access/range with the existing MR
table, reserves the same shared memory arbiter across8-byte read/modify/write
and actual backend visibility status, then returns wire AtomicACK(old value).
Per-QP replay caches avoid executing a duplicate twice; ordinary DMA cannot
interleave the read and write. No separate BRAM-only RDMA or CPU payload copy.

Fourteen bounded actual-RTL composition cases PASS, each<0.21seconds, using
the existing single MR/PTE/paged DMA/Corundum staging RAM. They cover both
operations, mismatch/overflow, duplicate replay, two QPs, competing DMA,
denial/epoch/PSN behavior and DMA/fence failures. Physical descriptors/host
ordering and integrity/peer admission remain explicit MODELS. This candidate
has a private test QP sequence table; shared native HLS QP sequencing, full
network/MAC ownership, requester and kernel/provider integration are STILL
required. Default graph and `IB_ATOMIC_NONE` remain unchanged. No physical
Atomic, timing or complete RNIC claim. See `docs/ROCEV2_ATOMIC.md`; checkpoint
`rocev2-rnic-progress-081.json` records remaining work. Nothing programmed,
installed, loaded, committed or pushed; BIOS/network/hardware untouched.

Preceding source/API Immediate milestone:

Progress080 connects Immediate to standard kernel `post_send`, normal device
publication and the real userspace provider. The opt-in native derivative
advertises RNC/SQC/RQC/CQC=1023/5/7/7; the driver re-reads all four actual
controllers under their proper locks, before queues, and binds profile1 only
for that exact matching tuple. Partial, mixed or stale profiles are refused.
Default hardware/RTL and legacy profile0 remain unchanged and refuse Immediate.
No application switch can enable the new descriptor format.

Actual C tests PASS9 cases: zero/nonzero SEND_WITH_IMM/WRITE_WITH_IMM, separate
full remote VA/key, base SEND signal-all without an RDMA cast, exact linked
bad-WR handling, real CQ/reference release and capability refusal. Complete
native bootstrap/device tests PASS20 cases, including matched1023 publication,
Immediate posting/receive WC and normal closure. Linux/pins/DMA/MMIO/core
completion are explicit MODELS in these C tests. The real installed libibverbs
and actual provider PASS both legacy and Immediate command tests, including
network-order0/nonzero values and WITH_IMM/WRITE receive WC serialization;
the kernel syscall replies are modeled and no real NIC context is opened.

The new full generated native profile also PASSES all7 requester and4 duplex
receive cases, <=15.3seconds each, preserving exact wire/replay/MR/PTE/DMA/
core/MAC/CQ and independent WRITE data/RQ authority. Actual AXI captures prove
the full1023/5/7/7 tuple. Its16 unedited CQ records PASS the real kernel C
bridge again. Physical host/root/MAC/peer boundaries remain MODELS and native
simulation is two-state. Fresh78-method checks, running-kernel W=1/new-export
build and frozen provider build PASS; neither module nor provider was installed.

This closes the source/API selection gap, NOT physical/kernel-runtime signoff.
All eleven full-goal requirements remain, including Atomic/zero/large/multi-SGE,
physical lifetime/thermal and original timing/DRC/CDC gates. The13.568ns HLS
estimate still misses4ns; no programming/BIOS/network/push/reboot. Next work
prioritizes a remaining major operation group, not a broad fine-bug audit.
Checkpoint: `rocev2-rnic-progress-080.json`. Two old failed executables and four
old compiled elaboration caches were losslessly gzip-archived with decompressed
SHA verification; source/logs/current executables remain. Recovery manifest:
`rocev2-rnic-cache-archive-080.json` (both files in `results/2026-10-18/`).

Preceding full-native integration milestone:

Progress079 integrates Immediate through the complete opt-in native graph,
not just individual interfaces. A checked16-module substitution retains the
full620-bit immutable owner through real coherent SQ/shared MR/PTE/executor/
replay/MAC/CQ, selects one actual generated Immediate native HLS core, and
preserves the original legacy core/default graph. Protected-wire notification
is separate from the posted RQ context. WRITE_WITH_IMM performs a full remote
RETH/key/PD/MR lookup independently of its RQ notification owner; empty RQ
returns genuine wire RNR before forwarding/advancing the receive PSN.

The actual full-generated requester path PASSES7 bounded cases: both Immediate
operations with0/nonzero notification, plus existing READ/WRITE/SEND. Exact
wire/payload/ICRC, byte-identical real replay, fresh MAC receipts, core proof
and20-word native CQ records are checked. Each case takes12.6–12.8seconds.
The full receive/duplex path PASSES4 cases, including both notifications,
zero/nonzero values and actual empty-RQ RNR. Each runs two work pairs on
independent coherent SQ/RQ rings, receives before the local SEND is acknowledged, withholds its OWN
physical MAC receipt, then retires real CQ/core owners. WRITE notification
uses a1-byte RQ at VA...3410 while65 bytes actually go to the independently
authorized remote VA...3210; the RQ buffer/sentinels remain unchanged. All
cases finish within15.3seconds. No forced producer proof or global drain1.

The16 unedited native CQ snapshots also PASS actual independent SQ/RQ/MR/CQ
C under ASan/UBSan: eight receive WCs have correct network-order WITH_IMM,
including value0, and WRITE uses RECV_RDMA_WITH_IMM despite RQ capacity1.
Actual descriptor bytes, distinct cookies, coherent ring addresses and MR
reference release match the captured inputs. Fresh78-method units and actual
full-native HLS hierarchy pass. Earlier failed test/compiler attempts are
retained separately; current evidence hashes were rechecked after the runs.

Physical host/root/MAC pins/peer and Linux/DMA/MMIO remain EXPLICIT MODELS.
These are two-state native simulations, not actual Linux/provider or physical
operation, whole-board timing or error/unplug qualification. Standard kernel
TX posting STILL selects profile0 and refuses Immediate; completion format7
alone does not enable or advertise whole-device support. Next is matching
trusted device capability/standard posting and remaining operations, including
Atomic/zero/large/multi-SGE, not a broad fine-bug/timing audit. The13.568ns HLS
estimate still MISSES4ns. No install/load/programming/BIOS/network/push/reboot.
All eleven requirements remain; checkpoint: `rocev2-rnic-progress-079.json`.

Preceding Immediate receive-completion milestone:

Progress078 adds the Immediate receive-completion path. Opt-in real RQ storage
keeps the620-bit posted owner immutable while separately binding wire-admitted
notification/flags, actual length/PSN, the752-bit HLS receipt and identical
fresh-tag768-bit MAC receipt. SEND notifications still obey posted capacity;
WRITE_WITH_IMM notifications may describe a65-byte remote write with a1-byte
RQ buffer, but independently authorized remote-MR data placement is still
required upstream. Unknown/mismatched wire/core/MAC metadata quarantines the
owner. Physical-memory visibility, core receipt, real ACK SFD/EOF/tail and
exact commit/retire remain mandatory; neither a notification nor quiet time
substitutes for them.

The CQC opt-in profile advertises format7, with20 immutable context words and
separate notification flags/value at0x03c/0x090. Original profiles1/3 keep their
19-word ABI. Actual kernel IO/decode/SQ/CQ C preserves the complete posted WQE,
emits network-order IB_WC_WITH_IMM (including value0), distinguishes
IB_WC_RECV_RDMA_WITH_IMM, and retains references under full CQ/lost ACK or bad
metadata. Current posting STILL selects legacy profile0; completion-format
support is NOT authority to advertise/enable whole-device Immediate support.

The connected actual RQ→ACK MAC receipt→CQC AXI test passes8 notifications;
its unedited snapshots then pass actual kernel C, including eight WCs,
CQ backpressure, ambiguous ACK reconciliation and corrupt-metadata retention.
Admitted wire placement, HLS receipts, physical visibility/MAC pins and Linux/
DMA/MMIO are EXPLICIT MODELS, not real data placement/native/generated-HLS or
physical runtime. Five new four-state provenance units and the complete78-
method short suite pass; the running-kernel W=1 build, standard-device/native
graph model regressions and unchanged-default native hierarchy pass too.

Next is matching these620/680/688/752/768-bit interfaces into the full native
parent/shared-core/wire-MR/executor/replay/MAC/CQ path, including separate
WRITE_WITH_IMM remote-MR authority and RQ notification ownership. The actual
parent still selects the old default profile; no new image/module/provider
was installed or programmed. No new HLS synthesis/timing pass: Immediate's
13.568ns estimate still misses4ns. All eleven full-goal requirements remain.
Current checkpoint: `rocev2-rnic-progress-078.json` in `results/2026-10-18/`.

Preceding Immediate descriptor/transmit milestone:

Progress077 connects Immediate to the actual descriptor/admission interfaces.
The fixed64-byte host descriptor uses bytes48..51 for a separate32-bit value,
bytes52..55 remain reserved0, and the software representation is still64bytes.
Explicit candidate-profile C/Linux-WR adapters map network-order imm_data
without treating base SEND as an ib_rdma_wr or aliasing the full remote key.
Default APIs/current posting STILL select profile0 and refuse Immediate;
there is no new device capability or production post_send support yet.

The actual SQ-result frontend and same MR table now retain/erase notification
according to genuine authorization, and the opt-in staging module transfers
the620-bit immutable owner BEFORE the280-bit SQ. Four-state tests cover both
operations/notification values, real MR/backpressure/failed-fetch/denial,
unknown notification refusal and unchanged default behavior. The complete
current short suite passes46 methods; actual running-kernel W=1 build links
the four new profile APIs without installation/loading. The existing full
native duplex hierarchy also elaborates with the changed default leaf modules.

A new matched bridge preserves the actual padding/checksum/ICRC pipeline and
selects the complete generated Immediate HLS core at the correct port widths.
Its descriptor→MR→staging→HLS→wire/ACK-retire runtime check now PASSES all8 cases
with the actual generated core and integrity RTL (about1.31seconds per case).
Exact wire RETH/IETH/full remote VA/key/notification/payload/padding/IP/ICRC
and genuine full620-bit request-retirement receipts are checked. Verilator
is two-state; the distinct candidate/default leaf tests are four-state. The
earlier VVP30second failure is retained, not relabeled. This candidate still
models fetched SQ results, source memory, executor lifetime and peer.
Native coherent DMA/MAC/CQ, receive notification/MMIO and
standard kernel/provider integration remain NEXT, not an achieved feature.
No hardware/BIOS/network/module/provider/commit/push/reboot action was taken.
Current checkpoint: `rocev2-rnic-progress-077.json` in `results/2026-10-18/`.
Earlier076 full-native runtime reports remain historical as-run evidence;
shared leaf/kernel sources changed this turn, so they are not a fresh current
full-native runtime pass. Original clocks/uncertainty/gates remain unchanged.

Preceding Immediate transport-source milestone:

Feature work has advanced to Immediate, after the matched duplex core passes
full-generated native READ/WRITE/SEND regression (each11.2–11.4seconds), real
native CQ, exact wire/ICRC, byte-identical replay and genuine memory/MAC proof
gates. The unedited CQ snapshots also pass the actual kernel SQ/CQ/MR C
bridge. Ordinary and initial-RNR duplex SEND/RECV/cancel cases were rerun with
the current launcher and the exact preceding compiled binary, not cached
result relabeling. Linux/physical boundaries remain modeled.

The new opt-in **Immediate candidate**, not selected into the native delivery,
implements both SEND_WITH_IMM and WRITE_WITH_IMM TX/RX in the same full duplex
HLS core. Immutable request context grows588→620bits, preserving the complete
remote VA/key separately from the notification. Actual generated EXH bytes
contain network-order immediate and, for WRITE, full RETH. The real RX parser
and header stripper recover the notification and padded payload. Wire values
are execution-proof sidecars, never written over the posted RQ context.
WRITE_WITH_IMM data is for the remote MR, not the RQ buffer; native full-key
authorization still needs matching integration. A1-byte RQ capacity with
65-byte write data is explicitly exercised.

Short C++ TX-to-RX packet-model tests pass8 operation pairs (both opcodes,
zero/mixed/high-bit/all-one notifications), real payload/ACK/MSN/PSN consumers,
PSN wrap, full request and receive retirement receipts. Separate TX tests pass
all8 values plus mismatched immutable metadata rejection. Network/physical
memory and native protection are NOT established by these C++ tests. Complete
matched HLS synthesis passes at unchanged clock/uncertainty/capacities and
checks the actual new typed port widths. It uses56678LUT/81179FF/159BRAM18K/
0DSP; its13.568ns estimate MISSES4ns, and is not250MHz/full-board signoff.
There is no generated-RTL runtime or physical Immediate pass yet.

This is NOT usable native/verbs Immediate support yet. The larger typed HLS
ports need matched full-key/RETH/RQ admission, CQ/MMIO notification metadata,
kernel/provider mapping and generated-native bounded verification. No
Immediate capability is advertised, no existing core is replaced, and no
FPGA/module/provider is programmed/installed/loaded. Atomic, zero/large/multi-
SGE and the other full-goal requirements remain. Evidence:
`rocev2-rnic-progress-076.json` in `results/2026-10-18/`.

Preceding duplex completion milestone:

The native duplex completion boundary now separates real physical memory
drain from the OTHER direction's pending MAC receipt. The diagnostic run
showed an exact matching HLS requester receipt, parent/router/SQ DMA drained,
but network `memory_drained=0` because it also included response-MAC quiet.
The new matched `DUPLEX_ENABLE=1` profile propagates actual protected backend,
PCIe/RAM/router/SQ drain to per-operation completion; each request/receive
still requires its OWN real MAC receipt/tail and all existing native proofs.
The public all-traffic memory/MAC barrier and configuration/close guards
remain unchanged. Default0 retains the previous serial drain behavior.

Full-generated native duplex simulation now PASSES both ordinary and initial
RNR cases (13.99/14.69seconds). Each runs two real coherent SEND/RECV pairs,
with peer receive placement/core proof while local SEND is unacknowledged,
local CQ completion while the other MAC barrier is held, and receive CQ only
after its OWN real MAC proof. It checks exact wire/ICRC, both queue cookies,
buffer reuse, real native PCIe/RAM/fences, then cancels a third no-packet RECV
using the actual flags63 certificate. No fake CQ or derived drain override.

The unedited four native CQ records, third WQE and cancellation reply also
pass actual kernel SQ/RQ/CQ/MR C, including WR_FLUSH_ERR and reference release,
with Linux/core/MMIO/DMA-mapper boundaries explicitly modeled. Actual-HLS
full-parent elaboration passes in both modes. Default-mode READ/WRITE tests
with HLS models pass; full-generated new-core READ/WRITE remains next. No
image/module/provider was deployed; physical/kernel/full-board timing/DRC/CDC
qualification and the other operations remain open. Current evidence is
`rocev2-rnic-progress-075.json` in `results/2026-10-18/`.

Preceding duplex routing milestone:

An opt-in duplex delivery now connects one native HLS core to independently
retained local-request and remote-request paths. Actual HLS memory producers
stamp origin into the former two AXI padding bits; ordered RTL credits retain
origin/exact length through data EOF and restore all94 original command bits
before the existing protected memory clients. Whole-packet RX arbitration
and post-integrity TX direction routing replace the exclusive whole-operation
role mux. Local and receive retirement cannot clear each other's owner.
There is still only one native MR/PTE namespace and one shared native core.

The complete new top compiles in C++; three short actual-consumer cases accept
peer SEND while our SEND/READ/WRITE remains unacknowledged, then complete both
directions through genuine HLS receipts. Four-state RTL checks pass11 memory
cases and8 connected-routing/lifetime cases with explicit HLS-port models.
Full native-parent elaboration also passes with the actual newly synthesized
core, independent rings, original DMA/MR/MAC/proof machinery and cancellation.
HLS uses38185LUT/82622FF/150BRAM18K/0DSP; its5.306ns estimate still misses4ns.

The first full-generated-native run proves peer receive placement and core
receipt while the SAME local SEND remains unacknowledged, but then reaches
the sender CQ deadline (proof flags3f, receive owner still held). That failure
is retained; the diagnostic and successful correction are recorded above.
It withholds our peer ACK until an
incoming SEND has real placement/core proof, and still withholds the receive
ACK's actual MAC receipt before allowing its CQ. It is NOT a runtime pass
or deployed duplex RC support. No clock/uncertainty, global-drain or memory
protection gate was relaxed. Physical/kernel/provider operation, original
full-board timing/DRC/CDC and the other required operations remain open.

Preceding standard-error functional milestone:

Standard `modify_qp(IB_QPS_ERR)` now blocks new posts and progresses the
receive-side error close in process/work context. It first caches the exact
native RQC cancellation certificate without releasing any work reference,
then obtains real QP STOP/PD-zero revocation, and only then publishes ordered
`IB_WC_WR_FLUSH_ERR` receive WCs with original WR IDs and zero length. CQ-full
retains unreported references and resumes the same proved cancellation batch;
coherent rings still require ordinary paired queue retirement. QP destruction
synchronously cancels its worker before core-owned storage can be freed.

The actual-source native-bootstrap model now passes19 cases, including six
new ERR/backpressure/late-proof/cookie/file-close/wrapped-RQ cases. Unedited
full-generated-native cancellation replies additionally pass the real kernel
SQ/RQ/CQ/MR C flush path in two cases. READ/WRITE/SEND native-CQ bridges and
existing verbs/device/CQ regressions pass. The running-kernel/pinned-parent
W=1 build passes with43 own/46 frozen inputs. IB core, workqueue execution,
pins/DMA/MMIO and physical hardware remain explicit model boundaries; no
module/provider/image was installed or loaded.

This is receive-side standard ERR support, NOT general outstanding requester
SEND/READ/WRITE abort, ERR-to-RESET reuse, arbitrary forced cleanup or hot
unplug. Missing native ownership proofs still retain memory indefinitely.
Real bus/provider runtime, simultaneous RC, remaining operations and original
full-board timing/DRC/CDC gates remain open. The full goal remains active;
current evidence is `rocev2-rnic-progress-073.json` in `results/2026-10-18/`.
See [the kernel queue contract](../../docs/ROCEV2_KERNEL_QUEUE.md).

Preceding existing-operation regression milestone:

The pending READ/WRITE/SEND full-generated-native regression has now finished
successfully. Each65-byte case runs in about11seconds with genuine native CQ,
shared MR/PCIe ownership, full wire/ICRC comparison, byte-identical retry and
fresh MAC tags. READ additionally performs real protected receive placement
and its memory fence. Exact captured native CQ bytes and matching software
WQE encodings also pass actual kernel SQ/CQ/MR C for all three operations;
Linux pins/DMA/MMIO/controller teardown remain boundary models.

This closes the verification gap left by checkpoint071; session22773 is
terminal, not a live build to resume. Production RTL/kernel/provider sources,
HLS target/uncertainty and both zero global-drain gates were unchanged.
No resulting-board timing, actual Linux/provider/physical memory operation or
surprise-unplug/parent BAR lifetime is proved. The full RNIC goal remains
active. Current evidence: `rocev2-rnic-progress-072.json` in
`results/2026-10-18/`. No image/module was loaded and no reboot performed.

Preceding whole-native cancellation milestone:

Receive cancellation now passes the actual full generated-HLS/native graph,
not only separate component models. Both ordinary and initial-RNR cases run
two genuine SEND/RECV pairs, then publish a third coherent RECV without a
peer packet and cancel it. Each case finishes in under16seconds. The actual
PCIe engine/parent guard stays busy while the physical root-complex model
withholds the third fetch's completion/TX sequence; no derived drain output
is assigned or masked. That accepted fetch still reaches SAME-MR admission
before the real posted-owner/RQC cancellation returns flags63 and paired
normal SQ retirement succeeds. Exactly four native CQ events remain: the
cancelled receive never produces a fake packet or success CQE.

The unedited four native CQ snapshots, third64-byte WQE and complete19-word
RQC cancellation reply also pass the actual kernel SQ/RQ/CQ/MR/cancel C in
both cases. A link-time DMA-allocator boundary model supplies the same two
host-model coherent IOVAs, so the full DMA64/layout/owner/producer/nonce are
compared exactly, not rewritten in the captured proof. Real Linux primitives,
pins/DMA/controller teardown and physical host/MAC are still models; this
does not prove a loaded kernel/provider or physical memory lifetime.

Current evidence is progress071. READ/WRITE/SEND full-generated regression
compilation is still active at that checkpoint; inspect its exact saved live
session/report before launching any replacement. No new HLS synthesis or
physical image/module installation occurred. The unchanged HLS5.306ns estimate
still misses4ns, and all full-board timing/CDC/runtime/parent lifetime gates
remain. `rocev2-rnic-progress-071.json` is in `results/2026-10-18/`.

Preceding cancellation source/component milestone:

Optional receive cancellation now joins the native RQC1 mailbox, coherent
fetcher, posted receive-owner store and user-file close path. With
`RECV_CANCEL_ENABLE=1` (default0, requires separate SQ/RQ), RQC1 advertises
features3 and accepts scoped command4. It blocks new receive takes/fetches,
waits for actual fetch/admission and memory drain, reclaims only never-taken
same-QPN/PD/epoch receive owners, then retires the unfetched ring tail.
An exact immutable full-owner/final-producer/nonce reply with flags63 is
required before Linux drops abandoned pending receive MR/work references.
This is a genuine new cancellation certificate, NOT a fabricated native
success/flush CQE or an inference from empty software queues. Coherent rings
stay allocated until ordinary QP STOP and paired queue close succeed.
Old RQC1/features1 keeps the preceding drain-only behavior; RNC stays511.

Actual-source kernel integration passes13 short bootstrap/file-close cases,
including pending RECV without any received packet/CQ event, withheld cancel
reply and corrupted full cookie. The actual RQC/fetch/posted-owner RTL passes
five short cases spanning fetched/unfetched tails, missing parent drain,
wrong cookie and retained in-flight receive ownership. Its descriptor backend,
admission/MR context formation and external drain are explicit models. The
full native hierarchy elaborates with actual existing generated HLS in both
new-cancel and legacy-default modes; this is NOT a full native simulation or
physical timing/runtime pass. Running-header/pinned-parent W=1 build passes.

Already-taken receive work still completes through its original placement,
HLS, MAC and CQ lifetime; cancellation never erases it. A timeout retains the
same batch/nonce and memory until exact reconciliation. Outstanding requester
SEND/READ/WRITE abort, arbitrary forced-core cleanup, parent BAR release,
durable epochs, full generated-native cancellation runtime and physical
qualification remain open. No module/probe/image was enabled or installed.
See `rocev2-rnic-progress-070.json` in `results/2026-10-18/` and
[the queue-control contract](../../docs/ROCEV2_SQ_CONTROL.md).

Preceding user-file close milestone (old RQC1/features1 behavior):

User-file close preparation is now connected to the real RDMA
`ufile_hw_cleanup` callback. A user QP and both CQs retain their actual
uverbs context association. Closing that file stops new posts, discards its
unread software WC metadata, suppresses/synchronizes notifications and pumps
currently visible native CQ events through the unchanged full-WQE/MR/proof
validation. Ordinary core destruction still needs real STOP and independent
SQ/RQ retirement replies before freeing any DMA ring or pinned memory.
The [upstream core cleanup path](https://github.com/torvalds/linux/blob/v6.17/drivers/infiniband/core/rdma_core.c)
defines this pre-destruction callback; a model does not prove running-core
or private-parent compatibility.

Ten short native-bootstrap model cases now pass. The four added user-close
cases cover unread completions on distinct CQs, delayed visibility retaining
MR/ring ownership, another context closing without affecting the live QP,
and a full shared CQ that previously backpressured the native RECV completion.
The actual running-header/pinned-parent W=1 build and existing device, verbs
and RTL-event-to-kernel-CQ regressions also pass. IB-core execution, pins/DMA,
hardware completion production and IRQ execution are explicit models.

This is NOT yet arbitrary forced-close or surprise-unplug recovery. A
preposted receive without an actual completed event is not cancelled by
closing a file: its native owner and pinned memory stay held. Missing or
invalid native completions, core cleanup failure, parent BAR release and
durable epochs still need complete lifecycle integration. A retained QP
forgets the core-owned ucontext pointer when that context is deallocated;
this prevents retaining that pointer, not a permission to release its work.
No bus probe was enabled, no module/image installed and no hardware changed.
Current evidence: `rocev2-rnic-progress-069.json` in `results/2026-10-18/`.

Preceding native-bootstrap milestone:

Native graph bootstrap now connects the actual RNC epoch/MR/page adapters,
separate SQ/RQ, CQ/router/retry and standard-device publication in one owned
initialization/normal-close path. `kernel/mqnic_graph.c` adds an explicit
pinned-mqnic auxiliary adapter that validates PCI/app/BAR/interface0/netdev0
before native CSR access. It is default-denied by `enable_native_attach`
BEFORE dereferencing the private parent layout; it is not an automatic probe.
Six short source-model cases pass, including actual three-page RNC MR
publication and SEND/RECV/CQ, retained ambiguous epoch replies, normal teardown
and two known-closed reattachments with increasing MR/QP watermarks. W=1
compilation uses the actual pinned parent and running-kernel headers.

All attachers of one physical parent must share ONE parent-owned epoch/owner
lease, not create per-open copies. Failed/ambiguous attachment retains the
whole graph and BAR/device references until real reconciliation/close. Only
successful normal close updates the in-memory high watermarks. Durable
storage and physical lifetime across reload/reset/OS boots are still caller
requirements, not supplied by an in-memory lease or a modeled reset.
The actual auxiliary driver still does NOT invoke this adapter: parent BAR
release must honor a successful close, never discard EBUSY from a void remove
callback. Exact loaded-parent compatibility, forced user-file cleanup and
surprise-unplug/native/physical gates remain open. See
`rocev2-rnic-progress-068.json` in `results/2026-10-18/` for current evidence.
No parameter was enabled and no module or image was installed/loaded.

Preceding standard API/provider milestone:

Standard RDMA publication APIs and an actual libibverbs userspace provider
now exist in source. `kernel/device.c` uses genuine IB allocation/registration,
query/port/GID/context and unregistration APIs around the existing bound
MR/SQ/RQ/CQ/verbs graph, not an empty device. Five short modeled-core/netdev
tests cover publication, actual SEND/RECV callbacks, completion and teardown;
the full kernel target compiles withW=1. Only existing fixed IPv4 RoCEv2 routes
are accepted; no Atomic, InfiniBand, MAD/CM or unrestricted get_dma_mr is faked.
The [Linux RDMA API](https://origin.kernel.org/doc/html/v6.17/driver-api/infiniband.html)
defines the actual allocation/registration boundary used by this layer.

`provider/as02.c` builds a real PABI34 shared provider against pinned rdma-core
50.0 headers and the installed libibverbs. Public `ibv_*` calls exercise its
PD/MR/QP/CQ/context lifecycle and real library command marshalling for
SEND/READ/WRITE/RECV, full64-bit addresses/keys and error propagation. Only the
kernel ioctl/write boundary is modeled; no real NIC context is opened.
Shared-object loading also passes in an isolated process. The provider uses
standard uverbs commands, not user BAR mappings, exposed DMA addresses or
CPU payload-copy transport. Build inputs are pinned by
`provider/build_frozen.py`; it never installs its library or driver config.

This is NOT yet an auxiliary/bus-wired registered device or a qualified
kernel/provider runtime. The existing CSR-only auxiliary module stays
default-denied and does not call these publication APIs. Device removal
currently requires all contexts/objects closed; EBUSY retains ownership,
not surprise-unplug recovery. Forced user-file cleanup, bus/parent lifetime,
persistent epochs and physical native/board gates still require integration.
See `rocev2-rnic-progress-067.json` in `results/2026-10-18/` for the current
evidence and unchanged requirements. No module/provider was installed.

Preceding transport milestone:

Independent physical SQ/RQ now work in the same generated-HLS/native-RTL
graph: a preposted receive no longer blocks SEND completion. Two SEND/RECV
pairs use distinct coherent ring addresses/cookies and independent work
sequences, with genuine CQ publication, buffer reuse and both queues'
actual control-path retirement. Both the posted-receive and initial-RNR
cases pass in under15seconds each. Full SEND/ACK wire bytes and ICRC are
checked, including a second SEND sourced from the actual received buffer.
`SEPARATE_RQ_ENABLE` remains opt-in/default0, requires the complete requester
CQ profile, and advertises RNC features511/CQC features3. The separate RQC1
window is at0x405000; the existing SQC1 window stays at0x402000. One actual
DMA fetch backend and one MR/PTE/native executor are shared, not duplicated.

The actual kernel QP/post_send/post_recv/CQ callbacks also support the two
rings;15 short callback tests pass, including SEND completion while RECV is
pending and paired teardown. Unedited native CQ snapshots and matching WQE
bytes are checked separately against the actual kernel queue/CQ/MR code.
See `rocev2-rnic-progress-066.json` in `results/2026-10-18/` for evidence and
unchanged remaining requirements. The preceding065 milestone established
native requester SEND/READ/WRITE CQ and retry in separate operation tests;
the existing default-disabled READ/WRITE regressions still pass.

These are offline functional results: physical host/MAC and Linux primitives
are explicit models. There is no registered RDMA device/user provider or new
programmed image. The unchanged4ns HLS target is not met by the5.306ns estimate;
full-board physical timing and native hardware qualification remain required.
Independent queues do not imply a fully concurrent standard RC engine: the
shared HLS still arbitrates exclusive local/remote execution roles. The next
major milestones are actual bus/parent/registered-device/provider runtime
integration, genuine ordinary simultaneous RC, then Immediate/Atomic and
remaining operation semantics. FPGA programming and module loading have not
been performed.

Current same-port initiator/responder source and short actual-RTL evidence:
[same-port integration](../../docs/ROCEV2_SAME_PORT.md) and the subsequent
[single-AXI control candidate](../../docs/ROCEV2_NATIVE_CONTROL.md).
Actual nonaliasing control decode/configuration CSR exists offline; native
board/runtime pins/RDMA-driver/provider integration is still missing. The
simulation is not a full RNIC or physical timing pass.

The later [native parent/app candidate](../../docs/ROCEV2_NATIVE_PARENT.md)
adds separately patched actual parent/core/application wiring and real
parent-drain/fault ownership. It still needs a resulting full board build,
physical/CDC gates and runtime driver/provider integration; do not program it
based on compile/unit or model-backed functional results.

The [full-board analysis path](../../docs/ROCEV2_BOARD_ANALYSIS.md) now freezes
actual board/parent/app/PCIe/PHY sources and original constraints. It runs
analysis only and deliberately cannot generate or program an image; all
original release/conditional CDC/native and broad RNIC requirements remain.

A separate [CSR-only auxiliary-control module](../../docs/ROCEV2_AUX_CONTROL.md)
now compiles against the pinned parent headers. It matches only ASN1 and
defaults to denying probe BEFORE private-parent-layout access. It is NOT
installed/loaded/bound and registers NO ib_device/provider/verbs. Exact
loaded-parent/header compatibility and full native gates remain unproven.

This is work toward the remaining general RoCE functionality, not a replacement
for it and not a claim of MCX455A equivalence. The verified native version2
READ/WRITE sources and image remain unchanged under `rdma/read/`.

`rtl/rocev2_mr_table.v` is the registered-memory authorization primitive.
It checks full keys, trusted QP protection domains, permissions,64-bit virtual
ranges and contiguous DMA translations. It does not perform DMA, respond to
network packets, implement Atomic operations or register an RDMA device.
It is now connected to the offline-tested protected responder described below.
It is selected by separate frozen board-analysis candidates, but has not been
deployed to the FPGA or verified with native registered-host-page DMA.

Management registration/invalidation requires externally proven quiescence
covering ALL memory leases, not just the lookup FSM. A stalled lookup/result
or management response also prevents reconfiguration. Registering an occupied
entry is rejected; invalidate first. Per-slot key generations are retained on
invalidation and refuse exhaustion rather than wrapping. Global reset is NOT
key revocation: future integration must close/flush QPs and establish a fresh
key epoch before exposing memory after reset. Memory pages must stay pinned
and mapped until every authorized operation drains.

Basic permission bits follow `ib_access_flags`: local write1, remote write2,
remote read4, remote atomic8; local read is implicit. Remote write/atomic
registration requires local-write permission. Lookup operation values0..4
are local read, local write, remote read, remote write, remote atomic.
Atomic authorization requires8-byte alignment/length; no atomic execution
is supplied. This first table describes contiguous spans, NOT scatter/gather
page translation or a complete `ibv_reg_mr` implementation.

Keys use low`log2(ENTRY_COUNT)`bits for the slot and all remaining bits for
the generation. Zero-length registrations/requests are rejected here; a
future verbs frontend must handle legal zero-length no-op semantics outside
the memory engine. A65-bit exclusive end exactly2^64is allowed; overflow
beyond it is rejected. Failed lookups disclose no DMA address/offset/length.

Run short real-RTL tests with `make -C rdma/rnic check`. They must not access
devices, start communication, reprogram the FPGA, reset interfaces or reboot.
See `docs/ROCEV2_RNIC_PROGRESS.md` for the unchanged overall scope and exclusions.

`tests/probe_responder_transport.py` separately characterizes the actual
pinned READ-capable generated HLS with a simulated memory source/sink. It
verifies real READ response and WRITE ACK bytes, but deliberately observes
that the UNPROTECTED transport accepts bad rkeys and truncates full64-bit
addresses. It is not an RNIC protection pass, not native hardware evidence,
and never opens a socket or modifies the deployed image. The current
deployed ingress rejects these incoming request opcodes.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 rdma/rnic/tests/probe_responder_transport.py \
  --hls-build /path/to/tested-read-hls-build --report /path/to/new-report.json
```

This manual generated-HLS probe is not part of the short dependency-free
`make check` target. Use a fresh report path; prior failures remain evidence.

The separate [per-WR-key candidate](../../../docs/ROCEV2_PER_WR_KEY.md) carries
full remote keys, explicit zero-key validity and original host-source context
through actual HLS C++ normal/retransmission/partial-READ paths. Its C++ and
SQ-adapter unit tests alone are NOT a generated-RTL/board/native/verbs pass.
The new explicit delivery also passes finite four-state per-WR wire/NAK,
legacy/protected/error/original-app checks, with physical memory/peer models.
The new248-bit SQ ABI is not selected by current frozen board profiles.

The new [host WQE/admission building blocks](../../../docs/ROCEV2_WQE_ADMISSION.md)
provide an explicit64-byte C/kernel descriptor and actual full-width local-MR
authorization RTL. They do NOT yet fetch a native host queue, execute page
DMA, publish CQEs, register verbs/provider callbacks or run on the FPGA.

The subsequent [shared-MR source integration](../../docs/ROCEV2_SHARED_MR.md)
connects the actual incoming responder and local WQE frontend to ONE existing
MR table. It adds fair/owned query arbitration, independent management-idle
and downstream lifetime guards, with short actual-HLS/ICRC/wire checks. It is
optional/default-disabled and not propagated into the native host queue path;
the older frozen META analysis does not qualify this newer source.

The later [SQ DMA-fetch candidate](../../docs/ROCEV2_SQ_DMA_FETCH.md) adds a
trusted coherent-ring fetch controller and real Corundum descriptor/RAM
backend. Short actual generic-PCIe/mux/RAM tests verify full C-encoded records
and a parent-drained UR recovery option; physical host/link remain models.
Real kernel queue allocation/CSR, native shared-MR execution and CQ/provider
are still missing. Descriptor fetch is not RDMA completion.

The subsequent [kernel SQ/work-reference library](../../docs/ROCEV2_KERNEL_QUEUE.md)
implements real coherent-ring allocation/posting APIs, atomic authorized MR
references and completion/drain-gated retirement. Running-header compilation
and actual-C/ASan/UBSan primitive-model tests pass, but no real allocator/MMIO/
CQ/provider callback has executed in Linux. Actual native integration and
ambiguous-work abort/flush remain unfinished; do not load/program from this.

The new [shared SQ/paged-payload DMA composition](../../docs/ROCEV2_SHARED_DMA.md)
translates full logical tags into unique physical16-bit tags and routes actual
segmented RAM ownership without aliasing. Short tests combine both real
backends/muxes/generic PCIe/parent guard, with physical host/link models. It
is not yet selected by the native parent or connected to MR execution/CQ.

The later [privileged SQ CSR composition](../../docs/ROCEV2_SQ_CONTROL.md)
removes the external raw SQ config bypass and connects actual AXI control to
that real shared DMA path. Full owner/epoch/layout/sequence and late lifetime
guards are enforced, with actual generic-PCIe byte/retirement checks under
explicit software/host/guard models. It is not a mapped native BAR, bound
kernel queue callback, MR/WQE executor, CQ or standard RDMA implementation.

The subsequent [actual kernel SQC1 adapter](../../docs/ROCEV2_SQ_KERNEL_MMIO.md)
connects coherent SQ library callbacks to real readl/writel and non-sleeping
bounded owner-checked register transactions, requiring an actual CQ publisher.
Running-header compilation and actual-C/ASan/UBSan model tests pass; no real
Linux BAR/pins/DMA/callback or native/provider registration has executed.

## Protected responder integration (not yet native)

`rtl/rocev2_protected_responder.v` connects actual packet-integrity validation,
trusted QP/PD/peer/PSN context, the MR table, the unchanged generated transport,
an authorized full64-bit backend command and completion-gated wire responses.
It is deliberately bounded to one configured QP, one outstanding operation,
IPv4, WRITE_ONLY and READ_REQUEST of1..4096bytes. There is no initiator SQ in
this wrapper. Invalid requests never enter HLS, so they cannot advance its
PSN or cause a memory command. Local rejection events are **not yet remote
access NAKs**, and retransmitted/duplicate requests are not yet recovered.

Saved authorized context, not the truncated HLS address/routing, supplies the
backend DMA address. All94meaningful HLS command bits are checked against
that context first. WRITE pad bytes are removed. Successful tagged backend
completion is required before exposing even the first response beat. MR/QP
changes remain blocked until backend completion AND the response's final beat
drain. Command/data/status mismatches cause a sticky fail-closed fault; a
fault does not release a possibly active memory lease. Reset recovery still
requires external DMA draining/QP closure/fresh keys; it is not implemented
by clearing this module. See [backend contract](../../docs/ROCEV2_RESPONDER_API.md).

The actual-generated-HLS offline probes are:

```sh
python3 rdma/rnic/tests/probe_protected_responder.py \
  --hls-build /path/to/tested-read-hls-build --report /path/to/fresh-report.json
python3 rdma/rnic/tests/probe_protected_boundaries.py \
  --hls-build /path/to/tested-read-hls-build --report /path/to/fresh-boundary-report.json
```

Selected evidence: `rocev2-rnic-protected-responder-003.json` covers19inputs
(13authorization/framing/context rejections,1ICRC drop,5successful operations),
stale-key reuse, blocked invalidation and high64-bit VA/DMA addresses.
`rocev2-rnic-protected-boundaries-002.json` covers1/64/4096-byte WRITE/READ,
all4161bytes in EACH direction, guard bytes and24-bit PSN wrap. Actual
response IPv4 checksums/ICRCs/QPNs/PSNs/AETH and every payload byte are checked.

`make check` also runs bounded admission/backend-contract RTL units with an
**explicit transport stub** for malformed command/address/length/route/QP,
write keep/last and failed/wrong-tag completion injection. These unit tests
are NOT the actual-HLS wire/interoperability evidence above. No test loads
a driver, performs host DMA, programs hardware or changes network/fan state.
The full RNIC/verbs/board integration remains unfinished.

The actual controlled/paged path can additionally run through both native-
shaped DMA mux levels and the actual generic Corundum PCIe engine:

```sh
python3 rdma/rnic/tests/probe_controlled_pcie.py \
  --hls-build /path/to/tested-read-hls-build --report /path/to/fresh-report.json
python3 rdma/rnic/tests/probe_controlled_pcie.py \
  --hls-build /path/to/tested-read-hls-build --completion-error read \
  --report /path/to/fresh-read-UR-report.json
python3 rdma/rnic/tests/probe_controlled_pcie.py \
  --hls-build /path/to/tested-read-hls-build --completion-error fence \
  --report /path/to/fresh-fence-UR-report.json
```

These finite manual probes replace descriptor/status/RAM *agents*, not the
actual hardware. Hard IP/link/TX-sequence generation/root-complex/host memory
are still modeled. The new native profile needs engine `DMA_TAG_WIDTH=19`
to retain16application bits after both routing levels. The existing board
configuration is not changed. See`docs/ROCEV2_DMA_BACKEND.md` for the actual
checks, explicit posted-visibility model rule and remaining native gates.

## Corundum DMA backend candidate

`rtl/rocev2_corundum_dma_backend.v` and the original Corundum RAM/source/sink
implement staging, actual application DMA descriptor interfaces, a required
WRITE visibility readback fence and READ-error zero drain. Full-width RAM
address/byte extent and tagged/drained ownership are guarded. `enable` stops
new work, not live DMA. Page pinning/SG translation, actual PCIe engine/link,
native board/kernel/provider integration remain unfinished.

`test_corundum_dma_backend_rtl.py` supplies14bounded RTL tests with a clearly
modeled descriptor engine/host memory. `probe_protected_dma.py` additionally
connects the actual generated HLS and protected responder through the real
backend/Corundum staging path; the earlier direct source/sink is removed.
Its19-input sequence and all65-byte payloads pass, including two readback
fences. It STILL models the PCIe engine and is not native host-DMA evidence.
See [DMA contract and evidence boundary](../../docs/ROCEV2_DMA_BACKEND.md).
The backend's isolated4ns physical probe passes, but full-board/native PCIe
DMA is not verified. `make check` now runs32MR/admission/backend test methods.

```sh
python3 rdma/rnic/tests/probe_protected_dma.py \
  --hls-build /path/to/tested-read-hls-build --report /path/to/fresh-dma-report.json
```
