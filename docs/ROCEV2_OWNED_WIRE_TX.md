# Actual FNS transmit producers with per-WR context

Progress047adds a separate actual same-table RX owner lookup/process/timer /
realpool candidate. It is NOT joined to THIS TX producer graph or native /
board/shared parent; trusted packet/QP epoch and actual RX IBH/EXH consumers
remain. Seven scoped FOUR-STATE cases pass, full2000live lookup not qualified,
HLS4.644ns UNMET. THIS TXHLS0023.964ns proof remains unchanged. See
`ROCEV2_RX_OWNER_LOOKUP.md`; no new CQ/retirement or full-wire claim.

Progress046 replaces only the selected EXH word-consumer arithmetic with
constant word cases, preserving its COMPLETE original16-bit index, unused
partial-word lanes and header/ready state. Exhaustive C++ differential checks
against the unchanged licensed original cover all65536indices at widths32,
64,128,256,512 for both128-bit RETH and32-bit AETH:655360comparisons in two
short cases. Whole candidate HLS002improves5.896→3.964ns, EXH3.921ns, original
4ns unchanged. Effective2.920ns warnings remain, NOT physical signoff.
Current scopes are C++00316cases, source0027units and generated RTL0035
FOUR-STATE cases with12AXIS hold monitors, including actual ACK/AETH output.
The earlier045results are retained history, not current-source replacements.

Progress045 starts binding the actual wire producers to the owned
retransmission work, rather than reconstructing an owner from a late QP
lookup. This is an opt-in TX candidate, NOT a selected shared/native/board
implementation or a completed RNIC. The original licensed FNS inputs and
Progress041–044 candidates remain unchanged.

## What is implemented

`owned_wire_tx_profile.py` derives complete actual `local_req_handler`,
`meta_merger`, `generate_ibh`, `generate_exh` and `merge_retrans_request`
function bodies from the frozen per-WR FNS source. Their original fields /
constructors and licensed notice are retained in new named types. Commented
braces and quoted debug strings are excluded from C++ scope extraction.
This is not a new behavioral model replacing the original producer actions.

An existing248-bit SQ record is paired with a192-bit trusted internal context:
QPN15:0, epoch79:16, sequence143:80, reserved191:144=0. Padding in the SQ record
must also be zero. QPN must be in the full original8-entry range and agree
with the SQ, and both64-bit epoch/sequence must be nonzero. The port MUST
eventually come from real native admission/ownership; checking its contents
is NOT proof that its presently external source is authenticated or pinned.

The same immutable context follows both actual local READ and WRITE/SEND
branches through event arbitration. The actual generated BTH/PSN path and
the independent local-address/remote-address/length path each carry it.
The real merge compares full QPN/epoch/sequence/valid/retry/lease identity
before emitting an `as02OwnedInsert`. A mismatch quarantines that merge and
does not register metadata, free memory, produce a CQE or accept later work.
No current-owner QP lookup supplies a replacement identity.

Actual retry input is the owned event containing its original248-bit lease.
The local handler validates QPN/full64-bit generation/epoch/sequence/index /
validPSN, retains that lease through event/BTH/EXH selection, and preserves
explicit key validity/key0 and host-memory selection. Retry validPSN bypasses
new PSN allocation and does not create another insertion. Fence markers are
REFUSED, not silently treated as normal events or falsely acknowledged.

The original `generate_exh` start position/condition now emits the full owner,
not bare QPN. For a first transmission it still has no allocated lease.
This is NOT MAC SFD and is NOT yet joined to real allocation/commit or wired
into the current owned timer. The original SEND omission in that start
condition is still open; general SEND/RECV completion is not claimed. Zero
length READ is explicitly fail-closed pending its proper semantics. Unsupported
operations do not create the old unmatched address record. These are remaining
requirements, not reductions of the general RoCE objective.

## Short, separate verification scopes

- Current C++003:16 independently bounded cases, total0.538s, each<0.298s.
  First14retain all prior cases; two added cases compare the new word
  consumer against the actual original across ALL65536indices at five widths
  for RETH and AETH. They include out-of-range indices, arbitrary before-word
  contents and both ready values; no index truncation/range assumption. Each
  call compares output, remaining count, full index, header and ready state.
  Four actual positive READ/WRITE requests include same-QP different WRs,
  QPN7and0, full-width epochs/sequences, explicit keys0/FFFFFFFF, READ4161
  metadata and actual24-bit PSN wrap. Actual BTH/RETH fields, original host
  address commands and complete insertion owners are checked. Other cases
  refuse mismatched epoch/sequence, missing context, malformed reserved bits,
  wrong QP, epoch/sequence0, bad retry generation and a marker. Valid actual
  replay preserves its full lease. These are actual function C++ checks,
  not an RTL FIFO-stall/X/Z/native-pins or large-payload DMA test.
- Seven derivation units002pass0.305s and freeze exact sources. They check the
  original fields/constructors, full licensed five actual producer bodies,
  exact owner-copy/PSN-join/start anchors, fail-closed missing anchors and
  unchanged4ns clock, complete index comparison, partial-lane semantics and
  all four actual RETH/AETH call sites. They are source invariants, not RTL tests.
- Current HLS002 constructs ONE new TX producer graph, original KU3P-1/4ns,
 8651FF/5630LUT/0BRAM/0DSP/0URAM. Estimate3.964ns is below the original period
  but NOT effective2.920ns timing or physical signoff; warnings remain. The
  EXH estimate improves5.896→3.921ns after removing the generic16-bit carry /
  subtraction chain. Full original16-bit input is compared in source; HLS
  can optimize provably reachable local states, not an explicit index/range cut.
  HLS0015.896ns remains historical **UNMET**, not promoted into a timing pass.
  No placement/routing/setup/hold/pulse/skew/CDC/DRC signoff is implied.
- Current generated RTL003:FOUR-STATE Icarus, five independently bounded cases,
  0.184..0.307s each, total1.122s. Actual uninitialized-reg X and undriven-tri Z calibration;
  real reset edge; original4ns clock. The positive case delays trusted-context
  arrival, holds insertion output until cycle200, and independently stalls
  the other outputs. Four requests produce four exact complete owner-bound
  insertions, four BTHs, eight RETH words and matching start/address/PSN/key /
  length/packet information. Three denied-context cases have no output side
  effects. Added ACK uses actual meta-merger/IBH/EXH, valid PSN, one AETH word
  with exactly4valid bytes, no new requester PSN/allocation/start/owner. Only
  valid AETH lanes are packet data; original unused output lanes are preserved,
  not reset-X masked or forced. Twelve passive monitors check valid/data
  stability while stalled on all10outputs and SQ/context inputs. Full-field
  independent expectations for original full-valid words,3000cycle and30s wall bounds
  remain. The generated RTL/binary/source hashes are checked before/after
  every run. No DUT force, reset-X masking or assertion waiver is used.

The top currently exposes typed HLS aggregate ports with padding, not the
existing416/192-bit outer timer codec ABI. Direct shared-HLS typed wiring or
explicit checked codecs must be implemented, never connected by truncation.
External QP-state/MSN/destination responders in the RTL bench are MODELS;
there is no native SQ, actual remote peer/MAC/payload DMA, actual timer/pool
join, RX ownership lookup, complete upstream fence, CQ or host unpin proof.
The retry/marker cases are C++ only; the five generated-RTL cases must not be
misrepresented as the entire16-case C++ coverage or full RX/TX core proof.

Original045C++00214cases, source0016units, HLS0015.896ns and RTL0014cases stay
retained with exact frozen source/binary/report identities, not current-source
proof. Intermediate RTL002passes the same new5functional cases but its old
summary counter labels the ACK AETH as RETH. Current003corrects EXH/RETH/AETH
diagnostic counters and adds12passive hold monitors, then freshly compiles /
runs the identical HLS002RTL; no assertions or wall/cycle bounds are removed.

Initial C++001 is retained FAILED:12 cases were recorded before upstream
`std::hex` caused case13's JSON case number to print `d`. Actual assertions
in that case completed, but the report parser rightly rejected it. Only the
test-summary stream was changed to explicit decimal; fresh002compiles and
runs all14cases. Original failed report/source/binary/logs remain intact.

## Next required work and protected state

Propagate real native admitted context and the actual RX IBH/EXH owner lookup
and ordered markers. Further scheduling/physical margin is still required;
3.964ns estimate with effective-budget warnings is not a release gate. Do not
relax original clock/uncertainty/protection. Join actual allocation /
commit/start/replay to the same timer/process/pool graph inside ONE shared
HLS/native parent. Downstream MAC/memory/PCIe/CQ owners and full resulting
board physical/conditional-CDC gates remain required. Existing failed physical
records remain failed; `local_core_drained=0`, WR/MR references held, all11
requirements intact. No fake/default-success completion or payload CPU-copy
substitute is introduced.

Source/offline only: no hardware/JTAG/programming/flash/module install-load /
probe/real traffic/fan/BIOS/network/reset/reboot/commit/push/deletion. BIOS
Medium, management/other devices and old READ/WRITE rollback are unchanged.
Disk2.7GiB free/98%; check before larger builds, do not silently delete evidence.
No reboot is currently needed; exact authenticated thread/goal restoration
remains UNPROVEN. Feature builds permitted; tests remain short and bounded.
