# Actual BTH/EXH receive parsing and retained owner handoff

## Progress051: current full-query capture and actual quarantine stalls

The actual same-table query decoder now captures ALL320bits in a genuine
elastic register before producing the original typed query. Every original
field and reserved22-bit guard is preserved, not replaced with a late QP /
head owner or an externally supplied success bit. Pop/replacement preserves
II1; the actual producer cannot overwrite a held query. HLS007 estimates
3.947ns overall (formerly4.002ns); query decoder4.002->2.542ns. All7measured
tasks II1;104BRAM18K/36109FF/35418LUT/0DSP/0URAM. Compile14.944s/HLS123.340s.
The estimate is now below nominal4.000ns ONLY. Original1.080ns
uncertainty/effective2.920ns warnings remain: NOT physical setup/hold/route /
full-board capacity/DRC/check_timing/CDC signoff or permission to program.

Actual C++006passes1.461s:1154full320query vectors (zero/all-one/every one-hot /
one-cold bit/512seeded patterns), including QPN24, epoch64, owner168, PSN24,
full syndrome, has-AETH/marker and all reserved bits. Previous full keep /
count/opcode/decoder/frame-check tests remain, including1048576actual guard
beats. Source00812units pass0.117s; source00712pass0.113s before CLI preflight
was added. No field/guard/assertion/range/capacity/clock was removed.

Fresh base XSIM00410cases and control XSIM00512cases pass, including the
original20oracles and two additional genuine quarantine/backpressure cases.
New11invalid first keep /12declared length reached without TLAST actually
produce private frame-fault40. The pipeline accepts only10/11beats before
upstream TREADY stops; the unaccepted source beat is held127cycles without
withdrawal, force, reset or test pool mux. No parser metadata/body, fence,
replay/RDinit, allocation/return or CQ effect; real pool remains2000free.
The new passive source-AXIS hold assertion also applies to the old cases.
This closes050's SPECIFIC long-bad-frame upstream-stall coverage gap, NOT
general protocol error policy, safe abort/flush/reset/unpin or recovery.

HLS006 remains FAILED: the command mistakenly named the Vitis/bin directory
instead of its vitis-run executable. C++ compile completed, but HLS never
started; exact inputs/logs/error record retained. The driver now checks
file+execute permission BEFORE creating a build. Fresh007uses the actual
executable; the failed attempt is not promoted or overwritten.

Storage: only terminal per-WR/timer/TX/RXlookup/current-HLS DB duplicates
3059files were losslessly archived after exact original/member SHA checks.
None of those DB paths was in050's indexed current artifact maps. Source /
frozen inputs, actual generated Verilog/VHDL and normal syn reports remain
in place; per-WR138/delivery140 aggregate hashes remain EXACT. Earlier3017
archive members are unchanged; all DB bytes recoverable through records
terminal-db-{manifest,archive}-051/051b.json and each run's archive. No root
filesystem expansion/remount/hardware/storage configuration or guard1500MiB
reduction. Only expanded duplicates removed, no permanent evidence/data loss.

The checked original rx_ibh_fsm still performs state-table/timer/retransmission
updates, and rx_exh_fsm consumes MSN/read-init before issuing memory commands.
They are NOT yet connected to this same-table immutable owner path /native
WRMR context. The existing shared-HLS RTL's one-active-role/<=4096B guard is
a PROTOTYPE, not a reduction of the full goal. Bind the real retained native
context BEFORE accepting metadata; preserve PD/key/range/pin/epoch ownership
through actual state/memory/MAC/PCIe/CQ, return each real coalesced-ACK lease,
and produce genuine ONE-core drain before releasing refs. No constant1 or
port-idle substitute. All11requirements remain, drain0/refsHELD, sourceoffline.

History audit is now a reusable report-producing identity checker rather
than an oversized terminal JSON dump. Incremental progress records refer to
the exact parent checkpoint and full generated audit instead of duplicating
the entire history. This changes storage/transport format, NOT requirements
or verification scope; original records remain immutable, failures explicit.

## Progress050: retained previous streaming count/check/commit pipeline

The former ingress now has three actual II1 tasks: annotation of the exact
17-bit cumulative count, frame-guard evaluation, and validated retention /
frame-command commit. Two private320-bit begin streams keep the complete
descriptor with each stage; a begin is NOT a parser command/authorization.
Annotation128 retains decoded95:0, total112:96 and first113. The check task
sets bad114; reserved127:115 remain0. Exact keep, minimum/opcode, full length,
overflow, last/non-last and reserved-bit guards remain. No capacity, clock,
range or permission cuts;8192retained words /uint16 frame bytes /8QP /
2000metadata remain. Actual packet bytes are unchanged.

The check task's genuine one-entry elastic register can pop and replace a
beat on the same cycle and does not overwrite a held beat. Actual commit
rejects bad/reserved bits, writes each valid word into the REAL retained
FIFO, and emits the parser command in a later EMIT state only after the
validated last write. A new private frame-fault output joins the existing
real-pool/process quarantine; it is not an injectable success/receipt port.
Ingress captures the actual completed320-bit descriptor before comparing
ALL bits in a separate state; nothing reopens on a merely buffered command.
Native admission/lifetime/CQ authority is NOT added by these stages.

Intermediate HLS0045.084ns -> CURRENT0054.002ns, original4.000ns target /
1.080ns uncertainty /2.920ns effective budget unchanged. **Still UNMET**:
not rounded to4ns, no placed/routed setup/hold/pulse/skew/DRC/check_timing /
CDC or full-board capacity signoff. Current stages: decoder3.300ns,
annotator3.947ns, frame-check3.624ns, frame-commit3.895ns, frontend3.660ns,
actual metadata process3.683ns; all6 II1. The actual remaining nominal
bottleneck is the SAME-table query decoder as02_rx_lookup_decode4.002ns.
Current104BRAM18K/35788FF/35366LUT/0DSP/0URAM, compile14.943s/HLS123.686s.
HLS004104BRAM18K/35339FF/35289LUT is retained intermediate evidence only.

Current source units00610pass0.102s; earlier00510pass0.098s frozen history.
Actual C++ differential005passes1.417s: all256keep,524288full-uint16-count /
valid-keep pairs,256opcode minima,65536actual decoder calls and1048576
ACTUAL frame-check annotated beats against original last/length/header rules.
These synthetic component annotations are not genuine native/end-to-end
packets, RTL backpressure proof or DMA placement. Earlier C0041.417s is the
pre-elastic version, retained exactly. Fresh base XSIM00310FOUR-STATEcases
pass70.656s,max8.081s; control XSIM00410pass108.747s,max12.746s, all256AETH
bytes. Exact current005Verilog/production wrapper, real pool/timer/reset /
X-Z calibration, unchanged oracle benches and30s individual wall bounds.
Actual metadata/body/fence stalls, full65535frame, truncation/fullQPN/PKey /
keep/header-version/ambiguity/epoch checks pass. All20public summaries match
049 except expected pipeline cycles; not universal/cycle equivalence.

Storage: completed wireRX HLS001/004/005 temporary DBs and the duplicate
generated VHDL004/005 trees were losslessly archived. SHA comparison preceded
removal of ONLY expanded duplicates;1907files are recoverable. HLS001543
members ALSO match the exact previous049checkpoint hashes; original reports
are not rewritten. DB archive records050/050b and VHDL050c each point to a
full member manifest. Restore db/ under that run's project/solution1/.autopilot,
or vhdl/ under project/solution1/syn after space is available. Actual Verilog
used by XSIM, frozen inputs, normal syn reports/logs and READ/WRITE rollback
remain in place. Earlier0491110-member archives are unchanged. No permanent
source/evidence/userdata loss, storage configuration/remount or disk-guard
reduction (1500MiB). Existing USB remains ro/noexec.

The private elastic register is structurally guarded; a dedicated long-bad-
frame/quarantine upstream-backpressure RTL case remains useful additional
coverage, not inferred from C++ streams or external metadata/body stalls.
All11requirements remain. Actual native packet/QPepoch/WRMR capture and
effectful RX/state/MSN/coalescedACK/TXtimerpool/MAC/DMA/CQ/ONEshared integration
are still missing; raw body is NOT DMA payload, receipts NOT lifetime grants.
Shared drain0/refsHELD; no FPGA/JTAG/traffic/fan/BIOS/network/reset/reboot/push.

## Progress049: retained previous registered schedule

The current generator replaces eight serial32-bit conditional increments
with an exact4-bit canonical-keep decoder. All256keep patterns retain the
old admission rule. A real II1 dataflow decoder carries the unchanged full
80-bit beat plus keep-count/header-minimum fields in a96-bit internal FIFO.
It does NOT authenticate/admit a packet. Frame-count/length/TLAST validation
and whole-frame retention remain before actual parser release; no serialized
extra per-body-beat state or smaller frame/queue geometry is introduced.

Actual header read/check/classify/query construction and lookup guard
evaluation/decision are registered separately. The SAME real metadata
process also registers first-record epoch selection before its next epoch /
generation/sequence comparisons. All original identity, ambiguity, range,
tail/chain, control-syndrome and receipt guards remain. Progress047 sources
are unchanged; only this composition's derived process is rescheduled.

HLS00110.256ns -> intermediate0025.678ns -> current0035.298ns at the SAME
4ns target /1.080ns uncertainty /2.920ns effective budget, KU3P-1,8QP /
2000metadata /8192frame words. Current decoder3.300ns, ingress5.298ns,
frontend3.660ns, actual process3.683ns. All four report II1. The remaining
critical ingress path is fault/readFIFO ->17-bit count add ->length compare
->retained-FIFO write. This is STILL UNMET, NOT placed/routed setup/hold /
full-board capacity/DRC/check_timing/CDC signoff. No constraint waiver.

Current003104BRAM18K/34499FF/34730LUT/0DSP/0URAM; C++ compile15.497s,
HLS121.680s. Intermediate002104BRAM18K/34405FF/34602LUT and exact sources /
generated RTL/reports remain retained, NOT counted as a current RTL pass.

Nine source units004pass0.100s. Actual C++ keep/length differential003passes
0.053s:256keep patterns,524288 full-uint16-count/valid-keep combinations,
256opcode minimums, and65536 calls to the ACTUAL decoder for every keep /
opcode pair retaining all80bits. Earlier001/002 C tests and source003 are
frozen history, not source-current proofs. C++ tests do not prove RTL flow
control/native admission or DMA. Fresh base XSIM00210cases pass71.153s,
max7.931s; fresh control XSIM00310cases pass106.691s,max12.698s. Both use
exact current003RTL, original4ns, real pool/timer/reset/X-Z calibration,
unmodified production wrapper/oracle benches and30s individual wall limits.
All256syndrome bytes, real handoff/fence stalls, actual full65535frame and
malformed cases pass. All20public case summaries match048 except expected
cycle changes; this is NOT universal/cycle equivalence or native proof.

Storage: the two OWN TERMINAL049 HLS002/003 temporary .autopilot/db trees
were losslessly archived,1110files/301823190bytes ->35236016bytes compressed.
Every original and archive member SHA matched BEFORE removing only those
duplicate expanded DB directories. Manifest and archive records are
results/2026-10-18/rocev2-rnic-terminal-db-{manifest,archive}-049.json.
Each run retains terminal-autopilot-db.tar.gz; its db/ subtree can be restored
under that run's project/solution1/.autopilot after space is available. Original
048/earlier DBs, frozen sources, syn RTL, normal synthesis reports/logs and
READ/WRITE rollback are unchanged. Disk guard1500MiB is NOT reduced; USB
ro/noexec and all system/storage/hardware configuration remain unchanged.

No new native packet/epoch/WRMR authorization, effectful RX FSM, memory DMA,
CQ publisher or ONE-shared/native/board selection. Raw body is still NOT DMA
payload; receipts are NOT a lifetime grant. All11requirements remain active,
shared drain0/refsHELD; no FPGA/JTAG/traffic/config/reset/reboot/commit/push.

## Progress048 baseline (retained history)

Progress048 adds an opt-in candidate joining the actual FNS BTH/EXH byte
parsers to Progress047's SAME pointer8/metadata2000 lookup/process, actual
timer and real pool. The external synthetic lookup-query port is removed
from this composition. Original candidates/READ-WRITE rollback sources and
shared/native/board selection are unchanged. This is NOT a finished RNIC.

## Packet and ownership boundary

The ingress descriptor supplies full24-bit QPN, trusted64-bit captured QP
epoch, uint16 frame length, admission flag and expected PKey. These are
CURRENTLY CALLER INPUTS, not genuine native admission. Epoch is not on wire.
Real peer/connection/QP epoch capture, ICRC, PD/MR authorization, freshness
and safe reset/PSN/QP reuse remain mandatory before live selection.

An 8192-word retained FIFO holds the entire declared uint16 frame before
parser release: contiguous nonzero keep, non-final full keep, exact TLAST /
length and original opcode/header minimum are checked. No 4096-byte cap or
FIFO-empty completion shortcut is used. This is existing-device RAM in an
offline source candidate, not a hardware addition or proof of board fit.

Actual original BTH parsing, original4-byte word shift, and actual AETH/RETH
parsing are derived from retained licensed FNS sources. Complete syndrome8,
raw BTH96, raw EXH128, original isNAK and numPkg accompany the result. All
three real parser TLAST branches produce explicit parser-end receipts. Full
QPN/PKey/header version/reserved bits and query/result/full-lease echoes
are checked. Nonzero admission/epoch alone do NOT prove authentication.

READ responses / ACK use the SAME locked-root metadata traversal. UNIQUE
selects immutable full248-bit lease; NO_MATCH/AMBIGUOUS/EPOCH_MISMATCH have
no selected lease. REMOTE_RAW is explicitly different: status255, qualified0,
lease0, original request fields retained. It is NOT remote MR authorization.

Metadata remains held until genuine external valid/ready acceptance. Only
the production wrapper's private exact1024-bit receipt permits the frontend
to accept the lookup result, and thus unlock the table. Lookup performs no
retirement. A future real consumer MUST retain real WR/MR lifetime BEFORE
acceptance; identity/raw metadata is NOT a lifetime grant.

Body cannot flow before that actual metadata handoff. Output is the ACTUAL
FNS EXH-parser raw stream, NOT DMA payload: READ AETH bytes remain, and no
pad/ICRC removal or memory-placement authority is implied. Nonunique local
responses and nonzero high-three-bit AETH control classes drain internally
instead of leaking as READ data. Full syndrome remains in metadata; no RNR
backoff/NAK handling/protocol success is implemented by this component.

The preserved legacy isNAK flag checks bits6:5 only (also true for E0..FF).
It is not a full-syndrome classification. The new raw-body discard uses
syndrome7:5 instead; future protocol policy must use complete syndrome8.

For forwarded bodies, exact parser-end AND a private actual external body
TLAST receipt are required before the ingress packet completes. The receipt
retains the exact previously accepted1024-bit owner token. Header-only ACK /
RETH and an original no-header empty final beat keep their actual parser
semantics. Unused absent-EXH metadata is explicitly zero; no DUT/reset-X
values are forced or waived.

A descriptor marker can enter the real lookup FIFO only after those actual
earlier handoffs. It joins the existing five-input/six-response subsystem
boundary. Following parsing cannot resume merely because a fence is buffered:
both the real core and RX frontend receive private receipts from the actual
external fence transfer. This is NOT whole-core/MAC/memory/PCIe/CQ drain.

## Typed interfaces

Descriptor320:

| Bits | Field |
|---|---|
| 23:0 /87:24 /103:88 | full QPN /trusted epoch /frame bytes |
| 104 /105 | caller admission /same-queue marker |
| 273:106 /289:274 | full168-bit marker owner /expected PKey |
| 319:290 | 0 |

Packet/body80: data63:0, keep71:64, last72, reserved79:73=0.
Marker descriptors have normal/admission/PKey fields0 and an exact valid
full marker owner. Normal descriptors have marker owner0.

Metadata1024:

| Bits | Field |
|---|---|
| 447:0 | complete Progress047 lookup result |
| 543:448 /671:544 | original raw BTH96 /EXH128 |
| 693:672 /694 /695 | original numPkg /original isNAK /REMOTE_RAW |
| 1015:696 /1023:1016 | entire ingress descriptor /0 |

Private meta/body acceptance1024 and fence-resume192 are INTERNAL wrapper
ports to the HLS graph, never externally injectable receipt interfaces.

## Bounded evidence

- HLS001 constructs at original KU3P-1/4ns,8QP/2000 metadata:104BRAM18K,
  34337FF/34605LUT/0DSP/0URAM. Compile14.745s, HLS115.025s.
  Estimate10.256ns is UNMET (ingress10.256/front4.903/process4.644ns).
  Clock uncertainty1.080ns/effective2.920ns is unchanged. No full-board
  capacity/routing/setup/hold/pulse/skew/DRC/CDC signoff is implied.
- Eight source units002 pass0.086s. Initial001 remains FAILED: a negative
  fixture replaced the nonexistent spelling "ins" rather than actual
  "inserts", so it did not mutate its anchor. Correcting the fixture changes
  no production code/assertion/clock/protection; original failed fixture
  is frozen in its retained inputs.
- Fresh XSIM001 compiles exact HLS001 + production wrapper + REAL pool.
  Ten bounded FOUR-STATE cases pass, each6.329..7.683s, total66.144s.
  X-reg/Z-tri calibration, real reset, original4ns and per-case30s wall
  limits remain. Cases cover real non-head ACK identity / held metadata
  blocking a queued actual ACK / genuine head advance, actual READ65 raw
  bytes, full RNR20/NAK60 preservation/no retirement, unmatched-body drain,
  REMOTE_RAW WRITE65 /header-only READ RETH, marker stalled by metadata and
  actual body handoff / actual fence-resume, truncated TLAST /fullQPN mismatch
  /PKey mismatch rejection, ambiguity /stale epoch, full65535-byte frame
  with65523 raw body bytes, and original no-header empty final beat.
- A separate control suite checks every AETH syndrome byte and invalid keep /
  header-version handling. Initial001 is FAILED: the fixture incorrectly
  expected the preserved legacy isNAK to use all three high bits, causing
  an exact metadata mismatch at E0. Original source/fixture/RTL/logs retained.
  A corrected fixture splits256 values into8 independently short32-value
  cases, followed by2 malformed-frame cases; production code is unchanged.
  Fresh002 passes all10 FOUR-STATE cases, each<9.035s: all256syndrome8 values
  preserved,32 class0 frames forward actual69-byte raw bodies,224 control
  frames drain without body/retirement; malformed keep/header-version reject.
  Original4ns/X-Z calibration/30s individual wall bound unchanged.

Result paths: results/2026-10-18/rocev2-rnic-owned-wire-rx-hls-001.json,
...owned-wire-rx-XSIM-001.json, ...owned-wire-rx-derivation-{001,002}.json,
...owned-wire-rx-control-XSIM-{001,002}.json. Exact source/generated RTL/frozen inputs /
compiled snapshot/log identities are retained in the records. Tests are
offline packet/descriptor stimuli, NOT live network/native-host proof.

## Remaining integration and protected state

Actual effectful rx_ibh_fsm /rx_exh_fsm, state/MSN decisions and commits,
coalesced ACK returning each real lease, retry/RNR/NAK policy, genuine captured
connection/WR context and references, actual TX start/allocation/metadata /
timer/pool/MAC-SFD, DMA visibility and CQ publisher still need a SINGLE
shared/native/MR/PTE/PCIe graph. Separate successful components are not that
unified graph. SEND/RECV/immediate/Atomic/zero/large/multiSGE and all other
11 requirements remain; none is deleted by this raw RX scope.

Original Progress047 full2000-live traversal remains unqualified after its
unchanged30s timeout; extra TWO-STATE active-region convergence is unresolved.
This new suite is not a substitute for those missing qualifications.

local_core_drained=0; WR/MR refs remain HELD. No FPGA/JTAG/programming, module
installation/load/probe, traffic, fan/BIOS/network changes, reset/reboot,
commit/push. BIOS Medium, management and unrelated devices preserved. SRAM
only after full resulting-board gates; no flash. Reboot restoration remains
unproven, no reboot needed/performed. Active full goal remains incomplete.

