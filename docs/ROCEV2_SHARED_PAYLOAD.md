# One paged payload backend for incoming and authorized local work

Progress028adds real source integration and bounded OFFLINE memory-DMA
evidence. It does NOT implement the local HLS transport executor, protected
READ-response/ACK ingress, a native CQ publisher, registered kernel/userspace
verbs or deployed hardware. The local executor/transport and final WR/wire/CQ
lifetime in these tests are explicitly MODELS, not completion substitutes.

## Same namespace, one backend

Progress029adds guarded native WQE-to-keyed-HLS SQ staging, not the missing
local memory/ACK/READ-response/CQ executor itself. It also corrects the real
protected parser's MigReq flag mask, preserving actual authorization gates;
see `ROCEV2_HLS_SQ_SUBMISSION.md`. Older source-bound actual-HLS records below
are historical after this parser change, not current-source signoff.

Static `LOCAL_MEMORY_ENABLE=0` preserves the dedicated incoming path and
ignores the new local memory ports. Enabled mode requires `LOCAL_WQE_ENABLE=1`
and complete16-bit tags. `rocev2_memory_client_arbiter` then connects two
authorized clients to the ONE existing `rocev2_paged_memory_backend`, its
sealed PTE namespace, staging RAM and actual DMA engine. No MR/PTE table,
payload backend or physical page-address cache is duplicated.

The option and complete local command/data/status ports propagate through
paged, controlled, same-port Ethernet, native and native-SQ source layers.
The native-SQ top still shares this one payload backend and its separate
coherent-SQ backend through the existing full-tag physical DMA router. Real
mqnic app/board selection is NOT implemented by exporting these ports.

The local port is a privileged INTERNAL executor contract: key32, MR-relative
offset64, length32, tag16 and direction. It takes no raw physical DMA address.
Its caller MUST be the executor of a successful SAME-MR authorization and
retain the full MR/QP/WR identity beyond memory result handoff. At this stage
that executor remains a fixture model; the hardware does not reconstruct or
bind an actual local HLS memory command to a WQE yet. This port is not mapped
for untrusted software, advertised through verbs or bound to a real driver.
The existing SQC1 feature1continues to mean control-only, not RNIC capability.

## Ownership and data handling

Round-robin selection captures the ENTIRE write/offset/length/key/tag tuple.
One explicit client owner is retained until the real memory result is
accepted. Complete16-bit client tags may coincide; no tag bit is stolen or
truncated. The backend command is registered and remains offered after a
later disable/fault. Registered512-bit data beats likewise remain stable
under downstream stalls/faults. No other client's data or result is accepted
as that owner's work.

Lengths1..4096match the current payload prototype; this is not a reduction of
the broader goal's zero/large/multi-SGE requirements. Offset addition uses65
bits: exclusive end2^64is legal, actual overflow is not. Keep/last/count and
all meaningful data bytes are checked; invalid tail bytes are zeroed, while
X bits outside keep are not treated as actual data. Extra data cannot replace
an already-held final beat. Successful backend status cannot bypass final
data handoff. Full status tag/error/owner must match.

Offered local memory work and arbiter ownership join the native MR/PTE/route
guard; actual memory_drained additionally requires the arbiter empty. A held
memory result therefore cannot look drained merely because physical TLPs
finished. A management pause does NOT cancel or block already-authorized
local memory work; otherwise STOP/revoke could deadlock against that work.
The caller's real WR lease must continue after memory result acceptance.
Memory result, fetch consumer, semantic ACK and descriptor completion are
NEVER RDMA/CQ completion or permission to unpin.

Known nonzero backend errors are delivered exactly to the retained owner,
then leave sticky fault/uncertain ownership with no safe release. Invalid
tuples, meaningful unknown data/status, wrong/unsolicited status and extra
data fault closed without a fabricated success or drain. This fail-stop
behavior is NOT completed abort/flush/recovery; source-bound safe teardown
and real error CQ publication still need implementation. Reset is not proof.

## Current bounded evidence

`memory-arbiter-unit-004` passes10four-state methods/37simulations. Client and
backend are MODELS. Cases include complete high key/offset/tag bits, identical
tags, round-robin/stalls, all15nonzero errors, invalid/unknown tuples/data/
status, last-data/status ordering, retained offers across fault/disable,
extra data during a held final beat and the full4096-byte/exclusive-end2^64
boundary. This alone proves no MR permissions, PTE, PCIe or completion.

`native-memory-unit-004` passes2methods in44.498seconds, with actual C/UBSan
WQEs, coherent SQ fetch, SQC1/native AXI control, SAME MR table and SINGLE
actual PTE/payload backend, RAM, common router, both real native-shaped muxes,
generic PCIe engine and actual parent-guard RTL. HLS is explicitly STUBBED;
physical host/link/MAC and the local transport/executor/final CQ owner remain
MODELS. Neither a constant drain nor descriptor/status/RAM engine agents are
used, and no DUT state is forced.

Each case fetches one actual C-encoded64-byte WQE and checks128unchanged
coherent ring bytes. The modeled executor copies ONLY its actual authorized
full key/offset/length/tag into the new memory client while retaining QP2's
guard. WRITE-source fetch checks65actual host bytes via two3+62scattered
page READs (plus the SQ READ). READ-destination placement checks65bytes via
two3+62posted WRITEs and an actual visibility-fence READ (plus SQ READ).
Every host payload/sentinel byte is checked, with no CPU payload-copy path.
Held data/status exclude STOP/MR/PTE/route mutation. Memory result handoff
alone does NOT release the modeled WR/CQ owner; early SQ retire returns35,
then only a fresh final owned retirement returns31after that owner releases.

Preserved failures: arbiter-unit001had an incorrect fixture port inventory;
native-memory-unit001referenced an undeclared fixture alias; unit002left the
old physical-address monitor sampling only incoming, not accepted local
commands. The monitor now samples BOTH real accepted client contexts and
keeps all original full physical address/page/split/tag checks. Unit003passed
before the extra-final-data check;004refreshes final source identity. No
failed report is overwritten or promoted to a passing result.

`native-memory-forward-compiled-001` additionally runs the exact140-file
per-WR HLS delivery with the new memory arbiter ENABLED in the full native
graph. It retains ALL original incoming2WRITE/3READ/IPv4/ICRC/QPN/PSN/AETH/
payload/range/ownership/fence and ordinary-host byte/sideband assertions,
then adds one actual C-encoded SQ fetch/SAME-MR authorization and65-byte
local source DMA through that SAME backend. Only the exact new memory
operation counters change: one extra payload command/result and three extra
physical READs (SQ64Bplus source3+62B). Full25native replies/ACKs and four
SQC1owned transactions retain their exact fields/proofs; no assertion gate
is dropped. The local transport/executor/final WR-CQ owner is STILL A MODEL.

The additional compiled TWO-STATE execution passes in11.82seconds/32472cycles:
15physical descriptors,11READ/4WRITE TLPs,11read completions,2fences,
130incoming WRITE/195incoming READ bytes,65local source bytes,256delayed
write-TX-sequence cycles, all host sentinels and128unchanged SQ ring bytes.
Compilation is separately bounded600seconds, simulation30seconds using the
established Verilator5.036helper/settings. This is NOT four-state/X/Z/reset,
actual protected local READ-response ingress or native wire/CQ completion
proof. Exact original138-file HLS and140-file delivery hashes stay unchanged;
the old120-second four-state full-forward observation failure remains saved,
not silently replaced by a two-state qualification claim.

Final portable034passes269methods in391.948seconds; source-checks037passes
7batches/64methods. Fresh default old-initiator READ005/WRITE005four-state
cases each retain one65-byte operation (68.65/69.94seconds). Default actual
parent compile013also passes, retaining all compiler warnings; it does not
select this new native-SQ/local-memory graph. Kernel source/headers have not
changed in028; prior frozen build004remains source-current, not runtime proof.

The new hierarchy remains physically unqualified. Historical negative full-
board/OOC reports and their frozen inputs are preserved, not inherited as
timing/CDC closure. Original clocks/capacities/protection remain required.
No programming, driver installation/load, live traffic, fan/BIOS/network
change, reboot, commit or push is performed in this stage.
