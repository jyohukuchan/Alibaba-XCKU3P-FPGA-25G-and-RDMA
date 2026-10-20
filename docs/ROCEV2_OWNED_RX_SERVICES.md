# Owned actual RX/state/MSN services — source/offline progress053

The actual owned FNS RX IBH/EXH functions are now composed with the actual
derived state-table and MSN-table implementations in a bounded C++ test.
State/MSN responses are **not models in this composition**. Native admission,
QPI/TX allocation and read-init remain explicit fixtures. This is not yet the
ONE shared/native/board graph, generated RTL, native DMA/CQ or physical proof.

## Source changes

`rdma/rnic/hls/owned_rx_services_profile.py` retains one original state RAM
and one original MSN RAM per instance. It preserves their licensed real
actions; it does not substitute a behavioral table or add a parallel
lease-to-owner lookup RAM. The actual stored MSN entry now contains its
packet/native owner, pending/active state and expected next PSN alongside
the original `dmaState` fields.

The RX state request encoder retains the full1024-bit packet token and588-bit
native context. The real state consumer uses that pending request's owner
for its response. Full epoch/sequence and native QPN checks precede table
access. The existing three-producer RX/TX/QPI ordered-marker consumer and
elastic dispatch are retained. TX/QPI read responses retain their original
request context; the original24-bit `req_next_psn-1` behavior is expressed
with a nonnegative25-bit intermediate for UBSan-safe PSN wrap.

The real MSN service does not simply stamp a new requester's tag onto stale
state. FIRST/ONLY retains the admitted native owner in the real entry.
MIDDLE/LAST requires the SAME full native context, selected248-bit lease,
next PSN and expected full64-bit VA; a second query before the matching
progress write is rejected. Writes require the exact1612-bit pending packet/
native owner, payload-only progress and the actual MSN value. After a final
progress write, the entry retains an owner/sequence tombstone; a replayed or
older READ cannot reinstall it. This is local MSN packet progression, **not
WR/MR release, memory visibility, completion or safe recovery**.

Connection epochs come from trusted QPI configuration, not wire bytes.
Initialization is required before access, keys retain all32bits including
zero, and TX QPN validation occurs before narrowing to the original index.
Ordinary QPI reinitialization is fail-closed. Genuine QP teardown/reuse/reset
needs the still-missing whole-core lifetime/epoch protocol; this restriction
is not a final capability limit or a claim of implemented recovery.

The owned RX producer also corrects native MSN progression to count payload
bytes, not raw wire padding. LAST emits a matching owned progress write as
well. A65-byte final payload advances by65, not68. The64-bit encoding of an
exclusive2^64 endpoint is zero only after the final packet transaction; it
is not permission to DMA to zero or to reuse an old address without a new
admitted owner. Raw memory-effect length, checked payload length and padding
remain separate.

## Current short evidence

Authoritative current records:

- `results/2026-10-18/rocev2-rnic-owned-rx-services-C-002.json`
- `results/2026-10-18/rocev2-rnic-owned-rx-services-derivation-002.json`
- `results/2026-10-18/rocev2-rnic-owned-rx-execution-C-011.json`
- `results/2026-10-18/rocev2-rnic-owned-rx-execution-derivation-009.json`

The actual RX/state/MSN composition runs with assertions and UBSan in about
0.04s under a30s process limit. It verifies36 packets (34 READ response
packets and2 WRITE ACKs),27 real state readbacks and39 real MSN readbacks.
Eight actual table slots are exercised in a short offline round-robin; this
is not eight physical RDMA connections or a long/many-connection test.

READ ONLY/FIRST/MIDDLE/LAST, all padding counts, PSN wrap, a real state-table
`req_next_psn=0`, a new READ on an already-used QP, exact64-bit endpoint and
zero/nonzero32-bit QPI keys are checked. Maximum32-bit WR length runs FIRST
only in the real-table composition; no4GiB transfer or fabricated skipped-
packet completion is claimed. The separate execution fixture still checks
maximum-length FIRST/LAST arithmetic with modeled state/MSN responses.

Fourteen negative service cases check uninitialized access, missing FIRST,
cross-WR/changed-lease continuation, pending-packet overlap, wrong exact
write owner, raw-padded progress, replayed completed READ, wide TX-QPN alias,
high-bit epoch mismatch, QPI reinit, ACK incorrectly attempting MSN write,
stale state epoch and invalid QPI initialization. Ten new derivation tests
and twelve current RX-execution derivation tests pass. The separate current
execution/UBSan regression passes in about0.11s, retaining all256 AETH values,
full owner-bit comparisons and its original short limit.

Two real ordered state-fence observations show why it is not a whole-core
certificate: a late TX change produces BUSY while a later RX request stays
behind its marker; another table OK occurs while an actual downstream
retransmission update is still held. Marker production in these tests is
an explicit fixture, not implemented real upstream producer closure.

Historical failures are retained unchanged. Execution C009 used an incorrect
test comparison at the2^64 endpoint (a64-bit stored endpoint versus an
untruncated65-bit expression). Services derivation001 exposed a missing
critical-original-action anchor check; that guard was added and the test was
rerun without weakening its expectation. Earlier passing snapshots remain
history, not substitute current-source evidence.

## Remaining full-goal work

All11 original requirements remain active in progress053 and its authenticated
parents. The next binding is the SAME real retransmission/pool/read-init path
with selected immutable leases, native WR/MR references and correct coalesced
ACK predecessor handling. Native coherent SQ/MR/PTE/PCIe/executor/checked-unpad/
MAC/CQ and genuine packet admission must join the same live shared HLS graph;
complementary C/trace/model proofs do not replace that graph.

MSN producer closure and all downstream command/body/memory/MAC/CQ ownership
are not proved by an MSN write or an idle port. `local_core_drained` remains0
and WR/MR references remain HELD. Standard ib_device/QP/WQ/CQ/provider and
remaining verbs/zero/large/multi-SGE/recovery are incomplete. No false CQ,
empty ib_device, default-success hardware callback or CPU payload-copy
substitute is added.

There is no HLS/RTL/physical qualification of these new consumers. Prior wire-
RX3.947ns is a different unchanged component and was only below nominal4ns,
not the original uncertainty-adjusted target. Old failed physical gates and
unqualified full2000-entry lookup case remain failed/unqualified. Original
8QP/2000metadata/4096PMTU/4ns geometry and rollback READ/WRITE are preserved.
The root filesystem is about1.3GiB free; the1500MiB HLS/XSIM guard is unchanged.
Only small C builds ran. No evidence/user-data deletion or storage changes.

No FPGA/JTAG/programming/flash/module install-load-probe/real traffic/fan/BIOS/
management-network/other-device/reset/reboot/commit/push action occurred.
BIOS Medium remains the preference. Reboot is not needed/performed, and exact
authenticated Codex thread/active-goal restoration remains unproven.
