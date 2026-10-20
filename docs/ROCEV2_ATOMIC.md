# RC64 Atomic candidate execution

Progress081 adds a real **responder memory execution** feature, not complete
native Atomic support. Default native RTL and `IB_ATOMIC_NONE` are unchanged.
The original protected responder, legacy images, clocks and all timing/drain
gates are untouched. Nothing is programmed, installed or loaded.

## Owned consumed-core completion (084)

`atomic_owned_transport.py` adds a checked full-core derivative, retaining the
082 source/raw core and083 composition as rollback. The actual packet guard's
immutable144-bit `{nonce32,requestPSN24,epoch64,QPN24}` now enters RX-IBH and
travels through RX-EXH, the512-bit request, actual protected RTL service and
392-bit response. The new registered owned adapter preserves the whole token
and execution/reply offers under disable/backpressure. It does not look up a
mutable current packet at service time. Four-state tests cover registered
offers, full/unknown/stale identity and executor response rejection.

Both RX consumers keep their existing owners. RX-EXH writes MSN only on fresh
execution, then queries and reads back the SAME table on its existing ordered
channel. RX-IBH similarly writes and reads back the SAME responder EPSN before
exporting a224-bit completion: owner144,originalOpcode8,actualEPSN24,
actualMSN24,flags8,error8,reserved8. Flags0/1/2 prove service consumption and
the two readbacks; flag3 means a response is expected,4 fresh advancement,
5 a proven no-packet drop. No new PSN/MSN table or fake RQ/native owner exists.
A cached replay can send an old AETH MSN while this receipt correctly reports
the current unchanged common MSN.

Actual complete HLS C++ plus actual Atomic/MR/PTE/paged DMA/RAM RTL PASSES9
Atomic jobs, normal SEND/two WRITEs and two QPs in0.293seconds. Stopping the MSN
consumer, then PSN consumer, withholds all completions until their real reads
finish. Drop emits a real core receipt and permits later normal/Atomic work.
Both unchanged Immediate TX/RX consumers also PASS on this complete new source.
These C++/RTL results alone are not generated-RTL/native/physical completion
claims; the separate generated-core results follow below.

Complete owned HLS synthesis001 PASS confirms512/392/144/224-bit service,
owner and done ports alongside unchanged existing native owner ports. It uses
59092LUT/84144FF/166BRAM18K/0DSP. The original4.00ns target and1.08ns
uncertainty are verified in generated XML; estimate13.568ns still MISSES the
target, so this is not board timing signoff or permission to program hardware.

Generated composition002 now PASSES4 actual-RTL cases in2.72/1.92/2.17/2.17s.
Case0 processes11 owned service requests on2QPs, emits11 genuine core receipts
and10 actual IP/UDP/checksum/ICRC packets, executes7/replays2/sequence-NAKs1/
drops1, and accepts all11 modeled-boundary retirements. The drop produces no
packet, reads back currentEPSN3/MSN5 with its own nonce10, then the next FADD
nonce11 advancesEPSN4/MSN6 and succeeds. Independent Python checks every
response and every actual owner/current-state completion, including cached
old wire MSN versus current readback MSN. Case1 denies MR with no DMA;case2
failed memory fence yields no service/core/wire completion;case3 flips one
actual returned nonce bit and actual HLS refuses it, preserving the packet
lease and producing no core/wire completion. Positive MAC/physical descriptor/
host ordering boundaries remain explicit MODELS, not actual native or board
proof. The raw per-case fixture capability flag for drop is constant; only
case0 actually exercises/proves the drop branch.

Diagnostic001 failed because the test scoreboard's previous `core_seen` flag
was still set before the next owner arrived; this was not a core receipt for
the drop. Clearing it on the preceding explicit retirement fixes that test
wait, without relaxing any proof. Exact pre-fix fixture/launcher, failed run,
binary and logs are retained.002 freshly translates RTL and reruns every case;
only byte-identical generated compiler inputs may reuse objects, never test
results. Its source/artifact SHA audit passes.

The matched `derive_atomic_owned_bridge.py` binds the actual guard owner
directly to HLS and exposes consumed-core receipts. It remains **Atomic-only**,
not a replacement for normal/native admission. Positive responses still need
their own real native MAC SFD/EOF/tail receipt joined before release; no MAC
idle heuristic or FIFO ready substitutes for that boundary. The full native
ordinary/Atomic memory exclusion integration and requester/standard API remain
unfinished. `IB_ATOMIC_NONE` and both zero global HLS drain inputs remain.

## Generated packet path and ownership (083)

`rocev2_atomic_packet_guard.v` is an **Atomic branch component**, not a
replacement for existing normal native traffic admission. The matched
`derive_atomic_bridge.py` places it after the actual whole-packet IPv4/ICRC
stage and before the real HLS width adapter. It snapshots trusted full QPN,
nonzero64-bit epoch and local/peer IP from management context, not the packet.
It validates the complete72-byte IPv4/UDP/BTH/AtomicETH request before any
byte or owner reaches HLS. Atomic is unposted: no RQ is required or invented.
PSN/MSN and MR permission decisions remain the common HLS and real MR service;
no independent sequence/protection table is added.

A nonwrapping32-bit packet tag distinguishes each accepted packet, including
duplicate PSNs. The guard retains its snapshot and packet ownership until an
explicit matching QPN/epoch/PSN/tag retirement is accepted. A stale tag cannot
release a new retry with the same protocol identity. Native integration must
provide real owned core/MAC retirement, not a user release knob. Already
offered packet/owner beats finish under disable/fault while the lease stays
held; reset is not safe cancellation/unpin proof. Four four-state methods
pass13 simulations. The first implementation's hidden global-header function
dependency was not updated by event-driven simulation; explicit data arguments
fixed it. Positive packet tests, unknown data/epoch/QPN rejection and exact
stale-tag tests now pass without weakening admission.

The full generated fixture connects the actual synthesized HLS top, the new
guard, real typed service adapter, Atomic engine, same MR/PTE/paged backend
and public segmented RAM ports to existing RX/TX IP/checksum/ICRC stages.
Peer packets and output bytes use an independent Python checksum/ICRC/Atomic
oracle. Physical descriptors/host write ordering and AXIS-to-native-MAC
retirement are explicit **models**; actual native queues, host pins/kernel,
physical MAC/tail and board operation are not established.

Composition003 PASSES all3 cases, taking2.77/1.87/2.17seconds respectively.
The main case sends four invalid requests first: one actual CRC rejection,
then three actual peer/QPN/format rejections before any service or DMA.
Ten admitted two-QP service requests exercise CAS success/mismatch, FADD
overflow/zero, cached replies across another QP's update, expected-PSN NAK
and an evicted drop. Six execute, two replay, one sequence-NAKs and one drops;9 packets leave
the real IP/checksum/ICRC pipeline. The independent Python oracle checks
every BTH/AETH/old-value field, IPv4 checksum and ICRC. Packet tags1..10 are
unique, including same-PSN retries. The drop deliberately retains its lease.
The other cases prove actual no-DMA MR denial and failed-fence retention
without a service result/wire reply. All memory bytes pass real RAM ports;
neighbor bytes remain unchanged. This is still two-state **modeled-boundary**
RTL execution, not physical/kernel/native publication or routed timing.

Diagnostic001 ran the main two-QP operation/replay path, a no-DMA MR denial
and a failed-fence ownership-retention case, but its source-change guard
correctly rejected the result after the
four-state fix. Its exact pre-fix guard/launcher are preserved with its logs.
The new translation consumes current RTL; only byte-identical compiler
inputs can reuse verified task-owned RAM objects. Every runtime is repeated;
no test result or producer proof is reused.002 retains a launcher Path-type
error before translation, not a device/protocol failure.

### Retirement boundary in the retained083 baseline

A valid service result accepted by an AXIS FIFO is **not** proof that the
shared RX PSN/MSN consumer has finished with it. A response packet passing the
actual pipeline is not physical MAC SFD/EOF/tail proof either. In particular,
an old unretained request may return a real `drop` result and emit no packet.
The fixture deliberately keeps that packet lease; it does not release on a
delay/quiet-time heuristic or pretend an RQ/core receipt exists.

Before full native publication, carry the immutable per-packet identity
through actual HLS admission/service consumption and export a genuine
post-consumption/shared-state readback receipt (implemented in the084 owned
derivative above, not backported into this rollback baseline). Join it to the matching real
MAC ownership (or proven no-packet drop) before native retirement. Then
integrate the existing single MR/PTE and all ordinary/Atomic memory clients
under the same exclusion domain. Requester descriptors/result placement,
standard kernel/provider capabilities and full physical/error qualification
are still required. This is the next major functional integration, not a
redefinition of completion around the currently passing subset.

## Shared sequencing and typed service (082)

`rdma/rnic/hls/atomic_transport.py` derives a complete matched
`rocev2_native_atomic_top` from the existing Immediate core without editing
the original source. AtomicETH is28bytes; its internal extended-header
container becomes224bits, while actual RETH/Immediate wire geometry and the
full620-bit immutable request context remain unchanged.

The **existing** receive PSN consumer reads the same QP table as SEND/WRITE/
READ and holds its owner until an Atomic service completion. The existing
MSN consumer supplies the current MSN. A successful new execution updates
these same tables; replay/NAK/drop does not. No independent HLS Atomic
sequence table is introduced. Replies use the existing connection/BTH/EXH/
packet assembly path, preserving the saved original MSN for replay.

The hardware-facing scalar AXIS ABI is explicit:

| Word | Fields, least-significant first |
| --- | --- |
| Request368 | Normalized BTH+AtomicETH320, authoritative expectedPSN24, currentMSN24 |
| Reply248 | BTH+AETH+old-value192, localQPN24, original requestPSN24, bytes6, advance1, drop1 |

`rocev2_atomic_service_adapter.v` checks the service request against an
independent trusted QPN/nonzero64-bit epoch, not packet-supplied authority.
It validates executor response identity and registers the exact typed reply,
retaining ownership through downstream backpressure. The actual native wire
owner must eventually provide this trusted context and honor its guard; a
testbench doing so is not evidence of real native admission.

`rocev2_atomic_responder.v` now has `SHARED_SEQUENCE_ENABLE=1`: it uses the
supplied **shared HLS** expectedPSN/MSN instead of its standalone private
tables. Trusted PD/peer/epoch configuration and actual MR/memory authority
remain protected. Every accepted service request returns a completion, even
if the operation is dropped without a packet; this releases the HLS sequence
owner without falsely advancing it. Default mode0 keeps the standalone tests.

Current evidence is `rocev2-rnic-atomic-shared-005.json` in the results folder.
Two live processes run actual HLS C++ consumers and actual adapter/Atomic/MR/
paged DMA/segmented RAM RTL. The HLS-emitted word goes unedited to RTL, and
the actual RTL-generated word returns unedited to HLS. A separate Python
network-byte/arithmetic oracle checks those transfers. The service's private
PSN/MSN are intentionally configured differently, proving shared mode does
not accidentally use them. One SEND and two WRITEs advance the real common
HLS tables between9 Atomic jobs on two QPs. The test verifies withheld-service
no-advance, wrap, replay after a different QP changes memory, CAS mismatch,
FADD overflow, sequence NAK and an evicted drop followed by ordinary traffic.
It finishes in0.279seconds. Existing Immediate TX/RX consumers pass eight
operations each on the new complete source. Four adapter methods additionally
check full/unknown QPN/epoch, stale/orphan response and registered ownership.

Host/physical descriptor/visibility behavior, trusted wire owner/peer admission
and ordinary SEND/WRITE payload sinks are explicit **models**. The HLS tests
execute real consumer C++ and compile the full top, but are NOT generated HLS
RTL, IP/UDP/ICRC/MAC/CQ, actual native/board/kernel/verbs or physical atomicity
proof. Full HLS generation001 completed in301.6seconds with original4ns/default
1.08ns uncertainty,8QP/2000entries and unchanged1500MiB free-space guard.
The actual generated top has368/248-bit service ports and unchanged existing
typed owner ports. It estimates58162LUT/82957FF/166BRAM18K/0DSP and13.568ns:
still a **4ns timing failure**, not physical timing/board qualification.
Exact source/frozen/generated hashes are in `rocev2-rnic-atomic-hls-001.json`.
The actual153-module hierarchy also passes Icarus elaboration with exactly
one PSN table, MSN table and RX-IBH/RX-EXH consumer each, recorded in
`rocev2-rnic-atomic-core-elaboration-002.json`. This is compile-only evidence,
not a generated-HLS packet execution result.

## Implemented path

`rdma/rnic/rtl/rocev2_atomic_responder.v` accepts a normalized, integrity/peer-
qualified40-byte BTH+AtomicETH. Low byte is first on the interface; multi-byte
wire fields are network order. Trusted management supplies PD, peer QPN and a
fresh64-bit epoch; none of them is supplied by the remote request. It executes
RC_COMPARE_SWAP(0x13) and RC_FETCH_ADD(0x14), both64-bit and8-byte aligned.

The operation uses the existing MR table's operation4, requiring the complete
key, PD, range and remote-atomic access. Only local-write plus remote-atomic
permission is needed; remote-read/write permissions are not substituted.
An MR-relative offset can be unaligned even though the full target VA and
translated physical address must be aligned. Full keys and offsets, not
packet-supplied physical addresses, reach the existing sealed-page backend.

`rocev2_atomic_memory_bridge.v` reserves the **same** existing memory arbiter
and backend across MR lookup,8-byte read, comparison/addition, writeback,
actual backend write-visibility status and response handoff. All other clients
in this atomicity domain must pass through client0; Atomic is client1. There
is one MR/PTE/backend/staging RAM, not a separate Atomic memory namespace.
Ordinary traffic waits until an already-accepted Atomic transaction finishes.
CAS mismatch returns the original value without writing. FADD wraps modulo2^64.
Memory lanes are native little-endian; the AtomicACK original value is wire
big-endian. The actual existing backend performs its write readback fence
before success; a submitted or acknowledged write descriptor is not enough.

One replay resource per candidate QP retains the full semantic request and
the original AtomicACK **before** exposing a response. A duplicate replies
with the cached old value without re-executing or incrementing MSN/PSN.
ACK-request changes do not change operation identity. A changed operand at
the same cached PSN is rejected; older evicted requests are dropped, never
re-executed. Future requests produce a sequence NAK naming the expected PSN.
PSN and MSN wrap independently at24 bits. Rebinding a candidate QP requires a
strictly newer epoch and discards the old replay resource. This is one
outstanding responder resource per QP, not arbitrary read/atomic concurrency.

MR denials produce a remote-access NAK before any DMA and quarantine that QP
until a fresh epoch. DMA/readback/status/ownership faults retain the reservation
and inhibit configuration/completion. Reset does **not** prove safe drain,
unpin or recovery. CPU and other-device writes are outside this exclusion
domain; **no global atomicity claim** is made.

## Bounded evidence

Run:

```sh
python3 rdma/rnic/tests/probe_atomic_responder.py --report /absolute/new-report.json
```

The14 cases connect actual new responder/bridge RTL to the existing actual MR
table, arbiter, page table/splitter, DMA backend and Corundum segmented staging
RAM. Every returned/updated byte passes through public stream/RAM ports; no
DUT memory/state is forced. Tests use a full high64-bit VA, nonzero MR base
offset, non-contiguous64-bit DMA pages, full keys/PD and unchanged-neighbor
sentinels. They cover CAS success/mismatch, overflow FADD, duplicate replay,
two independent QPs, competing ordinary DMA, key/PD/access/range/alignment
denial, sequence NAK, stale/fresh epochs, replay eviction and read/write/fence/
wrong-status failures. Response backpressure and held configuration leases
are checked. A separate Python `struct.pack` oracle checks emitted BTH/AETH/
AtomicACK bytes, including old-value byte order. Each simulation is <=30s.

Current standalone positive record: `results/2026-10-18/rocev2-rnic-atomic-responder-007.json`.
Earlier002–006 passed earlier source snapshots;001 retains a test-only assertion
that mistakenly checked exclusion after the Atomic response lease had already
been released. It was corrected; production exclusion was not weakened.

These are four-state RTL composition tests. The physical descriptor engine,
host bytes and readback ordering are explicit **models**, not physical PCIe
ordering/pinning evidence. Input integrity/peer admission is a modeled upstream
contract, not a tested integrated network front door. This test is not an
FPGA test, native HLS test, Linux/verbs test or timing pass.

## Required integration, still open

Mode0 owns a private PSN/MSN table for standalone tests; mode1 now uses the
same actual HLS PSN/MSN consumers, as shown above. Before native publication,
select the actual generated core/service in the complete native graph,
including true QP epoch/configuration/replay ownership, actual integrity/peer
admission and IP/UDP/ICRC/MAC response
ownership. Add requester descriptors with separate64-bit compare and swap/add
operands, protected local8-byte result placement, request retransmission and
true core/MAC/CQ retirement. Bind the resulting capability through the real
kernel/provider/standard API only when this entire path is present. CPU copies,
BRAM counters or a capability bit alone are not an acceptable replacement.
Native integration, physical lifetime/ordering, original4ns/1.08ns timing and
full-board DRC/check_timing/conditional CDC qualification remain unproven.

For build capacity, archive082 losslessly compresses15 exactly validated,
terminal old Verilator-generated C++ cache files (923302562raw bytes to
30436243compressed bytes). Each decompressed SHA matched before raw-cache
removal. Authored sources, raw HLS, inputs, logs, reports and executables are
retained. `results/2026-10-18/rocev2-rnic-cache-archive-082.json` lists exact
targets and hashes; recover any with `gzip -dk /absolute/file.cpp.gz`.

Wire layout and replay design were checked against the primary Linux RXE
implementation: [AtomicETH fields](https://github.com/torvalds/linux/blob/master/drivers/infiniband/sw/rxe/rxe_hdr.h),
[execution and replay](https://github.com/torvalds/linux/blob/master/drivers/infiniband/sw/rxe/rxe_resp.c).
This is protocol-reference use, not a claim that Linux RXE is the hardware
implementation or that this candidate already implements every RC requirement.
