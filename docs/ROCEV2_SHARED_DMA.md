# Shared SQ/paged-payload DMA building block (not native RNIC)

`rdma/rnic/rtl/rocev2_sq_paged_dma.v` composes the actual SQ DMA fetcher,
paged-payload backend and new `rocev2_dma_client_router.v`. It exposes ONE
original app-side16-bit-tag DMA port. It is a separately synthesizable source
composition, not yet selected by the native controlled/paged parent or bound
to registered Linux queues. Trusted raw configuration and previously
authorized payload commands are caller responsibilities. No MR check is
implicitly supplied by this raw backend wrapper.

## Full tags and actual segmented RAM ownership

The two backend clients have independent full16-bit logical tag spaces.
Logical tags are never shortened to reserve a client bit. The router records
logical/physical tag, client, direction and full RAM span, and allocates unique
nonzero16-bit physical tags. Physical status must match the entire issued
tag/direction before the logical tag/error is restored. Delayed duplicates,
unissued tags, wrong directions and unknown4-bit errors fault closed.

One physical operation per staging bank may be active, allowing both actual
clients concurrently. Bank0 is the paged payload backend; bank1 is the SQ
backend. Both require logical RAM selector0. Physical bank selection is
explicit, not address truncation or tag aliasing. Descriptor arbitration is
round-robin across both clients' read/write ports; accepted physical offers
are registered and cannot disappear under subsequent disable/fault.

Current descriptor authorization has an additional registered proposal phase.
IDLE snapshots the chosen original client/direction and complete address64/
selector/RAM15/length16/logical-tag16/immediate-enable fields WITHOUT asserting
client ready, allocating a physical tag or issuing DMA. CHECK performs the
full65-bit DMA64exclusive-end and17-bit RAM span checks from those registers,
rejecting unknown fields; READY uses the registered approval only. At actual
client-ready/valid handshake the checked snapshot becomes the physical offer
and receives the next unique tag. A newly preferred arbiter input cannot
replace its original owner. Full geometry, capacities and limits remain.

The selected source must keep its meaningful offer unchanged until acceptance.
Any withdrawal/change causes sticky fault13, no DMA/tag allocation, and retains
the proposal owner even after raw valid disappears. Invalid span/shape/unknown
context still faults10before acceptance. Disable may stall an unaccepted valid
proposal, but cannot retract accepted physical/RAM traffic. CHECK conservatively
holds logical completion for one validation cycle; an approved pending proposal
does not indefinitely block another issued client's completion during disable.
Global drained always requires NO proposal or raw offered request. This is NOT
a register holding yesterday's drained=1; current offers/lifetime vetoes remain.

Each of the two native256-bit RAM segments has separate write/read ownership
tokens. Commands, byte enables and responses are buffered and routed to the
captured client. Serialized untagged done/responses cannot be misattributed
to the other bank. Already accepted RAM commands/responses survive later
fault/backpressure; no synthetic successful completion is generated.
WRITE commands into staging RAM require every enabled byte within the
issued read descriptor. Engine reads from staging RAM permit the actual
rounded64-byte word intersections; host writes remain bounded by the
descriptor/TLP byte enables. Invalid selectors/ranges/directions, zero or
unknown write byte enables, and unsolicited client done/responses fault.

Physical status is held until the associated actual RAM tokens, raw offers
and child returns are quiet. Router drain alone is NOT parent PCIe drain,
MR/QP release, wire completion or CQ publication. The combined wrapper also
requires actual external parent drain and both child DMA boundaries. SQ error
recovery uses external parent AND router drain, deliberately not its own
SQ-busy/idle output (which would deadlock its READ_DRAIN state).

Native geometry remains RAM address15,2segments256, byte-enable32, segment
address9, DMA length16 and tag16. DMA64 exclusive-end2^64 is legal; overflow
beyond it is not. Unsupported immediate writes are refused, not truncated.
The physical tag counter refuses wrap at65535. Fresh epoch/recovery for
continued operation is unfinished; resetting this router is never proof of
parent cancellation or safe unpinning. Fault/ambiguous ownership intentionally
retains resources, but safe native abort/flush still must be implemented.

Actual first isolated implementation001exposed a four-loop dependency with
real `dma_psdpram`: router response-ready included same-cycle command-ready,
while real RAM command-ready depends on response-ready. The current source
instead asserts child response-ready only in registered WAIT AFTER command
acceptance. A zero-latency child may offer a response immediately but must
hold it until that next-cycle handshake; it is never sampled without ready.
Unsolicited response detection still distinguishes that owned early offer.
This is an RTL correction, not a loop allowance or disabled DRC. New isolated
build002is separately source-frozen; physical removal is not yet assumed.

## Short evidence and explicit models

`rocev2-rnic-dma-router-unit-005.json` passes17four-state methods/36simulations
with explicit descriptor/RAM agents. It covers equalFFFFlogical tags,0/8000,
reverse completion order, early status versus RAM ownership, UR error10,
full-width range/selector checks, four-port fairness, tag exhaustion, disable,
held commands/responses under fault, and delayed duplicate physical status.
The added case asserts NO combinational command-ready-to-response-ready path
and checks held zero-latency response ownership/data through registered WAIT.
These are actual router units, not actual PCIe or backend data-movement tests.
New proposal cases also cover no combinational acceptance/tag bypass, preserved
owner when a competing client becomes preferred,7selected-field mutations/
withdrawal,3unknown full-field shapes, disable plus another client's completion,
and fault before acceptance. First pipelined unit004failed ONLY the older
immediate-next-edge fairness assumption. Current005keeps exact order/full
one-hot winner checks with a finite12-cycle acceptance bound, not relaxed
payload/range/status/ownership requirements. All older failures are retained.

`tests/probe_sq_paged_dma.py` separately instantiates the actual paged and SQ
backends, router, BOTH native-shaped muxes, generic Corundum PCIe DMA,
segmented RAM/AXIS clients, and actual `rocev2_pcie_parent_guard`. It uses no
descriptor/status/RAM agents, internal forcing, constant parent-drained value
or host-model counter substituted for parent proof. The physical root
complex/hard-IP/link/host memory, trusted queue/PTE configuration and authorized
payload command/source are explicitly MODELS. Same-requester/TC0/attr0 posted
visibility is modeled, NOT real PCIe ordering qualification.

Current005passes7physical descriptors/restored statuses,5READ and2WRITE TLPs,
two actual C/UBSan-encoded64-byte SQ records,65-byte payload WRITE and READ
split3+62across scattered full-DMA64 pages, and an actual visibility fence.
It checks every payload/record byte,16319host sentinel bytes,128unchanged
ring bytes, concurrent two-bank ownership, full16->18->19-bit mux tag and
RAM selection12/13, delayed completions,128total delayed write-TX-sequence
cycles, held SQ results and final actual parent/combined drain. Sources and
retained bench/records are SHA-bound. Completion of fetch is still NOT RDMA
WR completion. The portable batch includes this finite actual-PCIe graph.

First probe001failed a harness assertion comparing a pipelined mux output to
the *current* input descriptor. Those are not the same transaction when both
clients progress. Probe002keeps a tag-indexed accepted-descriptor scoreboard
and checks the entire later engine tuple exactly once; no RTL, byte/range,
ordering or ownership assertion was relaxed. Earlier001evidence is retained.
Router-unit001is historical after adding fairness/duplicate unit fixtures;
unit002and probe002are historical after the real RAM loop correction. Current
source-bound unit/probe results were003at that stage. They are historical
after the descriptor proposal pipeline; current unit005/raw probe004and
CSR-controlled probe003retain unchanged all-byte/range/proof assertions.
Progress027raw005/CSR-controlled004refresh both after the new per-QP fetch
queue_pending output; the exact1056/1658cycle byte/proof results remain.

First OOC001completed with terminal1, WNS-3.088ns/TNS-13263.778ns/9079setup
failures, hold+0.012ns/0fail and4LUTLP-1critical warnings/check_timing loops.
Resources18145LUT/12501FF/20BRAM/0DSPare actual isolated results, not full-board
capacity. All13original/frozen inputs matched at terminal observation; the
router and driver now differ from that historical snapshot. No image was
written or authorized. The enhanced current OOC driver explicitly rejects
nonzero check_timing categories and DRC errors/critical warnings, as well as
negative setup/hold. Its exact Tcl gate body passes18bounded fixture checks,
including rejection of the ACTUAL failed001loop report. Gate-unit success is
not physical timing or functional success. Build002uses the same original
4ns clock and full geometry, no waivers; its outcome remains to be collected.

That original002/session12328subsequently completed terminal1on negative setup.
Actual final check_timing reports ALL12categories0, including0loops; DRC has
0errors/0critical warnings/1warning. Physical RAM/router loop removal IS now
verified for its exact13unchanged original/frozen inputs. All23893routable
nets route with0errors. At original4ns, WNS-2.524ns/TNS-9878.554ns/8529setup
failures remain, hold+0.034ns/0fail,pulse0fail. Actual isolated resources are
18053LUT/12492FF/20BRAM/0DSP. This is NOT timing closure or board release.

The remaining worst path is rst -> request arbitration/full-DMA64descriptor
span validation/live-fault/completion/backend drain -> SQ configuration/
producer-table CE,29logic levels/5.971ns data delay. A real registered
authorization/configuration boundary must break that dependence while
retaining current offered-command and lifetime vetoes. Registering a stale
drained=1alone is NOT safe. No slower clock, guard bypass, false-path or loop
waiver is authorized. Kernel-only source work does not change this snapshot;
the new CSR/native parent/PCIe engine/HLS/board are outside this OOC top.

Descriptor proposal/CHECK/READY source work now implements a registered full-
width validation boundary for that identified chain. Original OOC002frozen
inputs/reports are not edited; the mutable router now differs. Fresh isolated
OOC003/session91411froze13current inputs under unchanged4ns/full geometry and
existing DRC/check_timing/setup/hold rejection. It completed terminal1at
2026-10-19 05:13:39UTC: WNS-2.897ns/TNS-12549.917ns/9346setup failures,
WHS+0.034ns/0hold failures/0pulse failures. ALL12check_timing categories are0;
DRC has0errors/0critical warnings/1warning. All24088routable nets route with
0errors. Actual isolated resources18161LUT/12644FF/20BRAM/0DSPare not board
capacity. All13original/frozen hashes matched at terminal and collection.

The descriptor pipeline did NOT achieve timing closure. The worst actual
path now starts at router segment1 registered RAM-WR address bit8, through
byte-span checking/live fault/status/backend drain to SQ producer-table CE:
22logic levels,6.806ns data delay (1.470logic/5.336routing). A safe registered
RAM-validation/configuration ownership boundary is still needed; caching an
old parent-drained=1must not grant new authority. Physical loop removal is
verified for this exact snapshot, but negative setup forbids release. Reports,
checkpoint and hashes are preserved in `rocev2-rnic-sq-paged-dma-ooc-003.json`.
No image, slower clock, capacity reduction, false-path or loop waiver was
introduced. No CAD session remains live after91411terminal completion.

## Still required

Progress027now maps SQC1 in the NEW source/offline native-SQ top and connects
its real coherent SQ fetch to the SAME existing native MR/PTE/backend. Raw
SQ ownership is not an MR lease; actual authorization/downstream masks retain
MR ownership, while per-QP pending/fetch/work owners exclude route changes.
The top shares one original payload backend plus the separate SQ backend,
not a second payload/MR/PTE copy. See `ROCEV2_SQ_CONTROL.md` for the passing
four-state priority case, additional two-state full incoming+SQ case and
the preserved120-second full-forward observation failure. This new graph
is NOT selected in the real mqnic app/board parent or physically qualified.
The new queue_pending output changes two original OOC003inputs; all39isolated
and1880full-board frozen manifest rows remain intact, not inherited signoff.

Actual SQC1/atomic kernel MMIO source is not bound to a real bus/device/QP/CQ/
provider. No actual CQ publisher or registered driver/provider is supplied.
Genuine local sealed-page execution in that shared MR/PTE namespace,
local work executor, per-WR wire/fence/CQ lifetime, abort/flush, SEND/RECV/
immediate/Atomic and wider operation semantics are still required. The actual
parent compile012only elaborates its legacy/default mode; the new sources
are uninstantiated there. It is not proof of enabled native shared DMA.

No resulting-feature full-board physical/CDC release, FPGA programming,
actual kernel pins/coherent allocation, live host DMA, standard verbs or
thermally supervised native function test is claimed. Older META full-board
analysis contains neither these shared clients nor current per-WR delivery.
See `ROCEV2_RNIC_PROGRESS.md` for the unchanged broad goal/exclusions.
