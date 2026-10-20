# Protected WQE-bound positive ACK / READ-response ingress

Progress032update: full portable038is now terminal0,309methods/849.164seconds.
Response-guard004passes11methods/34simulations and native-response003passes
its actual protected-token/native-placement/fence case. The actual-HLS READ
wire-pad ABI difference is now addressed by separate production unpad RTL;
its new coupled actual-HLS native READ build is still live, not a pass. See
`ROCEV2_READ_UNPAD.md` for exact latest scopes and preserved failures.

Progress031adds production `rocev2_wqe_response_guard`: a real whole-packet
receive gate that binds a positive WRITE ACK or READ RESPONSE ONLY to a saved
authorized588-bit WQE. It supplies the actual memory executor's READ placement
token only AFTER packet validation, then replays the unchanged packet to HLS.
This is not a complete native RNIC, cryptographic authentication or CQ engine.

## Saved authority, never reconstructed from RX

The full original WR ID/sequence/epoch/QPN/PD/tag/operation/flags/length, local
key/VA/offset and remote VA/key remain immutable. Complete knownness, full QPN
bounds BEFORE narrowing, nonzero epoch/sequence/tag and65-bit exclusive interval
ends are checked. Key0, PD0, QP0and an exact exclusive end2^64remain legal.

Local/peer IP and expected PSN are captured atomically from TRUSTED issued-WR/
connection ownership, not incoming bytes. That actual native issued-PSN/wire
controller is STILL missing: expected connection/PSN are explicit MODELS in
the new native unit. Peer IP checks are not protection against IP spoofing;
READ responses have no on-wire local key/PD. Those remain the saved, already-
authorized WQE's authority under continuous native MR/QP ownership.

The existing real `rocev2_ipv4_icrc` checks the ENTIRE IPv4/ICRC frame before
its first byte reaches the new parser. Parser checks exact trusted peer/local
IPs, destination QPN and expected24-bit PSN; current plain IPv4/UDP4791/zero-
UDP-checksum policy; BTH PKey/TVer/reserved/SE policy with M0/M1allowed; exact
operation, ACK-class AETH and exact payload/pad/packet length. Positive AETH
credit bits remain data, not a false error. Nonzero UDP checksums, other opcodes,
NAK/RNR and segmented responses are not advertised as implemented here.

The parser never queries or duplicates MR/PTE tables. READ's full original
context is offered to the actual memory executor BEFORE any HLS RX beat.
The real executor is already holding its native per-QP guard. HLS's later
shortened memory command still must match all96bits, and memory authority
still comes ONLY from the original full key/relative offset/length/tag.

Registered replay preserves every validated packet byte/keep/last through
backpressure. Unknown meaningful bytes/shape fail closed; invalid integrity
never emits a token, HLS frame or response event. Bad peer/QP/PSN/shape/opcode/
syndrome emits a local rejection and RETAINS the original expected WR so a
later legitimate response can still finish it. Rejection is not wire NAK/RNR
recovery and not a successful CQ completion.

Unowned packets are drained/discarded, never queued for a future WQE. In
particular, an unowned SOP coincident with expectation capture MUST keep its
whole tail on the discard path. Only one raw packet is admitted at a time;
there can be no extra integrity-FIFO packet carried across response ownership.
Halt/disable prevent NEW expectations, not progress of an accepted WR. Faults
retain guards and already-offered token/beat/event, not reset-based recovery.

## Response, memory and CQ remain different owners

A READ placement token is NOT memory completion. A successfully replayed frame
is NOT a completed HLS memory write. A response event is NOT PCIe visibility,
MAC completion, WR/CQ completion or permission to unpin.

The guard retains native wire ownership through token, all HLS RX beats and a
held full-context response event. A genuine downstream per-QP owner must
ALREADY be held before token/event ready, and stay held through replay.
Missing/lost ownership faults closed. The native unit keeps the response wire
guard through actual posted-write/fence/memory-event handling, then hands the
response event to an explicitly held downstream CQ MODEL. No actual CQ is
invented and no default-success hardware callback/ib_device is introduced.

## Bounded evidence and remaining gates

The new unit exercises READ1/64/65/4096bytes with M0/M1, WRITE ACK credit bits,
full zero/high context and PSN extremes, malformed/unknown expected owners,
wrong peer/QP/PSN/opcode/AETH/PKey/pad/length with valid ICRC, bad ICRC/IP checksum/
sideband, held replay, missing/lost guards and unowned/SOP-capture races.
These are actual integrity/parser/replay RTL; issued context, HLS/memory/CQ
are MODELS. Final source-bound records are emitted by portable038, currently
in progress at checkpoint031; a full309-method pass is NOT claimed yet.

Native response002passes one bounded case in31.345seconds: actual C/UBSan READ
WQE -> coherent SQ -> SAME MR -> actual owner/SQ producer/executor -> real
response-integrity/peer/QP/PSN/length gate -> real placement token -> real
shared PTE/RAM/router/generic-PCIe ->65-byte placement/two posted writes/fence.
A valid-ICRC wrong-QP response first has no memory side effects. Unchanged
validated response bytes, guarded replay, all host/ring sentinels and STOP/
early-retire exclusion are checked. HLS extraction/commands, issued context,
physical host/link and final wire/CQ remain MODELS; this is NOT actual-HLS READ
or deployed/native RDMA completion. A later unit-helper parameterization makes
002historical. Portable038has now emitted fresh native-response003: that
latest-source native case PASSES. The remaining full batch, including the
whole response-guard unit collection, is still live; no full309pass is claimed.

Preserved fixture failures: unit001used an incorrect interface-port count
before elaboration. Unit002corrupted PACKET10when replacing PACKET1; whole-
placeholder matching fixes it. Its missing-guard fault injection also tripped
a monitor that assumed every ready was a LEGAL guarded transfer; the monitor
now follows the real guarded transfer and the negative case independently
requires sticky fault, full retained token/all guards and NO HLS bytes.
Native001recomputed ready after the original blocking posedge counter advanced;
it now drives/samples the same opposite-edge registered ready. No RTL authority,
byte/sentinel, STOP/retire or valid-ICRC negative check is waived. Targeted
rechecks pass, including the final QP0/PD0/key0/PSN-edge context cases.

Separate previous-stage actual-HLS WRITE source compiled002is now terminal0:
463.04-second build and10.68-second finite execution, coherent C WQE/SAME-MR/
HLS/executor/paged-PCIe to one65-byte-verified IP packet. Full key0/VA64/QPN/PSN,
padding, IPv4/ICRC, hierarchy, source/artifact/binary hashes are verified. Its
three actual HLS cores are the original initiator + protected responder + new
source. Physical host/link/final wire-CQ are MODELS. This is additional TWO-
STATE execution ONLY: not X/Z/reset/four-state signoff, not peer ACK/READ
placement or real board communication. Earlier timeouts/failures remain intact.

Required next: bind this receive gate to actual shared native HLS transport
and real issued-PSN/wire/MAC/CQ lifetime, keep real READ payload/fence/ACK error
ordering, implement retries/replay/NAK/RNR/abort/flush, broader operations and
standard kernel/userspace RDMA lifecycle. One-WR/one-response/nonzero<=4096B
is a prototype, NOT a narrower final goal. Resulting FULL-board original-clock
setup/hold/pulse/skew/routing/DRC/check_timing/conditional-CDC and short supervised
hardware gates remain mandatory. No clock/path/capacity/physical gate waived.

No FPGA programming/JTAG, driver installation/loading/probing, real traffic,
fan/BIOS/network/other-device/reset/reboot, commit or push occurs. Exact Codex
thread/goal restoration after reboot remains unproven; none is needed now.
