# Combined experimental READ/WRITE API (version2)

Implemented and verified in RTL and on the SRAM-loaded combined READ/WRITE001
FPGA image. See [native results and tested ranges](ROCEV2_READ_RESULTS.md).
The preserved WRITE003 image exposes version1 and does not implement this window.
All offsets below are relative to application BAR2. No host DMA is exposed.

## Identification and ownership

Read0x00=`0x524f4332` and0x04=`0x00020000` before any write. Version1 clients
must reject version2. Use the same exclusive device lock as the WRITE client;
do not run separate old WRITE and new READ controllers against this BAR.

The original18configuration words at0x40..0x84 and command0x08 remain.
Commands are START=1, CLEAR=2, ABORT=4. Configuration/mode/window writes are
allowed only while both controllers are IDLE. CLEAR is required after DONE
or ERROR before changing operation. START snapshots the context, resets
transaction counters (not RAM contents), and increments the run generation.

## Added registers

| Offset | Access | Meaning |
| --- | --- | --- |
|0x100|RW, IDLE only|Operation:0WRITE,1READ; other values rejected|
|0x104|RW, IDLE only|READ outstanding-resource window, default1, maximum32|
|0x108|RO|Capture capacity:262144bytes|
|0x10c|RO|Capture window base:0x10000|
|0x110|RO|READ operations fully committed to RAM|
|0x114|RO|Application payload bytes actually committed|
|0x118|RO|Discarded wire padding bytes|
|0x11c|RO|Validated response memory commands / PMTU chunks|
|0x120|RO|Bit8:SQ/descriptor synchronization fault; bits7:0:buffer error|
|0x124|RO|Authorized READ SQ descriptors|
|0x128|RO|Allocated local capture extent, including slot alignment|
|0x12c|RO|Bit0:buffer fault; bit1:capture idle; bit2:RAM host port idle|
|0x130|RO|Monotonic run generation; no wrap permitted|
|0x10000..0x4ffff|RW, quiescent only|256KiB capture RAM,32-bit aligned accesses|

Status0x0c retains the old flags and state encoding; bit7 now indicates READ
mode. The old0x2c/0x30/0x34 counters still describe the WRITE pattern source,
not READ capture. Capture counters are separate and survive transport reset.
Buffer errors:1descriptor,2memory command,3keep/TLAST framing. Controller
errors retain1configuration,2watchdog,3completion metadata,4memory,5abort.
Rejected-control reason5means generation exhaustion, requiring global reset;
it must not silently wrap and make an ancient queued response current again.

## READ memory layout and completion

READ size is1..65536bytes, count1..4096. Local stride is
`(size+63)&~63`; `stride*count` must fit256KiB. Operation`i` reads peer
`remote_base+i*size` into capture offset`i*stride`. These are local RAM
offsets, never host physical addresses. The peer MR covers the contiguous
`size*count` range and must explicitly grant REMOTE_READ. The read window
must not exceed the peer QP's negotiated responder resources; start with1.

Prefill every expected payload byte with its complement before START, with
independent sentinels in slot padding. Once active, RAM reads and writes
receive SLVERR. Outstanding BAR RAM transactions cannot be canceled or
stolen by START, including a simultaneous AR/START race. After DONE or ERROR,
the host can read actual RAM; CLEAR does not erase its contents.

At4096-byte PMTU a READ reserves`ceil(size/4096)` response PSNs. Response
memory commands must match the next authorized descriptor, QP, chunk address,
padded wire length and flags. Up to3wire pad bytes are consumed but never
stored. DONE requires all transport completions, all application bytes
committed, an idle capture pipeline and the original physical-TX drain gate.
An HLS completion alone is insufficient.

Only configured peer/QP ACKs and READ responses in READ mode are admitted.
Inbound WRITE, SEND and READ requests remain rejected. Queued old-generation
RoCE frames are discarded, while ordinary host traffic remains unchanged.
An already-presented old frame is drained during the endpoint's fixed4096
initialization cycles; its maximum9214-byte frame is shorter than that drain
interval. This does not grant public inbound access to RAM.
