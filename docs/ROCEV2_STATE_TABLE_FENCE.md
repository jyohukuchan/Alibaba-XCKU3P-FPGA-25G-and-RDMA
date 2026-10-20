# Actual state-table readback with three ordered producer markers

Progress037 adds an opt-in derivative of the REAL frozen FNS state-table
consumer. RX, TX and QPI each present a marker through their own normal FIFO.
The consumer blocks subsequent requests only on a marked queue, executes all
preceding normal work on the other queues, and requires the SAME full168-bit
{QPN16,PSN24,epoch64,sequence64} identity on all three markers before sampling
the actual table. Missing or mismatching markers cannot become success by
waiting a fixed time or by observing a currently empty input.

This is a component of a future genuine core fence, NOT that fence. Upstream
producer admission, actual marker injection after real producer FSM work,
timer/retransmission/retry/stream ownership, WR/MR lifetime and CQ publication
are separate unfinished requirements. No shared/native/full-board core has
selected this derivative; shared `local_core_drained` remains0 and owners
stay HELD. The timer-state component from036 is likewise not whole-core drain.

## Actual implementation and unchanged behavior

`rdma/rnic/hls/state_table_fence_profile.py` retains the complete original ETH
license, ordinary request/response types and ALL original RX/TX/QPI table
actions byte-for-byte inside guarded branches. It preserves all8entries and
the original BRAM table with actual RAW dependencies, not a second shadow
table. No false dependency, table reset/cancel, clock/capacity cut or synthetic
CQ success is added. The original retryCounter's3-bit initialization behavior
is retained, not reinterpreted as a new protocol capability.

An8-bit resettable initialization bitmap gates reads; the real BRAM is not
claimed initialized until original QPI setup has written every field. An
uninitialized fence returns status5 with snapshot_valid0 and no BRAM data.
Full16-bit QPN range is checked before indexing on ALL three ordinary paths
and markers. Bad encoding, invalid ordinary access, or full-token mismatch
sets a sticky fault with the failed producer/QPN, never a low-bit alias.

An elastic dispatch register holds actual FIFO requests before classification
and table access. Normal dispatch and capture can overlap; marker dispatch
does NOT capture a following request on that same call. FIFO read-enable is
based on previously committed seen bits and the saved request type, not the
current range/fault/table result. Sampling, classification and response
emission are also separated. HLS reports final II1/core depth4; this is not a
measured25G performance or resulting full-board timing guarantee.

The snapshot's status0 means the actual local-request window is closed
(`req_next_psn == req_old_unack`) at the rendezvous. It does NOT certify that
all responses, retransmission events or memory/wire work have been consumed.
The real original RX/TX/QPI response streams are still subject to backpressure.

## Private isolated ABI

Each of the three224-bit input streams contains qpn[15:0], argA[39:16],
argB[63:40], retryCounter[66:64], write67, isResponse68, marker69,
epoch[133:70], sequence[197:134], qpState[200:198], reserved[223:201]=0.
For ordinary RX: argA=epsn; TX: argA=psn; QPI: argA=remotePSN,argB=localPSN.
For markers: argA=ownerPSN, other normal-control fields must0. This is an
internal component ABI, not a public arbitrary-DMA/verbs interface.

The336-bit readback is qpn[15:0],PSN[39:16],epoch[103:40],sequence[167:104],
status[175:168],snapshot_valid176,seen[179:177],resp_epsn[203:180],
resp_old_outstanding[227:204],req_next_psn[251:228],req_old_unack[275:252],
req_old_valid[299:276],retryCounter[302:300],failed_source[304:303],
failed_qpn[320:305],padding[335:321]=0. RX's ordinary80-bit response and
TX/QPI's128-bit table responses are the original values with zero padding.

Status0=actual initialized closed request window;1=marker QPN out of range;
2=request window outstanding;3=zero epoch/sequence;4=sticky malformed input,
ordinary access or full-token mismatch;5=uninitialized table. No status is a
whole-core/WR/MR/CQ release certificate. Fault precedence is retained.

## Short source-bound evidence and retained history

Current csim005 passes32actual-C++ rendezvous queries in0.004s, all8entries,
all6producer orders, missing-marker withholding, ordinary original responses,
late TX update, RX update held behind its marker, PSN wrap/high64-bit tokens,
range/zero-token/mismatch/reserved faults. Construction takes36.752s. Complete
input/driver/generator profiles, emitted C++ and generated RTL are frozen and
hashed. Source invariant unit004passes4methods in0.009s: original actions/
types/license/BRAM storage, full-range/initialization/full-token guards and
6changed-anchor rejections. A clean checkout without the retained HLS fixture
explicitly skips these source units, not a claimed circuit verification pass.

Current generated FOUR-STATE RTL005passes59queries in a short bounded run.
It uses the exact actual HLS RTL, not edited generated files or a replacement
table. It checks all8entries/6orders/missing markers/ordinary outputs/late
writes, high64-bit mismatch, full16-bit ordinary/marker QPN guards and20
successive tokens under real FIFO/output backpressure. All four response
streams retain valid/data while stalled. It additionally checks8ordinary TX
writes with continuous VALID followed by actual RX/window readback and restore;
the observed handshake-cycle count is recorded, not a physical25G throughput
claim. Importantly, all THREE real normal
responses remain VALID/HELD after a state-window OK readback. This positively
demonstrates why the component is NOT a whole-core drain or release proof.

csim001 failed at compile on direct ap_uint-to-enum cast; its frozen inputs
and failure remain. csim002 function/construction passed but JSON counters
were affected by original QPI debug output's std::hex ("20" is not a reliable
decimal query count). An explicit std::dec and required32-query check correct
that in003onward. Do not use002numeric summary as accurate decimal evidence.
All historical inputs/profile/driver snapshots and logs are retained.

The actual HLS estimates were0024.618ns,0034.111ns,0044.201ns,0053.158ns at
unchanged4ns. No estimate above4ns was promoted to timing success. Generated
RTL001/002/003 passed54/57/57functional cases on those earlier exact designs;
RTL004passed57on current HLS005before adding the burst case. They are
historical scopes, not the current59-case RTL005or physical proof. Source unit002
failed a stale `else if` spelling check after dispatch refactoring (3/4methods,
pass_testfalse), then003corrected that exact syntax assertion;004updates the
committed-seen checks. Original failed checker snapshots remain.

Current HLS resource estimate is11BRAM18K,1660FF,2475LUT,0DSP/URAM. Its top
estimate3.158ns is not a bound on every independently reported helper path:
decoder effective-budget warnings still quote3.369ns; core warning3.158ns
also exceeds the tool's2.92ns uncertainty-adjusted budget. There is NO Vivado
physical/resulting-full-board timing/routing/DRC/check_timing/conditional-CDC
signoff. Old full-board/OOC capacity/timing/CDC failures remain failed.

## Next real integration

Implement ordered producer FSM admission/injection and actual retransmission
pointer/meta/free-list/event ownership fences; join all owners with the real
timer/state consumers and full saved WR before issuing any genuine retirement
certificate. Then bind shared native coherent SQ/MR/PTE/PCIe/response/MAC/CQ /
kernel/provider lifecycle and wider operations/recovery/network requirements.
Neither a table-window equality nor an ACK/idle/time delay substitutes for it.

No FPGA/JTAG/programming/flash/module install-load-probe/real traffic/fan/BIOS/
network/reset/reboot/commit/push. BIOS Medium and management are preserved.
Original READ/WRITE and raw138/delivery140 HLS rollback sources remain intact.
Tests are short; necessary feature builds remain allowed. Exact authenticated
Codex thread/active-goal reboot restoration remains unproven; no reboot needed.
