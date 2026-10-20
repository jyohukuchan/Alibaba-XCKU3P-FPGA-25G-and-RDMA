# Per-WR remote-key and retransmission context candidate

This is separate unfinished native-RNIC work, not a released bitstream,
standard verbs implementation or native host-DMA success. Existing FPGA,
verified old sources and the frozen full-board META analysis are untouched.

## Reason for the change

The actual pinned FNS `generate_exh()` previously emitted the MSN/QP table's
`r_key` for every READ request and WRITE ONLY/FIRST RETH. That cannot represent
successive standard RDMA work requests on the same QP with different remote
keys. The running6.17kernel's `struct ib_rdma_wr` has `remote_addr` and `rkey`
per WR. This remote key is NOT the local SGE lkey: local PD/lkey/VA/range,
page registration and in-flight DMA ownership still require their own checks.

`per_wr_context.patch` is applied ONLY to a fresh verified FNS copy AFTER the
separate sequential metadata reset patch. Exactly3allowlisted files change:
transport header/implementation and retransmitter header. Original pinned
checkout, generated old/STATE/META RTL and current frozen CAD snapshots do
not change. No smaller table/QP/FIFO, disabled protection/integrity/retry,
shorter timer, slower clock or new timing exceptions are used.

## Explicit SQ ABI, no zero-key sentinel

The old request has240bits; its high32parameter bits were unused. They now
hold the full remote key. One appended validity bit selects explicit per-WR
key versus the legacy QP-table policy. The logical width is241bits; the
byte-aligned AXI stream width is248, verified on actual new HLS output.

| New SQ bits | Meaning |
| --- | --- |
|31:0|Existing opcode|
|41:32|Existing QP number|
|42|Existing source-host selector|
|43|Existing last flag|
|47:44|Existing offset|
|111:48|Existing full local address|
|175:112|Existing full remote address|
|207:176|Existing length|
|239:208|Full32-bit per-WR remote key|
|240|Explicit key valid, including when key is0|
|247:241|Zero padding|

Legacy C++ constructors set validity0. New explicit requests set it1;
`rkey==0` NEVER means fallback. `rocev2_wrkey_sq_adapter.v` has a static,
validated mode: legacy mode preserves all240bits and adds validity0;
explicit mode replaces only bits239:208 and sets validity1. QP/host/address
bits are never stolen or aliased. The adapter is connected in a NEW frozen
integrity-transport derivative below, not in the immutable original sources
or running/frozen META board. The adapter unit pass alone is not proof of
generated HLS packing or legacy wire compatibility.

## Ownership context through retry

The actual normal-event, insertion-address/length, merged-entry, stored
metadata and retransmission-event paths now retain the exact key plus its
validity. The real retransmitter's partial READ updates keep these fields
while advancing addresses, length and PSN. The source-host selector is also
retained: the old retry path forced internal memory even when the initial
request selected host memory. Preserving that bit is NOT implementation or
proof of the missing registered-host-source DMA frontend.

All2000metadata entries now contain13fields rather than10. The same explicit
complete-table initialization remains mandatory before any request admission;
the3new fields are explicitly cleared too. Existing STATE reset and sweep
restart semantics are retained in source. C++ startup tests alone do NOT
prove warm hardware reset, interrupted sweeps, FIFO scheduling or X/Z safety.

## Current bounded evidence

Preparation `wrkey-source-001` freezes all source/profile inputs before any
compiler. It is deliberately `pass_test=false`: source preparation is not
functional success. New HLS construction uses the original4ns/part/STATE
settings through the copied driver and records pre/terminal input identities.
HLS success cannot authorize board selection/programming.

Actual HLS C++ test `wrkey-csim-004` passes25003assertions in0.049s after an
8.83s GCC13/C++17 compilation.38actual non-system include dependencies are
hashed BEFORE and AFTER compilation, alongside exact source and frozen input
checks. Actual functions exercised: local request handler, metadata merger,
extended-header generator, metadata table and complete retransmitter pipeline.
Checks include41real RETH outputs, key0/high-bit/all-ones/alternating keys,
same QP, both host selectors,6001metadata responses across2000entries/all13
fields/append preservation,13actual retry events, selected NAK/timer retries,
READ partial advances and24-bit PSN wrap. This is C simulation, NOT actual
generated RTL, wire ICRC, native PCIe, timing or general NAK/recovery proof.

Early Csim001returned1because the result serializer inherited hexadecimal
formatting; its raw output is retained, not silently counted as a report pass.
Csim002passed the earlier bench but is historical after extra constructor
checks/C++17. Csim003failed to compile a new test's temporary ACK argument
against the original non-const-reference constructor; the fixture was corrected
without changing the design/constructor. All attempts/logs remain separate.

The5new portable tests pass in0.038s:3synthetic patch-scope/dry-run/refusal
tests and2actual adapter RTL tests. They are NOT HLS functional evidence.
`probe_wrkey_metadata_reset.py` is prepared for all8024original reset/storage/
append checks,16resets/interrupted sweeps and unchanged backpressure/deadlines,
with explicitly reviewed384-bit response/512-bit request packing. It refuses
unexpected actual ports. The new HLS001/session79137is now terminal0,138files
hash`716f5d9262ac414f88406600f5d88fe83a9bf2fa122b49eec2fd1aa8584a8f2a`.
Actual SQ248and metadata384/512ports are verified. HLS-only estimate is
25114LUT/64686FF/85BRAM18K/4.043ns, versus META24981/64294/77/4.043ns.
This is NOT a placed/routed timing or full-board capacity result.

Fresh four-state new table001/session24485now passes all8024checks:
4023zero/2000data/2001append,16resets,100235clocks, including interrupted
sweeps/no early admission/output backpressure and all13fields through actual
FIFO ports. No internal forcing, smaller table or deadline relaxation.
New IPv4-reset001also passes88constructor observations. Those are narrow
actual generated modules, not full per-WR/legacy/protected wire success.

## Explicit delivery and current four-state wire evidence

`fpga/prepare_wrkey_transport.py` creates NEW `wrkey-transport-profile-001`.
All138raw716f5d92HLS files are byte-identical copies. Only a NEW copy of
the original integrity bridge's SQ interface is derived: static key-mode
parameter(default legacy1), separate32-bit key input and explicit adapter
connections to the248-bit core. No generated HLS logic/header/data repair.
The140delivered files have aggregate
`569df76e3fbd33346ce830e580fc9671dd8ae33e6c410b0e7b79018681cec828`.
Preparation is deliberately NOT a functional pass or image authorization.

The finite runner excludes the original bridge exactly once, binds the
actual completed HLS record and reconstructs the permitted derivation.
Edited self-consistent manifests cannot hide changed raw/adapter/bridge
bytes or missing/extra files. HLS instance hierarchy and original benches
stay intact. Native mode0always uses the exact supplied key, including0;
legacy mode1retains old240bits with validity0.

All current records below pass four-state Icarus with30scompile/120ssimulation
bounds. No internal forcing, shorter timer or weakened DUT/assertion:

| Current record suffix | Actual finite checks |
| --- | --- |
|wire-read003 / wire-write003|4requests/one QP;0,80000000,ffffffff,12345678keys;64-bit remote VA,24-bit PSN wrap, length/padding/IPv4checksum/ICRC;260WRITEbytes|
|wire-nak-read004 / wire-nak-write004|Actual IPv4 PSN-sequence NAK(syndrome60),4real replays after4original requests;all8keys/addresses/PSNs/payloads/ICRCs;520WRITEbytes and original host selectors on initial/retry commands|
|native-control002|Actual enforcing AXI/CSR/parent-guard/same-port/protected HLS/page/RAM/mux/generic PCIe RTL;130WRITE/195READbytes; unchanged protection/lifetime/sideband assertions|
|legacy-read002 / legacy-write002|Old65-byte initiator inside dual wrapper;65READcapture+127sentinels; unconfigured responder forbidden descriptors/TLPs|
|read-error002 / fence-error002|Actual generic PCIe UR/parent/protected fault path still withholds successful wire response and page-release proof|
|app-read65001 / app-read4097001 / app-write65001 / app-warm001|Original APP3x65/3x4097READ/PSN wrap,12291payload+253sentinels;3x65WRITE/cumulativeACK;2x4097distinct warm payloads/stale READ FIRST/backpressured host frame,8194payload+254sentinels|

Normal/retry key packet cases take25.28..26.28s. Native/control112.69s,
legacy76.31/75.12s, UR48.80/49.05s, original APP32.45/91.19/31.92/76.70s.
Memory/peer/root-complex/MAC remain MODELS. Explicit native-key mode is
tested at the IP transport boundary, NOT through a native host WQ/provider.
Whole-parent traffic, registered host pages and hardware DMA are not proven.

Actual patched parent/core/app compile002also passes board MAC16/external64/
sync128/globalDMA19/app16parameters, excluding exactly the duplicate original
bridge/adapter. All compiler warnings are retained; no parent/core/data stub.
Parent/app still selects legacy default mode. Compile-only, not traffic.

Fresh raw-HLS timer001passes8621169cycles/26retry events/all8QP ACK restart/
stop phases and warm reset; first retry250002..250007clocks at4ns. Explicit
30sVerilator limit/two-state/power-up-delta scope; not native/four-state timing.
Full portable018/session46585passes162methods(187.559s), source-checks017/
session23458also0. The7new delivery tests are SYNTHETIC interface/provenance/
refusal/API checks, not HLS/wire evidence.

Retained failures: NAK001had an `endend` fixture syntax error. NAK002and
first native/legacy/error001completed RTL checks but report assembly failed
on duplicate identity keyword arguments. Metadata extensions are now
delivery-prefixed and a synthetic API regression covers that boundary;
no DUT/check was bypassed. Earlier normal001/002, NAK003and parent001are
historical after helper changes. Current selected records above rerun the
same conditions against the final helper and ALL finish0.

Remaining: complete original13-size/large-capture/PMTU/release coverage;
actual board/native per-WR WQ submission integration and resulting original
full-board physical/CDC gates;
real registered host-page source DMA/lifetime and standard kernel/provider/
WQ/CQ/verbs. SEND/RECV/immediate/Atomic/concurrency/error/recovery/congestion
and other full-goal requirements remain open. No hardware/reboot/push action.
