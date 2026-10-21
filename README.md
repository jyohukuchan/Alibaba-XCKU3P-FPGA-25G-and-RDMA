# Alibaba XCKU3P FPGA 25G and RDMA

[日本語](README.ja.md)

Experimental **Corundum-based 25GbE NIC port for the Alibaba AS02MC04 / XCKU3P**.
Native 25GbE and experimental **FPGA RoCEv2 RC READ/WRITE initiators** have been
demonstrated against a ConnectX-4 CX455A through a QSA28 and passive SFP28 DAC.
The combined version2 image reads native CX455A memory into256KiB of protected
FPGA RAM, with every requested byte verified through actual PCIe BAR readback.
A finite 64 MiB WRITE test on the preserved WRITE003 image verified every receiver byte at **24.264 Gbit/s**
payload rate using the FPGA time counter, including initialization/drain.
This is a bounded experimental initiator, not a complete FPGA verbs provider,
inbound SEND/WRITE target, READ responder, native InfiniBand or production-reliability claim.

## Status

| Area | Current status |
| --- | --- |
| Hardware | AS02MC04, `xcku3p-ffvb676-1-e`, PCIe Gen3 x8 |
| Ethernet | One connected SFP28 port tested at native 25GbE, FEC off, AN off |
| Jumbo TCP | CX455A → FPGA **24.75 Gbit/s**; FPGA → CX455A **24.54 Gbit/s** |
| ICMP | 100/100 received in each direction; full-MTU DF packets also tested |
| Static timing | Tested clean RoCE RTL image passes setup/hold, native clocks, routing, 38 bus skews and DRC gates |
| Clean-RTL build | Combined READ/WRITE001 SRAM-loaded; accepted WRITE003 preserved as rollback |
| RDMA / RoCEv2 | Native READ/all-byte BAR capture, segmentation/tails/PSN wrap/error-CLEAR recovery and same-image WRITE regression verified; WRITE003 separately has ACK-loss/watchdog evidence |
| Incremental RNIC source | Offline native queue/MR/DMA/kernel/provider development, SEND/RECV/Immediate and Atomic responder candidates; not a new hardware-qualified image |
| Persistence | SRAM programming only; flash was not modified |

### RNIC development snapshot (2026-10-21)

Publication update: this user-requested checkpoint includes progress176–181,
the scheduled WRITE-abort implementation/tests, and successful AND failed
reports. The latest [fixed-MAC native40 run](results/2026-10-18/rocev2-rnic-write-abort-scheduled-mac-native-full-001.json)
has now ended: fresh compilation PASSES966.875s under1200; the first8 cases,
including both new fatal-WRITE cases, pass, but case9 `LARGE_SEND_IMM` fails
its packet-issue deadline (exit-6). The remaining31 cases were not run, and
the all40 runtime auditor is unexecuted. This is NOT a completed regression
or hardware release. C++140/compatibility/HLS-generation/source audits retain
their separate scopes. Original timing still FAILS15.571ns versus4ns; error
CQ/STOP/lifetimes remain unfinished. `scripts/check.sh` still fails its
historical TX-padding source identity check. No hardware/default changes;
older live/unpublished notes below are checkpoint history, not current status.

Local181: fresh scheduled compilation PASSES1197.687s under1200, but its first
access test fails: the fixture holds NAK tag6001's MAC receipt forever. Failure
and binary stay intact. A same-binary [partial diagnostic002](results/2026-10-18/rocev2-rnic-write-abort-scheduled-native-partial-diagnostic-002.json)
PASSES9.383s with genuine wire/HLS-abort/native-cancel/queued-RQ/quarantine
proofs, NOT all40. Diagnostic001's wrong tag-retag counter expectation remains
a recorded failure; `translated` counts tag changes, not address translation.
New test-only MAC-hold/actor factoring retains all419 checks/all40 raw recipes;
[preflight2320](results/2026-10-18/rocev2-rnic-write-abort-scheduled-mac-native-fixture-diagnostics-001.json)
PASSES. Same206 HLS/DUT, partial1100 stalls/gates unchanged; fresh fixed-bench
native40 build14062 is LIVE, not runtime-qualified yet. No error CQ/STOP/unpin/
timing/physical/hardware/default/Git qualification; older live notes are history.

Local180: actual scheduled HLS generation PASS865.357s,206 RTL/data files.
RTL shrinks108.19MB to10.40MB (parser103.60MB to5.81MB); [audit2322](results/2026-10-18/rocev2-rnic-write-abort-scheduled-generated-diagnostics-001.json)
preserves all121 port contracts and sole domains. Estimate15.571ns still
FAILS original4ns/default1.08ns. Whole scheduled native graph460RTL/8data
elaborates9.671s, all262 non-HLS leaves unchanged. [Preflight2249](results/2026-10-18/rocev2-rnic-write-abort-scheduled-native-fixture-diagnostics-001.json)
retains the ENTIRE original40-case bench/inputs/391+28 checks exactly. A NEW
binary is now compiling under unchanged1200s/30s gates; new native40 runtime
is NOT yet qualified. Original timeout remains a failure, all11/error CQ/
STOP/lifetimes/timing/physical remain; no hardware/default/Git action. Older
live/unexecuted notes below describe their checkpoint times.

Local progress178: the first fresh native40 compiler actually TIMED OUT at
the unchanged1200s gate; zero packet cases ran. The failed record/objects/logs
are retained. New abort HLS emitted108MB RTL, including a103.6MB parser;
new simulator C++ was1.38GB versus698MB previously. A separate state-scoped
abort/checkpoint source candidate passes all140 C++ cases and real legacy
service compatibility, retaining160 original outcome/oracle fields exactly.
[Audit2274](results/2026-10-18/rocev2-rnic-write-abort-scheduled-diagnostics-001.json).
Its actual HLS generation is now LIVE, not yet generated/native/timing-qualified.
No original check/deadline/core was waived or replaced in the failed result.
Native40/error CQ/STOP/lifetimes/original timing/all11 remain; no hardware/Git action.
Earlier live native40 statements below are historical checkpoint observations.

Local progress176 after publication97781fd: exact source/preflight revalidation
passes, and the complete new40-case bench elaborates without diagnostics.
A fresh native40 executable is compiling in a new object directory, under the
unchanged1200s deadline; no packet execution or new native runtime PASS is
claimed yet. A new runtime auditor requires every prior38 result except wall
time to match, plus real fatal wire/abort/cancel/retained-RQ/quarantine evidence.
That auditor is not runtime-qualified yet. No hardware/default/Git action;
original timing/error-CQ/STOP/lifetime/all11 requirements remain open.

Publication update: this user-requested snapshot includes progress173–175 and
the unfinished progress176 native40 test fixture, with successful AND failed
reports. WRITE-abort C++140, controller66, merged control81, frontend47 and
new native hierarchy elaboration pass in their respective scopes. Actual new
HLS generation is complete, but its estimated15.571ns FAILS the original4ns
target. [Native40 fixture preflight](results/2026-10-18/rocev2-rnic-write-fatal-native-fixture-diagnostics-001.json)
passes1449 evidence bindings and preserves all38 original case inputs/checks;
the new binary and its40 packet tests have NOT been built/run. Native38/CQ105
on the prior core remain the latest completed integrated regressions. Standard
error CQ, full QP stop/recovery and safe reference release remain unfinished.
No build is running; no FPGA/driver/default changes accompany publication.
Earlier local/unpushed/live-build statements below are checkpoint history.
`scripts/check.sh` still has its recorded historical TX-padding source-hash
mismatch; this snapshot does not claim an all-green suite or hardware release.

Local progress175 completes actual abort HLS generation208 files (1577.657s,
127951 LUT/169686 FF/306 BRAM18K/0 DSP), with [2303-binding port/domain audit](results/2026-10-18/rocev2-rnic-write-abort-generated-diagnostics-001.json).
Estimated15.571ns still FAILS original4ns/default1.08ns. New native fatal61/62
classification/quarantine/HLS-abort/real-cancel wiring elaborates against the
ENTIRE new core (462RTL/8data,123.334s). Same tested real ICRC/MR frontend47
and ONE PSN/fatal serial controller81 pass; [source audit1743](results/2026-10-18/rocev2-rnic-write-fatal-native-source-diagnostics-001.json).
This is NOT fresh native packet execution: all38 old cases plus genuine fatal
scenarios still need running. Selected1000 is not standard error CQ/STOP/QP
or global drain/unpin; fatal63/full lifetime/recovery/all11 remain. All jobs
are terminal, not blocked. No hardware/default/Git action; older live notes
below describe checkpoint times, not a physical/timing-qualified release.

Local progress174 adds a separate selected-WRITE abort RTL controller:
66 four-state cases PASS, including independent full960/1000 owners,
withheld positive commit/ACK retirement/fatal wire/HLS/cancel/local-report
proofs and retained quarantine. [586-binding audit](results/2026-10-18/rocev2-rnic-write-abort-control-diagnostics-001.json).
It is NOT YET wired into native; all upstream native/HLS/MAC/quarantine
producers are models. It never grants QP/global drain, STOP, error CQ or unpin.
The SAME new HLS synthesis50411 remains LIVE, not stopped/restarted or
generation-qualified. Native38/CQ105/CPP140 retain their separate scopes.
No hardware/default/Git changes; earlier checkpoint notes below are history.

Local progress173 after publication8017904 fixes the unfinished WRITE-abort
helper ordering and the new test's padded-tail oracle (now checks payload
AND every zero-pad byte). All140 actual C++ modes PASS, with every105 old
summary/independent oracle identical; unchanged real Atomic/Immediate service
compatibility also PASS. [2307-binding audit](results/2026-10-18/rocev2-rnic-write-abort-hls-diagnostics-001.json).
The960-bit selected-WRITE abort/992-bit receipt uses actual retirement and
same PSN/MSN tables before selected-state clear/verify. Privileged native/
MAC/fence/management inputs remain models; it is NOT native fatal-QP recovery,
a QP/global DMA drain or permission to unpin. New HLS generation is LIVE,
not qualified yet. Native38/CQ105 remain the latest completed native/software
regressions, not rerun for this new core. Original timing/all11 remain.
No hardware/default/install/load/reboot/Git action this development turn.
Earlier failed/unpushed/live notes below describe their checkpoint times.

Publication update: this user-requested checkpoint adds progress170–172 and
the unfinished progress173 WRITE-abort source, including successful AND failed
reports. Native38 and standard C CQ105 are the latest completed regressions;
the separate WRITE-abort candidate FAILED C++ compilation before any of its
planned140 cases ran. [Abort failure record](results/2026-10-18/rocev2-rnic-write-abort-hls-001.json).
Its helper declarations are not visible before their first template use;
no permissive-compiler workaround, new abort HLS generation, native integration
or safe fatal-QP recovery is claimed. Earlier local/unpushed/live-build/Git
statements below are checkpoint history. No jobs are currently running.
This publication changes no hardware, installed drivers or operating settings;
the new RNIC still lacks original4ns timing closure and physical qualification.

Progress172 completes FRESH native38: NAK/suppression/retry/duplicate without
repeated DMA/RQ/CQ, plus every37 old case, PASS (1039.639s build/max12.389s).
All37 old raw inputs, summaries and independent wire/host/owner oracles stay
identical. [3657-binding runtime audit](results/2026-10-18/rocev2-rnic-write-psn-control-native-runtime-diagnostics-001.json).
Actual real-header module build and standard C unedited-native-CQ105 also
PASS; all68 kernel inputs and100 old CQ outcomes are identical.
[1707-binding software audit](results/2026-10-18/rocev2-rnic-write-psn-control-native-software-diagnostics-001.json).
All jobs are terminal; older live-build notes below are history. Physical
host/peer/PHY and Linux/MMIO/pin/DMA boundaries remain models. This is NOT
physical qualification, live installed Linux, fatal-QP cleanup or timing
closure; all11 remain. No hardware/default/install/load/Git action this turn.

Progress171 prepares fresh native38: retain every37 old recipe/raw input and
378 fatal checks, add actual future-MID NAK, suppressed repeat, correct retry,
identical MID and post-LAST replay without repeated DMA/RQ/CQ. The original
LAST real-MAC receipt still stalls1100 cycles. [Fixture audit002](results/2026-10-18/rocev2-rnic-write-psn-control-native-fixture-diagnostics-002.json)
passes1920 evidence bindings and is strictly consumed with117 file bindings
before compilation. An earlier nested manifest schema failed before compile;
its original report/source/startup failure remain, not qualified evidence.
FRESH38 compilation is LIVE at this checkpoint, not a native control runtime
pass. Original1200s/30s/4ns/resource gates and all11 remain. No hardware/default/
Git changes; local afterd0ec4b6. Older no-build notes below are checkpoint history.

Progress170 extends the ONE RECV/WRITE/RNR allocator with distinct control
480/512/528 ownership/HLS/MAC proofs. All144 component cases and both original
legacy benches PASS; every78 prior summary is identical, including real MAC
mixed traffic and five control syndromes. [770-binding audit](results/2026-10-18/rocev2-rnic-receive-control-ack-diagnostics-001.json).
The certified PSN controller passes46 four-state cases. Actual native hierarchy
elaboration passes8.372s with the entire new197-file control HLS, not a mixed
old core. Fresh native packet execution of all37 old cases plus NAK/retry/
duplicate-no-second-data is still REQUIRED; no native runtime/physical/timing
pass is claimed. Local after user-requested publicationd0ec4b6; no new Git,
hardware, driver, BIOS, fan or network changes.
Actual checked frontend47 also PASS with every old raw input and protection/
replay result identical. [922-binding native-source audit](results/2026-10-18/rocev2-rnic-write-psn-control-native-diagnostics-001.json).

Publication update: this user-requested snapshot includes progress167–169,
including successful AND failed reports. The latest integrated native milestone
is RNR/same-PSN retry (37 cases); the new control ACK/NAK HLS is generated but
not yet native/MAC-integrated. Older local/unpushed/building statements below
are checkpoint history. No hardware release or timing pass is claimed.

Progress169 adds a DISTINCT control-only ACK/NAK path on the same HLS ACK/MSN
pipeline: full480-bit native-context/serial owner and512-bit header receipt.
CPP105 modes PASS with all87 old outcomes/oracles identical; actual old owned
Atomic/Immediate service compatibility also passes.
[1907-binding consumer audit](results/2026-10-18/rocev2-rnic-control-response-hls-diagnostics-001.json).
Actual new197-file HLS generation passes502.562s, including480/512 and every
old checked port. [2239-binding generated audit](results/2026-10-18/rocev2-rnic-control-response-generated-diagnostics-001.json).
Estimated15.571ns still FAILS original4ns/default1.08ns; this is NOT native
NAK/duplicate/MAC/fatal-QP recovery or physical qualification. Native protected
admission, shared MAC proof and fresh native regressions remain. Earlier RNR
native37 remains the completed native milestone. No jobs/install/hardware/Git
actions;167–169 local after5428885. Four terminal scratch DBs are losslessly
archived/retained in RAM; restore ALL archived caches before any needed reboot.

Progress168 completes fresh native37: retained-WRITE empty-RQ RNR and SAME
LAST/PSN retry, plus every36 old case, PASS (996.591s build/max9.944s case).
All36 old raw inputs and summary oracles stay identical.
[2988-binding actual-runtime audit](results/2026-10-18/rocev2-rnic-segmented-write-rnr-native-runtime-diagnostics-001.json).
The real-header kernel build passes10.993s with all68 frozen inputs identical;
actual standard C consumes the unedited RNR-retry CQ in100 cases, all95 old
outcomes identical. [1673-binding matched-source audit](results/2026-10-18/rocev2-rnic-segmented-write-rnr-native-software-diagnostics-001.json).
No build remains live. Host/root/peer/PHY/PTP and Linux/MMIO/pin/DMA boundaries
remain models, not live kernel/provider/physical or real-peer RNR proof. NAK,
full1MiB/multiSGE/cleanup/congestion/original timing/all11 remain. No install,
image/default/Git changes;167–168 local after5428885. Older live-build notes
below describe their checkpoints, not the current state.

Progress167 integrates retained-WRITE RNR into the actual native graph, using
the existing HLS event pipeline and ONE RECV/WRITE/RNR ACK allocator. Complete
hierarchy elaboration passes8.348s. The controller passes all24 cases after a
same-cycle test observation fix; the DUT and failed002 report stay unchanged.
[1753-binding source/fixture audit](results/2026-10-18/rocev2-rnic-segmented-write-rnr-native-source-diagnostics-001.json)
retains all36 old recipes and364 fatal messages. A FRESH37-case native build is
LIVE: empty-LAST-RQ RNR, genuine RQ post and identical LAST/PSN retry must earn
actual generated-HLS/MR/PCIe/fence/MAC/PSN/whole-CQ proof. This is NOT yet a
native RNR runtime pass.13 UNOPTFLAT warnings remain unwaived. No image,
driver, default or timing change;167 is local after publication5428885.

Publication snapshot: progress162–165 and the in-progress166 RNR sources and
reports are included. Older local/unpushed/building statements below describe
their checkpoints, not the current publication state. No build is running.
The latest completed integrated milestone is profile8 native36 plus the
kernel/provider source checks described below; this is not a hardware release.

In-progress166 adds one shared RECV/WRITE/RNR ACK allocator: all78 component
modes and both legacy fixtures pass, including four mixed frames through the
actual MAC RTL. [RNR ACK component report](results/2026-10-18/rocev2-rnic-receive-write-rnr-ack-002.json).
The retained-WRITE RNR controller is still WIP: its latest test FAILS, and the
read-only observer does not turn that failure into a pass. No native RNR/retry
integration or new physical result is claimed. Successful AND failed reports
are retained. Original timing and the historical TX-padding source check still
fail; no test/default/clock/hardware gate has been relaxed for publication.

Progress165 completes matching profile8 native36 (894.628s build/max9.734s
cases), real-header kernel build10.843s, actual C callback202 cases and
95 unedited-native-CQ cases, with all170 old callback summaries identical.
The true zero-capacity RQ yields an8193-byte WRITE/Immediate WC; corrupted
full owners do not retire it. [2130-binding matched source audit](results/2026-10-18/rocev2-rnic-segmented-write-native-software-diagnostics-001.json).
Provider9/CQ-policy140800 checks remain successful. Linux/MMIO/pin/DMA
primitives and provider syscall/WC replies are MODELS; this is not live
kernel/native/provider or physical qualification. No jobs/install/default
changes. WRITE wire RNR/NAK/retry, full1MiB/multiSGE/live refs/cleanup,
original timing/physical and all11 remain.162–165 local after7234cab.

Progress164 adds a DISTINCT private WRITE software identity:131071/511/13/63,
profile8, preserving every older/default tuple. Only three native CSR feature
words change; full elaboration passes8.168s. A FRESH matching36-case native
build is LIVE, not yet runtime-qualified. Actual CQ-header predicate tests
pass140800 combinations with128000 old/unknown rows identical; only profile8
permits large flags3 WRITE notices. Real libibverbs/private-provider tests
pass all9 identities and zero-capacity RQ/WC/network-order Immediate cases.
[652-binding source-only audit](results/2026-10-18/rocev2-rnic-segmented-write-software-source-diagnostics-001.json).
The new kernel module builder rejects the OLD successful native tuple; real
module/callback/native-CQ/MR-lifetime coupling still requires matching gates.
No install/image/default change; this source work remains local after7234cab.

Progress163 completes the FRESH actual native run: all36 cases pass, including
incoming8193 WRITE/Immediate and every34 prior case with identical raw inputs
and summary oracles. Actual generated HLS/native PSN/shared MR/PTE/PCIe/
nonce/fence/sole ACK/MAC/whole CQ execute together; compile896.667s and
maximum9.534s/case retain the original1200s/30s bounds. [4366-binding audit](results/2026-10-18/rocev2-rnic-segmented-write-native-runtime-diagnostics-001.json).
The build is now TERMINAL, not still live as in the older checkpoint below.
Host/root/peer/PHY/PTP remain models; full1MiB/multiSGE, matched software,
real-peer recovery, partial-HLS cleanup, original timing and physical proof
remain. In particular, current profile7 still rejects flags3 WRITE notices
above4096 bytes: the new8193 native CQ is not yet a driver/provider feature.
No image/driver/default changes;162–163 remain local after7234cab.

Progress162 qualifies the actual native-only FIRST-header admission gate:
all512 opcode/state frames pass, including2560 blocked zero/unknown-gate
cycles and uninterrupted SECOND/body drain. [Header-gate runtime](results/2026-10-18/rocev2-rnic-native-write-header-gate-001.json).
A fresh actual native build now targets incoming8193 WRITE/Immediate PLUS
all34 unchanged old cases. [Fixture audit](results/2026-10-18/rocev2-rnic-segmented-write-native-fixture-diagnostics-001.json)
retains every old recipe and359 fatal checks; it is NOT native runtime proof.
The build is still running, combinational-path warnings are NOT waived, and
no new payload/runtime/timing/hardware pass is claimed. This work is local;
explicit publication7234cab covers157–161 below, not this later addition.

Publication update: this snapshot includes progress157–160 and the current
progress161 native integration sources, with successful AND failed reports.
Local/unpushed statements below describe earlier checkpoints. This remains
development work, not a hardware release or a complete RoCE implementation.

Progress161 inserts the checked-frame WRITE controller into the complete
native graph: the actual generated typed HLS, native expected-PSN commit,
shared MR/PTE/backend/physical nonce, sole RECV/WRITE ACK allocator and genuine
late-RQ/whole-CQ paths. Full native elaboration passes in8.225s without HLS
stubs, missing leaves or port-width waivers. [Compile-only evidence](results/2026-10-18/rocev2-rnic-segmented-write-native-elaboration-001.json).
This is NOT payload-runtime proof: all34 prior native cases and the new
WRITE/Immediate cases still need a fresh integrated run. The new native-only
first-header admission gate is also not separately runtime-qualified.
Full1MiB native transfers, matched software, recovery/partial-message cleanup,
original4ns timing and physical qualification remain open. No FPGA image,
driver, advertised capability, BIOS/fan/network setting or default is changed.

Progress160 adds the real checked-frame WRITE controller: frontend/MR,
packet memory, actual backend visibility, typed HLS/ACK and atomic frontend/
native-PSN-commit fanout. ALL14 bounded cases pass (max5.283s, original10s),
including8193 full bytes, real CRC/replay, genuine LAST-only680 RQ owner,
3 fences/ACKs and NO positive MAC SFD before actual visibility. The derived
classifier also passes all256 opcodes x2 states/512 full frames. [447-binding audit](results/2026-10-18/rocev2-rnic-segmented-write-controller-diagnostics-001.json).
HLS/native-PSN endpoint/descriptor-host/CQ boundaries remain MODELS; this
controller still needs placement in the complete native graph. No generated
WRITE payload/native runtime or timing qualification follows.157–160 local.

Progress159 selects the ENTIRE actual typed-WRITE generated HLS set in the
native graph and propagates424/456 owner/receipt ports through9 leaves.
Full native elaboration passes8.172s: same native HLS/MR/PTE/backend/nonce,
old3 MR arbiters plus ONE new client, no old/new generated-helper mixture.
An exact extracted native MR island passes8 short four-client contention/
same-tag/permission/range/key/invalidation cases. [1432-binding audit](results/2026-10-18/rocev2-rnic-write-native-gateway-diagnostics-001.json).
This is boundary elaboration/MR-island runtime, NOT integrated WRITE
frontend/backend/ACK/CQ or live generated-WRITE payload runtime. That
insertion, all34 old regressions and original timing still remain.
157–159 local/unpushed after public fbea645; no capability/default change.

Progress158 connects actual message-MR/late-RQ, typed packet memory/unpad,
physical nonce, paged backend/staging RAM/fence and shared ACK/MAC/DONE.
ALL14 short cases pass (max2.700s, original10s/4ns): ordinary/Immediate8193
bytes, every host byte/sentinel,5 scattered write descriptors,3 fences,
3 nonces and3 actual XGMII/FCS/SFD/CDC ACKs. Zero-capacity notification
still yields one8193-byte whole CQ ticket with a separate genuine RQ.
[398-binding scope/failure audit](results/2026-10-18/rocev2-rnic-remote-write-memory-diagnostics-001.json).
HLS traces/descriptor engine/host ordering/CQ consumers remain MODELS;
this is NOT complete native PCIe/TLP/live-generated-HLS/board proof.
Both157/158 stay local after public fbea645; original timing remains open.

Progress157 adds ONE shared RECV/WRITE ACK tag allocator. Distinct424 WRITE
and genuine620 RQ identities bind to the SAME actual ACK/EOF/SFD/1024-tail;
LAST Immediate publishes two independent proofs and cannot retire either
alone. ALL58 bounded cases and two unchanged legacy fixtures pass; five
mixed frames pass actual MAC FIFO/XGMII/FCS/SFD/receipt-CDC byte/tag checks
(max1.663s/case, original10s/4ns). [800-binding scope/failure audit](results/2026-10-18/rocev2-rnic-receive-write-ack-diagnostics-001.json).
HLS receipts/ACKs here replay checked actual C++ traces, NOT live generated
HLS/native DMA/CQ proof. Full integration and original timing remain open.
This addition is local/unpushed; publication fbea645 below covers154–156.

Publication update: this snapshot includes progress154–156 source and both
successful and failed reports. References below to local/unpushed work or
the previous public HEAD are historical. Native integration and original
timing qualification remain incomplete; this is not a hardware release.
`scripts/check.sh` still rejects the historical TX-padding source/test
identity mismatch; no overall-green claim is made.

Progress156 adds an actual HLS WRITE-packet execution path: protected424
identity -> actual parser/payload EOF/ACK-MSN/SAME PSN-table readback ->
distinct456 receipt. ALL87 C++ modes pass, every65 old mode/summary retained;
both WRITE modes check6 messages/284 full tokens through1MiB with unchanged
complete data/ACK/whole-RQ oracles (new4.642/4.732s, original30s bounds).
Actual owned Atomic service RTL and prior Immediate consumers also pass.
[1116-binding scope audit](results/2026-10-18/rocev2-rnic-segmented-write-owned-diagnostics-001.json).
Exact new RTL generation PASSES497.799s under original4ns/default1.08ns/
8QP/2000 and1500MiB/7200s gates; all old/new424/456/776 ports verify.
The15.571ns estimate still FAILS the original timing requirement.
[Generated-RTL provenance](results/2026-10-18/rocev2-rnic-segmented-write-owned-generated-diagnostics-001.json).
This is NOT native/physical success. Typed424 is never a fake posted620 RQ. Actual backend/
MAC/CQ coupling and safe message teardown still remain. Local/unpushed.

Progress155 adds the checked-frame WRITE frontend: actual IPv4/ICRC ->
parsed full-context MR authorization -> late-RQ -> registered owned replay.
ALL47 component cases pass, max2.077s under original10s/4ns/100000 cycles.
8193-byte WRITE/Immediate replay every input byte unchanged; RQ shortage
retries the same frame without duplicate replay. Bad ICRC never reaches MR;
an owner is required before replay and replay EOF before an execution proof.
Backend/HLS/MAC/CQ consumers remain MODELS; this is not full-native/DMA/
Linux/physical proof. The1MiB case is FIRST+safe cancellation, NOT full1MiB.
Host-only CRC constant memoization matches every448 original vendor mask /
55296 coefficients; hardware sources/gates stay unchanged.
[902-binding scope/failure audit](results/2026-10-18/rocev2-rnic-segmented-write-rx-front-diagnostics-001.json).
New work remains local/unpushed; original timing qualification stays open.

Progress154 connects the segmented-WRITE guard to the actual MR table and
late-notice RQ in46 four-state component cases (max0.122s), plus all62 old
queue modes on the new queue variant (max0.165s). Full-message/per-packet
checks, up to1MiB, distinct remote/RQ owners, late-RNR same-PSN/offset retry
and joint CQ retirement pass. An actual notice/head-VALID combinational
loop was fixed with a non-authorizing posted-head peek; every original
take/protocol/proof/CQ/retirement gate is byte-identical. Backend/HLS/MAC/
CQ and posted-admission producers remain models; this is NOT native or
physical proof. [Scope/failure audit](results/2026-10-18/rocev2-rnic-remote-write-mr-notice-diagnostics-001.json).
This addition is local/unpushed; prior publication/history follows.

This publication includes progress152/153 source and successful/failed
reports, plus the unfinished `rocev2_remote_write_message_guard` leaf.
That leaf passes syntax compilation only: its actual MR/RQ functional
tests and native integration have not run. No new hardware or timing
qualification is claimed. Uncommitted/unpushed descriptions below are
historical states, superseded by this explicit publication.

The new [incremental RNIC sources](rdma/rnic/README.md) include protected host
memory/queues, kernel/provider work, SEND/RECV/Immediate and Atomic candidates.
The [retained-source dispatcher native regression](results/2026-10-18/rocev2-rnic-segmented-executor-native-full-001.json)
passes all27 simulated cases, each under25s, including ordinary WRITE/SEND,
zero-length services, RQ/RNR, requester Atomic and permission checks. It uses
actual generated HLS, MR/PTE/DMA and XGMII/FCS/SFD/CDC/MAC/CQ RTL for the new
ordinary source cases; physical host/root/peer/PHY/PTP endpoints remain
models, and ordinary READ/SEND_IMM retain prior MAC-receipt models.

The [matched large-wire native regression](results/2026-10-18/rocev2-rnic-segmented-profile-native-full-001.json)
now passes all29 simulated cases, including8193-byte WRITE/SEND and all27
prior cases, each in18.05..26.61s. Its8191/13/15/31 RNC/SQC/RQC/CQC tuple matches
the private large-WR kernel cohort. The new cases exercise actual generated
HLS, scattered-page MR/PTE/DMA, board-faithful TX FIFO/CDC, XGMII/FCS/SFD/MAC
and one final whole-WR CQ, with independent wire/data/owner checks. Physical
host/root/peer/PHY/PTP endpoints remain models. Earlier failed runs and their
FIFO, PCIe3DW-model and pre-padded-LAST diagnoses are retained separately.
Up to1MiB remains HLS/component evidence, not this full-native runtime test.

A private RNC8191/CQC31/profile4 Linux source cohort builds against
the running kernel headers. Its [actual C posting/MR/SQ/CQ tests](results/2026-10-18/rocev2-rnic-segmented-kernel-post-003.json)
pass65 ASan/UBSan cases, including8193-byte/1MiB WRITE/SEND and all47 prior
cases, under explicit Linux/MMIO/DMA/completion models. This is not execution
inside Linux. A separate [actual kernel/native SQ-CQ integration test](results/2026-10-18/rocev2-rnic-segmented-kernel-native-cq-001.json)
passes65 cases:13 unedited native snapshot pairs plus52 explicit corrupt-copy
controls. Real C posting/coherent128-byte SQ/full-owner CQ/WC/ref retirement
execute under Linux/MMIO/DMA models. Native and C page tables remain separate;
this is not live kernel/RTL coupling. A private standard-provider cohort also
passes all five firmware profiles through real libibverbs serialization,
but actual Linux/provider/API/physical runtime, large receive/READ/Immediate
and multi-SGE remain incomplete. No module is installed/loaded; defaults and
`IB_ATOMIC_NONE` are unchanged.

A new private protected segmented READ-response RX candidate now passes
[all17 methods/60 component cases](results/2026-10-18/rocev2-rnic-segmented-read-response-002.json),
including59 four-state cases and an explicit1MiB/256-packet two-state case.
The first failed suite and its diagnostic evidence are preserved separately.
A separate true segmented READ HLS candidate now passes its
[actual C++ consumer tests](results/2026-10-18/rocev2-rnic-segmented-read-hls-003.json):
four whole READs4097 bytes..1MiB,278 response packets, stored replays, prior
regressions and nine negative cases. Its first failed run is preserved; the
correction distinguishes validated nonterminal READ timer progress from final
completion. Actual owned Atomic RTL-service/Immediate compatibility also
passes. [New HLS generation](results/2026-10-18/rocev2-rnic-segmented-read-generated-hls-001.json)
and exact generated-RTL elaboration pass, but its13.885ns estimate fails the
original4ns/default1.08ns conditions; no generated-RTL runtime pass is claimed.
The previous/default8191/31 profile keeps READ4096. A separately named
experimental16383/63 candidate below now admits larger READs, but actual
end-to-end native DMA/whole-WR completion and kernel/provider support for
that profile remain unverified. See
[exact evidence and limits](docs/ROCEV2_ATOMIC.md).

A new retained-owner READ memory controller passes35 four-state component
cases, including1MiB/256 fragments. A separate
[actual HLS C++ output-snapshot integration test](results/2026-10-18/rocev2-rnic-segmented-read-dma-hls-001.json)
passes four whole READs/278 fragments through the real origin router, bounded
unpad and executor RTL. Placement, backend visibility/status and CQ are models;
this is not live HLS/native DMA, generated-RTL runtime or physical proof.
The new READ memory selection is now wired into a separate complete native
hierarchy with the actual new HLS and common MR/PTE/physical-nonce/backend
ports. New/old route tests pass17 cases and whole-graph elaboration passes.
This is still compile-only native evidence; that earlier memory-only cohort
keeps READ4096 pending the separate profile/runtime work below.

The experimental expected-remote-MSN tracker now passes
[12 component cases](results/2026-10-18/rocev2-rnic-expected-remote-msn-007.json)
using genuine SQC cookie/epoch/PD lookups. Two genuinely allocated QPs retain
independent MSN history without route reconfiguration. Accepted-QP/SQC/MSN
wiring also passes [complete-native elaboration](results/2026-10-18/rocev2-rnic-expected-remote-msn-native-elaboration-002.json).
The component's route/WR/TX/CQ endpoints remain models; native evidence is
compile-only, not wire/MSN interoperability. Fresh remote RC peers are required;
its original8191/31 cohort keeps READ4096 and failed evidence is preserved.

The separate READ RX/MSN/memory/whole-WR lifetime graph is now connected and
passes [complete-native elaboration](results/2026-10-18/rocev2-rnic-segmented-read-lifetime-native-elaboration-001.json).
[Lifetime component tests](results/2026-10-18/rocev2-rnic-segmented-read-lifetime-002.json)
pass29 cases, including19 READ controls and all10 original WRITE/SEND cases.
One READ request retains its replay cache through FIRST/MIDDLE and joins
LAST, final HLS ACK/whole receipt, aggregate memory and actual MAC ownership
before CQ. RX/HLS/memory/CQ/MAC-pin endpoints are modeled in these component
tests;1MiB READ means256 modeled response events, not actual native payload
runtime. That original8191/31 cohort keeps READ4096; defaults are unchanged.

A distinct experimental RNC16383/CQC63 source profile now opens READ admission
up to1MiB through checked SQ/MR/HLS-SQ/CQ gates. Its actual C128 codec passes20
methods; real local-MR admission26 cases, HLS-SQ staging21 cases and register/
CQ27 cases pass. [Complete-native elaboration](results/2026-10-18/rocev2-rnic-segmented-read-profile-native-elaboration-001.json)
passes with the exact RX/MSN/memory/lifetime/HLS graph. These are component
runtime plus native COMPILE results, not execution of a genuinely fetched
large READ through native RX/DMA/host visibility/CQ. No installed/default
driver/provider selects this profile.

The [first full-runtime attempt](results/2026-10-18/rocev2-rnic-segmented-read-native-full-002.json)
now compiles the actual new graph successfully, but **fails during QP setup,
before a fetched READ/data transfer** (`main native RNIC fault 00`). The new
runner plans one8193-byte READ plus all29 previous cases; only the first READ
case was attempted, and none passed in this batch. The failure, exact hashes
and [audit](results/2026-10-18/rocev2-rnic-segmented-read-native-diagnostics-002.json)
are retained. At that historical checkpoint the root cause was unconfirmed;
the route correction and subsequent native success are recorded below.

A separate route-observer correction now passes six short real-controller
cases: the old fault is reproduced, while the corrected observer retains the
peer/IP route across a PSN-only QP_TX command. Invalid commands and stalled
acceptance remain checked. [Complete-native elaboration](results/2026-10-18/rocev2-rnic-segmented-read-route-native-elaboration-001.json)
passes with only two observer lines changed; all original gates remain.
The [fresh corrected native build](results/2026-10-18/rocev2-rnic-segmented-read-route-native-full-001.json)
passes compilation and reaches genuine SQ fetch, actual READ request emission
and the first4096-byte paged-write/fence descriptors, but times out at the
unchanged30s limit. A separate same-binary diagnostic reaches cycle24000 with
no fault,33 write TLPs and no second fragment's physical write descriptor: completion and absence
of a functional stall are NOT proved. The later optimized -O1 run reaches the
original cycle deadline in9.436s and confirms a real stall: first fragment
completes, but the second waits for2176 payload bytes while the next command
is blocked. Neither historical batch proves full READ/CQ or the old29 cases;
the subsequent command-queue batch below does.

A new owner-checked two-command metadata queue breaks that
command/data dependency without changing serial DMA/status/fence/CQ ownership.
[Component tests](results/2026-10-18/rocev2-rnic-segmented-read-command-queue-001.json)
pass23 cases, retaining all17 prior cases, with explicitly modeled HLS/backend/
CQ endpoints. The [fresh complete-native run](results/2026-10-18/rocev2-rnic-segmented-read-command-queue-native-full-001.json)
now PASSES all30 cases: new8193-byte READ plus all29 old cases. New READ uses
actual generated HLS/SQ/MR/PTE/protected RX/MSN/DMA/shared nonce/status/fence/
board-MAC/FCS/SFD/CDC/CQ RTL and passes in6.078s, including every host byte and
one whole-owner CQ. All cases take4.175..6.279s under the unchanged30s limit;
[audit](results/2026-10-18/rocev2-rnic-segmented-read-command-queue-native-diagnostics-001.json)
verifies1665 bindings. Physical host/root/peer/PHY/PTP remain MODELS; old ordinary
READ/Immediate cases retain their old MAC-pin completion models. This is not
Linux/physical/timing qualification or a native1MiB READ test. Separate matched
16383/63 kernel/provider support now has a separate source cohort below;
old/default8191/31 keeps READ4096.

New explicit software profile5 binds exact16383/63/SQC13/RQC15/stride128.
Its actual kernel source builds against running headers; actual WR/SQ/MR/CQ
C passes90 modeled-boundary cases (all65 old retained), and70 cases consume
unedited native SQ/CQ captures, including8193 READ, with exact posted bytes/
MR retirement. The actual installed libibverbs/private provider passes all
six identities and4097/8193/1MiB READ chains under fake-fd/WC models.
[Software audit](results/2026-10-18/rocev2-rnic-segmented-read-software-diagnostics-001.json)
verifies626 new successful bindings and preserves failed fixtures/preimages.
This is not installed/live Linux/RTL or physical proof. Single SGE and4KiB
Immediate/RQ remain; native1MiB READ and original timing remain unqualified.

A further separate RNC32767/CQC127 candidate now PASSES actual8193-byte
segmented SEND/WRITE Immediate and ALL30 prior native cases:32 total, each
4.125..6.430s. Immediate appears only on LAST; real SQ/MR/PTE/generated HLS/
DMA/shared nonce/status/board-MAC-FCS-SFD-CDC/CQ and all source/sentinel bytes
are checked. Physical host/root/peer/PHY/PTP remain MODELS; native1MiB is not
tested. Separate matched source-only kernel/profile6/provider builds and
passes134 standard-C callback cases,80 untouched native-SQ/CQ snapshot cases
and all7 provider identities with modeled Linux/syscall boundaries.
[Current audit and failures](results/2026-10-18/rocev2-rnic-segmented-immediate-native-software-diagnostics-001.json)
verify2586 fresh bindings. This is not live Linux/RTL or physical/timing
qualification. Source/C++/API models allow1MiB; incoming RQ stays4KiB/single
SGE, old/default/profile5 stay unchanged. The earlier
[source/component audit](results/2026-10-18/rocev2-rnic-segmented-immediate-diagnostics-001.json)
is retained separately, not relabeled as a native-runtime result.

This is a **work-in-progress source snapshot**, separate from the earlier
hardware-tested READ/WRITE images. Its latest HLS estimate13.885ns misses the original
4ns target; no new FPGA image, installation or hardware claim is published.

A separate incoming SEND/Immediate HLS candidate now passes44 C++ modes
(all21 previous retained), testing full payloads through1MiB. Actual message
RQ/ACK/CQC component coupling also passes8193-byte/3-packet ACK lifetimes and
one CQ publication/full AXI snapshot; queue units pass48 cases. HLS/MR/DMA/
PHY/host boundaries remain models in those RTL component executions. The
SAME new full HLS synthesis is still running; the new native source graph's
syntax check ignores missing leaves and is NOT complete native elaboration.
[Evidence and remaining work](results/2026-10-18/rocev2-rnic-receive-message-native-components-diagnostics-001.json).
Existing native/software profile6 incoming RQ4096/defaults are unchanged;
actual new generated-HLS/MR/PTE/DMA/native/standard API/timing work remains.

Progress149 subsequently generates actual source007 RTL in 399.510 seconds
and passes complete application-native elaboration with every leaf present,
one shared MR/PTE/HLS/message-RQ and the actual 776-bit whole output. Four
additional actual PCIe-DMA-to-MR-to-RQ cases pass (maximum 0.367 seconds),
with no descriptor/status/RAM/MR substitute. Physical host/root/link/config
and the error sink remain models; no received-payload/HLS/MAC/CQ runtime is
inferred from descriptor posting. The HLS estimate is 15.571 ns: original
4 ns timing is NOT met. A fresh new-graph build for all 32 old native cases
is running; new large incoming native transfer and matched software remain
unproved. [Generated/native-connection audit](results/2026-10-18/rocev2-rnic-segmented-receive-generated-diagnostics-001.json).

Progress150 completes all 32 exact old native cases on that new graph
(4.476..6.831 seconds each, fresh compile642.135s). The separate original
source004 HLS run times out at its unchanged7200s limit; its child processes
subsequently exit naturally. Failures/logs stay intact. New whole-native
8193-byte incoming SEND/Immediate tests on one8194-byte RQ, with genuine
three packet/fence/ACK-MAC lives and one whole CQ, are now building003.
Its actual full bench elaborates without width/missing-leaf waivers, but
no new incoming payload/runtime pass is claimed yet. Failed001 anchor and
002 observer-port binding attempts are retained with exact preimages.
[Native old32/timeout/failure audit](results/2026-10-18/rocev2-rnic-segmented-receive-native-regressions-diagnostics-001.json).

Publication after progress151 records that full-native003 compiled but
FAILED at the original second-packet deadline. Read-only inspection of the
unchanged DUT objects identified the raw reference entrance blocking a held
receive group's continuation. A separate derived fix changes only that
entrance; pending ownership, MR, HLS, MAC and whole-CQ checks stay intact.
[Reference gate tests](results/2026-10-18/rocev2-rnic-receive-continuation-gate-001.json)
pass nine current cases plus the expected old-gate negative control.
[Complete native elaboration002](results/2026-10-18/rocev2-rnic-segmented-receive-native-elaboration-002.json)
passes with actual generated HLS and no missing-leaf/width waivers.
The corrected full-native34-case run has NOT started; new incoming8193
runtime, matched software, original4ns timing and physical proof remain
unverified. No hardware or installed/default profile is changed. Earlier
progress149/150 build-state descriptions above are historical snapshots.

Progress152 now PASSES all34 fresh corrected-graph native cases, including
8193-byte incoming SEND/Immediate on one8194-byte RQ, three real packet/MR/
DMA/fence/ACK-MAC releases and exactly one whole HLS/CQ/host ACK. Compile
798.354s; new cases8.534/8.584s, original1200s/30s limits unchanged. Separate
exact65535/255/13/31/profile7 kernel source builds against running headers
and passes170 actual C callback model cases (all134 old retained),2442 IO
identity/geometry cases and90 unedited native SQ/RQ/CQ snapshot cases. The
private provider passes all8 identities and new standard RECV marshalling.
[Native/software scope audit](results/2026-10-18/rocev2-rnic-segmented-receive-native-software-diagnostics-001.json).
Linux/MMIO/pins/DMA/completion boundaries are models; snapshots are separate
executions, not live Linux/RTL or matching physical-page-table coupling.
Default/installed profile6 incoming4096 and IB_ATOMIC_NONE are unchanged.
Native1MiB, multi-SGE, segmented WRITE Immediate, recovery/interop and original
4ns full-board timing/physical work remain open. Source004 timeout, full003
failure and the first callback-vector error stay recorded with exact preimages.
This progress152 addition is local/uncommitted, with no automatic push.

Progress153 adds a separate segmented incoming WRITE/WRITE Immediate HLS
source and late-notification RQ component. Actual C++ passes65 modes (all44
old retained), including6 messages/284 packets per new operation through1MiB,
independent complete data/ACK oracles, LAST-only MSN, PSN wrap, distinct RETH
target and late RQ capacity0/1/17/etc. The RQ component passes62 cases (all48
old retained), keeping separate320-bit remote and620-bit posted identities,
whole bytes rather than LAST bytes/capacity, and remote-retirement backpressure.
[Scope/failure audit](results/2026-10-18/rocev2-rnic-segmented-write-receive-diagnostics-001.json).
Peer/memory/posted-RQ boundaries and the component's trusted remote-MR/HLS/
MAC/visibility producers are MODELS. These separate tests are NOT connected
native proof; the new source has no generated RTL, native MR/DMA/CQ coupling,
matched software or physical qualification. All old/default sources and
original timing gates remain. No automatic commit/push.

The current source checkpoint also adds a 1 MiB posted-RECV codec and a
correctly typed `ib_recv_wr` adapter: 37 codec methods, 78 admission/staging
cases, four actual MR-to-message-RQ handoff cases, and a real-kernel-header
adapter build pass. These are not installed callbacks or a matched new
driver/provider profile. A separate balanced KEEP checker passes 103,665
finite old/new behavioral comparisons, all 44 C++ modes and unchanged
Atomic/Immediate compatibility. Candidate 005 is rejected for narrowing
short-beat acceptance; candidate 006 compile failures are retained, not
relabeled by candidate 007's success. No new synthesis/timing benefit is
claimed for 007. Original source004 synthesis was still active at
2026-10-21 09:16 UTC; it was not stopped or restarted for publication.
[Publication integrity and scope](results/2026-10-18/rocev2-rnic-segmented-receive-publication-diagnostics-001.json).
The recorded-data part of `bash scripts/check.sh` currently detects a stale
historical `rocev2_tx_padding.v` SHA after adding44-byte SEND support. The old
evidence and strict check are retained, not relabeled or waived. See
[current scope and limitations](docs/ROCEV2_RNIC_PROGRESS.md).
The focused Atomic RTL suite passes21 methods (73 internal simulations). A broader RNIC suite is not
green: native MAC-lifetime and QP-TX cases reported errors/failure, and the
remaining full-suite run was stopped. This snapshot is not a passing release
or a claim that every older test matches the current development profile.

The two throughput measurements were **sequential**, not simultaneous full
duplex, using MTU 9000, four TCP streams and 20 measured seconds per direction.
TCP retransmissions occurred. MTU 1500 has a substantial reverse-direction
performance limitation. See [the complete results and caveats](docs/RESULTS.md).

The new RoCE measurements use a different clean-RTL image and finite tests,
not the historical TCP/ECO image. See [native WRITE evidence](results/2026-10-18/rocev2-native-003.json)
and [current milestones](docs/ROCEV2_PROGRESS.md). No software RXE endpoint
stands in for the FPGA in these native tests. Do not treat a single short
measurement as sustained-load qualification. Separate finite
[ACK-loss/watchdog/recovery evidence](results/2026-10-18/rocev2-native-retry-recovery-003.json)
covers controlled faults, not arbitrary network failures or production reliability.

The newer combined READ/WRITE image has its own [native evidence](results/2026-10-18/rocev2-rw-native-001.json)
and [READ results/use guide](docs/ROCEV2_READ_RESULTS.md):8READ cases, including
65536bytes x4 (all256KiB),4096operations and error/CLEAR recovery, plus2WRITE
regressions, all-byte zero mismatches. These are finite functional tests,
not a new throughput measurement or a repeat of WRITE003's ACK-loss tests.

## What this project adds

- Native 25G configuration for this board's fixed **156.25 MHz** reference,
  a 25.78125 Gbaud GTY link and fractional QPLL feedback of 82.5.
- A six-bit, independent two-stage synchronization fix for PHY-status signals
  entering VIO's PCIe clock domain. Functional Ethernet paths are not waived.
- Vivado 2025.2 PCIe class-code configuration and implementation-flow fixes.
- Timing-oriented build recipes, guarded output gates, and historical ECO
  helpers used during bring-up.
- A Linux 6.17 mqnic compatibility patch, explicit test configuration and
  read-only JTAG temperature diagnostics.
- Scoped RoCEv2 READ/WRITE endpoints, protected capture RAM, packet-integrity/control/guard integration,
  measured hardware results and an explicit remaining-work roadmap.

The Ethernet MAC/PCS, PCIe DMA and NIC architecture remain **Corundum**.
The initial board adaptation comes from **quake0day's AS02MC04 port**, with
board constraints referenced from **FPGA Ninja / Taxi**. This is a board port
and engineering validation, not a new Ethernet protocol implementation.

## Get the source and check it

```bash
git clone --recurse-submodules https://github.com/jyohukuchan/Alibaba-XCKU3P-FPGA-25G-and-RDMA.git
cd Alibaba-XCKU3P-FPGA-25G-and-RDMA
bash scripts/check.sh
```

Dependencies are pinned to the revisions in [third-party notices](THIRD_PARTY_NOTICES.md).
Checks need Git, Bash, Tcl and jq, but do not need Vivado or access hardware.

To build, install Vivado **Standard 2025.2** with Kintex UltraScale+ device
support (Lab Edition cannot synthesize), then run:

```bash
VIVADO_BIN=/path/to/Vivado/2025.2/bin/vivado bash fpga/build_25g.sh
```

This is **build-only**. It does not load a driver, program JTAG, write flash,
change networking or reset PCIe. See [build status and instructions](docs/BUILD.md)
before relying on a new image. Prebuilt vendor-generated binaries are not
distributed in this initial source publication.
The RoCE-enabled build additionally needs the pinned generated HLS profile;
see [RoCE build and test instructions](rdma/README.md).
The separate combined READ/WRITE build is documented in [rdma/read](rdma/read/README.md);
the original default RoCE build remains the WRITE-only profile.

## Hardware and safety

Read [hardware and bring-up notes](docs/HARDWARE.md) before attempting programming.
Identify your exact FPGA, adapter and PCIe bridge; never copy another host's
PCIe addresses. Keep a known-good rollback image and adequate direct airflow.

The recorded load test stayed below approximately **55°C** with the test
workstation's fans set high. This is not a thermal guarantee for another host
or design. The optional temperature reader requires an explicitly selected
JTAG adapter serial number. Never use it concurrently with programming.
The later finite native 64 MiB RoCE case, with BIOS Medium retained, sampled
**60.32..60.62°C**; it is not a sustained-traffic thermal test.

Do **not** run the dependency port's flash targets or DRP-tuning script
unreviewed: they contain assumptions that do not match every board/host.

## Layout

- `fpga/`: board RTL, XDC, 25G configuration and offline build/ECO Tcl.
- `external/`: pinned upstream Git submodules; not a fork of their ownership.
- `patches/`: mqnic Linux compatibility patch.
- `scripts/`: source checks and opt-in host test/temperature helpers.
- `rdma/`: experimental endpoint/HLS integration, native peer/controller and tests.
- `results/YYYY-MM-DD/`: scoped measurement/provenance JSON and report excerpts.
- `docs/`: build, hardware, CDC, results and RDMA roadmap.

An optional [traffic test guide](docs/TESTING.md) explains the explicit opt-in,
device selection and thermal monitoring required for the adapted helper.

## License

Original additions use **BSD-2-Clause-Views**. Preserve upstream file notices
and the MIT board-constraint notices. See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), including the selected HLS
transport's own license. Future dependencies require their own review. This is community research without any
vendor affiliation or production-readiness guarantee.
