# Kernel coherent SQ and work-reference support

These are actual new kernel-library implementations, compiled/linked against
the running6.17.0-1033-oem headers, NOT a registered or loaded RDMA driver.
No real page pin/coherent allocation/MMIO/post_send/CQ callback has executed
in Linux. The separate userspace tests execute the SAME C bodies with explicit
kernel-primitive/umem/DMA/HW/CQ MODELS. Neither evidence scope replaces native
driver/provider/runtime/physical/lifetime verification or completes the RNIC.

## Actual MR work ownership, not a sleepable post path

`mr.c/.h` retains its sleepable control mutex and actual `ib_umem` lifecycle.
A separate IRQ spinlock protects published fast views, slot ownership, pool
clients and `refcount_t` work references. Publication exposes a fast MR only
AFTER exact hardware confirmation. Non-sleeping `as02_user_mr_get_work` checks
full local key, trusted PD, complete64-bit range and local-read/local-write
permission against the actual live MR; it does not copy payload or replace
hardware SG translation with a CPU DMA address.

The pool owns base reference1. Close first disables new getters and marks the
MR closing; with ANY work reference it returnsEBUSY BEFORE hardware revoke,
unpin or freeing. The existing invalidation/drain proof is still mandatory
after the last work reference. Work put never drops the pool base, frees an
object, sleeps or unpins. Global uncertain publication disables new getters,
not existing ownership. A queue/client reference also prevents pool destroy
or starting a new MR epoch while queue objects can still access the pool.

Control lock order is mutex -> fast spin; atomic paths never acquire that
mutex or call hardware control, allocation/unpin/device-release functions.
Pool initialized flags use READ_ONCE/WRITE_ONCE; caller must additionally own
stable device/module/pool execution lifetime. These APIs cannot make a stale
raw pointer or arbitrary WR identifier into an object reference.

## Real coherent-ring allocation and posting implementation

`sq.c/.h` owns up to8queues, with2..25664-byte entries each. A queue pool pins
the MR pool/client, actual parent DMA device and support module. It takes
required persisted per-queue epoch watermarks. Allocations use the actual
`dma_alloc_coherent`/`dma_free_coherent` API and returned DMA64 handles, never
virt_to_phys, user physical addresses or the private ib_device dma member.
Full QP bounds, DMA alignment/end, nonzero increasing epochs and command-cookie
exhaustion are checked. Ambiguous hardware allocation stays pool-owned/mapped
with a cleanup handle rather than losing the only lifetime owner on error.

Each atomic `as02_sq_post` uses the actual `ib_rdma_wr`/SGE converter and fixed
little-endian codec, acquires a genuine authorized MR work reference, copies
ONLY the64-byte descriptor into coherent ring storage, and executes `dma_wmb`
BEFORE the required atomic producer-doorbell callback. Kernel shadow entries
retain MR and full WR context. There is no sleeping/allocation/payload copy in
this path. Ring credits are held until actual work retirement, not FPGA fetch
consumer movement. A full ring refuses; stored context is not overwritten.

Any producer-publication error may have reached hardware: producer/data/ref
ownership is NOT rewound/cleared. The queue stops and remains quarantined.
This is not a successful standard post_send error-recovery implementation;
source-bound abort/flush of such outstanding work is still unfinished.

## Completion and destruction gates

`as02_sq_complete` resolves full queue cookie/epoch/QP/PD and expected64-bit
sequence against kernel-owned shadow context. Actual memory AND transport
completion proof is required. A fetch-only proof, unknown status or mismatched
sequence cannot free a WR/MR. WR id comes from retained context, never an
untrusted pointer in a hardware record. Signaled WRs and all error WRs call the
mandatory actual CQ publisher before releasing the MR reference; successful
unsignaled WRs retain the same memory/transport proof requirement but need no
user CQE. CQ-full leaves the entry/reference owned for an exact retry.

Atomic callback lock order is queue-fast -> MR-fast/CQ. The event handler must
not enter while holding its CQ lock. A CQ callback failure must have made NO
CQE visible; event-consumer advancement waits for a successful commit. These
are requirements for the future ACTUAL driver CQ implementation, not proof
supplied by the library or its modeled callback.

Close stops new posts and returnsEBUSY while owned work remains. Once empty,
the real control callback must return a fresh request cookie, exact owner and
last producer plus queue-invalid, fetch/work/wire/completion-drained proof
before coherent unmapping/freeing. Pool teardown with queues/clients retains
device/module/storage ownership. Errors/timeout/reset never imply drain.
Caller cannot free the enclosing driver/pool object after an EBUSY/error return.

## Queue-library evidence and subsequent MMIO integration

`kernel-sq-build-002`:22inputs frozen BEFORE actual W=1/GCC13/running-header
compile/link:19own files,2pinned mqnic headers,1launcher. Both support and
CSR-only auxiliary modules link. Actual symbol table contains4WQE,4MR-client/
work-reference and6SQ APIs. Default auxiliary probe remains denied BEFORE
private parent-layout access; no ib_device/provider is registered or module
loaded. Native parent/header private ABI remains unverified.

`kernel-queue-unit-002`:10short actual-C cases under ASan+UBSan and pthreads.
Only primitive/umem/coherent allocation/HW/CQ behavior is modeled, not replaced
MR/SQ implementation. Tests check full authorization, publication before fast
exposure,4thread-held MR references during close, stopping getters, no pin/
device/module release without proof; descriptor bytes/barriers/ring reuse,
CQ backpressure, READ-destination/WRITE-source permissions, unsignaled/error
CQ policy, full queue handles/epochs, ambiguous allocate/doorbell/retire and
2threads posting16owned WRs followed by matched retirement. The model aborts
on allocation, sleeping control/mutex operations or frees under a fast lock.

Two uncertainty cases deliberately retain globally reachable pool/MR/ring
ownership. They do NOT manufacture reset/completion/drain just to make cleanup
or a sanitizer pass. Native abort/flush/removal/pin lifetime is unproven and
must be completed, not redefined as permanent quarantine success.

First kernel build001and unit001both passed but are historical after adding
READ_ONCE/WRITE_ONCE lifecycle flag accesses;002binds final source. Older
kernel-aux-build002/native-attach003/WQE-codec001records include old Makefile/
MR sources and are historical. Fresh native-attach004and codec002reruns bind
the current Makefile. Original rollback sources/image are not changed.

Full portable023/session90010passes203methods in216.264s, including these10
cases and all previous C/RTL/generic-PCIe cases. Source-checks021passes7methods.
This is not kernel-runtime, physical signoff or a registered verbs test.

Later `sq_io.c`/`sq_hw.c` adds actual owner-checked bounded atomic SQC1 MMIO
callbacks, compiled into this support module. See `ROCEV2_SQ_KERNEL_MMIO.md`.
Actual kernel-sq-build003is now the27-input/22-symbol running-header compile;
the earlier002Makefile-bound build is historical. Existing queue-unit002still
binds unchanged MR/SQ/WR bodies under its narrower primitive/HW/CQ models.
New kernel-sq-hw-unit002executes actual IO/HW/MR/SQ bodies in13methods/48cases
with explicit readl/writel/MMIO/time models, not actual Linux/native IO.
Fresh native-attach005and codec003replace earlier Makefile-bound checks.

## Standard QP ERR and proved receive flush (checkpoint073)

The actual verbs callback accepts `IB_QP_STATE`/`IB_QPS_ERR`, reports ERR on
query and rejects subsequent posts. Acceptance is a state change, not a
claim that DMA or outstanding work has finished. A sleepable progression
pumps genuine native CQ events, obtains the exact RQC flags63 cancellation
certificate, stops the QP and confirms PD-zero remote-authority revocation,
then emits ordered `IB_WC_WR_FLUSH_ERR` receive WCs. Each WC uses the retained
WR ID, RECV opcode and zero length; it is an error notification derived from
a genuine ownership-revocation certificate, never a fabricated native or
successful completion. Already-completed SEND/RECV WCs remain unchanged.

`as02_sq_prepare_receive_cancel` retains the validated full owner, final
producer and nonce in queue-owned state without publishing a WC or dropping
any MR reference. Only after actual QP STOP does `as02_sq_flush_receive`
release each reference after its WC has been committed. CQ backpressure
retains the remaining references and proof; a retry must not reissue the
already-retired hardware cancellation. Delivery follows WQE sequence across
ring wrap. Ordinary paired SQ/RQ retirement is still required before coherent
rings can be freed. User-file abandonment may discard remaining WCs/work
references only using that same genuine cancellation proof.

Transient busy/timeout/CQ-full progression is retried by delayed work; invalid
proofs retain ownership without a busy retry loop. An explicit repeated ERR
request can retry reconciliation after the real proof becomes available.
QP destruction synchronously cancels the worker before taking the device
control mutex, avoiding a worker/device-lock deadlock or freeing its storage
while work remains scheduled. Linux workqueue/core behavior is modeled in
the source tests, not proved by executing this driver in the running kernel.

Six new actual-source bootstrap cases cover simple ERR, CQ-full ordered
resume, withheld cancellation, full-cookie corruption, file-close during
partial flush and wrapped RQ sequence. Together with the13 preceding cases,
all19 pass. Two exact unedited full-generated-native RQC/WQE/CQ proof bridges
exercise the kernel C flush library; those do not execute the standard verbs
callback against real IB core. Existing15 verbs,5 device,5 CQ cases and the
three READ/WRITE/SEND native-CQ bridges pass. Running-header/pinned-parent
W=1 compilation separately passes; no module/image is installed or loaded.

Outstanding requester SEND/READ/WRITE still require their genuine native
completion/drain evidence; this change supplies no general abort authority.
Legacy hardware without receive cancellation keeps its drain-only behavior.
ERR-to-RESET reuse, arbitrary forced/core cleanup, late ambiguous QP STOP,
parent BAR/epoch lifetime and surprise unplug remain incomplete. Neither
accepted ERR nor a software-empty queue authorizes unpinning or unmapping.

## Remaining real integration

Actual SQ CSR/atomic MMIO, CQ/router, verbs and userspace provider source now
exists, but has not executed with a physical native device or been bound by
default; the SQ adapter requires its caller's real CQ commit callback.
There is still no default successful hardware/CQ backend.
Connect the actual bus/ib_device/QP/CQ lifecycle and coherent rings, shared
physical DMA tag/RAM routing, actual native shared-MR/page/work executor and
wire/CQ completion. Close source-bound ambiguous-post/flush/hot-unplug/reset
recovery; preserve required additional operations and bounded protocol/network
behavior. Then exact new full-board original timing/routing/DRC/conditional
CDC plus short thermally guarded native tests retaining READ/WRITE. No real
FPGA program/module load/network/fan/BIOS/reboot/commit/push action here. Broad
RNIC goal remains active and incomplete; reboot continuity is still unproven
and no reboot is needed for this stage.
