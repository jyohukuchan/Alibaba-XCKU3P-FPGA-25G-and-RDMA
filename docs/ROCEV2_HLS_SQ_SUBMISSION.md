# Guarded native WQE ownership before per-WR HLS submission

Progress029implements real hardware metadata/ownership staging and fixes an
independent BTH MigReq receive-compatibility defect. It does NOT complete the
local HLS memory executor, protected ACK/READ-response ingress, actual wire/
memory/MAC/CQ lifetime, kernel/userspace verbs, board selection or hardware.

## Actual native staging

`rocev2_wqe_hls_sq` accepts the complete588-bit trusted work tuple from actual
native coherent-SQ/SAME-MR admission. It validates complete known identity,
QPN bounds before narrowing, epoch/sequence/tag, authorization/error shape,
opcode/flags/length and65-bit local/offset/remote interval ends. No separate
MR table, software permission fallback or CPU payload copy is introduced.

Order is mandatory: capture the authorized work; hand its complete context
to a real executor whose per-QP guard is ALREADY asserted; only then offer
HLS the SQ. The receiver's guard must continue across SQ acceptance through
real execution/wire/CQ ownership. SQ acceptance ends only the staging lease,
NEVER the WR or pinned-page lifetime. Denied/failed-fetch work transfers its
full error/identity to an error-owner path but produces no HLS SQ. Descriptor
unavailable/WR_ID0still requires the trusted queue shadow, not invented CQEs.

The output is the ACTUAL248-bit per-WR HLS ABI, not a legacy240-bit record:

| Bits | Field |
| --- | --- |
|247:241|Zero padding|
|240|Remote-key valid=1, including key0|
|239:208|Complete per-WR remote key32|
|207:176|Length32|
|175:112|Remote VA64|
|111:48|Local VA64|
|47:44|Offset metadata0|
|43:42|Last1/host1, for both WRITE source and READ destination|
|41:32|Validated QPN10|
|31:0|WRITE_ONLY10or READ_REQUEST12|

Context and already-offered SQ remain stable through backpressure, disable
and faults. Halt prevents a NEW SQ offer, not withdrawal of one already seen
by HLS. A missing/lost downstream guard, unknown or malformed trusted context
causes sticky fault and retained guards; no fake completion/drain/recovery.
Current1SGE/nonzero1..4096prototype limits are not a reduction of the broader
zero/large/multi-SGE/operation requirements. Exclusive interval end2^64remains
legal, actual overflow does not.

Static `HLS_SQ_ENABLE=0` retains the existing external work-owner interface.
Enabled mode requires the shared payload memory path, inserts this producer
INSIDE `rocev2_native_sq_endpoint`, and supplies executor context plus keyed
SQ streams. Existing work fields become diagnostic; external m_work_ready
is ignored in this mode. New m_work_handoff always reports actual capture.
Submission guards join actual MR/PTE/route/SQ-retire exclusion. Native MR
management pause cannot deadlock an already-authorized owner handoff.

The streams still need binding to the existing transport/core and a genuine
local memory/ACK/READ-response/wire/CQ controller. They are private internal
ports, not an arbitrary user-DMA BAR or standard RNIC capability. The actual
mqnic app/board parent still selects the legacy default profile. No new empty
ib_device, default-success callback or capability advertisement is supplied.

## Bounded evidence and scope separation

`wqe-hls-sq-unit-001` passes7four-state methods/19simulations. Work authorization,
executor and HLS are MODELS. Complete high/zero keys, addresses, QPN0/7, PD0/
65535and16metadata combinations, all15fetch errors, denied/unknown/overflow
records, owner handoff gaps, lost guards, halt and stable offered SQ are checked.

Native control/SQ/MR units enable the option in the actual coherent-SQ/AXI/
MR/PTE/shared-backend/router/mux/generic-PCIe/parent-guard hierarchy. Actual C/
UBSan bytes are fetched, then real SAME-MR authorization precedes full guarded
context and keyed SQ. A second case invalidates the key during real inflight
SQ fetch; the denied owner is retained with no HLS submission. STOP/route/
early retire remain excluded through context/SQ/downstream modeled handoff;
fetch or SQ acceptance is not CQ completion. HLS and executor/CQ are explicitly
MODELS in those native units, not actual local wire/DMA execution.

Separate `wqe-hls-wire-{write,read}-004` leaves execute this same producer with
the EXACT unchanged generated per-WR HLS: one real248-bit SQ, actual per-WR
adapter, padding and IPv4/ICRC. Each produces one independently checked packet
in approximately22.7..23.0seconds. Actual C/UBSan WQE bytes feed the producer;
authorization, source memory and downstream WR/CQ are MODELS. The downstream
guard intentionally stays held until test end: no peer ACK, native DMA or
completion is fabricated. WRITE checks65source bytes; READ is request
generation ONLY, not receive placement. Zero remote key is NOT the configured
nonzero QP fallback; full VA64/QPN/PSN/length/header/pad/checksums are checked.

These two scopes are complementary, NOT one unified native WQE-to-HLS-to-DMA-
to-wire/CQ integration proof. Full local HLS command binding and authenticated
receive placement remain required. The original multi-WR HLS benches remain
unchanged; these are new bounded single-WR cases with explicit scope.

## MigReq compatibility correction, not path migration

The new leaf's stronger header check initially rejected existing HLS output
flags0x70(WRITE with3pad bytes) and0x40(READ). Both carry MigReq1. Linuxv6.17
defines MigReq as BTH flag0x40, distinct from pad0x30and transport version0x0f;
it is not reserved. See [RXE header definitions](https://github.com/torvalds/linux/blob/v6.17/drivers/infiniband/sw/rxe/rxe_hdr.h)
and [kernel BTH definitions](https://github.com/torvalds/linux/blob/v6.17/include/rdma/ib_hdrs.h).

The diagnosis also found the same error in the actual incoming protected
parser: its old0xcfmask rejected every M1packet before MR. The parser now
permits M0/M1while preserving current SE0/TVer0policy, PKey/pad/length and all
integrity/peer/QP/PSN/PD/key/permission/VA-range gates. A packet flag cannot
change the privileged trusted peer context; actual path migration is NOT
implemented or advertised. The outgoing-leaf validator now checks the actual
expected M1flag explicitly instead of silently treating it as reserved.

`bth-migration-diagnosis-001` preserves original parser/header hashes, actual
HLS packet flags and primary sources. `bth-migreq-unit-001` passes3four-state
methods using actual parser/MR/ICRC with an EXPLICIT HLS/backend model: M0/M1
READ/WRITE, TVer/SE rejection, all8authority/shape rejections and an ICRC drop.

Actual-HLS positive001passes M0WRITE/M1READ/M1WRITE/M0READ with4wire replies,
130WRITE/130READ bytes in41.09seconds. Protection001passes8actual rejections
and1ICRC drop, then M1WRITE/M1READ with2wire replies/65bytes each in35.83seconds.
Peer QPN/PSN/ACK, all READ/WRITE bytes, IPv4/ICRC and deferred backend status
are checked. Memory visibility and peer remain MODELS, not native DMA/runtime.
No compatibility assertion is waived to make M1pass.

Preserved failures: native-hls-sq-unit001used the old external-ready stall
monitor even though enabled mode captures internally; it now observes the
real m_work_handoff, retaining all stability/owner checks. Initial leaf001
never executed due Python syntax errors. Leaf003WRITE/READ failed the wrong
MigReq-as-reserved validator; actual packets and failed reports remain intact.
Intermediate002leaf passes and native002/003passes are historical after later
source/validation changes, not silently promoted to current-source evidence.

All resulting full-board original-clock timing/routing/DRC/conditional-CDC
and short thermally supervised native gates remain required. Frozen negative
CAD reports do not qualify this source. No programming, driver install/load,
live traffic, fan/BIOS/network change, reboot, commit or push occurs here.

Final portable036passes281methods in456.483seconds, including fresh source-
bound native-hls-sq-unit004/native-sq-unit005/native-memory-unit005/native-
shared-mr-unit002/BTH-unit002and WQE-HLS-SQ-unit002records. Source-checks040
passes7batches/64methods. Fresh shared MR/paged rechecks pass7methods in
72.702seconds. Default actual parent compile015passes with original warnings
retained (new native-SQ/HLS option NOT selected). Legacy READ006/WRITE006each
retain one65-byte operation in67.24/69.04seconds. Pre-MigReq-fix portable035
passed278methods/420.257seconds but is a historical intermediate, not the
current final batch. No current negative physical gate is waived or inherited.
