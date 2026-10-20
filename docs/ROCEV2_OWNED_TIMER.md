# Owned actual timer coupled to insert/ACK/head/replay processing

Progress047derives a SEPARATE same-table RX lookup/process/timer candidate
with actual read locking/private response acceptance and a fifth query-input
closure marker (new fence bit310). Original THIS candidate/interface stays
unchanged. New lookup HLS4.644ns is UNMET, not a replacement for current
timerHLS0043.613ns; seven fresh FOUR-STATE cases are scoped, full2000live lookup
not qualified. Real packet/RX/native/shared/MAC/DMA/CQ binding remains.
See `ROCEV2_RX_OWNER_LOOKUP.md`; no whole-core retirement permission added.

Progress046improves the SEPARATE actual TX producer candidate estimate to
3.964ns from5.896ns at unchanged4ns; warnings/no physical signoff. Its current
5FOUR-STATE cases include actual ACK/AETH and held-token checks. It is still
NOT joined into THIS timer/process/pool graph or selected in shared/native /
board. Current timerHLS0043.613ns and its6XSIM cases are unchanged, not replaced
by TX-only evidence. See `ROCEV2_OWNED_WIRE_TX.md`; full goals remain.

Progress045adds a separate actual FNS TX producer candidate carrying full
WR context through local/event/BTH/EXH and matching real PSN/address queues.
It has short FOUR-STATE evidence but is NOT joined into THIS timer/process /
pool graph; first EXH start still needs actual allocation/commit/lease binding,
and is not MAC SFD. New TX HLS5.896ns UNMET does not replace current timer
HLS0043.613ns evidence. See `ROCEV2_OWNED_WIRE_TX.md`; full goals remain.

Progress043 connects the ACTUAL timer producer to the real owned
retransmission process,8pointer/2000metadata tables and real lease pool.
`rocev2_owned_timer_retrans.v` has NO externally injectable timer-request
port. Timer starts, ACK/head controls, retry rearms and barrier/resume messages
are actual process outputs, not test callbacks. Original Progress041/042 and
rollback sources remain untouched; this option is NOT selected in the shared
native/board parent.

This is a metadata-processing producer composition, NOT yet the full FNS
wire `rx_ibh_fsm`/`rx_exh_fsm`/`generate_ibh`/`generate_exh` context binding.
Initial starts follow actual leased metadata insertion, not actual MAC SFD.
Wire producers, coherent SQ/native runtime and downstream MAC/DMA/CQ remain
required. No completed general-RNIC or whole-core retirement claim is made.

Progress044 pipelines the actual timer's compare/normalize/time/horizon /
commit actions and marker/resume validation. Current HLS004 whole-subsystem
estimate is3.613ns (timer itself3.489ns) at unchanged4ns, improved from6.894ns.
Warnings remain against2.920ns effective budget; this is NOT placed/routed
timing or full-board/CDC signoff. The same current coupled graph now also
passes six XSIM FOUR-STATE cases with explicit X/Z calibration, each<21.367s,
including the actual1ms/two-WR replay. Details and historical negatives below.

## Full identity belongs to the oldest outstanding record

One timer per QP tracks the head's actual full248-bit immutable lease. Later
TX inserts on that QP can append newer WRs without retagging the oldest timer.
Timeout output copies the stored head QPN/original PSN/epoch/sequence; a queued
old timeout cannot acquire the new head's identity through a late QP lookup.
The real replay walker checks the initial WR identity, then preserves each
following record's OWN full lease while enforcing QPN/epoch/monotonic sequence.
It now handles a valid list crossing multiple WRs, rather than relabeling all
records with the original head's context.

After an EXACT successful real pool return, the actual process reads the next
head's actual metadata, validates its index/generation/QPN/epoch/sequence and
sends an old-lease→next-lease control. The timer updates its head only from
that control, or binds an unbound first insertion. Partial READ progress keeps
the immutable lease and follows original FIRST/MIDDLE timer-reset semantics.

Exact old head lease comparison and full64-bit epoch/retired-WR sequence
tombstones reject stale stops/rearms and delayed TX starts after retirement.
An ACK/stop can arrive before a delayed TX start without reactivating completed
work. Advancing between records of the SAME WR does not prematurely retire
that WR's sequence. Provably older queued timer requests are ignored without
retagging/replaying/freeing the newer WR; future/wrong-QP/unknown identities
retain fail-closed guards. This is not completed general NAK/RNR/loss recovery.

Epoch change while an old head remains bound quarantines instead of overwriting
it. These table registers reset locally: this is NOT persistent kernel/QP epoch
management, safe abort/flush/reset, power-loss recovery or unpin permission.
The real pool separately retains uncertain leases; resetting timer/control
state does not make those reservations safe to release.

## Break the real cyclic producer-fence dependency

Waiting for the timer's TX marker before letting old timeout work reach the
process would form a cycle, because that work itself can rearm TX. The actual
FSMs instead perform this ordered sequence:

1. The process closes its three upstream insert/update/RX-retry queues and
   places a marker behind its actual earlier ACK/head controls.
2. The timer closes new scanning, places an ordered marker AFTER earlier real
   timeout outputs, but still accepts prior/replay TX starts. It does not
   invent a snapshot from FIFO idleness or erase active state.
3. The process finishes earlier timeout/replay work before consuming that
   same-queue timer marker, then emits the TX marker after actual retry rearms.
   The timer applies all earlier TX starts and samples its real entry only
   after BOTH control/TX markers agree.
4. The process joins this SIXTH actual consumer response with the existing
   pointer/meta/pool/event/RDinit acknowledgements. Only the real external
   fence-response handshake produces the private timer-resume receipt and
   reopens producer windows.

BUSY remains BUSY when the target WR still owns a head even if its timeout
counter just reached0. It is not a successful CQE or completed recovery.
The existing320-bit boundary response keeps its original fields, adds timer
qualified302 and timer{time_nonzero,retries4,active,bound}309:303, with319:310=0.
Only retransmission/timer handoff boundaries are covered. Other real upstream
state/parser producers and downstream memory/PCIe/MAC owners may retain work;
shared `local_core_drained=0` and WR/MR references remain held.

## Clock, construction and short verification

Original timer constants/backoff/countdown/retry-cap and8-entry round-robin
scan are retained. At original4ns,1ms is31250idle visits per QP, not a shortened
test constant. Processing controls can delay visits, never shorten the count.
There is no forced DUT state, fake timer RAM, allocator or CQ-success callback.

Historical HLS001/002 estimates5.810/6.894ns both MISS original4ns; their exact
inputs/reports remain retained. HLS003's real compute/commit states improve
to4.186ns, still UNMET. Current004 (`owned-timer-hrgttx1h`) additionally
registers marker format and actual resume-token validation, reaching3.613ns
overall and3.489ns on the timer. Resources70BRAM18K/18814FF/20880LUT; all8timer
entries remain real registers. No clocks, uncertainty, capacities, identity /
range protection or physical gates are waived. Warnings remain at effective
2.920ns budget. No full-board placement/routing/check_timing/CDC proof exists.

Control capture/read/check, epoch normalization, head/time calculation,
retirement maximum, latest sequence and real table commit are separate FSM
states. TX starts have the corresponding stages; marker format/result and
actual resume input/check are registered. Earlier markers cannot overtake the
pending commit because new inputs are not processed outside RUN/HALT_WAIT_TX.
The ordinary idle scan body is EXACT apart from emitting its saved identity;
a source invariant reverses only that output change and compares the original
actions. Control service uses more cycles, but original idle1QP/cycle/II1,
4ns/31250visits/1ms/backoff and full8QP/2000metadata geometry remain intact.

Current verification003 has intentionally SEPARATE scopes:

- Actual C++ timer array/FSM:6queries/250428cycles/0.032s. Real1ms countdown,
  queued old timeout identity across head change, stale controls/starts,
  stop-before-start race, same-WR multiple leases and marker/resume checked.
  C++ streams are not an RTL output-stall or reset-X model.
- Standalone actual timer generated FOUR-STATE RTL:3cases, each<0.666s;
 5snapshots cover oldest-vs-latest owner, real late-control/tombstone behavior,
 closed-window controls, full indexFFFF and mismatched markers. These are
 timer-producer cases, NOT the entire current coupled graph or full1ms RTL.
- ACTUAL coupled process/tables/pool/timer wrapper compiled TWO-STATE:
 6cases, each<3.521s. Real event/RDinit stalls, BUSY→ACK→new clear window,
 malformed/missing upstream markers and a genuine1ms timer replay across TWO
 different WRs with their own full leases, real ACK/head advancement/returns
 and all-six-response fence checked. The final case runs258214cycles without
 any injected timer request. It is not native wire/DMA/CQ or X/Z/physical proof.

Current XSIM001 independently compiles the EXACT current HLS004 RTL, production
wrapper/pool and UNCHANGED coupled bench. Six FOUR-STATE cases pass6.379..21.367s,
including the actual1ms/two-WR timeout. All summary fields INCLUDING diagnostic
cycle counts match the corresponding TWO-STATE cases exactly. A separate
test-only top checks an uninitialized reg is X and undriven tri is Z before
each case; no DUT state/memory is forced. Snapshot hashes are unchanged across
all runs. No ignore-assertion/severity-downgrade/HDL-relaxation flags are used.
This is full current-subsystem FOUR-STATE functional evidence, NOT exhaustive
X/Z/reset fault injection, analog CDC, whole FNS/MAC/DMA/native CQ or physical
timing qualification. Each simulation retains the30s bound.

Initial verification001 passes C++/3standalone FOUR-STATE cases but overall
FAILS because Verilator5.036 crashes internally compiling the coupled graph.
It is retained, not promoted. Historical002 reuses ONLY the exact hash-verified
standalone probe RTL (same source), then freshly compiles/runs the coupled
graph with `-fno-dfg`. This disables a simulator optimization, NOT FPGA logic
or tests. Generated RTL is unchanged and binary hashes are checked before /
after every simulation. No assertions or30s simulation limits were relaxed.
Current003 freshly constructs the standalone probe and both RTL simulations
from current004sources. Four current structural derivation tests004pass0.034s,
now freezing their exact source fixture. Intermediate source-unit002/003fail
only stale comment/temp-variable anchors, not RTL behavior; their original
drivers/reports are retained and not promoted. All timer/horizon/lease/resume
guards remain checked; the current source invariant is stronger.

No FPGA/JTAG/programming/traffic/temperature measurement, module install /
load/probe, fan/BIOS/network/reset/reboot/commit/push/deletion occurred.
BIOS Medium, management/other devices and READ/WRITE rollback remain intact.
