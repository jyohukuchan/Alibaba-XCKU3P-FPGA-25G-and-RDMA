# Shared incoming/local-work memory authorization

This is real source integration and bounded offline RTL evidence, NOT a native
host queue, pinned-page execution, completed RDMA device/provider or deployed
FPGA image. The older META full-board analysis predates this source change
and failed setup timing; its frozen reports cannot qualify this newer path.

## Actual single namespace

`rocev2_protected_responder` has a static `LOCAL_WQE_ENABLE` parameter, default0.
Default0 retains the dedicated remote-query connections and ignores every new
local port. Default1 inserts `rocev2_mr_query_arbiter` before the SAME existing
`mr_table` instance. There is no second table, registration shortcut, copied
key cache or local-authority fallback. The actual `rocev2_wqe_admission`
frontend connects to this local port; incoming packets retain the actual
integrity/parser/peer/QP/PD/PSN gate before the other port.

The two-client arbiter captures the complete PD/key/address/length/operation/
tag tuple, uses round-robin selection, and allows one query at a time. An
explicit owner bit routes results, so identical16-bit cookies from different
clients do not alias. A stalled query stays registered and valid; a stalled
response blocks reassignment. Non-owner outputs and denied translated
addresses/extents are zero. Wrong tags, successful lengths or unknown errors
cause a sticky fault without inventing a response/completion or drain. Even
an unsolicited response cannot retract a query already offered under stall.
Reset is not host-page/DMA lifetime proof.

Local WRITE requests use LOCAL_READ authorization to read their source;
local READ uses LOCAL_WRITE for its destination. The full local key, trusted
PD and64-bit range are validated by the SAME table as remote requests. The
local port deliberately does not expose the contiguous DMA-address result:
the future executor must use sealed/scattered page translation, not truncate
the user IOVA through the HLS48-bit/routing fields.

## Management exclusion without blocking progress

`local_work_guard` must include the WQE frontend's offered/accepted ownership
AND actual downstream work ownership, without a handoff-edge gap. It must
remain asserted across uncertainty/fault until real external recovery. An
MR query response, accepted work item or local reset is not an RDMA completion
and cannot release kernel MR/queue/page references.

MR/QP configuration quiescence now includes that guard, offered local queries
and shared-query ownership/fault. Separately tracked management ownership
covers the accepted command, its application pipeline and its held response.
`local_configuration_idle` includes management offers/pause and this pending
ownership, but does not depend on `local_work_guard`/`cfg_ready`. Connecting
it to the WQE frontend therefore does not create a combinational guard loop.

In shared mode RX admission uses this independent management-idle condition,
not the MR **mutation-ready** signal. A local lease correctly makes mutation
not-ready but must not prohibit an independent incoming frame/lookup. An
accepted local query continues across a later pause/disable. Management still
has priority before a new local WQE is accepted, including every cycle of an
accepted command or backpressured configuration response.

## Current bounded evidence

`mr-query-arbiter-unit-001`:6four-state methods, external validator response
model, full-width tuples, identical cookies, query/response backpressure,
continuous-offer fairness, denied-address zeroing and sticky ownership faults.
This alone is not MR permission or actual-HLS evidence.

`shared-mr-unit-003`:3methods use actual C/UBSan descriptor bytes, actual WQE
RTL, actual integrity/parser/responder and a SINGLE actual MR table. Only the
HLS transport is explicitly stubbed. The downstream local executor lifetime
is also an explicit fixture owner, not hardware/pinned-page proof.

The same final fixtures run with the exact per-WR delivery (138unchanged raw
HLS files,140delivery files). No transport stub or internal forcing:

| Actual-HLS record | Bounded observations |
| --- | --- |
|shared-mr-namespace-hls-001|11local queries/results;19incoming frames,13rejections,1ICRC drop,2WRITE/3READ operations and5wire replies; old/fresh/full-bit/wrong-PD/permission/64-bit-range/key0 cases|
|shared-mr-lease-hls-001|4local queries/results,1modeled downstream lease; management-offer/accepted/held-response priority, deferred invalidation and stale/fresh rekey;1incoming WRITE/ACK|
|shared-mr-overlap-hls-002|1local query/result held across disable/pause and an independent incoming WRITE/ACK; remote progress resumes after the held local MR response while local work-result ownership still excludes mutation|

These actual-HLS simulations take approximately37.6..41.5seconds each. Actual
IPv4/ICRC, peer QPN, PSN, ACK AETH and all three65-byte READ payloads are checked
independently. The local WQE is NOT submitted to HLS SQ, no native local DMA
or CQE is executed. Incoming backend memory is a model, not PCIe host memory.
`wrkey-parent-compile-004` additionally elaborates the actual patched parent/
core/app at MAC tags16/external64/sync128/global DMA tags19/app tags16, retaining
all warnings. That parent still selects the default single-client path;
source availability is not enabled shared native integration.

The earlier progress018 portable batch020passed184methods in208.010seconds,
including the existing default-mode regression suites and9new shared/arbiter
methods. Source-checks019passes7methods. Each of the three retained actual-HLS
compiled simulations contains exactly ONE elaborated `rocev2_mr_table` instance;
the resulting VVP files are additionally hashed in progress018. These results
do not establish a physical timing pass, native traffic or host-page lifetime.

The failed first unit run remains preserved: a negative-offset fixture literal
caused compilation failure and the initial shared admission deadlocked RX
behind a local result. Corrected byte-literal formatting did not weaken an
assertion; separating management-idle from mutation-ready fixed the real RTL
progress dependency. Unit002/overlap-HLS001 are intermediate passes before the
final management-priority/count-observation fixture additions, not current
final-harness evidence. No failed record is overwritten or relabeled.

## Paged and controlled integration (progress025)

The actual `rocev2_paged_responder` and `rocev2_controlled_responder` now
propagate default-OFF `LOCAL_WQE_ENABLE`, the full local request/response and
the continuous work guard into that SAME existing MR table. These are not
additional copied key tables. At progress025this option was not yet propagated
through the same-port/native wrappers; the follow-up below does that. Neither
stage implies a host-SQ/local payload executor or actual board-parent selection.

PTE management needs its own accepted-command/held-response ownership bit.
In shared mode new admission uses this independent ownership plus raw MR/QP/
PTE offers, not backend/PTE **mutation-ready**. The latter depends on guard
quiescence, so feeding it into local admission would create a combinational
loop and block fresh RX behind a held local result. Actual PTE/MR/QP mutation
still requires real quiescence, publication pause and backend drain. The
controller additionally blocks new local WQEs while its management command,
reply, building/tainted state or fault is owned. Accepted local work continues
through a later disable/management pause; handoff is not lifetime completion.

`rocev2-rnic-shared-mr-paged-unit-002.json` passes4bounded tests with actual
C/UBSan descriptor bytes, MR/PTE/control/RAM RTL and an explicit HLS stub.
Earlier unit001is a passing intermediate fixture, superseded when the actual
HLS execution/provenance and independent wire checks were added.

`rocev2-rnic-shared-mr-paged-hls-001.json` runs those same4cases against the
verified per-WR delivery,138unchanged raw/140delivery files, with NO transport
stub or internal forcing. It checks19local queries/results,3explicit modeled
downstream leases, key0/high-key-bit/PD/access/full64-bit-range denials and
stale/fresh rekey; raw PTE-offer/accepted/held-response priority; deferred
MR/PTE invalidation across result handoff; and fresh incoming RX while local
results are held. The controlled case uses its actual exclusive AXI mailbox
and publication sequencer, with no externally driven raw config bypass.
Each case executes ONE65-byte incoming WRITE through actual sealed-page
translation,3+62page split, segmented RAM,2physical write descriptors and a
visibility-fence read. Every host sentinel/payload byte and the resulting
wire IPv4 checksum/ICRC/QPN/PSN/ACK AETH is checked. Actual simulations take
34.3..46.7seconds each. The four retained VVP files each elaborate exactly
ONE MR table/arbiter/paged responder; only the controlled case has a control
wrapper. Fixture/compiler/simulator/VVP hashes are retained and rechecked.

PCIe descriptor execution/host memory/posted visibility and the downstream
local work lifetime remain explicit MODELS. This is not local payload DMA,
SQ execution, CQ publication, pins, Linux runtime, standard verbs or native
hardware. Parent-compile010again elaborates the unchanged default legacy
selection with all warnings retained; it does not enable this local feature.

## Enabled native/same-port follow-up (progress026)

`rocev2_dual_ethernet_endpoint` and `rocev2_native_endpoint` now propagate the
same default-OFF `LOCAL_WQE_ENABLE`, complete local query/response and work
guard. No MR table is copied. New admission additionally requires an enabled,
nonzero-epoch Ethernet route and no outer TX/completion fault. It does NOT
depend on global quiescent/config_safe, which include the caller's guard.
Accepted queries/results stay connected after a later outer fault; the
caller must retain uncertain downstream ownership, not infer cancellation.
The work guard also excludes route COMMIT through actual global config_safe.
There is no new BAR aperture/ABI, SQC1 decode or advertised verbs capability.
The real mqnic board/app parent still does not select a local host-SQ executor.

`native-shared-mr-control-003` enables the option in the actual native AXI
crossbar, same-port Ethernet, exclusive control sequencer, SINGLE MR/PTE,
segmented RAM, two native-shaped DMA muxes, generic PCIe DMA and actual parent
ownership guard. Host-model outstanding counters are NOT drain-proof inputs.
Thirteen actual C/UBSan WQE queries/results cover full local permissions,
PD/key0/high-bit/VA64/range/rekey; a held local result permits a FRESH incoming
WRITE, then an explicit modeled downstream owner holds actual STOP and unsafe
Ethernet COMMIT off. Full sequence/command/cookie/slot/key/error/flags/ACK
checks cover25control replies. No normal allow/deny/global-idle/byte assertion
is removed. The original5incoming operations still pass:2x65-byte WRITE,
3x65-byte READ,8READ/4WRITE TLPs,8read completions,2visibility fences,
256delayed write-TX-sequence cycles, all host sentinels/payload bytes and
5independently decoded Ethernet/IPv4/ICRC/QPN/PSN/ACK/READ replies. Ordinary
host TX/RX/completion bytes and sidebands are retained. Actual simulation
108.79seconds;25496cycles. Final safe STOP/route COMMIT and old root/capture
aperture readback pass. Only the WQE-to-MR authorization is local, not local
payload execution or transport submission.

`native-shared-mr-fault-004` injects an invalid completion through the explicit
physical-MAC model queue, not a forced DUT state or invented DMA status. The
actual outer fault0xf2blocks new local admission while an already-held MR
response and accepted WQE result still progress. The modeled downstream lease
is deliberately retained through the end: no false quiescence, MR/PTE mutation,
DMA/WR completion, flush/recovery or unpin is claimed. Actual simulation
79.51seconds. Each actual-HLS VVP has ONE native/same-port/control/paged/MR/
arbiter/parent-guard instance. Source, delivery and retained artifacts are
hashed;138raw HLS files remain unchanged in the140-file per-WR delivery.

`native-shared-mr-unit-001` adds2portable actual-C/native-management tests
(32.566seconds total) with an EXPLICIT HLS stub. Real local MR/STOP/route/fault
ownership is checked; no network or DMA operation is issued. These are NOT
HLS/wire/PCIe-payload substitutes for the actual-HLS cases above.
Parent-compile011elaborates the actual patched parent/core/app in its DEFAULT
legacy selection with original warnings retained, not an enabled native local
queue. Fresh default legacy READ/WRITE004cases retain old initiator behavior.

Intermediate failed attempts remain preserved, not relabeled: control001
rejected a missing actual parent-guard instance, fault001had JSON-string
fixture syntax errors; the existing actual parent-proof composition and raw
string fixture were then connected without changing RTL assertions. Both002
cases expired at70seconds with NO functional result. Exact frozen25-second
diagnostics of enabled AND known-successful default VVP each had only3initial
time steps; the default successful run took108.36seconds. The probe therefore
uses the SAME existing120-second bounded native simulation limit, not longer
protocol cycle/byte/ownership limits. Fault003then reached the intended0xf2but
the original normal-only monitor rejected it; fault004sets the existing
expect_fault flag only at the explicit injection edge and still checks the
exact fault, blocked new work and retained owner. No broad fault waiver is
introduced. Diagnostic Verilator lint attempts did not produce a loop proof
(initial timing-option errors, then a45-second observation expiry); neither
is a timing/CDC/physical pass.

## Native coherent SQ admission follow-up (progress027)

`rocev2_native_sq_endpoint` now connects actual mapped SQC1 control and the
real coherent-SQ DMA fetch to `rocev2_sq_wqe_admission` and this SAME native
MR table. It shares the original native paged payload backend and one common
full-tag DMA router; there is no duplicate MR/PTE or payload backend. This
is a NEW source/offline top, not selected/deployed in the real board parent.
See `ROCEV2_SQ_CONTROL.md` for mapping, error/context handling and exact limits.

The important ownership boundary is raw ring/fetch versus MR authority.
Management may invalidate a key while fetched bytes await admission. Raw SQ
ownership protects its ring/route, but is NOT ORed into the native MR lease:
that would deadlock pause/invalidate against admission. The real admission
bridge and actual downstream executor/wire/CQ masks protect MR lifetime from
offer/handoff onward. The current downstream executor/CQ is still an explicit
fixture model; accepting a result does not complete a WR or release MR refs.

The actual-HLS priority001case passes in97.03seconds: a real shared-port SQ
READ is delayed while native invalidation enters, the MR command completes,
and the fetched stale key is denied by that table without local payload DMA.
Retirement is refused while the modeled CQ owner holds the work. Two new
portable native cases use an explicit HLS stub; the separate bridge has
5methods/16four-state runs including X/error/full-width authority checks.

Prior progress026native actual-HLS control/fault records remain preserved
historical source evidence after changes to native configuration guarding and
headers; they are not silently promoted to new-source physical/runtime proof.
Default old-initiator READ/WRITE004sources remain unchanged. No MR/PCIe/WR
lifetime completion, reset safety or current physical closure is inferred
from a compiled two-state run or an observation timeout.

## Still required

Progress028now exposes the privileged authorized local-memory contract through
the actual native layers into a new arbiter before the SINGLE existing PTE/
payload backend. Coherent SQ/SAME-MR and actual scattered PCIe source/destination
memory paths pass with an EXPLICIT local transport/executor/CQ model; see
`ROCEV2_SHARED_PAYLOAD.md`. This is not actual per-WR HLS command binding or
wire/CQ completion. Full WR guards must continue beyond memory result handoff.

Select this now-native/same-port/paged/controlled local path in the real board
parent and bind trusted bus/QP/kernel ownership to the source-level coherent
SQ fetch/control path. Implement sealed-page local execution/staging and wire/memory/fence/CQ
completion, with non-sleeping kernel MR/QP/queue references. Current MR-control
mutex callbacks are sleepable and cannot simply become an atomic `post_send`
fast path. Standard kernel/user verbs/provider and additional required
operations/recovery/concurrency remain open, as do a resulting exact new
full-board original timing/routing/DRC/conditional-CDC gate and short thermally
guarded native tests retaining the old READ/WRITE behavior. No FPGA program,
module loading, traffic, reboot, networking/fan/BIOS change, commit or push
occurs in this stage; the broad RNIC objective remains active and incomplete.
