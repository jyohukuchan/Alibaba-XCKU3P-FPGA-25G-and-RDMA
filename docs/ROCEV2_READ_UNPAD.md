# Checked READ wire-padding normalization

Progress033update: corrected peer-fixture READ replay003is now terminal0in
12.086seconds on the exact unchanged compiled design: actual HLS68bytes ->
production adapter65bytes -> real paged PCIe/two posted WRITEs/fence; all
host/ring sentinels and request/header/byte/guard checks pass. The only driver
change is packet payload generation to match the existing native179/d3oracle;
old002failure is preserved. Exact before/after sources/bench/binary/non-peer
fixtures are checked, not assertions rewritten or a failure promoted. Still
additional TWO-STATE/offline host/peer/CQ MODELS, not hardware/runtime. New
issued/lifetime logic is a separate integration scope; see
`ROCEV2_WQE_LIFETIME.md`.

Progress032adds production `rocev2_wqe_read_unpad` and a new coupled actual-HLS
READ probe. The latest completed source regression038passes309methods; the
new adapter separately passes5methods/39four-state simulations. This is NOT
a claim that a single314-method batch ran or that actual native RDMA is done.
The new coupled READ build002is live at checkpoint032; no READ-HLS pass yet.

## Why an adapter is required

The exact unchanged generated FNS READ implementation includes up to3wire pad
bytes in BOTH its memory command length and data. The original verified READ
buffer already handles this distinction; see `rdma/read/rtl/rocev2_read_buffer.v`
and `rdma/read/tests/probe_read_transport.py`. A65-byte response produces a68-
byte HLS command/data stream, not65. The new full-WQE memory executor correctly
expects65actual authorized payload bytes. Directly connecting the two is an
ABI mismatch, and forwarding all68would overwrite bytes outside the WQE.

This adapter is actual synthesizable RTL between the raw HLS READ destination
stream and the existing full-WQE executor. It does not edit generated HLS,
repair packets or weaken any original transport assertion.

## Validation, not permission by truncation

The full588-bit ORIGINAL protected READ token is captured, not reconstructed
from shortened HLS addresses. Knownness, READ-only/authorization/error shape,
full QPN bounds before narrowing, flags, epoch/sequence/tag and65-bit local/
offset/remote exclusive interval ends are checked. An actual executor owner
must already hold the per-QP guard. Key/PD/VA remain saved original authority;
there is no duplicate MR table or physical DMA address supplied here.

All96raw HLS command bits must equal the saved-WQE-derived expected PADDED
ABI: complete QPN/routing/stream/host/sync/control/address, padded length and
zero high padding. Any mismatch faults BEFORE offering a normalized command.
Only after that exact check does the adapter emit the same command with the
original payload length. The actual executor then independently checks this
normalized command against its OWN complete retained WQE, and the backend still
uses ONLY that executor's saved full key/relative offset/length/tag.

Raw data must have the exact PADDED keep/last and known meaningful bytes.
Registered output keeps ONLY the original payload prefix, zeroing every tail
byte; discarded wire padding is counted, never forwarded as DMA data. Command/
data offers remain stable through stalls, disable and faults. Missing/lost
guards and malformed/duplicate commands/data fault with retained all-QP guards.
Final output acceptance ends only this staging lease, not memory visibility,
ACK/MAC/WR/CQ completion, permission to unpin or completed recovery.

The protected response token MUST be captured atomically by both adapter and
actual executor BEFORE replay reaches HLS. The new probe uses a guarded two-
consumer fanout: neither consumer can accept unless BOTH are ready, and the
response guard advances only on that same acceptance. Adapter guards join the
native wire guard, continuous through its last output and later memory/fence/
response event -> already-held downstream CQ MODEL ownership.

## Verification and remaining scope

`read-unpad-unit002` passes5methods/39simulations in0.973seconds. Lengths1/2/3/
4/63/64/65/4095/4096exercise all pad amounts and beat/PMTU boundaries. Nonzero
wire pad is deliberately discarded, never stored. Every raw ABI field/high
padding bit, invalid/unknown/non-READ/overflow context, malformed keep/last/
unknown bytes and lost guards across already-offered command/data are checked.
Token, HLS and downstream executor are explicit MODELS in this leaf, not native
DMA, integrity or CQ proof. Unit001failed an incorrect port-count preflight
before elaboration; that failed record remains intact.

The new `probe_native_read_hls.py` is a finite coupled integration of actual:

    C WQE -> coherent SQ -> SAME MR -> owner/SQ -> unchanged HLS READ request
    -> protected RX/token -> same HLS data extraction -> checked unpad
    -> full-WQE executor -> shared PTE/RAM/router/PCIe -> posted-write fence

The peer/physical host/link, trusted connection/issued-wire controller and CQ
are STILL MODELS. The test observes the actual emitted request BEFORE any
response and obtains expected PSN from those emitted bytes, checking it against
the initialized independent request oracle. This is not an implemented native
issued-PSN/QP/wire controller. One valid-ICRC wrong-QP response must have no
memory side effect, then a real protected65-byte response must be extracted by
ACTUAL HLS, not a modeled data/command agent. All68raw/65normalized bytes and
3discarded pad bytes, command routing, request key0/VA64/QPN/PSN/IPv4/ICRC,
full host/ring sentinels, actual posted writes/fence, STOP/early retire and
held early HLS ACK vs memory event/CQ MODEL are checked without fabricating a
CQ completion. As of checkpoint032this build is LIVE, not proven passed.

READ-HLS001was stopped during its OWN isolated compiler group, before simulation,
after an independent ABI oracle exposed wrong guessed routing literals in the
NEW TEST's expected command. The failed report/inputs/logs remain. Only that
owned group was stopped; no hardware or unrelated process was affected.
Expected commands now come from explicit independent ABI offsets. The corrected
002is a fresh build, not a timeout restart, cached/edited binary, waived field,
rewritten HLS command or promoted failure.

The runner bounds compilation600s and simulation30s. Additional compiled
TWO-STATE execution is not a substitute for X/Z/reset/four-state or resulting
physical signoff. Current full38passes309/849.164seconds including response-
guard004(11methods/34simulations) and native-response003. No sustained load,
many-connections or hardware qualification is performed by these finite cases.

Next required work remains real native issued-context/shared transport/MAC/CQ/
registered-page lifetime, broader operations and replay/retry/NAK/RNR/abort/
recovery, kernel/userspace provider/runtime, all full-board ORIGINAL-clock
setup/hold/pulse/skew/routing/DRC/check_timing/conditionalCDC and short supervised
hardware gates. Prototype one-WR/nonzero<=4096B does NOT reduce the full goal.
No programming/JTAG/driver install/load/probe/traffic/fan/BIOS/network/reset/
reboot/commit/push. Exact Codex thread/goal restoration remains unproven; no
reboot is needed now.
