# Actual retransmission pointer/lock readback

Progress038 adds an isolated opt-in derivative of the real FNS retransmission
pointer consumer. Both its request and update producers must supply the SAME
full168-bit {QPN16,PSN24,epoch64,sequence64} marker through their own normal
queue. A missing marker, a valid pointer, a global lock or an earlier lock
wait cannot be turned into success by a delay or an empty FIFO observation.
This is NOT full retransmission/core drain or WR/MR/CQ retirement authority.

## Actual storage, lock/wait ordering and limits

`rdma/rnic/hls/retrans_pointer_fence_profile.py` keeps the entire original ETH
licensed header byte-for-byte and appends an explicit derivative. Only that
derivative is instantiated by the isolated top. Original normal update,
request/lock and wait/release actions are byte-identical. Original functions
are unselected, not extra instantiated pointer/meta tables.

The real8-entry BRAM table is initialized by addressed zero writes to EVERY
entry before consuming requests. No reset bitmap fabricates an empty entry.
The private-DUT simulated reset case first writes nonzero/valid data into QP7,
then verifies actual BRAM clearing before new readback. It is NOT a physical
FPGA/host reset test or permission to release an external owner across reset.

The original global `pt_isLocked`, `pt_lockedQP`, `pt_wait` and retained
`pt_req` govern the normal path. An ordered request marker cannot overtake a
waiting lock request. Its earlier unlock update must be applied before that
request's real response/new lock and the marker behind it can progress.
Sampling includes actual pointer head/tail/valid and global lock/wait state,
with known zero masked QPNs only when the corresponding state is inactive.

A registered update stage cuts the update-FIFO/guard-to-BRAM path. Pending or
newly queued updates retain priority over request/wait progress, even before
the update reaches that register. A marker stops subsequent same-queue work.
Snapshot/classification/emission are also registered. No normal action, RAW
dependency, QP capacity or clock is waived; normal HLS scheduling stays II1.

FULL16-bit QPNs are checked on ordinary requests/updates and markers before
indexing. A VALID pointer's head and tail must each be below the unchanged
`META_TABLE_SIZE=2000`;1999 is accepted and2000 rejected. That is a tested
pointer-index bound, NOT proof that the2000-entry retransmission metadata
table, free-list, process FSM or event streams were instantiated/tested here.
Those remain separate real consumers/owners requiring integration.

## Private component ABI

Both224-bit inputs contain qpn[15:0],head[31:16],tail[47:32],valid48,lock49,
marker50,PSN[74:51],epoch[138:75],sequence[202:139],reserved[223:203]=0.
Ordinary requests use only QPN/lock; ordinary updates use QPN/head/tail/valid.
Markers require ordinary control fields0. They are not public verbs/DMA API.

The288-bit readback is qpn[15:0],PSN[39:16],epoch[103:40],sequence[167:104],
status[175:168],seen[177:176],snapshot_valid178,head[194:179],tail[210:195],
valid211,locked212,waiting213,locked_qpn[229:214],waiting_qpn[245:230],
failed_source246,failed_qpn[262:247],padding[287:263]=0. Normal40-bit output
is {7zero,valid,tail16,head16}. Source0=request,1=update.

Status0=actual pointer invalid and no global lock/wait;1=marker QPN range;
2=valid pointer/global lock/wait;3=zero epoch/sequence;4=sticky bad encoding,
ordinary access/pointer-index or full-token mismatch. Status0 still does NOT
certify downstream response, metadata/free-list/replay/event or core drain.

## Short evidence and timing boundary

Current actual-C++002passes35readbacks in0.004s: all8entries/full tokens/PSN
wrap/both marker orders, original lock/wait/unlock sequence, missing-marker
withholding, ordinary responses and range/encoding/mismatch faults. Original
header/source identities are frozen and unchanged. Source invariant unit002
passes4methods0.006s including exact original actions, real BRAM initialization,
full-width guards and5changed-anchor rejections. Clean checkouts lacking the
retained verified HLS fixture explicitly skip those units, not verification.

Current generated FOUR-STATE RTL003passes39readbacks in a short bounded run,
using exact actual HLS files without generated-RTL edits/replacement models.
It checks simultaneous request/update input preserves update priority, real
cross-QP global-lock wait/release, response stability under output stalls,
both head/tail2000 bounds, full QPN nonaliasing, high64-bit mismatch, and actual
BRAM clearing after simulated reset. Crucially a normal pointer response is
still VALID/HELD after pointer-state OK. Therefore this result positively
rejects treating the component as downstream/core drain or release permission.

HLS001 had estimate4.152ns at original4ns and is NOT timing signoff. Historical
generated RTL001passed38cases on that exact unstaged circuit. The registered
update candidate002constructs in35.135s,16generated RTL/data files, estimate
3.347ns,3BRAM18K/1396FF/1813LUT/0DSP/URAM. RTL002passed39before the additional
simultaneous-input stimulus;003is current. Exact historical profiles, drivers,
benches, logs and source hashes remain. No failed/old timing result is promoted.

Effective-budget warnings remain: decoder3.34675ns/core3.347ns exceed2.92ns
uncertainty-adjusted budget. No physical Vivado/resulting-full-board setup/
hold/pulse/skew/routing/DRC/check_timing/conditional-CDC gate has been run for
this new component. Old full-board/OOC timing/capacity/CDC failures remain.

## Still required

Real producer-FSM admission/marker injection; actual metadata/free-list/
release/process/replay/event ownership fences; a genuine joined per-WR core
retirement certificate; propagation through the actual shared native coherent
SQ/MR/PTE/PCIe/response/MAC/CQ/kernel/provider lifecycle and broader operations/
recovery/congestion/network compatibility. Timer/state/pointer readbacks are
isolated constituents and have NOT been selected in shared/native/board core.
`local_core_drained` remains0 and shared WR/MR guards remain HELD.

No hardware/JTAG/programming/flash/module install-load-probe/real traffic/
fan/BIOS/network/reset/reboot/commit/push. BIOS Medium and management remain
untouched. Original READ/WRITE/raw138/delivery140 HLS rollback sources remain.
Necessary builds are allowed, tests short. Exact authenticated Codex thread/
active-goal reboot restoration remains unproven; no reboot is currently needed.
