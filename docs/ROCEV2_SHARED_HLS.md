# One shared HLS core, one protected MR namespace

Checkpoint075 separates the physical-memory and per-owner MAC boundaries in
the matched duplex main profile. The actual generated-native diagnostic says
`req_valid1 req_ready0 match1 memory0 parent1 router1 SQ_DMA1 net0 local_mem0`.
The HLS operation was complete; the existing network memory barrier also
waited for the other receive ACK's intentionally withheld MAC completion.

With `DUPLEX_ENABLE=1`, the protected backend still requires REAL parent
PCIe/RAM drain but no longer waits for an unrelated MAC timestamp/tail before
finishing its memory status/fence. `physical_memory_drained` propagates that
actual backend proof through the original native layers, ANDs the real router,
SQ fetch/backend and parent proof, and is used by per-operation completion.
Both local and receive owners still need their OWN HLS/wire/MAC/EOF/tail and
exact CQ proofs. Public `memory_drained` still includes response-MAC quiet;
configuration/full-close barriers and all-zero global HLS drain inputs stay
unchanged. Default0 retains the original extra MAC gate/serial behavior.

Actual full-HLS hierarchy checks pass for both modes. Full native003 PASSES
ordinary/initial-RNR cases in13.99/14.69seconds, with unchanged deadlines,
real in-flight PCIe/fence checks, local CQ while the global MAC barrier is
held, and the negative check withholding the receive's OWN MAC proof. Both
cases complete two SEND/RECV pairs and four exact native CQs, reuse the same
registered buffer, then cancel the third receive without a peer packet using
the real flags63 proof. Full wire/ICRC and all saved-context checks remain.

The exact CQ/WQE/cancel snapshots pass actual kernel SQ/RQ/CQ/MR C flush and
reference logic; Linux/core/MMIO/DMA mapping are models, not running-driver
evidence. Default0 READ/WRITE/HLS-model regressions pass; the new core still
needs full-generated READ/WRITE regression and physical/kernel qualification.
HLS5.306ns still misses4ns; all original full-board timing/DRC/conditional CDC
gates remain. The complete RNIC goal is active, not capped at these two pairs.

Checkpoint074 adds a MATCHED opt-in duplex variant to this same native graph.
`hls/duplex_transport.py` derives `rocev2_native_duplex_top` from the complete
request/receive-receipt core. Its actual memory-command producers mark
REMOTE1/LOCAL2 in bits95:94, formerly AXI byte padding; all94 existing command
fields stay exact. `fpga/derive_duplex_transport.py` replaces only the shared
transport/selected raw top, without another MR table, extra core or changing
the protected original. Old padding0 is not accepted as provenance.

`rocev2_memory_origin_router` retains ordered per-command origin/byte credits
until exact data EOF, including separate local/remote busy counts. It routes
write payload and merges read returns without using a changing global role.
The original protected memory clients still validate all addresses, keys,
PDs, layouts and memory ownership. Provenance is not DMA authority. A packet
RX mux retains a grant through EOF; a TX router buffers both IPv4 header beats
before using the actual BTH request/response opcode to choose its existing
protected MAC/lifetime path. Per-request and receive owner/receipt/retire
state are independent; neither retirement clears the other direction.

Three C++ actual-consumer cases pass with a peer SEND arriving while our
SEND/READ/WRITE is genuinely unacknowledged. Eleven four-state memory-router
cases and eight connected-routing/lifetime cases pass with modeled HLS ports.
Actual complete-parent/generated-HLS elaboration passes. The first full native
run reaches real peer receive placement/core proof while local SEND is still
unacknowledged, but then fails the sender CQ deadline with flags3f and the
receive owner retained. Its exact failure is kept; checkpoint075's diagnosis
and successful native correction above supersede that failed runtime.
The new complete HLS estimate remains5.306ns at unchanged4ns/default1.08ns
uncertainty, with38185LUT/82622FF/150BRAM18K/0DSP. Full resulting-board timing,
DRC/conditional CDC and short physical/kernel/provider checks still remain;
no global-core drain substitute, programming/module load or hardware change.

The following earlier entries describe the retained exclusive-role profile
and separate historical candidates, not a claim that duplex runtime passed.

Progress051 brings the SEPARATE wire-RX nominal HLS estimate to3.947ns with
full320query capture and all guards intact; effective-budget/physical/CDC
signoff still missing. New actual quarantine upstream-stall cases pass; not
safe recovery/flush or selection in THIS shared/native/board graph. Existing
one-role/4096B prototype checks are NOT the full objective cap. Actual native
context/effectful RX/state/memory/MAC/CQ integration still required before
genuine core drain; localdrain0/refsHELD. See `ROCEV2_OWNED_WIRE_RX.md`.

Progress050 adds real II1 count/check/commit, private elastic result retention
and registered full320descriptor completion checks in the SEPARATE wire-RX
candidate. HLS4.002ns still UNMET at original4ns, not physical/CDC proof. It is
NOT selected in THIS shared/native/board graph. No packet/WRMR lifetime grant,
effectful RX/MSN/DMA/CQ integration added; drain0/refsheld/full11requirements
remain. See `ROCEV2_OWNED_WIRE_RX.md` for current/historical/archived scopes.

Progress049 improves the SEPARATE wire-RX scheduling10.256->5.298ns at the
same4ns clock/full geometry. Real II1 packet decode, registered header checks
and SAME metadata epoch selection are not selection in THIS shared/native /
board graph. Ingress timing remains UNMET; actual native authorization,
effectful RX/MAC/DMA/CQ/lifetime remain incomplete. Drain0/refsheld/full goal
unchanged. See `ROCEV2_OWNED_WIRE_RX.md` for exact current/historical evidence.

Progress048 adds actual byte-level BTH/EXH parsing, full-syndrome/raw-header
metadata and real handoff receipts to the SEPARATE same-table lookup/timer /
pool candidate. Ten fresh short FOUR-STATE cases pass; HLS10.256ns UNMET
at original4ns. It is NOT selected in THIS shared/native/board graph; trusted
admission/epoch are still inputs, no effectful RX/DMA/CQ/lifetime grant.
Drain0/refsheld/all11requirements remain. See `ROCEV2_OWNED_WIRE_RX.md`.

Progress047adds a SEPARATE actual process/pointer8/metadata2000/timer/realpool
lookup candidate, not a shadow owner table. Seven fresh bounded FOUR-STATE
cases prove scoped lookup/hold/ambiguity/epoch/READrange/fifth marker behavior.
Full2000live traversal remains unqualified after30s timeout; HLS4.644ns UNMET
at original4ns. It is NOT selected in THIS shared/native/board graph, does
not capture real packet/QP epoch or bind full RXIBH/EXH/MAC/DMA/CQ ownership.
Drain0/refsheld and all11requirements remain. See `ROCEV2_RX_OWNER_LOOKUP.md`.

Progress046improves the separate actual TX producer candidate HLS5.896→3.964ns
at original4ns by equivalent EXH word selection. C++full-index/width checks
and5short generated FOUR-STATE cases pass, including ACK/AETH and12passive
AXIS hold monitors. Effective2.920ns warnings remain, NOT physical signoff.
This is STILL NOT selected in THIS shared/native/board graph or joined to
actual timer/pool/RX/native admission/MAC/DMA/CQ. Drain0/refsheld/full goals
unchanged. See `ROCEV2_OWNED_WIRE_TX.md` for current vs historical scopes.

Progress045adds a separately selected actual FNS TX producer candidate with
full perWR context on local/event/BTH/EXH/PSN/address insertion and original
retry lease. Four short generated FOUR-STATE cases pass, but HLS5.896ns is
UNMET at original4ns. It is NOT wired into THIS shared/native/board graph or
actual timer/pool; real native admission/RX lookup/ordered markers/MAC/DMA/CQ
remain. `local_core_drained=0` and refs stay held. Full goals unchanged.
See `ROCEV2_OWNED_WIRE_TX.md` for exact C++/source/RTL scopes and remaining work.

Progress044pipelines the actual owned timer controls to improve whole candidate
HLS estimate6.894→3.613ns at original4ns, with warnings/no physical signoff.
The exact current timer/process/pool candidate passes six independent XSIM
FOUR-STATE cases including real1ms/two-WR retry. This candidate is still NOT
selected in THIS shared core/native parent or full wire-producer/MAC/DMA/CQ
lifecycle. `local_core_drained=0`, existing references held; full goals remain.
See `ROCEV2_OWNED_TIMER.md` for scopes and retained timing/checker failures.

Progress043couples real metadata insert/ACK/head/replay FSMs with an ACTUAL
full-lease timer and its ordered sixth fence response. It is NOT selected in
THIS shared core/native parent and is not full FNS wire-producer closure or
MAC/DMA/nativeCQ drain. Current coupled proof is TWO-STATE; standalone timer
has separate FOUR-STATE checks. `local_core_drained=0` and refs stay held.
HLS timing6.894ns remains unmet at4ns. See `ROCEV2_OWNED_TIMER.md`.

Progress042joins actual process-injected pointer/meta/pool/output markers and
genuine handoff receipts in a separate retransmission subsystem wrapper, with
five short FOUR-STATE cases. It is NOT selected in THIS shared core/native
parent and does not cover upstream real producer closure or downstream MAC /
DMA/native CQ owners. `local_core_drained=0` remains; no references released.
See `ROCEV2_OWNED_RETRANS_FENCE.md` for exact scope and retained timing failures.

Progress041adds a separately selected actual FNS retransmission process with
full immutable248-bit pool leases on real metadata/events/RDinit, coupled to
the real2000slot pool in a production wrapper. Seven short actual generated
four-state simulations pass; real event/RDinit remain HELD after pool zero.
It is NOT yet selected by THIS shared core or the native/board parent and
does not produce a genuine core certificate. `local_core_drained` stays0;
WR/MR ownership is intentionally retained. See `ROCEV2_OWNED_RETRANS.md`.

Progress035adds `rocev2_shared_hls_transport` and an opt-in, exactly checked
derivative of the existing protected responder. An incoming protected request
and an authorized local WQE use ONE actual unchanged generated HLS core and
ONE actual MR table. This avoids treating the earlier three-HLS simulation
graph as the eventual native/board design.

## Source and ownership boundary

`derive_shared_responder.py` does not edit the original responder or rollback
sources. Its output exposes local-role ports, replaces only the existing
transport instance, includes the real shared-owner guard/fault in existing
protection, and requires the SAME local-MR client to be enabled. The four
derivation units reverse these exact interface changes byte-for-byte to the
original source, check the single MR/core boundary and reject seven missing
anchors. Original parser/ICRC/peer/PD/key/access/VA/range/status protection is
not replaced with another authorization namespace.

The shared transport selects an entire protected remote operation or a local
operation, never individual memory beats. The remote path retains its existing
validated-RX/MR/visibility/TX lease. The local path captures the full588-bit
positive authorized WQE before SQ admission, checks the trusted full QPN and
intervals, and compares ALL248SQ bits: explicit key-valid, full key0/high/
all-one keys, local/remote64-bit VAs, length and all routing/reserved fields.
Raw HLS96-bit memory commands select a stream; they are NOT new DMA authority.
The real local executor must still check the retained full-WQE contract.

RX/TX, READ/WRITE command/data and40-bit ACK metadata are routed under that
same retained role. Unowned HLS offers, malformed owners/SQ, stale retire
identities and in-flight configuration faults quarantine all QPs. Already
accepted work is not canceled by a local reset or a new ownership offer.

The remote role returns through its existing real responder lease controller.
The local role CANNOT retire merely because AXI ports are quiet. Exact saved
context plus an independently proved same-core drain certificate is required.
Actual FNS internal tables/timers/pipelines/retry ownership are not yet bound
to such a certificate. The new actual-HLS probe keeps `local_core_drained=0`,
does not publish a memory-complete/CQ success, and deliberately ends with the
role/MR/whole-WR guards HELD. A modeled drain in an isolated unit tests only
the private interface, not the missing real certificate or permission to unpin.

The frozen HLS input profile explicitly enables `RETRANS_EN`. In its actual
`ib_transport_protocol.cpp` RX-IBH process, state-table and retransmission
updates are queued, the ACK metadata is emitted, and the timer-clear request
is queued separately. `state_table` is another dataflow consumer. Therefore
accepting ACK metadata does not certify that all these consumers committed
their updates or that no retry work remains. A genuine owner-retirement/fence
handshake must cover those state/queue/timer owners; observing quiet external
ports or adding an arbitrary quiet-time delay is not a replacement. This is
unfinished engineering, not an external blocker or a reason to reset/unpin.

Progress036adds an isolated actual timer-consumer state readback with ordered
RX markers, real pending TX application and full-token snapshots. Generated
four-state RTL passes46queries including a real1ms timeout still held after
timer-state OK. This explicitly does NOT prove whole-core drain; the shared
core has not selected this derivative and retains `local_core_drained=0`.
See `ROCEV2_TIMER_STATE_FENCE.md` for scope, retained failures and the3.911ns
HLS estimate, which is not original-clock full-board physical signoff.

Progress037adds the actual state-table consumer's RX/TX/QPI three-marker
rendezvous with real BRAM/full-token readback and original normal actions.
Actual generated RTL checks59cases, including8ordinary burst writes and real normal responses still
HELD after table-window OK. It is isolated/not selected here and does NOT
prove producer/retry/event/core drain or permit owner release. See
`ROCEV2_STATE_TABLE_FENCE.md`; genuine shared drain remains0 and wider native/
CQ/provider/full-board/recovery work remains required.

Progress038adds the actual retransmission pointer/lock consumer's two-marker
readback. Generated RTL003checks39cases incl real wait/unlock/update priority
and a normal response still HELD after pointer-state OK. Metadata/free-list/
process/replay/event producers and real marker injection remain separate
required owners. The derivative is isolated/not selected here, not a core
retirement certificate; shared drain stays0/MR owners held. See
`ROCEV2_RETRANS_POINTER_FENCE.md` for source-bound evidence and timing limits.

Progress039adds actual2000entry metadata commit/readback with real RAW/order
dependencies.27readbacks/6005normal reads check every entry zero/nonzero/zero
after simulated reset in actual generated RTL. Original ACK release does not
erase record valid; commit OK can return VALID data with a normal response
HELD. Therefore this isolated/unselected constituent is NOT active/free/core
drain/MR/CQ permission. Real free-list/process/event/producer ownership remains;
shared drain stays0. See `ROCEV2_RETRANS_META_FENCE.md` for exact scope.

Progress040adds actual2000slot lease RAM/free ring with generation/full owner
matching, ordered allocation/release markers, and local-reset retention of
owned/unconsumed reservations.16short tests pass; actual mapped BRAM/GND-only
generation reset pins checked via immutable synthesis DCP. This is a candidate
request/grant allocator, NOT yet the original FNS process/free-list binding,
post-synthesis function/full-board signoff, hard-reconfiguration recovery or
whole-core/MR/CQ release. Shared drain stays0/owners held. See
`ROCEV2_RETRANS_POOL.md` for boundaries and preserved initial failures.

## Bounded evidence and limits

The current four-state role units pass5methods/46simulations, with an
explicit HLS replacement. They check remote-to-local role routing across all
streams, SQ stability/complete fields, invalid full QPN/owner/range, explicit
keys, retire0/X/Z-drain holding, stale identities, unowned HLS output and
in-flight configuration. Test-only `core.STUB_*` signals are the HLS model's
outputs; production state is not forced. Current derivation units pass4methods.
Both batches finish in under2seconds. These are not actual-HLS/physical tests.

Actual-HLS probe001PASSES with exactly one HLS/core/MR graph: protected incoming
65BWRITE -> actual tagged simulated-memory commit/WRITE ACK, then actual C/
UBSan WQE -> SAME MR lookup -> actual guarded SQ/key0 -> SAME live HLS READ
request -> own-TX-derived issued PSN -> real protected response gate -> SAME
live HLS68raw bytes -> checked unpad65bytes/3pad -> simulated memory, plus real
Ethernet/MAC tag/receipt/tail/lifetime RTL. A wrong-QP response with valid ICRC
has no HLS/data side effect. Every memory/sentinel byte is checked and an MR
invalidation remains blocked by actual owners at the finite end. No additional
HLS core or raw generated-HLS edits are used.

001is historical after splitting a mixed initialized/uninitialized wire
declaration for Icarus portability and strengthening the independent MAC-byte
oracle. Its exact original module/probe copies and compiled artifact are
retained; their hashes match001inputs. It was a valid additional TWO-STATE
Verilator run, NOT four-state/X/Z/physical proof.002also PASSES with complete
independent Ethernet bytes/frame boundary/tag checks;003additionally connects
and checks remote full MR key/offset and explicitly declares the ACK-ready
wire. Fresh source-current003PASSES in2.669seconds. Current role/derivation
unit002reports match those sources. These runs are additional TWO-STATE only.
Original001/002probe snapshots remain hash-exact historical inputs, not
source-current passes after the explicit-port/oracle changes. No assertion or
raw generated-HLS repair is used to change a failed functional outcome.

The actual shared-core case has NO coherent host SQ fetch, real pinned host
pages, actual PCIe/PTE placement, memory visibility fence, kernel CQ/provider,
board selection or physical network. Simulated memory/peer/MAC pins remain
explicit models. Its actual HLS/SAME-MR proof and the earlier native PCIe/
MAC trace-backed proof are complementary, NOT a completed native shared-HLS /
PCIe/CQ/runtime proof. It proves neither safe local role reuse nor generalized
retry/concurrency/zero/large/multi-SGE/SEND/RECV/immediate/Atomic support.

The actual-HLS compiler retains an UNOPTFLAT warning at the unchanged
`rocev2_ipv4_icrc` CRC vector. It is not suppressed or converted into a physical
pass. All original-clock resulting full-board timing/routing/DRC/check_timing/
conditional-CDC gates, old physical failures and rollback identities remain.

Next propagate this checked shared-role boundary through actual paged/control/
native parent layers, bind the real coherent SQ/full-WQE executor/PTE/PCIe /
response/MAC path, and implement genuine core-drain/CQ/driver/provider lifetime.
Keep all wider functionality and short recovery/interoperability requirements;
this retained positive one-local-WR case is not a new objective limit.

No FPGA/JTAG/flash/driver install-load-probe/real traffic/fan/BIOS/network/
reset/reboot/commit/push. BIOS Medium and management are preserved. Exact
authenticated Codex thread/active-goal reboot restoration remains unproven;
no reboot is needed for this source/offline work.
