# Kernel SQ-to-SQC1 MMIO adapter (not a registered RDMA driver)

`kernel/sq_io.c/.h` implements the actual shared-C SQC1 register transaction
protocol. `kernel/sq_hw.c/.h` connects the existing real coherent-SQ/MR-reference
library callbacks to actual Linux readl/writel, IRQ spinlocks, monotonic time
and cpu_relax. This is production-path source, not a built-in successful model
backend. It is compiled into the support module, but NOT loaded, probed or
executed in Linux. The actual native parent still does not map SQC1, and no
ib_device/provider/standard verbs or real completion queue is registered.

## Protocol and atomic context

Use a zero-initialized caller-owned `as02_sq_hw` object, a stable kernel-owned
4KiB SQC1 BAR region and a REQUIRED actual CQ commit callback. There is no
default/no-op CQ publisher. Native firmware/parent-private-ABI/persistent epoch/
reset/lifetime gates must already be satisfied; ID/ABI alone does not establish
those facts. Init reads ID/ABI/feature1/clean available state/sequence0and
performs no writes. It refuses adopting another driver's queued/old sequence.
Logical detach is terminal and never reinitializes the same object.

Queue create/retire callbacks and atomic producer publication use the same
IRQ-spinlocked transport. Lock order is queue-fast -> SQC-fast -> CQ. A CQ
event handler must not hold its CQ lock before `as02_sq_complete`, nor reenter
SQC from its CQ publisher. No sleeping, allocation, umem release or CPU user
payload copy occurs inside the MMIO adapter. The caller retains the real
BAR/device/module/context lifetime until all owned operations are safely gone.

Each command validates full QPN/PD/epoch64/cookie64/DMA64/ring/producer64/nonce64,
writes all15metadata words, reads them back, then rings the exact next sequence.
Pre-doorbell staging failure does NOT consume a sequence: strict FPGA next-
sequence checking remains usable on retry. Only before the possibly posted
doorbell does software publish its complete expected owner and mark pending/
uncertain. Every timeout or ambiguous response preserves that state.

The reply parser checks every one of the15snapshot words, known semantic error,
exact allocation/retire proof flags and full consumer64. Error flags must0.
Allocate consumer must0, publish consumer cannot exceed producer, retire consumer
must equal final producer. It rechecks live reply/sequence before exact ACK and
checks idle/sequence afterward. Hardware error128/unknown/reserved flags or
foreign context never become a success proof. A known semantic rejection may
be ACKed/resynchronize transport, but remains a failed hardware operation.
BRESP alone is not success; SQC1 sticky status and exact owned reply govern it.

Busy waits use BOTH a monotonic deadline (1..1000us configuration) and at most
256polls per response/ACK phase; even a stopped clock cannot spin forever.
The same deadline spans both phases. These are software loop bounds, not a
claim about measured native IRQ latency or platform MMIO-access completion.
The final0xffffffffsequence may be exactly ACKed in exhausted state, but no
next command wraps. Continued safe sequence/tag epoch recovery is unfinished.

## Real queue-library connection and lifetime

`as02_sqc_sq_hw_ops` supplies actual allocate/publish/retire/CQ callbacks for
`as02_sq_pool_init`. Allocate and retire proofs are built from the validated
hardware reply, not the original requested layout copied as fake confirmation.
The pool's real coherent descriptor write and dma_wmb precede actual posted
MMIO. No user payload is copied by CPU. Full WR/MR ownership stays in the
existing shadow queue until actual memory+transport proof AND actual CQ commit.

On producer error the existing SQ code quarantines the possibly exposed WR,
ring and MR ref without rollback. `as02_sq_hw_reconcile` can match an exact
late reply and resynchronize ONLY the transport: it does not unquarantine the
queue, retire a WR, publish a CQE, cancel hardware or unpin pages. The pending-
WR abort/flush/CQ teardown path remains required. Logical detach clears the
adapter's BAR pointer under its spinlock and forbids subsequent IO; it does
not authorize freeing retained contexts/pages or solve native hot unplug.

## Evidence, explicit models and still-open work

Actual frozen kernel-sq-build003/session69064compiles/links27inputs (24own,
2pinned parent headers,1launcher), W=1/GCC13/running6.17headers, both support/
CSR-only auxiliary modules and22WQE/MR/SQ/IO/HW symbols. No install/load,
probe/MMIO/pins/DMA/CQ callback executes. Default auxiliary probe remains off
and the loaded parent's exact private ABI remains unverified. Build002is
historical after the Makefile/source-graph change.

Kernel-sq-hw-unit003passes13methods/48short cases under ASan/UBSan, executing
the same actual MR/SQ/WR/IO/HW C bodies with EXPLICIT userspace Linux primitive,
readl/writel/MMIO/clock/CQ/coherent allocation/umem/hardware-proof models. It
checks all15wrong reply-word positions, full range/identity/shape/refusal,
pre-bell failure/sequence retry, known failure/proof retry, CQ-full ownership,
post/ACK timeout, stopped-clock bound, late transport-only reconcile, terminal
detach, final sequence and two threads posting16owned WRs before CQ retirement.
Negative in-flight cases intentionally retain real-C model objects/MR refs and
never fake successful cleanup for leak tooling. These are NOT actual Linux
primitives/native BAR access, actual RTL co-simulation, PCIe data or real pins.
First unit001never executed: its fixture failed strict compilation (explicit
low32-bit constant cast and misleading indentation); its log is retained.

Fresh native-attach006and codec003refresh current Makefile-bound unit identity,
not native runtime. Shared actual RTL control/generic-PCIe tests remain separate
source-bound evidence in `ROCEV2_SQ_CONTROL.md`, not relabeled as C-to-RTL/native
driver tests. No new RTL was edited during this kernel-MMIO stage.

Progress027adds source-only native SQC1@0x402000decode and real SQ-fetch-to-
shared-MR authorization; see `ROCEV2_SQ_CONTROL.md`. Fresh kernel-sq-build004
freezes27inputs and links22symbols against the running headers, retaining
default-disabled probing. Unit003refreshes the header's honest source-only
mapping comment; C callback bodies are unchanged. Neither compile nor these
explicit models execute real MMIO/pins/DMA or publish an actual CQE.

Actual mqnic app/board SQC1 firmware selection, real kernel/ib_device/QP/CQ/provider
lifecycle, true incoming/local shared MR/PTE/WQE execution, actual wire/fence/
completion ownership and safe failure recovery are still required. Likewise
SEND/RECV/immediate/Atomic/wider operations/reliability/congestion and resulting
full physical/conditional CDC/short thermal-native gates are not completed.
No reboot is needed; exact authenticated Codex restoration remains unproven,
so no reboot or unrelated hardware/network/fan/BIOS/commit/push change occurs.
