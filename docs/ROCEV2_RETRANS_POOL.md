# Real2000-slot lease allocator candidate

Progress041 now supplies an opt-in actual FNS process/metadata/pointer binding
and a production wrapper around this EXACT unchanged pool RTL. Seven short
generated-RTL simulations pass, including actual full-pool ACK/reuse and READ
mutable-PSN/immutable-lease behavior. See `ROCEV2_OWNED_RETRANS.md`. The original
shared/native/board path is still NOT switched. Genuine upstream producer
marker injection, complete core lifetime and standard/native CQ remain open;
actual output still held after pool zero proves this is not retirement.
The Progress040 unit/synthesis evidence below concerns the allocator alone.

Progress040 adds `rdma/rnic/rtl/rocev2_retrans_pool.v`, a real packed lease-RAM
and free-ring allocator. This is a proposed REPLACEMENT for the original
autonomous `freelist_handler`/FIFO interface, not a passive observer of a
prefetched free-index stream. The original FNS process/free-list path and
board selection have NOT been changed yet. Test producers are models; storage,
allocation, release and owner scanning are the actual new production RTL.

The original unmodified path still needs the opt-in replacement selected.
That replacement retains full WR/insert context before requesting a lease,
binds the returned generation to actual metadata, and returns the exact lease
from real ACK/release processing. This candidate binding now works offline;
shared/native selection, genuine upstream producer marker injection and the
joined core/native/CQ lifecycle remain unfinished. No private allocator
response is public verbs or MR/CQ authority.

## Ownership, not leftover metadata bytes

Each actual slot stores one atomic234-bit record:
{state2,generation64,sequence64,epoch64,PSN24,QPN16}. FREE=0,OFFERED=1,OWNED=2.
The2000-entry ring contains ONLY free indices. Startup/local-reset rebuild
reads EVERY actual slot and reconstructs ring/counts without erasing leases.
`free+active=2000` is checked throughout the functional tests and again against
an actual all-slot scan when issuing a per-WR allocator snapshot.

An allocation reserves a FREE record as OFFERED and advances the retained
generation on the SAME commit edge. Its full result is held under backpressure.
Only actual result acceptance changes OFFERED to OWNED. Unaccepted offers
cannot be normally returned, including after local reset loses that output.
This prevents an unread grant becoming a reusable index by reset/default idle.

Release requires OWNED state, full16-bit valid index, exact64-bit generation
and ALL168owner bits. It atomically marks the record FREE and enqueues that
index once. Duplicate release, stale generation, wrong owner/full QPN/index
and malformed fields do not free another lease. The generation counter never
wraps: MAX is refused. A test uses MAX-1 seed without reducing capacity/clocks.
There is no forced DUT-state modification in the tests.

Local `rst` clears control/output state, not lease RAM, generation or fault.
Uncertain leases and fault quarantine therefore survive rebuilding. This is
NOT completed recovery: an abandoned offer stays reserved and needs future
trusted abort/recovery. FPGA RECONFIGURATION/POWER LOSS reinitializes RAM /
counter; actual kernel/persistent-generation/old-DMA recovery is still required.
It is NOT proof that MR references can be released across such events.

## Ordered per-WR allocator snapshot

Both allocation and release producers carry their own same-queue marker.
Both full168-bit {QPN16,PSN24,epoch64,sequence64} markers must match; a missing
or mismatched marker never becomes success through time or FIFO idleness.
Later work is blocked on the marked producer and through snapshot acceptance.

Once BOTH markers arrive, actual synchronous RAM reads scan ALL2000slots.
OFFERED and OWNED records matching QPN/epoch/sequence count as this WR's active
leases. PSN is echoed/marker-matched but deliberately not part of that count:
one WR can own multiple metadata PSNs. The full-capacity case explicitly
varies PSNs and still counts all2000leases for that WR. Global active/free
counts are cross-checked against real records; no shadow default-success bit.

Status0means no allocator reservations for that WR at this ordered snapshot.
Other WRs may still be active. It does NOT cover metadata/pointer/timer/replay/
event/MAC/DMA ownership, full-core drain, physical reset recovery or CQ commit.
Shared `local_core_drained` stays0 and existing WR/MR guards stay HELD.

## Private ABI and errors

Owner168 is {sequence64,epoch64,PSN24,QPN16}. Allocation192 input has owner in
[167:0],marker168,reserved[191:169]=0. Release256 input has index[15:0],
generation[79:16],owner[247:80],marker248,reserved[255:249]=0. Markers on the
release queue require index/generation0. Allocation/release256 results are
{status8,owner168,generation64,index16}; successful grant data can be returned
unchanged as a normal release. Error results are not successful leases/CQEs.

Allocator snapshot224 is owner[167:0],owner_active[179:168],
global_active[191:180],free[203:192],status[211:204],snapshot_valid212,
reserved[223:213]=0. Status0=zero owner reservations;2=owner busy;3=bad owner
token;4=sticky fault/count inconsistency. Only0/2have a qualified snapshot.
Normal result errors include1=range,3=encoding/token,4=quarantine,
5=duplicate/free release,6=stale generation,7=owner mismatch,
8=unaccepted offer/generation exhaustion,9=pool invariant. Exact valid releases
can finish after quarantine, but the allocator snapshot still reports fault:
this does NOT implement global safe recovery or MR/CQ release.

X/Z input checks are explicit simulation diagnostics under non-SYNTHESIS code,
not analog CDC/ECC detection. Known-signal SYNTHESIS-defined simulations are
also tested and must give identical actual summaries; no synthesis X-literal
don't-care shortcut is used to claim physical protection.

## Short evidence, initial bug and retained synthesis history

Current unit003passes16methods/simulations in4.171s. Twelve four-state cases
cover all2000unique indices, exhaustion/backpressure/release/reuse, per-WR
multi-PSN counts, retained OWNED and unconsumed OFFERED leases, fault retention,
duplicate/stale/full-owner/full-index/full-QPN errors, both ordered markers,
blocked later work, high64nonce mismatch, X/Z diagnostics and nonwrapping
generation and immutable lease-PSN mismatch. Four additional known-signal
SYNTHESIS-defined cases match the
same summaries exactly. The full case actually grants/releases2002leases;
the stale case refills the real whole pool before trying an old token.
Every simulation is below1second. No many-network-connection/load qualification.

Initial unit001FAILED: grant wire order is owner/gen/index, but the handoff
write mistakenly copied it into RAM's gen/owner layout. The all2000owner scan
detected bad records and returned quarantine, not the expected busy result.
The packing was fixed in source, NOT an assertion or expected result changed.
Failed report/logs/binaries/exact frozen sources remain. Report completeness
requires the full named16-case set and terminal success; the failed batch does
not acquire a positive flag from partial method counts.

Isolated actual Vivado synthesis uses1640LUT/1728FF and14RAMB36E2 primitives:
13lease banks,1free ring. All64generation register reset pins are traced to
actual primitive GND drivers, not inferred from net names. Source/private
reset behavior is therefore accompanied by actual mapped BRAM/reset-wiring
evidence, but post-synthesis functional replay and physical reset testing were
NOT performed. No FPGA hardware has been touched.

Synthesis verifier001stopped before synthesis on an unsupported redirect
command;002completed actual synthesis/DCP but its checker queried a nonexistent
IS_GND net property. Both overall runs remain FAILED. Corrected003reopens the
exact HASH-VERIFIED002DCP and checks real GND driver connectivity/BRAM cells.
It is an immutable synthesis replay/verification, NOT a fresh synthesis or
changed RTL/clock; original DCP/profile/driver/logs remain.003verification
takes52.740s. The design itself has not changed since functional unit002.
Unit003adds an explicit immutable lease-PSN rejection case without changing
RTL;002remains a valid historical16case pass before that extra stimulus.

The unplaced OOC synthesis-only estimate has WNS+0.802/WHS+0.071 at4ns,
but454inputs/743outputs have no delay constraints, no clock-source/skew
binding, no placement/routing, and OOC DRC warns not all connectivity checks
run. A zero synthesis-DRC count is NOT full-board DRC/timing/CDC signoff.
All original resulting full-board setup/hold/pulse/skew/routing/check_timing/
conditional-CDC gates and historical negative capacity/timing results remain.

## Next real implementation

Bind the actual FNS insertion/release process to request/grant/return leases,
retain generation and full-WR identity through actual metadata/ACK/retry paths,
including the original IMMUTABLE lease PSN (the protocol metadata PSN can
advance during a segmented READ and must not replace that lease field),
inject ordered markers from closed real producers, and join pool with actual
timer/state/pointer/metadata/event/stream ownership before a core certificate.
Then actual shared native SQ/MR/PTE/PCIe/MAC/CQ/kernel/provider and broader
operations/recovery/network support. Uncertain/quarantined ownership is NOT
completed recovery. No narrowing of the general RoCE objective is implied.

No JTAG/programming/flash/module install-load-probe/traffic/fan/BIOS/network/
hardware reset/reboot/commit/push. BIOS Medium/management preserved. Source /
offline feature builds/tests only; exact authenticated Codex thread/active-
goal reboot restoration remains unproven and no reboot is needed now.
