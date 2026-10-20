# Native MAC receipts and whole-WR ownership

Progress035adds a separate live ONE-shared-HLS/SAME-MR path using this real
MAC/lifetime binding; incoming WRITE then local READ/actual extraction/unpad
pass with simulated memory/peer/MAC pins, retaining all owners because actual
core-drain/memory/CQ success is unproven. It does not upgrade the native PCIe
trace proof below into an actual shared-HLS/PCIe/CQ proof. See
`ROCEV2_SHARED_HLS.md`.

Progress034adds production `rocev2_wqe_mac_tx` and
`rocev2_wqe_tx_lifetime`. These close the previously modeled tag-to-owner
MAC proof inside the native offline composition. They do NOT select a new
board profile, implement a kernel CQ/provider, or prove a live shared-HLS /
physical-MAC / actual-CQ end-to-end path.

## Actual role separation and tag mapping

The mapper accepts the complete588-bit authorized READ/WRITE owner before
its dedicated post-integrity IP frame. Full identity, authorization shape,
QPN bounds, nonwrapping intervals and captured Ethernet addresses are checked.
The separate lifetime observer still checks actual emitted IP/RETH metadata
and derives response PSN from OWN accepted TX. The IP stream is not arbitrary
host traffic, and the MAC mapper is not a second MR namespace or ICRC engine.

The actual Ethernet framer and frame-locked arbiter merge this local WR with
the existing native host/legacy/protected-responder Ethernet output:

| MAC completion tag | Owner and return path |
| --- | --- |
| MSB1 | Ordinary Corundum host, tag/timestamp/backpressure unchanged |
| `0x0000` | Existing legacy READ/WRITE initiator, unchanged |
| `0x4000` | Existing protected responder, unchanged |
| `0x2001..0x3fff` | New local WR, exact issued tag -> retained full owner |

No caller can supply a full-context "MAC completed" substitute to the binding.
A genuine external completion tag must match a local frame actually accepted
by the downstream MAC path. Unknown, future, stale, duplicate, unissued or
malformed receipts quarantine all QPs; they are not forwarded into legacy
tag0 accounting. A local fault does not stop valid ordinary Ethernet frames
or steal native host completions.

Tags are NOT reused. Default capacity is8191allocated local frames per whole
parent/NIC reset; exhaustion closes new local admission rather than wrapping
and aliasing an old receipt. The last admitted WR can finish and native host
traffic continues. This is a conservative prototype limitation, NOT a reduction
of the full RoCE goal. Safe bounded-tag reuse/epoch retirement/recovery still
needs implementation; no automatic reset or old-completion cancellation is
provided or authorized by these modules.

## SFD is not wire EOF, and a MAC proof is not a CQ

The mapper requires actual final MAC-beat acceptance, a matching SFD receipt,
framer idle and a conservative1024-cycle tail restarted after BOTH the final
beat and receipt. Its reviewed contract is250MHz core, MAC>=25Gb/s and IP
frames<=4156bytes, with REAL hardware completions. The minimum tail is checked
at elaboration. This local drain does not assert that the HLS core, all parent
queues, unrelated host traffic or the entire NIC is drained.

Pinned Corundum `mqnic_port_tx.v` has a `TX_CPL_ENABLE=0` fallback that fabricates
a completion from accepted output EOF. That mode is NOT SFD evidence. The new
`REAL_MAC_COMPLETION_ENABLE` parameter must be1and the eventual actual parent
profile must independently prove its matching real-completion configuration;
this parameter default alone does not prove deployed parent wiring. The
existing parent has real frame-FIFO logic, but the new resulting board graph,
MAC timing/status/underflow and reset assumptions still need qualification.

`rocev2_wqe_tx_lifetime` atomically captures the SAME original WR into both
owners. It internally connects real MAC tag/owner proof and local drain to
the existing full-context memory/response/HLS-ACK/two-drain proof join. The
remaining HLS transport drain MUST be actual same-core accounting, not1.
Prepared CQ tickets remain stable under stalls/faults and their acceptance
does not release MR/QP ownership. Only the subsequent exact CQ commit can
release it. Same-edge MAC duplicates or parent faults block even an otherwise
exact commit; the full guard is retained. Actual CQ publication must honor
the binding's fault output; a prepared ticket is not permission to publish a
success after a fault, and there is no default-success publisher callback.

## Short, scope-matched evidence

`wqe-mac-tx-unit001` passes8methods/33four-state simulations. It independently
checks Ethernet bytes, real arbiter roles and output stability under stalls;
READ/WRITE, early/late SFD, EOF/tail ordering, full-context snapshots, native
completion backpressure, invalid/stale/duplicate/unknown receipts, owner/range
errors, malformed IP, no tag reuse and reduced-width exhaustion are covered.
Physical MAC pins are explicit models, not real hardware.

`tx-lifetime-unit001` passes5methods/20four-state simulations. Real MAC proof
joins memory/RX/ACK in different orders; memory/ACK/HLS drain cannot replace
MAC receipt. Invalid atomic broadcasts never half-capture an owner. Offered
CQ tickets survive faults; duplicate MAC or parent1/X/Z on the exact commit
edge cannot release the WR. Other proofs and final CQ publisher are models.

`native-mac-lifetime-unit001` passes1method in31.482seconds, using the actual
C/UBSan coherent SQ/SAME MR,
protected RX/token, executor/PTE/RAM/router/generic-PCIe/two posted writes/
visibility fence and the new real MAC/lifetime composition. Actual native
Ethernet egress/completions are interposed, NOT tied off. One host Ethernet
frame runs concurrently, its complete bytes and returned native tag/timestamp
are checked independently. The local frame is independently checked against
the retained actual-HLS READ request plus captured Ethernet header, tag2001.
Memory/fence, MAC proof, HLS drain, ticket acceptance and final commit remain
separate gates; native STOP/early-retire/host/ring sentinels stay checked.

This native case replays retained actual-HLS TX bytes and still MODELS HLS
extraction/ACK/HLS-only drain, physical MAC/host/link and the actual CQ publisher.
It is NOT the separate live-HLS READ extraction proof, nor a new three-HLS
board graph or capacity claim. Offline receipt correlation is now real RTL;
physical MAC completion, OS pins and standard verbs remain unexecuted.

Verilator lint of this production binding has0errors and0UNOPTFLAT loop
warnings. It retains30warnings:26in unchanged external framer/arbiter sources
and4width warnings in the unchanged lifetime observer. No warning suppression
was added to source. Lint with warnings is not physical/timing/CDC signoff.
These are separate short batches, not a newly run full regression suite.

## Remaining full goal and protected boundaries

Next bind actual SAME shared native HLS TX/RX/issued protection, real per-WR
HLS drain, native driver/CQ ring/IRQ/publisher/commit and pinned-page lifetime.
Do not infer that integration from this trace-backed proof. Denied/failed-fetch
error owners, signaled/unsignaled CQ semantics, broader operations, bounded
concurrency, retry/NAK/RNR/loss/congestion/compatibility and safe recovery remain.
This positive one-frame/nonzero<=4096B READ/WRITE prototype is not the full RNIC.

All exact resulting FULL-board original-clock setup/hold/pulse/skew/routing/
DRC/check_timing and conditional CDC gates remain required. Historical failed
gates remain FAILED. No hardware programming/JTAG/driver install-load-probe/
real traffic/fan/BIOS/network/reset/reboot/commit/push was performed. BIOS
Medium and management networking are preserved. Exact authenticated Codex
thread/active-goal reboot restoration remains unproven; no reboot is needed.
