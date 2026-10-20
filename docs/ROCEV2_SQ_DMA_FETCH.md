# DMA-backed coherent send-queue descriptor fetch

Synthesizable SQ fetch and actual Corundum descriptor/RAM/AXIS integration,
NOT native coherent allocation, queue CSR/doorbells, verbs, page execution,
CQ publication or FPGA deployment. It does not yet feed the separately tested
shared-MR frontend through actual paged/controlled/native endpoint layers.
Fetching a descriptor is NEVER an RDMA completion. Full RNIC scope stays open.

## Trusted rings and lifetime

`rocev2_sq_fetch.v` supports8trusted internal QPs, each with a kernel-owned
coherent DMA64 ring of2..256power-of-two64-byte entries. Only the future trusted
kernel controller may supply its DMA base, PD, nonzero64-bit epoch and full
24-bit internal QP. Do NOT expose arbitrary user physical addresses here.
Actual coherent allocation and device/module/QP references remain unfinished.

Serialized commands allocate, publish producer, or retire/cancel an unfetched
tail. Full QP bounds,64-byte base alignment and65-bit ring-end checks prevent
alias/wrap; a ring ending exactly at2^64is valid. Allocation/retirement require
real parent drain and no selected/downstream owner. Active allocation and
non-increasing epochs refuse. Retirement keeps the epoch watermark. Reset is
not safe revocation: persistent fresh host epochs and actual lifetime recovery
are still required. Cancellation generates no flush CQEs or driver-ref release.

Producer/consumer are full64-bit monotonic counts. Ring slots wrap, trusted
sequence does not: it is consumer+1. Producer cannot retreat or overrun ring
credits. Round-robin selects pending non-halted queues. Tag16refuses wrap;
exhaustion/global reset recovery remains an external lifetime requirement.
The driver must store the whole WQE and perform the appropriate coherent-DMA
write barrier BEFORE publishing producer/MMIO. Coherence alone is not ordering.
The test MODEL explicitly loads descriptors before publication, not native CPU
or PCIe ordering proof.

Selection captures full DMA64 address/QP/PD/epoch/sequence/tag. Commands and
results survive stalls/disable. Exactly64bytes/all keep/last AND matching DMA
status are required, in either order, before result. Malformed/duplicate/
unsolicited data/status, wrong tags or unknown wide errors cause sticky faults
without invented completion/drain. Known4-bit DMA errors zero the record and
halt its queue; error records go to recovery, NEVER normal WQE authorization.

Consumer advances on record handoff, NOT RDMA completion. The caller must
atomically retain actual MR/QP/queue/WR ownership on EVERY handoff, including
errors. `queue_guard` covers selection/offered DMA/read/held result/uncertainty;
actual downstream guards and parent drain protect reconfiguration. Unknown
ownership and mappings cannot be released merely by local reset or a reply.

## Actual backend and READ error option

`rocev2_sq_dma_fetch.v` connects the fetcher to the real existing
`rocev2_corundum_dma_backend`, `dma_psdpram` and `dma_client_axis_source` path,
not CPU payload copy. Existing minimum8192-byte RAM/native15-bit address
geometry is retained without guard relaxation. SQ use never writes host memory
or issues a WRITE fence.

The backend's new static `RECOVER_READ_DMA_ERROR` defaults0, preserving old
protected-payload fail-stop behavior. ONLY the SQ wrapper sets1. After a known
matching terminal READ error it drains zero bytes, reports the ORIGINAL DMA
status (UR10, not relabeled as local code6), then waits in `READ_DRAIN` for
real parent AND local DMA/RAM drain before accepting another command. WRITE/
fence errors, bad tags, malformed RAM/streams and sticky uncertainty NEVER
take this option. Native parent fault recovery is separate; this is no license
to ignore its sticky errors. Parent drain must be independent real descriptor/
TLP/RAM evidence, not derived from this wrapper's busy/idle. Wrapper metadata
also requires backend idle/drain. A backend protocol fault guards all queues.

## Bounded source-bound evidence

`sq-fetch-unit-003`:7actual four-state controller methods, explicit backend/
drain MODEL. Tests full-QP/PD/DMA64/epoch,2QP fairness/ring reuse/top64-bit end,
configuration/producer credits, stalls/disable/downstream/parent guards,
queue-local errors/stale-fresh epoch, malformed/tag/unknown/unsolicited faults
and tag exhaustion. Not actual PCIe evidence.

`sq-pcie-005`/`sq-pcie-error-005`: actual C/UBSan descriptors through actual
generic `dma_if_pcie`,2native-shape muxes/RAM demuxes, backend RAM/AXIS and SQ
controller. Leaf/interface/engine tags16/18/19, RAM routing12, DMA64/RAM15/
2x256-bit RAM/256-bit TLP. Only trusted config/host memory/root complex/hard-IP/
link are MODELS. No descriptor/status/RAM substitute agent or internal forcing.

Normal:6records/6actual64-byte reads, full bytes,2QP/ring reuse/disable during
TLP stall/parent retirement guard. UR: actual Unsupported Request completion
parsed by generic RTL,1zero64-byte record/error10, independent queue progress,
canceled unread tail, stale epoch refused and fresh-epoch refetch;4reads/results,
3successful records. Parent proof is additionally withheld40cycles and this
qualifier can NEVER make false-positive drain. Staging remains unavailable.
Both final probes take under1second here, retain generated fixtures/C bytes/
compiler warnings/raw logs, and hash consumed sources before/after. They do NOT
prove native whole-parent fault/reset/MR-ref/CQ recovery. Two actual-PCIe cases
also run in the portable `make check` target.

Current full portable022passes193methods in213.561s, including old default
protected/backend regressions and9new SQ methods. Source-checks020passes7;
actual full patched parent/core/app compile005passes with new SQ sources
uninstantiated and default old behavior, not native SQ traffic.
The earlier021batch also passed193methods before the fresh-CI launcher edit;
022is the complete rerun against the final005launcher source.

Preserved failures: unit001fixture port-count typo; unit002historical after
final source changes. PCIe001rejected unsupported256-byte staging;8192minimum
is retained. Error002exposed actual UR10 and default fail-stop policy; final
SQ-only parent-drained recovery explicitly replaces that assumption. Earlier
normal002/normal003/error003passes predate final40-cycle proof observations.
No failed evidence is overwritten or relabeled as passing. Final005only adds
creation of the ignored output directory for fresh CI checkouts;004is historical
after this launcher change, not a current launcher hash match.

## Still required

Subsequent source work supplies the full-tag common router/real RAM-bank
ownership (`ROCEV2_SHARED_DMA.md`), actual SQC1 CSR/kernel callback source,
and NEW source/offline native-SQ mapping/real-fetch-to-SAME-MR authorization
(`ROCEV2_SQ_CONTROL.md`). The coherent SQ backend is separate from the ONE
existing paged payload backend; both use unchanged complete16-bit logical
tags, translated into unique physical16-bit tags before original18/19-bit
muxes. Native real mqnic app/board selection is still missing, not inferred
from source-level wrapper simulation. Never directly alias the independent
tag spaces, truncate a tag bit or fake completion/drain.

Progress027adds a full per-QP queue_pending output, distinct from busy/fetch
and actual MR/work leases. Unit004checks posted-but-unfetched ownership and
preserves all7methods/10simulations. Fresh normal/error PCIe006recheck all
original byte/status/proof assertions in801/684cycles. The retained005records
are historical after this real source/interface change. Full portable033
passes257methods in331.997seconds after the two old fixture port inventories
were updated explicitly; failed032and interface-recheck001logs remain saved.

Real coherent allocation/barriers/queue CSR and non-sleeping MR/QP/WR ownership;
real driver/parent binding of shared-MR native wiring, sealed-page local DMA/staging and wire/memory/fence/
MAC/CQ completion; standard kernel/user verbs/provider; remaining operations
and bounded recovery/network behavior; exact new full-board original physical/
CDC gates and short thermally guarded native tests retaining old READ/WRITE.
Do not duplicate MR namespaces, truncate IOVAs or call consumer a completion.
Frozen META CAD predates BOTH shared-responder and backend-option edits, so
does not qualify this newer desired source. No hardware/network/fan/BIOS/
reboot/module-load/commit/push action occurs in this stage.
