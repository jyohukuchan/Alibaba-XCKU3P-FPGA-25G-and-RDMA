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
Historical publication checks: focused Atomic RTL12 methods PASS; an earlier
full RNIC suite was not green (native MAC-lifetime ERROR and QP-TX FAIL before
the remaining run was interrupted). The new bounded30-case native batch below
passes; this does not relabel the old suite or qualify a hardware release.

## Latest functional milestone (2026-10-22)

Publication checkpoint (progress188–190): this user-requested push includes
integrated fatal-RQ cancellation/lease-export sources, native42 results and
the paired optional Linux per-RQ flush candidate with236 callback/36 parent
modeled cases. Successful AND failed attempts remain. Live Linux–FPGA,
whole QP/device STOP, complete reference release/recovery, original timing
and physical qualification remain unproven. No hardware/default changes;
historical local/in-progress/no-Git notes below retain their original meaning.

Local190: SAME fresh native42 PASS971.526s compile/max13.891s, [runtime3212](../../results/2026-10-18/rocev2-rnic-fatal-rq-lease-native-runtime-diagnostics-001.json).
All40 old entire outcomes except seconds identical; both new real RQC19-word/
full owner/nonce/flags63/consumer certificates pass with SQC/quarantine retained.
Actual/observed700 input maps IDENTICAL. Paired optional exact FEC15/31 driver
build75 PASS11.544s; actual-C callback236/parent36 PASS, [audit2707](../../results/2026-10-18/rocev2-rnic-fatal-flush-diagnostics-001.json).
All220 old callbacks and all36 parent full summaries identical. Ordered per-RQ
flush WCs/ref puts, full-CQ retention/retry, pending SEND and QP/SQ/parent refs
are tested under EXPLICIT Linux/MMIO/certificate/pin/DMA/workqueue models.
This is not installed/running Linux-native coupling or global STOP/unpin.
Original lifecycle/whole STOP code remains; failed new counter-oracle001 is
retained with exact preimage, only its initialization baseline corrected.
All jobs terminal. No hardware/default/Git action; original11/timing/physical/
whole STOP/recovery remain. Historical compiling/unbuilt notes below stay history.

Local189: prior fresh native42 compile953.788s; all40 controls PASS/full
outcomes except seconds identical, new access case FAILS pre-command and
partial is unrun. [Failure2443](../../results/2026-10-18/rocev2-rnic-fatal-rq-cancel-failure-diagnostics-001.json)
and read-only original-O1 inspection9.351s confirm certified/current owner
but aggregate atomic_rx_guard contains permanent control quarantine. All686
actual/observed inputs match identically; failed model/binary/logs remain.
New actual RX/reference/memory lease export keeps original aggregate guards,
live control-owner VALID and every other work term; full465/eight-data
elaboration9.863s/[source2252](../../results/2026-10-18/rocev2-rnic-fatal-rq-lease-native-source-diagnostics-001.json)/
[fixture1477](../../results/2026-10-18/rocev2-rnic-fatal-rq-lease-native-fixture-diagnostics-001.json)
pass, exact SAME42 bench elaborates without diagnostics. Fresh simulator
compiles under original gates; no actual new RQC receipt yet. Paired per-RQ
Linux flush candidate remains UNBUILT and gated on actual native42/runtime
audit success. Whole STOP/error CQ/recovery/refs/timing/physical remain.
No default/hardware/Git change; all failed evidence remains false.

Local188 after `9279e4e`: actual full fatal-RQC source elaboration465 RTL/
eight data PASS9.782s, [source audit2729](../../results/2026-10-18/rocev2-rnic-fatal-rq-cancel-native-source-diagnostics-001.json).
All207 HLS and both complete SQC/RQC quarantine configuration guards remain;
only actual RQC command4 may distinguish permanent quarantine from a lease
after both fatal receivers accept and the live full owner/frontier match.
[Fixture1460](../../results/2026-10-18/rocev2-rnic-fatal-rq-cancel-native-fixture-diagnostics-001.json)
retains all40 raw inputs/oracles/444 assertions and adds two genuine full19-word
RQC receipt cases. Extended bench elaborates without diagnostics; fresh native42
compilation is LIVE under original1200/30/180s/4ns/j4/O1 gates. No new packet/
RQC runtime proof yet. Explicit optional FEC31 is NOT accepted by old FEC15
software. Error CQ/whole STOP/global drain/unpin/recovery/timing/live Linux/
physical remain. Defaults/hardware/Git unchanged since the requested push.

Publication checkpoint: this explicit push includes progress185–187 and
in-progress188 cancellation groundwork, with successful AND failed reports.
Actual FEC-native40 packet/MMIO simulation passes; optional Linux polling/
callback source builds and modeled execution pass. Live Linux-native coupling,
error/flush CQ, whole STOP/recovery and original timing remain unqualified.
Entries below retain their historical checkpoint-time state.

In-progress188: fatal RQC authority passes [33 four-state component cases](../../results/2026-10-18/rocev2-rnic-fatal-rq-authority-001.json)
on recorded native fatal records, with producer/context/lease MODELS. The
companion native derivation is a draft, not integrated/elaborated/runtime
qualified. No actual RQC cancellation receipt, CQ, STOP, global-drain,
quarantine-release or unpin proof is added. No hardware/default changes.

Local187: optional parent bootstrap/FEC polling/stop source builds75 inputs
and passes parent36/all220 old callback cases, [audit2810](../../results/2026-10-18/rocev2-rnic-fatal-parent-diagnostics-001.json).
All20 old graph and220 callback full summaries stay identical. Read-only FEC
preflight before epoch/bind before publish/start after publish and polling
without CQ users are checked. Threaded model stop joins a live handler and
prevents requeue; self-stop refuses. Logical poll stop still retains complete
graph/lease/BAR/refs. Linux/MMIO/IB-core/certificate/workqueue execution remains
modeled, NOT installed/native coupling or safe device STOP/unbind/recovery.
No default/hardware/Git changes; all original11/timing/physical remain open.

Local186: actual FEC-native40 PASS1010.068s compile/max13.791s; [runtime3155](../../results/2026-10-18/rocev2-rnic-fatal-event-native-runtime-diagnostics-001.json)
checks all40 previous full results except seconds, two added fatal-mailbox
results only. Real AXI32-word readback/ACK/observer retirement preserve native/
SQC/RQC quarantine and queued RQ; exact new snapshots pass unchanged C277.
Optional actual QP ERR/event-handler/lifetime hooks compile full73 inputs and
pass callback220/all202 old summaries, [audit1100](../../results/2026-10-18/rocev2-rnic-fatal-verbs-diagnostics-001.json).
[Cross-audit1467](../../results/2026-10-18/rocev2-rnic-fatal-event-native-software-diagnostics-001.json)
binds identical C source; Linux/certificate/MMIO execution is modeled, NOT
live Linux-native coupling. Real parent FEC attachment/polling, error/flush
CQ/STOP/recovery/ref retirement and15.571ns timing/physical remain. Jobs ended;
no default driver install/load/hardware or further Git action.

Local185 after `8c13d42`: new FEC-native40 fixture [preflight1455](../../results/2026-10-18/rocev2-rnic-fatal-event-native-fixture-diagnostics-001.json)
preserves all40 raw inputs/419 checks, adding25 actual AXI/ACK/SQC-RQC guard
checks. Entire new bench elaborates without diagnostics; fresh compiler is
LIVE under original gates, not a new packet/MMIO PASS. Runtime audit and
unchanged-C decoder/readback runner are prepared, unexecuted. No further
Git/hardware/default action; timing/Linux/error CQ/STOP/lifetimes remain.

Local184: actual event-status native40 PASS, compile967.520s/max13.841s under
original1200s/30s/180s/4ns. [Runtime audit3155](../../results/2026-10-18/rocev2-rnic-write-abort-event-native-runtime-diagnostics-001.json)
checks every old38 full outcome except wall time and genuine fatal61/62
owner/wire/HLS-abort/cancel/host/RQ/quarantine. Prior failures stay false.
This is simulation, not physical/Linux/timing (15.571ns still fails) signoff.

New optional FEC1 fatal-notification candidate retains selected1000 in32
AXI-Lite words: signature/ABI/features at0/4/8, status0xc, exact sequence ACK
0x10, last-ACK0x14, sequence0x18, fault0x1c, record0x40–0xbc. Empty/partial
owners, full SQC cookie+epoch and actual inner packet relationships are
validated; RNC command cookie/WR id/message cookie are not QP identity.
The C poller handles delivery backpressure/ambiguous ACK without duplicate
accepted callbacks and terminal detach never ACKs or releases references.
RTL11/C277/kernel-support build pass [audit1846](../../results/2026-10-18/rocev2-rnic-fatal-event-mmio-diagnostics-001.json),
using actual recorded native seeds and exact RTL readback, NOT live Linux IO.

A separate native FEC graph adds optional0x406000/4KiB aperture, same207 HLS,
two native leaf edits, tested tracked two-consumer fanout and persistent
native-quarantine SQC/RQC guards. Elaboration9.903s/[audit2748](../../results/2026-10-18/rocev2-rnic-fatal-event-native-source-diagnostics-002.json)
PASS; new FEC-native packet/MMIO and Linux QP callbacks remain unexecuted.
No driver/default capability advertisement, hardware action or further Git
publication. ACK never means error WC/STOP/global drain/unpin/recovery.

Local183: actual HLS207 generation860.083s PASS; [audit2323](../../results/2026-10-18/rocev2-rnic-write-abort-event-generated-diagnostics-001.json)
keeps all121 ports and verifies the real independent metadata engine/collector
and no duplicate old RAM. Actual metadata ap_continue=1, not scalar mf_full_n;
this structural proof is not packet execution. Native461RTL/8data hierarchy
elaborates9.860s, all262 non-HLS leaves unchanged. [Preflight2341](../../results/2026-10-18/rocev2-rnic-write-abort-event-native-fixture-diagnostics-001.json)
retains the ENTIRE previous40-case bench/419 assertions/raw bytes. A fresh
native40 executable is compiling under original gates; no new runtime pass.
Timing15.571ns still FAILS4ns/default1.08ns; all11/error CQ/STOP/lifetimes/
physical remain. No hardware/default/Git action; older live notes are history.

Local182 after `e29c8da`: actual unchanged-object observers find the SEND
stall at unfinished metadata init; ACK is pending inside the real HLS join.
Old init completes55.6us, new only1698/2000 at100.8us. Actual generated scalar
fault rendezvous throttles the II1 table behind the II15 parser. Separate
sticky-event metadata source retains identical reset sweep/RAM/owner checks,
passes C++140/legacy services/new2001-read+fault-event component and
[audit4738](../../results/2026-10-18/rocev2-rnic-write-abort-event-diagnostics-001.json),
including all160 old outcome/oracle fields. Actual HLS002 is LIVE under
original gates; no candidate native40/timing/reset-RTL/physical success yet.
Failed attempts/logs remain; no hardware/default or further Git action.

Publication checkpoint: this explicit request includes progress176–181 source,
tests and successful/failed reports. The [latest fixed-MAC native40 run](../../results/2026-10-18/rocev2-rnic-write-abort-scheduled-mac-native-full-001.json)
has ended: compilation PASS966.875s; first8 cases (including fatal access/
partial) PASS, then case9 `LARGE_SEND_IMM` fails its packet-issue deadline.
Remaining31 cases and the all40 runtime auditor were not run. No complete
native40/old38-equivalence/Atomic/standard-API/physical/timing qualification is
claimed. Original4ns still fails at15.571ns; error CQ/STOP/lifetimes remain.
The strict historical TX-padding source identity check still fails. No
hardware/default changes; older live/unpublished notes are checkpoint history.

Local181: scheduled native compiler1197.687s PASS, first access case FAILS
because test control indefinitely holds its NAK's real MAC receipt. The old
failure/binary remain. Same-binary partial diagnostic002 PASS9.383s through
real61/abort992/native cancel/selected1000/retainedRQ620/quarantine, not all40.
Diagnostic001 failed its new post-parser counter oracle; source defines
`translated` as tag rewrites (FIRST tag1==nonce1), not PTE/address translation.
No DUT/command/page/status check changes. Test-only case-correct MAC hold and
separate actor retain all419 checks/40 raw recipes/partial1100 stalls;
[preflight2320](../../results/2026-10-18/rocev2-rnic-write-abort-scheduled-mac-native-fixture-diagnostics-001.json).
Fresh fixed-bench build14062 is LIVE, not qualified. Actor-finished is NOT a
DUT/CQ/drain proof; original timing/error CQ/STOP/lifetimes/all11 remain open.

Local180: actual scheduled HLS206 generation865.357s PASS; full RTL108.19MB
to10.40MB/parser103.60MB to5.81MB. [Audit2322](../../results/2026-10-18/rocev2-rnic-write-abort-scheduled-generated-diagnostics-001.json)
retains all121 ports/domains; estimate15.571ns still FAILS original timing.
Native460RTL/8data elaboration9.671s PASS, all262 non-HLS leaves identical.
[Preflight2249](../../results/2026-10-18/rocev2-rnic-write-abort-scheduled-native-fixture-diagnostics-001.json)
retains ENTIRE original40 bench/raw/391+28 checks. Fresh binary compilation
is LIVE; original1200s/30s/4ns gates unchanged, NO fresh native40 runtime pass.
Old timeout/all11/error CQ/STOP/lifetime/physical limits remain. No hardware/
default/Git action; earlier live/unexecuted/prepared notes are checkpoint history.

Local179 preparation (not execution qualification): new
[`audit_write_abort_scheduled_generated.py`](tests/audit_write_abort_scheduled_generated.py)
checks all121 old port contracts and the entire new cohort/domains; its
original-port reader/negative controls and AST pass, but the new HLS audit
has NOT run. [`check_write_abort_scheduled_native.py`](tests/check_write_abort_scheduled_native.py)
is AST-valid and unexecuted; it requires actual generation/audits and retains
all262 non-HLS leaves unchanged. SAME HLS99277 is still live. No new native,
timing, drain, STOP or safe-unpin success is claimed; all11 remain.

Local178: actual first native40 compilation TIMED OUT at original1200s, with
zero cases run; all failure artifacts remain. Separate state-scoped abort
candidate C++140 and real legacy service compatibility PASS, with all160 old
outcome/oracle fields identical; [audit2274](../../results/2026-10-18/rocev2-rnic-write-abort-scheduled-diagnostics-001.json).
Same checks/ports960/992/checkpoint/tables/clear, not fake drain or old-core
substitution. Actual candidate HLS generation is LIVE; size/timing/native
improvement is UNPROVEN. All original11/error CQ/STOP/lifetime gates remain.
No hardware/default/Git changes; earlier native40-live notes are history.

Local176 after97781fd: exact inputs/preflight revalidate, whole new40 bench
elaborates without diagnostics; a fresh native40 binary is compiling under
the original1200s deadline, not packet-runtime-qualified yet. New runtime
audit source requires all38 old complete outcomes except seconds and genuine
fatal wire/abort/cancel/retained-RQ/quarantine, not error CQ/STOP/unpin. The
auditor itself is unexecuted. No hardware/default/Git changes; all11 remain.

Publication update: progress173–175 and unfinished176 are included, preserving
both successful and failed reports. Abort C++140/controller66, merged81,
frontend47 and whole new native elaboration pass, but original4ns timing
still FAILS (estimate15.571ns). [Native40 fixture preflight](../../results/2026-10-18/rocev2-rnic-write-fatal-native-fixture-diagnostics-001.json)
passes1449 evidence bindings; all38 old inputs/checks remain. Its fresh binary
and40 packet cases have NOT been built/run. Prior-core native38/CQ105 remain
the latest completed integrated regressions. Error CQ/full QP stop/recovery/
reference release are unfinished. No build is running and no hardware/driver/
default changes were made. Historical unpushed/live notes below are not current.

Local175: actual abort HLS208 generated1577.657s, audit2303; original timing
still FAIL15.571ns. Actual fatal61/62 quarantine/abort/cancel native hierarchy
elaborates462RTL/8data/123.334s against the whole new core. Same actual tested
ICRC/MR frontend47 and shared PSN/fatal serial helper81 pass; old46 outcomes
identical. [Source audit1743](../../results/2026-10-18/rocev2-rnic-write-fatal-native-source-diagnostics-001.json).
This is NOT fresh full native packet runtime: old38 plus genuine fatal cases
remain required. Selected1000 output is not standard error CQ/STOP/QP-global
drain/unpin; quarantine stays,63/full lifetime/all11 remain. All jobs terminal;
no hardware/default/Git action. Older live/not-wired notes are checkpoint history.

Local progress174: new separate selected-WRITE abort RTL controller66 PASS,
[audit586](../../results/2026-10-18/rocev2-rnic-write-abort-control-diagnostics-001.json).
Genuine full positive wire/commit/retire, fatal wire/retire, HLS992, local
report and actual selected cancel/readback are REQUIRED INPUT CONTRACTS;
their producers are MODELS here, not yet native-wired. Exact960/1000 ownership
and persistent quarantine do not certify QP/global drain, STOP/error CQ/unpin.
SAME HLS50411 is LIVE, not generation-qualified. No hardware/default/Git action.

Local progress173 after8017904: selected-WRITE abort C++140 PASS, all105 old
summaries/independent oracles identical, unchanged Atomic/Immediate service
compatibility PASS. [Consumer audit2307](../../results/2026-10-18/rocev2-rnic-write-abort-hls-diagnostics-001.json).
Actual retirement checkpoint/same PSN/MSN/selected state clear/verify are tested;
privileged native/MAC/fence/management producers are models. New960/992 HLS
generation is LIVE; no generated/native/fatal-QP/global-drain/unpin/physical
or timing pass is claimed. Native38/CQ105 remain the latest completed native/
software regressions and were not rerun for this core. Earlier failure/no-live
notes are history. No hardware/default/install/load/reboot/Git changes.

Publication update: the user-requested snapshot adds progress170–172 and the
unfinished progress173 WRITE-abort source, with successful AND failed reports.
Native38/CQ105 below remain the latest completed regressions. The separate
abort candidate FAILED C++ compilation (helper declarations after template
use); none of its planned140 cases ran. [Failure record](../../results/2026-10-18/rocev2-rnic-write-abort-hls-001.json).
No abort HLS generation/native integration/safe fatal-QP drain is claimed.
Earlier unpushed/no-Git/live-build statements describe their checkpoint times;
no jobs are currently live. No hardware, driver or default change accompanies
this publication. Original4ns timing and physical qualification remain unmet.

Progress172: actual fresh native38 TERMINAL PASS, including real NAK60,
suppressed repeated future MID, correct retry, identical MID and post-LAST
duplicate ACK1f WITHOUT second MR/DMA/RQ/CQ/native-PSN execution. Actual shared
HLS/MSN/MAC/host/CQ proofs and every37 old input/summary/wire/host/owner oracle
pass unchanged. Compile1039.639s/max12.389s retain original1200s/30s/4ns.
[Runtime audit3657](../../results/2026-10-18/rocev2-rnic-write-psn-control-native-runtime-diagnostics-001.json).
Real-header module build10.843s keeps all68 prior inputs identical; actual
standard C consumes unedited wholeCQ in105 cases, all100 old outcomes identical.
[Software audit1707](../../results/2026-10-18/rocev2-rnic-write-psn-control-native-software-diagnostics-001.json).
All jobs terminal, not a physical/real-peer/live-Linux/timing/fatal-QP pass.
Proper error/quarantine/teardown/full1MiB/multiSGE/live refs/all11 remain.
No install/load/program/default/Git changes; old live-build notes are history.

Progress171 starts a FRESH native38 compile: all37 old recipes/raw inputs and
378 fatal messages remain, plus actual NAK/suppression/retry/duplicate MID and
post-LAST with no second DMA/RQ/CQ. [Fixture preflight002](../../results/2026-10-18/rocev2-rnic-write-psn-control-native-fixture-diagnostics-002.json)
passes1920 evidence bindings;117 direct file bindings are consumed by the
runner BEFORE build/object creation. Old malformed nested-manifest001 and
startup rejection remain unqualified, not rewritten/waived. New whole bench
elaboration passes; native38 compilation is LIVE, not a runtime pass. Retain
original1200s/30s/4ns/root1GiB/RAM4GiB/all11. No hardware/default/Git change.

Progress170: ONE shared ACK tag sequence now handles distinct control480/
HLS512/MAC528 without an invented RQ/WRITE/RNR/data/PSN/CQ receipt. Actual
component144+2 PASS, all78 old summaries identical; actual mixed control/
WRITE/RECV/RNR/control and five-syndrome MAC frames/FCS/SFD/CDC are checked.
[Component audit770](../../results/2026-10-18/rocev2-rnic-receive-control-ack-diagnostics-001.json).
The certified PSN controller46 and native full hierarchy8.372s PASS; entire
actual new197-file HLS replaces the old cohort, with one ACK/MSN/state table
and original native MR/PTE/backend/nonce/RQ/CQ namespaces. This is NOT fresh
native runtime: all37 prior cases plus NAK suppression/retry/duplicate without
second data/RQ/CQ still need actual execution. Full fatal-QP recovery/timing/
physical/all11 remain. No hardware/default/Git actions; local afterd0ec4b6.
Actual checked frontend47 PASS; every old input/protection/replay result is
identical. [Native-source audit922](../../results/2026-10-18/rocev2-rnic-write-psn-control-native-diagnostics-001.json)
binds the actual same tested frontend in the selected native hierarchy.

Publication update: this user-requested snapshot includes progress167–169,
successful and failed reports alike. RNR/same-PSN retry native37 is the latest
completed integration; control ACK/NAK HLS generation is NOT native/MAC or
physical qualification. Older local/unpushed/building notes are checkpoint
history. Original timing/defaults/remaining requirements are unchanged.

Progress169 adds control-only480/512 HLS ownership/receipt, distinct from
WRITE424/456 and posted RQ620. The same actual ACK/MSN consumers emit duplicate
ACK1f and NAK60/61/62/63; actual MSN1 and unchanged same PSN table are checked.
CPP105 PASS, all87 old summaries/full independent oracles identical, real old
owned Atomic/Immediate RTL compatibility PASS.
[Consumer audit1907](../../results/2026-10-18/rocev2-rnic-control-response-hls-diagnostics-001.json).
Actual generation502.562s/197 RTL+data files passes under original7200s and
1500MiB-start/4ns/default1.08ns/8QP/2000. New480/512, sticky fault and all old
ports are checked. [Generated audit2239](../../results/2026-10-18/rocev2-rnic-control-response-generated-diagnostics-001.json).
LUT113600/FF143708/BRAM18K306/DSP0 are HLS estimates, not full-board fit.
15.571ns still FAILS original timing. The512 receipt proves only actual ACK
header/MSN consumption, NEVER payload/DMA/PSN advance/RQ/MAC/CQ execution.
Native full-context admission/serial, shared fresh MAC528 proof, PSN-NAK
suppression/retry/duplicate and proper fatal-QP quarantine/teardown remain.
Native RNR37 is still the prior completed native cohort, not this new HLS.
No live jobs/hardware/default/Git actions. Four exact terminal scratch DBs
have persistent verified archives and RAM copies; restore ALL old/new archived
caches before any necessary reboot. All11 remain;167–169 local after5428885.

Progress168: fresh native37 is TERMINAL PASS, including actual retained-WRITE
RNR/same-PSN retry and all36 prior cases with identical raw inputs/summary
oracles. Compile996.591s/max9.944s retain original1200s/30s/4ns bounds.
[2988-binding runtime audit](../../results/2026-10-18/rocev2-rnic-segmented-write-rnr-native-runtime-diagnostics-001.json).
Rejected LAST leaves the real8192-byte message/MR/HLS/PSN/RQ/CQ state intact;
RNR6003 uses actual SFD/EOF/tail, exact ACK retirement and independent local
report. Genuine zero-RQ post and SAME LAST/PSN retry yield positive6004 and one
whole8193/flags3 CQ. Every host byte/pad/sentinel and all four wire frames pass.
Real-header module build10.993s uses all68 IDENTICAL old frozen inputs, no
kernel feature/ABI change/install/load. Actual standard C unedited-native-CQ100
passes, all95 old outcomes identical; four corrupt new owners retain lifetime.
[1673-binding matched-source audit](../../results/2026-10-18/rocev2-rnic-segmented-write-rnr-native-software-diagnostics-001.json).
Previous202 modeled-primitive callback tests were not reexecuted. Host/root/
peer/PHY/PTP and Linux/MMIO/pins/DMA remain models, NOT installed/live Linux/
provider/physical/real-peer RNR proof.13 UNOPTFLAT warnings remain unwaived;
HLS15.571ns FAILS original timing. All11/full1MiB/multiSGE/NAK/congestion/
partial-HLS cleanup/physical remain. No active jobs/default/Git/hardware actions;
167–168 local after5428885. Older live-build statements below are history.

Progress167 inserts the checked RNR controller into the real native hierarchy:
actual native identity/message/MSN/reject input, SAME existing HLS RNR pipeline,
one shared fresh-tag ACK allocator, exact wire-proof/ACK-retire/local-consumer
handshakes. Complete elaboration passes8.348s; no new MR/HLS/PTE/backend/nonce
namespace, RQ/DMA/PSN/CQ grant or positive visibility bypass is invented.
Controller003 passes24 after only a1ns settling observation within the same4ns
cycle; failed001/002 and the unchanged DUT/observer remain exact.
[Source/fixture audit1753 bindings](../../results/2026-10-18/rocev2-rnic-segmented-write-rnr-native-source-diagnostics-001.json)
retains every36 old recipe and364 fatal messages. Fresh native37/full002 is
BUILDING, not runtime-qualified: FIRST/MID8192, rejected LAST withoutRQ, real
RNR6003, genuine zero-RQ post and SAME raw LAST/PSN retry must yield one8193
CQ and final positive6004. All36 old input/oracles/1200s/30s/4ns gates remain.
Full001 is retained as a fixture derivation startup failure, not a runtime
failure or proof.13 UNOPTFLAT warnings remain unwaived; original timing/all11
still open. No hardware/default/install/Git actions;167 local after5428885.
Older no-build/not-integrated/local statements below describe their checkpoints.

Publication snapshot includes progress162–165 and in-progress166, both passing
and failing reports. Older local/unpushed/live-build notes below are history;
no build is currently running. The newest completed integrated milestone is
profile8 native36 and the matched software-source tests, not live hardware.

The new RNR ACK derivative passes78 modes plus both old fixtures, including
RNR/WRITE/RECV/RNR through the actual MAC RTL with four distinct shared tags.
[ACK component002](../../results/2026-10-18/rocev2-rnic-receive-write-rnr-ack-002.json).
RNR packet producers and HLS/controller boundaries remain models. The new
`rocev2_segmented_write_rnr_control.v` is NOT yet native-integrated and its
[latest controller test002](../../results/2026-10-18/rocev2-rnic-segmented-write-rnr-control-002.json)
still FAILS. [Read-only observer](../../results/2026-10-18/rocev2-rnic-write-rnr-control-observer-001.json)
confirms a real REPORT handshake and registered counts, not a successful test
or native retry. No fixture, DUT or assertion is changed by this publication.
Wire RNR/retry/NAK, original timing, physical and all11 requirements remain.

Progress165: the NEW131071/511/13/63/profile8 native36 is TERMINAL PASS,
compile894.628s/max9.734s under original1200s/30s. All36 old raw inputs/data
summary oracles stay identical; only expected CSR identity literals differ.
Real running-header module build10.843s, actual standard C callback202 cases
and unedited-native-CQ95 cases all PASS. Every170 old callback summary remains
identical. New native33-word flags3/8193/Immediate/CQC511 and actual C128 zero
RQ bytes are consumed directly: IB_WC_RECV_RDMA_WITH_IMM reports8193 despite
capacity0, and four owner mutations retain queue/MR/CQ lifetime.
[2130-binding matched-source audit](../../results/2026-10-18/rocev2-rnic-segmented-write-native-software-diagnostics-001.json).
32 new callback cases cover old-profile refusal, bad tuples/geometry/WRs,
oversized/notified/corrupted events, reference retention, full CQ backpressure
and ambiguous producer ACKs. Primitive Linux/MMIO/pin/DMA and provider syscall/
WC models remain; no live installed Linux/native/provider/physical proof.
No active jobs/install/default/Git changes. Incoming WRITE wire RNR/NAK/retry,
full1MiB native/multiSGE/live refs/partial-HLS cleanup/original timing/physical
and all11 remain.13 UNOPTFLAT warnings unwaived; HLS15.571ns still FAILS4ns.

Progress164 adds private profile8/RNC131071/CQC511/SQC13/RQC63 source
derivatives across native CSR/kernel/provider. Exactly THREE native identity
leaves differ; every owner/data/MR/HLS/PSN/ACK/CQ gate remains byte-identical.
Elaboration001 passes8.168s. Fresh matching36 execution/session68327 is LIVE;
the old65535 native36 is not substituted as new-identity runtime evidence.
Actual UBSan CQ predicate140800 combinations pass,128000 old/unknown rows
identical, profile7 flags3 still4096; profile8 alone permits up to1MiB source
semantics. Actual libibverbs/private-provider all9 identities pass; six modeled
WRITE-notice lengths0..1MiB use genuine standard zero-capacity RQ marshalling,
chained bad-WR errors and network-order Immediate/WC byte counts.
[652-binding source-only audit](../../results/2026-10-18/rocev2-rnic-segmented-write-software-source-diagnostics-001.json)
also verifies the real new module builder rejects the old native identity.
NO new module build, actual callback/MR/RQ/CQ lifetime, unedited new native
snapshot consumption or installed API proof yet. Full1MiB native/multiSGE/
recovery/cleanup/original timing/physical/all11 remain; Atomic_NONE unchanged.

Progress163: native-full002/session74185 is TERMINAL SUCCESS. The fresh
actual typed-HLS/controller graph passes ALL36 cases: new8193 incoming
WRITE/Immediate plus ALL34 original recipes with identical input hashes and
summary oracles. Compile896.667s/max9.534s per case meet original1200s/30s.
[4366-binding actual-runtime audit](../../results/2026-10-18/rocev2-rnic-segmented-write-native-runtime-diagnostics-001.json).
Every payload/pad/sentinel byte and ACK frame passes, with four actual MR
queries, five scattered PCIe page writes, three visibility fences/real MAC
receipts/native PSN commits and true LAST-only zero-capacity RQ/whole8193 CQ.
Actual executable hierarchy matches elaboration, entire197-file typed HLS
RTL/data set is selected, no previous object/binary is reused. New binary SHA
`b9282fe6a0b708ba82a978a5047f054dfd754bff70e3acac1eec20dcd1eb9e3d`.
13 UNOPTFLAT warnings remain UNWAIVED (old34 build had12); runtime success
is not loop/setup/hold/CDC/DRC/routing qualification. Host/root/peer/PHY/PTP
are models, not physical pinning/PCIe ordering. Profile7 flags3 CQ limit4096
is unchanged: new8193 notices still need an explicit matched kernel/provider
capability cohort, not a silent old-profile limit increase. Full1MiB/multiSGE/
recovery/partial-HLS cleanup/original timing/all11 remain. No live jobs or
image/driver/default/hardware changes;162–163 local after7234cab.

Progress162 adds actual native FIRST-header gate runtime:512 frames/256
opcodes/two states,2560 blocked zero/unknown-gate cycles, all bytes/KEEP/EOF/
stalls and post-FIRST drain pass in0.088s under original10s/4ns/100000cycles.
[Header gate001](../../results/2026-10-18/rocev2-rnic-native-write-header-gate-001.json).
Fresh `probe_segmented_write_native_full.py` selects the EXACT elaborated
typed HLS/controller graph and the ENTIRE same-generation `.dat` manifest,
with no old executable/object reuse. New8193 WRITE/Immediate must earn
actual native424/456/PSN, whole/per-packet MR, scattered PCIe writes/fences,
real ACK/MAC and genuine LAST-only zero-capacity RQ/whole8193 CQ proofs.
All34 old case recipes/order and359 fatal checks remain;37 new fatal checks
are added. [Fixture-only audit](../../results/2026-10-18/rocev2-rnic-segmented-write-native-fixture-diagnostics-001.json).
The new36-case build is still LIVE, NOT a compilation/runtime pass. Its13
UNOPTFLAT warnings are retained/unwaived, not a loop/timing qualification.
Original1200s compile/30s cases/4ns and1GiB root/4GiB RAM guards remain.
All11/software/recovery/full1MiB/original timing/physical gates stay open.
Explicit publication7234cab covers157–161;162 stays local/unpushed.

Publication update: progress157–160 and the current progress161 integration
sources/reports are included. Earlier local/unpushed statements are history,
not the current publication state. Successful and failed evidence is retained.

Progress161 adds `derive_segmented_write_native.py` and
`check_segmented_write_native.py`. The actual checked-frame controller is now
inserted in the complete native graph, using the actual typed generated HLS,
native expected-PSN commit, SAME MR/PTE/backend/global physical nonce, ONE
dual-owner ACK allocator, genuine late RQ and whole-CQ retirement. The new
native-only first-header admission gate holds the next frame while terminal
WRITE completion is pending; already accepted frames retain their drain path.
[Native elaboration001](../../results/2026-10-18/rocev2-rnic-segmented-write-native-elaboration-001.json)
passes8.225s, all original11 feature switches enabled, no behavioral HLS,
missing-leaf waiver or port-width coercion. This is COMPILE ONLY: no fresh
34-case old native regression or new WRITE/Immediate payload runtime has run,
and the added first-header gate has no separate runtime evidence yet.
Full1MiB native/multiSGE/matched Linux-provider lifetimes, real-peer recovery/
NAK/RNR/MSN/congestion, partial-HLS cleanup and original full-board timing
remain. The previous15.571ns HLS estimate still FAILS the original4ns target
with default1.08ns uncertainty. No image/driver/capability/default is changed;
the historical TX-padding hash failure in `scripts/check.sh` is not waived.

Progress160 adds `rocev2_segmented_write_controller.v`: real checked raw
frontend/MR -> packet memory -> HLS/ACK joins, genuine680 late-RQ owner/
parsed Immediate placement, real EOF/fenced-status TX visibility and paired
frontend DONE/native-PSN commit. No ACK SFD can escape before actual backend
visibility. ALL14 cases pass, max5.283s under original10s/4ns/100000cycles;
8193 host bytes/sentinels,8344/8348 unchanged replay bytes,5 scattered page
writes/3 fences/nonces/MAC ACKs and3 native commits match. Bad status/DMA/
fence/HLS MSN emit0 positive ACKs/commits. Full derived selector512 frames
passes every opcode/force/byte/KEEP/EOF/stall. [447-binding audit](../../results/2026-10-18/rocev2-rnic-segmented-write-controller-diagnostics-001.json).
HLS/PSN endpoint/descriptor-host/CQ producers/consumers remain models or
checked C++ traces. This actual controller is NOT yet placed in the native
boundary graph; real generated-HLS runtime/all34 old regressions plus new
WRITE/Immediate/full1MiB/matched software/all11/timing still remain.
No cancellation/drain/unpin substitute; partial HLS state cleanup unproved.

Progress159 adds `derive_segmented_write_native_gateway.py`: real typed
424/456/sticky-fault ports traverse9 native leaves to actual new HLS002.
The ENTIRE old007 generated module/data set is replaced, never mixed.
A real new query client sits BELOW existing normal/SQ/Atomic arbitration
and ABOVE the SAME MR table; external native identity/held/QP/MR guards
quarantine unprotected/wrong-PD/non-WRITE/unknown offers. Full elaboration
passes8.172s with one native HLS/MR/PTE/backend/nonce and3->4 MR arbiters,
original native/READ/whole-RQ/drain0/geometry gates unchanged. Exact native
MR-island8 cases pass (four clients/same tags/stalls/high64 translations/
denial zeroing/invalidation). [1432-binding audit](../../results/2026-10-18/rocev2-rnic-write-native-gateway-diagnostics-001.json).
WRITE frontend/packet-memory/ACK/whole-CQ insertion and expected-PSN
completion updates remain; boundary ports are NOT an integrated feature.
No live generated-WRITE payload or new34-case native runtime claimed.
All11/original timing/software qualification remain;157–159 local/unpushed.

Progress158 adds `rocev2_remote_write_memory.v`: actual guarded424 MR tuple
fanout to HLS/ACK,96-bit command assertion (never DMA authority), exact
wire-padding removal and shared MR-relative backend command. Real data
EOF/ordered backend status/HLS456/actual ACK472 join before frontend DONE;
ACK retire is separate and true late-RQ ownership remains through whole CQ.
Connected actual MR/guard/RQ/nonce/PTE/staging RAM/fence/ACK/MAC graph passes
ALL14 cases, max2.700s with original10s/4ns/100000cycles. Normal/Immediate8193
bytes and every host sentinel match, with5 scattered writes/3 real fences/
3 nonce commands/3 actual XGMII/FCS/SFD/CDC ACKs. Actual notification CQ
ticket is8193, not zero RQ capacity or LAST1 byte. [398-binding audit](../../results/2026-10-18/rocev2-rnic-remote-write-memory-diagnostics-001.json).
The HLS96/456/data/ACK/whole producers and descriptor-engine/host-order/CQ
consumer boundaries are models/checked actual C++ traces, NOT live generated
HLS/complete native PCIe TLP/physical proof. Full integration/1MiB/matched
software/all11/original timing remain.157/158 local after public fbea645.

Progress157 adds `derive_receive_write_ack.py`: ONE class6000 ACK sequence
for legacy RECV and typed WRITE424, with no invented posted620 RQ for
FIRST/MID/plain LAST. LAST Immediate holds both actual identities, requires
the same456 WRITE/752 RQ PSN/MSN/extent/ACK, and emits independent472/768
proofs only after actual accepted EOF/SFD receipt/1024-tail. Neither owner
can retire alone or before both proof consumers accept. Actual MAC/FIFO/
XGMII/FCS/SFD/receipt CDC verifies five mixed full frames, shared6001..6005
tags and all six proofs. ALL58 cases plus both unchanged legacy fixtures
pass (max1.663s, original10s/4ns/100000cycles). [800-binding audit](../../results/2026-10-18/rocev2-rnic-receive-write-ack-diagnostics-001.json).
Exact actual C++8193 WRITE traces supply HLS inputs; this is NOT live new
generated-HLS/native backend/DMA/CQ/physical proof. The same original timing
and all11 remain open. Published baseline fbea645;157 stays local/unpushed.

Explicit publication now includes progress154–156 source and successful/
failed reports. Local/unpushed and old-public-HEAD notes below are history.
This does not qualify native integration, timing or hardware, and the
historical TX-padding provenance failure in `scripts/check.sh` remains.

Progress156 implements actual HLS packet completion for segmented WRITE:
native424 owner -> real parser/payload EOF/ACK-MSN/SAME PSN-table readback
->456 receipt. Full320 message identity stays across FIRST/MID/LAST; late
RQ remains a different genuine620 owner, never a fake FIRST/MID owner.
ALL87 C++ modes retain all65 old names/summaries and add22 typed cases;
each WRITE mode checks6 messages/284 full tokens through1MiB, unchanged
every byte/ACK/pad/whole-RQ oracles. Compile83.019s/new4.642/4.732s, all
original600s/30s/8QP/2000 bounds retained. Real owned Atomic/MR/memory RTL
and old Immediate compatibility pass26.199s compile/1.016s runtime.
[1116-binding evidence audit](../../results/2026-10-18/rocev2-rnic-segmented-write-owned-diagnostics-001.json).
Exact frozen002 RTL generation PASSES497.799s in `native-zero-service-hls-vwnhb_tj`
under original1500MiB/7200s/4ns/default1.08ns/old+424/456/776 port gates.
Actual estimate15.571ns FAILS original timing;112990 LUT/140339 FF/279 BRAM18K/
0 DSP are HLS estimates, not board fit. [Generation audit](../../results/2026-10-18/rocev2-rnic-segmented-write-owned-generated-diagnostics-001.json)
verifies741 more bindings. No generated-RTL functional/native/physical
success is inferred, no live job remains. The obsolete001 cohort
was never executed/synthesized and stays intact. Native real MR/DMA/fence/
ACK-MAC/CQ and safe partial-message teardown remain; do not convert separate
tests or modeled parent-drain into completion. All11 remain; local/unpushed.

Progress155 implements a checked-frame segmented-WRITE frontend. Actual
IPv4/ICRC -> saved356 privileged context/parser -> message/per-packet MR ->
late-RQ -> real registered owned replay passes47 four-state cases, max2.077s
(original10s/4ns/100000 cycles). Every authorized8193-byte WRITE/Immediate
frame byte/mask/EOF is unchanged, no replay occurs without an owner, and
even correct proof before replay EOF cannot release the message. RQ
shortage retries the same frame/PSN/tag with no duplicate replay; bad ICRC
never reaches MR. The1MiB case is FIRST+safe cancellation, NOT full transfer.
Host-only CRC constant memoization matches ALL448 unchanged-vendor masks /
55296 coefficients, no original hardware/function/XOR/policy changes.
[902-binding scope/failure audit](../../results/2026-10-18/rocev2-rnic-segmented-write-rx-front-diagnostics-001.json).
Raw context references, management, posted admission and downstream owner/
backend/HLS/MAC/CQ consumers remain models. Actual protected-native MR/PTE/
DMA/HLS/ACK-MAC/CQ/RNR integration, generated new HLS and matched software
remain; do not combine separate tests into a native proof. All11 original
requirements and original timing/physical gates stay open. Local/unpushed.

Progress154 executes the actual remote-WRITE message guard, REQUIRE_EPOCH
MR table and late-notice RQ together:46 cases through1MiB plus all62 exact
old queue modes pass (max0.122/0.165s, original4ns/100000cycles/10s/8QP).
Real full/per-packet MR checks, high key/PD/permission/range/translation,
RNR same-PSN/offset/tag retry, distinct320/620 owners, whole-byte CQ and
joint retirement backpressure run. A discovered notice/head-VALID loop is
fixed in a separate queue variant with a non-authorizing posted-head peek.
Every old actual gate reconstructs byte-for-byte; failures/preimages stay.
[Scope/failure audit](../../results/2026-10-18/rocev2-rnic-remote-write-mr-notice-diagnostics-001.json)
verifies283 bindings. Metadata/trusted QP/initial MSN, posted admission,
backend/HLS/MAC proof and CQ consumers are models; no payload DMA/new HLS
generation/native/Linux/physical claim. Full native protection/data/fanout,
matched software,1MiB native/multiSGE/interop and original timing still
remain. Latest public HEAD is be16288; these additions are local/unpushed.

Explicit publication includes progress152/153 plus unfinished
`rtl/rocev2_remote_write_message_guard.v`. The guard has only passed syntax
compilation; its actual MR-table/late-RQ functional test and native hookup
have not run. Existing success/failure reports are preserved separately.
No new hardware, timing or complete-RNIC claim is made. Historical local/
uncommitted/unpushed descriptions below describe the earlier checkpoints.

Progress153: separate new incoming segmented WRITE/Immediate HLS source
passes65 C++ modes (all44 old retained). Both new modes check6 messages/
284 packets through1MiB; runtimes3.899/3.980s, original30s bounds. FIRST
holds the RETH target/total, MID retains offset/PSN/MSN, LAST alone advances
MSN; LAST Immediate consumes one distinct posted RQ and joins actual final
data/ACK/MSN proof with whole-write metadata. RQ capacity is not DMA target
or WC length. A separate late-notice RQ passes62 four-state RTL cases (all48
old retained), maximum0.168s, full320 remote/620 RQ owner binding and sticky
CQ/remote-MR retirement fanout. Component upstream MR/HLS/MAC/visibility
producers are MODELS, not native injection or authorization. The new HLS
and queue are separate executions, not a connected native graph. Native
remote-MR message/packet refs, late RNR, DMA/MAC/CQ/software, new synthesis
and original-clock/physical qualification remain. No new HLS build starts
under the unchanged1500MiB root-space guard; no old binary or slower clock
substitute. [Evidence audit](../../results/2026-10-18/rocev2-rnic-segmented-write-receive-diagnostics-001.json)
verifies863 bindings and both startup failures/exact preimages. All11 scope
remains; installed/default/hardware/BIOS/management/Git stay unchanged.

Progress152: fresh corrected native004 ALL34 PASS (all32 old retained),
compile798.354s/new RX8.534/8.584s. Incoming8193 SEND/Immediate each uses
one8194-byte RQ, four actual MR queries, three real DMA/fence/HLS/ACK-MAC
packet releases and one whole CQ/host ACK; every modeled host payload and
sentinel byte/full620-bit owner match. Original1200s/30s/4ns gates remain.
Separate exact65535/255/13/31/profile7 kernel builds10.842s, no warning;
170 actual callback-model cases (36 RECV/all134 old),2442 actual IO C cases,
all8 real-libibverbs provider identities and90 unedited actual-native SQ/RQ/
CQ snapshot cases pass. New RX snapshots keep their original33-word shape;
no geometry words or completion proofs are synthesized. Linux/MMIO/pins/
DMA/CQ boundaries remain explicit models, not live kernel/RTL/page-table or
physical coupling. Header/native/C compile results do not install a profile.
[Full functional scope](../../results/2026-10-18/rocev2-rnic-segmented-receive-functional-diagnostics-001.json),
[actual snapshot/C lifetime audit](../../results/2026-10-18/rocev2-rnic-segmented-receive-native-software-diagnostics-001.json).
The failed callback001 vector toggled epoch1 to0 instead of a valid distinct
owner. Read-only GDB confirms that;002 changes only that input bit to63,
keeping the exact ESTALE assertion and driver. All original failure evidence
and preimages remain. All11 requirements, native1MiB/multiSGE/WRITE Immediate/
interop/timing/physical work stay open. No hardware/install/load/default/
network/fan/BIOS/flash/reboot or Git change; this addition is local/uncommitted.

Publication after progress151: actual full-native003 compiled697.994s but
FAILED the original packet1 (second packet) deadline after a genuine first
packet DMA/fence/ACK-MAC release; no whole CQ completed. Read-only archived
DUT inspection003 verifies1913 bindings and identifies raw-reference
admission closed by whole-CQ pending despite a known retained receive group.
The separate continuation deriver changes only that entrance, not ownership
or MR/HLS/MAC/CQ proof requirements. Reference gate001 passes nine current
cases plus an unchanged old-gate expected-failure control; complete native
elaboration002 with actual generated HLS passes4.865s without leaf/width
waivers. The corrected full-native34-case runner is included but NOT run.
New large incoming runtime remains unverified; all11 requirements and the
15.571ns-versus4ns timing failure remain. No live build or hardware/default/
install/load/network/fan/BIOS/flash/reboot change at publication.
[Original failure](../../results/2026-10-18/rocev2-rnic-segmented-receive-native-full-003.json),
[read-only diagnosis](../../results/2026-10-18/rocev2-rnic-segmented-receive-native-fatal-diagnostics-003.json),
[fixed graph compile](../../results/2026-10-18/rocev2-rnic-segmented-receive-native-elaboration-002.json).
The following numbered entries retain their historical build states.

Progress150: fresh new-core compatibility001 ALL32 exact old native cases
PASS, compile642.135s/runtime4.476..6.831s; all old data/owner/MR/PTE/DMA/
nonce/fence/boardMAC/CQ oracles retained. Original004 HLS job times out at
7200s; children exit naturally, no restart or substitution of007 success.
New actual8193 incoming SEND/Immediate on one8194-byte RQ plus all32 old
cases (34 required) now builds003/session62988 after real full bench
elaboration. Three real packet/MR/fence/ACK-MAC lives, distinct whole776
receipt, one CQ, all host bytes/sentinels and withheld final1100-cycle MAC
receipt are required; no new incoming runtime success inferred yet.
001 strict anchor/002 observer-name failures and preimages remain.
[Native regression/failure audit](../../results/2026-10-18/rocev2-rnic-segmented-receive-native-regressions-diagnostics-001.json)
verifies6408 bindings. All11 requirements/original4ns timing remain;
15.571ns is a timing FAIL, no installed or hardware change or auto push.

Progress149: source007 actual HLS generation002 PASSES399.510s, real776-bit
whole output; estimate15.571ns FAILS unchanged4ns/default1.08ns timing.
Complete actual new-HLS native elaboration001 PASSES4.750s, no missing leaves
or stub, original shared MR/PTE/PSN/MSN/domain/drain multiplicities retained.
Additional real C128/PCIe/RAM/MR/messageRQ posting001 ALL4 PASS (max0.367s),
15 fetched records/10 real full-range MR queries/7 posted owners. Physical
host/root/link/config/error sink are models; no payload/HLS/MAC/CQ runtime
is inferred. Fresh new-graph ALL32 old native regression build79723 is live;
actual new incoming large transfer and matched software remain unproved.
[Generated/connection audit](../../results/2026-10-18/rocev2-rnic-segmented-receive-generated-diagnostics-001.json)
checks4672 fresh/3661 historical bindings; original padding gate still fails.
Original source004 job74092 remains live, not restarted. All11 requirements,
profile6/default incoming4096/oneSGE/Atomic_NONE and hardware settings remain.

Publication after progress147 includes the separate 1 MiB RECV C128 codec,
typed standard RECV adapter and actual full-range MR-to-message-RQ posting
tests: 37 codec methods, 78 MR/staging cases, four handoff/denial cases and
real-header/ASan/UBSan adapter execution pass. No installed or matched new
kernel/provider profile is claimed. Balanced KEEP candidate007 passes
103,665 finite old/new comparisons plus all44 C++ modes and old compatibility;
candidate005 is rejected by an actual short-beat counterexample and006's
compile failures remain. These do not prove a synthesis/timing improvement.
Original source004 synthesis was still active at 09:16 UTC, not restarted.
[Publication scope and integrity](../../results/2026-10-18/rocev2-rnic-segmented-receive-publication-diagnostics-001.json).
Native/software profile6 incoming RQ4096 and all original11 requirements
remain; no hardware, installation or module changes accompany publication.

Progress146: new whole-message RQ retains full620 ownership through packet
leases and whole CQ commit/retire. ALL48 four-state cases PASS, max0.161s;
certificate producers are explicit models. Additional actual RQ/ACK/CQC
coupling PASSES0.167s:8193 bytes/3 actual fresh-tag ACK/EOF/receipt/1024-tail
lifetimes,one actual CQ publication,all24 AXI context words/actual bytes/
Immediate and RQ-to-CQ guard until exact host ACK. HLS/MR/backend/PHY/host
endpoints remain MODELS, not live native payload proof. New coordinated
source65535/255/13/31 changes15 of40 bodies for actual saved-MR offsets,
packet/whole retire split and separate whole HLS output. Explicit-profile
syntax002 ignores missing HLS/vendor leaves (`-i`), NOT full elaboration.
SAME new HLS generation74092 is still running; no new generated RTL/timing/
native/Linux/physical proof. Profile6 incoming RQ4096/defaults unchanged;
no matched new software or installation. [Component audit](../../results/2026-10-18/rocev2-rnic-receive-message-native-components-diagnostics-001.json)
rechecks328 fresh/165 historical bindings/failures. All11 scope remains.

Progress145: separate new full-duplex HLS source adds segmented incoming
SEND/SEND_WITH_IMMEDIATE<=1MiB. [C++004](../../results/2026-10-18/rocev2-rnic-segmented-receive-hls-004.json)
ALL44 modes PASS, all21 old retained, each new operation6 messages/284
packets/all bytes,4.672/4.738s. Full620 posted owner/capacity stays distinct
from actual cumulative bytes; exact fragment/offset/PSN/padding/identity
checks, real payload EOF/ACK/MSN/SAME PSN consumers and separate packet752/
whole772 receipts. [Unchanged compatibility001](../../results/2026-10-18/rocev2-rnic-segmented-receive-compat-001.json)
PASSES actual Atomic RTL service/Immediate TX/RX. [Whole unit003](../../results/2026-10-18/rocev2-rnic-receive-message-join-003.json)
ALL18 PASS with two interleaved QPs/PSN+MSN wrap; packet certificates are
explicit models in that unit. Actual HLS generation is RUNNING with original
4ns/default1.08ns/8QP/2000/1500MiB guards and timing warnings; no generated
RTL or timing success is claimed yet. Native MR/PTE/DMA/MAC/whole CQ wiring
is NOT implemented/proved for this new receiver. Native/software profile6
RQ4096/single SGE/Atomic_NONE/defaults remain unchanged. WRITE Immediate's
remote-MR and late notification-RQ ownership is a distinct pending path,
not a SEND destination alias. All11 scope and physical/live API/recovery/
original timing gaps remain. No hardware or new Git action.

Progress143: actual generated-HLS complete-native Immediate001 PASSES ALL32:
new8193 SEND/WRITE Immediate and ALL30 old cases. Compile633.005s; all cases
4.125..6.430s/original1200s build/30s runtime. Per new WR:one actual whole MR
query/grant,3 source commands/statuses/common physical nonce translations,
3 expectations/MAC-FCS-SFD-CDC frames,2 advances,one HLS receipt/CQ;6 paged
descriptors/68 read TLPs, no data writes/fences. Every wire/source/sentinel
byte and full owner match, Immediate LAST-only, final real MAC receipt held
to prevent early CQ. Small SEND_IMM also now retains source lease/real MAC.
Physical host/root/peer/PHY/PTP MODELS; ordinary READ MAC-pin model retained.
New explicit source-only32767/127/profile6 kernel/provider cohort built against
real running headers10.242s. New WR adapter real-header build5.138s and ASan/
UBSan0.012s:48 large Immediate/22 compatibility/22 negatives, every old case
retained. Standard callback C ALL134 PASS (44 new/all90 old), max0.015s;
untouched native SQ/CQ snapshots ALL80 PASS (16 pairs/four mutations each),
all128 posted bytes and actual C refs/ACK retire match. Real libibverbs/
private provider ALL7 identities PASS (all6 old), full Immediate/SGE/MR/bad-WR
serialization with fake-fd/WC models.2586 new/103 failed historical/1665 old
native bindings verified. Strict preflight CQ-count and nested test-main/
indentation failures/preimages preserved; no assertion/gate/limit relaxed.
No live Linux/RTL/pins/page-table coupling, native1MiB or physical/timing
qualification; HLS13.885ns still fails4ns/default1.08ns. RQ4096/single SGE/
old/default/profile5/Atomic_NONE unchanged. No install/load/hardware/Git.
All11 scope remains; next coarse work: large inbound receive/Immediate and
multi-SGE, plus missing live API/recovery/original timing/physical proof.
[Audit](../../results/2026-10-18/rocev2-rnic-segmented-immediate-native-software-diagnostics-001.json).

Progress142 (historical): NEW separate32767/127 source candidate adds true segmented
SEND/WRITE Immediate<=1MiB over the same actual READ-capable HLS and native
graph. Actual C++ ALL21 old/new modes PASS; each Immediate op6 WRs/284 packets/
13 stored first/middle/LAST replays, exact LAST-only Immediate/whole receipt,
max5.469s/original30s. All old11 modes and Atomic RTL-service/Immediate TX/RX
compatibility remain. New HLS generation PASS374.863s,81375 LUT/99264 FF/
209 BRAM18K; original4ns/default1.08ns/8QP/2000 retained, estimate13.885ns FAIL.
Full-native elaboration PASS3.510s with exact14 coordinated leaves/new HLS,
strict width/shared-domain/module-count/both-global-drains0 gates. Actual
codec26 methods (all20 old), wire17 cases, source/unchanged-child19, real
MR/HLS-SQ61, register/CQ27 and padding/ICRC9 methods PASS.4513 fresh bindings
and648 historical bindings/preimages audited. Explicit HLS/RX/ACK/backend/
MAC-pin/CQ boundaries remain modeled; HLS C++ snapshots through ICRC are
separate executions. No native Immediate payload/CQ runtime, matching Linux/
provider, physical or original timing pass; receive4096/single SGE/defaults/
profile5 stay. All11 scope retained; no program/load/network/fan/BIOS/reboot/
Git change. Next coarse work: actual new generated-HLS native Immediate
runtime with all30 old regressions, then matching software source/lifetimes.
[Audit](../../results/2026-10-18/rocev2-rnic-segmented-immediate-diagnostics-001.json).

Progress140 (historical): NEW separate exact16383/63/SQC13/RQC15/stride128 software profile5
kernel/provider source cohort. Running-header full kernel build001 PASS9.989s;
actual READ WR adapter build PASS4.482s and ASan/UBSan0.012s, old54 positive/
14 negative plus new24 large READ/15 compatibility positives/14 negatives.
Actual WR/SQ/MR/CQ standard C90 cases PASS (25 new/all65 prior), max0.015s;
actual C consumes unedited native128-byte records/CQ in70 cases (14 operation
pairs/four negative mutations each), max0.016s. Real libibverbs/provider six
profiles (allfive old) PASS with new READ+SEND4097/8193/1MiB chains, max0.018s.
No user BAR/DMA/C128 ABI or MR/ref bypass; failed fixture startup/indentation/
queue-count oracle reports/preimages retained.626 fresh successful bindings,
84/90 failed historical and all1665 prior native bindings verified unchanged.
Linux/MMIO/pin/DMA/completion/fake-fd/WC boundaries remain MODELS, separate
executions not live Linux/RTL/page-table coupling. Nothing installed/loaded;
old/default8191/31 READ4096, single SGE/Immediate-RQ4096 and Atomic_NONE remain.
Native1MiB/large RX/Immediate/multi-SGE/recovery/physical/timing still open;
original13.885ns fails4ns/default1.08ns/all11 scope retained. No hardware/Git.
[Audit](../../results/2026-10-18/rocev2-rnic-segmented-read-software-diagnostics-001.json).

Progress139 (historical): actual generated-HLS complete-native queue001 PASSES ALL30
cases: new8193-byte READ plus ALL29 previous cases. Fresh compile623.025s;
all runtimes4.175..6.279s, READ6.078s, original1200s/30s limits unchanged.
Genuine SQ/MR/PTE/protected RX/MSN/HLS/DMA/shared nonce/status/fence/board
MAC-FCS-SFD-CDC/CQ run. READ has3 commands/statuses/fences,3 RX,1 placement/
HLS receipt/aggregate memory event/CQ,8193 verified bytes,4read/67write TLPs,
PSNfffffe->000001 and genuine MAC receipt. All16384 host bytes/sentinels and
whole748 owner/ABI63 CQ independently reverified; all1665 source/artifact/RAM
bindings match. Physical host/root/peer/PHY/PTP MODELS; old ordinary READ/
Immediate regressions retain original MAC-pin completion models. No native
1MiB test/Linux/API/physical/board timing pass. Original HLS13.885ns still
fails4ns/default1.08ns; defaults8191/31 keep READ4096. Next coarse work is a
separate matched16383/63 kernel/profile/provider, preserving all old profiles,
MR/queue/CQ lifetimes and all11 original requirements. No hardware or Git change.
[Audit](../../results/2026-10-18/rocev2-rnic-segmented-read-command-queue-native-diagnostics-001.json).

Progress138 (historical): -O1 native002 compiles620.672s and fails the original cycle
deadline in9.436s, not30s wall time. Actual first READ fragment/status/fence
complete; second waits for2176 bytes with data_ready1/data_valid0, next raw
command blocked, stable18000..28000cycles. All1510 bindings/model/binary/log/
source preimages preserved. New two-entry owner-checked metadata lookahead
changes one mux leaf; genuine placement/guard, independent full-owner raw
checks, original serial child DMA/status/fence and whole-CQ lease remain.
Queue component001 PASS12 methods/23 cases, all17 old cases retained; actual
child/unpad/mux/nonce, modeled HLS/placement/backend/CQ. New8193 coupled data/
command and16385 full-queue cases pass; all cases<0.342s. Native elaboration
PASS3.418s/1422 bindings, same45 module-kind/domain counts,37 common RTL files
identical, all23 unit mux bodies match selected native bytes. Fresh actual
HLS/native build live, all30 cases and1200s/30s limits preserved. No native
large READ/CQ/API/physical success yet; original timing/defaults unchanged.
[Audit](../../results/2026-10-18/rocev2-rnic-segmented-read-command-queue-diagnostics-001.json).

Progress137 (historical): corrected-route full-native001 compiles433.696s and passes the
previous genuine QP setup failure. Actual coherent SQ fetch/one READ request
through board MAC/FCS/SFD and first4096-byte paged-write/fence descriptors
are observed. Runtime hits original30s limit; no completed case, old29 not
attempted. Same-binary/identical-input line-buffered diagnostic reaches24000
cycles with33 write TLPs/no fault, but no second physical write descriptor; a real
functional stall is NOT excluded. Original failed report/binary/logs and all
1508/47 bindings stay unchanged. New -O1 host C++ build with read-only actual
child/unpad/status/nonce/backend prints is live, keeping exact RTL/clocks/
all30 cases/independent oracles/1200s build/30s runtime. First O1 elaboration
failed on seven missing .datapath observer paths; all1499 bindings/preimages
preserved before observation-only correction. No large-READ/CQ/host-visibility
or kernel/provider/hardware pass, timing relaxation or default change.
[Audit and limits](../../results/2026-10-18/rocev2-rnic-segmented-read-route-native-diagnostics-002.json).

Progress136 (historical): isolate the real QP_TX/route-observer contract mismatch. Actual
controller requires empty route fields for PSN-only setup; the old observer
overwrites the accepted peer/IP with those zeros and actual MSN logic faults.
[Component003](../../results/2026-10-18/rocev2-rnic-segmented-read-config-route-003.json)
passes six cases (one baseline fault reproduction and five corrected cases),
all<0.027s. Actual MR controller/MR/PTE/observer/predictor run; decoded host
commands/QP apply/quiescence/parent drain are modeled, NO SQC identity/WR.
Only two observer lines change in a separately checked derivation; all prior
gates/guards and default/kernel/provider profiles stay unchanged. Corrected
complete native elaboration001 PASS3.436s/1419 bindings, same domains/counts.
A fresh actual full-native build is live; READ payload/DMA/visibility/CQ and
all29 old runtime cases remain UNVERIFIED in this corrected cohort. Two probe
fixture failures/preimages and the original failed native002 remain preserved.
[Audit and limits](../../results/2026-10-18/rocev2-rnic-segmented-read-config-route-diagnostics-003.json).

Publication checkpoint135 (historical): new full-native runner adds an actual8193-byte
READ fixture ahead of ALL29 prior bounded cases. The actual connected graph
compiles, but [runtime002](../../results/2026-10-18/rocev2-rnic-segmented-read-native-full-002.json)
FAILS during QP setup before SQ fetch/READ data (`main native RNIC fault 00`).
Only LARGE_READ was attempted,16.398s; the29 old cases were NOT run in this
batch. No large-READ native runtime, CQ/host visibility, regression or physical
pass is claimed. Root cause remains unconfirmed. Exact source/artifact/binary
hashes and the failure log are preserved; [audit002](../../results/2026-10-18/rocev2-rnic-segmented-read-native-diagnostics-002.json)
verifies all1503 recorded bindings. This publication includes failed evidence,
not a green release. No hardware/default/fan/BIOS/network setting is changed.
[Evidence and limitations](../../docs/ROCEV2_ATOMIC.md).

Progress134 (historical): NEW separate RNC16383/CQC63 source profile admits READ<=1MiB
through actual SQ/local-MR/HLS-SQ/CQ gates, on the fully connected133 graph.
New private C128 READ codec passes20 methods (all15 prior unchanged), actual
MR admission11 methods/26 cases (all8 old Atomic methods), HLS-SQ8 methods/
21 cases (all5 old), register/CQ27 cases including12 genuine publications.
Old codecs still reject large READ; old8191/31/kernel/provider/default READ
remains4096. This is not new driver/provider support. Real MR rejects bad
key/PD/read-only/out-of-range work; no modeled MR grant supplies authority.
Complete native profile001 PASS3.448s/1415 bindings, same exact HLS/RX/MSN/
memory/lifetime/domain/clock/drain graph. All52 MR leaf copies,21 HLS-SQ and
2 register/CQ bodies equal actual native bytes. This is COMPILE ONLY, NOT
actual fetched large READ RX/HLS/DMA/host visibility/CQ runtime. That new
runtime plus old29 native cases are next; no old binary is relabeled.
Fixture startup failures/preimages remain. Original HLS13.885ns still fails
4ns/default1.08ns; no hardware/default/install/load/reboot/Git changes.
[Evidence and limitations](../../docs/ROCEV2_ATOMIC.md).

Progress133 (historical): new `derive_segmented_read_lifetime.py` connects actual trusted
MSN to the exact protected segmented RX and READ memory/lifetime path. One
whole READ request retains its cache through FIRST/MIDDLE, validates every
response PSN/class and uses LAST PSN for final HLS ACK; whole HLS receipt must
retain first PSN and advance next PSN by the full response span. Only LAST
ACKs replay; memory/MAC/producer/CQ joins remain real separate consumers.
[Lifetime002](../../results/2026-10-18/rocev2-rnic-segmented-read-lifetime-002.json)
PASSES10 methods/29 four-state cases:19 READ plus all10 original WRITE/SEND.
READ cases<0.123s, largest old WRITE28.919s under original30s bounds.1MiB READ
uses256 modeled response events, not real RX payload/HLS/native DMA proof.
Failed001's five inherited fixture helper-export errors and19 READ passes
are preserved, not relabeled. New native elaboration001 PASS3.508s/1409
bindings; all116 unit leaf copies and60 protected RX guards match exact
selected native bytes. One HLS/MR/PTE/nonce/PSN/MSN domain; both drains0.
This is COMPILE only: large READ admission stays4096 until distinct matched
profile/genuine SQ/MR/RX/DMA/CQ runtime. Defaults/kernel/provider/hardware
unchanged; mid-READ recovery/timing/physical qualification remain incomplete.
[Evidence and limitations](../../docs/ROCEV2_ATOMIC.md).

Progress132 (historical): expected-remote-MSN component007 PASSES7 methods/12 four-state
cases, including two genuinely allocated SQC owners interleaved WITHOUT
route reconfiguration; both QPs independently advance MSN1->2. Real128-byte
SQC/fetch profile, genuine64-bit cookie/epoch/PD lookup, all7 logical operations,
packet/replay non-recount, exact CQ lease, real guarded SQC retirement,
new-epoch-only reset and stale/unknown/foreign quarantine are checked. Each
case runs0.0293..0.0389s under the unchanged10s bound. Route/WR/TX/CQ are
MODELS, not native protocol/physical proof. Original failures/preimages remain.
Complete native elaboration002 PASS3.447s/1404 bindings with exactly one MSN
predictor, unchanged shared HLS domains/MR/PTE/nonce and both drains0. Actual
accepted TX-only QP route and SQC owner ports are wired, but expected MSN is
NOT yet connected to protected segmented RX. No native runtime pass claimed;
large READ admission stays4096 and default/kernel/provider/hardware unchanged.
[Evidence and limitations](../../docs/ROCEV2_ATOMIC.md).

Publication checkpoint131 (historical): expected-remote-MSN RTL, genuine accepted-QP/SQC
lookup wiring derivation and a test fixture are included as UNVALIDATED WIP.
[Attempt003](../../results/2026-10-18/rocev2-rnic-expected-remote-msn-003.json)
compiles six cases, but all stop at time zero on the mandatory128-byte SQ
profile assertion. This proves no MSN behavior. Earlier001/002 derivation
startup failures remain separate; no failed report is relabeled. All50
current003 source bindings match. No new complete-native elaboration/runtime
or hardware qualification is claimed for this extra derivation. READ admission
stays4096; kernel/provider/defaults and the passing130 cohort are unchanged.

Progress130: new private native READ memory selector and external-unpad route
are wired to the actual common MR/PTE/physical nonce/backend and exact new
generated HLS. Stable large-READ role uses the bounded internal unpad;
source/Atomic/zero/small READ keep the unchanged legacy paths. Actual full
token fanout and genuine CQ readiness joins remain, with no second MR table.
[Mux003](../../results/2026-10-18/rocev2-rnic-segmented-read-memory-mux-003.json)
PASSES9 methods/17 four-state cases, retaining all11 prior cases;299 bindings
verified. First failed fixture batches and an actual unknown-READY diagnostic
remain separate; READY now requires known-zero refusal under route faults.
[Complete native elaboration001](../../results/2026-10-18/rocev2-rnic-segmented-read-memory-native-elaboration-001.json)
PASSES3.459s/1400 bindings, one native MR/PTE/nonce/HLS PSN/MSN domain and
both global drains still0. This is NOT native runtime: READ admission stays
4096 until protected RX/expected remote MSN/whole-WR lifetime integration.
RNC8191/CQC31/default/kernel/provider unchanged; no large READ capability
advertised or hardware applied. [Details](../../docs/ROCEV2_ATOMIC.md).

Progress129 (historical): NEW retained whole-owner READ memory controller reuses the exact
bounded executor/unpad children, derives every subrange only from saved748
authority, retains one protected placement lease, uses fresh nonwrapping
child tags and joins all real data/status handshakes before one aggregate
event. Only identical genuine CQ retirement releases the whole owner.
[Executor002](../../results/2026-10-18/rocev2-rnic-segmented-read-executor-002.json)
PASSES14 methods/35 four-state cases, including1MiB/256 fragments15.942s,
tail padding, queued next data/commands, early/delayed/stale statuses and
late faults. First33 cases and unchanged RTL are retained;319 bindings checked.
[Actual C++-snapshot integration001](../../results/2026-10-18/rocev2-rnic-segmented-read-dma-hls-001.json)
PASSES four READs/278 real destination commands and1126403 payload bytes
through the actual origin router/controller/unpad/executor, runtime12.775s.
Two corrupt-copy controls PASS; all338 historical bindings reverified.
CPP and RTL are SEPARATE executions, not live/generated-HLS runtime; protected
RX, backend/fence/visibility/CQ endpoints are models. Actual native MR/PTE/
nonce/DMA/CQ integration, trusted remote MSN and mid-READ recovery remain.
Default READ4096 and hardware unchanged; original timing still fails13.885ns.
[Exact scope/provenance](../../docs/ROCEV2_ATOMIC.md).

Progress128 (historical): actual true READ HLS [C++003](../../results/2026-10-18/rocev2-rnic-segmented-read-hls-003.json)
PASSES all11 modes: four READs4097..1MiB/278 response packets/four stored
replays, all prior regressions/291 independent wire checks, nine negative
controls. Each request emits one complete READ and one final whole-owner
receipt after actual payload/pointer/pool/timer/common-state consumers.
READ4.801s/prior8.028s/negatives<0.072s; all311 bindings reverified.
[Compatibility001](../../results/2026-10-18/rocev2-rnic-segmented-read-compat-001.json)
also PASSES actual owned Atomic RTL-service/Immediate TX/RX0.964s/310 bindings.
The first failed run remains immutable; nonterminal READ timer progress now
has a distinct trusted class, never a final release. New guarded-source003
[HLS generation001](../../results/2026-10-18/rocev2-rnic-segmented-read-generated-hls-001.json)
PASSES365.89s,171 generated files/15 checked port widths. Exact generated-RTL
elaboration001 PASS1.732s/705 bindings, but estimate13.885ns FAILS original
4ns/default1.08ns. No generated-RTL runtime/native/physical or board-fit claim.
Default READ stays4096; trusted remote MSN, mid-READ retry, native DMA/CQ and
Linux/provider/physical integration remain incomplete. No hardware/default/
install/load/reboot or automatic publication. [Details](../../docs/ROCEV2_ATOMIC.md).

Publication checkpoint (2026-10-21, historical): protected segmented READ RX
[component002](../../results/2026-10-18/rocev2-rnic-segmented-read-response-002.json)
PASSES all17 methods/60 cases:59 four-state cases plus one explicit two-state
1MiB/256-packet case. All8500 source/artifact/RAM bindings were reverified.
A separate true segmented READ HLS candidate compiles and passes its prior
regressions, but [HLS001](../../results/2026-10-18/rocev2-rnic-segmented-read-hls-001.json)
FAILS its new READ runtime after the first4096-byte payload. Remaining new
READ modes did not run; there is no HLS synthesis/native/physical pass.
Both successful and failed reports remain separate. Incremental RNIC READ
still4096; defaults/Atomic_NONE/hardware are unchanged. See
[exact scope and remaining work](../../docs/ROCEV2_ATOMIC.md).

Progress127 (historical): new private segmented READ-response RX retains one whole748-bit
owner/placement token over validated FIRST/MIDDLE/LAST packets, with strict
CRC/peer/PSN/length/AETH/trusted-remote-MSN checks and offset/bytes/last metadata.
59four-state cases pass; component001 still FAILED because its warning
classifier rejected the compiled1MiB case before runtime. That unchanged
two-state binary independently PASSES full1MiB/256 packets/one token1.442s.
Fresh all17-method/60-case002 first1MiB case PASSES1.414s with identical DUT/
packet bytes; remaining cases RUNNING, same bounds/RTL, no full-suite pass yet. NOT selected
in native/HLS/kernel/provider, no new DMA/whole-WR CQ/physical claim. Incremental
RNIC READ remains4096; trusted MSN must not come from local inbound state/RX.
All11 original requirements remain. [Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Progress126 (historical): [matched8191 native-full001](../../results/2026-10-18/rocev2-rnic-segmented-profile-native-full-001.json)
PASSES ALL29 cases, each18.05..26.61s;1443 source/artifact/RAM hashes verified.
New [actual kernel/native SQ-CQ integration001](../../results/2026-10-18/rocev2-rnic-segmented-kernel-native-cq-001.json)
PASSES65 ASan/UBSan cases:13 genuine UNEDITED native snapshot pairs plus52
explicit-copy corruptions. Actual standard C posting/coherent128-byte SQ,
CQC31/full748-owner matching/WC and MR-ref retirement execute, including
8193 WRITE/SEND/Atomic/ordinary/zero. Linux/pins/DMA/MMIO/teardown remain
separate MODELS; not actual Linux/provider/live RTL/physical-page coupling.
Full-native large runtime is8193, up to1MiB remains HLS/component/C/provider
serialization evidence. All11 requirements and large RX/READ/Immediate/
multi-SGE/recovery/original timing remain open. No hardware/default/install/
load/reboot/automatic Git changes. [Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Progress125 (historical): new matched8191/31 native8193-byte WRITE/SEND both PASS, with
independently rechecked complete wire/data/nonce/source/full748-CQ/owner
oracles. Actual native AXI tuple8191/13/15/31 matches the kernel. Three real
packet/source commands, one final CQ/retirement and no fault/remaining owners
per case. ALL27 old regressions still run on the SAME launcher; no all29 or
whole-batch hash-audit pass yet. Physical endpoints remain models, not real
Linux/standard-API/physical execution. All11 requirements and large RX/READ/
Immediate/multi-SGE/recovery/original timing remain open. No hardware/default/
install/load/reboot/automatic Git changes. [Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Progress124 (historical): private matched8191 standard-provider cohort PASSES all FIVE
public libibverbs/ASan/UBSan profiles, retaining ALL four old ones and adding
4097/8193/1MiB WRITE/SEND chains with actual standard serialization/MR/bad-WR/
WC handling. Syscall and WC replies are modeled; not actual kernel execution.
Actual four-state RNC8191/CQC31 AXI/CQ/dependency tests PASS27 cases, and whole
new graph elaboration PASS3.17s, with same native domains/owner/drain checks.
Only two identity leaves change from the previously passing padding graph.
New matched8191/31 all29 native run is COMPILING, not runtime-qualified yet.
All11 original requirements and real Linux/API/physical/timing integration,
large RX/READ/Immediate/multi-SGE/recovery remain open. No default/install/
load/hardware/reboot/automatic publication. [Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Publication checkpoint (historical): [padding-native-full001](../../results/2026-10-18/rocev2-rnic-segmented-padding-native-full-001.json)
PASSES ALL29 simulated cases:8193-byte WRITE/SEND and ALL27 prior cases,
each18.15..27.12s.1438 source/artifact/RAM hashes reverified. Real generated
HLS/MR/PTE/DMA/nonce/board-TX/CDC/XGMII/FCS/SFD/MAC paths reach one full748-bit
whole-WR CQ, retaining real owner/tail/receipt gates. Physical endpoints remain
models; up to1MiB remains separate HLS/component evidence. This passing graph
still has RNC4095/CQC15 and an explicitly private large simulator codec.

A separate private RNC8191/CQC31/profile4 Linux cohort PASSES running-header
build9.59s and [actual C post/MR/SQ/CQ tests](../../results/2026-10-18/rocev2-rnic-segmented-kernel-post-003.json):
ALL65 ASan/UBSan cases (18new+ALL47old), including8193/1MiB WRITE/SEND and
failure lifetimes, under explicit Linux/MMIO/DMA/completion models. This is
not actual Linux execution or matched8191 native/standard-provider runtime.
Its new RTL identity helper remains unqualified. No module install/load,
default/IB_ATOMIC_NONE/hardware changes. All11 requirements and large RX/READ/
Immediate/multi-SGE/recovery/physical/original timing remain open. Historical
scripts/check.sh SHA mismatch remains. [Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Progress122 (historical): native003 proves exact first/middle large WRITE MAC frames, then
FAILED24.16s: the legacy normalizer rejects/erases correctly pre-padded LAST
metadata.28 later cases NOT RUN; no full-WR/CQ pass.1290 failed bindings/models
preserved. New named private LAST-aware adapter keeps legacy/default paths
and all real CRC/owner/drain/tail gates. Six component methods PASS, all3old
tests retained (5four-state methods,1explicit2state capacity method, each<30s).
New whole-native elaboration PASS3.20s/1216 records/one new leaf; all29-case
runtime is COMPILING, NOT passed. Linux large-profile/SQ/MR/CQ integration and
all11 functional/API/physical/multi-SGE/recovery/original-timing requirements
remain open. No hardware/install/reboot/default/automatic publication changes.
[Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Progress121 (historical): native002 proves the first real4170-byte large WRITE frame's
complete bytes/FCS/SFD/tag/EOF, then FAILED on a genuine low-page3DW PCIe read
rejected by the old root model;28 later cases NOT RUN. New strict3DW decoder
and full64 actual-descriptor/TLP range/order checks PASS14 component cases.
All35 private RNIC RTL files are unchanged. Native003 is COMPILING all29 after
bench/width checks, NOT runtime-passed. A new PRIVATE correctly typed Linux
large WRITE/SEND adapter passes real-header link and68 C/ASan/UBSan cases,
but performs no actual Linux posting/MR/SQ/CQ and is not selected by defaults.
All11 Linux/API/physical/multi-SGE/recovery/original-timing requirements remain
open; no hardware, installation or automatic publication changes.
[Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Progress120 (historical): frozen failed-model inspection proves inherited1KiB TX frame
FIFO overflow, not MAC-underflow/DUT fault. New actual board32KiB synchronous
frame queue plus512-byte cut-through CDC PASSES four component methods,
including slow large/jumbo wire/FCS/tags/held receipts and genuine bad/oversize
fatal controls. Peer ACKs now follow actual XGMII TERM; all35 private RNIC RTL
files are unchanged. New29-case native-full002 is COMPILING after bench/width
checks, NOT runtime-passed. Physical endpoints remain models; all11 functional/
Linux/API/physical/multi-SGE/recovery/original-timing requirements remain open.
No hardware or automatic publication changes.
[Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Publication checkpoint (historical): the new29-case large-wire native run has finished
FAILED. Compilation passed in424.65s; its first8193-byte WRITE stopped at a
MAC/FIFO assertion after19.60s. The other28 cases were NOT RUN. Failed evidence
is retained and its1276 bound records were reverified. The inherited1KiB
whole-frame test FIFO differs from the board's32KiB TX FIFO/cut-through CDC;
diagnosis and fixture alignment remain, with no correction in this snapshot.
The prior27-case pass is PRE-large-wire; component1MiB and codec15-method
passes do not establish native large-transfer success. This is not a release
or new hardware image. Linux/API/physical/original timing remain open.
[Failed run](../../results/2026-10-18/rocev2-rnic-segmented-wire-native-full-001.json)
and [evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Progress119 (historical): private full-range C128 codec PASSES15 C/UBSan methods without
changing old codecs/capabilities. New actual8193-byte WRITE/SEND cases use
genuine full-range MR/three DMA pages, bounded source reads, real HLS/packet/
MAC/CQ and independent wire/host oracles. All29 cases, including ALL27 prior
cases, are COMPILING after bench/width elaboration, NOT runtime-passed yet.
Physical endpoints remain models; Linux/physical/multi-SGE/recovery/original
timing remain open. [Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Progress118 (historical): an opt-in derivative now wires true large WRITE/SEND packet
ownership, coordinated range/PSN gates and one final whole-WR CQ. Actual
lifetime/cache/framer/tag/EOF/tail component tests PASS10 cases including1MiB/
256 packets in29.17s; surrounding HLS/memory/RX/CQ/MAC pins remain models.
New actual native-graph elaboration PASSES, COMPILE-ONLY. Prior27-case runtime
is the pre-large-wire graph; actual generated-HLS/native large runtime and
new-graph27-case regression remain unproved. Standard codec still limits4096.
No default/device capability/hardware changes; Linux/physical/multi-SGE/
recovery/original timing remain open. [Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Progress117 (historical): actual retained-source dispatcher native simulation PASSES ALL27
cases, each<=24.76s. Nonzero65-byte WRITE/SEND now traverse actual MR/PTE/DMA,
shared physical nonce, HLS, replay, XGMII/FCS/SFD/CDC/MAC and genuine atomic
CQ/HLS/source retirement, retaining the full owner past aggregate memory event
and withheld second MAC receipt. All25 old cases also pass on the same graph.
Physical endpoints remain models; ordinary READ/SEND_IMM keep prior MAC models.
Native large admission/per-packet wire/whole-WR CQ, Linux/provider/physical,
multi-SGE/recovery and original timing remain OPEN. No hardware capability or
new image is advertised. [Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Progress116 (historical): actual retained-source/CQ ownership observers and nonzero ordinary
WRITE/SEND are added to the new dispatcher native runtime suite. All27 cases
are COMPILING after bench elaboration/width checks, NOT runtime-passed yet.
The new ordinary cases use actual MAC/XGMII/FCS/SFD/CDC, withholding its second
receipt, and check exact full owner plus genuine DMA tag/status translation.
Large native admission/wire/CQ, Linux/provider/physical and original timing
remain unproven. [Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Publication115 (historical): the new segmented-HLS/shared-DMA-nonce native simulation PASSES
all25 existing cases, each<=23.91s. A new retained-source/legacy dispatcher now
keeps ordinary WRITE/SEND authority through replay until genuine atomic CQ
retirement; source and dispatcher unit tests each PASS11 cases. The latest
dispatcher graph has COMPILE-ONLY evidence, not the25-case runtime pass, which
is on the previous graph and lacks nonzero local ordinary WRITE/SEND cases.
Large native admission/wire/CQ, multi-SGE, Linux/provider/physical operation
and full-board timing remain OPEN. HLS11.180ns STILL fails original clocks.
No new device capability or hardware-tested image is advertised.
[Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Progress114 (historical): a shared physical DMA-command identity translator is now connected
after all actual memory clients, before the one paged backend. Unit tests and
whole new-HLS/native graph elaboration PASS; the25-case native regression is
RUNNING with its first case passed, not a whole-batch pass. Large native admission/source/wire/CQ still
remain OPEN; no device capability or physical/timing success is advertised.
[Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Progress113 (historical): segmented WRITE/SEND HLS generation PASSES,75,548LUT/98,051FF/
209BRAM18; estimated11.180ns STILL fails original timing. A new retained
whole-WR source DMA component PASSES six four-state methods/nine cases with
the actual unchanged bounded native child. Shared backend tag isolation and
actual large native memory/wire/CQ integration remain OPEN; backend/CQ in
these units are models. No device capability, bitstream, Linux or physical
success is claimed. [Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Progress112 (historical): full-native004 PASSES all25 ordinary-zero/RQ/RNR/requester/Atomic/
permission scenarios, with actual HLS/MAC/real SFD/EOF/tail. NEW same-core
large WRITE/SEND source PASSES C++ tests through1MiB: real FIRST/MIDDLE/LAST,
six WRs/284 packets/seven stored replays,291 independent full-wire checks,
one final WR receipt, PSN wrap and five no-issue negatives. Actual Atomic RTL/
unchanged Immediate compatibility also PASS. New-top HLS generation is RUNNING,
not yet generated-RTL or timing proof. Large native/kernel/provider/physical,
READ/Immediate>4096 and multi-SGE remain open. No actual device capability is
advertised. [Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Progress111 (historical): the first ordinary zero WRITE now reaches its real core and
tagged4001 MAC/SFD/EOF/tail lifetime, but native003 FAILS a fixture tag oracle;
the remaining24 cases did not run. Frozen-model inspection isolates the task
loop-number reference. The corrected monitor uses independent accepted order,
with all exact owner/core/wire/drain checks retained and no DUT/HLS changes.
Fresh25-case native004 is COMPILING, NOT a pass. Linux/physical, large/multi-SGE,
recovery and original timing remain open. [Evidence](../../docs/ROCEV2_ATOMIC.md).

Publication109 (historical): prior zero-RQ native validation PASSES all21 cases. The newer
ordinary zero WRITE/READ graph is still a development candidate: full-native002
failed a reused Atomic-history byte oracle during its normal-WRITE prelude,
before any zero service ran. Frozen-model inspection confirmed correct data
and sentinels; only the scenario-specific expected-byte selection changed.
Fresh25-case full-native003 is IN PROGRESS at this snapshot, not a pass.
Original timing still fails13.568ns; no Linux/physical/board qualification
is claimed. [Evidence and remaining work](../../docs/ROCEV2_ATOMIC.md).

Progress108 (historical): ordinary zero WRITE/READ HLS generation PASSES, and the real
native graph now connects privileged QP/RX identity, distinct service owner,
MAC-first reservation and fresh SFD/EOF/tail lifetime. Actual owner/MAC RTL
tests and full-graph elaboration PASS. Zero admission also waits for the
actual preceding normal-response MAC drain; the25-case fixture includes a
real normal WRITE prelude followed by zero WRITE/READ. Fresh native002 is still
COMPILING, not a pass. New HLS estimate13.568ns still fails original clocks;
no board signoff or actual Linux/physical qualification is claimed.
[Evidence, resources and remaining work](../../docs/ROCEV2_ATOMIC.md).

Progress107 (historical): fullRX004 now PASSES all21 whole-native requester/Atomic/zero-RQ/
RNR cases, each<=21.91s, with actual generated HLS/RQ fetch/MAC/CQ and exact
wire/owner checks. Physical host/root/peer/PHY/PTP remain models. NEW same-core
ordinary zero WRITE/READ service source uses its own344-bit owner and real
RETH/MSN/TX/PSN400-bit core receipt, no RQ or Atomic alias/data DMA. Actual
C++/owned-RTL-service/Immediate compatibility PASS; HLS generation subsequently
passes at108, not native zero-service runtime or board proof. Original timing gates and
all Linux/physical/large/multi-SGE/recovery work remain. No hardware/default/
automatic publication changes. [Exact boundaries](../../docs/ROCEV2_ATOMIC.md).

Publication106 (historical): actual fullRX003 PASSES zero-buffer SEND/SEND_IMM/WRITE_IMM
reception, two receives each with generated HLS/RQ fetch/MAC/CQ and independent
wire/CQ checks. The entire batch FAILS a later fixture counter check: local
posted-buffer MR authorization was mislabeled as wire traffic. Only the
observer is corrected, with stronger independent exact counts/owner fields.
Fresh21-case fullRX004 is RUNNING at publication, not a pass. No DUT/HLS or
deadline/oracle/drain/timing relaxation. Linux/physical, remaining native
cases, ordinary incoming zeroWRITE/READ and large/multi-SGE remain open.
This commit/push is user-requested. [Evidence and limits](../../docs/ROCEV2_ATOMIC.md).

Progress105 (historical) adds actual coherent zero-RQ receive/MAC/CQ runtime fixtures.
The first whole-native RX run FAILED at an old62-byte Ethernet minimum;
actual debugger confirmed the drop occurred before IP integrity. Exact
private SEND44/60 routing and separate two-byte Ethernet-padding handling
now pass targeted real RTL and whole-graph elaboration. FullRX002 passed
actual IP integrity, then found the old parser minimum requiring four data
bytes; its private zero-RQ derivative is corrected and elaboration005 passes.
Strict CRC/final length/predicate/owner/drain/timing gates stay. Subsequent
RX003 has partial passes but FAILS the batch (see106 above). No hardware/default changes.
See [scope and preserved evidence](../../docs/ROCEV2_ATOMIC.md).

Progress104 connects a private zero RQ/ACK/CQ source candidate and freshly
generates the actual matching complete HLS.25 four-state methods and real
whole-graph elaboration pass; native RX runtime is NOT yet proved. One
HLS/MR/PTE/PSN/MSN domain, no fabricated data-memory completion, original
drains/clocks retained. Estimated13.568ns still fails timing. Independent
requester full003/004 hit generated-C++ scope errors before runtime; fresh
005 now PASSES all13 requester cases (five zero operations), real replay/
XGMII/MAC/CQ and no data MR/DMA, each<=19.21s. This tests the older zero
requester graph, NOT native zero-RQ runtime. Linux/physical/large/multi-SGE and
normal incoming zeroWRITE/READ remain. [Details](../../docs/ROCEV2_ATOMIC.md).

Progress103 adds real RQ-owned empty SEND/Immediate SOURCE behavior with
actual header/EOF/ACK/MSN/PSN consumers and no memory transaction. Fresh
full-top C++ and actual owned-RTL-service/Immediate compatibility pass; all
prior Atomic/zero requester cases run again. Native RQ/CQ, HLS generation
and incoming normal zeroWRITE/READ remain unfinished. At publication,
requester native002 FAILED its1200s compile deadline; NO runtime cases ran.
The giant generated C++ function was the observed compiler bottleneck, not
a reported hardware fault. The original log is preserved and only its own
leftover children were stopped. No retry was started for publication;
original limits/source gates remain unchanged.
See [exact stage boundaries](../../docs/ROCEV2_ATOMIC.md).

Progress102: fresh whole-native batch001 passed all eight previous cases and
real zero WRITE/READ, then FAILED zero SEND at the old integrity IP48 limit.
A new native-only SEND44/opcode04/pad0 integrity helper passes targeted real
TX/RX RTL and whole-graph elaboration; fresh complete13-case compilation002
was IN PROGRESS at102, then timed out before runtime (see103 above).
Original integrity/timing/drains stay unchanged. A matched
private4095 provider now passes actual public libibverbs zero serialization
for six operations/both SGE forms alongside every earlier Atomic context.
These are NOT live Linux/hardware tests or a complete native zero RX/RQ pass.
See [status and preserved diagnostics](../../docs/ROCEV2_ATOMIC.md).

Progress101 integrates zero REQUESTER source into the SAME private actual
native graph. Canonical zero work uses no data MR/DMA; READ waits for the
actual protected response token. Whole-graph elaboration and14-method/49-case
four-state SQ/pad/framer/lifetime regression PASS. Actual leaf regression
also PASSES39 methods/155 cases. Complete generated-HLS/native13-case
compilation/runtime remains IN PROGRESS at this checkpoint. No whole-native zero runtime or Linux/HW
pass is claimed. Incoming zero/RQ/provider and original timing are pending.
See [current evidence and scope](../../docs/ROCEV2_ATOMIC.md).

Progress100 adds real zero-length requester SOURCE handling to the same
Atomic/Immediate HLS: five operations, stored replay and guarded ACK/header/
timer/state retirement without data-memory commands. Full C++/owned RTL
service compatibility and fresh HLS generation PASS. Private future4095
kernel zero SQ/RQ/CQ code builds with actual headers;47 modeled callback
cases and11 UBSan codec methods PASS. Complete native zero/receiver/provider
integration is still pending; no coupled Linux/native or physical result is
claimed. Original13.568ns HLS estimate still misses the timing gate. See
[full boundaries and evidence](../../docs/ROCEV2_ATOMIC.md).

Progress099 adds actual SQC-bound per-QP Atomic receive permission in a
NEW RNC2047/private Atomic128 graph, separate from general RW admission and
independently required alongside MR permission. Binding/RX-reference/MR-
paged-memory four-state cases PASS. Matched running-header kernel build,
37 modeled actual-C callback cases and public provider511/1023/2047 standard
permission serialization also PASS. Whole-native elaboration passes, and
fresh [whole-native002](../../results/2026-10-18/rocev2-rnic-atomic-access-native-full-002.json)
PASSES465.97s compilation and eight cases, each15.44..19.00s. Actual ordinary
WRITE and outgoing CAS work on an incoming-Atomic-denied QP; actual incoming
Atomic QP/MR denial returns owned NAK62 without Atomic memory commands,
with exact wire/common-state and real MAC/HLS retirement. Physical host/
root/peer/PHY/PTP remain models; ordinary requester MAC pins stay modeled.
Default/proof inputs and Atomic NONE remain. See
[permission evidence and scope](../../docs/ROCEV2_ATOMIC.md).

Progress098: [public provider002](../../results/2026-10-18/rocev2-rnic-atomic-provider-002.json)
PASSES actual libibverbs CAS/FADD serialization/WC metadata with the unchanged
provider;128-byte descriptors remain kernel-private. [Kernel/native-CQ001](../../results/2026-10-18/rocev2-rnic-atomic128-kernel-native-cq-001.json)
PASSES12 cases: actual standard callback C reproduces096 native128-byte SQ
records and consumes its unedited Atomic/READ/SEND_IMM CQ snapshots, with
operand/padding negatives retaining ownership. Syscall/Linux/pin/DMA/MMIO/
teardown boundaries are modeled, not a live kernel/RTL/physical path.
Per-QP remote-Atomic receive authority and MR permission propagation remain;
no capability advertisement, install, hardware or timing qualification.

Progress097 implements an opt-in, checked PRIVATE kernel128 requester
cohort: actual Atomic post_send/typed signal-all, dual coherent128-byte
rings, strict format negotiation, RESULT-write MR refs and full-operand
CQ/WC retirement. [Running-header build001](../../results/2026-10-18/rocev2-rnic-atomic128-kernel-build-001.json)
PASSES8.49s and [ASan/UBSan post002](../../results/2026-10-18/rocev2-rnic-atomic128-kernel-post-002.json)
PASSES14 new/15 legacy cases, each<0.015s. Those callbacks run in USERSPACE
with modeled Linux/pin/DMA/MMIO/completion boundaries, NOT in Linux or
coupled to096 RTL. Default sources/build and `IB_ATOMIC_NONE` stay unchanged.
Provider128 posting, remote-Atomic MR/QP receive permissions, actual kernel/
physical/timing qualification remain. Nothing is installed or loaded.

Progress096 now connects24 matched native replacements and PASSES
[complete elaboration003](../../results/2026-10-18/rocev2-rnic-atomic128-native-elaboration-003.json)
in2.61s with no port-width mismatch: one actual new requester HLS/PSN/MSN
and MR/PTE domain alongside unchanged legacy delivery. SQC/RQC128-byte
format and CQ operands pass11 methods/42 four-state cases with modeled
adjacent endpoints. [Fresh whole-native001](../../results/2026-10-18/rocev2-rnic-atomic128-native-full-001.json)
PASSES CAS/FADD/READ/SEND_IMM/mixed Atomic responder-WRITE, each18.65..19.01s
after447.86s feature compilation. CAS/FADD execute actual C128 SQ, same
MR/PTE, protected8-byte page-split result DMA/fence, real MAC XGMII/FCS/SFD/
CDC/replay and actual CQ ownership. Host/root/peer/PHY/PTP remain modeled;
ordinary requester MAC pins remain modeled. Kernel/provider128 posting,
standard API, physical and original timing/CDC qualification are incomplete.
Default drivers still refuse the new exact features; `IB_ATOMIC_NONE` stays.

Progress095: [generated requester003](../../results/2026-10-18/rocev2-rnic-atomic-request-generated-003.json)
PASSES actual full HLS/integrity RTL execution in1.77s: CAS/FADD exact wire/
ICRC/operands, LE8-byte result and816-bit core receipts with PSN wrap. This
is two-state RTL; upstream owner/SQ/connection/peer/memory endpoints are models.
Native response/executor/MAC-lifetime/result-pad leaves additionally PASS21
methods/110 four-state cases, preserving full748-bit ownership and existing
normal/Immediate operations. See [Atomic details](../../docs/ROCEV2_ATOMIC.md).
The PCIe/MR/staging, generated core and these native leaves are NOT yet ONE
matched128-byte native/SQC/kernel/provider/result-DMA/MAC/CQ graph. Core done
is not host visibility or WR completion. Default hardware/`IB_ATOMIC_NONE`
and original timing/CDC gates remain unchanged; no automatic push.

Progress094 adds SAME-core CAS/FADD request TX/replay and AtomicACK-derived
8-byte LE result output. [Requester C++001](../../results/2026-10-18/rocev2-rnic-atomic-request-HLS-001.json)
PASSES9 mixed fresh requests/4 real stored replays in0.47s, including held
actual result/timer/state consumers and negative class/operand/framing tests.
[Compatibility003](../../results/2026-10-18/rocev2-rnic-atomic-request-compat-003.json)
PASSES prior Immediate TX/RX and owned Atomic responder against the actual
protected MR/paged-memory RTL service in0.88s. This is C++ transport evidence,
not generated RTL/native result DMA/MAC/CQ/API/physical or timing signoff.
The matched source preserves receive620 while requester748/SQ408/done816
carry both operands. Fresh full HLS synthesis001 completes318.01s and the
actual generated bridge elaborates with ONE shared domain. Estimated13.568ns
still FAILS original4ns/1.08ns; these are not generated runtime/native/timing
signoff. Default64-byte profile and `IB_ATOMIC_NONE` remain unchanged.

Progress093 adds Atomic requester local-result MR admission and connects it
to actual128-byte SQ/PCIe/RAM fetch and real guarded748-bit owner/408-bit SQ
staging. [Positive pipeline001](../../results/2026-10-18/rocev2-rnic-atomic-request-pipeline-001.json)
and [UR-error pipeline002](../../results/2026-10-18/rocev2-rnic-atomic-request-pipeline-002.json)
PASS0.38/0.33s, checking all fetched bytes, operands and context bits. Failed
fetches preserve trusted identity but cannot generate HLS SQ authority.
New four-state admission/staging tests PASS13 methods/36 simulations;
unchanged old admission/Immediate/owner tests PASS23 methods. Physical host/
root/config and downstream owner/HLS sinks remain models. SAME-core HLS
Atomic request/ACK/result/replay, native executor/MAC/CQ and matched128-byte
SQC/driver/provider are still incomplete; default `IB_ATOMIC_NONE` remains.

Progress092: [full native runtime003](../../results/2026-10-18/rocev2-rnic-atomic-native-full-003.json)
PASSES mixed FADD/duplicate/ordinary WRITE, READ and SEND_IMM, each<=17.80s.
One actual native QP/HLS/MR/PTE/exclusive-memory graph and Atomic MAC path
are connected. Independent full-byte memory/wire/FCS/ICRC/common-state and
owner/retirement checks pass; Atomic uses actual XGMII/SFD/receipt CDC without
fake WQE/RQ/CQ. Host/root/PHY/peer/PTP input remain models; ordinary requester
MAC pins remain modeled. A strictly checked Python-only normal-ACK oracle
correction reused the unchanged frozen executable but reran ALL cases fresh.
Diagnostic001/002 remain failures. No physical/API/timing claim follows.

Atomic requester groundwork now includes a separate128-byte C codec and
actual extended SQ/RAM/mux/PCIe fetch:7 C UBSan methods,6 four-state methods/
9 simulations and both positive/UR-error DMA cases PASS. Full-width operands,
all128 bytes, queue ownership and recovery are checked. Requester admission,
shared HLS Atomic TX/ACK/result placement, matched SQC/driver and MAC/CQ/
kernel/provider integration remain; default64-byte profile and `IB_ATOMIC_NONE`
are unchanged. See [Atomic details](../../docs/ROCEV2_ATOMIC.md).

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
