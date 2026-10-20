# Same-table receive owner lookup

Progress048 derives a SEPARATE composition feeding this same-table service
from actual FNS BTH/EXH packet bytes/full syndrome, with retained full frame,
raw headers and actual external metadata/body/fence receipts. Ten short
FOUR-STATE cases pass; HLS10.256ns UNMET at original4ns. This does not change
the Progress047 candidate or qualify its missing full2000-live case. Trusted
native packet admission/effectful RX/MAC/DMA/CQ/shared selection still remain.
See `ROCEV2_OWNED_WIRE_RX.md` for exact interface and lifetime limitations.

Progress047 adds an opt-in lookup service to the ACTUAL owned retransmission
process, its ONE8-entry pointer table, ONE2000-entry metadata table, actual
timer and real lease allocator. It is not a shadow QP→current-WR owner table.
The original FNS/Progress041–046 sources, generated rollback and board/native
selection remain unchanged. This is NOT the completed wire RX path or RNIC.

## Identity, traversal and lifetime

Normal queries contain full24-bit QPN, PSN24, opcode8, epoch64, complete AETH
syndrome8 and has-AETH. The epoch MUST come from real packet/connection
admission; it is not present on wire, and nonzero validation does not prove
that this presently external source is trusted. Native admission, connection
validation and safe PSN/QP reuse/epoch recovery remain required.

The process locks and reads the actual QP pointer entry, then traverses the
actual linked metadata through its existing request/response queue. It checks
index, full248-bit lease, nonzero64-bit generation/epoch/sequence, exact QPN,
epoch consistency, strictly increasing generation and nondecreasing WR
sequence, next/tail coherence and the original2000-record bound. It scans to
the real tail even AFTER a match. Zero matches yields NO_MATCH; multiple
matching records yields AMBIGUOUS with NO selected lease. A different admitted
epoch yields EPOCH_MISMATCH without retagging the packet to the current head.

READ spans use the actual current mutable metadata PSN/remaining length,
widened to33bits BEFORE length rounding. PSN deltas are modular24-bit; the
full32-bit lengthFFFFFFFF is not shortened or overflowed. The immutable
original lease/PSN remains unchanged across actual FIRST progress. A normal
ACK does not bind a READ request as a WRITE completion. RNR/NAK syndrome bytes
can identify their underlying owner but remain OPAQUE protocol controls,
never interpreted by this lookup as success, retry policy, timer clear or CQ.
Zero READ and other required operation semantics are still open, not removed
from the goal.

The exact result is held until a genuine external valid/ready transfer.
`rocev2_owned_rx_lookup.v` privately echoes that exact448-bit result; there is
NO externally injectable receipt port. The actual process verifies the echo
before unlocking its table pointer with the exact unchanged entry. A queued
ACK/update cannot run while the binding is merely buffered or stalled.

Lookup performs NO metadata write, allocation return, timer clear, RDinit,
payload DMA, CQE, MR/QP release or unpin. After response acceptance, a future
RX consumer must retain/validate the full context and join genuine per-WR
ownership; this service is not itself a new lifetime grant. A non-head match
must NOT be blindly converted into the old head-only update: coalesced ACK
commit, actual RX IBH/EXH decisions and downstream owners still need binding.
Persistent `metadata.valid` alone never means active ownership: actual empty
pointer roots return NO_MATCH even though freed metadata remains initialized.

## Wire ABI and ordered boundary

Query320 bits:

| Bits | Field |
|---|---|
| 23:0 /47:24 /55:48 | QPN /PSN /opcode |
| 119:56 /127:120 /128 | trusted epoch /full syndrome /has-AETH |
| 129 /297:130 | same-queue marker /full168-bit marker owner |
| 319:298 | must be0 |

Binding448 bits:

| Bits | Field |
|---|---|
| 247:0 | selected immutable lease, ONLY on UNIQUE |
| 271:248 /295:272 /303:296 /367:304 | exact query QPN /PSN /opcode /epoch |
| 391:368 /399:392 /411:400 | READ delta /lookup status /records visited |
| 419:412 /420 /421 /422 | full syndrome /has-AETH /is-head /lookup qualified |
| 447:423 | 0 |

Status0=UNIQUE,1=NO_MATCH,2=AMBIGUOUS,3=EPOCH_MISMATCH. UNIQUE is identity
lookup only, NOT packet authorization, an ACK success or a completion.

The real process now requires a FIFTH same-queue query-input marker. Four old
input closures alone cannot close scanning or produce a successful boundary
response while queries remain. Original real timer's two-phase cycle break
and six consumer receipts remain; fence bit310 additionally certifies query
closure. The wrapper checks this bit and only genuine external fence
acceptance reopens the input window. This is a scoped boundary, NOT complete
actual wire-producer closure, whole-core/MAC/memory/PCIe/CQ retirement.

## Bounded evidence and retained failures

- Current HLS002 constructs actual8-QP/2000-metadata lookup/process/timer at
  original KU3P-1/4ns:70BRAM18K/23661FF/24225LUT. Estimate4.644ns is **UNMET**;
  no timing/physical/CDC signoff. The complete original licensed header and
  original table implementations remain retained; no capacity/protection cuts.
- Seven source units002pass0.042s with frozen fixtures. Same real table paths,
  complete identities, traversal/ambiguity/span checks, fifth marker, private
  actual handshake receipts and no lookup retirement verified structurally.
  These are not RTL or native-host proof.
- Current XSIM003 freshly compiles exact HLS002 plus the real production
  wrapper/pool and runs SEVEN separately bounded FOUR-STATE cases. Full X-reg /
  Z-tri calibration, real reset and original4ns/30s wall bounds. They cover
  non-head identity and held lookup blocking a queued real ACK, genuine head
  advancement/pool return followed by NO_MATCH, real READ progress across PSN
  wrap retaining the original lease, fullFFFFFFFF length endpoint, ambiguous
  records and stale epoch, refusing24-bit QPN010002 instead of truncating to2,
  missing fifth marker/BUSY fence/genuine fence acceptance, and preserving
  RNR20/NAK60 without a return or completion. Query fields are TEST STIMULI,
  not actual packet/native admission. No pool test mux or forced DUT state.

The full2000-live-record traversal case8 is **NOT qualified**. Initial XSIM001
records seven passing cases, then exceeds its UNCHANGED30s wall bound on case8;
the OVERALL report remains FAILED, never promoted. A separate bounded,
read-only exact-kernel diagnostic observes real progress through24us:cycle5992,
76insertions/77active allocations, no releases/events/bindings. It is not a
full capacity pass or evidence of hardware failure. The100us diagnostic also
hits30s and remains incomplete. Current003 explicitly requests1–7, omits8,
and reports `full_eight_case_suite_pass=false`; it is not an eight-case pass.
The full geometry remains implemented and required; no long test bound was
increased or component capacity reduced to get green results.

Additional compiled TWO-STATE001 fails before its first completed case with
"Active region did not converge." This does not qualify capacity or replace
the FOUR-STATE evidence; root cause remains unresolved. Copied-kernel XSIM002
executes case1 but overall fails its strict snapshot check because copied
runtime `xsim_script.tcl`/`xsimkernel.log` change. That failed report is retained,
not waived; current003 uses a FRESH compile and exact immutable build-file
hashes. No assertion/severity/clock/identity weakening is used.

HLS001 is retained FAILED at C++ compilation: ambiguous signed36-bit versus
unsigned33-bit ternary types. The corrected source uses an explicit widened
33-bit rounding assignment; fresh002constructs. No function test pass is
inferred from the original failed compile.

During read-only diagnostics XSIM rotated a generated operation journal.
Its exact original bytes were recovered from the retained per-case log and
matched the original SHA256; the prior main journal is also archived with its
exact original SHA. Failed reports remain unchanged, and later diagnostics
run in separate directories. Circuit/bench/output logs and compiled images
remain retained. The journal aliases are recorded by the evidence audit.

## Remaining actual objective

Connect actual RX IBH/EXH and genuine trusted packet/QP epoch capture to these
queries; join exact immutable binding to actual decision/receive placement /
coalesced ACK and per-WR ownership. Then select ONE shared MR/native SQ/PTE /
PCIe/MAC/timer/process/pool graph, implement real standard driver/CQ/provider
and remaining operations/recovery, and meet the resulting ORIGINAL full-board
physical/conditional-CDC gates before short thermally supervised real tests.
All11requirements remain active. `local_core_drained=0`, WR/MR references held.

Source/offline only; no hardware/JTAG/programming/flash/module install-load /
probe/real traffic/fan/BIOS/network/reset/reboot/commit/push. BIOS Medium,
management/other devices and old READ/WRITE rollback remain unchanged. Disk
2.2GiB free/98%; check before larger builds, no silent source/evidence cleanup.
No reboot needed now; exact authenticated thread/goal restoration unproven.
