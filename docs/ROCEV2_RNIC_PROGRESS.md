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

Explicit publication snapshot (2026-10-21): progress162–165 and the CURRENT,
unfinished166 RNR component sources/reports are included at the user's request.
Local/unpushed/previous-HEAD/live-build statements below are checkpoint history.
No build is currently running. The active functionality goal is not complete;
this publication does not narrow any of the eleven original requirements.
Generated/vendor build artifacts, credentials, binaries and private agent/cache
administration remain excluded. Existing successful AND failed evidence stays
unaltered. No hardware, driver install/load, network, fan/BIOS, flash or reboot
action is performed for publication.

In-progress166 adds `derive_receive_write_rnr_ack.py`, extending the existing
single RECV/WRITE ACK sequence with a distinct368-bit RNR owner and384-bit
wire proof. It requires the real captured negative ACK, accepted EOF, SFD/MAC
receipt and1024-cycle tail before independently backpressured proof and exact
retirement. It does not invent a posted RQ, positive WRITE/HLS receipt or CQ.
[Component002](../results/2026-10-18/rocev2-rnic-receive-write-rnr-ack-002.json)
PASSES all58 old+20 new modes and both legacy fixtures under unchanged10s,
4ns/100000-cycle gates. The new actual-MAC mixed path is RNR/WRITE/RECV/RNR,
four full frames and fresh shared tags6001..6004. RNR body/producer and HLS/
controller boundaries remain MODELS; this is not generated-HLS/native retry.
[Failed component001](../results/2026-10-18/rocev2-rnic-receive-write-rnr-ack-001.json)
is retained: mode90 initially cleared a bit already zero;002 changes only the
fixture mutation to the actual syndrome bit. The DUT derivative is unchanged.

`rocev2_segmented_write_rnr_control.v` and its24-mode test are new WIP, NOT
connected to the native hierarchy. The intended path retains the rejected
WRITE identity, binds a fresh typed RNR owner before issuing the HLS event,
and waits for wire proof and ACK retirement before the local error consumer.
[Controller001](../results/2026-10-18/rocev2-rnic-segmented-write-rnr-control-001.json)
FAILS during test port parsing. After a parser-only correction,
[controller002](../results/2026-10-18/rocev2-rnic-segmented-write-rnr-control-002.json)
still FAILS at mode0's final lifecycle assertion; the remaining23 modes were
not executed. A
[read-only observer](../results/2026-10-18/rocev2-rnic-write-rnr-control-observer-001.json)
against the exact frozen failing bench and unchanged DUT observes the actual
REPORT handshake, then IDLE/counts1/fault0 before the following negedge. The
fixture checks combinational guards immediately after withdrawing VALID with
no settling delay; this is diagnostic evidence only. The original failure is
NOT relabeled and no fix/retest is included in this publication.

The latest completed integrated milestone remains profile8 native36 and the
matching software-source/callback/native-CQ tests in165 below. Incoming WRITE
RNR/same-PSN retry/NAK still require actual native and real-peer integration.
Full1MiB native, multiSGE, live registered Linux/provider references, safe
partial-HLS teardown, congestion, original4ns/default1.08ns/full-board timing/
fit/CDC/DRC/routing and short supervised physical work remain. HLS15.571ns
still FAILS and13 native UNOPTFLAT warnings remain unwaived. The publication
rerun of `scripts/check.sh` still FAILS on the historical TX-padding SHA
mismatch; no overall suite pass is claimed. BIOS Medium, management networking,
oneSGE, `IB_ATOMIC_NONE`, both zero global drains and rollback images stay intact.

Progress165: previous164 was PROGRESS (distinct profile8 sources, actual
CQ predicate140800/provider9 passes and verified-live fresh native build).
All363 authored/174 public-report/614 live-input hashes revalidated. SAME
session68327/runner2909319/compiler2909330 was polled, not restarted. The
new matching131071/511/13/63 native36 is now TERMINAL PASS:894.627967s build,
maximum9.733767s/case, original1200s/30s/4ns unchanged. All36 old raw inputs
and every data/owner/cardinality summary remain exact; only EXPECTED identity
constants change. [New-identity native audit001](../results/2026-10-18/rocev2-rnic-segmented-write-profile-native-diagnostics-001.json)
PASSES2998 bindings; all197 generated HLS files and actual sole native
MR/PTE/backend/nonce/ACK/RQ/controller multiplicities match.13 UNOPTFLAT
warnings remain unwaived; no loop or physical timing closure follows.

`build_segmented_write.py` then froze the matching source and actually
built/linked modules with real running-kernel headers in10.842521s under
original180s. No module was installed or loaded; Atomic_NONE/defaults stay.
[Kernel build001](../results/2026-10-18/rocev2-rnic-segmented-write-kernel-build-001.json).

New boundary models support the explicit profile8 tuple without changing
old profile models. [Actual standard callback202 cases](../results/2026-10-18/rocev2-rnic-segmented-write-kernel-post-001.json)
PASS under ASan/UBSan, compile8.364628s and original10s/case. All170 old
case names and summaries remain identical;32 WRITE-notice cases add zero and
nonzero notification capacity, lengths0/1/4096/4097/8193/1MiB, old-profile
refusal, bad tuples/geometry/WRs, bad whole owners/epochs/cookies/proofs/
errors/counts, full CQ/backpressure and ambiguous RQ producer ACK. Actual
standard C posts/checks exact128-byte records and keeps/releases its MR/RQ/CQ
references correctly.1MiB completion input is MODELED, not native payload.

[Unedited-native-CQ95 cases](../results/2026-10-18/rocev2-rnic-segmented-write-kernel-native-cq-001.json)
also PASS (compile7.383391s, each <=10s). All18 old pairs/four mutations each
remain, plus the new WRITE/Immediate pair. The actual NEW native33-word CQ
with8193/flags3/Immediate89abcdef/CQC511 and its original genuine zero-capacity
C128 receive record are read WITHOUT rewriting observed data. Standard C
post_recv emits the same128 bytes. poll_cq yields one IB_WC_RECV_RDMA_WITH_IMM
with byte_len8193/BE Immediate, despite posted capacity0, and exactly one CQ
ACK. Zero RQ gains no invented local payload-MR work ref: the separately
registered MR remains registered/refcount1 until explicit cleanup. Four
malformed in-memory copies retain the owner and do not ACK/unpin or publish a
false completion. The original native input/event files remain unchanged.

[Matched source audit001](../results/2026-10-18/rocev2-rnic-segmented-write-native-software-diagnostics-001.json)
PASSES2130 exact bindings across actual new native36, real-header kernel,
callback202, native-CQ95, provider9, policy140800 and the strict old-tuple
build rejection. The semantic-tested CQ header equals the actual frozen module
header byte-for-byte. Old failed receive-post001 remains failed (exact
preimage); successful old170 baseline002 is distinct. Initial audit attempts
corrected ONLY the frozen-input map base directory and selection of that
actual successful old baseline; DUT/test/data/gates were not changed.
Exact initial audit source preimages are retained locally. The model-source
startup checker also narrowed an ambiguous derivation anchor to its exact
full geometry expression; no actual kernel/hardware gate was relaxed.

This is SOURCE and SNAPSHOT coupling, not live Linux/RTL/provider execution.
Linux primitives/pins/MMIO/coherent DMA and provider syscall/WC replies are
explicit models. Registered physical page/QP/MR lifetimes and actual PCIe/CPU
visibility remain unqualified. All11 remain: full1MiB native/multiSGE,
incoming segmented WRITE wire RNR/NAK/retry, real-peer MSN/recovery/congestion,
privileged partial-HLS cleanup, original4ns/default1.08ns/full-board fit/
setup/hold/CDC/DRC/routing and short supervised physical behavior. HLS15.571ns
still FAILS; no image/install/load/reboot/fan/BIOS/network/Git action. No active
jobs;162–165 local after7234cab. Next coarse feature boundary is real wire
RNR/NAK/retry for retained incoming WRITE messages, not silent capability
expansion or timing waivers. Historical scripts/check.sh TX-padding identity
failure remains, and no overall goal/whole-suite/physical completion is claimed.

Progress164: previous163 was PROGRESS (actual complete native36 execution and
4366-binding audit). All351 authored/170 report hashes revalidated unchanged.
All11 remain. No automatic Git/driver/hardware/default action is authorized.

New `derive_segmented_write_profile.py` gives the same qualified native WRITE
graph a DISTINCT source identity: RNC131071/CQC511/SQC13/RQC63/profile8.
Exactly THREE leaves change: control/CQ/queue CSR feature words only. Native
payload/owners/PSN/MR/PTE/backend/nonce/HLS/ACK/RQ/CQ gates and old identities
remain byte-identical. Full native elaboration001 PASSES8.167276s with no
missing leaves/HLS stubs/port-width waiver and identical module counts.
Fresh matching native36/session68327 is LIVE; original1200s build/30s cases/
4ns clocks/root1GiB/RAM4GiB guards remain. Only EXPECTED capability words
change in the existing complete36 test fixture; observed events/data are NEVER
normalized. The old65535 successful binary is not used as new131071 proof.

`derive_segmented_write_kernel.py` adds profile8 to the actual standard verbs,
MR/QP/native graph, ring codec/replay and CQ semantic paths. It requires the
exact131071/511/13/63 tuple/geometry; old/default cohorts remain. The actual
C128 large/zero RECV codec is reused, not a user DMA/BAR/payload-copy bypass.
Only profile8 accepts flags3 WRITE notification bytes through1MiB; profile7
still limits that class to4096 and retains its1MiB non-WRITE receive semantics.
[CQ semantics001](../results/2026-10-18/rocev2-rnic-segmented-write-cq-semantics-001.json)
PASSES140800 actual C predicate combinations under UBSan, including all256
flags, all profiles/unknowns, zero/4096/4097/8193/1MiB/oversized lengths and
five capacities.128000 old/unknown rows are exactly unchanged. This is NOT
execution of the real MR/queue/CQ callback lifetimes or1MiB native transfer.

`derive_segmented_write_provider.py` retains all8 old firmware identities and
adds131071, using the same real standard uverbs/libibverbs marshalling.
[Provider001](../results/2026-10-18/rocev2-rnic-provider-segmented-write-001.json)
PASSES all9 profiles. New chained zero-capacity RECV requests exercise bad-WR
errors and WRITE-notice WC lengths0/1/4096/4097/8193/1048576, actual RDMA-WITH-
Immediate opcode and big-endian Immediate values. The syscall/WC producer is
a MODEL: this does not prove kernel callbacks/native CQ or real1MiB data.

New `build_segmented_write.py` will freeze/build/link real running-header
modules ONLY after the exact NEW native tuple and all36 actual cases pass.
Its actual invocation with the old successful65535 native36 report is rejected
BEFORE creating a build report or compiling modules. [Source diagnostics001](../results/2026-10-18/rocev2-rnic-segmented-write-software-source-diagnostics-001.json)
PASSES652 bindings across the semantic/provider/native-boundary evidence and
this negative gate. Eleven reviewed kernel leaves change in a separate source
cohort, not installed/default files. Atomic_NONE stays. Actual new module build,
callback/reference lifetimes and UNEDITED matching native33-word WRITE CQ
consumption are NEXT, not proved by these source/predicate/provider checks.

The initial development command mixed kernel/provider module search paths
(duplicate `derive_atomic_access` basenames); separate subprocesses with each
owning path resolved that startup-only import error. A provider CLI attempt
without required `--rdma-core` stopped at argument parsing; the actual reported
run uses the same pinned local rdma-core tree as previous successful cohorts.
Neither is a DUT failure or a waived test. No existing source was changed to
hide either diagnostic. Matching native compile retains13 UNOPTFLAT warnings.
All11/full1MiB native/multiSGE/live registered APIs/recovery/partial-HLS cleanup/
original4ns timing/physical remain. No image/install/load/reboot/fan/BIOS/network
or Git action. New source work is local after explicit publication7234cab.

Progress163: previous162 was PROGRESS (actual header-gate512 runtime, new
36-case full native fixture and a verified-live fresh compile). Checkpoint162
350 authored/168 public-report/618 live-input hashes all revalidated exactly.
The SAME session74185/runner2905891/compiler2905912 was polled, never restarted
for an observation timeout. Its actual terminal result is now SUCCESS.

[Native-full002](../results/2026-10-18/rocev2-rnic-segmented-write-native-full-002.json)
PASSES ALL36 actual executions. Compile896.666412s remains below1200s; new
WRITE8.832630s/WRITE+Immediate9.433548s and maximum9.533906s (large SEND+IMM)
remain below the original30s/case. Actual typed generated HLS/native PSN/
MR/PTE/PCIe TLP/global physical nonce/visibility fence/sole dual-owner ACK/
MAC/XGMII/FCS/SFD/receipt CDC/whole CQ execute together, not trace models or
the earlier component's descriptor-only RAM engine. All three424 owners,
456 HLS receipts and atomic native expected-PSN commits match. Full8193 host
bytes/padding/sentinels and ACK frames match, with four whole/per-packet MR
queries, three real memory commands, five scattered page writes, three
actual fences/ACKs and strict no-positive-SFD-before-fence checks. FIRST/MID
consume no RQ; LAST Immediate alone consumes the real zero-capacity C128 RQ
and produces ONE whole8193/flags3 CQ and genuine host ACK. Holding its final
MAC receipt1100 cycles retains the actual PSN/message/RQ/CQ ownership.

Every34 old case passes on this NEW binary, including large READ/SEND/WRITE/
Immediate, incoming SEND/Immediate, zero RQ/RNR/ordinary services, requester
CAS/FADD, mixed Atomic and permission denials, and all five zero operations.
Every original raw-input hash and every available summary oracle is identical,
not normalized or copied as execution proof. The old successful34 binary and
all frozen failures remain intact. New binary SHA is
`b9282fe6a0b708ba82a978a5047f054dfd754bff70e3acac1eec20dcd1eb9e3d`.

[Runtime diagnostics001](../results/2026-10-18/rocev2-rnic-segmented-write-native-runtime-diagnostics-001.json)
PASSES4366 exact bindings. Actual executable-bench module counts match native
elaboration, including the single shared MR/PTE/backend/nonce/ACK/RQ and the
real WRITE controller/frontend/bridge. All197 same-generation HLS RTL/data
files are selected. Full001 `.dat` startup failure and exact source preimages
are retained; header-gate and fixture audits are separately bound. Native
inputs are two-state; physical host/root/peer/PHY/PTP are still MODELS, not
live pinned Linux or physical PCIe ordering. Real native TLP behavior is not
itself physical host-ordering proof.

Warnings are not erased: the old34 build had12 UNOPTFLAT warnings, the new36
has13. Existing CRC/priority nodes overlap, and native configuration/admission/
guard cones expand. Actual runtime success does NOT establish loop-free or
original setup/hold/CDC/DRC/routing closure. HLS estimate15.571ns still FAILS
the original4ns/default1.08ns; full-board fit/timing remains unqualified.

Next feature boundary is software: current exact profile7 still accepts
WRITE/Immediate flags3 receipts only through4096 bytes. New native8193/flags3
and zero-capacity ownership must reach a NEW explicit matched kernel/provider
capability cohort; do not silently widen the old profile or advertise support
on an older core. Full1MiB native/multiSGE, registered live Linux refs/verbs,
real-peer NAK/RNR/recovery/MSN/congestion and partial-HLS teardown also remain.
All11 original requirements stay open. No active feature jobs, install/load/
program/fan/BIOS/network/reboot/Git action.162–163 local after explicit7234cab.
`scripts/check.sh` still fails the historical TX-padding source/report hash
identity check; no whole-suite or physical release success is claimed.

Progress162: previous goal turn was PROGRESS: actual native controller
insertion and complete native elaboration001 passed. The intervening explicit
user-requested51-file publication7234cab includes157–161, successful and
failed reports. This goal turn does NOT authorize automatic further Git or
hardware/default changes, and all11 requirements remain unchanged.

The ACTUAL native-only `allow_header` extension now has four-state runtime
evidence, not just the earlier base classifier512. [Header-gate001](../results/2026-10-18/rocev2-rnic-native-write-header-gate-001.json)
PASSES all256 opcodes x2 current-message states/512 frames. Each FIRST is
offered for5 cycles with opposite old classification and alternating0/X
admission:2560 cycles accept no header/output and retain the configuration
guard. After release with current message state, admission closes again
immediately after FIRST; SECOND, buffered headers and BODY still drain with
the original every-byte/KEEP/EOF/stall assertions. Compile/runtime10s,
4ns and100000cycles stay unchanged; runtime0.087117s. This is the actual
native router leaf, not a complete native payload or physical proof.

`segmented_write_payload_native_fixture.py` adds two8193-byte incoming
WRITE/Immediate cases to all34 old native cases. Full independent424 token,
456 generated-HLS receipt and actual native expected-PSN commit are checked,
with four real whole/per-packet MR queries, three MR-relative memory commands,
five scattered PCIe page writes, three actual visibility fences/ACK SFDs and
exact full host payload/pad/sentinels. Only LAST Immediate may consume a real
zero-capacity coherent RQ; its whole CQ must still report8193/flags3, not the
capacity0 or LAST1 byte. Final actual MAC receipt is held1100 cycles to forbid
premature PSN/guard/CQ retirement. These are NEW TEST REQUIREMENTS, not passes.

[Fixture diagnostics001](../results/2026-10-18/rocev2-rnic-segmented-write-native-fixture-diagnostics-001.json)
PASSES recipe/input provenance only: all34 old descriptors/order and359
original fatal messages survive,37 new fatal checks added, no internal force.
New raw Ethernet beats are261/260/4 ordinary or261/260/5 Immediate. Existing
native MR first offset3565 + relative528 = host offset4093;8193 bytes end at
12286, so the same THREE sealed pages suffice (unlike a different component
geometry with MR-first4093). This is not a page-count assertion relaxation.

Fresh actual native-full002/session74185 is building with the exact actual
elaboration001 selected RTL and ENTIRE same-generation197-file HLS manifest.
No old executable/object is reused. Original1200s build,30s/case,4ns clocks,
1GiB root/4GiB RAM guards remain. Full001 stopped before bench generation:
the selector incorrectly looked for `.dat` hashes in the RTL-only source map.
Its failure and exact preimages remain; the corrected selector verifies ALL
actual `.dat` paths/hashes against the original generated-HLS manifest, not
a fallback/missing-file waiver. No DUT gate, expected payload or timeout changed.

At this checkpoint compilation is LIVE, not successful or timed out. Its13
UNOPTFLAT warnings include existing CRC/priority paths and newly expanded
native admission/configuration/guard cones; they are retained and NOT waived.
Neither source/fixture audit nor eventual compilation can substitute for the
new36 runtime cases or full-board original setup/hold/CDC/DRC/routing proof.
Software flags3 ceiling4096/default Atomic_NONE/installed profile/BIOS Medium/
management networking stay unchanged. No reboot, JTAG, flash or load test.

Explicit publication update (2026-10-21): this snapshot includes progress157–160
and the current progress161 integration work, with both successful and failed
reports. Local/unpushed statements and older public HEADs below are historical.
The explicit push does not complete the broader goal, authorize future
automatic pushes, or qualify a new hardware/software release. All11 original
requirements and the original timing/default/safety gates remain unchanged.

Progress161 adds `derive_segmented_write_native.py` and
`check_segmented_write_native.py`. The real checked-frame WRITE controller is
now placed in the COMPLETE native graph, not just exported through boundary
ports. It consumes the actual typed generated HLS set and native QP/PD/epoch/
expected-PSN context. Its full424/MSN/proofs commit updates the actual native
expected PSN on the SAME edge as frontend DONE. New memory arbitration uses
the SAME MR table/PTE/backend/global physical nonce; ACKs use ONE dual-owner
RECV/WRITE allocator. Actual late-RQ head peek, LAST-only680 HLS owner,752
packet/776 whole receipt,472 MAC proof and whole-CQ retirement are wired.
The positive TX-visibility gate requires actual data EOF and fenced status.
No private MR/PSN model or invented RQ/status/MAC/CQ/drain proof is substituted.

The WRITE classifier precedes the existing Atomic classifier. A native-only
`allow_header` gate blocks ONLY a new FIRST header while terminal WRITE is
still held, so a following READ/SEND is not classified as the old message.
Already accepted SECOND/header/body beats keep their existing drain gates;
the continuation override follows actual message-active state, not the wider
completion guard. This new header-admission extension is compile-checked but
has NOT yet had a separate runtime test. Earlier512-frame classifier evidence
covers the base classifier only, not this extension.

[Native elaboration001](../results/2026-10-18/rocev2-rnic-segmented-write-native-elaboration-001.json)
PASSES8.224583s under the original180s/1GiB hierarchy gate, all original11
feature switches enabled. It selects447 actual RTL files and verifies sole
HLS/MR/PTE/backend/nonce/ACK/RQ multiplicities, actual native PSN/HLS domains,
both global HLS drains0 and no missing-leaf/port-width waiver or HLS stub.
This is ELABORATION ONLY. Fresh all34 unchanged prior native cases PLUS new
incoming8193 WRITE/WRITE+Immediate with live generated HLS/PCIe TLP/DMA/fence/
MAC/CQ/PSN still remain. Neither the old34-case binary nor component trace
models count as this new runtime proof. Full1MiB native, multiSGE, matched
Linux/provider/verbs lifetimes, wire NAK/RNR/recovery/congestion and safe
partial-HLS-message cleanup remain open. The old15.571ns HLS estimate still
FAILS the original4ns/default1.08ns requirement; no full-board pass follows.

Before publication edits, all343 authored/164 public-report bindings from
checkpoint160 and all502 source/13 persistent-artifact/1 RAM-artifact hashes
in new native elaboration001 were rechecked with no mismatches. All new
Python sources parse and all new JSON reports parse. Original pre-publication
documentation is retained locally for historical hash resolution. There is
no active feature build and no FPGA/driver/network/fan/BIOS/reboot action.
`scripts/check.sh` retains its historical TX-padding source/report hash failure;
no overall test-suite success or physical release is claimed by this push.

Progress160: previous159 was PROGRESS (actual typed-HLS/native boundary
elaboration and MR-island8). All338 authored/158 report hashes revalidated.
Public HEAD fbea645 remains;157–160 local. All11 requirements unchanged.

New `rocev2_segmented_write_controller.v` actually combines the checked
frontend and packet-memory leaf. Full424/MR/true-length identity reaches
real HLS and ACK owner handoffs; LAST Immediate separately emits genuine
680-bit RQ owner and real parsed32-bit Immediate/620 RQ placement. No fake
RQ is emitted for FIRST/MID/plain LAST. The original frontend gains ONLY
read-only parsed Immediate output in a separate native derivative, with
every original gate/byte reconstructing exactly. No raw RETH/key authorizes
physical DMA, no status/core/MAC/CQ proof is invented.

Two native-level ordering gates are explicit. Positive ACK TX is released
only by actual payload EOF AND the actual tagged fenced backend status,
not HLS/quiet/SFD alone. The same four-consumer DONE/token/MSN/proofs must
transfer to the real frontend AND native expected-PSN endpoint on the SAME
edge. With either consumer stalled, neither packet nor PSN advances. ACK
retirement remains separate; real late-RQ/whole-CQ ownership survives.
Partial HLS-message teardown is unproved, so cancellation/drain inputs stay
disabled, not a manufactured safe cancel/unpin/reset path.

[Controller003](../results/2026-10-18/rocev2-rnic-segmented-write-controller-003.json)
PASSES ALL14 original bounded modes. Actual whole IPv4/ICRC/FIFO/checker,
frontend/replay/MR/lateRQ/controller/memory/nonce/PTE/staging RAM/fence/
ACK/MAC/FCS/SFD/CDC execute together. Complete8193 bytes and host sentinels
match, raw replay8344 ordinary/8348 Immediate bytes are unchanged, with
5 scattered write descriptors/3 fence and nonce commands/3 actual ACKs/
3 native commit transfers. True zero-capacity notification produces one
full680 HLS RQ owner ONLY on LAST and an8193 whole CQ ticket. Missing native
commit READY keeps frontend and packet live; backend fence not yet done
keeps even the first positive MAC SFD absent. Bad physical status/partial
DMA/fence/HLS MSN produce0 SFDs and0 commits, retain MR/QP/RQ guards; bad
LAST padding leaves only the2 real prior packet commits/PSN4.

Compile1.442s/max5.283s, original10s/4ns/100000cycles unchanged. Whole raw
producer phase covers CRC buffering/replay (bounded4000 cycles), not the
old metadata-only300-cycle boundary; no MR response deadline/shape/gate
was relaxed. Whole replay bytes, real680 RQ owner and exact typed token
oracles remain independent. HLS96/456/payload/ACK/whole-RQ inputs are models
or unchanged checked actual C++ traces. Native shadow-PSN endpoint, PCIe
descriptor/posted-host ordering, clock/PTP/PHY/CQ consumers are MODELS.
This is NOT live generated-HLS payload, actual PCIe TLP, full native/1MiB/
Linux/physical qualification, nor placement into the native gateway yet.

`derive_write_controller_leaves.py` also derives the native checked-frame
WRITE selector before the existing Atomic/normal selector. It classifies
06/07/08/09, or routes any frame to the retained WRITE message handler when
force is asserted; all original storage/stall/byte/KEEP/EOF gates remain.
Alternate port names retain Atomic ancestry only; classification supplies
NO authority. [Classifier002](../results/2026-10-18/rocev2-rnic-native-write-classifier-002.json)
PASSES every256 opcode x2 force states =512 five-beat frames (260 WRITE/
252 other), all bytes/KEEP/EOF preserved under stalls. Changing force after
the second header cannot reroute a frame. Original Atomic selector remains
unchanged and will stay after this classifier in complete native insertion.

Failed controller001 preserves fixture duplicate hierarchy observation and
one implicit1-bit queue-guard net. Only the fixture uses a single hierarchy
prefix and explicit8-bit declaration; controller/front/memory RTL unchanged.
Successful002 remains intact;003 adds only a genuine full680-LAST-only
owner oracle and retains every prior summary assertion. Preimages:
`write-controller-001-preimages-yNh3Q465`,
`write-controller-002-preimages-wZxjwwND`.
Failed classifier001 samples combinational configuration_guard in the SAME
negedge that its producer deasserts VALID, before continuous assignments
settle. Only observation moves1ns within the same4ns cycle; no added clock,
timeout/gate/expected-data/DUT change. Exact fixture preimage:
`native-write-classifier-001-preimages-F5zGavwa`. Original failures/logs/
frozen sources/binaries stay, no source normalization or success relabel.

[Audit001](../results/2026-10-18/rocev2-rnic-segmented-write-controller-diagnostics-001.json)
verifies447 bindings, actual source graph/module counts, exact raw images/
CRC/real MAC bytes and source/route parent reconstruction. Controller
subtree lint has no loop/latch/driver/port issue; warnings remain recorded,
NOT timing or board fit qualification. Historical TX-padding provenance
check still fails, HLS15.571ns still fails4ns/default1.08ns. No all-green claim.

Next remains complete native insertion, not another compatible-only test:
put this classifier BEFORE Atomic, connect controller to accepted native
context/shared MR/real typed HLS/RQ owner ports, add same shared-memory
client BELOW ordinary protection but BEFORE existing backend/global nonce,
replace the single ACK allocator with the reviewed dual-owner variant,
and bind native expected-PSN commit/true late-RQ/whole-CQ retirement. Preserve
all old paths and all34 original native regressions PLUS new WRITE/Immediate.
Keep full1MiB/matched software/multiSGE/live Linux refs, real privileged
partial-message HLS state cleanup, short real-peer recovery/RNR/MSN/
congestion and original-clock board/short supervised physical qualification.
No hardware/default/install/load/program/network/fan/BIOS/flash/reboot/Git
action. BIOS Medium/Atomic_NONE/oneSGE unchanged. No live job or reboot
needed. Restore all archived RAM caches and prove authenticated exact-thread/
goal revival before any necessary reboot. Pre-turn docs:
`write-controller-progress159-doc-preimages-zFtr00gJ`.

Progress159: previous158 was PROGRESS (connected packet MR/RQ/data/nonce/
PTE/RAM/fence/ACK-MAC14). All333 authored/150 public hashes revalidated.
Explicit public HEAD fbea645 stays;157–159 local. All11 requirements stay.

`derive_segmented_write_native_gateway.py` now threads actual native424
owner/456 receipt/sticky fault ports through9 leaves to the real typed002
HLS. Its whole generated module/data set REPLACES old007; no old/new helper
mixture or behavioral core. Shared remote ownership now includes a real
held WRITE owner. Protected native QPN/PD/epoch/known held/MR/QP guards
check new owner and query offers; unprotected/wrong-PD/non-WRITE/unknown
requests cannot handshake. ONE extra actual MR arbiter is BELOW existing
normal/SQ/Atomic query arbitration and ABOVE the SAME actual MR table.
Full64 address/offset/DMA/error/tag/length responses retain their owner.
Actual accepted native context/expected-PSN outputs are available to the
enclosing frontend, not reconstructed from a peer. No capability change.

[Native gateway003](../results/2026-10-18/rocev2-rnic-segmented-write-native-gateway-003.json)
PASSES full native ELABORATION8.172s with original root/RAM1GiB and180s
compile gates. Exact old34-case qualified selection is retained; one native
HLS/PSN/MSN/parser/service domain, one MR/PTE/backend/physical nonce and
all legacy paths remain. Existing3 MR arbiters become4; one actual new
WRITE-retire join exists. Both global drains remain0, original4ns/default
1.08ns/8QP/2000/READ1MiB/whole-RQ conditions stay. No missing-leaf waiver,
port-width coercion, old compiled binary or new default/capability release.

This is a BOUNDARY stage, NOT complete WRITE source insertion: the actual
checked frontend/packet memory/shared ACK/late-RQ/CQ controller still needs
connection to these ports, native expected-PSN packet completion and safe
partial-message cleanup. It does not claim new generated-WRITE payload
execution or rerun all34 old native cases. All runtime gates remain required.

[Native MR island002](../results/2026-10-18/rocev2-rnic-write-native-mr-gateway-002.json)
PASSES8 cases with original10s/4ns/100000-cycle bounds (max0.02s scale).
The exact compiled native MR-chain and new guard expressions are extracted
BYTE FOR BYTE: actual normal/SQ/Atomic/WRITE callers contend through three
query arbiters and ONE real epoch-required MR table. Same0xf123 tags never
alias replies, stalls preserve ownership, full64 offsets/translations and
denial zeroing match independent oracles. Stale WRITE key, wrong PD/op/X,
permission and range failures cannot authorize work. A completed lookup
does NOT release the modeled whole-message guard; actual MR invalidate
waits. After exact invalidation a WRITE lookup sees that SAME revoked key,
not a private namespace. Caller states/leases/management/response consumers
are MODELS; no complete native/HLS/DMA runtime is implied by this island.

Failed gateway001 preserves strict anchor failure before native compile:
RNIC routes whole output to `rq_message_data` and shared transport to
`core_recv_message_data`, not the generic pass-through name. Only those
exact routing anchors changed. Failed002 retains an actual successful
8.141s compile; the verifier then indexed an MR-arbiter count absent from
the old report. The old real elaborated binary is now hash-checked and
counted (3), then compared to new4. No default count or multiplicity waiver.
Preimages: `write-native-gateway-001-preimages-aotdW0iC`,
`write-native-gateway-002-preimages-t3XTiZ1M`.

Failed MR001 preserves seven successful modes, then the INVALIDATE fixture
incorrectly expects the allocated key to be returned. Exact read-only
frozen observer002 shows opcode2/error0/key0/quiet1, matching actual table
code. Only the opcode-specific management oracle changes, not RTL or MR
denial/invalidation semantics. Its preimage is
`write-native-mr-001-preimages-nmGbqkwQ`. First clock-only observer001 had
not sampled final VALID before the fixture's negedge abort; it is retained,
with exact preimage `write-native-mr-observer-001-preimages-Bp6Fip1P`.
Observer002 samples VALID rise, does not drive or alter any DUT/fixture.

[Audit001](../results/2026-10-18/rocev2-rnic-write-native-gateway-diagnostics-001.json)
verifies1432 source/artifact/failed/old bindings, actual9 boundary sources,
exact native MR-island bytes, unchanged prior successful summaries and
original native/HLS gates. The same historical TX-padding provenance check
still fails; HLS15.571ns still fails4ns/default1.08ns. No all-green claim.

Next is ACTUAL controller insertion, not more compatible-only compile:
route checked opcode06/07/08/09 frames to existing frontend without losing
Atomic/normal paths; bind true native context/MR/QP/whole-message guards;
connect packet memory through SAME shared backend/global nonce and sole
shared ACK allocator; preserve distinct620 late-RQ/whole-CQ retirement.
Add native expected-PSN updates only after full certified packet DONE,
and real partial-message HLS cleanup/lifetimes. Then exact fresh native
build/all34 prior regressions PLUS new WRITE/Immediate, full1MiB/matched
software/multiSGE/live Linux refs/short peer recovery/RNR/MSN/congestion and
original board fit/setup/hold/CDC/DRC/routing/short supervised physical work.
No install/load/program/default/network/fan/BIOS/flash/reboot/Git action.
BIOS Medium/Atomic_NONE/oneSGE unchanged; no live job or reboot needed.
Restore ALL archived RAM caches and prove authenticated exact-thread/goal
revival before any necessary reboot. Pre-turn docs:
`write-native-gateway-progress158-doc-preimages-qe4w5uzP`.

Progress158: previous157 was PROGRESS (shared real ACK/MAC58+2). Revalidated
all329 authored/144 report hashes before edits. Public main/origin/main
remain fbea645;157/158 local/uncommitted. All11 original requirements stay.

New `rocev2_remote_write_memory.v` accepts the actual message guard's
complete424 token/MR offset/address/notify/real RQ tuple. Independent held
handoffs deliver the SAME owner to HLS and the ONE ACK allocator. Every
meaningful96-bit HLS command field (including origin, VA routing, whole
packet length and LAST control) must match saved context, but its address
is NEVER backend authority. Only saved MR-relative offset/full key/true
packet length/tag reaches the backend. Wire KEEP/EOF/count and every pad
byte are checked; only actual payload bytes reach registered output.
Offered data/command remain stable on late faults/disable.

The actual backend's ordered fenced status must match the saved logical
tag, translated through real nonwrapping physical nonce. Real HLS456
token/MSN/error is held and forwarded to the shared ACK allocator; its
actual472 MAC proof must match that SAME456. Data EOF, fenced status,
HLS and ACK proof flags are individually earned before full424/MSN DONE.
No quiet time/global drain/constant producer certificates are substituted.
Frontend DONE and ACK packet retirement are distinct; the real RQ pair
must still participate on Immediate and the whole MR/RQ/CQ lease stays.
Partial HLS message teardown/unpin is NOT implemented by this packet leaf.

[Connected memory004](../results/2026-10-18/rocev2-rnic-remote-write-memory-004.json)
PASSES ALL14 modes. Ordinary/Immediate8193 and admission-disable/early-data
variants check every host byte/sentinel,5 actual scattered DMA64 page-write
descriptors,3 backend readback-fence commands,3 nonwrapping command nonces,
3 real ACK XGMII/FCS/SFD/receipt-CDC frames and3 full joined DONEs. Genuine
zero-capacity posted RQ is notification-only; actual queue yields one
8193-byte whole CQ ticket, not zero capacity or LAST1 byte, and retains both
remote and RQ owners through exact commit/retire. MR and page invalidation
remain blocked by live guards. Original10s compile/runtime,4ns/100000cycles
remain; compile0.677s/max2.700s. Actual MAC wire bytes/FCS/tags6001..6003
are independently decoded. Bad command/address/origin/KEEP/EOF/pad, HLS
token/MSN, wrong physical status, partial DMA and fence failures retain
authority and cannot publish false completion. Some negative vectors cause
real partial writes: this is fail-stop retention, NOT rollback/cancel proof.

Actual graph contains one guard/MR/late-RQ/memory/nonce/PTE/page splitter/
backend/Corundum RAM/sink/source/ACK/MAC plus real FIFO/CDC. It is still a
COMPONENT graph: metadata/trusted context/posted admission and HLS96/456/
payload/ACK/whole-RQ producers remain models or exact checked C++ traces.
Descriptor engine, posted-host ordering, clocks/PTP/PHY and CQ commit/
retire consumers remain explicit models. No actual PCIe TLP engine, live
new generated HLS, full native hierarchy,1MiB/live Linux or board executes.
Separate previous checks must not be combined into a whole-native proof.

All failed executions remain exact.001/002 fail compile on duplicate
retire-token net, then a ready net modeled as a reg and a monitor referring
to the unmapped rather than actual handshake. Only those declarations/
connections change.003 passes0..4, then early-data case5 correctly faults
on LAST: read-only frozen observer shows remaining1/wire4 but KEEP all64
and LAST0 before command issue. Only the fixture now supplies KEEP0x0f/
LAST1 there; the unchanged early-data-before-command assertion, full byte/
shape/pad oracle,10s bound and DUT remain. Preimages:
`remote-write-memory-001-preimages-RUG4en4n`,
`remote-write-memory-002-preimages-taynIuAK`,
`remote-write-memory-003-preimages-ffhUQpLN`. Observer, binaries, logs and
original failed reports remain. No DUT change hid any of these failures.

[Audit001](../results/2026-10-18/rocev2-rnic-remote-write-memory-diagnostics-001.json)
verifies398 bindings, exact fixtures/failures/reconstruction, independent
full MAC/bytes and actual module counts. Leaf lint preserves all warnings
and finds no loop/latch/driver issues; NOT a timing/fit proof. The old
TX-padding source-check mismatch remains and HLS15.571ns still FAILS the
original4ns/default1.08ns. No overall-green or complete native claim.

Next is complete protected-native insertion: actual raw frontend, SAME
native MR/PTE/backend/physical nonce instances, new typed generated002 HLS
and ONE shared ACK, preserving every old/default SEND/READ/WRITE/zero/
Atomic path. Replace the ENTIRE generated HLS module/data set, not mixed
007/new helpers. Qualify actual full-native elaboration and all prior34
regressions plus WRITE/Immediate; retain full1MiB/matched software/multiSGE/
live Linux refs, safe privileged partial-message state teardown, short
peer/RNR/MSN/recovery/congestion and original full-board fit/setup/hold/
CDC/DRC/routing/short supervised physical proof. No hardware/default/
install/load/program/network/fan/BIOS/flash/reboot/Git action. BIOS Medium,
Atomic_NONE/oneSGE stay; no live job or reboot needed. Restore ALL archived
RAM caches and prove authenticated exact-thread/active-goal revival before
any necessary reboot. Pre-turn docs:
`write-memory-progress157-doc-preimages-oe78WvZ5`.

Progress157: previous156 was PROGRESS (actual typed WRITE HLS87 and new
RTL generation, timing still FAIL). The intervening explicit user push is
verified main/origin/main/remote fbea645799fed384d7f8134810a1128be2ca4d28.
Its41 files publish154–156, not new native/physical success. Publication
doc preimages remain in `publication-progress156-SzMtIavH`; the ignored
push record binds old/new docs. All325 source/139 report hashes revalidated
with those exact publication-only doc changes before current work.

New `derive_receive_write_ack.py` extends the qualified message ACK leaf
with ONE shared nonwrapping class6000 sequence. No second allocator/domain
is introduced. Atomic/requester/zero-service/host tags keep their routes.
The full424 WRITE owner is separate from a genuine620 RQ; plain WRITE has
NO fake RQ. Whole-message identity, PD/epoch/key/extent/PSN and canonical
notify-only late RQ are checked, with full456 HLS error/token/MSN binding.
The existing full62-byte ACK/header checks use the same actual PSN/MSN.
LAST Immediate additionally requires the real752 RQ proof, matching length/
PSN/MSN/flags/full owner before transmission. Every qualified parent byte
reconstructs exactly by reversing only the explicit typed extensions.

The actual captured ACK is sent unchanged except fresh shared6000 tag.
Exact real SFD receipt plus accepted EOF AND the original1024-cycle tail
are still mandatory. WRITE472 and RQ768 proofs can stall independently.
The notify packet cannot release either identity until both proofs were
accepted and BOTH exact retire VALID/READY transfers occur together.
Correct early VALID waits safely; stale/wrong tokens quarantine. This
releases packet ACK ownership, NOT whole-RQ CQ/MR lifetime or partial-HLS
message state. No timing/drain/reference/CQ certificate is invented.

[Shared ACK003](../results/2026-10-18/rocev2-rnic-receive-write-ack-003.json)
PASSES ALL58 modes plus two unchanged legacy fixtures (old two-packet ACK
and real whole-message queue/three ACKs/one CQ). New positive cases cover
8193 WRITE/Immediate, zero-capacity notification RQ, mixed RECV/WRITE,
SFD without EOF, EOF without accepted receipt, independent completion and
paired retirement stalls, early matching VALID, prior drain0/X, other tag
classes and nonwrapping shared-sequence exhaustion.47 bad full owner/
RQ/core/header/PSN/MSN/KEEP/EOF/tag/retire/parent cases fail closed.
Max1.663s, compile0.6s scale, original10s/4ns/100000cycles unchanged.
One actual MAC-chain mode sends five whole mixed frames through real
128->64 async frame FIFO,25G XGMII MAC/FCS/SFD and timestamp CDC FIFO;
all full wire bytes, FCS, tags6001..6005 and five receipts match independent
Python decoding, with three WRITE and three independent RQ proofs.
Receipt FIFO is held1100 cycles and then backpressured; no fixed delay
substitutes its real acceptance. Exactly one ACK allocator, one MAC,
one async adapter/two async FIFOs are present in actual elaboration.

Typed456 receipts and ACK bodies are exact unchanged traces of the actual
87-mode C++ HLS test, rechecked against all284 independent token oracles.
Only selected8193 packets replay here, NOT a live generated-HLS instance,
full native1MiB or actual payload DMA. Privileged owner/RQ admission,
backend visibility/fence, whole-CQ and retire consumers, clocks/PTP/PHY
pins remain modeled boundaries. Separate previous raw/HLS/ACK successes
must not be combined into a native proof. The host-only CRC memoization
copy remains identical to the448-mask/55296-coefficient verified helper;
original vendor hardware/function/XORs are untouched.

Failed001 is retained: both old fixtures passed but three invalid Verilog
task declarations prevented the new fixture compile. Only that syntax
changed; original10s compile/runtime gates stay. Failed002 retains ordinary
WRITE success but an Immediate test mistakes READY on an unasserted RQ
VALID for a retirement. Read-only exact frozen observer shows held1,
both proofs accepted, WRITE VALID1/READY0 and RQ VALID0/READY1, fault0.
No retirement occurred. Only the two assertions change to require actual
VALID AND READY transfer; same busy/retention checks remain. No DUT change
was made after either failure. Exact sources remain in
`receive-write-ack-001-preimages-WpJcqto9` and
`receive-write-ack-002-preimages-dMstVq5Y`; observer/report/binaries retained.

[Audit001](../results/2026-10-18/rocev2-rnic-receive-write-ack-diagnostics-001.json)
verifies800 source/artifact/previous/failure bindings, exact parent and
fixture reconstruction, actual MAC/FCS/bytes/module counts and scoped
HLS trace replay. Leaf lint has no combinational-loop/latch/driver warnings;
all width warnings remain recorded, NOT a board timing qualification.
Historical `scripts/check.sh` still fails TX-padding provenance; exact
HLS estimate15.571ns still fails4ns/default1.08ns. No overall-green claim.

Next: wire the real typed HLS456 and ACK472 to an actual native remote
WRITE DMA/physical nonce/data EOF/visibility-fence join before frontend
DONE; independent true late-RQ packet/whole-CQ fanout must remain. Preserve
all normal SEND/READ/WRITE/zero/Atomic/default paths and SAME MR/PTE/backend.
Actual generated new native elaboration/runtime, full1MiB/matched software,
multiSGE/live Linux refs, short real-peer/RNR/MSN/recovery/congestion and
original-clock full-board fit/setup/hold/CDC/DRC/routing/short physical
qualification remain required. Partial-message HLS teardown/unpin remains
unproved; no modeled drain/reset substitute. All11 original requirements
stay intact. No install/load/program/hardware/default/network/fan/BIOS/
flash/reboot/Git action this goal turn. BIOS Medium/Atomic_NONE/oneSGE stay.
No live job remains; no reboot needed. Restore ALL archived RAM caches and
prove authenticated exact-thread/active-goal revival before any necessary
reboot. Pre-turn published docs remain in
`receive-write-ack-progress156-doc-preimages-0z49Rb5S`.

Publication on explicit user request (2026-10-21) includes progress154–156
source and successful/failed reports. All325 authored-source and139 report
hashes matched checkpoint156 before the publication-only documentation
update; exact prior docs remain in `publication-progress156-SzMtIavH`.
Local/unpushed and previous-public-HEAD statements below are historical.
`scripts/check.sh` was rerun and still fails the existing TX-padding
source/test identity gate. No new functional build or hardware action was
performed for publication; native integration, timing and all11 original
requirements remain open. Build products, caches and credentials are excluded.

Progress156: previous155 was PROGRESS (actual raw checker/MR/RQ/replay47
and exact CRC-mask448). Public HEAD remains be16288;154..156 stay local.
All eleven requirements remain intact, not a smaller component-only goal.

New `segmented_write_owned_transport.py` derives a distinct complete HLS
cohort from the qualified WRITE prototype without changing its sources.
`as02WriteOwner` carries the exact native424 token, separate from620 RQ.
The real segmented-WRITE parser validates token/RETH/PSN/count/offset/key/
whole-message identity, retaining the full320 prefix per QP through MID/
LAST. LAST Immediate additionally binds the real independent RQ's PD/epoch.
Dedicated fields carry this owner through actual payload and ACK/MSN
consumers. They do not repurpose an RQ/SQ or fabricate one for FIRST/MID.
Exact payload KEEP/EOF/count/zero-padding checking now covers ordinary
segmented WRITE too. Real payload EOF and actual ACK/MSN receipts must
match the complete token; a new lower-priority query reads the SAME actual
PSN table after RX/TX/QPI/other updates. Only then is the distinct456-bit
packet receipt published. No idle duration, fake status or global drain is
used; actual backend visibility/MAC/CQ still require separate native joins.

[Complete C++001](../results/2026-10-18/rocev2-rnic-segmented-write-owned-hls-001.json)
PASSES ALL87 exact modes: every65 old mode/summary plus one actual-consumer
withholding case and21 typed-owner/message/RQ negatives. Compile83.019s;
ordinary/Immediate WRITE4.642/4.732s; maximum old prior8.388s, original
600s compile/30s per mode and8QP/2000 geometry unchanged. Each WRITE mode
executes6 messages/284 packets through1MiB with independent every-full424
identity/tag/cookie/offset/PSN/MSN Python oracles, alongside unchanged full
payload/pad/ACK/whole-RQ byte oracles. Missing actual owner blocks execution;
withholding data EOF, ACK/MSN, SAME-table response or the real join blocks
receipt. Late missing RQ keeps the remote owner unconsumed. PD/epoch/cookie/
key/VA/total/PSN/tag mismatch, including valid-shaped changed message and
independent posted RQ contexts, cannot produce a receipt or command.

[Compatibility001](../results/2026-10-18/rocev2-rnic-segmented-write-owned-compat-001.json)
PASSES real owned Atomic/MR/memory RTL9 jobs plus unchanged8 Immediate TX
and8 Immediate RX consumers, compile26.199s/runtime1.016s under original
600s/30s limits. [Audit001](../results/2026-10-18/rocev2-rnic-segmented-write-owned-diagnostics-001.json)
verifies1116 current/old/failed bindings and all65 old summaries. Protected
native owner/peer/connection/RQ/memory boundaries remain models in these
HLS tests. Do NOT combine separate raw/HLS tests into a native proof.

The strict initial generator anchor failure is retained in
`rocev2-rnic-write-owned-source-startup-001.json` and exact preimage
`write-owned-startup-001-preimages-14oN9Wmy`: there are TWO actual top
overloads/interfaces, not one; both must expose the typed ports. Source
cohort001 is retained but superseded BEFORE any C++ execution/synthesis.
Inspection found consuming a remote owner before a late RQ was available
would lose it across parser retries. Cohort002 requires both available
before consuming either and is the ONLY current tested/build input. Exact
cohort001 generator preimage: `write-owned-cohort001-preimages-MhQdXyFh`.
Neither an old source/binary nor an easier compatibility-only run qualifies002.

The exact-source HLS builder requires all87 actual executions, every prior
old consumer, full token/byte/ACK/RQ logs and real owned-service compatibility.
It retains original1500MiB/7200s/4ns/default1.08ns/8QP/2000 and all old port
gates, adding actual generated424/456 ports and sticky fault-output checks.
RTL generation finished as ONE job `native-zero-service-hls-vwnhb_tj`, not
a restart of the old timed-out synthesis. [Generation001](../results/2026-10-18/rocev2-rnic-segmented-write-owned-generated-hls-001.json)
PASSES497.799s with actual424 owner/456 receipt/776 whole-RQ/sticky fault
and every old port verified. Frozen inputs and generated files are bound.
Actual estimates are112990 LUT/140339 FF/279 BRAM18K/0 DSP. The SAME15.571ns
estimate FAILS original4ns/default1.08ns (effective2.92ns); no relaxed clock
or timing/board pass. [Generated audit001](../results/2026-10-18/rocev2-rnic-segmented-write-owned-generated-diagnostics-001.json)
verifies741 further source/RTL/XML/log bindings. Tool/children exited
naturally; no synthesis remains live. This is generation/port evidence,
not new generated-RTL functional simulation or full native elaboration.

Before launch, four exact successful old scratch DBs were process/cwd/FD/
maps-audited twice, persistently compressed/fsynced with complete hash
manifests, compared to archives and RAM copies, and only then relocated
with same-path symlinks. No source/generated RTL/failure/log was removed;
all bytes remain accessible and restorable. Available root at start was
1715232768B > original1572864000B guard. ALL new and older RAM-backed DBs
must be restored and every manifest verified before ANY reboot; no reboot
is needed or authorized here. This archive is storage administration, not
functional evidence or an HLS completion claim.

Next: actual typed-HLS/generated-RTL integration with protected frontend,
shared MR/PTE/DMA/physical nonce/fence and ACK-MAC/SFD/EOF/tail/CQ fanout.
WRITE and real RECV must share ONE collision-free ACK tag allocator, keep
424 remote and620 RQ records distinct, and on LAST Immediate certify both
against the SAME actual ACK. No new tag class may collide with Atomic,
requester, zero-service, RECV or host classes. Existing HLS WRITE-message
state persists across FIRST/MID; modeled parent-drained/cancel is NOT safe
HLS teardown or unpin proof. Privileged partial-message teardown needs real
state/reference handling, not reset or forged idle. Full native1MiB, exact
matched new software, multiSGE/live Linux refs, short real-peer/RNR/MSN/
congestion and original-clock board/physical qualification remain mandatory.
No install/load/program/default/network/fan/BIOS/flash/reboot/Git action.
BIOS Medium, Atomic_NONE and oneSGE stay. Exact authenticated thread/goal
reboot revival is still unproved. Progress155 docs are preserved in
`write-owned-progress155-doc-preimages-r3MsGTeC`.

Progress155: previous154 was PROGRESS (actual message MR/RQ46 + old62,
non-authorizing peek fix). Public HEAD remains explicitly authorized
be16288;154/155 are local/uncommitted. All eleven requirements remain.

`rocev2_segmented_write_rx_frontend.v` now implements checked whole-frame
capture, privileged full356 native-context retention, IPv4/UDP/BTH/peer/
full-QPN/PSN/header policy and FIRST/MIDDLE/LAST/Immediate length parsing.
FIRST alone supplies the RETH/key/total; continuations use the existing
message guard's saved address/offset and exact per-packet MR checks. The
external query ports are intended for the SAME native MR namespace, not a
new private validator. Actual owner admission is required before the real
native-style AXIS replay register sees any beat. The complete unchanged
frame (including pad/ICRC) is replayed under stalls. Even correct-token
proof bits cannot advance execution before actual replay EOF. The full
message/context guard survives packets, shortage retries and CQ/retire.
No downstream data/fence/HLS/MAC/CQ certificate is invented by the module.

[Raw frontend005](../results/2026-10-18/rocev2-rnic-segmented-write-rx-front-005.json)
PASSES47 four-state cases, maximum2.077s with original10s compile/runtime,
4ns clock and100000-cycle overall bound. Uses actual IPv4/ICRC/FIFO,
frontend, message guard, MR table, late-RQ and registered replay bodies.
Normal8193, Immediate8193/8192, high64-bit endpoint4097 and continuation
tests compare every header/payload/pad/ICRC byte/mask/EOF to independent
authored input and the independent full424 token/MR translation oracle.
Plain8193 replays8344 wire bytes/3 frames, Immediate8348/3. RQ shortage
validates4 actual CRC frames but grants/replays only3, with5 genuine MR
queries; retry keeps the same PSN/offset/private tag and takes only1 RQ.
Bad actual ICRC yields1 drop/0 queries/0 grants/0 replay. Correct proof
before replay EOF faults with the message owner still held and0 completions.
Tag/cookie exhaustion, malformed RETH, high/stale keys, PD/permission/range,
bad metadata/proof/X values, cancel and mismatched retire checks remain.

The1MiB raw case intentionally proves FIRST extent admission, one4096-byte
packet and safe drained cancellation, NOT a full1MiB transfer. The original
metadata-only1MiB46-case proof stays separate. Private tags are not wire
fields: new raw26 does not pretend a peer can inject a reused private tag;
that original negative remains in unchanged metadata46. Trusted raw-reference
context/management, posted-RQ admission, downstream owner consumer and
backend/data/fence/HLS/MSN/ACK-MAC/CQ producers are MODELS at this boundary.
This is not the complete protected-native graph, actual payload DMA,
generated new HLS, live Linux/provider or real physical execution.

Original failed executions are immutable.001 times out before any clock
(read-only observer:2 time steps) while vendor constant LFSR masks initialize;
002's naive per-net compile-time masks instead hit the same10s compile
guard. New simulation-only helper memoizes the original index-independent
matrix prefix once per exact width and retains the original function and
all actual XOR/output bodies. No production/vendor source, polynomial,
port, clock, limit, checksum or frame policy changes.
[Exact-mask proof001](../results/2026-10-18/rocev2-rnic-CRC-constant-masks-001.json)
PASSES ALL448 state/data masks for32/64/96/128-bit CRC lanes,55296 complete
coefficients against the UNCHANGED actual vendor function (max0.059s/case).
Identical coefficients and XORs preserve four-state inputs, not merely a
sampled binary CRC model. The raw005 helper matches that exact frozen copy.

003 exposes a fixture READY race: deriving READY from a blocking posedge
scoreboard counter makes consumer and register sample different values.
Read-only frozen observer shows the same first beat across that transition;
only boundary READY driving moves to negedge, SAME whole-byte assertions.
004 then fails the old five-cycle MR-fault assertion before a full checker
frame reaches authorization. The raw producer now returns at the SAME
public MR/reject/fault/owner boundary as the old metadata producer. Full
CRC/frame latency is not MR response time; original five-cycle fault and
10s/4ns/100000-cycle assertions remain unchanged. All failures, exact
fixture preimages, raw logs/inputs and binaries stay retained.

[Audit001](../results/2026-10-18/rocev2-rnic-segmented-write-rx-front-diagnostics-001.json)
verifies902 current/prior/failed bindings, exact CRC masks, correct producer
phases and unchanged protected raw sources. The inherited historical
TX-padding source gate still fails; no overall-green or strict full-native
elaboration claim. HLS15.571ns still FAILS original4ns/default1.08ns.

Next remains actual insertion into the shared-native protected graph:
shared MR/PTE/DMA64 refs/nonce/fence, typed HLS ownership and actual MSN
readback/ACK-MAC/tail/whole-CQ fanout, genuine RNR wire behavior, exact new
HLS generation and matched software/native runtime. Full1MiB, multiSGE,
live Linux refs, short real-peer recovery/congestion and original-clock
board fit/setup/hold/CDC/DRC/routing/short physical proof remain required.
No HLS starts under the unchanged1500MiB guard (root~1.10GB). No hardware/
install/load/program/default/network/fan/BIOS/flash/reboot/Git actions.
No live job remains; no reboot needed. Restore ALL archived RAM caches and
prove authenticated exact-thread/goal revival before any necessary reboot.
Progress154 doc preimages: `write-rx-front-progress154-doc-preimages-vAD2RNk0`.

Progress154: previous153 was PROGRESS (new separate WRITE HLS65/RQ62).
The subsequent explicit publication is verified main/origin/main/remote
`be1628899bf5bb6d13a03c0528ff74c2c0d1acfc`; no further automatic Git action
is authorized. This turn executes the previously syntax-only remote-WRITE
guard with an actual REQUIRE_EPOCH MR table and real late-notice queue.
All eleven requirements remain incomplete; this is not a native release.

[Connected MR/RQ004](../results/2026-10-18/rocev2-rnic-remote-write-mr-notice-004.json)
PASSES46 four-state cases and ALL62 exact old queue modes on the new
variant. Original4ns/100000cycles/10s/8QP limits remain. Normal/exhausted
compiles0.042/0.039s; maximum new0.122s/old0.165s. Genuine high-generation
MR keys, trusted PD, remote-write permission, whole and per-packet extents,
64-bit offsets/translations and the inclusive top-of-address-space case
are checked against independent request/token oracles. One1MiB message
performs257 actual MR queries and256 granted/completed packet lifetimes.
Missing permission, wrong PD, stale/high keys, unregistered slot and a
whole-range overflow that still fits FIRST produce actual MR denials,
never substituted success responses. Unknown/tag/child-offset corruption,
bad sequencing, exact whole token, missing data/fence/HLS/MAC proofs,
stale cancellation and mismatched retire owners retain guards/fail closed.

LAST Immediate alone takes a distinct genuine posted620-bit RQ; zero/one/
17-byte notification capacity is not the remote DMA target or whole CQ
length. An absent RQ returns modeled error38 with no new grant, leaves
PSN/offset unchanged and retries the SAME packet/tag after a real queue
post. Actual MR invalidation cannot pass while the full remote320-bit
owner is held. Packet grant alone does not advance execution. Correctly
matched terminal/CQ/remote-retire fanout retains both owners under
backpressure; privileged cancellation cannot release an in-flight packet.
The actual guard and MR checks run, but metadata/integrity/trusted QP and
initial MSN, posted-RQ admission, backend data/fence, HLS/core/whole, actual
ACK-MAC/tail and CQ consumers are EXPLICIT MODELS in this component test.
No payload DMA, generated new HLS/native graph or live Linux executes.

Preserved failures:001's fixture missed the real MR management transfer
after reset and waited on an already unconsumed response. Read-only
observer proves no MR lookup or packet grant; only clock-edge transfer
sampling was corrected.002's ordinary WRITE passes, but actual Immediate
coupling times out at10s: notice VALID depends on protocol-gated RQ head
VALID, which depends on this same notice's combinational protocol fault.
Read-only frozen-DUT observer stops at4 queries/2 grants/111 time steps;
Verilator diagnoses the exact loop. New separate
`derive_write_notice_binding_queue.py` adds a posted-head observation port
independent of that same combinational fault. The peek NEVER authorizes a
take, MR or completion. Actual head/notice/protocol/CQ/retirement gates are
not weakened. Removing only the new module name/ports/peek assignments
reconstructs the qualified parent BYTE FOR BYTE; all62 old cases rerun.
003's negative offset vector injected FIRST query2 while its oracle expected
MIDDLE query3; only the injection phase was corrected, same fault/retention
assertions. All exact fixture/runner preimages and failed reports remain.

[Audit001](../results/2026-10-18/rocev2-rnic-remote-write-mr-notice-diagnostics-001.json)
verifies283 actual/current/prior/failed bindings plus read-only diagnostics
and unchanged protected sources. Its first reconstruction removal literal
left one inserted blank line; the failed auditor/preimage is retained in
`rocev2-rnic-remote-write-audit-startup-001.json`. Only that removal literal
was corrected, retaining exact-byte comparison (no whitespace normalization).
The inherited TX-padding provenance check still fails. HLS15.571ns still
FAILS original4ns/default1.08ns; no overall suite/timing/physical pass.

Next is actual protected opcode06/07/08/09 continuation/RNR admission,
full-message/per-packet shared MR refs/PTE/DMA64, generated new HLS,
genuine backend/ACK-MAC/whole-CQ fanout and exact matched software/native
runtime. Native1MiB, multiSGE, real-peer recovery/MSN/congestion, live Linux
refs and original-clock board fit/setup/hold/CDC/DRC/routing/short physical
proof stay open. No HLS synthesis starts below the original1500MiB root
guard (currently about1.11GB). No hardware/default/install/load/program/
network/fan/BIOS/flash/reboot/Git action; BIOS Medium, Atomic_NONE and oneSGE
remain. No live job or reboot needed. Restore ALL archived RAM caches and
prove authenticated exact-thread/goal revival before any necessary reboot.
Pre-turn publication docs: `remote-write-progress153-doc-preimages-HFkrIeg0`.

Publication on explicit user request (2026-10-21): publish the current
progress152/153 source and both successful and failed reports. Also include
the unfinished `rtl/rocev2_remote_write_message_guard.v`: its corrected
source passes syntax compilation, but no functional MR-table/late-RQ test
or native integration has run. The original syntax failure and exact
preimage remain separate. Do not infer authorization or persistent MR refs
are already proved merely from this leaf's interface. Current publication
rechecks the functional, native/software and WRITE-component evidence
audits; it does not repeat long builds or claim an overall-green suite.
The inherited historical TX-padding provenance check and original timing
failure remain. No install/load/program/network/fan/BIOS/flash/reboot change.
All eleven requirements remain open. Historical local/unpushed descriptions
below refer to their original checkpoints. Exact pre-publication docs are
retained locally in `publication-progress153-drkhvn`.

Progress153: previous152 was PROGRESS (actual corrected all34 native,
matched real-header profile7,170 callbacks/90 unedited snapshots/8 provider
identities). This turn adds missing segmented incoming WRITE/Immediate
functionality in separate HLS and late-RQ components, not another timing
optimization. All eleven requirements remain; no automatic commit/push.

`segmented_write_receive_transport.py` derives a new complete source from
qualified receive007 without changing it. Per-QP FIRST retains full64-bit
RETH target/total, offset and first/next PSN/base MSN. FIRST/MIDDLE require
full4096/no-pad fragments; LAST must exactly finish the declared total.
Only LAST advances MSN. The raw HLS memory command always uses the saved
RETH target+offset, never a posted RECV address/capacity. LAST Immediate
alone consumes a canonical distinct RQ and waits when it is absent. A new
typed internal write-metadata stream joins the genuine final packet data/
ACK/MSN readback proof before producing whole776 with total bytes/first
PSN/last PSN/Immediate. Packet proof remains752; no raw owner field is
repurposed. Existing small/zero WRITE Immediate produces its real metadata
on the same new internal path. The qualified old SEND helper remains;
the new top and checked harness use the new join. Native MR authorization,
backend visibility, real RNR/MAC/CQ coupling remain external requirements.

[HLS C++001](../results/2026-10-18/rocev2-rnic-segmented-write-receive-hls-001.json)
PASSES ALL65 exact modes: ALL44 old retained, two new complete WRITE modes
and19 malformed/sequence/RQ/padding negatives. Compile75.437s; new modes
3.899/3.979s, original600s compile/30s runtime and8QP/2000 geometry retained.
Each new mode executes6 messages/284 packets through1MiB, with independent
complete byte/padding/ACK/PSN/MSN Python oracles. Includes PSN wrap, Immediate
0/ffffffff/89abcdef-derived values, late RQ capacity0/1/17/8194/1MiB, one
actually withheld RQ, and data/ACK/table/whole-join stalls. Plain WRITE never
consumes a posted RQ or emits a receive notification. Immediate notification
contains the full written byte count, not its final packet or RQ capacity.
Peer, posted RQ and memory are models; this is C++ execution of actual HLS
consumers, NOT newly generated RTL or native MR/PTE/DMA/MAC/CQ/Linux proof.

Separate `derive_write_notice_queue.py` keeps the original message RQ and
adds a qualified late-notice variant. It accepts a full320-bit trusted
remote-message identity from a FUTURE real remote-MR guard, binds PD/epoch/
QPN to a genuine posted620-bit RQ, and keeps them distinct. Valid metadata
may wait for an actual RQ; it cannot manufacture a posted owner. The final
packet's real placement/core/MAC/visibility plus whole HLS receipt must match
the trusted full total/PSN span. Whole received bytes may exceed notification
RQ capacity; RQ memory is not written. Both the full RQ and remote identity
remain held through CQ ticket/commit and remote-MR retirement backpressure;
neither packet ACK nor an offered-but-unaccepted retire can release them.

[Late-notice RTL001](../results/2026-10-18/rocev2-rnic-write-notice-queue-001.json)
PASSES62 four-state cases: ALL48 old message-RQ cases plus14 new. Original
4ns clock/100000-cycle/10s limits remain; maximum runtime0.1673s. Positive
8193/1MiB/4097/8192 cases and initially absent RQ keep one posted/taken RQ,
one final-packet release and the actual whole byte count. Wrong PD/epoch/
key/range/QPN/unknown valid, wrong LAST PSN/whole first PSN/byte count fail
closed. Remote MR identity and placement/HLS/MAC/visibility proof producers
are explicit component MODELS, NOT actual MR/HLS/backend/MAC execution or
signals injected into a production native graph. The C++ and RTL component
tests are separate, not proof of their live connection.

Strict startup failures are preserved: HLS generator001 first used an
outdated top-call anchor, before writing any tree; exact source preimage
`write-receive-startup-001-preimages-4OP43K1j`. The queue generator001 first
matched an ambiguous retire suffix; exact preimage
`write-notice-startup-001-preimages-Eh6Gm2TM`. Only exact source anchors were
corrected; no oracle/limit/clock/geometry relaxation or old source rewrite.
[Audit001](../results/2026-10-18/rocev2-rnic-segmented-write-receive-diagnostics-001.json)
verifies863 current/old/failed bindings, every exact old mode, unchanged
qualified007 tree and protected raw sources. The unchanged inherited source
check still fails historical TX-padding provenance; no overall-green claim.

Protocol cross-checks used Linux RXE's request-resource and message-end MSN
handling ([resource checks](https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/+/5b10ff013e8a57f8845615ac2cc37edf7f6eef05/drivers/infiniband/sw/rxe/rxe_resp.c),
[message-end MSN](https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux.git/+/0275dc184aa007b260374af6d46fb15741c062a8/drivers/infiniband/sw/rxe/rxe_resp.c)).
No Linux implementation code was copied into the new HLS/RTL.

New actual full-message/per-packet remote-MR refs/protection, native opcode/
continuation/RNR admission, late RQ/packet/whole-HLS/backend/MAC/CQ fanout,
generated new HLS/complete native/runtime and exact matched software remain
required before claiming actual new WRITE Immediate support. Current native
profile7 all34 evidence is unchanged and is NOT proof of this new source.
No new HLS synthesis starts below the original1500MiB root guard; it is not
weakened. Native1MiB, multi-SGE, real-peer recovery/congestion/interoperability
and original-clock full-board fit/setup/hold/CDC/DRC/routing/short physical
proof remain. Latest actual HLS15.571ns still FAILS original4ns/default1.08ns.
No install/load/program/default/network/fan/BIOS/flash/reboot/Git action.
No job remains live. No reboot needed; restore ALL archived RAM caches and
prove authenticated exact-thread/goal restoration before any necessary
reboot. Progress152 doc preimages: `write-receive-progress152-doc-preimages-aszOVXxc`.

Progress152: the previous goal turn151 and its explicit publication were
PROGRESS (actual fault diagnosis/targeted gate/complete compile, then verified
main/origin/main/remote53eefbf8bbb8b0eb9ca71d9294ac940f0be54011). This turn
adds genuine large incoming execution and matched standard software source;
it does not automatically commit/push or narrow the eleven requirements.

[Fresh corrected native004](../results/2026-10-18/rocev2-rnic-segmented-receive-native-full-004.json)
PASSES ALL34 exact cases: both new8193-byte incoming SEND/Immediate cases and
ALL32 old case names. Fresh compile798.354s; new cases8.534/8.584s and all
cases<=8.584s under original1200s/30s limits/4ns clocks. One actual8194-byte
C128 RQ owner survives three packets, four real full-range MR queries,
scattered-page DMA64/low32 addressing, unique physical command nonces,
three real ordered readback fences, HLS packet processing, genuine board
FIFO/XGMII/FCS/SFD/CDC/MAC receipts/1024-cycle tails and three packet releases.
Only the final whole776 receipt and final actual MAC release allow one full
CQ/retire/host ACK. The real final MAC receipt is withheld1100 cycles so
memory/core/per-packet release alone cannot complete the request. Every
16384 modeled host payload/pad/sentinel byte, coherent RQ input, actual
received8193 vs capacity8194, full620 owner/Immediate/PSN/MSN0/0/1 and ACK
wire bytes match independent oracles. Physical host/root/peer/PHY/PTP remain
models; this is actual generated-RTL native simulation, not real FPGA IO.

Separate `derive_segmented_receive_kernel.py` integrates the typed large
RECV adapter and C128 codec into the actual kernel source cohort. Only exact
RNC65535/CQC255/SQC13/RQC31/profile7 plus original128/748/0xa0 geometry can
bind it. RQC31 cannot be accepted as SQC; mismatched tuples fail before ring
allocation. RECV obtains a full-capacity local-write MR reference, independent
RQ sequence/cookie/ring and full owner; CQ decodes actual received length,
not capacity. Only this profile raises SEND/Immediate receive length to1MiB;
segmented WRITE Immediate is NOT enabled by the notification validator.
All old/default tuples, full MR/PD/key/range/ref/uncertain-producer/CQ-full
retention and IB_ATOMIC_NONE remain unchanged.

[Real-header build001](../results/2026-10-18/rocev2-rnic-segmented-receive-kernel-build-001.json)
PASSES10.842s with full modules/symbols and no compiler warnings, gated by
the exact corrected ALL34 native proof. No install/load occurs.
[Callback002](../results/2026-10-18/rocev2-rnic-segmented-receive-kernel-post-002.json)
PASSES ALL170 actual standard callback C cases (36 new RECV plus ALL134 old).
Maximum runtime0.0153s, ASan/UBSan/original10s per case. New cases cover full
1MiB capacity, offset/high keys, exact independent128 posted bytes, zero,
capacity-vs-actual counts, network-order Immediate, standard bad-WR tail,
read-only/range/key/SGE refusal, stale full owner, CQ pressure and unknown
producer retaining the actual modeled MR reference. Linux primitives/MMIO/
pin/coherent DMA/hardware-completion boundaries are explicit models.

[Failed callback001](../results/2026-10-18/rocev2-rnic-segmented-receive-kernel-post-001.json)
stops at RECV26: the fixture's low-bit epoch mutation turns actual epoch1
into0, testing canonical-form rejection rather than a valid stale owner.
Read-only GDB on the unchanged failed executable confirms epoch1/context0.
Exact public fixture/runner preimages in `receive-kernel-post-001-preimages-8oxDUI04`
remain.002 changes only the mutation to epoch bit63, keeping it nonzero and
distinct and retaining the SAME exact ESTALE assertion, all170 cases and
the unmodified real-header driver cohort. No output normalization, stale
report rewrite, timeout/assertion waiver or manufactured cleanup occurs.

[Actual IO C001](../results/2026-10-18/rocev2-rnic-receive-kernel-identity-001.json)
PASSES2442 identity/geometry/notification conditions in0.0123s:384 SQ/RQ,
2048 CQ and10 receive-bound cases. CSR reads are models; this is not the
full driver or native proof. [Private provider001](../results/2026-10-18/rocev2-rnic-provider-segmented-receive-001.json)
PASSES all8 exact FW identities/all7 old retained, original10s runtime
(maximum0.0175s). Real installed libibverbs/private provider executes standard
MR/RECV/SGE/two-WR-chain/exact second-bad-WR/CQ marshalling through1MiB,
with actual-byte4096/8193/1048575 versus capacity4097/8194/1048576 and
Immediate values0/89abcdef/ffffffff. ONLY fake-fd syscalls/WC replies are
modeled on that path. No real NIC context opened, provider installed or
kernel module loaded; serializer success is not real MR/RQ execution.

[Unedited native/C001](../results/2026-10-18/rocev2-rnic-segmented-receive-kernel-native-cq-001.json)
PASSES90 actual-C cases: ALL16 old operation pairs/four negative mutations
each plus the two new large receive pairs. All128 bytes posted through the
standard C RECV callback match the genuine coherent RQ input and the actual
native33-word CQ snapshot retires its full owner/MR reference once, producing
WC8193, not capacity8194. Snapshots are never rewritten or extended with
invented geometry words; geometry remains an explicit separate CSR model.
All malformed events are labeled in-memory negative copies and retain refs.
Maximum runtime0.0149s/original10s, ASan/UBSan. Linux/MMIO/pins/DMA/teardown
are models in a SEPARATE execution, not live kernel/RTL or physically matched
page tables. [Functional audit001](../results/2026-10-18/rocev2-rnic-segmented-receive-functional-diagnostics-001.json)
verifies8750 current/prior/failed bindings; [native/software audit001](../results/2026-10-18/rocev2-rnic-segmented-receive-native-software-diagnostics-001.json)
verifies2325 further bindings. The original TX-padding provenance gate still
fails; no overall suite-green claim.

All11 remain incomplete. Native1MiB, multi-SGE, segmented WRITE Immediate's
independent remote MR/late notification RQ, live registered Linux/RTL/ref
lifetimes, real-peer recovery/RNR/congestion/interoperability, original-clock
full-board fit/setup/hold/CDC/DRC/routing and short supervised physical work
remain. HLS15.571ns FAILS original4ns/default1.08ns; no waiver. Installed/
default profile6 incoming4096 and oneSGE stay unchanged. No hardware/default/
install/load/network/fan/BIOS/flash/reboot/Git action. No build remains live.
No reboot needed; restore ALL archived RAM caches and prove authenticated
exact-thread/goal revival first. Publication151 doc preimages are retained
in `receive-publication151-doc-preimages-Sdw1PgN9`; this152 work is local.
The following numbered sections preserve their historical observed states.

Publication after progress151 (explicit user request): commit/push the
current source-development checkpoint, including successful and failed
reports. No new long build is started merely to publish this snapshot.
This is not a release or completion of the original eleven requirements;
no further automatic commit/push is authorized by this publication.

[Actual full-native003](../results/2026-10-18/rocev2-rnic-segmented-receive-native-full-003.json)
compiles697.994s with all leaves present, but LARGE_RX_SEND FAILS10.237s
at the unchanged10000-cycle deadline for packet1 (the second/MIDDLE packet).
FIRST genuinely performs4096-byte DMA, its real fence, core/placement and
board ACK-MAC release; MID receives no new MR query/command, and whole CQ
never completes. All original fixture assertions, inputs, clocks and limits
remain; the failure is retained, not relabeled by earlier old32 passes.

[Read-only diagnosis003](../results/2026-10-18/rocev2-rnic-segmented-receive-native-fatal-diagnostics-003.json)
verifies1913 original bindings, relinks only a diagnostic main against the
unchanged archived DUT objects, and stops at the SAME original fatal.
Actual state shows pending=1/group_active=1/offset4096, valid stable trusted
context, no raw reference grant/frame, and a queued second frame. The raw
reference entrance still requires !recv_completion_pending, preventing a
known held group's continuation. Normal checked-ready is already1; neither
that later gate nor the correctly encoded input hex is the root cause.
Diagnostic001's criterion error and002's unsupported GDB nested-array read
are retained with exact script/GDB preimages; diagnostic success is not a
native pass or an assertion/timeout waiver.

`derive_segmented_receive_continuation.py` retains the old complete graph
and changes only the raw reference enable to admit a known pending held
group. QP readiness/pause/MR-idle/config/trusted-context/ref/fault checks
remain; pending is never cleared, and no owner/MR/HLS/MAC/CQ authority is
fabricated. [Gate001](../results/2026-10-18/rocev2-rnic-receive-continuation-gate-001.json)
passes nine current reference-RTL cases, plus the SAME continuation oracle
rejecting the old expression as expected. Metadata/checker are modeled;
this unit result is not full payload/native proof.

[Complete native elaboration002](../results/2026-10-18/rocev2-rnic-segmented-receive-native-elaboration-002.json)
PASSES4.865s with the corrected entrance and actual source007 generated HLS,
no missing-leaf/width waiver, all shared-MR/PTE/domain/whole-join/profile
checks and both global drains0 retained. The separate corrected full runner
preserves ALL34 cases, the original8193-byte/8194-capacity fixture and all
data/MR/PTE/nonce/fence/MAC/owner/CQ oracles; it has NOT been launched.
No build remains live at this publication. New incoming full-native runtime,
matched registered driver/provider, multiSGE/WRITE Immediate/recovery/interop,
original-clock board timing and short supervised physical work remain open.
HLS15.571ns still FAILS original4ns/default1.08ns. No hardware/install/load/
default/network/fan/BIOS/flash/reboot action. Earlier numbered entries below
retain the state observed at their checkpoint, not the publication's state.

Progress150: previous149 was PROGRESS (actual007 HLS/full native compile,
real PCIe-to-MR-to-RQ descriptor execution). [Fresh new-core native compatibility001](../results/2026-10-18/rocev2-rnic-segmented-receive-native-compat-001.json)
now PASSES ALL32 exact old case names, compile642.135s, runtimes4.476..6.831s
under original1200s/30s gates. Actual new HLS, MR/PTE/scattered DMA/physical
nonce/status/fences/board FIFO/FCS/SFD/CDC/MAC/CQ and all full-data/sentinel/
owner oracles execute. This is OLD-function regression, not new large RX.
Original source004 [HLS001](../results/2026-10-18/rocev2-rnic-segmented-receive-generated-hls-001.json)
actually times out at the original7200s limit09:45:40Z; final report remains
FAILED. Its original children2872461/2872554 subsequently naturally vanish
from `/proc`; no manual signals or restart occur. New007's actual generation
success is not substituted for failed004, whose frozen inputs/raw output stay.

New `segmented_receive_payload_native_fixture.py` adds actual incoming8193
SEND/SEND_IMM on one8194-byte C128 coherent RQ owner: exact FIRST/MID/LAST
PSN/MSN/notification, actual full-capacity post query plus three independent
saved-VA/key per-packet MR queries, three actual PTE/DMA/nonce/status/readback
fences, three packet ACK-MAC/tail releases, one real whole776 HLS output,
one whole CQ/retire and exact host ACK. Actual data/capacity differ by1;
all16384 modeled host bytes and padding/sentinels and complete CQ AXI owner
are independent oracles. Two early packet releases must retain the SAME RQ;
the final actual MAC receipt is withheld1100 cycles and must prevent CQ.
The actual three scattered pages include DMA64 and low-DMA32 headers; all
old PCIe format/address/byte-enable/TC/attribute/nonce/status/200-cycle fence/
64-cycle TX-ACK guards remain. No internal owner/MR/status/core/MAC receipt/
retirement/drain is driven. Physical host/root/peer/PHY/PTP remain models.

New `probe_segmented_receive_native_full.py` preserves ALL32 exact old cases
and adds the two incoming cases (34 total), all required, original1200s
build/30s runtime and4ns clocks. [Failed001](../results/2026-10-18/rocev2-rnic-segmented-receive-native-full-001.json)
is a strict fixture-anchor mismatch (existing service MAC predicate also
follows the RQ predicate); exact preimageJoDWgkOc retained. The corrected
anchor preserves both predicates and adds only final new-RX withholding.
[Failed002](../results/2026-10-18/rocev2-rnic-segmented-receive-native-full-002.json)
is actual Icarus observer binding to nonexistent`dut.cq_commit_ready`;
exact preimagenxQgKska retained. It observes actual`s_cq_commit_ready` now;
no completion is injected and no assertion/clock/timeout is relaxed.
Fresh003 passes full actual bench elaboration (empty diagnostic log, no
missing-leaf or width waiver) and is LIVE in Verilator build62988, run
`segmented-receive-native-full-7t4ynzje`, objects
`/dev/shm/as02-segmented-receive-native-full-obj-p6iwsj9s` at10:04:13Z.
No new8193 receive pass, native1MiB operation, matched software or physical
timing proof is inferred from merely building it.

[Native regression audit001](../results/2026-10-18/rocev2-rnic-segmented-receive-native-regressions-diagnostics-001.json)
verifies6408 current/prior/failed bindings and exact preimages. The unchanged
source gate still stops on historical TX-padding SHA mismatch; no overall
suite green. All11 requirements remain, especially actual new large RX,
registered driver/provider/profile/ref lifetimes, segmented WRITE Immediate
independent remote MR/late notification RQ, multiSGE, real-peer/nonterminal
MSN/recovery/RNR/congestion and original full-board fit/timing/CDC/DRC/routing/
short supervised physical work. Current HLS estimate15.571ns still FAILS
original4ns/default1.08ns. No hardware/default/install/load/network/fan/BIOS/
flash/reboot or Git action. No reboot needed; authenticated same-thread/goal
revival unproved and ALL archived RAM caches must be restored first.

Progress149: previous explicit publication148 was PROGRESS: main/origin/main
and independent remote main were verified at9de05e83febfc48ec220a75d00a34dea8594b9c7.
No new commit/push is made or authorized automatically in this goal turn.
[Actual generation002](../results/2026-10-18/rocev2-rnic-segmented-receive-generated-hls-002.json)
PASSES399.510s from frozen source007, all44 C++/old compatibility and original
1500MiB/4ns/default1.08ns/8QP/2000 gates retained. Real whole output776 and
all inherited generated ports checked. Resources101682LUT/128313FF/245BRAM18K/
0DSP; estimated15.571ns FAILS the original4ns/effective2.92ns target. This is
actual RTL generation, not full-board placement/timing or physical success.
Original source004's SAME live scheduling job74092/PID2872554 is not killed
or restarted; at09:40:49Z elapsed01:55:07/CPU01:51:48, original7200s limit.

[Complete native elaboration001](../results/2026-10-18/rocev2-rnic-segmented-receive-native-elaboration-001.json)
PASSES4.750s with actual new generated HLS, no `-i`, no stub/missing leaves,
all11 complete-profile switches, one MR/table/sharedPSN-MSN domain/new whole
join/messageRQ and original legacy core retained. All inherited source,
component, port-width, module-count and both-global-drains0 gates remain.
`segmented_receive_native_sources.py` replaces exactly15 reviewed bodies,
adds one actual messageRQ and removes the old active Immediate HLS cohort.
This is actual application-native compile ONLY, not new payload execution.

[Actual C128/PCIe/MR/RQ001](../results/2026-10-18/rocev2-rnic-receive-pcie-post-001.json)
ALL4 PASS, maximum0.367s/original10s runtime. Actual Corundum client/backend/
RAM/mux/genericPCIe and actual new fetch/admission/MR/messageRQ execute:
15 coherent128-byte records,10 real full-capacity local-write MR queries,
7 actual posted owners. Full620 identities are independently reconstructed,
same-QPN SQ/RQ banks stay separate, posted/held RQ prevents real MR revoke,
and read-only/range/stale-generation/sequence/epoch/reserved/remote-field/
PCIeUR denials cannot post authority. Real failed-PCIe parent-drain waiting
and halted queue are checked. No HLS/MAC/CQ proof or retire is invented;
all descriptors/rings remain byte-identical. Physical host/root/link and
privileged configuration/error sink are models. No payload PTE/DMA/native
completion, installed Linux or physical proof is inferred from this test.

Fresh `probe_segmented_receive_native_compat.py` is now building the SAME new
generated-HLS graph for ALL32 old cases, with original1200s build/30s runtime,
4ns clocks, physical-nonce/status/fence/boardMAC/CQ/full-byte/sentinel checks.
Only expected exact RNC65535/RQC31/CQC255 identities change. Build79723 in
`segmented-receive-native-compat-gpxp6d5c`, RAM objects
`/dev/shm/as02-segmented-receive-native-obj-cfqqqck0`, is authoritatively live
in Verilator/C++ compilation at09:40:49Z. No old32 pass or new large RX native
runtime is claimed yet. [Generated audit001](../results/2026-10-18/rocev2-rnic-segmented-receive-generated-diagnostics-001.json)
checks4672 fresh/3661 historical bindings with exact preimages, retaining
rejected005/compile-failed006 and the unchanged failing historical padding
source gate. Existing whole component, C/API and old evidence remain.

One explicit terminal zero-request HLS scratch DB (1482 files) was losslessly
archived, compared against original/RAM manifests and relocated to RAM after
two exact-target process/cwd/FD/maps audits; unrelated source004 job untouched.
Persistent archive and manifest remain. Restore this AND ALL earlier cache
archives before ANY reboot. No reboot needed; exact authenticated thread/
active-goal revival still unproved. All11 original requirements remain,
including new native large RX, matched actual driver/provider lifetimes,
segmented WRITE Immediate, multi-SGE, real-peer MSN/recovery/RNR/congestion,
original full-board clocks/fit/CDC/DRC/routing and short physical work. No
program/install/load/default/network/fan/BIOS/flash/reboot or new Git action.

Publication checkpoint (2026-10-21, after progress147): the user explicitly
requested commit/push of progress145..147, including successful and failed
public reports. This is a source-development checkpoint, not a release or
completion of the original eleven requirements. No further automatic push
is authorized by this checkpoint.

Progress147 adds full posted-RECV capacity through 1 MiB to a separate
128-byte C codec and a correctly typed standard `ib_recv_wr` adapter.
[Codec001](../results/2026-10-18/rocev2-rnic-segmented-receive-wqe-001.json)
passes 37 methods (all 26 old plus six prior Immediate methods retained),
including independent complete-byte oracles, full-64-bit inclusive ranges,
reserved fields, canonical zero and null/alias failure clearing.
[Admission001](../results/2026-10-18/rocev2-rnic-segmented-receive-admission-001.json)
passes 78 actual MR/admission and TX-SQ staging cases across 31 methods,
retaining all 25 old methods. The real MR query covers the full posted
capacity/key/VA/local-write permission; RECV never becomes a TX SEND.
[MR-to-RQ001](../results/2026-10-18/rocev2-rnic-receive-mr-post-001.json)
passes four real MR-to-message-RQ handoff/denial cases, preserving the full
620-bit admitted owner and blocking MR modification while the RQ owns it.
Record fetch, privileged configuration and error consumers are models;
this is not PCIe DMA, HLS payload, MAC/CQ retirement or physical proof.
[Adapter001](../results/2026-10-18/rocev2-rnic-segmented-receive-verbs-adapter-001.json)
builds against real kernel headers and executes ASan/UBSan base-only RECV
and all inherited adapter assertions. It does not register/post a callback,
pin an MR, install/load a driver or advertise a new provider profile.

Separate balanced KEEP-prefix candidate007 preserves the extent consumer's
short nonterminal beats and split-padding checks. [Conformance003](../results/2026-10-18/rocev2-rnic-receive-extent-conformance-003.json)
passes 103,665 finite comparisons of actual old/new accept/reject and
copied-byte side effects, not a formal equivalence or timing proof.
[C++007](../results/2026-10-18/rocev2-rnic-segmented-receive-hls-007.json)
passes all 44 modes (all 21 old retained); new SEND/Immediate receive modes
take 4.646/4.690 seconds, each six messages/284 packets through 1 MiB.
[Compatibility003](../results/2026-10-18/rocev2-rnic-segmented-receive-compat-003.json)
passes unchanged actual Atomic RTL service and Immediate TX/RX.
Candidate005's normal 44-mode pass is NOT semantic equivalence: its
conformance001 fails on a legal short nonfinal beat, so it is rejected.
Candidate006's AP ternary compile failures and exact generator preimage
remain. Candidate007 fixes the explicit AP cast only; old assertions,
timeouts, clocks and frozen sources were not changed. Neither005 nor007
has a new HLS synthesis result. The original source004 job remained live
at 2026-10-21T09:16:25Z (PID2872554, CPU01:27:24), still scheduling with
timing/II warnings. It is not restarted or waited out for publication.

[Publication audit](../results/2026-10-18/rocev2-rnic-segmented-receive-publication-diagnostics-001.json)
records exact report/source/artifact checks, named historical preimages and
the inherited failing source gate. Generated/vendor outputs, private cache
archives and local progress checkpoints remain excluded from Git. Existing
native/software profile6 RQ4096, one SGE and `IB_ATOMIC_NONE` are unchanged.
Actual new generated-HLS full-native integration, matched software/profile,
segmented WRITE Immediate, multi-SGE, recovery/real-peer MSN policy and
original full-board/physical gates remain open. No hardware, installation,
module, network, fan, BIOS, flash or reboot change accompanies this push.

Progress146: previous145 was PROGRESS (actual large incoming SEND/Immediate
C++44 modes and separate whole-receive consumer18 cases). The SAME HLS
generation job74092 remains authoritatively LIVE, CPU active in scheduling;
not restarted, no generated-HLS/timing/native qualification inferred.
New `rocev2_receive_message_queue.v` retains one full620 posted RQ through
all packet DMA/HLS/ACK-MAC leases and one whole CQ commit/retire. Packet
release is independent and cannot pop/unpin the RQ. [Four-state RQ003](../results/2026-10-18/rocev2-rnic-receive-message-queue-003.json)
ALL48 PASS (zero/small/exact-multiple/8193/1MiB metadata, PSN/MSN wrap,
full identity/sequence/epoch/PD/key/range/padding/unknown/stale proof checks,
held packet/ticket backpressure). Maximum case0.161s, original10s bounds.
ALL placement/MR/backend/HLS/whole/MAC certificate producers are MODELS in
that unit; it is not a native payload transfer.
[RQ+actual ACK001](../results/2026-10-18/rocev2-rnic-receive-message-ack-001.json)
PASSES0.138s: one8193-byte owner/capacity1MiB,3 actual header/proof/tag/EOF/
receipt/1024-tail ACK lifetimes,3 per-packet releases,one whole CQ TICKET.
Timestamp-without-EOF, EOF-without-receipt and receipt/bridge stalls block
progress. [RQ+ACK+actual CQC001](../results/2026-10-18/rocev2-rnic-receive-message-cq-001.json)
PASSES0.167s: actual publisher commit/retire,one visible event, complete24
AXI context words independently checked, bytes8193 distinct from capacity
1MiB, wire Immediate unchanged. RQ guard hands off to actual CQ guard until
the exact modeled host ACK; CQ is no longer a manual success source in this
additional test. HLS/MR/backend/PHY pins/upstream frame/host AXI are still
models. These tests do not prove live generated HLS/MR/PCIe/native coupling.
New `fpga/derive_segmented_receive.py` coordinates40 bodies/15 changed
leaves: full saved native offset and same-MR authority, packet vs whole
retire fanouts, genuine whole776-bit HLS port/backpressure, new private
65535/255/13/31 source identity, posted capacity<=1MiB and one whole CQ.
[Syntax002](../results/2026-10-18/rocev2-rnic-receive-message-graph-syntax-002.json)
selects all11 complete-profile parameters, but uses Icarus `-i`: missing
HLS/vendor leaves are ignored. It is explicitly NOT full elaboration or
runtime. Earlier default-parameter Syntax001 remains historical/subset-only.
No matched codec/kernel/provider or live capability is advertised. Current
native/software profile6 and its4096-byte incoming RQ are unchanged.
[Component audit001](../results/2026-10-18/rocev2-rnic-receive-message-native-components-diagnostics-001.json)
rechecks328 fresh/165 historical bindings. Failed reserved-Verilog-name and
fixture delta-settling assertions/preimages remain; only fixture names and
post-VALID combinational settling changed, no functional checks removed.
All11 requirements and original clock/fit/CDC/DRC/routing/physical gates
remain. Next finish the SAME live HLS job, verify actual new ports, then
actual protected shared MR/PTE/backend/nonces/status/fences/native large RX
and every old regression, followed by matched software source. WRITE IMM's
independent remote MR/late notification RQ, multi-SGE and recovery/real peer
MSN policy remain. No install/load/program/network/fan/BIOS/flash/reboot/Git.

Progress145: previous explicit publication144 was PROGRESS, remote/main
verified at45dc8a2. New separate `rocev2_native_segmented_receive_top` adds
owned segmented SEND/SEND_WITH_IMMEDIATE RX<=1MiB in the SAME full duplex
READ/WRITE/SEND/Immediate/Atomic source. [Actual C++004](../results/2026-10-18/rocev2-rnic-segmented-receive-hls-004.json)
ALL44 modes PASS, ALL21 prior modes retained. Each new operation6 messages/
284 packets (4097/8192/8193/12289/65537/1MiB), runtime4.672/4.738s; compile
70.354s. Full620 posted identity is unchanged across fragments, actual bytes
accumulate independently of capacity, exact offset/PSN/pad/opcode/sequence/
epoch/PD/key/range checks precede raw commands. Actual data EOF, ACK/MSN and
SAME PSN readback remain required. Packet752 and whole-message772-bit
receipts are distinct; neither grants DMA authority or native CQ retirement.
MSN advances only on LAST; parsed BTH padding now survives both actual RX
forwarding paths. Independent full-data/ACK/whole-byte oracles and21 new
negative cases retain original30s limits. [Compatibility001](../results/2026-10-18/rocev2-rnic-segmented-receive-compat-001.json)
PASSES unchanged actual Atomic RTL service/Immediate TX/RX (compile25.090s,
runtime0.978s). [Whole-message unit003](../results/2026-10-18/rocev2-rnic-receive-message-join-003.json)
ALL18 PASS, two interleaved QPs/PSN+MSN wrap/small WRITE notification/zero;
packet-proof producers on this UNIT boundary are models, not substitutes
for the actual44-mode receive execution. Its maximum case0.005s.
Fresh HLS generation is RUNNING from exact source004/frozen inputs with the
original1500MiB guard/4ns/default1.08ns/8QP/2000-entry gates; timing warnings
are present. No generated RTL/runtime/timing success is claimed yet. Initial
header selection, missing prototypes/scope/fixture imports and lost padding
failures remain in separate reports with exact preimages; no check relaxed.
The current native/software profile6 STILL receives<=4096 and is unchanged.
Large native RX requires genuine same RQ/MR/PTE/DMA/status/fence ownership,
per-packet actual ACK-MAC release and one whole CQ/retire, not limit changes.
Segmented WRITE_WITH_IMMEDIATE must retain remote MR separately and acquire
its notification RQ at the appropriate packet; not faked as a SEND buffer.
Real peer/nonterminal ACK-MSN policy/recovery/RNR/congestion, multi-SGE,
live Linux/device and original full-board physical/timing gates remain open.
All11 requirements retained. Three terminal scratch DBs were losslessly
archived/hashed and relocated to RAM; restore them before ANY reboot. No
reboot needed or performed, authenticated exact thread/goal restoration is
still unproved. No program/install/load/network/fan/BIOS/flash or new Git
action. Next verify the live HLS job, then wire actual native large receive.
[Consumer audit](../results/2026-10-18/rocev2-rnic-segmented-receive-consumer-diagnostics-001.json)
rechecks948 fresh/1475 historical bindings and records the live generation
observation separately; it is not a generated-HLS or native-runtime result.

Protocol behavior was cross-checked against the primary
[Linux v6.17 RXE responder](https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/infiniband/sw/rxe/rxe_resp.c):
SEND/WRITE MSN advancement is at message end, and SEND completion byte count
is actual consumed data, not posted capacity. No Linux source was copied.

Publication checkpoint (2026-10-21, after progress143): the user explicitly
requested this commit/push of progress142..143 source, documentation and
public success/failure reports. Rechecked all241 checkpoint source hashes,
56 report hashes and2586 current native/software evidence bindings; syntax
checks passed for23 new Python sources and25 JSON reports. The original
`scripts/check.sh` still FAILS at the historical transport-RX record versus
`rdma/rtl/rocev2_tx_padding.v` SHA mismatch; neither record nor gate is
changed. The13.885ns HLS estimate still fails the original4ns target; no
physical or live Linux/RTL qualification is claimed. This publication is
PROGRESS, not completion of the11 requirements. No hardware changes, new
long builds, reboot or authorization for future automatic pushes.

Progress143: previous142 was PROGRESS (actual large-Immediate C++/HLS and
full-native wiring/components). Now genuine native Immediate001 PASSES ALL32
cases, including new8193-byte SEND/WRITE Immediate and ALL30 old cases. Fresh
compile633.005s; cases4.125..6.430s, new6.229/6.429s, unchanged1200s/30s.
Actual coherent SQ/full-range MR/PTE/generated HLS/protected RX/MSN/source
child DMA/shared physical nonce-status/wire/replay/board FIFO-FCS-SFD-CDC-MAC/
whole CQ complete. Each new op3 fragments,3 statuses/nonce translations/MAC
frames,2 advances,one whole receipt/CQ,6 paged read descriptors/68 read TLPs,
no data writes/fences. Full independent packet/128-record/748-owner and
16384 source/sentinel-byte checks retain final actual MAC receipt withholding.
Old small SEND_IMM now uses actual retained source and actual board MAC;
ordinary READ still has its explicit old MAC-pin model. Physical host/root/
peer/PHY/PTP MODELS, native1MiB not tested. No output normalization or old
binary treated as new source proof. All1862 native bindings match.
Separate exact32767/127/SQC13/RQC15/stride128 software profile6 implements new
WR adapter/SQ encode-decode-replay/CQ/full MR/PD/range/ref/failure lifetimes;
all old/default/profile5 selectors stay. Full real-header modules PASS10.242s;
adapter real-header5.138s/ASan-UBSan0.012s,48 new large/22 compatibility/22
negative, every old assertion kept. Actual standard C callbacks ALL134 PASS
(44 new/all90 old), compile7.723s/max0.015s. Unedited native SQ/CQ integration
ALL80 PASS (all14 old+two new pairs/four mutations each), compile6.969s/max
0.015s; every128 posted byte and actual C MR/CQ ACK release match. Actual
libibverbs/private provider ALL7 FW identities PASS (all6 old), max0.018s,
4097/8193/1MiB Immediate chains/full values/keys/SGEs/exact second bad-WR;
fake-fd/WC replies modeled. Total2586 new successful/103 historical and1665
old native bindings audited. Failed strict fixture CQ-count startup and
post-header-build nested-main/indentation fixture compile remain with exact
preimages. Only require all four independently expected CQ ABI reads and
rename the frozen prior test main/split counter statement; no assertion,
sanitizer,-Werror,clock,drain or timeout relaxed. No actual live Linux/RTL/
provider/device/pins/page-table coupling; no install/load/program/hardware/
network/fans/BIOS/flash/reboot/Git. RQ4096/single SGE/Atomic_NONE unchanged.
HLS13.885ns fails original4ns/default1.08ns/full-board gates; all11 original
requirements remain. Next coarse features: large inbound receive/Immediate,
multi-SGE, then missing live API/recovery/congestion/interop/physical/timing.
[Audit](../results/2026-10-18/rocev2-rnic-segmented-immediate-native-software-diagnostics-001.json).

Progress142 (historical): previous explicit publication141 was PROGRESS (remote/main
verified at e22ff35; no future automatic push). Add new coarse feature,
segmented SEND/WRITE Immediate<=1MiB, separate exact RNC32767/CQC127 source.
Same748-bit owner, real FIRST/MIDDLE/LAST replay/ACK/pointer/pool/timer/PSN
consumers, Immediate only on LAST, one whole-WR receipt. Actual HLS C++ ALL21
old/new modes PASS (all11 old),6 WRs/284 packets/13 stored replays per new op,
max5.469s; every original30s bound retained. Compatibility real Atomic RTL
service and Immediate TX/RX PASS. New actual HLS generation PASS374.863s,
81375 LUT/99264 FF/209 BRAM18K/0 DSP, estimate13.885ns still FAILS original
4ns/default1.08ns/8QP/2000. Complete-native elaboration PASS3.510s,14 explicit
leaves and new exact HLS selection, strict ports/counts/shared domains/drains.
Actual C/UBSan26 methods (all20 old); wire8 methods/17 cases max29.423s;
source10/19 with unchanged bounded child; real MR/HLS-SQ25/61; exact register/
CQ27 cases/20 complete publications; padding/ICRC9 methods max19.586s PASS.
4513 current and648 historical bindings verified, exact failure preimages
preserved. Initial codec macro/helper, source report-container, MR permission
oracle and strict startup-anchor failures remain separate, never relabeled.
The MR correction uses an independently stale-generation key and adds a
positive read-only source case, retaining READ local-write checks. No gate,
assertion, sanitizer, timing or timeout relaxed. All HLS/RX/ACK/backend/CQ/
MAC-pin/control models and separate HLS-C++/ICRC snapshots remain explicit.
Actual native Immediate payload/DMA/common-nonce/MAC/CQ runtime, matching
kernel/provider and Linux/physical/original full-board timing remain open.
RQ4096/single SGE/old/default/profile5/IB_ATOMIC_NONE unchanged. All11 original
requirements retained. Two inactive HLS scratch DBs losslessly relocated to
RAM with persistent archives/hash manifests, local-only administration audit;
restore before reboot, exact authenticated thread/goal restoration unproved.
No reboot needed or performed, no hardware/default/module/network/fan/BIOS/
flash/Git change. Next: genuine native Immediate with all30 existing cases,
then exact new software source/lifetimes; large RX/multi-SGE/recovery remain.
[Audit](../results/2026-10-18/rocev2-rnic-segmented-immediate-diagnostics-001.json).

Publication checkpoint (2026-10-21): the user explicitly requested another
current-progress commit/push. This publishes progress136..140 source and
public success/failure reports, including native8193-byte READ/all29 old
cases and matched profile5 kernel/provider source. It does not authorize
future automatic pushes or imply installed Linux, physical hardware, native
1MiB READ, original timing qualification or completion of the overall goal.
Publication checks reparse new Python/JSON, verify the new native/software
evidence against local hashes and run `git diff --check`. `scripts/check.sh`
still fails at the historical transport-RX/TX-padding SHA mismatch; the
original record/check remain unchanged. No new hardware tests or long builds
are required for this publication.

Progress140 (historical): new explicit matched READ software profile5 source implemented,
not merely serialization. Exact16383/63/SQC13/RQC15/128-byte geometry/mixed-
tuple refusal; old0/1/3/4/default paths remain. Actual new Linux READ WR adapter
selects full-range codec only for READ>4096, delegates every old operation;
SQ expected-record/replay/CQ validates with that codec only under new profile.
Full MR/PD/range/local-write/ref/ring/CQ/failure-lifetime checks retained.
Private running-header kernel build001 PASS9.989s, WR-adapter build4.482s and
ASan/UBSan0.012s (all54 positive14 negative old;24 new large READ,15 other
positive,14 negative). Standard callback C post003 ALL90 PASS (25 new/all65
old), max0.015s; snapshot integration001 ALL70 PASS (14 untouched native pairs,
four labeled bad-copy mutations each), max0.016s. All128 kernel/native posted
bytes and actual C CQ/MR retirement match. Real installed libibverbs/private
provider ALL6 FW identities PASS (all5 old), READ+SEND4097/8193/1MiB, exact
bad-WR/keys/SGE/READ WC lengths; fake-fd/WC only modeled, max0.018s.
626 fresh successful bindings verified (133/95/175/38/185), plus84/90 historical
failures and unchanged1665 native139 bindings. Startup helper-import error
zero compiled cases, modeled indentation -Werror failure and wrong allocated-
SQ-count oracle remain with exact preimages. Corrections only restore helper
API/add model braces/independently require allocated SQ1+producer0+MR ref1;
no kernel gates, ASan/UBSan/-Werror/10s limits or old assertions weakened.
Actual Linux/MMIO/pins/DMA/completion/page tables remain boundary models or
separate native snapshots; no live Linux/RTL/provider/device execution, install,
load, hardware/fans/BIOS/network/flash/reboot/Git. Source profile5 permits1MiB
READ/WRITE/SEND, one SGE and Immediate/RQ4096; native READ tested8193 only.
Large receive/Immediate, multi-SGE/recovery/physical/original timing remain,
HLS13.885ns>4ns/default1.08ns/all11 scope retained.
[Audit](../results/2026-10-18/rocev2-rnic-segmented-read-software-diagnostics-001.json).

Progress139 (historical): fresh command-queue full-native001 PASSES ALL30 cases with exact
actual generated READ HLS and original independent oracles. New8193 READ and
ALL29 previous cases pass. Compile623.025s; cases4.175..6.279s/READ6.078s,
original1200s compile/30s runtime,4ns/default1.08ns clock conditions unchanged.
Actual coherent SQ/MR/PTE/protected RX/MSN/HLS/paged DMA/common nonce/3 genuine
statuses/3 host fences/board MAC-FCS-SFD-CDC/whole-owner CQ complete. READ3 RX,
one token/receipt/aggregate event/CQ,4read/67write TLPs/8193 visible bytes and
wrapped PSNsfffffe->000001. All16384 host bytes/sentinels and independent full
READ owner/ABI63 CQ reverified from preserved C128/capture. All1665 source/
artifact/RAM bindings match (1449/214/2), frozen binary/models/logs retained.
The report uses overall pass_test/source_unchanged plus each exit0 and strict
per-case oracle outputs; a universal per-case pass_test field is not part of
its schema. Physical host/root/peer/PHY/PTP remain
MODELS; older ordinary READ/Immediate MAC-pin models remain explicitly scoped.
Native1MiB READ, actual Linux/provider/API/physical and original full-board
timing are NOT proved. HLS13.885ns still fails4ns/default1.08ns; source16383/63
admits1MiB but old/default/kernel/provider8191/31 stays READ4096. Next coarse
feature: separate exact16383/63 software profile (new explicit profile5) with
actual Linux WR adapter, SQ encode/decode/replay/CQ/full-MR lifetimes and
provider FW binding, retaining every old profile/default. All11 original
requirements remain, no hardware/default/fan/BIOS/module/network/flash/reboot/
Git changes. [Audit](../results/2026-10-18/rocev2-rnic-segmented-read-command-queue-native-diagnostics-001.json).

Progress138 (historical): original -O1 native002 compile PASSES620.672s; actual READ fails
original cycle deadline in9.436s, distinguishing functional wait from CPU
slowness. Actual first4096-byte fragment/status/fence completes. Second child
waits for2176 bytes, data_ready1/data_valid0, future raw command valid/ready0,
stable18000..28000cycles;3 RX,2 commands,1 status/fence,0 aggregate events.
All1510 bindings and exact authoring preimages/model/binary/log preserved.
New separate derive_segmented_read_command_queue.py changes ONLY READ mux:
two exact owner-derived future commands may queue after genuine placement,
while original serial child DMA/status/fences and whole-owner/CQ joins remain.
Queue must drain at CQ; no RAW address becomes DMA authority. New component
001 PASSES12 methods/23 cases, retaining all17 prior mux cases; coupled8193
producer/data and full-queue16385 plus four malformed/unknown refusals. Actual
child/unpad/mux/common nonce, modeled HLS/placement/backend status/fence/CQ.
372 bindings verified, maximum case0.342s/original10s bounds. Derivation startup
anchor failure/preimages retain zero compiled/runtime cases. Complete native
elaboration001 PASS3.418s/1422 bindings/same45 kinds/domains;37 common RTL files
identical, only mux differs, all23 unit mux bodies equal actual native bytes.
Fresh actual HLS/native build live session99689, original30 cases/independent
oracles/1200s compile/30s runtime. Actual generated-HLS deadlock resolution/
full READ/CQ still unverified. All11 scope/timing/default/hardware/Git safety
retained; original13.885ns still fails4ns/default1.08ns, no reboot needed.
[Audit](../results/2026-10-18/rocev2-rnic-segmented-read-command-queue-diagnostics-001.json).

Progress137 (historical): corrected QP observer now passes the previously failing genuine
native QP_TX setup and reaches actual coherent SQ fetch/READ wire emission/
first4096-byte paged-write/fence descriptors. Full-native001 compiles433.696s,
then TIMES OUT at original30s bound: no completed case/old29 not attempted.
All1508 source/artifact/RAM bindings and exact preimages verified/preserved.
Separate exact-binary/identical-input30s line-buffered diagnostic reaches24000
cycles,33 write TLPs, first3+4093-byte writes and one-byte fence read; no fault
or second physical write descriptor observed. This does NOT prove completion
or distinguish simulator cost from a functional stall. All47 diagnostic
bindings verified, original failed input/model/binary/log/report unchanged.
New -O1 host C++ simulation build and read-only child/unpad/status/nonce/
backend progress snapshots keep RTL/FPGA clocks/oracles/1200s build/30s runtime
and all30 cases. First optimized attempt FAILS Icarus elaboration on seven
monitor paths missing actual native_endpoint.datapath; all1499 bindings and
exact preimage preserved before adding only that hierarchy segment. Fresh002
build is live, session56210, directory segmented-read-route-o1-native-full-xkdqr376.
No old binary is new-source proof; all native large READ/CQ/API/physical goals
still incomplete. Original timing13.885ns fails4ns/default1.08ns; defaults/
hardware/modules/network/fans/BIOS/flash/reboot/Git unchanged. All11 retained.
[Audit](../results/2026-10-18/rocev2-rnic-segmented-read-route-native-diagnostics-002.json).

Progress136 (historical): actual-controller reproduction isolates QP_TX route erasure.
The real controller REQUIRES empty peer/IP/RX_PSN fields on accepted PSN-only
updates. Old observer writes those zeros into the effective route; actual MSN
predictor latches0xa2. New separate checked derivation changes ONLY two lines
of controlled-responder observation: normal accepted config updates route,
TX-only config leaves existing route untouched while actual TX_PSN still
applies. Controller, predictor, identity/range/guards/HLS and defaults unchanged.
Component003 PASSES6 cases (one exact old-fault reproduction, five corrected),
all<0.027s: genuine command refusal before QP, wrong QPN/PD,12 forbidden-field
mutations, accepted/stalled updates, normal reapply/reset. No SQC identity or
WR is provided; decoded commands/QP apply/quiescence/drain are explicit models.
First fixture001's missing loop integer and002's original slot0-only reply
oracle fail separately. Exact preimages/all130/132 historical bindings kept;
corrections only declare mutation_index and independently require slot1 for
the deliberate slot1 mutation, retaining exact slot equality/all reply checks.
Fresh003140 bindings and complete-native0011419 bindings verified;37 common
RTL files equal failed native002, only the two observer lines differ. Original
failed native0021503 bindings and model/log preimages are unchanged.
Full corrected native fresh build is live (session4838), original1200s build/
30s runtime/all30 cases/oracles retained. Only extra read-only subfault prints
precede the original fatal assertion. No new payload/DMA/CQ runtime pass yet;
all11 requirements remain, original timing13.885ns>4ns/default1.08ns fails.
No hardware/default/module/network/fan/BIOS/program/flash/reboot/Git changes.

Publication checkpoint135 (2026-10-21, historical): user explicitly requested a current
progress commit/push. Include132..134 source/component work plus the NEW
30-case native runner and failed full-runtime evidence, without claiming a
completed feature or all-suite pass. The8193-byte READ fixture uses the actual
C128 SQ record, connected MR/PTE/MSN/HLS/DMA/nonce/lifetime/MAC/CQ graph;
physical host/root/peer/PHY/PTP remain models. Expected payload, page-fragment/
fence descriptors, wrapped PSNs and whole-owner/CQ checks are independent
test expectations, NOT observed successful transfers.

Fixture startup001 and full-native001's wrong observation hierarchy are kept
as separate failed reports/preimages. The observation-only correction changes
no production RTL or assertion. Fresh full-native002 passes Icarus elaboration
and actual Verilator/C++ compilation436.743s. Its first LARGE_READ runtime
FAILS after16.398s during QP setup, before SQ fetch/READ data, with
`main native RNIC fault 00`. The remaining29 cases were NOT attempted in this
batch. Root cause remains unconfirmed; configuration-route observation is a
candidate for diagnosis, not a proved fix. All1437 source/64 artifact/2 RAM
bindings are reverified unchanged, including the failed binary and bench;
[audit002](../results/2026-10-18/rocev2-rnic-segmented-read-native-diagnostics-002.json)
preserves the terminal failure excerpt. Original1200s build/30s runtime bounds
and all clocks/drains/timing gates remain. New large READ native execution,
matched kernel/provider/API/physical qualification and original timing gates
are still open. Source syntax/JSON parsing and diff whitespace checks pass;
`bash scripts/check.sh` still FAILS the historical TX-padding SHA check, not
waived or rewritten. No hardware/default/module/network/fan/BIOS/program/
flash/reboot changes; this user-authorized publication does not authorize
future automatic pushes. All11 original requirements remain in scope; the
overall goal is not complete.

Progress134 (historical): NEW explicit private READ-capable RNC16383/CQC63 profile opens
actual READ<=1MiB admission/HLS-SQ/CQ length gates on the connected133 graph.
Only four leaves change; original8191/31/kernel/provider/default keep READ4KiB.
New wqe_segmented_read.c/.h are serialization-only, not a post/MR authority or
installed driver/provider selection. C/UBSan codec20 methods PASS with all15
old codec methods unchanged. Actual full-range MR/SQ admission11 methods/
26 cases PASS, retaining all8 prior Atomic methods. Actual748-owner/408-SQ
staging8 methods/21 cases PASS, retaining all5 old; real RNC/CQ27 cases PASS,
including12 genuine publications/ACKs and original dependency/owner refusals.
Two fixture import failures (method indentation/literal multiline text) have
separate startup records and exact preimages, zero compiled/runtime cases;
the exact inherited method is compiled inside a temporary Python class, only
codec entry point changed. Profile001's absent negative-fixture ABI-anchor
failure preserves133 bindings/preimage; original reject fixture reused intact,
positive case still explicitly checks63/12 publications. Fresh002 all27 PASS.
Complete READ-profile native001 PASS3.448s/1415 bindings, original one shared
HLS/PSN/MSN/RX/Atomic/MR/PTE/nonce graph and both global drains0. All52 actual
MR admission leaf copies/21 HLS-SQ/2 RNC-CQ bodies equal selected native bytes.
Audit reverified14 codec/218 MR/150 HLS-SQ/133 failed/241 fresh profile/1415
native bindings, exact historical preimage only. Native COMPILE only: actual
fetched large READ RX/HLS/DMA/status/host visibility/CQ execution remains
unverified. Next fresh native runtime must add large READ and retain all29
old cases/oracles/<=30s limits, not reuse an old binary or normalize snapshots.
All11 scope retained, kernel/provider/API/physical/mid-READ recovery/large RX/
Immediate/multiSGE and original timing13.885ns>4ns/default1.08ns remain open.
No hardware/default/module/install/network/fan/BIOS/flash/reboot/automatic Git.
[Evidence and limits](ROCEV2_ATOMIC.md).

Progress133 (historical): actual private READ RX/MSN/memory/whole-WR lifetime is connected.
One complete READ request, independent per-response PSN/class counter, only
LAST marks RX complete/ACKs retained replay, final HLS ACK uses LAST PSN and
full producer receipt checks first->next response-span PSNs. Original actual
MAC/EOF/tail/replay/memory/CQ joins/global drains unchanged. New lifetime002
PASS10 methods/29 four-state cases:19 READ controls plus all10 original
WRITE/SEND. READ65/4097/8193/1MiB (1/2/3/256 modeled response events), absent
LAST/ACK/memory/producer, wrong PSN/class/syndrome/full-owner/unknown and bad
first/next/opcode receipt controls. READ runtimes<0.123s; largest old1MiB
WRITE28.919s, original30s limits retained. RX/HLS/memory/CQ/MAC pins modeled;
1MiB READ is not actual RX payload/HLS/native DMA/runtime qualification.
Failed001 preserves19 READ passes but five inherited Python helper-export
startup errors. All222 bindings and20 uncompiled hardware leaves preserved;
only existing helper export added, hardware bytes unchanged. Complete native
elaboration001 PASS3.508s/1409 bindings, exact old60 protected RX guards and
all116 fresh unit leaf copies equal selected native bytes. Actual expected
MSN connected; one actual generated HLS/shared MR/PTE/nonce/PSN/MSN domain,
both global drains0. Fresh unit462/native1409 bindings verified; historical
changed generator resolves only to exact saved preimage. COMPILE ONLY: READ
admission4096/RNC8191/CQC31/default/kernel/provider unchanged. Next distinct
matched capability/admission and genuine native SQ/MR/RX/data/status/CQ runtime
remain, alongside mid-READ recovery/API/physical and all11 original scope.
HLS13.885ns still fails original4ns/default1.08ns/full-board timing. No hardware,
install/load/network/fan/BIOS/program/flash/reboot/automatic commit/push.
[Evidence and limits](ROCEV2_ATOMIC.md).

Progress132 (historical): genuine-SQC expected-remote-MSN component now PASSES7 methods/
12 four-state cases. The reused fixture now selects the actual128-byte SQC
and actual matching fetch; the production profile assertion is unchanged.
004's unchanged RTL diagnostic proves a fixture delta-cycle sampling race:
guardff before combinational settling, guard80 after #1, exact assertion and
foreign-expectation quarantine then pass. Corrected005 passes all11 cases.
New two-genuine-SQC case006 exposes latest-configured-QP-only selection;
all11 prior cases still pass. The real RTL now retains per-QP accepted routes
and selects actual SQC identity by offered/held full owner. Fresh007 passes
all12, independent per-QP1->2 MSN history without route reconfiguration.
Same route/epoch does not reset; newer genuine SQC epoch does. Each case
0.0293..0.0389s, original10s bounds; route/WR/TX/CQ endpoints remain MODELS.
Actual accepted-QP/SQC/owner/CQ/config/queue joins are wired into the complete
native graph; elaboration002 PASS3.447s/1404 bindings, one extra MSN predictor,
all previous common HLS/MR/PTE/nonce domains and both global drains0 retained.
All116 historical005/122 failed006/122 fresh007/1404 old-native/1404 fresh-native
bindings reverified, changed historical sources resolve ONLY to saved exact
preimages. This is component runtime plus native COMPILE, not native wire/
protocol or physical qualification. The expected-MSN output is not yet
connected to segmented RX; actual READ final-response/lifetime/CQ/retry joins
remain. READ admission4096 and kernel/provider/defaults unchanged. All11 scope
retained; original timing13.885ns still fails4ns/default1.08ns. No hardware,
install/load/network/fan/BIOS/program/flash/reboot/automatic commit/push.
[Evidence and limits](ROCEV2_ATOMIC.md).

Publication checkpoint131 (2026-10-21, historical): user explicitly requested a progress
commit/push. Include current expected-remote-MSN predictor/native derivation
and its failed tests as WIP, not a completed feature. The route observer covers
genuine accepted TX-only configuration; a dedicated SQC lookup is intended
to supply real cookie/epoch/PD without a mailbox-busy gap. These are source
changes, not verified native behavior. Attempts001/002 failed during checked
derivation startup. Attempt003 compiles six cases, but ALL stop at time zero:
the reused fixture has not selected the mandatory128-byte SQ profile. All50
source bindings match; no logical MSN operation, lease, epoch transition or
native runtime has passed this batch. Original reports/logs/models remain.
The passing130 cohort is unchanged. Large READ admission remains4096;
protected RX/MSN/whole-WR lifecycle, mid-READ recovery and original board
timing remain open. No hardware/module/network/fan/BIOS/flash/reboot changes.
This publication request does not authorize future automatic commits/pushes.
[Exact evidence and limitations](ROCEV2_ATOMIC.md).

Progress130: actual native READ memory selector/external-unpad bypass and
exact new generated HLS are wired into the full parent hierarchy. Legacy
source/READ/Atomic/zero paths are unchanged; one full-owner READ role retains
token/unpad/DMA/CQ ownership. Same common MR/PTE/physical nonce/backend ports,
not a new memory table or bypass. Mux003 PASS9 methods/17 four-state cases,
all11 old cases retained, original10s runtime bounds,299 bindings verified.
Failed001/002/preimages are preserved; actual unchanged unknown-route READY
was X despite quarantine, now explicitly gated and asserted known-zero.
Legacy short-READ fixture respects its existing outer CQ lifetime rather
than inventing the retained READ-only extra barrier; memory/status checks stay.
Complete native elaboration001 PASS3.459s/1400 bindings, original module/domain/
port/clock/drain checks; one MR/PTE/nonce/new HLS PSN/MSN/RX and both drains0.
COMPILE ONLY: large READ admission remains4096. Protected segmented RX,
trusted expected REMOTE MSN and actual final-response/whole-WR lifetime/CQ
are still needed before opening a new distinct capability profile/runtime.
Current RNC8191/CQC31/default/kernel/provider and hardware remain unchanged.
All11 scope retained, timing13.885ns still fails original4ns/default1.08ns.
No hardware/install/load/network/fan/BIOS/program/flash/reboot/automatic Git.
[Evidence and limits](ROCEV2_ATOMIC.md).

Progress129 (historical): actual retained READ fragment controller + unchanged bounded
unpad/executor children now exist. Every saved full748 owner supplies full64
VA/relative offset/key authority; one protected placement lease, fresh A001..
Afff nonwrapping child tags, checked actual padded raw commands and exact
unpadded DMA bytes, all fragment data/status joins, one aggregate memory
event and identical CQ retirement retain the owner through the whole WR.
Executor001 PASS12/33; unchanged RTL plus two new lifetime cases in002 PASS
14 methods/35 cases, ALL four-state, including1MiB/256 fragments15.942s.
Actual HLS C++ output-snapshot integration001 PASS:4 full owners/278 commands/
1126403 payload bytes/9 removed pad bytes through actual origin router/new
controller/unpad/executor. CPP4.830s, RTL12.775s; two corrupt copies<0.134s.
All307 historical unit/338 snapshot/319 current unit bindings verified with
exact old fixture preimage; no report relabeling/changed original assertions.
CPP and RTL execute separately. Protected RX/placement, backend statuses/
visibility/fences and CQ are MODELS, not actual native MR/PTE/physical nonce/
DMA/CQ/Linux/API integration or generated-RTL runtime. Default READ4096;
trusted remote MSN, mid-READ recovery, large RX/Immediate/multi-SGE remain.
Original timing13.885ns fails4ns/default1.08ns; full-board fit/timing unproven.
All11 requirements retained; no hardware/default/install/load/fan/BIOS/network/
program/flash/reboot/automatic Git writes. [Evidence and limits](ROCEV2_ATOMIC.md).

Progress128 (historical): true segmented READ HLS C++003 PASSES all11 modes: prior complete
regressions/291 wire-replay oracles, four READs4097..1MiB/278 response packets/
four stored request replays and nine actual negative controls. READ runtime
4.801s; prior8.028s; negatives<0.072s each, original30s bounds unchanged.
The failed001 real timer rejects nonterminal owned updates; corrected002/003
distinguish trusted READ_FIRST progress from terminal ACK/Atomic/READ_ONLY/
READ_LAST, and joins validate response opcode/token/PSN as well. No final
certificate was relaxed. Failed001 and all authoring preimages remain.
New owned-service/Immediate compatibility001 PASS0.964s with actual Atomic
RTL, unchanged runner/oracles and original30s bound. All311 C++003 and310
compatibility bindings reverified;003 hardware bodies equal passing002.
New HLS generation001 PASSES365.89s on exact003 under original1500MiB/4ns/
default1.08ns/8QP/2000-entry/port/source/compatibility gates. Generated171
files/259 frozen inputs remain exact; all15 checked port widths match.
Exact generated-RTL elaboration001 PASS1.732s/705 total bindings. This is NOT
RTL runtime/native/timing proof: estimate13.885ns FAILS original timing.
Resources81862LUT/98926FF/209BRAM18K/0DSP; no board fit/closure claim.
Default READ4096, trusted remote MSN/retry/native DMA/CQ/Linux/
provider/physical integration and all11 original requirements remain open.
Two inactive object caches were losslessly backed up and moved to RAM to
retain the original space guard; restore before any reboot. No reboot needed
or authenticated goal-restore proof; no hardware/default/install/load/fan/
BIOS/network/program/flash/automatic commit/push changes.
[Evidence and limits](ROCEV2_ATOMIC.md).

Publication checkpoint (2026-10-21, historical): corrected protected segmented READ RX
component002 is terminal PASS, all17 methods/60 cases. All8500 bindings/594
unique files were reverified.59 cases are four-state; the explicit1MiB case
is two-state,256 packets/one token/321979 cycles, runtime1.423s. Failed001 and
its independent same-binary diagnostic are preserved, not relabeled.
New true segmented READ HLS source is separate and unselected. Its actual
C++ compile and prior regressions PASS, but new READ runtime001 FAILS after
first4096-byte data placement when timer processing resumes. The unchanged
external replay timer rejects nonterminal owned updates; its relationship
to this failure remains a diagnosis, not a completed fix. Remaining new
negative modes did not run. No synthesis/native/whole-WR CQ/physical READ
qualification; default READ limit4096 and all11 requirements remain.
This user-requested publication includes unfinished source and failed
evidence, with no authorization for subsequent automatic commit/push.
[Evidence and limits](ROCEV2_ATOMIC.md).

Progress127 (historical): NEW separately named protected segmented READ-response leaf
retains full748-bit owner/one placement token over FIRST/MIDDLE/LAST, checks
per-packet CRC/peer/PSN/length/class/AETH and trusted expected REMOTE MSN,
exports offset/bytes/last/AETH-presence and keeps the downstream lease.
Not selected in native/HLS/kernel/provider; incremental RNIC READ still4096.
Component001 FAILED only on an overbroad warning classifier after full1MiB
compile179.48s;16of17 methods/59four-state cases PASS (all8oldAtomic+2zero
methods retained), tails4097..12289/PSN-wrap/bad CRC/header/MSN/lease covered.
All8518 bindings/612unique files verified before fix. SAME unmodified1MiB
two-state binary independently PASSES256packets/one token/321979cycles1.442s;
not a relabeled all-suite pass. Fresh002 keeps all17/60,180s/30s bounds,
actual port/pin refusal and unchanged RTL;1MiB loop fixture runs FIRST.
Fresh1MiB case also PASS1.414s/identical DUT/packet bytes/321979cycles; remaining
suite RUNNING, no all17 pass. Actual READ memory/HLS/common-state/CQ/
Linux/API/native/physical integration and all11 original requirements remain.
No hardware/default/install/load/reboot/automatic publication.
[Evidence and limits](ROCEV2_ATOMIC.md).

Progress126 (historical): SAME matched8191 native-full001 is terminal PASS ALL29 cases,
compile427.49s/runtime18.05..26.61s; all1443 source/artifact/RAM bindings
reverified. No prior4095 result substituted. New actual profile4 standard
post_send/MR/SQ/CQ C consumes13 UNEDITED native SQ/CQ snapshot pairs and
matches all128 posted/coherent bytes, genuine complete owners and standard
WC/ref retirement. Kernel/native CQ001 PASSES65 ASan/UBSan cases (13genuine+
52explicit-copy mutations), compile6.59s, each<0.015s,172 bindings verified.
CAS/FADD/READ/SEND_IMM/small WRITE/SEND/8193 WRITE/SEND/five zero operations
covered; corrupt operands/extensions/length/offset never ACK/free/publish.
Linux/pins/DMA/MMIO/teardown are MODELS, native/C page tables separate, not
live kernel/RTL/provider/API/physical execution. All11 original requirements,
large RX/READ/Immediate/multi-SGE/recovery/original timing remain OPEN.
No hardware/default/install/load/reboot/automatic publication.
[Evidence and limits](ROCEV2_ATOMIC.md).

Progress125 (historical): SAME matched8191 native build finished;8193-byte WRITE26.61s and
SEND26.31s PASS complete independent wire/data/nonce/source/full748-CQ/owner
oracles, rechecked from immutable case logs/events. Actual AXI capture
8191/13/15/31 matches kernel RNC/SQC/RQC/CQC; CQ feature31 in both events.
Three actual source/physical-nonce commands/frames and one whole-WR CQ/retire
per case, no fault/live owners/source changes. ALL27 old regressions continue;
NOT an all29 pass, final report/all-bindings audit pending. Compiler terminal,
same launcher alive; no restart/input edits. Physical endpoints remain models;
standard libibverbs-to-actual-Linux execution is still not proved. All11 goals,
large RX/READ/Immediate/multi-SGE/recovery/original timing remain OPEN.
No hardware/install/load/reboot/default/automatic publication.
[Evidence and limits](ROCEV2_ATOMIC.md).

Progress124 (historical): exact8191 standard-provider cohort PASSES all FIVE actual public
libibverbs/ASan/UBSan profiles, including ALL four old profiles and new4097/
8193/1MiB WRITE/SEND chains/MR/second-bad-WR/zero-byte-WC serialization.
Only fake-fd syscalls/WC replies are modeled; not actual kernel execution.
Four-state RNC8191/CQC31 AXI/CQ/dependency tests PASS27 cases/290 bindings;
ALL six old mailbox cases/four old CQ owners remain. Whole matched graph
elaboration002 PASS3.17s/1220 bindings/no width mismatch/same owner/domain/
drain gates. Only two actual identity leaves change; no default selection.
Fresh exact-profile all29 native-full001 is COMPILING, not runtime-passed.
Fixture expected capability fields are explicit, never normalized observations.
Preserved startup/caller/provenance diagnostics waive no test or guard.
All11 requirements, actual Linux/API/native/physical integration, large RX/
READ/Immediate/multi-SGE/recovery/original timing remain OPEN. No hardware,
install/load/reboot/default/automatic publication. [Evidence and limits](ROCEV2_ATOMIC.md).

Publication checkpoint (2026-10-21, historical): new padding-native-full001 PASSES ALL29
simulated cases, including8193-byte WRITE/SEND plus ALL27 prior cases.
Compile431.52s; runtimes18.15..27.12s;1438 bound hashes reverified. Large cases
join real HLS/MR/PTE/DMA/nonce/board-TX/CDC/XGMII/FCS/SFD/MAC to one full748-bit
whole-WR CQ with real withheld final receipt; physical endpoints remain models.
This RNC4095/CQC15 private simulator graph does not qualify the new matched
RNC8191/CQC31/profile4 kernel cohort. That separate cohort PASSES running-header
build9.59s and actual C/ASan/UBSan65 cases (18new+ALL47old) under explicit
Linux/MMIO/DMA/completion models.122/143 kernel hashes reverified. No modules
installed/loaded. New RTL identity helper is not independently runtime-qualified;
matching provider/native/physical/API integration, large RX/READ/Immediate,
multi-SGE/recovery/full-board timing remain OPEN. Up to1MiB remains HLS/component
and C evidence, not full-native runtime. HLS11.180ns still fails original clocks;
historical SHA mismatch still stops scripts/check.sh. No hardware/default/
reboot changes; this publication is explicitly user-requested, not a release.
[Evidence and limits](ROCEV2_ATOMIC.md).

Progress122 (historical): native003 compiled421.59s then FAILED first large WRITE24.16s;
28 cases NOT RUN. Actual first/middle MAC frames match independent full bytes/
FCS/ICRC/tag/EOF, three source commands reach offset8193, but no final receipt/
CQ. Frozen-model inspection proves old unpadded-only normalizer overwrites
actual HLS LAST pad3 with0 and marks it bad; TX bad1/RX bad0/overflow0.1290
original bindings and failed models/preimages preserved. New named private
LAST-aware normalizer retains exact aligned lengths/zero pad and original
legacy normalization; no checksum/ICRC/owner/drain/tail gate relaxed. Component002
PASSES six methods: all3 old tests retained,5four-state methods<=17.67s and
same maximal capacity case in explicit2state Verilator0.071s.51 records verified.
New whole-graph elaboration001 PASS3.20s/1216 records/no width warnings/one new
leaf; only1of35 parent files changes module selection. Fresh all29 padding-native
full001 is COMPILING, NO runtime pass yet. Linux large capability negotiation/
SQ/MR/CQ integration and all11 requirements remain; large RX/READ/Immediate/
multi-SGE/recovery/physical/original timing still OPEN. HLS11.180ns still fails.
No hardware/default/reboot/automatic publication. [Evidence and limits](ROCEV2_ATOMIC.md).

Progress121 (historical): native002 compiled426.98s and proves its first real4170-byte
MAC frame exactly (payload/RETH/ICRC/FCS/SFD/tag/EOF) before FAILED first large
WRITE20.55s: inherited root model refused genuine low-page3DW MemRd;28 cases
NOT RUN.1288 bindings/model/preimages preserved. New strict low-page decoder
retains old4DW guards and adds actual full64 descriptor/TLP byte/order/status
joins; component001 PASSES14 cases1.64s. All35 private RNIC RTL files unchanged.
Fresh native003 is COMPILING all29 after bench/width checks; NO runtime pass.
New PRIVATE typed Linux large WRITE/SEND adapter PASSES real running-header
link3.68s and actual C/ASan/UBSan54 positive+14 negative cases0.012s, not actual
Linux posting.8 real C leaves unchanged across preserved fixture failures.
Matched large capability/SQ/MR/CQ lifetime integration remains. All11 functional/
Linux/API/physical/multi-SGE/recovery/original timing requirements remain OPEN;
HLS11.180ns still fails. No hardware/reboot/default/automatic publication.
[Evidence and limits](ROCEV2_ATOMIC.md).

Progress120 (historical): unchanged failed-model inspection isolates the inherited1KiB
whole-frame TX FIFO overflow; MAC/bad-frame/timestamp/DUT fault0, no SFD/CQ.
Its1276 original bindings/preimages are preserved. New board-faithful path
uses the actual32768-byte synchronous tx_fifo plus512-byte cut-through CDC,
with real config/width/pipeline propagation bound and all error gates retained.
Four-state board-TX component001 PASSES four methods, each<=5.15s,39 records
verified, including slow large/jumbo frames, held receipts and genuine expected
bad/oversize fatal controls. Peer ACKs now wait for actual XGMII TERM. All35
private RNIC RTL files are identical to failed001. Fresh native-full002 is
COMPILING both8193-byte cases plus ALL27 prior cases after bench/width checks;
NO runtime pass yet. All11 requirements and Linux/API/physical/multi-SGE/
recovery/original timing remain OPEN; HLS11.180ns still fails. No hardware,
reboot or automatic publication. [Evidence and limits](ROCEV2_ATOMIC.md).

Publication checkpoint (2026-10-20, historical): new large-wire native-full001 is terminal
FAILED, not compiling. Compilation succeeded in424.65s; the first8193-byte
WRITE hit `real MAC/FIFO error` after19.60s and the remaining28 cases were NOT
RUN. All1276 bound records were reverified; failed evidence is preserved.
The inherited1KiB whole-frame test FIFO differs from the board's32KiB TX FIFO
plus small cut-through CDC path; exact fatal flag/root cause remains under
investigation, with no correction or new runtime in this snapshot. The prior
27-case pass is PRE-large-wire, not this candidate. Component10-case/1MiB
and private codec15-method passes remain narrower evidence. All11 requirements,
Linux/API/physical/recovery/multi-SGE and original timing remain OPEN;
HLS11.180ns still fails original4ns/default1.08ns. No hardware changes.
[Failed run](../results/2026-10-18/rocev2-rnic-segmented-wire-native-full-001.json)
and [evidence limits](ROCEV2_ATOMIC.md).

Progress119 (historical): explicit private full-range C128 codec PASSES15 real-C/UBSan
methods; legacy zero/Atomic/4096 policies and installed/default capability
are unchanged. New actual-native8193-byte WRITE/SEND fixture genuinely
registers8721 bytes/three scattered DMA pages, checks one fullMR grant and
4096/4096/1 source reads, per-packet real HLS/ACK/PSN/MAC/cache lifetimes,
exact host/wire/sentinel bytes and one full748 CQ. Both large cases plus ALL27
prior cases are COMPILING in new native-full001 after complete bench/width
elaboration; no runtime success yet. Same1200sbuild/30scase limits/globaldrains0.
Physical endpoints remain models; all11 requirements and large RX/READ/
Immediate/multi-SGE/Linux/API/physical/recovery/timing work retained. HLS
11.180ns still fails original clocks. [Evidence and limits](ROCEV2_ATOMIC.md).

Progress118 (historical): coordinated large WRITE/SEND packet ownership is implemented in
an opt-in private derivative. Full748 owner, true FIRST/MIDDLE/LAST/whole RETH,
per-packet consecutive PSNs/RX/HLS-ACK/MAC/EOF/1024-tail and explicit cache
advance precede one final whole-WR receipt/CQ; no fake CQ/global-idle bypass.
Four-state component004 PASSES five methods/10 cases,240 records verified,
including1MiB/256 packets/255 advances/one commit in29.17s and protocol/receipt
negative controls. HLS/RX/memory/CQ/MAC-pin boundaries are models. Whole native
new-graph elaboration001 PASSES3.23s/1211 records/no width warnings, but is
COMPILE-ONLY. Prior27-case runtime is PRE-large-wire; actual new large HLS/MR/
DMA/XGMII/source/CQ runtime and all27 regressions remain. Standard codec still
limits4096; no capability/default/hardware changed. Large RX/READ/Immediate,
multi-SGE/Linux/API/physical/recovery/timing and all11 requirements retained.
HLS11.180ns still fails original clocks. [Evidence and limits](ROCEV2_ATOMIC.md).

Progress117 (historical): actual retained-source dispatcher native-full001 PASSES ALL27
scenarios after414.61s compilation, each<=24.76s;1398 source/artifact records
reverified after terminal success. Ordinary65-byte WRITE/SEND now prove actual
full748 source ownership through MR/PTE/DMA/HLS/replay, shared physical nonce,
two genuine XGMII/FCS/SFD/CDC/MAC receipts, withheld second receipt and exact
atomic CQ/HLS/source retirement. All25 old cases also pass on the same graph.
Physical endpoints remain models; normal READ/SEND_IMM keep prior MAC-receipt
models. This is not Linux/physical/timing qualification. Native large admission
still4096; per-packet true segmentation/PSN/ACK/MAC/replay ownership and one
whole-WR final CQ must be integrated coherently. Large RX/READ/Immediate,
multi-SGE, real host/API/physical/recovery/timing and all11 requirements remain.
HLS11.180ns still fails original clocks; no hardware or automatic publication.
[Evidence and limits](ROCEV2_ATOMIC.md).

Progress116 (historical): a new read-only actual source/CQ observer checks the same full748
owner across trusted admission, retained DMA/replay authority, aggregate event
and atomic genuine HLS/CQ retirement. Dispatcher native-full001 is COMPILING
ALL27 cases: nonzero ordinary WRITE/SEND plus all25 previous cases. Ordinary
source traffic now uses actual XGMII/FCS/SFD/CDC/MAC and withheld second MAC
receipt, exact logicalC001->physical1->C001 status, independent CQ-owner and
source/sentinel/wire/replay checks. Bench elaboration/width checks passed;
runtime is NOT yet proved. Original1200s build/30s-case limits remain. Large
native wire/admission/CQ, Linux/physical/API/multi-SGE/recovery/timing and all11
requirements remain open; no hardware or automatic publication changes.
[Evidence and limits](ROCEV2_ATOMIC.md).

Publication115 (historical): segmented-HLS/shared-physical-nonce native-full001 PASSES ALL25
existing cases after415.90s compilation, each<=23.91s;1380 source/artifact
records reverified. Actual HLS/MR/PTE/DMA/XGMII/FCS/SFD/CDC/MAC/CQ execute
together, but physical endpoints remain models, not Linux/hardware signoff.
New retained-source/legacy dispatcher and atomic genuine-CQ fanout are wired.
Source007 PASSES seven methods/11 cases; dispatcher003 five methods/11 cases,
including ordinary small WRITE/SEND,8193-byte fragmentation/replay, common
physical tags and withheld/foreign CQ. Their adjacent backend/CQ/grant are
models. Latest dispatcher native elaboration002 is COMPILE-ONLY; the25-case
runtime pass is the previous graph and does not exercise nonzero local
ordinary WRITE/SEND. The new dispatcher full-native probe remains unexecuted.
Native large admission/per-packet wire/whole-WR CQ, READ/Immediate>4096,
multi-SGE, standard API/Linux/physical/recovery/full-board timing and all11
requirements remain open. HLS11.180ns STILL fails original clocks. No hardware
changes; this push is explicitly requested, not future automatic authority.
[Evidence and limits](ROCEV2_ATOMIC.md).

Progress114 (historical): new common physical command nonce captures the full immutable
logical tuple AFTER all memory clients, maps fresh nonwrapping physical tags
to the actual paged backend and translates only its real matching status.
Four-state nonce001 PASSES four methods/eight cases0.13s;27records verified.
Actual new-HLS/shared-MR/PTE/backend graph elaboration002 PASSES3.23s with
1162current source records, singular domains and no width/drain bypass.
New native-full001 is RUNNING all25 existing scenarios; first AFTER_WRITE
PASSES21.50s with actual backend/nonce identity/counts checked, remaining24
pending. Read-only observers retain full tuple/status checks; no batch pass.
Large native admission/source/wire/whole-WR CQ are still OPEN, as are all11
requirements, READ/Immediate large/multi-SGE/Linux/physical/recovery/timing.
HLS11.180ns still fails original clocks. No hardware or automatic Git changes.
[Evidence and limits](ROCEV2_ATOMIC.md).

Progress113 (historical): actual segmented HLS001 PASSES generation351.54s; all696 bound
records/old ABIs verified.75,548LUT/98,051FF/209BRAM18/0DSP;11.180ns STILL
FAILS original4ns/default1.08ns. New whole-WR source DMA component retains
full748-bit authority across bounded reads/re-reads, fresh nonwrapping logical
tags and final-event handoff until exact CQ retirement. Actual unchanged
native child executes command/data/status guards; four-state source006 PASSES
six methods/nine cases1.39s with40records/nine exact child clones verified.
Backend/CQ endpoints are models; shared physical nonce isolation and actual
large native memory/wire/CQ wiring remain OPEN. READ/Immediate>4096, multi-SGE,
Linux/provider/recovery/physical/full-board timing and all11 requirements
remain. No hardware or automatic publication. [Evidence and limits](ROCEV2_ATOMIC.md).

Progress112 (historical): fresh full-native004 PASSES ALL25 zero-service/RQ/RNR/requester/
Atomic/permission scenarios, each<=22.66s, after410.44s compilation; all1207
records reverified. Actual HLS/MAC/SFD/EOF/tail run together; physical endpoints
remain two-state models. NEW same-core large WRITE/SEND source implements
true FIRST/MIDDLE/LAST, one full WR owner/final receipt, actual per-packet
ACK/replay/pointer/pool/timer/common-PSN joins and exact terminal padding.
C++00351.23s/8.06s PASSES six WRs/284 packets/seven stored replays, independent
291-wire reconstruction,1MiB payload and five no-issue negatives, plus all old
cases. Actual Atomic-RTL/unchanged Immediate compatibility00125.25s/1.01s PASS.
New-top HLS generation001 is RUNNING under original clocks/geometry/gates.
Large native/MR/DMA/MAC/CQ/kernel/provider, READ/Immediate>4096, multi-SGE,
physical/recovery/full-board timing remain open; prior13.568ns still fails.
All11 requirements retained; no hardware or automatic Git changes.
[Exact evidence and limits](ROCEV2_ATOMIC.md).

Progress111 (historical): full-native003 compiled421.03s and the first ordinary zero WRITE
reaches its real HLS/core, actual tagged4001 MAC/XGMII/FCS/SFD and full EOF/tail
lifetime. The batch FAILS its first case at a fixture tag comparison; all24
later cases did not run. Frozen-model inspection proves exact owner/core,
MAC-done/receipt/tail and fault0, but a task loop-control variable still reads0.
The expected tag now uses the monitor's independent accepted-retirement order,
retaining every exact wire/owner/drain assertion; all47 derived RTL/HLS-data
files are unchanged. Fresh25-case full-native004 is COMPILING, not a pass.
All11 requirements remain; Linux/physical/large/multi-SGE/recovery/timing are
open. No hardware or automatic Git publication. [Exact evidence](ROCEV2_ATOMIC.md).

Publication109 (historical): the genuine normal8-byte WRITE prelude in full-native002
compiled412.05s, then failed its reused Atomic-history byte oracle before
any zero-service execution; the other24 cases did not run. Frozen-model
inspection confirmed the intended data and untouched sentinels, with no DUT
fault. Only scenario-specific expected-byte selection was corrected, retaining
all byte/posted-valid checks and all47 derived RTL/HLS-data files unchanged.
Fresh25-case full-native003 is IN PROGRESS at publication, NOT a runtime pass.
Successful source/unit/HLS-generation and prior zero-RQ21-case evidence remain
distinct. Original timing still fails13.568ns; Linux/provider/physical,
large/multi-SGE, recovery and all11 requirements remain open. Explicitly
requested checkpoint push only; no hardware changes or future auto-push.
[Failure, correction and exact boundaries](ROCEV2_ATOMIC.md).

Progress108 (historical): actual ordinary-zero HLS generation PASSES340.46s,67,767LUT/
92,925FF/209BRAM18;13.568ns still FAILS original clocks. Distinct344-owner/
400-core ports and all old ABIs verified. New native integration binds the
actual privileged QP/RX references, reserves MAC before HLS, takes no RQ or
data-memory authority, and retains the packet through fresh real SFD/EOF/
1024-cycle-tail retirement. Owner/MAC tests and actual whole-native
elaboration003 PASS with singular domains/no width or drain bypass. A source
review added the real existing normal-response drain gate before zero-owner
admission; first compilation001 was stopped at294.25s before runtime and
all evidence preserved. Fresh25-case actual HLS/PCIe/XGMII/MAC native
compilation002 is LIVE, including real normal8-byte WRITE followed by zero
WRITE/READ, not a
runtime pass. All original Linux/provider/physical/large/multi-SGE/recovery/
timing requirements remain. [Exact boundaries](ROCEV2_ATOMIC.md).

Progress107 (historical): fresh fullRX004 PASSES all21 whole-native cases, each<=21.91s:
six zero-RQ capacity0/128 scenarios, two empty-RQ/RNR scenarios and all13
old requester/Atomic/permission cases. All1182 inputs/artifacts reverified;
real generated HLS/RQ fetch/ACK/XGMII/MAC/CQ execute together, physical host/
root/peer/PHY/PTP still modeled. NEW ordinary zero WRITE/READ service SOURCE
uses a distinct344-bit owner and400-bit same-table RETH/MSN/TX/PSN receipt,
not a fake RQ/Atomic alias or memory operation. C++00344.43s/2.53s and actual
owned-service/Immediate compatibility00123.58s/0.93s PASS. Native zero-service
integration and HLS generation remain separate: synth001 subsequently passes
generation at108 but fails original timing; new native runtime pending.
Original clocks/drains/geometry/board gates unchanged. All11
requirements, Linux/physical/large/multi-SGE/recovery/timing remain open.
No hardware or automatic publication changes. [Evidence and limits](ROCEV2_ATOMIC.md).

Publication106 (historical): fullRX003 compiled402.94s and PASSES three actual zero-buffer
receive scenarios (SEND/SEND_IMM/WRITE_IMM), two receives each with independent
wire/CQ checks, actual generated HLS/RQ fetch/MAC/CQ and no data MR/DMA. The
whole batch FAILS its fourth case: two128-byte-buffer receipts complete,
but the fixture counts shared local MR-table traffic as remote queries.
The fixture observer is corrected with exact independent RX/local/RQ/table
checks; all1102 failed inputs/artifacts are reverified with source preimages.
Fresh21-case fullRX004 is RUNNING at publication, NOT a pass; all47 derived
RTL/HLS-data files are unchanged. Linux/physical, remaining native cases,
ordinary zeroWRITE/READ, large/multi-SGE, original timing and all11 goal
requirements remain. This push is explicitly requested, not a release or
hardware qualification. [Details and evidence](ROCEV2_ATOMIC.md).

Progress105 (historical) adds actual coherent RQ128/zero RX/MAC/CQ full-native scenarios
alongside all13 old cases. First RX001 compiled406.98s then FAILED the first
case: actual debugger confirmed Ethernet ingress dropped a legitimate60-byte
empty SEND before IP integrity, not an observed CRC failure. Private exact
SEND44/60 steering and separate two-Ethernet-pad-byte normalization now pass
four component methods (12 routed frames plus21 good/10 bad strict-IP frames)
and actual whole-native elaboration0042.78s, no width/drain bypass. FullRX002
then passed actual IP integrity but FAILED the first case at the inherited
parser minimum requiring four payload bytes. Exact failed-model counters
and source preimages are preserved. That private minimum is corrected,
retaining full final length/pad/owner/PSN/profile checks; actual elaboration005
PASSES2.87s. FullRX003 subsequently has partial passes but FAILS the batch
(see106 above). All original checksum/ICRC/predicate/timing gates stay.
Remaining zero RX/Linux/physical/normal zeroWRITE/READ/
large/multi-SGE/timing and all11 requirements remain. [Details](ROCEV2_ATOMIC.md).

Progress104 integrates a private zero RQ admission/placement/ACK/CQ candidate
with no fake MR/DMA status.25 four-state methods PASS3.78s, including old
Atomic/Immediate cases and real ACK-owner tag/receipt/tail/CQ checks. Fresh
complete zero-RQ HLS generation PASSES321.30s; real whole-native elaboration
PASSES2.88s with one HLS/MR/PTE/PSN/MSN/fetch/RQ/ACK/CQ domain and no width
warnings. Original timing STILL FAILS (estimated13.568ns vs4ns/default1.08ns).
Native RX runtime/Linux/physical/normal zeroWRITE/READ/large/multi-SGE and
all11 original requirements remain. Independent requester full003/004
failed generated-C++ scope compilation; exact inputs/results preserved.
Fresh005 PASSES422.29s compilation and all13 whole-native REQUESTER cases,
including five zero operations with real replay/XGMII/MAC/CQ and no data
MR/DMA. Compiler partitioning only changed, deadlines/oracles unchanged.
It does NOT test the newer zero-RQ graph or Linux/physical operation.
No hardware/default/install/network/BIOS/reboot/push.
See [current boundaries](ROCEV2_ATOMIC.md).

Progress103 adds SOURCE zero RQ receive semantics in the SAME complete HLS:
real SEND/SEND_IMM/WRITE_IMM headers/empty EOF/ACK/MSN/common PSN, six posted
zero/nonzero buffer cases and six owner/EOF negatives. No zero memory
command/data, fake RQ or quiet receipt. Full-top C++003 PASSES36.86s compile/
1.40s execution with ALL prior Atomic/zero requester cases repeated. Actual
owned-service/Immediate compatibility001 PASSES22.19s/0.91s. Native RQ/CQ,
HLS generation, incoming normal zeroWRITE/READ, large/multi-SGE and all
Linux/physical/timing/full-goal work remain. At publication, separate
requester native002 has FAILED its original1200s compile limit, with NO
runtime cases executed. The huge generated C++ function at -O0 was the
observed bottleneck. Its report-bound log was preserved and only its own
leftover build children stopped; no retry, clock/source relaxation or
hardware mutation. [Details](ROCEV2_ATOMIC.md).

Progress102 observed fresh whole-native001:456.73s compilation, all eight
099 regressions and actual zero WRITE/READ PASS with real HLS/replay/MAC/
CQ and no data MR/DMA; entire batch FAILS at zero SEND. Actual frozen-model
diagnosis found the old IP48 minimum rejecting legitimate empty SEND44.
A new named native-only ICRC helper accepts44 only for SEND_ONLY/pad0;
original legacy/default/admission integrity stays unchanged. New integrity
002 PASSES3 methods/five<=15.31s four-state runs,47 valid/25 invalid frames;
full elaboration003 PASSES2.74s. Fresh changed-graph whole-native002 was
COMPILING at102, then timed out before runtime (see103 above). The new matched private4095 provider separately
PASSES all four old/new profiles and six public zero verbs/SGE/bad-WR/WC
serialization cases; syscall replies remain models. Incoming zero/RQ and
Linux/physical/large/multi-SGE/timing/full-goal qualification remain.
See [exact evidence and failure boundaries](ROCEV2_ATOMIC.md).

Progress101 adds a checked zero REQUESTER native integration candidate over
the same29-module Atomic-access graph, with actual generated zero HLS and
full748/408/816 requester ABIs. No local MR query/DMA for canonical zero
work; READ still waits for the real protected response token. Full native
elaboration002 PASSES2.92s with one MR/PTE/PSN/MSN domain and no width/drain
bypass. Staging002 PASSES14 methods/49 four-state cases, including five
actual zero framer/lifetime cases and prior Atomic regressions. Leaf002 also
PASSES39 methods/155 four-state cases in361.98s total, each simulation
bounded30s. Adjacent endpoints remain models. Fresh whole-native13-case
compilation/runtime is IN PROGRESS at this checkpoint, not a pass.
All zero incoming/RQ/provider, large/multi-SGE, actual Linux/physical and
original timing/CDC/full-goal requirements remain. See [boundaries](ROCEV2_ATOMIC.md).

Progress100 implements zero-length normal REQUESTER behavior in the same
complete Atomic/Immediate HLS SOURCE: real packet/stored replay/ACK/header/
timer/state retirement, no data-memory command, one-PSN zero READ, full
owner and exact wire oracles. C++002 PASSES0.92s and actual owned-RTL-service/
Immediate compatibility001 PASSES0.89s after permitted feature compilation.
Fresh HLS001 PASSES318.05s generation with unchanged port/capacity geometry,
63,274LUT/86,265FF/189BRAM18;13.568ns estimate still misses original clocks.
A private future4095 kernel source cohort supports actual standard zero
SQ/RQ/CQ callbacks without a local MR reference, exact full-owner checks
and explicit feature negotiation. Running-header/W=1 build PASSES9.19s;
47 ASan/UBSan modeled callback cases and11 UBSan codec methods PASS.
These are separate HLS/C/kernel-model proofs, NOT a coupled native or Linux
runtime. Complete native zero integration, incoming zero responder/RQ
semantics, matched provider4095, large/multi-SGE and all11 original goal
requirements remain. Source/evidence/cache recovery and failures are recorded
in [Atomic/zero status](ROCEV2_ATOMIC.md). No hardware or automatic push.

Progress099 adds a NEW private RNC2047 Atomic128 cohort: real privileged
QP access6/14 is bound to actual SQC cookie/epoch/PD, retained in immutable
raw RX references and captured by the actual Atomic executor. QP denial
returns RemoteAccess0x62 before lock/MR/replay; allowed QPs still need actual
MR Atomic permission. General RW-only RX remains admitted. Binding11/25,
RX refs9/16 and actual MR/paged-memory19 four-state cases PASS. Matched
standard kernel registration/QP-route/source negotiation builds with actual
running headers/W=1 in8.84s, then37 ASan/UBSan modeled callback cases PASS.
Private provider/installed serializer checks EXACT511/1023/2047 contexts and
standard MR/QP access serialization in<0.019s each. Full native elaboration
PASSES2.63s without port-width mismatches. Fresh full runtime002 PASSES465.97s
compilation then eight cases, each15.44..19.00s: all prior normal/Atomic
requester and mixed responder cases plus outgoing CAS on incoming-Atomic-
denied QP, QP denial and MR denial. Actual normal WRITE succeeds first; real
owned NAK62 requires no Atomic memory operation, with zero QP-denied MR
queries versus one MR-denied query, exact wire/FCS/ICRC/common-state and
real MAC/HLS retirement. Physical host/root/peer/PHY/PTP remain models;
ordinary requester MAC pins remain modeled. Default/proof-bound files and Atomic
capability NONE remain unchanged. All Linux/HW boundary and full-goal
requirements remain. See [Atomic details](ROCEV2_ATOMIC.md).

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
