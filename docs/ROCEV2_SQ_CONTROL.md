# Privileged SQ control and actual shared DMA (not native RDMA)

## Later native RQC1 receive cancellation (milestone070)

At milestone072 the previously pending READ/WRITE/SEND regression also
passes on current RTL with actual generated HLS (about11seconds per case).
Its unedited CQ snapshots and software/native WQE bytes pass actual kernel C
for all three operations. Session22773 is terminal. No new physical/board,
running IB-core/provider or parent BAR-lifetime qualification is inferred;
the broad goal remains open. See progress072 for current evidence.

Milestone071 now exercises this cancellation in the full actual-generated
native graph in ordinary and initial-RNR cases (<16seconds each). Two SEND/
RECV pairs complete before a third real coherent RECV is cancelled without
a packet. The physical root-complex model withholds its accepted read's TX
sequence/completion; the actual PCIe/parent guard, not a substituted drain
wire, blocks early cancellation. The real full RQC reply and third WQE are
captured and consumed unedited by actual kernel C together with the four
original native CQ snapshots. Kernel DMA-allocator/controller/pin boundaries
remain models. These are not physical bus/kernel/provider lifetime or board
timing results. The separate READ/WRITE/SEND regression build is active at
checkpoint071; its saved process must be polled rather than duplicated.

The separate native receive mailbox at0x405000 keeps ID `RQC1`, ABI1 and the
same15-word snapshot/reply layout. Optional `RECV_CANCEL_ENABLE` defaults0
and requires the full separate native SQ/RQ profile. Only this RQC1 instance
advertises features3 (base1 plus cancellation bit2). SQC1 remains features1;
there is no new SEND/Atomic capability or change to the RNC511 signature.
The original feature1 contract below remains unchanged for old profiles.

Command4 uses the complete existing QPN/nonzero PD/epoch/cookie/DMA64/depth,
the exact final producer and nonzero batch nonce. Owner/layout validation
precedes any cancellation. The immutable request blocks new coherent fetch
selection and new receive takes; already accepted fetch/admission continues
to its real posted-owner handoff. Only after those genuine guards drain may
the posted store reclaim matching QPN/PD/epoch entries. A held receive is
never erased: placement, HLS receipt, ACK/MAC and native CQ retirement must
finish normally. Missing parent/memory drain or unknown owner fields cannot
authorize the store handshake.

After posted-store cancellation, the actual fetcher executes its separate
RQ-only internal command0: rechecks epoch/PD/base/depth/final producer,
parent DMA and every downstream guard, then retires the unfetched tail.
The mailbox requires that actual final-producer reply and captured
parent/fetch/work/wire/completion drain before returning flags `0x3f`.
Bit `0x20` distinguishes this explicit cancellation from ordinary retire's
`0x1f`; ordinary fetch consumer advancement is still NOT a WR completion.
The blocker remains through the exact mailbox reply ACK.

Linux accepts command4 only after reading actual RQC1/features3. File close
first abandons WC/user-notification delivery, then this real cancellation
adapter matches the full snapshot, producer, nonce and flags63. Only that
new certificate authorizes releasing pending abandoned RECV work/MR refs;
it does not manufacture native CQEs or success WCs. Coherent ring storage
still needs ordinary paired close and real QP/SQ retirement. A timeout or
corrupt reply retains the batch nonce, all memory and command ownership;
exact later reconciliation remains possible while genuine CQ events progress.

Evidence is source/offline: five actual RQC/fetch/posted-store RTL cases,
13 actual-source kernel bootstrap/file-close boundary-model cases, a W=1
running-header/pinned-parent build and actual-generated-HLS hierarchy
elaboration. The RTL cluster models the descriptor backend, admission/MR
context formation and external drain; the kernel model does not execute
physical RTL or actual IB core. No full new generated-native cancellation
simulation, physical timing/CDC/runtime, arbitrary requester abort, forced
core failure or surprise-unplug/BAR-lifetime readiness is claimed. No image
or module was installed, loaded or programmed.

## Original control-only composition

`rocev2_sq_control_regs.v` adds an actual AXI-Lite32 SQ configuration/
publication mailbox. `rocev2_sq_controlled_dma.v` connects it to the actual
existing SQ/paged/RAM/tag-router composition. The wrapper has NO external raw
SQ configuration port; accepted AXI commands drive the real fetch controller.
This is source integration, not a registered Linux driver/provider, native
parent mapping, local WQE/MR execution, completion queue or deployed firmware.

The mailbox is intended for kernel-owned control. AXI PROT is not an
authentication mechanism; a future native driver must restrict this BAR and
publish only DMA addresses from its actual coherent allocator. It must never
expose raw DMA configuration directly to untrusted users. The current native
endpoint/loaded image does NOT map this mailbox. The NEW source/offline
`rocev2_native_sq_endpoint` maps it at0x402000; this is not a deployed-image
or standard-verbs capability claim. Raw PTE configuration and already-authorized
payload commands remain trusted caller inputs of the combined DMA wrapper.

## ABI and ownership

The shared ABI header is `rdma/rnic/kernel/sq_regs.h`; ID `SQC1`/`0x53514331`,
version `0x00010000`, address width12. Feature1 means SQ control ONLY, not CQ,
standard verbs or RNIC capability. Corundum's actual AW/W/R/B adapter handles
independent channels and held responses. It ties BRESP to OKAY even on its
register timeout: B completion alone NEVER proves publication. Software must
check sticky MMIO status and the exact owned semantic reply.

Offsets0x40..0x78hold15staging words. Doorbell0x10with full strobes snapshots
ALL words atomically. Staging edits cannot alter an offered command. A new
nonzero32-bit sequence must equal previous+1; exhaustion refuses wrap. The
same complete snapshot is retained in0x100..0x138until exact-sequence ACK
at0x14. Additional reply error/flags/consumer64are0x13c/0x140/0x144..0x148.

| Words | Field | Validation |
| --- | --- | --- |
|0|Sequence|Nonzero, exact next value, no wrap; bell data must match|
|1|Command|1allocate,2publish,3retire; full reserved bits rejected|
|2..3|QPN,PD|Full32-bit checked QPN<8,PD<=65535before narrowing|
|4..5|Epoch64|Nonzero; allocation strictly newer than retained watermark|
|6..7|Cookie64|Nonzero complete software ownership identity|
|8..9|DMA64|Aligned64; exact committed allocation address on post/retire|
|10|log_depth|1..8,2..256records of64bytes; exclusive end2^64legal|
|11..12|Producer64|Allocate0; post exactly previous+1; retire exact final producer|
|13..14|Retire nonce64|0for allocate/post, nonzero complete fresh caller nonce for retire|

Cookie/epoch/PD/DMA/depth are recorded only after the real fetch controller
accepts the allocation and returns matching full QPN/epoch/empty-consumer
evidence. Every later publish/retire must match that complete owner/layout.
Failed allocation cannot accidentally publish an active software owner.
Known semantic errors return error/flags0without advancing the owner producer.
The actual fetch controller also checks ring capacity, monotonic producer,
queue halt, epoch, selected-operation and parent/downstream ownership.

Allocation flags7describe actual active/empty/parent-safe acceptance. Retirement
flags31require a real successful fetch invalidation, actual parent/fetch/
work/wire/completion guard inputs clear at admission, matching full response
context AND final fetch consumer equal to the submitted final producer.
The wrapper ORs work|wire|completion guards into the actual fetcher's downstream
guard, so a guard that rises AFTER snapshot but before acceptance also rejects
retirement. Epoch watermarks remain after successful retirement.

Fetch invalidation can cancel an unfetched tail, but that is NOT RDMA WR
completion. If its returned consumer differs from final producer, the CSR
returns uncertain128/flags0, marks the owner tainted/fatal and retains ownership.
It MUST NOT allow kernel ring/MR refs to be freed on that invalidation alone.
Fetch results, consumer movement, semantic ACK and parser recovery are not
CQE/wire/host-page lifetime proof.

Unknown response errors, wrong QPN/epoch, unsolicited responses or endpoint
fault cause sticky fatal/taint with no safe proof. Accepted configuration
offers remain stable. Busy/duplicate/wrong-sequence/partial bells, wrong/empty
ACKs and unknown/unaligned accesses set sticky MMIO_ERROR without overwriting
the existing command or response. CLEAR_ERROR0x18requires write1/full strobes
at IDLE and never clears fatal, cancels DMA or establishes a new key epoch.
There is no reset CSR. Fresh source-bound abort/flush/epoch recovery is still
required, not considered complete through permanent quarantine.

## Evidence and limits

Current `rocev2-rnic-sq-control-unit-005.json` passes9four-state methods/
36simulations through actual CSR, actual AW/W adapter and actual SQ controller.
The backend/data/status and parent/work/wire/CQ guards are EXPLICIT MODELS.
It covers normal allocate/post/fetch/held-result/retire, immutable snapshots,
full ownership/reserved/unknown shape rejection, all early and late lifetime
guards, response corruption, sequence exhaustion, DMA64end, actual ring-full
error and unsafe unfetched-tail cancellation refusal. No internal forcing.
Unit001was an earlier28-case pass;002failed only a harness assumption that
unknown-address timeout would return AXI SLVERR. The actual pinned adapter
always returns OKAY, so003asserts that behavior AND sticky-error/no mutation;
neither erroneous002evidence nor the original adapter was overwritten. Later
004adds a complete staging-word knownness check and four DMA/nonce/epoch/
producer-X cases;003is an intermediate32-case pass. Fresh005retains all36
cases after the fetcher's new per-QP queue_pending output and header update.

`probe_sq_controlled_pcie.py` uses the actual production wrapper, real CSR/
SQ/paged/tag-router/RAM, BOTH native-shaped muxes, actual generic PCIe engine
and actual parent proof RTL. It reuses the previous shared probe's exact
byte/range/sentinel/route/ordering assertions. SQ allocate, two single-WR
producer increments and final retirement travel ONLY through AXI, with all
15reply words/full nonce/consumer/flags and exact ACK checked.

Current004passes4CSR commands,7physical descriptors/restored statuses,
two actual C/UBSan-encoded64-byte SQ records,65-byte scattered payload WRITE
and READ, a visibility fence,128delayed write-sequence cycles,16319host
sentinels and128unchanged ring bytes, with both clients concurrently active.
The physical root complex/host/hard-IP/link, privileged software MMIO agent,
trusted PTE/authorized payload source and zero downstream work/wire/CQ owners
are MODELS. No constant parent proof or descriptor/status/RAM engine agent.
No real kernel allocation/pins/MMIO/native driver or CQ publication occurs.
Earlier001is historical after the shared router's registered RAM-response
boundary correction;002is historical after descriptor proposal pipelining.
Fresh003retains every original byte/guard/proof assertion, with6additional
clocks of combined activity from registered descriptor authorization;004
rechecks them after the new fetch ownership output. Both finish in1658cycles.

## Actual native SQ mapping and shared MR (progress027)

The subsequent progress028optional local-memory port uses the SAME existing
native PTE/payload backend through a real ownership arbiter. See
`ROCEV2_SHARED_PAYLOAD.md`: actual SQ/MR-to-scattered-memory tests pass, but
the local transport/executor/final CQ are explicitly MODELS. This does not
advertise standard verbs or change feature1/control-only meaning below.

The new `rocev2_native_sq_endpoint` places the SAME controller in a private
outer AXI crossbar at0x402000/4KiB. Existing native windows retain their full
addresses/decoder;0x403000 remains DECERR. It selects ONE original native
endpoint/MR/PTE/paged payload backend, ONE coherent SQ fetch backend, and the
existing full16-bit-tag router before the common app DMA port. No raw SQ/MR/
PTE/result bypass or copied registration table is exposed.

Fetched64-byte records and trusted full QPN/PD/epoch/sequence/tag enter
`rocev2_sq_wqe_admission`, which uses the actual native local port of the SAME
MR table. Failed DMA bytes never become WQEs: exact DMA error/context remain,
all authority fields are zero and descriptor_available is false. WR_ID0then
means unavailable, not an actual completed WR_ID; a future CQ publisher must
use the trusted SQ shadow/sequence. Unknown descriptor/context fields reject
or fault closed without aliasing. This is authorization, NOT local payload
execution, transport submission, CQ completion or a kernel/provider binding.

Raw ring/fetch ownership is deliberately distinct from an MR lease. A raw
result waiting behind native MR management must not block that management.
The bridge begins MR protection at the real admission offer/handoff; actual
executor/wire/CQ guards must continue it without a gap. Raw queue_pending,
fetch/bridge/downstream owners separately veto Ethernet route COMMIT and SQ
retirement. Fetch-consumer advancement is NEVER WR completion.

`sq-admission-unit-002` passes5methods/16four-state simulations, including
all15nonzero DMA errors after a successful record (no stale data), full-width
protection, management priority and unknown descriptor/context cases.
`native-sq-unit-004` passes2actual-control/SQ/MR/RAM/router/mux/generic-PCIe/
parent-guard cases with an EXPLICIT HLS stub. Each checks128coherent ring
bytes and one64-byte SQ fetch; downstream executor/CQ lifetime remains a
MODEL. Actual generated-HLS `native-sq-priority-hls-001` independently passes
the inflight-fetch/revoke/stale-key denial case in97.03seconds: one actual
SQ READ, four owned CSR commands, early retire error35then fresh successful
flags31. No native payload execution/CQE or Linux allocation is claimed.

`native-sq-forward-hls-001` reached the120-second Icarus limit before the full
case finished; its partial log is retained and is NOT a pass. The additional
`native-sq-forward-compiled-001` uses the established Verilator5.036 helper:
compilation is separately bounded600seconds, execution30seconds. The exact
original incoming5operation/bytes/range/PSN/ICRC/AETH/fence/ownership and
ordinary-host assertions remain, plus one real64-byte SQ READ and native
authorization/handoff/retire checks. It passes in11.67seconds/32256cycles,
9READ/4WRITE TLPs,9read completions,2fences,130WRITE/195READ payload bytes,
256delayed write-TX-sequence cycles and128unchanged ring bytes. Both the
original138-file HLS hash and140-file delivery hash remain unchanged.
This is additional TWO-STATE evidence, not a replacement four-state/X/Z/reset
or physical qualification. Exact Icarus hierarchy is also independently
elaborated; one each native/SQ/MR/router/backend/parent-guard is checked.

The new top is not yet selected by the actual mqnic app/board parent. Kernel
headers define the new source-only offset without claiming the deployed
image implements it. Old shared-DMA OOC frozen files remain intact, but the
new fetch output changes two original source identities; those failed timing
reports are historical, not physical qualification of this top.

The subsequent `sq_io.c`/`sq_hw.c` now supplies actual kernel SQC1 callbacks
for the real `sq.c` library, requiring a real CQ publisher; see
`ROCEV2_SQ_KERNEL_MMIO.md`. Compilation and explicit C-model execution are
NOT native runtime BAR access or standard post_send registration. Actual
bus/ib_device/native controller/parent integration, shared
local/incoming MR/PTE execution, actual per-WR wire/fence/CQ lifetime, safe
abort/flush, provider/verbs and the remaining operations/reliability still
need implementation. Neither these tests nor the separate shared-DMA OOC
analysis replaces full resulting-image physical/conditional CDC/native gates.
No programming, module load, network/fan/BIOS change or reboot was performed.
