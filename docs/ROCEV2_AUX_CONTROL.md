# Native CSR-only auxiliary control candidate

This is actual Linux auxiliary-driver source, **not a complete RDMA driver**.
It is compile-tested ONLY: never installed, loaded, bound, or executed against
the FPGA in this stage. No ib_device, uverbs/provider, QP/CQ, DMA mapping or
user-page pin is exposed. The full RNIC goal remains open.

The later067 source milestone adds separate standard-device publication APIs
and a libibverbs provider around the actual MR/queue/verbs implementation.
Those APIs are compile/model-tested but are NOT called by this CSR-only
auxiliary driver. Its default denial and private-parent/runtime gates remain
unchanged. A successful provider build or IB-core boundary model is not an
actual bus registration or permission to enable/load this module.

Milestone068 adds `native_graph.c` and the separately callable
`mqnic_graph.c` adapter to the support library. The normal initialization
path now uses real RNC MR/page and queue adapters before publishing the
standard device. `enable_native_attach` defaults false before any private
mqnic layout access. This is NOT wired into the existing CSR probe/remove:
the parent must first provide an actual BAR/epoch lease and honor successful
normal graph close before unmapping. A bool opt-in, modeled parent, in-memory
watermark or retained device reference is not physical/ABI/hot-unplug proof.
The CSR-only auxiliary driver's behavior below remains unchanged.

Milestone069 adds a real standard-device `ufile_hw_cleanup` callback and
context-bound QP/CQ close preparation. It abandons unread software completion
metadata and user notifications, not native events or memory ownership.
Visible native completions still pass the actual decoder/SAME-WQE checks;
normal core destructors still require real STOP and queue retirement replies.
Completed-but-unpolled shared/distinct CQ close paths are model-tested, but
uncompleted preposted receives, arbitrary forced cleanup and surprise unplug
are not solved. Neither this callback nor its short tests change the default
denial, wire the automatic auxiliary probe, or authorize BAR release/module
loading. See `rdma/rnic/README.md` and progress069 for the current scope.

## Attachment boundary

Optional `AS02_BUILD_AUX=1` builds `as02_rnic_ctrl.ko` alongside the separate
`as02_mr_support.ko`. The controller matches ONLY
`auxiliary:mqnic.app_41534e31` (ASN1), never the old deployed ROC2 application.
Parent PCI identity must be1234:1001/subsystem1ce4:0009, mapped application
BAR exactly16MiB. Full-width values are checked before any native CSR read;
unknown/high bits, other NICs, absent mappings or unreviewed sizes are rejected.

Crucially, `enable_probe` defaults FALSE and is a read-only/load-time parameter.
Default denial occurs BEFORE even dereferencing mqnic's private parent layout.
The auxiliary alias and a successful compile are NOT a parent/header ABI proof.
Loading or enabling this prototype is NOT authorized by the build evidence.
Future runtime work requires the exact loaded parent/header compatibility,
exact new firmware/native identity, functional/physical/CDC and ownership gates.

If later legitimately enabled, probe borrows the parent's already-mapped
application window; it neither claims/remaps PCI BARs nor changes bus mastering.
`as02_rnic_hw_init()` reads the exact0x400000/4KiB controller ID/ABI/features
and fresh paused/empty/drained state under the I/O mutex. It does not seed
an epoch, submit a doorbell, configure QPs, start DMA or reset hardware.
No external file/sysfs/ioctl/data-plane handles exist in this stage.

Remove serializes terminal logical detach before the parent unmaps its BAR,
clears driver data and frees only this unused CSR context. Detach failure or
unexpected pending/uncertain control state retains the context, never invents
DMA drain. The pinned mqnic parent deletes the child before clearing bus
mastering/unmapping BARs. Future QP/MR/userspace integration MUST add real
reference/pool/quarantine lifetimes; this no-external-users stage is not
sufficient for those cases. See `ROCEV2_CONTROL_ABI.md` for detach semantics.

## Evidence and remaining gates

`native_attach.c` is the actual shared-C full-width identity/geometry validator
used by the kernel probe. Five portable C/UBSan/static scope tests pass
(native-attach-unit004 after the SQ Makefile change): exact identity/ABI size, old/wrong/high identity
bits, absent/unreviewed BAR mapping, NULL and no fake verbs/writes. Parent
metadata and the static probe audit are MODELS, not executed kernel callbacks.

The source-frozen candidate `aux-control-frozen-4WRXAxG7` contains14own source/
header/Makefile inputs and2pinned parent headers, hashed before compilation.
Both modules compiled/linked withW=1/gcc13/running6.17.0-1033-oem headers. This
aux-build001snapshot is now HISTORICAL after adding WQE objects to the Makefile.
At that stage `kernel-aux-build-002` froze17own files+2parent headers+1launcher
BEFORE actual compilation and links the real C/Linux WR conversion APIs;
see `ROCEV2_WQE_ADMISSION.md`. No kernel WR callback executes or verbs appear.
BTF is
skipped because vmlinux is unavailable; no module is loaded. The parent
header dependency is pinned Corundum1ca0151b97af85aa5dd306d74b6bcec65904d2ce.

Later MR work-reference/SQ changes make aux-build002historical too. Current
`kernel-sq-build-002` freezes19own files+2headers+1launcher and links14WQE/
MR-ref/SQ APIs in the support module; CSR-only auxiliary behavior is unchanged.
See `ROCEV2_KERNEL_QUEUE.md` for actual-source model tests versus the explicitly
unexecuted native allocator/MMIO/CQ/driver/provider path. No module is loaded.

Read-only runtime inspection found mqnic loaded with srcversion
`2B7846A14E770BA5B472258`, but `modinfo mqnic` could not locate an installed
module file, and a narrow search in the task repository/research directories
did not locate its binary. Therefore matching the currently loaded parent's
private layout to these headers is UNPROVEN. The default probe remains denied;
do not infer safety from the version string or alias. This does not prevent
offline protocol/kernel/board development, and is not a reason to reboot.

The [Linux RDMA core API](https://docs.kernel.org/driver-api/infiniband.html)
has its own device registration/lifetime requirements, distinct from this
CSR-only module; no empty/stub RDMA device is registered as a substitute.

Actual registered host pages, native DMA/ownership, standard kernel RDMA
registration/provider/WQ/CQ/verbs/per-WR keys, SEND/RECV/immediate/Atomic and
wire recovery/congestion requirements remain open. The deployed/legacy path
still uses a QP-table key. A separate per-WR transport now preserves exact
remote keys through actual RTL wire/NAK tests, but this CSR-only attachment
does not submit those requests through native host WQ/CQ/verbs. The new local
WQE admission frontend is likewise not yet connected to the native queue/DMA
executor; neither success is supplied by merely attaching this control module.
