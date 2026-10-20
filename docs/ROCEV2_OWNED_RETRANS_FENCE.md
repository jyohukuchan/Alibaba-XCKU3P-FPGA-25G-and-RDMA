# Real retransmission subsystem boundary fence

Progress043 now adds an opt-in ACTUAL owned timer producer driven by real
insert/ACK/head/replay controls, removes external timer injection and joins
its real state as a sixth response using ordered two-phase closure. This is
still NOT full wire-producer/shared-core/MAC/DMA/native CQ retirement. See
`ROCEV2_OWNED_TIMER.md`. The original Progress042 scope below is retained.

Progress042 adds an opt-in fence on the ACTUAL owned retransmission process,
pointer/lock BRAM,2000metadata records, real pool and actual output handoffs.
It is NOT a whole shared-HLS/MAC/DMA/native/CQ retirement certificate.
Progress041 sources and the original licensed FNS prefix remain untouched;
this derivative is not selected in the shared/native/board parent.

## What actually closes and acknowledges

Four input streams (insert, update, RX retry, timer retry) each carry their
own same-queue marker with full168-bit QPN/PSN/epoch/sequence. Full tokens
must agree, QPN<8 and epoch/sequence nonzero. Markers are not inferred from
idleness. A marked input stays closed through GENUINE external fence-response
acceptance. Raw/decoded FIFO buffering of later data is not execution/admission.
An actual retained insert at credit0cannot hide ACK processing or allow its
later same-queue marker to overtake it.

After all four arrive and earlier actual work finishes, the process FSM ITSELF
emits seven ordered markers: pointer request+update, metadata request, pool
allocate+release, event and READ-address output. There is NO test pool mux in
`rocev2_owned_retrans_fenced.v`. Five real acknowledgements are required:

- The actual pointer consumer observes BOTH queue markers, then samples the
  real addressed QP entry/global lock/wait. Existing ordinary update priority
  is preserved, including an update still queued before its head register.
- The actual metadata consumer stops behind its same-queue marker and reads
  ALL2000full records. The actual data digest and read count are returned and
  propagated externally so reads cannot disappear as unused logic. Digest is
  NOT cryptographic ownership, nor is leftover metadata.valid an active bit.
  Real same-index memory dependencies remain; no false-dependency waiver.
- The unchanged real pool consumes BOTH actual process producer markers and
  scans actual lease RAM. Exact token/status/qualified counts are checked.
- Event/RDinit markers sit behind every earlier normal item in those exact
  output queues. The production RTL wrapper removes each marker ONLY at the
  actual raw AXIS head, after earlier real normal transfers. Private receipt
  registers return the exact tokens to the process. No external idle/drain
  success input, diagnostic allocator mux or fake output receipt is used.

Status0 requires all these acknowledgements and no target-WR pool reservation
or QP pointer/lock/wait state. Status2means the ordered window is BUSY, not a
CQE, unpin permission or completed recovery. Other-WR pool reservations may
remain; global/free counts are honest. Pointer's global lock check can be
conservative for unrelated QPs. This is a globally closed prototype window,
not a claim of scalable per-QP concurrent retirement or product parity.

An HLS AXIS buffered write is NOT external acceptance. After writing a fence
response the process waits for the wrapper's private receipt generated ONLY
by the actual external response handshake. It cannot reopen its four input
windows just because the response entered an internal AXIS register.

Even status0 covers only this subsystem's handoff boundary: downstream TX/MAC,
READ receiver, memory/DMA/PCIe, other timers/state producers and their queued
owners can still hold work. Genuine upstream full-WR context/marker injection
in the full FNS RX/TX/timer graph, joins with all other owners and native CQ /
driver/provider remain incomplete. `local_core_drained` stays0 and existing
shared WR/MR references stay held. Local reset is NOT safe runtime flush or
hard-reconfiguration/power-loss recovery.

## Private candidate encoding

Normal Progress041 fields are retained. Insert416 marker399,reserved415:400=0;
on marker all normal payload fields270:40must be0. Update224 marker200,
reserved223:201=0; marker opcode must0. Retry/timer192 marker168,
reserved191:169=0. QPN/PSN/epoch/sequence occupy their original fields.

Internal raw event576 marker575 and raw RDinit320 marker319 carry owner168
in167:0 and otherwise0. They are removed by the production wrapper and never
exposed as normal events/addresses. Private actual-handshake receipts are
192-bit owner168 with24reserved zero bits. These are not public host controls.

External diagnostic fence320: owner167:0,status175:168,input_seen179:176,
reply_seen184:180,qualified185,pool_owner197:186,pool_global209:198,
pool_free221:210,metadata_digest285:222,metadata_reads297:286,
pointer{wait,lock,valid}300:298,metadata_qualified301,reserved319:302=0.
Qualified0is never substituted for missing acknowledgements. Fault11is bad /
mismatched input marker;12is bad downstream token/status/receipt. Original
normal-path errors are retained. Fault quarantine is not safe recovery.

## Evidence and retained limitations

HLS003 (`owned-retrans-fence-oynaqpvk`) uses original4ns/all8QP/2000slots,
70BRAM18K/11311FF/12136LUT/0DSP/0URAM, estimate3.613ns. Initial001was4.610ns.
Registered real pointer/meta queue heads and bounded8-bit opcode comparison
reduce the actual paths; no clock/uncertainty/range/owner/capacity cuts.
Warnings remain against2.920ns effective budget after1.080ns uncertainty.
This is NOT placed/routed/full-board timing/CDC signoff. A whitespace-anchor
preflight attempt002failed before compilation; original copied inputs remain
in `owned-retrans-fence-5rr5vma6`, no HLS002report was produced. It is not a
successful build. Exact001/003sources/logs are retained.

Current RTL002's five genuine production-wrapper FOUR-STATE cases verify:

- Actual pool scan/zero while real event output is HELD: no fence response.
  After genuine handoff, exact metadata digest and qualified clear response.
  Later real insert stays blocked while that response is HELD in registered
  AXIS output, executes only AFTER genuine acceptance, and honestly remains
  active at finite test end.
- READ4161metadata FIRST→LAST/FFFFFF→0/full immutable lease. After event
  handoff and actual pool zero, held real RDinit still prevents response.
  Genuine RDinit handoff permits the exact current-record digest response.
  This is NOT4161-byte payload/native DMA/CQ completion.
- Actual active pointer/lease returns BUSY without freeing anything; after
  real ACK the SAME WR can create a NEW two-marker pool/metadata window and
  receive clear. Both real pool scans and new receipts are observed.
- Missing fourth input marker never emits downstream markers or response;
  full-token disagreement / malformed marker payload yields fault11, no fake
  completion. Finite silence is a negative test, not success authority.

Each four-state case is bounded30s; observed longest28.018s. Initial RTL001
passed ordinary WRITE/READ but its fullpool Icarus case hit30s, so overall001
FAILED and remains retained. The limit was NOT raised or assertions weakened.
Ordinary fullpool/stale/linked regressions are additionally compiled with
Verilator, explicitly TWO-STATE, not replacement X/Z/reset/physical proof.
All six current regressions pass, including actual fullpool ACK/reuse and
stale ACK/retry/fullQPN/linked-record protection; each0.305..1.584s. The five
four-state cases and these six two-state cases are SEPARATE proof scopes,
not eleven four-state tests or a native/whole-core runtime test.
Input producers in all benches are models; full upstream producer closure
is not claimed. No forced DUT state or fake RAM/allocator was introduced.
Four structural derivation tests pass separately and do not replace RTL.

Source/offline only: no FPGA programming/JTAG/traffic/temperature measurement,
module install/load/probe, fan/BIOS/network/reset/reboot/commit/push/deletion.
All existing failed physical gates and READ/WRITE rollback remain intact.
