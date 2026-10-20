# Experimental registered host-memory support

The kernel source in `rdma/rnic/kernel/` is a compile/link support library,
**not yet a registered RDMA device, bus driver, userspace provider or deployed
data path**. The running image still has application DMA disabled. No module
from this directory has been loaded and no runtime user-page pin/DMA test has
been executed. Do not load it merely to make `ibv_devices` list an adapter.

## Pinning and lifetime

`mr.c` uses actual `ib_umem_get`, `rdma_umem_for_each_dma_block` and
`ib_umem_release`, not `virt_to_phys`, physically-contiguous assumptions or a
CPU payload-copy replacement. The future RDMA driver must supply a real
initialized `ib_device` and actual hardware callbacks. There is no successful
default/no-op callback. Page mapping, long-term pinning, memlock accounting
and dirty release are delegated to RDMA core. Unsupported ODP, relaxed
ordering and other access flags are refused; supported basic access still
requires the actual operations to exist before exposing them as capabilities.

The pinned object's `umem->iova` remains the original user address. The RDMA
core DMA-block iterator AND release accounting use it. Remote IOVA is stored
separately, so its page offset need not equal the user pointer's first-page
offset. The Linux implementation and pinning documentation were inspected:
[Linux6.17 umem.c](https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/infiniband/core/umem.c),
[pin_user_pages](https://docs.kernel.org/core-api/pin_user_pages.html).

Each pool owns up to8mappings, each at most256x4096B pages including its first
page offset. Mapping objects retain pool/device/module references. Failed or
ambiguous publication remains pool-owned and pinned; it is not discarded on
an error return. Pool teardown returns EBUSY while any mapping remains and
retains ownership. The eventual driver's remove/error path MUST NOT free the
pool/device while that happens; actual stop/drain cleanup is still required.
These entry points are serialized sleepable control paths, not send/poll fast
paths. The caller owns an execution/module reference while invoking them.

The shared portable `mr_contract.c` implements:

1. BUILDING: validate user/IOVA64 range, access, first offset and cookie; fill
   unique aligned DMA64 pages, including legal zero/alias DMA bases.
2. READY: seal only when every required page exists; pages become immutable.
3. PUBLISHING: enter BEFORE calling hardware, so a lost/error response cannot
   be mistaken for never-published memory.
4. LIVE: accept only matching cookie/slot/full-generation-key proof.
5. REVOKING: request invalidation/drain; failure retains all ownership.
6. DRAINED: release only after matching invalidation AND actual DMA-drain
   evidence. A timer, no-error inference or resetting one FSM is not evidence.

Only never-published BUILDING/READY or DRAINED objects can unpin. In-place
reinitialization of an existing layout is rejected. Software cookies refuse
wrap. Fresh key epochs require closed QPs, invalid MR table, drained DMA and
a trusted generation floor. Highest/slot generations advance from actual
proof; stale, mismatched or exhausted keys fail. A persistent host watermark
across driver/OS lifetimes and real reset/drain proof remain outer-driver
requirements, not something this in-memory library provides.

## Hardware page translation and publication

`rocev2_mr_page_table.v` resolves already-authorized full-key/slot/offset/extent
leases to page-bounded DMA64 pieces. It does not perform QP/PD/access checking.
The MR guard must check those FIRST, and its authorized offset/full key must
remain bound to the same operation through completion.

The new `rocev2_paged_memory_backend.v` connects that table, a serial page
descriptor splitter and actual Corundum staging RAM/source/sink. See
`ROCEV2_DMA_BACKEND.md` for error retention, readback fencing and the explicit
modeled PCIe/host-ordering boundary. `rocev2_paged_responder.v` now binds the
actual HLS/guard's full key/relative offset to that backend and supplies
pause/config arbitration. The new `rocev2_controlled_responder.v` adds the
exclusive transactional sequencer/AXI mailbox; `rnic_hw.c` supplies real
kernel callbacks using the same ABI (compiled, not executed on hardware).
Board/bus-driver/native-MMIO/pin integration remain unimplemented. Those callbacks close admission
across this entire publication sequence:

1. Allocate an MR key while packet/work admission is blocked.
2. BEGIN the PTE header with that exact allocated key; load actual DMA pages
   from the pinned scatter/gather mapping and SEAL every page.
3. Publish the key only after both tables acknowledge matching configuration;
   then reopen admission. Any ambiguous error retains mappings/quarantines
   the pool and requires invalidation/drain cleanup.
4. Deregistration closes admission, invalidates the MR, drains ALL leases and
   DMA, invalidates the matching PTE header, and only then confirms unpin.

Never predict/consume a PTE generation before MR key allocation: a partial
failure could otherwise desynchronize their generations. A missing/inactive
PTE must never become raw offset-to-physical DMA, even if MR metadata is valid.
There are no default successful callbacks. The new explicitly selected
`as02_rnic_mr_hw_ops` validates real mailbox replies and generates proof from
them; it is not bound to a live device by this compile/link library.

The new publication controller holds the real gate across the
ENTIRE sequence, including gaps between page commands and held responses.
It does not automatically reopen after merely allocating an MR key or loading
the final page without SEAL. Close/invalidate must return matching ownership
cookie/slot/generation plus actual parent-engine drain proof; the composite's
error-retained state must never be converted into a successful unpin by timeout.
The controlled top hides the raw config ports. Its complete AXI/HLS simulation
uses20host commands, including invalidate during an active WRITE and fresh
key reuse. Actual parent PCIe drain/native host memory remain modeled, not
proven by those sequences. See `ROCEV2_CONTROL_ABI.md` for ownership/ABI and
late-reply/ACK/error recovery limits.

## Evidence and build

`rocev2-rnic-mr-contract-001.json` records9finite C/UBSan tests and3330page
resolution queries against an independent integer oracle. Full-operation
key/PD/access/range checks precede the first returned segment; denied outputs
are zero. Tests include64-bit edges, noncontiguous full-DMA64 pages, independent
user/IOVA offsets, stale epochs, incomplete immutable tables and uncertain
publish/revoke ownership. They do not exercise actual kernel page pins.

`rocev2-rnic-page-table-001.json` records8actual-RTL tests against that shared
C contract, including all8slots and256pages, generation reuse, missing/sealed
state, whole-operation range errors and stalled configuration/query ownership.
`rocev2-rnic-paged-backend-008.json` additionally connects actual page table,
splitter, backend and Corundum RAM in12short tests. PCIe descriptors, host
memory and ordered visibility remain modeled. The actual AXI/controller top
and compiled MMIO callbacks are described in`ROCEV2_CONTROL_ABI.md`; current
full95batch005records include controller004/control-regs004/I/O003.

The support library compiles/links against the running6.17.0-1033-oem headers:

```sh
make -C rdma/rnic/kernel CC=x86_64-linux-gnu-gcc-13 module
make -C rdma/rnic check
```

The first command uses W=1. BTF generation is skipped when vmlinux is absent;
that is not a runtime test. Real `reg_user_mr`/`dereg_mr`, PD/QP/CQ/queue/verbs
callbacks, kernel/uAPI provider, board CSR/DMA integration and bounded native
functional tests remain required before usable RNIC support can be claimed.
