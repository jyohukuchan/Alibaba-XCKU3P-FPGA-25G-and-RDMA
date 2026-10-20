# Experimental Corundum DMA backend

`rdma/rnic/rtl/rocev2_corundum_dma_backend.v` connects authorized contiguous
memory commands to the real Corundum application DMA descriptor/RAM interfaces.
It instantiates the existing `dma_client_axis_sink`, `dma_client_axis_source`
and `dma_psdpram` RTL. Its RAM is on-device DMA staging, **not a CPU-copy
replacement for host DMA**. The deployed image still has app DMA disabled;
this backend is not yet board-integrated, and native host DMA is unverified.

## Data and visibility sequence

For an incoming remote WRITE:

1. Accept one already-authorized DMA64/length32/tag16 command.
2. Receive the exact payload through the AXI-Stream sink into staging RAM.
3. Wait for the sink's tagged status, including actual RAM write completion.
4. Issue a host-memory DMA WRITE descriptor, without immediate data.
5. Wait for that descriptor's matching status, then issue a one-byte DMA READ
   to the **same host address**, into a separate reserved staging-RAM line.
6. Wait for the readback fence's completion and all RAM accesses to drain.
7. Return the backend status; the protected responder still holds its MR
   lease and wire response until this succeeds and the response drains.

The fence is a conservative visibility mechanism, not a timed delay. Its
ordering argument assumes the same requester/function/TC, non-relaxed,
snooping requests, and the write descriptor retiring after its last request
has entered the ordered PCIe transmit path. AMD's ordering documentation
states that later non-relaxed reads may not bypass preceding writes.
Applying that rule to this backend's host-read fence is an integration
inference; it still needs actual engine/link/host verification, not merely
the descriptor model's programmed behavior.
[AMD PCIe transaction ordering](https://docs.amd.com/r/3.0-English/pg347-cpm-dma-bridge/Transaction-Ordering-for-PCIe?contentId=NuS9Eo3CFntd7EgWXhtctA).

The locally pinned Corundum path is `mqnic_core_pcie_us -> mqnic_core_pcie
-> dma_if_pcie`, **not** the older standalone `dma_if_pcie_us` engine.
`mqnic_core_pcie_us.v` explicitly passes `TX_SEQ_NUM_ENABLE(1)`;
`dma_if_pcie_wr.v` waits for the last operation's TX sequence acknowledgement
before status, and both generic read/write engines emit TC0/attribute0 and
the same requester-ID input. The backend header mentions the older engine's
`RQ_SEQ_NUM_ENABLE` name; actual integration must verify the generic path's
`TX_SEQ_NUM_ENABLE` plus its live sequence feedback, arbitration and requester
identity. The header now names both generic and older standalone US forms.
Never assume that a similarly named parameter alone proves the
end-to-end ordering or host coherency conditions.

For a remote READ, issue host DMA READ into staging RAM, validate its status
and RAM drain, then send RAM bytes through the AXI-Stream source. The backend
waits for BOTH the source's tagged status and the externally accepted last
data beat before producing its own status. Descriptor enqueue is not memory
completion, and source prefetch is not output-stream completion.

## Protection and error ownership

The caller must already authorize key/PD/access/full64-bit range and supply
a mapped DMA address. This module additionally rejects zero tags/length,
staging overflow and a65-bit address-end overflow. Defaults are8192B staging,
8128B maximum payload, a64B reserved fence line,16-bit DMA length/tag, and
two256-bit RAM segments/512-bit AXI streams. It does not implement arbitrary
virtual-page scatter/gather translation, pinning or `ibv_reg_mr`.

Full external RAM select/address and enabled-byte bounds are checked before
the smaller RAM can alias high address bits. Host-read DMA may write only its
exact issued payload/fence span. Host-write DMA reads only allocated staging
words. Per-segment pending counters prevent a premature status from retiring
RAM ownership. Byte-enable padding does not become a host write extent.

Failed DMA READs never return old staging contents. After matching error
status and RAM drain, the backend emits the full expected number of **zero**
bytes and then a nonzero backend status. The protected responder has not
committed, so its buffered success response is never exposed on the wire.
This cooperative drain handles an early DMA error without deadlocking the
frontend's data-before-status contract. Failed WRITE/fence statuses are also
errors, never a successful wire ACK. They leave the backend faulted after
the caller consumes the error. Proper wire NAK/QP-error handling is separate
unfinished transport work.

Wrong tags, unsolicited statuses, malformed RAM accesses and client/stream
contract errors produce a sticky fault. An outstanding authorized descriptor
valid is **not withdrawn** under backpressure, and already-issued DMA retains
its RAM ownership. Only matching drained status may retire that in-flight
descriptor, even after fault. There is no timeout that silently releases a
memory mapping. `enable=0` prevents new commands but does not cancel existing
work. `dma_drained` means this backend has no outstanding DMA descriptor/RAM
access; it is NOT a substitute for the responder's MR/QP/response lease gate.

Reset is not DMA cancellation or MR revocation. Before unmapping/unpinning,
the future kernel driver must stop new QP work, establish actual engine drain
or successful cancel/reset, retain pages during cleanup, and establish fresh
keys before reopening QPs. Do not reset this module to manufacture a drained
flag while the parent PCIe DMA engine remains live.

## Evidence boundary

`rocev2-rnic-dma-backend-003.json` records14finite RTL tests with actual
Corundum RAM/source/sink/backend but a **modeled descriptor engine and host
memory**. They cover1/31/32/63/64/65/4095/4096B, unaligned DMA64 addresses,
all host bytes/guards, delayed posted visibility and readback, READ-zero drain,
WRITE/fence errors, wrong-tag retained/drained ownership, high-RAM alias and
byte-range denial, malformed input, overflow/zero tag, and disable/drain.
Both default16-bit and actual board15-bit RAM-address geometries are tested.
The first001attempt had three testbench errors (waiting for ready before
driving a nonmatching keep, and checking inactive RAM-segment ready bits);
its failure log/report remain preserved, not promoted to a pass.

`rocev2-rnic-protected-dma-005.json` connects actual generated HLS, actual
MR/packet guard, this backend and actual Corundum staging clients/RAM in the
same simulation. It removes the earlier direct memory source/sink model.
This sequence uses the actual board15-bit/segment9-bit RAM geometry.
19input frames yield13local rejections,1ICRC drop,5successful RoCE operations,
two DMA WRITEs, three payload DMA READs and two readback fences. Every
65-byte WRITE is checked through the actual segmented staging-RAM read
responses, and all three65-byte network READ responses match. Full wire
checksums/ICRC/PSN/QPN/AETH and invalidation ownership are checked.

That integrated test STILL MODELS the PCIe descriptor engine/link/host memory
and strict ordering. It is not actual TLP-engine/native DMA, pinned-memory,
driver/provider or full-board signoff. Those remain required next steps.

`rocev2-rnic-dma-ooc-001.json` preserves an isolated routed4ns timing failure
(WNS-0.057ns) on input keep -> Corundum sink status-FIFO logic. The candidate
now validates into a real AXI skid register before the original sink;
status still waits for actual staging commit, not just skid acceptance.
`rocev2-rnic-dma-ooc-002.json` passes isolated4ns with WNS+0.027ns/
WHS+0.012ns,3981LUT/3029FF/8BRAM,0failing timing endpoints and0DRCerrors/
critical warnings (oneOOC output-load warning). This is NOT board signoff;
the margin is small and full native clock/routing/CDC gates remain required.

## Paged host-memory candidate

`rocev2_paged_memory_backend.v` now composes the unchanged contiguous staging
backend with `rocev2_mr_page_table.v` and `rocev2_page_dma_engine.v`. Its command
address is explicitly named **`s_command_offset`**, not DMA: it is an already
authorized MR-relative offset plus a full allocated MR key. Only the page
table can supply physical DMA64 descriptors to the parent engine. The
protected packet frontend now exposes/binds that key/offset contract;
`rocev2_paged_responder.v` connects it to the paged memory backend. The complete
path is tested with actual generated HLS, but NOT a board/host PCIe profile.

The table supports8MRs, up to256mapped4KiB pages each, full64-bit DMA bases,
and an initial user-page offset independent of remote IOVA alignment. BEGIN
uses the already-allocated MR key, PAGE loads unique aligned page indices,
SEAL requires every page, and INVALIDATE retains the generation. Whole
remaining-operation range/key checks occur BEFORE issuing the first segment;
an invalid request cannot produce a valid-prefix DMA side effect.

The splitter preserves staging offsets across page boundaries and waits for
each matching physical status before issuing the next piece. Physical tags
are unique/monotonic within the reset epoch and refuse16-bit exhaustion;
aggregated status retains the original command tag. A successful WRITE has
one host-read fence after all payload pieces, not one fence per page. This
continues to rely on the SAME unverified physical ordering assumptions above.
The first user-page offset and MR-relative operation offset both participate
in every translation, including the fence.

PTE configuration is permitted only with external responder quiescence AND
idle memory/splitter ownership. A nonquiescent responder can still submit its
already-authorized command: a held invalidate must wait, not deadlock it.
The control path must stop new packet/MR admission across the entire MR/PTE
publication transaction: allocate MR key while admission is closed, load and
seal the PTEs with that exact key, and only then publish/reopen. This global
transactional CSR commands are now implemented by`rocev2_mr_control.v` and
`rocev2_control_regs.v` in the actual`rocev2_controlled_responder.v` top.
Real kernel MMIO callbacks compile/link using the shared ABI, but live bus/
MMIO/pin/native PCIe integration is still absent. See`ROCEV2_CONTROL_ABI.md`;
direct raw config benches alone are not the controller's proof.

Every translation, descriptor, RAM or status failure retains the mapping
lease. The composite refuses to assert `dma_drained` after ANY fault, even
when individual physical statuses later drain. In particular, partial WRITE
failure may leave posted writes without the normal success fence: there is
NO automatic unpin/cleanup proof. The driver must retain pages until a
separately proven actual PCIe stop/drain/reset cleanup. Backend RAM faults
halt future page pieces but preserve any already-valid stalled descriptor.
Neither timeout, disabling admissions nor resetting only this FSM proves
page lifetime safety. READ errors drain zero for the full original extent,
then a nonzero status, never partly valid/stale payload with success.

Selected `rocev2-rnic-paged-backend-003.json` passes12finite tests in2.6s:
all eight1..4096B boundary lengths, independent first-page offset4093,
scattered DMA64 pages including the top64-bit page, actual segmented RAM,
all WRITE/READ and host guard bytes, delayed posted visibility/fence, partial
READ/WRITE/fence errors, stale/unsealed/range denial before DMA, wrong tags,
simultaneous status rejection, held invalidation, disable and RAM-fault halt.
The PCIe descriptor engine/host memory/order are still MODELED. Full-suite
record004 uses the same sources. `rtl/paged_backend_ooc.tcl` separately probes
this composite at isolated4ns with unchanged I/O constraints. Record
`rocev2-rnic-paged-ooc-001.json` is terminal0: WNS+0.087ns/WHS+0.023ns,
0setup/hold/pulse failures,8835LUT/6816FF/12BRAM,0DRCerrors/critical,
1OOC no-routable-output-load warning. This is NOT native DMA, actual pinned
pages, provider/verbs or full-board signoff.

## Bound packet-to-paged-memory integration

`rocev2_protected_responder.v` now captures full RETH key and obtains MR-relative
offset from the SAME successful MR lookup as its authorized address/length.
Both outputs are retained with the command under backpressure; they are not
reconstructed from HLS's48-bit address or by a second untrusted RX parser.
`EXTERNAL_ADMISSION_CONTROL=1` enables `cfg_admission_pause`: it gates only
the first checked beat of a new packet. Accepted partial frames, memory
operations and buffered TX responses continue draining. The legacy contiguous
probe defaults this parameter0; the paged composite hardcodes it1.

`rocev2_paged_responder.v` connects that guard to the real paged backend.
MR metadata's unused contiguous DMA base is forced0; its offset is NEVER
sent raw to the PCIe outputs. Only the matching page table can translate it.
MR/QP/PTE configuration requires the host pause gate. MR and PTE command
pipelines/responses are mutually exclusive; a held response blocks the
other path and QP changes. Invalidation cannot preempt an accepted packet,
memory lease or final TX response. Backend faults close new admission and
retain lifetime ownership. Global quiescence includes both config paths,
backend and wire response; `memory_drained` also requires backend idle and
is not the temporary gap between WRITE payload and visibility fence.

The historical `rocev2-rnic-paged-responder-003.json` exercises the ACTUAL composite and
generated HLS:19frames,13local rejects,1ICRC drop,5successful operations;
12physical DMA descriptors (4WRITE/6payload READ/2fence READ), unique tags1..12.
Every65B operation starts at first-user-page offset3565 + MR-relative528,
crossing two unrelated DMA64 pages as3B+62B; the second page is the top64-bit
page. Every WRITE staging byte, all195network READ bytes, full host guard
memory, response IPv4/ICRC/QPN/PSN/AETH and old/fresh-key reuse are checked.
The earlier direct guard/backend002record predates the composite wrapper;
001also misserialized integer-width binary direction flags in its JSON,
although its raw simulation log records the correct directions. Do not select
that old report as reliable descriptor-direction evidence.

`rocev2-rnic-paged-responder-unit-003.json` additionally passes3finite control
cases with an EXPLICIT transport stub: queued packet waits through full
MR/PTE publication and an explicit reopen; pause plus held invalidations do
not deadlock an accepted partial packet; MR/PTE/QP commands and stalled
responses never capture concurrently. This is not extra HLS wire evidence.

Current `rocev2-rnic-paged-responder-boundaries-002.json` verifies six more actual-HLS
composite operations at1/64/4096B:4161bytes in each direction, PSN wrap from
0xfffffe, every response checksum/header/payload, host guard and pad bytes,
and every one of13physical descriptors. First user-page offset4093forces
64/4096B operations across the scattered DMA64 page boundary, including a
4093-byte piece on the top64-bit page.

Actual-HLS READ-piece2, WRITE-piece2 and fence errors are separately verified
by`rocev2-rnic-paged-responder-{read,write,fence}-error-003.json`. Each produces
one guarded nonzero memory status/fault34, no successful wire response,
no completed operation and NO memory/page-release proof. The first001error
attempts wrongly required the normal success-only drained flag on error;
those logs remain failures. The corrected tests retain the success invariant
and explicitly require no release on errors, not a relaxed lifetime rule.
The complete95method portable suite also passes; composite control cases
use an explicit transport stub, while these separate probes use actual HLS.

The protected-only physical route002(before new key/offset/pause ports) is
terminal0at4ns WNS+0.122ns/WHS+0.023ns,32090LUT/67772FF/41BRAM,0timing
failures and0DRCerrors/critical. That historical pass does NOT validate the
changed frontend or the combined paged top. The source-frozen combined
synthesis156inputs is terminal0with44265LUT/74026FF/53BRAM but estimated
WNS-1.253ns; actual physical route001terminated1with WNS-0.705ns/WHS+0.019ns.
Its worst path was descriptor length -> RAM-end addition -> enabled-byte
range guard -> pending/drain -> FSM CE (15levels), not the synthesis reset
estimate. The exact read upper bound is now registered WITH descriptor
address/length/valid before any handshake; WRITE rounded bound is captured
with the authorized command. Byte/word bounds and completion/lifetime rules
are unchanged. This is a candidate timing fix, not a physical pass.

Current`rocev2-rnic-controlled-responder-003.json` repeats all19frames/
5operations through actual AXI-only control plus HLS/paged DMA,20matched
host replies, all130WRITE/195READ bytes and host guards. It includes active
WRITE invalidation and fresh-key reuse; raw config inputs are private.
Full95batch005and boundary002/error003/contiguous-DMA005revalidate these same
registered-extent sources. The new actual AXI/controller top now synthesizes
with162frozen inputs via`controlled_responder_synth.tcl` (session46864).
Resulting physical/full-board/native/conditionalCDC gates remain required.

## Actual generic PCIe engine and native-shape mux path (offline)

`tests/probe_controlled_pcie.py` replaces the descriptor/status/RAM agents
with the pinned ACTUAL `dma_if_pcie{,_rd,_wr}` and both native-shaped mux
levels:3interface/application ports (application index2), then2control/data
ports (data index1). Other ports are explicitly idle, not a concurrency test.
The actual AXI mailbox/controller/HLS/guard/page table/splitter/staging RAM
remain in the same test. All raw configuration stays private.

This discovers an important native-profile requirement: existing board
`DMA_TAG_WIDTH=16` leaves only13application tag bits after these muxes, but
the page engine deliberately requires16-bit unique physical tags. Do NOT
truncate the tags or pretend that exhaustion/reuse is safe. The NEW profile
must use engine `DMA_TAG_WIDTH=19`, yielding16application bits after the
2+1routing bits. The probe uses these actual widths, application RAM select1,
engine RAM select4, RAM address15/segment-address9,256-bit TLPs,256PCIe tags,
read/write tables256/32 and `TX_SEQ_NUM_ENABLE=1`. The old board configuration
and rollback sources remain unchanged. Full source-bound native gates still
need to validate the new profile separately.

Selected normal record`rocev2-rnic-controlled-pcie-005.json` is terminal0:
19frames/13rejects/1ICRCdrop/5operations,20actual host AXI replies,12physical
descriptors routed through both muxes,8READ TLPs/4WRITE TLPs/2visibility fences,
all130WRITE/195READ bytes and full host padding/guard memory checked. Actual
engine request headers are checked for DMA64, requester`0x8200`,TC0/attr0;
all12actual routed tags have the expected high routing bits`0x60000` and the
original unique low16bits. Independent monitors check TLP ownership during
backpressure. Each WRITE TLP's TX sequence acknowledgment is withheld for
64simulated cycles (256total), and successful descriptor/network completion
or parent-drained proof before that acknowledgment is forbidden.

Parent drain is NOT tied high here: it covers accepted application descriptor
ownership, actual engine read/write busy, pending mux descriptors, TLPs,
completion input and segmented RAM commands/responses; engine errors latch
and refuse proof. This is a concrete offline path, not the final native
parent wiring. Ordinary same-requester/TC attr0 posted-write visibility is
an EXPLICIT root-complex MODEL rule, not physical ordering evidence. The
hard IP, link, TX-sequence source, root complex and host memory remain MODELS;
there are no runtime pins, kernel callbacks or native transactions.

Actual READ-piece2 and WRITE-fence UR completion cases are selected in
`rocev2-rnic-controlled-pcie-{read,fence}-error-003.json`, both terminal0. They
inject a real3DW no-data/Unsupported Request completion into the actual
generic engine, NOT a fabricated descriptor status. The engine reports
DMA error10; the guard must complete its zero/error drain and enter fault34,
with zero success responses/completed operations and no page-release proof.
Even a model-visible WRITE is not releasable after a failed fence.

Earlier normal001failed a TESTBENCH assumption that the generic TLP header
stays unchanged on non-SOP beats. The pinned engine defines the header at SOP
and changes unused later header copies; the root model now correctly uses
SOP metadata while independently checking complete stalled-beat stability.
Earlier UR001waited for the first page-engine fault instead of the later
guarded drain; UR002then incorrectly expected fabricated-model error4/5
instead of actual generic-engine UR10. Their failure logs are preserved;
no DUT permission, drain, fault or success criterion was relaxed.
No failing/estimated timing image is permitted to program the FPGA.
