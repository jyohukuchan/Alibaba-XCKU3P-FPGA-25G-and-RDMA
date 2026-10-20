# Ordered readback of actual transport-timer state

Progress036 implements an isolated opt-in derivative of the frozen FNS timer
consumer. It is one constituent of a future genuine core fence, NOT that
fence, a CQE, or permission to release a QP/WR/MR. The one-core shared role
still keeps `local_core_drained=0` and retains its owners. This component has
not been selected in that core or any native/full-board image.

## Implementation and ordering

`rdma/rnic/hls/timer_state_fence_profile.py` derives the original licensed
`transport_timer.hpp` without editing it. The original stop/restart, TX
backoff tiers, retry limit, scan and timeout algorithm remain byte-identical
inside the derivative. Eight resettable register entries and actual table
RAW dependencies are preserved. The real250MHz/eight-entry1ms interval uses
31250 visits, not the shortened nonsynthesis timer. No capacity/clock cut,
false dependency, arbitrary quiet-time success or timer cancellation is used.

A typed marker follows ordinary RX stop updates in the SAME FIFO. While it
is pending, the consumer cannot consume RX updates behind it. Pending real
TX starts are applied before state sampling; a late start invalidates the
old registered snapshot and forces a resample. Such a start yields BUSY,
not false inactive success. The actual table supplies active/time/retry
data. Sampling, classification and emission occupy separate registered
phases, reducing the long table-to-response path.

This does not order arbitrary upstream TX producers or drain downstream
timeout/replay work. Future integration needs closed producer admission,
ordered tokens through the real RX/state/retransmission consumers, retry
queue ownership and acknowledgements. No component may infer that proof
from external idle, an ACK, this readback alone, or a fixed delay.

## Private isolated ABI

The176-bit RX input is qpn[15:0], stop16, marker17, PSN[41:18], epoch[105:42],
sequence[169:106], reserved[175:170]=0. Internal typed updates are171bits.
The TX-start input is a FULL24-bit QPN, checked before indexing; `010002`
must fault rather than alias QP2.

The240-bit response is qpn[15:0], PSN[39:16], epoch[103:40], sequence[167:104],
status[175:168], snapshot_valid176, active177, time[209:178], retries[213:210],
failed_qpn[237:214], padding[239:238]=0. Full64-bit epoch/sequence and24-bit
PSN are echoed, not reconstructed from narrowed context. Timeout40 is
{PSN24,QPN16}. This ABI is private test/component integration, not verbs.

| Status | Meaning |
| --- | --- |
| 0 | Actual snapshot is inactive with zero time and retries; timer state only |
| 1 | Out-of-range marker QPN; no timer entry indexed |
| 2 | Active timer, nonzero time, or outstanding retry state |
| 3 | Invalid zero epoch or sequence |
| 4 | Sticky malformed encoding or full-width QPN fault; failed QPN retained |

## Short evidence, preserved failures and timing limits

Current `timer-fence-csim-003.json` passes26actual-C++ readbacks, including all
eight entries, full tokens/PSN wrap, pending starts, FIFO ordering, invalid
full QPN/reserved encoding and the REAL1ms timeout. C simulation takes0.064s;
isolated HLS construction takes34.916s. Its generated13RTL files are retained
with frozen source/profile/driver hashes. Source invariant units003pass4
methods in0.005s, including byte-identical original scan/backoff/stop logic.
These units explicitly skip on a clean checkout lacking the retained HLS
input fixture; that skip is not evidence of circuit verification. The
standalone construction/RTL probes require the actual verified inputs.

Current `timer-fence-RTL-003.json` tests those exact generated RTL files with
FOUR-STATE Icarus, not a timer replacement or edited generated RTL. It passes
46readbacks in25.432s, all8entries, real FIFO/output backpressure, full token
ordering, late TX start, invalid inputs and a250010-cycle actual timeout.
Both response streams retain valid/data while stalled. Crucially an actual
timeout remains VALID and HELD after a subsequent timer-state OK response.
Therefore the test positively demonstrates why state OK is NOT core drain
or a memory/CQ/release proof. There is no host/peer/FPGA access in these tests.

Historical csim001 failed on a C++ numeric-token spelling before synthesis.
csim002 passed function/construction but estimated4.627ns at4ns target.
RTL001 failed because the bench initialized reset asserted without driving
an assertion edge; generated FIFO occupancy/address registers stayed unknown.
Read-only diagnostics reproduce it, then show proper reset and unchanged
RTL passing all46queries. RTL002 is that historical unstaged circuit's valid
22.479s functional pass. Exact original driver/profile snapshots and all
failed reports/logs remain. Derivation001 had an uppercase pragma spelling
in its checker, not a circuit failure; its corrected002 checks the actual
lowercase pragma and preserves the failed checker snapshot. Source-unit003
only adds the explicit missing-fixture skip; all4methods execute here.

Registered phases improve the HLS estimate to3.911ns (FF1041/LUT2182, no BRAM,
URAM or DSP). This is NOT physical timing signoff: scheduling still reports
effective-budget/II warnings (including3.911ns input-to-branch and3.489ns
original scan-to-timeout). No original-clock resulting full-board setup/hold/
pulse/skew/routing/DRC/check_timing/conditional-CDC gate has been run for this
new component. Old full-board/OOC capacity and timing failures remain failed.

## Remaining integration and operating constraints

Next implement the other real-consumer/producer/retry ownership fences, then
bind the resulting genuine full-owner certificate to shared-role/lifetime
retirement and actual CQ publication. Native coherent SQ/MR/PTE/PCIe/MAC,
kernel ib_device/provider and broader SEND/RECV/immediate/Atomic/concurrency/
recovery/congestion/interoperability work remain in scope, not completed by
this isolated readback. Original READ/WRITE and raw138/delivery140 HLS are
unchanged rollback baselines.

No hardware/JTAG/programming/flash/module install-load-probe/traffic/fan/BIOS/
network/reset/reboot/commit/push. BIOS Medium and management are untouched.
Builds needed for features are allowed; tests remain short. Exact authenticated
Codex thread/active-goal reboot recovery is still unproven; no reboot is needed.
