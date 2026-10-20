# Owned FNS retransmission process and real lease-pool binding

Progress042 adds a separate opt-in actual queue/consumer/output boundary fence
around this unchanged Progress041 process foundation. Genuine process FSM
pool-marker injection and actual external handoff/response receipts replace
test-only marker authority in that NEW composition. It is still NOT full
upstream/shared-core/MAC/DMA/native/CQ retirement. See
`ROCEV2_OWNED_RETRANS_FENCE.md`; original Progress041 scope below is retained.

Progress041 adds an opt-in real FNS-derived retransmission subsystem, not a
shadow metadata model or a synthetic allocator callback. The selected graph
contains one actual process FSM, the real8-entry pointer/lock table and the
real2000-entry metadata table. `rocev2_owned_retrans.v` connects its generated
HLS request/grant/return ports to `rocev2_retrans_pool.v`. No test allocator
mux, bare-index free or default-success drain/CQ input exists in this wrapper.
It is NOT yet selected in the shared/native/board parent.

## Identity and actual state changes

The opt-in generator preserves the complete original licensed FNS header as
an unselected prefix. The original rollback/source selection is unchanged.
The selected derivative retains pointer locking, insertion/linked-list append,
actual metadata clear/write/append/read, partial READ mutation and retry walk.
All2000metadata slots and all8pointer entries are addressed during startup;
the selected metadata function removes the old false inter-dependency waiver.

Before allocation the process retains the insert record and full64-bit WR
epoch/sequence. Only an actual matching256-bit grant with successful status,
full valid index, nonzero generation and ALL168owner bits can start pointer /
metadata insertion. The metadata stores the FULL248-bit immutable lease:
{sequence64,epoch64,originalPSN24,QPN16,generation64,index16}. The actual event
and READ-address outputs also carry that stored lease, along with original
full key/key-valid/host/64-bit addresses/length/offset fields.

Protocol `meta.psn` changes during a segmented READ, includingFFFFFF→0, while
the allocation lease's original PSN does NOT. ACK/READ update checks stored
full WR context and the current protocol PSN before side effects. Partial READ
updates retain the lease through the real metadata write/copy. Final return
uses that immutable lease, not a reconstructed mutable PSN. Pointer update /
unlock is deferred until the EXACT real successful return acknowledgement.
Wrong old-WR ACKs or retries quarantine without freeing/replaying a new WR.

At actual pool credit0 the process must remain able to service updates: it
does not start waiting for an unfillable allocation. This process is the sole
production allocation-request producer in the wrapper. Test-only direct API
prefill is explicitly outside that production ownership rule. Future shared
producer admission/reset recovery must preserve that rule, not infer credits
or retirement from arbitrary external activity or quiet cycles.

Raw/decoded input registers and separate capture/check FSM states remove
the input-FIFO-read→full64-bit owner-check→action chain. No clocks, capacity,
keys, range/owner protection or physical gates are relaxed.

## Short offline evidence

Current HLS construction005 (`owned-retrans-yql9p4n2`) targets
xcku3p-ffvb676-1-e at the original4ns. Estimate improves4.642→3.965ns;
resources70BRAM18K/9698FF/6701LUT/0DSP/0URAM. II1 does not mean one complete
WR per clock. Scheduling warnings remain against the2.920ns effective budget
after1.080ns uncertainty. This is NOT placed/routed/full-board timing or CDC
signoff. Retained001failed on scalar feedback in HLS dataflow; replaced by
real fault streams.002actually generated RTL but FAILED its module-count
checker, which counted RAM children as extra function modules.003corrects
that checker;004registers inputs;005registers process capture/check phases.
Exact failed/intermediate inputs/logs remain retained, not promoted to passes.

Current generated FOUR-STATE RTL002 runs six bounded cases plus the actual
production wrapper (no diagnostic pool mux). Each simulation is below15s:

- WRITE65/key0/key-valid1/host1/full64-bit VAs and exact real timer event;
  ACK returns actual lease while that event remains HELD. Old WR retry is
  rejected after a newer WR takes the same QP.
- READ4161 metadata FIRST→LAST, actual address/length mutation and PSN wrap;
  final real pool acceptance proves immutable originalPSN survived. This is
  metadata/event behavior, NOT actual4161-byte payload DMA or native CQ.
- Real allocator API prefill1999slots, actual FNS insert consumes slot1999,
  second insert stays pending at free0, ACK returns the first lease, and the
  pending insert acquires that same index with a NEW generation2001.
  Prefill is not2000connections; foreign leases remain honestly active.
- Stale ACK with identical protocol PSN but OLD full WR sequence cannot free
  the newer record. Full QPNFFFF is rejected before any allocation.
- Two actual linked records for one WR, distinct PSNs/generations/indices,
  actual append/retry traversal and individual real ACK returns.
- Actual unmodified production wrapper performs WRITE and partial READ /
  final return with exact key0/full address/immutable-lease output checks.

FOUR-STATE simulations have no forced DUT state or fake RAM. Input producers
are bench models. Diagnostic marker injection in the six-case composition is
a TEST-ONLY allocator mux, NOT genuine upstream FNS producer closure. The
separate wrapper case has NO such mux. Current source derivation002 has four
structural tests; these are not a substitute for the actual RTL tests.

Historical derivation001's driver was reconstructed from the exact previous
source edit and verified against the hash already in that original report;
the matching copy is retained beside the results. It was not frozen during
that unit run. Its old profile/top are frozen in HLS003. Current002 checks
the actual current files, including the production wrapper.

## Deliberately incomplete scope

Actual pool zero is seen while REAL event/RDinit outputs are still VALID and
HELD. Therefore pool emptiness, metadata validity, ACK, an idle port or an
arbitrary delay CANNOT certify whole-core drain, CQ completion or MR unpin.
The shared core retains `local_core_drained=0` and actual WR/MR owners stay
held. Upstream full-context generation and genuine per-producer marker
injection, ordered pointer/metadata/timer/state/replay/event/output joins and
native parent propagation are still required. Private counters are diagnostic
only, not release authority. Local pool retention does not make a reset of
the process/tables into completed abort/flush/reconfiguration recovery.

The prototype accepts only an exact current ACK PSN/WR. General coalesced ACK
spans, mixed-WR retry walk, duplicate/loss/NAK/RNR recovery, wider SEND/RECV /
immediate/Atomic/zero/large/multi-SGE semantics remain FULL-goal requirements,
not exclusions or capability advertisements. A rejected stale request is
quarantine, not completed recovery. Real kernel pinned memory/ib_device /
standard queues/provider/CQ and resulting full-board physical qualification
remain incomplete. No FPGA/JTAG/programming/traffic/temperature measurement,
module install/load/probe, network/fan/BIOS/reset/reboot/commit/push occurred.
