# Native WQE-bound local memory execution

Progress031update: the corrected fresh actual-HLS source compiled002is now
terminal0, passing one65-byte actual coherent-SQ/SAME-MR/HLS/executor/paged-PCIe
IP WRITE packet with independent full key0/VA64/QPN/PSN/pad/IPv4/ICRC checks in
10.68seconds after463.04seconds of compilation. Source/artifact/binary hashes
and the three genuine HLS instances are verified. This remains additional
TWO-STATE offline evidence with physical host/link/final wire-CQ MODELS, not
X/Z/reset/four-state, peer ACK, READ placement or native board completion.
The new actual positive response/READ-token guard is described separately in
`ROCEV2_WQE_RESPONSE_GUARD.md`; actual shared HLS/issued-wire/CQ binding remains.

Progress030adds production `rocev2_wqe_memory_executor`, connecting the full
SAME-MR authorized WQE owner to actual HLS memory commands and the existing
shared paged-memory client. This is incremental execution work, not a complete
RNIC, native board deployment, protected READ-response receiver or CQ/provider.

## Authority and lifetime

The entire588-bit trusted context remains saved: full WR ID/sequence/epoch,
QPN/PD/tag, operation/flags/length, local key/VA/relative offset, remote VA/key
and authorization/error identity. Known identity, QPN bounds before narrowing,
nonzero sequence/epoch/tag, legal operation/flags and65-bit interval ends are
validated. An exclusive end2^64is legal; actual wrap/overflow is rejected.
Key0, QP0and PD0remain legal, not implicit absent/legacy values.

All96bits of the HLS memory command must match the saved WQE: padded QPN10,
VA-derived routing/stream/address, host1, sync0, control1and exact length28.
These fields are consistency assertions, NEVER backend address authority.
The actual backend command uses ONLY the saved complete key32, MR-relative
offset64, length32and tag16. No CPU payload copy, duplicate MR or user-supplied
physical DMA address is added.

WRITE consumes one HLS source-read command and forwards registered, validated
512-bit shared-memory data to HLS. READ placement consumes one destination-
write command and forwards validated HLS data to shared memory. READ also
requires an identical full588-bit response context from a TRUSTED protected
receive controller BEFORE any raw command is accepted. Raw HLS alone cannot
authorize READ placement. That receive controller must check actual integrity,
trusted peer/IP/QP/PSN/opcode/length and bind the result to the retained WQE;
it is NOT implemented by this new module, not inferred from the context port,
and remains explicitly MODELED in the native READ unit.

Data keep/last and meaningful-byte knownness are checked; invalid tail bytes
are zeroed. Commands, output beats and memory events are registered and remain
stable through stalls, admission disable, halt and faults. Already-owned work
can continue despite executor-local admission disable. Native top-level enable
is DIFFERENT: it pauses the whole outer DMA router. Accepted owners must stay
held across that pause, and the router must resume before new physical DMA
descriptors can progress. The native fixture checks pause/retention/resume.

A backend success event is accepted only after its exact tagged data's final
output beat. Early success waits; exact errors can be consumed without a data
success. A denied WQE or failed fetch transfers full original error/identity
without any HLS/memory command. Descriptor-unavailable WR_ID0still needs the
trusted queue shadow later; it does not invent a CQE.

Memory status is NOT WR completion. Per-QP guards cover owner offer/capture,
command, all data and held memory event. A downstream wire/CQ owner must
ALREADY hold the per-QP guard BEFORE event ready; otherwise fault retains the
event/guards. Backend DMA error transfers its exact error but quarantines all
guards, never reports safe drain/unpin/recovery. No reset-based cancellation,
default-success completion callback, fake ib_device or verbs capability is
introduced.

## Current prototype limits and integration

One retained WR, one HLS memory command, nonzero1..4096bytes and one SGE are
implemented here. Duplicate commands currently fault; actual retransmission
memory replay, zero/large/multi-SGE, broader operations and concurrency remain
required. These limits are NOT a redefinition of the full general RoCE goal.

Actual native coherent-SQ tests wire the production SQ producer and executor
through the existing native top's private owner/HLS/shared-memory ports.
The actual mqnic app/board still selects its legacy default. A real shared
transport selection, protected ACK/READ-response ingress, native wire/MAC/CQ
controller, abort/retry, kernel runtime pins and standard provider are missing.
The full original-clock resulting-board setup/hold/pulse/skew/routing/DRC/
conditional-CDC and short supervised hardware gates remain mandatory. Old
negative frozen physical reports remain negative, not inherited signoff.

## Bounded verification

Four-state executor unit002passes14methods in1.993seconds. It checks complete
authority, each raw ABI field/padding, full response-context identity, QP0/PD0/
key0/exclusive-end2^64, all15fetch errors, denied MR, unknown/malformed owner,
opposite/duplicate/unknown commands, data shape/knownness, early/misowned status,
exact backend errors, registered offers across fault/halt/disable, and guarded
event handoff. MR/HLS/backend/receive/CQ are EXPLICIT MODELS in that leaf.

Native executor unit002passes two cases in42.522seconds: actual C/UBSan64-byte
records, coherent-SQ fetch, SAME native MR, actual owner/SQ producer/executor,
single shared PTE/payload RAM/router/mux/generic-PCIe and real parent guard.
Source65bytes spans two scattered physical pages; placement65bytes uses two
posted WRITEs and a real visibility fence. Full host/ring sentinels, pause/
STOP/early-retire exclusion and downstream event ownership are checked. HLS
requests, authenticated READ response, physical host/link and wire/CQ remain
MODELS. Later unit-helper expansion makes002historical; the final full batch
emits fresh source-bound003records.

`probe_native_executor_hls.py` builds a NEW finite WRITE-source integration:
actual coherent WQE -> actual SAME-MR -> guarded SQ -> unchanged generated
per-WR HLS -> actual memory executor -> actual shared PTE/PCIe -> HLS IPv4
packet. Physical host/link and final wire/CQ owner remain MODELS; no peer ACK,
protected READ response, MAC completion, Linux pins or deployed RDMA completion
is claimed. All65actual modeled-host bytes, key0/VA64/QPN/PSN, padding and
independent IPv4/ICRC are checked. This is not just complementary disconnected
HLS/authorization tests, although the real board/network/CQ remains missing.

Four-state source-HLS003is a retained120-second wall timeout with NO protocol
pass/fail result. Unit helper expansion also happened during that run, so it
cannot become current source-identity evidence. The additional compiled
two-state run retains the exact finite bench and all protection/DMA/byte/
ownership assertions, but NEVER substitutes for X/Z/reset/four-state or
physical qualification.

Additional compiled001is also a retained FAILURE, not a pass: the genuine
local source case reaches its65-byte packet and ownership/sentinel checks,
but Verilator schedules `$finish` until the process yields and then executes
the old DIFFERENT five-incoming-operation scenario's trailing coverage checks.
The new finite case now has a named initial block and explicit return after
its own final checks/finish; no actual local/PCIe/protection assertion is
removed or weakened. The hierarchy expectation is also corrected to3real
HLS cores: original native initiator + original protected responder + new
source. A fresh compiled002build is in progress at checkpoint030; no cached
binary, edited generated C++, waived assertion or passing protocol result is
claimed. Its exact live handle is retained for the next continuation.

Final portable037passes297methods in520.468seconds, including fresh source-
bound executor003(14methods/70simulations) and native-executor003(2methods).
Source-checks041also passes all31unittest batches/201methods (the command runs
the source script and BOTH existing RDMA/READ source/test targets; repeated
source batches remain counted explicitly, not201distinct test definitions).
Checkpoint030retains the full11requirements, current source/frozen/rollback
audit and precise pending/failed HLS evidence. No new full-board timing or
native hardware completion is established by these checks.

Preserved fixture failures: native unit001wrongly expected new router DMA
while native global enable was0; the fixture now verifies retained ownership
and resumes that router, without changing RTL or weakening STOP/retire/byte
checks. HLS source001/002never ran due fail-closed fixture-anchor checks; their
logs remain. No failed result is overwritten or promoted to a passing result.

This stage performs no FPGA programming, driver install/load/probe, live
traffic, network/fan/BIOS changes, reboot, commit or push. Exact authenticated
Codex goal/thread restoration after reboot remains unproven; none is needed.
