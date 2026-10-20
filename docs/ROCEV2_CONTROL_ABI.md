# Experimental registered-memory control path

This is a prototype NEW identified control region, **not the deployed ROC2
BAR API, a registered RDMA device or native DMA proof**. No module was loaded,
live MMIO executed, real user pages pinned or FPGA programmed in this stage.
The old running READ/WRITE image must not be probed with writes from this ABI.
`kernel/rnic_regs.h` is the kernel-visible register/word/opcode definition.

`rocev2_controlled_responder.v` composes the actual AXI mailbox,
`rocev2_mr_control.v` publication sequencer and tested paged/HLS responder.
All raw MR/PTE/QP config ports are PRIVATE. There is no direct host bypass
that can register an MR and accidentally reopen admission before PTE seal.
The live profile MUST connect `parent_dma_drained` to actual application
descriptor/TLP/RAM ownership evidence, not a constant or a timeout. The
current offline probe explicitly MODELS that input and the PCIe engine/host.

## Transaction and lifetime rules

The controller exclusively owns8slots. Each mapping has a64-bit owner cookie,
full allocated32-bit generation key, trusted PD and MR/PTE-created state.
Each subcommand has a separate nonzero strictly increasing32-bit sequence.
Sequences and generation keys refuse exhaustion/reuse, never silently wrap.
Across FPGA/driver/OS lifetimes the caller must retain a generation watermark
and coordinate shared reset with actual parent drain/closed QPs. Neither a
controller reset nor a saved software counter is DMA cancellation.

| Command | Meaning and successful proof |
| --- | --- |
|1EPOCH | Initial trusted generation floor; no QP/mapping may exist. Only after seed AND final real drain: flags14(QPs closed/table invalid/DMA drained), returned key is the floor. Not a hardware reset. |
|2BEGIN | Close new admission, drain old work, allocate the ACTUAL MR key, then BEGIN PTE with that exact key. Return private key only; flags0, still building/paused. |
|3PAGE | Load one aligned DMA64 page under matching cookie/key; flags0. Gaps between page commands stay paused. |
|4SEAL | Actual PTE seal requires every page. Return published flag16; admission remains paused until this reply is consumed, then resumes only if RUN was requested and no building/tainted entry remains. |
|5INVALIDATE | Match owner/key (key0 allows uncertain-key cleanup), invalidate MR then PTE, recheck endpoint AND actual parent drain. Only then flags3(invalidated/DMA drained), returning retained generation key. |
|6QP | Configure trusted QP/PD/peer/IP/PSNs while closed/drained, wait for actual QP-ready; flags0. |
|7RUN | Requires epoch/QP ready and no building/tainted entry. Reopen only after the owned reply is consumed. |
|8STOP | Stop new admission and wait actual endpoint/parent drain; flags2. Does not clear QP state, reset hardware or permit reseeding an already-used epoch. |

Once BEGIN claims a slot, errors retain owned building state. Duplicate/missing pages and failed
seal never publish. Invalidation errors retain taint/ownership. A BEGIN that
never created a hardware header can still be cleaned by an actual INVALIDATE
absence certificate: hardware exclusively knows the slot has no MR/PTE owner,
retains its generation, and independently proves global endpoint/parent drain.
It is not a successful no-op software callback. A stale owner cannot use this
path to touch a currently occupied slot. The shared C lifetime contract still
checks cookie, slot, known key or minimum required generation before unpin.

Unexpected config responses, malformed allocated keys or endpoint faults
produce sticky fatal quarantine. Already-valid config requests are never
withdrawn under backpressure; only their accepted response may drain after
fault, without a success/release reply. No timeout reopens admission/unpins.
Parent drain is rechecked AFTER epoch seed and after BOTH invalidation acks,
not merely when the command initially starts. Accepted partial packets and
their memory/TX responses continue draining while new admission is closed.

## AXI-Lite mailbox

Region-relative32-bit little-endian registers, ID`0x524e4331`, ABI`0x00010000`,
features1(paged MR control ONLY, not standard RDMA capability bits):

| Offset | Register |
| --- | --- |
|00/04/08/0c | ID/ABI/features/status |
|10 | Full-strobe write1 doorbell; snapshot ALL21staging words once |
|14 | Full-strobe ACK with the EXACT held reply sequence; wrong/stale ACK does not consume it |
|18 | Full-strobe write1 clears parser error ONLY when idle, endpoint quiet and actual parent drained; no controller/DMA reset |
|1c | Last queued sequence |
|20..70 |21staging words from `enum as02_ctl_word` in the kernel header |
|80..9c |8held reply words: sequence/op/cookieLo/cookieHi/slot/key/error/flags |
|a0/a4/a8 | Building-active-tainted masks/controller last sequence/fatal code |

Staging includes sequence, opcode, cookie64, slot/key/PD/access, IOVA64,
length32/first-user-page-offset, page index/DMA64, QP/peer/IP/PSNs. Byte strobes
work on staging; doorbell/ACK/clear require all4strobes. Reserved high bits
are rejected before narrowing. Editing staging after doorbell cannot change
the queued command. A busy/invalid doorbell sets sticky MMIO_ERROR and never
overwrites the pending snapshot. Replies stay owned and stable across reads
and AXI R/B backpressure until the exact ACK. There is no reset register.

IMPORTANT: this pinned Corundum `axil_reg_if` returns AXI OKAY even on its
internal register timeout. Bus completion is NOT command success. Unknown/
unaligned accesses set sticky MMIO_ERROR (unknown reads return0); software
must inspect status and the matched hardware reply. The controlled top also
closes new packet admission on parser error without canceling accepted work.

Status bits0..11 are READY/BUSY/REPLY/PAUSED/FATAL/EPOCH/QP/RUN/MMIO_ERROR/
PARENT_DRAINED/ENDPOINT_QUIET/ENDPOINT_FAULT. These are explicitly checked by
the C client; unknown bits/device versions are not silently adopted.

## Actual kernel implementation and evidence boundary

`rnic_io.c` is the shared metadata transport client, not a payload-copy path.
It validates the NEW ID/ABI and fresh paused/empty state before ANY write;
the old ROC2 signature is rejected. It stages all21words, reads them back,
marks uncertainty BEFORE the posted doorbell, and validates response sequence,
opcode, cookie64, slot, full key, error and exact proof flags. It rechecks
fault/status/sequence before ACK and waits for actual reply consumption.
Wrong/timeout/ambiguous results return zero output and retain pending owner
metadata. A valid nonzero hardware error is a transport completion, NEVER
a publication or unpin proof. No-op/default transport callbacks do not exist.

`rnic_hw.c` supplies real kernel `readl`/`writel`, monotonic time and bounded
sleepable polling. Its MR callbacks seed the trusted epoch, BEGIN/load actual
pinned scatter/gather DMA pages/SEAL using the returned key, and INVALIDATE
only with actual flags3and returned generation. Callback proofs are populated
from validated hardware replies, not from requested metadata. They link with
the existing ib_umem lifecycle library against the running6.17kernel; this is
NOT runtime MMIO or pin testing, and still no bus driver/ib_device/provider.

The caller serializes control; the MR callback holds one mutex across the
entire BEGIN/PAGE/SEAL sequence. Bus-driver lock ordering must preserve the
pool->I/O order. On uncertainty the pool retains PUBLISHING/REVOKING objects
and device/module/page references. Explicit late-reply reconciliation only
resynchronizes transport; it does NOT unpin or change the MR lifecycle. Lost
ACK with no remaining reply, exhausted control sequences, endpoint faults,
hot-unplug and hardware reset cleanup still need a proven outer recovery
procedure. Do not free a busy pool/device or infer drain from no response.

### Terminal logical detach (not hot-unplug recovery)

The shared C client now has `as02_ctl_detach()`. Under the SAME caller
serialization as execute/reconcile, it marks this attachment terminal
without ANY transport read/write/time/wait, ACK or hardware reset. Execute
and reconcile subsequently return `-ENODEV` with zero output. Even a valid
late invalidation/drain reply cannot be consumed or turned into a release
proof after detach. Pending/uncertain state, full expected owner words and
monotonic sequence remain intact; the same object cannot be reinitialized.

`as02_rnic_hw_detach()` serializes with the real kernel I/O mutex, marks the
control attachment detached, then clears its BAR pointer. Real readl/writel
callbacks assert that mutex and reject detached/NULL mappings. Initial
identity reads are now also under that mutex. A future actual bus driver
must stop new users and call this BEFORE BAR unmap, and retain the control,
pool, page, device and module objects while ownership is unknown. This
function neither unregisters an ib_device nor solves their reference lifetimes.

The pinned parent `mqnic_common_remove()` deletes/uninitializes the auxiliary
child before `mqnic_pci_remove()` clears bus mastering and unmaps BARs. Thus
that future auxiliary remove callback has an ordering point for logical
detach, but merely returning from it is NOT DMA drain. No busy pool/page
may be released because a device disappeared or an MMIO pointer was cleared.
There is still no actual RNIC auxiliary driver or runtime hot-unplug test.

I/O007passes14actual shared-C/UBSan cases (0.218s), including idle and
completed-history detach, ambiguous posted command preservation, exact late
drain reply refusal, repeated no-I/O calls and reinitialization denial. The
report counts successful tests, not merely started names. Real kernel
callbacks are compiled separately; this portable test models MMIO/replies,
does not execute readl/writel, pin pages or prove native removal safety.

Selected finite evidence (all offline):

- MR-control003:11actual sequencer/MR/PTE tests with QP/drain models, including
  generation reuse/exhaustion, owner denial, paused publication, partial and
  duplicate pages, never-created cleanup and post-ack drain rechecks.
- Control-regs003:6actual mailbox/Corundum AXI tests against the kernel ABI,
  independent AW/W, byte strobes, queued snapshot stability, backpressured
  replies, stale ACK, parser-error recovery, high/unaligned denial.001was a
  testbench-only illegal wire assignment and is preserved as a failed log.
- Controlled-responder003:actual complete AXI/control/HLS/paged path after
 registered RAM descriptor extents (same protection/ownership rules);
 20matched host commands/replies,3registered MRs,19frames/13rejects/1ICRCdrop/
 5successful operations,130WRITE and195READ bytes. Invalidation is submitted
 during an active WRITE and proof waits for its memory/final-TX completion;
 old key is rejected and fresh key16works. Raw config ports are not driven.
- I/O003:10actual shared-C/UBSan tests against a MMIO/reply model: all8commands,
 full64-bit metadata, bad identity/key/proof, pre-doorbell failures, ambiguous
 doorbell/ACK, timeout/late reply and sequence exhaustion. Not kernel runtime.

The actual parent PCIe TLP path, new native board profile/clock-route-CDC gate,
runtime registered-host-memory cases, standard kernel RDMA/verbs/provider/
WQ/CQ/SEND/RECV/etc. remain required. This control stage is NOT the full goal.

The next offline probe`tests/probe_controlled_pcie.py` now also composes the
actual native-shaped3-port interface/application and2-port control/data DMA
muxes and actual generic PCIe read/write engine. Its parent-drain input is
derived from actual busy/descriptor/TLP/RAM evidence, not a constant. Host
AXI and hard-IP/link/root-complex/host memory still remain models; this is
not execution of the real kernel callbacks or native BAR/PCIe integration.
The new profile requires engine tag width19to preserve the page engine's
full16-bit tags through both routing levels. See`ROCEV2_DMA_BACKEND.md` for
selected records, actual UR error tests and explicit ordering assumptions.
