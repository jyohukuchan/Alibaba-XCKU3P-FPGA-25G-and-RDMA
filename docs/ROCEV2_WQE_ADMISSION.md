# Host work-request format and local-MR admission frontend

These are real new C/kernel/RTL building blocks, NOT a completed native host
WQ/CQ, registered `post_send`, ib_device/provider, host-page DMA or FPGA
deployment. Current physical META analysis and running rollback image do not
contain this frontend. Its original admission-only tests use a dedicated actual
MR-table instance. The later [shared-MR integration](ROCEV2_SHARED_MR.md) connects
the actual local frontend and incoming responder to ONE actual table and passes
short actual-HLS cases; it is still not enabled in the native parent path.

## Fixed descriptor, separate trusted context

`kernel/wqe.c` explicitly encodes/decodes64little-endian bytes; a C struct is
NEVER cast onto device memory. Every failure clears output. Current subset:
one local SGE, nonzero1..4096B READ/WRITE, signaled flag only. Larger/zero-byte
operations, multiple SGEs, SEND/immediate/Atomic/inline/fence and other flags
remain unfinished and are refused, not silently truncated or advertised.
This new subset does not reduce the existing HLS8QP/2000entry/PMTU capacity.

| Byte offset | Field |
| --- | --- |
|0|Opaque64-bit WR identifier|
|8|64-bit expected submission sequence|
|16|Full64-bit local IOVA|
|24|Full64-bit remote virtual address|
|32|32-bit length|
|36|Full32-bit LOCAL key|
|40|Full32-bit REMOTE key, including exact0|
|44|16-bit operation:1WRITE,2READ|
|46|16-bit flags:bit0signaled only|
|48|64reserved bits, all0|
|56|64-bit queue epoch|

QP/PD/tag/expected epoch/expected sequence are supplied by trusted queue
context, NOT descriptor bytes. They must refer to a live driver-owned queue;
the frontend does not allocate QPs, advance ring indices, acquire kernel MR
references or manage sequence/epoch exhaustion. The future owner must refuse
wrap/reuse until actual lifetime/drain requirements hold. An untrusted WR id
is never authority to free a mapping or invoke a kernel callback.

The C shape validator preserves all key/address bits and permits a range
ending exactly at the top64-bit byte. It is NOT memory authorization. Local
key0can be encoded but is still rejected by hardware without a matching live
registration. Remote key0NEVER chooses a default or the local key.

`kernel/verbs_wqe.c` uses the actual Linux6.17 `ib_rdma_wr` and `ib_sge`
types, maps READ/WRITE/SGE address/local-key/remote-address/remote-key and
explicitly translates `IB_SEND_SIGNALED` to native flag bit0. Unsupported opcodes,
flags or SGE counts return errors. This is an unregistered conversion API,
not an implemented or runtime-tested `post_send` callback.

## Actual admission and permission boundary

`rtl/rocev2_wqe_admission.v` captures all64bytes and trusted context on one
complete keep/last handshake. Record shape, reserved bits, full epoch/sequence,
internal QP<8, opcode, flags, length and full64-bit address-overflow checks
precede ANY local-MR query. Caller management-idle must include pending
transactions, not just the current cfg_valid signal.

| Work request | Actual local MR operation |
| --- | --- |
|RDMA WRITE|LOCAL READ(0), to read the source buffer|
|RDMA READ|LOCAL WRITE(1), to receive into the destination buffer|

The actual MR validator checks full local key, trusted PD, access and complete
range. Successful output preserves full local IOVA, MR-relative64-bit offset,
local key, remote VA/key and queue ownership context. It deliberately does
NOT forward the MR table's contiguous-DMA-address output: the native paged
executor must resolve the real sealed/scattered DMA64 pages. User IOVAs/DMA64
addresses must not be truncated through the HLS48-bit/routing-field boundary;
use owned staging tokens and separately retained authorized full context.

An admitted work item is NOT a successful RDMA completion. No DMA, wire SQ,
CQE, interrupt or unpin is produced here. The future executor must acquire
downstream ownership on the handoff edge and retain it through actual data/
fence/MAC/wire/CQ publication as required. Shared MR configuration quiescence
must include BOTH this frontend and that downstream ownership without a gap.

`configuration_guard` covers accepted work and the offered first WQE beat.
Management offers have priority while idle; configuration-idle must not form
a combinational dependency on the guard. Disabling new admissions does NOT
withdraw an already offered MR query or result. All context stays stable
under request/response/result backpressure. Clean denials zero all address/
key/length/opcode/flag outputs while retaining the trusted routing tuple.

Malformed shape/context/opcode/flags/length/address errors are20..27; known
MR errors1..10are returned as denials. Wrong MR response tag, mismatched
successful extent or unknown error causes a sticky fault(31/32/33), with NO
successful/error completion fabricated and busy/config guard held. Resetting
this local block is NEVER global DMA-drain/page-release proof; outer unknown
ownership and pinned mappings still require real lifetime recovery.

## Current evidence, not native functionality

`wqe-codec-001`:7methods, actual shared C/UBSan+independent Python byte oracle,
1000seeded random records and fixed full-width/zero-key/top-byte/invalid/
null/overlap cases. One method is only a static kernel-adapter routing check;
no kernel WR function executes in userspace tests.

`wqe-admission-001`:6actual four-state RTL suites with actual C-generated
descriptors and actual MR table. Includes WRITE-source/READ-destination
permissions, full high-bit local keys/high IOVA/cross-page span, local key0/
wrong key/PD/range denials, malformed descriptors and full context mismatches
before lookup, top64-bit byte/key0/max internal QP, disabled/stalled query/
response/result, management exclusion and uncertain-response faults. Only
external MR response ports are corrupted for fault tests; no internal forcing
or software authorization replacement. No real host queue fetch/pages/DMA.

`kernel-aux-build-002`:20inputs frozen BEFORE actual W=1/GCC13compile/link
against running6.17.0-1033-oem headers:17own files,2pinned parent headers,
1launch script. Both support/CSR-only modules link, including the actual
kernel WQE API symbols. Neither is installed/loaded, no as02module is observed
loaded, no probe/MMIO/pin/DMA occurs. Auxiliary default probe remains off;
loaded mqnic private-layout compatibility remains unverified. Earlier
kernel-aux-build001is historical after adding WQE objects to the Makefile.
The later SQ/work-reference source changes make aux-build002historical too;
`ROCEV2_KERNEL_QUEUE.md` documents current22-input kernel-sq-build002and real
coherent-ring/MR-ref code. Its native allocator/producer/CQ callbacks remain
unexecuted; modeled actual-C execution is not Linux runtime verification.

At the original admission stage, full175-method portable batch019and source-checks018passed. An actual
parent/core/app compile003includes the uninstantiated new frontend source;
this is syntax/elaboration evidence, NOT integration/traffic through it.

The newer shared query arbitration and downstream guard integration/evidence
are documented in `ROCEV2_SHARED_MR.md`, distinct from native execution.
The subsequent `ROCEV2_SQ_DMA_FETCH.md` adds an actual DMA fetch client/backend
and finite generic-PCIe tests, still without real kernel coherent allocation
or connection into native shared-MR/WR execution/CQ/provider.

Remaining: genuine pinned/coherent host-SQ fetch and native trusted context/shared-MR wiring,
MR/QP/queue reference/lifetime, page-DMA/staging executor, actual local READ
receive target/wire completion/CQ publication, standard kernel/user verbs,
complete required operations and bounded recovery/concurrency, resulting new
full-board original physical/CDC gates and short thermal-supervised native
checks. No hardware/reboot/fan/BIOS/network/commit/push change in this stage.
