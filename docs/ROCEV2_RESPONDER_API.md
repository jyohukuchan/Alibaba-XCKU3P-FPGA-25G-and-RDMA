# Experimental protected responder backend contract

Source: `rdma/rnic/rtl/rocev2_protected_responder.v`.
This is an offline-verified integration, **not a deployed board API or RDMA
driver ABI**. The existing native version2 initiator image is unchanged.

## Implemented subset

One trusted QP (localQPN0..7, peerQPN24bits), one outstanding operation,
IPv4 without options/fragments, UDP4791/checksum0, PKey0xffff, and
WRITE_ONLY/READ_REQUEST of1..4096bytes. SEND, immediate, Atomic, segmented
WRITE/READ, initiator SQs, multiple pending operations, wire NAK/RNR,
duplicate/retry recovery and congestion handling are not implemented here.

The first complete-frame IPv4/ICRC gate runs before QP/MR admission. Format,
opcode, expected peer/local IP, localQPN, PSN, RETH length and WRITE wire
extent/pad are checked before querying the MR. PD comes only from the trusted
QP configuration, never the packet. Successful MR lookup retains the full
VA64/DMA64/length32/tag16 context before forwarding the unchanged packet to
the HLS transport. The baseline transport's integrity gates remain present.
Rejected requests do not enter HLS, touch backend memory, send a success
reply or advance the expected PSN. Correct next requests recover without
reset. Zero-length requests are rejected; future verbs no-op semantics must
be handled separately. Only one-packet responses are supported in this stage.

## Configuration and ownership

All ports use ready/valid handshakes on `clk`, synchronous active-high`rst`.
Hold each valid and its payload until accepted. QP configuration is accepted
only when quiescent and no MR configuration/response has priority. `qp_ready`
indicates the initial HLS table startup, both QP/connection handshakes and
mandatory MR epoch initialization have completed. No packet is admitted
until all three are ready.

When `EXTERNAL_ADMISSION_CONTROL=1`, `cfg_admission_pause` additionally prevents
the first checked beat of NEW packets from being admitted. It does not stop
an accepted partial packet, active memory/data operation or TX response from
draining. The legacy contiguous probes default this parameter0; the actual
`rocev2_paged_responder` composite hardcodes1 and drives the gate. Full MR/PTE
publication must keep it closed across all commands and their responses.
The new `rocev2_controlled_responder` owns that gate with a transactional
MR/PTE sequencer and exposes only the new identified AXI mailbox, not raw
configuration inputs. See `ROCEV2_CONTROL_ABI.md`; the live board/bus-driver
and real PCIe/MMIO/page-pin paths are still not integrated.

MR registration/invalidation uses the same fields/errors as
`rocev2_mr_table.v`: REGISTER1, INVALIDATE2, SET_EPOCH3;8entries, PD16, key32, VA64,
contiguous DMA64/length64, basic access bits local-write1/remote-write2/
remote-read4/remote-atomic8. Registration returns a new generation key;
invalidate retains the generation, and exhausted generations never wrap.
This does not pin/map user pages or implement scatter/gather/`ibv_reg_mr`.
The protected top requires SET_EPOCH once per reset, with a trusted29-bit
generation floor in `cfg_mr_key`; the response echoes that floor. Registration
and lookup are blocked before it (registration error10). The floor must be
at least every previously issued generation, retained outside the reset FPGA.
Maximum/oversized floors, duplicate seeds and exhausted keys are rejected.
Legacy standalone tables default to epoch-optional; the protected top does
NOT use that default. Management captures fields, computes65-bit ends in a
separate stage and rechecks external quiescence before committing. Hold valid
through the handshake, then wait for the separately backpressurable response.

`quiescent` remains false from the first buffered packet beat through
authorization, memory commands/data/completion and the response's final
output handshake. It is also false while a rejection event or QP configuration
is outstanding. A pending MR management response separately blocks new
management/admission handshakes. Only after ownership drains may an MR be
revoked or QP context changed.
Configuration asserted in the middle of reception must wait, not stop the
partially received packet from draining. Buffered but not yet admitted
packets in the preceding integrity FIFO have no lease: they must pass the
new current context/key checks when later admitted.

## Full-width backend command

| Signal | Meaning |
| --- | --- |
| `m_memory_command_write` |1WRITE,0READ |
| `m_memory_command_address` | Authorized contiguous **DMA64**, NOT raw/truncated RETH VA |
| `m_memory_command_length` | Exact RETH payload extent, excluding wire padding |
| `m_memory_command_tag` | Nonzero transaction tag16; monotonically increases within this reset epoch |
| `m_memory_command_key` | Complete authorized RETH key, captured for this same MR lease |
| `m_memory_command_offset` | MR-relative64-bit offset from the same successful MR lookup |
| `m_memory_command_valid/ready` | Exactly one accepted command per admitted operation |

Every meaningful94-bit HLS memCmd field must match saved context: lowerVA48,
wire length28, final/control1, VA-derived stream/route bits, sync0, host1,
and the10-bit localQPN. The unused AXIS top2bits are ignored. These routing
fields are checked, **never interpreted as host DMA routing**. No address
bits are reconstructed from the truncated HLS output: the previously
authorized context supplies the full translated64-bit backend address.
An opposite-direction, duplicate or mismatched command faults without
releasing the lease. No additional HLS SQ/other memory users may bypass this
single-operation association. Tag0is unused; exhaustion refuses admission
rather than wrapping. The tag is not a persistent post-reset security epoch.

The paged composite uses the explicit key/offset, NOT the legacy contiguous
address output. It forces that unused DMA base0 and allows only the matching
page table to produce physical PCIe DMA64. The complete authorized key/offset/
length/direction/tag connection is observed under backpressure in the actual
HLS composite probe; no truncated-address reconstruction or host-copy path.

## Data and completion

WRITE data uses512-bit little-endian byte lanes,64-bit dense-prefix keep
and last. No data is transferred before its command is accepted. Actual
HLS wire extent/keep/last is checked before each beat; final wire pad bytes
are removed from keep and zeroed in data. Exactly the authorized payload
extent, not HLS's padded length, reaches backend memory.

READ data comes from the backend after command acceptance on the corresponding
512-bit stream. It must have full nonfinal keeps, exact dense-prefix final
keep, exact payload length and correct last. Hold valid/data/keep/last stable
under backpressure. The backend must not return bytes from another lease.

`s_memory_status_{tag,error,valid,ready}` is accepted only after the final data
handshake. A matching tag and error0mean all writes are **visible to later
operations**, or all read accesses are complete with no outstanding DMA.
It is insufficient to acknowledge descriptor enqueue or payload FIFO entry.
Failed or wrong-tag status causes a sticky fault; it must never produce a
successful wire ACK. The backend must retain mappings/pages until the lease
really drains, including error cleanup. In this subset, any read error must
be reported without an incomplete data stream trapping the status interface;
there is no early-error/abort channel yet. Consequently this contract is NOT
ready for a fallible PCIe DMA backend without cooperative error drain. The
new experimental Corundum backend in`ROCEV2_DMA_BACKEND.md` implements zero
drain followed by error status, plus retained descriptor ownership. Actual
PCIe engine integration, driver cleanup and reset recovery remain unverified.

The HLS WRITE ACK may already be buffered before memory placement. Output
valid/ready is held off until successful backend completion. It remains
backpressurable afterward. The memory lease and MR invalidation gate remain
held until the response's **last** beat is accepted. Expected receivePSN
then increments modulo2^24. The next admitted READ therefore sees the earlier
committed WRITE. `tx_deferred_cycles` records exercised deferred-response
cycles; it is not a throughput or native latency benchmark.

## Rejections, faults and reset limitation

Local rejection events carry error8/QPN24/PSN24 and remain stable until
accepted. MR errors1..10retain the MR table definitions. Integration errors
are16format,17QP/peer,18PSN,19unsupported opcode,36tag exhaustion. These
events are not wire NAKs; no interoperable RC recovery claim is made yet.

Sticky backend faults are32command,33data shape,34status and35unexpected
transport output/integrity error. They stop new memory/data/TX admissions
and prevent configuration; they do NOT prove outstanding accesses have
ceased. A driver-level abort/drain/reset procedure remains required.

Reset clears volatile table state and tags: it is **not key revocation or DMA cancel**.
Before any future live integration resets/reopens this endpoint, close QPs,
drain/cancel all actual memory accesses, and establish a fresh key epoch from
a retained host watermark. The new required seed blocks accidental default
reopening, but does not supply persistent storage or prove DMA drain itself.
Host page lifetime, PCIe translation/protection and those recovery paths
remain implementation work, not assumptions satisfied by the offline RAM.
