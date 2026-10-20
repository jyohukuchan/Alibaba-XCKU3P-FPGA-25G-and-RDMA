# Actual2000-entry retransmission metadata commit/readback

Progress039 adds an opt-in derivative of the REAL FNS metadata-table consumer.
It preserves ALL2000entries and original write/append/read actions. A marker
follows actual operations in the SAME FIFO; registered sampling reads actual
table data and echoes {index16,QPN16,PSN24,epoch64,sequence64}. Requests behind
the marker cannot change its snapshot. This is commit/data readback, NOT
allocator active/free state, whole-core drain, or WR/MR/CQ release permission.

## Crucial ownership distinction

Original `process_retransmissions` ACK handling releases the index through
`releaseFifo` and updates the pointer, but does NOT erase the metadata record
or clear its `valid` bit. That bit alone does NOT tell whether this WR owns
the slot. Old bytes can legitimately remain after allocator release.

Therefore metadata status0 means the ordered marker reached the actual table
and its data was read without a local input fault. It can return a VALID
record. It cannot certify allocation, release, retry/event/response consumption
or ownership transfer. Actual free-list/release/process/replay/event owners,
real producer admission/marker injection and the full saved WR must still
join before any genuine retirement certificate. Current shared drain remains0
and owners HELD. No shared/native/full-board core selects this derivative.

## Storage, dependencies and ordering

`rdma/rnic/hls/retrans_meta_fence_profile.py` retains the complete original
licensed header unchanged and appends one explicit derivative. Only that
derivative is instantiated. The original addressed2000entry reset sweep,
all zero assignments and normal full-write/append/read actions are retained
byte-for-byte. No capacity/clock reduction or second shadow metadata table.

The selected derivative REMOVES the original `meta_table inter false`
DEPENDENCE directive. Real same-index RAW/WAR/WAW dependencies must not be
waived when write/append/read/marker operations follow each other. The old
unselected header remains untouched, including its original directives.
The current generated RTL tests actual same-index sequences, not a replacement
RAM model. Full reset remains real addressed writes to all2000entries; no
bitmap or fixed quiet-time fabricates empty table data.

An elastic raw register and decoded-message register separate wide480-bit
input parsing/checks from FIFO emission. A registered consumer request
separates validation from BRAM access; marker dispatch never captures a later
request on the same call. Sampling/classification/emission are registered.
All four helpers/consumer retain reported HLS II1; core depth4. These are
scheduling results, not physical25G throughput or full-board timing signoff.

Full16-bit index is checked before all table accesses; valid-owner QPN must
fit all8slots before a marker samples data. Append links and valid non-tail
write links must be below2000. Both write+append, reserved marker/input bits
and invalid normal write opcode are faults. Invalid opcode is safely clamped
before enum conversion while remaining a fault, never written as a valid
operation. Sticky input faults retain the failing full16-bit index.

## Private isolated ABI

The480-bit input is index[15:0],write16,append17,marker18,QPN[34:19],
PSN[58:35],epoch[122:59],sequence[186:123],entry[459:187],reserved[479:460]=0.
Markers require zero ordinary control/data fields. Normal requests are the
original privileged internal metadata operations, NOT public verbs/DMA API.

Entry273bits are rkey[31:0],rkey_valid32,host33,PSN[57:34],next[73:58],
opcode[105:74],localVA[169:106],remoteVA[233:170],length[265:234],lst266,
offs[270:267],valid271,isTail272. Opcode wire field is32bits, with explicit
defined-range checks before conversion to the original enum. Normal288-bit
output is {15zero,entry273}. Full key0/key-valid/host/VA64/length fields are
stored and checked; they are NOT independent DMA authority or proof of large
payload/operation capability.

The512-bit readback is index[15:0],QPN[31:16],PSN[55:32],epoch[119:56],
sequence[183:120],status[191:184],snapshot_valid192,entry[465:193],
failed_index[481:466],padding[511:482]=0. Status0=ordered actual data snapshot;
1=index range;2=owner-QPN range;3=zero epoch/sequence;4=sticky malformed input/
ordinary range/link/opcode fault. In particular0is NOT an active/free claim.

## Short evidence and retained intermediate designs

Current actual-C++003passes23readbacks and2005normal reads in0.016s, including
ALL2000entries initially zero, same-index write/append/read ordering, high64-
bit tokens/VA fields, PSN wrap, key0/key-valid, behind-marker update ordering,
full index/QPN/link/opcode/encoding faults and VALID data with commit OK.
Three independent typed codec cases inspect actual semantic fields, drive the
encoder from independently constructed original entries and check safe invalid
enum conversion; not only a symmetric raw encode/decode roundtrip.

Current actual generated FOUR-STATE RTL003passes27readbacks/6005normal reads
in17.865s. It checks all2000entries initially zero; writes and reads every
entry nonzero; performs a simulated PRIVATE-DUT reset; then reads/checks every
entry zero again. It tests exact full data fields, original append semantics,
same-index RAW/order/ranges and stalled response stability. A real normal
response remains VALID/HELD after a commit OK snapshot of VALID metadata.
This positively demonstrates why commit is not downstream/core/allocator drain.
The simulated reset is NOT a real FPGA/host reset or safe runtime recovery
certificate. No generated RTL edits, fake RAM/CQ callbacks or payload-copy
substitute. Source invariant unit001passes4methods0.006s; a clean checkout
without the retained HLS fixture explicitly skips, not a verification pass.

HLS construction003takes37.592s and retains22generated RTL/data files with
complete frozen source/profile/driver hashes. Full actual resource estimate:
39BRAM18K/3025FF/2119LUT/0DSP/URAM. Current estimate2.812ns at unchanged4ns;
no HLS200-887 target warning remains in that run. This is NOT physical timing.
Earlier001top estimate4.217ns had a5.031ns decoder warning and4.152ns core
warning;002estimate4.122ns still exceeded target. Those functional/construction
passes are historical, never timing signoff. Historical generated RTL001/002
passed the same27/6005cases in11.442/16.370s on their exact designs. Old
profiles, drivers, C++/benches/logs/compiled artifacts remain hash-exact.

No new Vivado physical/resulting-full-board setup/hold/pulse/skew/routing/DRC/
check_timing/conditional-CDC qualification. Old full-board/OOC timing/capacity/
CDC failures remain failed. Original READ/WRITE/raw138/delivery140 rollback
sources and images remain unchanged; this table-only design is not a board.

## Next real integration and constraints

Implement actual free-list/release ownership and process/retry/event fences,
then real producer-FSM admission/injection and a genuine joined per-WR core
certificate. Propagate the shared native coherent SQ/MR/PTE/PCIe/response/MAC/
CQ/kernel/provider lifecycle and wider operations/recovery/network support.
Table commits and valid bits, ACKs, idle ports or delays never replace it.

No hardware/JTAG/programming/flash/module install-load-probe/real traffic/
fan/BIOS/network/reset/reboot/commit/push. BIOS Medium/management preserved.
Builds needed for features allowed, tests short. Exact authenticated Codex
thread/active-goal reboot restoration remains unproven; no reboot needed now.
