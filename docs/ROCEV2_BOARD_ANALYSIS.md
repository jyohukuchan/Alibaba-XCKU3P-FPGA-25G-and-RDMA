# Full-board RNIC analysis candidate (not released)

This is the actual full AS02 board source/IP/constraint analysis path, not
another isolated endpoint substituted for it. It does NOT produce an image,
program SRAM/flash, load a driver or modify networking/fans/BIOS. Standard
kernel RDMA/provider/native host-memory operation is still unfinished.

Later source work adds optional [shared local/incoming MR queries](ROCEV2_SHARED_MR.md)
to `rocev2_protected_responder`. The META11803build completed from its
unchanged1070-file frozen snapshot, which does NOT contain that edit, the WQE
frontend or per-WR delivery. Its timing/resource outcome is evidence for the
frozen comparison only. Previous original-path checksum equality is historical
after the protected-source edit; never attribute that CAD outcome to current
shared-client source or relax preparation/physical/CDC gates to accept it.

Subsequent SQ work adds a default-off terminal-READ-error recovery option in
`rocev2_corundum_dma_backend` and new SQ-only fetch sources. Immutable META
inputs contain NEITHER change. Mutable-original differences now include both
responder and backend; original default protected error behavior is retained
and must pass fresh portable checks. No frozen CAD input is edited.

## Terminal older META comparison, not timing closure

The original session11803completed0at2026-10-19 04:00:53UTC without writing
an image. Process success means analysis/report generation completed, NOT
physical timing success. `rocev2-rnic-full-board-meta-route-001.json` binds
the final reports/checkpoint and all1070unchanged frozen inputs.

Actual post-route optimized4ns/250MHz results: WNS-0.348ns/TNS-799.383ns/
6144setup-failing endpoints; WHS+0.008ns/0hold failures;0pulse failures.
All312317routable nets are routed with0routing errors. All38bus-skew
constraints meet (minimum slack+1.712ns), and all12check_timing categories
report0. DRC reports0errors/0critical warnings/36warnings. Actual post-route
resources are134148LUT(82.44%),222844FF,286BRAM tiles,39URAM and3DSP.

The worst setup path runs from responder guard `data_remaining_reg[19]`
through memory-write keep/ready logic to HLS `inputWord_data_reg_105[13]/CE`.
It has14logic levels and4.278ns data delay (1.311ns logic/2.967ns routing).
This source-bound path suggests breaking the guard/ingress ready dependency;
it does NOT justify slowing clocks, bypassing checks, reducing tables or
editing generated frozen HLS. A new implementation and resulting complete
physical checks are required before claiming a fix.

CDC still lists18critical paths (7CDC-1,4CDC-4,1CDC-10,6CDC-13),14CDC-6 and
1555CDC-15warnings. Exact conditional CDC review is NOT completed or inherited
from the older deployed image. No blanket waiver, physical pass or current
per-WR/shared-MR/SQ/native release is authorized. Mutable original responder/
backend differ from the snapshot as documented above; its old full-board
outcome must not be relabeled as the current feature image's result.

## Tested state-reset HLS candidate

Separate build `state-reset-hls-ow6h8r42/project` is terminal0(session40530),
all264frozen inputs unchanged.138generated files have SHA256
`53d2587920d678969f045a7ba300d821533b5efae35f09145aba3b0344a36b0c`.
The old control-only7bcfddc9and tested reset-all5fab3e92outputs are unchanged.
STATE resets static/global/control state while generated pipeline data
register reset branches differ from ALL. Narrow actual IPv4 constructor
reset-state001passes all88observations, no bad header states.

STATE does not materially reduce area: HLS estimates remain32097LUT/84023FF/
77BRAM18K/4.043ns for both ALL and STATE. Actual same-top STATE synthesis001/
session7120completed0 under `native-state-synth-X1V8Zolo/impl`, with all186
frozen inputs verified. It uses135314LUT(83.16%)/192339FF/168BRAM tiles,
only140LUT/175FF less than ALL. At4ns, WNS is-1.074ns with3193setup failures,
WHS+0.016ns/0hold failures and0pulse failures. Its worst unplaced path is
reset to the HLS remote-memory-command FIFO, not the ALL RAM-address path.
The previous ALL estimate was135454LUT(83.24%)/192514FF/168BRAM tiles and
WNS-1.011ns. Both exclude parent/app/board and are neither routed passes nor
proven final full-board capacity results. No image is authorized by them.

Read-only ALL hierarchy audit001 preserves its source checkpoint. Each HLS
instance dominates endpoint area (the initiator HLS is50693LUT). A generated
1024-bit packet FIFO maps to577SRLs plus control, matching512data+64keep+1last:
the apparent padding is already removed there and is NOT evidence of a
447-bit-per-word resource-saving opportunity. Rebuilt hierarchy can also
attribute absorbed logic to a FIFO; its module total alone is not a safe
basis for changing depths, QP capacity, retransmission or integrity checks.

### Separate sequential-metadata-reset candidate

Primitive-name audit `storage-audit-SLfxkD6r` completed0(session92084) without
changing the ALL checkpoint. Much of the large rebuilt FIFO hierarchy is
actually `written[...]` logic absorbed from the HLS resettable RAM wrappers,
not the two-deep FIFO storage. The generated metadata RAMs each implement
a2000-bit reset/written vector and zero-vs-RAM output selection. This is
direct generated/netlist evidence, not a reason to reduce table capacity.

`build_meta_reset_profile.py` applies `sequential_meta_reset.patch` to ONLY
the allowlisted retransmitter header in a NEW frozen FNS copy. It leaves
the pinned checkout, STATE/ALL outputs, original physical gates and running
full-board snapshot untouched. The10metadata fields are explicitly cleared
for ALL2000entries before ANY request is consumed; warm reset restarts the
sweep, including an interrupted sweep. Only that array's implicit reset is
disabled; sweep index/completion and all other STATE reset remain enabled.
No smaller QP/table/FIFO, shorter timer, disabled retry or integrity bypass.

The intended tradeoff is a bounded post-reset initialization delay in place
of parallel reset bookkeeping, NOT exposure of uninitialized data. Actual
generated RTL, reset interruption, all fields/storage/append/backpressure,
old/protected wire regressions and final timing must independently pass.
AMD documents per-variable [reset control](https://docs.amd.com/r/2025.2-English/ug1399-vitis-hls/pragma-HLS-reset)
and the latency of [array initialization](https://docs.amd.com/r/2025.2-English/ug1399-vitis-hls/Initializing-and-Resetting-Arrays).

Candidate HLS session68644completed0 in `meta-reset-hls-1_q64nwg/project`,
all frozen/original inputs unchanged,138generated files SHA256
`60c9a20e6671f223444c9a115d6295fdff456672d6354ed240e2317529cdbc19`.
HLS estimates24981LUT/64294FF/77BRAM18K/4.043ns, versus STATE32097LUT/
84023FF. Actual same-top native-meta synthesis69986completed0 with all186
original/frozen inputs verified:85465LUT(52.52%)/154206FF/168BRAM tiles/3DSP,
49849LUT and38133FF less than STATE. This is actual endpoint area reduction,
not full-board signoff. Unchanged4ns unplaced WNS-1.127ns/TNS-1242.412/
3579setup failures, WHS+0.016/0hold,0pulse failures. Worst path is reset to
HLS retrans2rx_init FIFO;9DSP pipeline warnings,0DRC errors/critical. No
routed/timing pass or slower clock/integrity/protection bypass.
It is now selected ONLY for the separate frozen full-board META analysis
described below, NEVER an image. Three synthetic
patch-scope/preservation/refusal tests pass (unit001,0.010s); these are not
functional reset evidence. The actual table test first passes on the old
STATE generated RTL: metadata-reset001/session82186terminal0,8024response
checks (4023zero,2000all-field data,2001append),16resets,82254clocks with
output backpressure. No testbench internal forcing/repair. This baseline
pass must NOT be relabeled as the new candidate's result.

Fresh new-candidate metadata-table001/session40654also completed0 under
four-state Icarus:8024checks/4023zero/2000data/2001append/16resets/100235clocks,
including enforced no-admission before2000initialization clocks, queued last-
entry read, warm reset and resets interrupting the sweep. The generated
clear index/completion have explicit reset branches; metadata RAM wrappers
no longer contain the old `written` vectors. New IPv4-reset001also passes
all88constructor observations. These are narrow module tests, not a full
new-candidate wire/native pass.

Three fresh new-candidate native-control/legacyREAD/legacyWRITE Icarus runs
were bounded at60seconds and returned124(no protocol outcome). Their empty
outer logs are not a success or an assertion failure. Keep the limit,
do not silently change protocol deadlines. `fast_transport_sim.py` provides
additional compiled TWO-STATE runs with unchanged original benches/assertions,
separate180second compile and30second simulation limits. Their records must
retain `four_state_simulation=false`, `X_Z_behavior_verified=false` and
`compiled_two_state_additional_only=true`; they cannot replace four-state
release/reset/native evidence. Native-control90569and legacyREAD92532ended1
at the180second compilation bound with generated C++ fork synchronization
locals referenced outside their scope; neither simulation ran or passed.
Their original logs/generated C++ are retained. A new helper revision
disables C++ FUNCTION splitting (not RTL/bench/assertion changes), while
retaining file splitting. Retried native-control55072and legacyREAD35694
are live compiled checks, not assumed passes. The helper now owns an
isolated compile/simulation process group and terminates/reaps that group
on timeout; a finite3case success/error/timeout diagnostic passes. No
unrelated process group is targeted.

Those retried002compilations55072/35694also hit their180second build bound
(terminal1), without an observed generated-C++ scope error or any simulation
outcome. Do NOT call them communication successes. Third attempts003,
native44081and legacyREAD60287, retain the identical RTL/benches/assertions
and30second execution bound, disable C++ grouping and use compiler-O0 to
shorten binary construction. Build allowance is600seconds, separate from
the user's short simulation requirement. Before the compiler, each new
directory now records exact input/bench SHA256 and command in `inputs.json`.
Their current source/compile identities are separate from002, not retroactive
verification of the interrupted builds. Both003attempts now completed0:
native compile445.51s/simulation9.77s; legacyREAD compile448.81s/simulation3.98s.
Their results remain explicitly TWO-STATE additional checks, not replacements.

Fresh new-candidate four-state native001/session5455also passed in114.24s.
Its helper subsequently changed ONLY to avoid separately compiling support
modules already directly included by legacy benches. The first legacy
four-state attempt failed compilation for duplicate exact module definitions,
not a protocol outcome. Current helper native002/session26235and legacyREAD
002/session26750, legacyWRITE001/session3761, actual URread001/session31971
and URfence001/session27956are ALL terminal0. Exact60c9a20eHLS, untouched
original benches/assertions and120second execution bounds. Native checks
actual parent guard/control/PCIe,130WRITE/195READ bytes; legacyREAD checks
65capture+127sentinel bytes. UR still causes actual parent fault1/protected
fault34,0success/wire/no page-release proof. Actual patched parent/core/app
compile001/session32303also completed0 with MAC16/external64/synchronous128/
global DMA19/app16; all warnings retained, compile-only not parent traffic.

The full portable139method batch012/session54474completed0(182.686s), and
source-checks011/session7300completed0. These do not contain the new HLS
communication qualification or authorize programming.

Subsequent logical-detach support changes only kernel/shared-C sources, not
the current frozen board or endpoint synthesis HDL. Shared I/O007passes14
C/UBSan tests, full portable batch013/session37189passes143methods(190.797s),
source-checks012/session7716completed0. Source-frozen kernel build003/
session38544links successfully withW=1 against6.17.0-1033-oem, module SHA256
`98b256952223de65b29975cb9836569e5fcaf4b8cace56324b7d0b86087e4a72`.
It is NOT loaded, no bus/ib_device/provider is registered, no user pages
are pinned, and runtime hot-unplug/DMA safety is not proven. See the control
ABI's terminal logical-detach section; clearing a BAR pointer never proves
memory release or allows an uncertain pool/context to be freed.

Fresh STATE full-path evidence (all terminal0):

- State-native-control001/session5002: actual parent guard/control CSR/
  same-port/protected HLS/page/RAM/mux/generic PCIe RTL,21control replies,
  19frames/13rejects/1ICRCdrop/5ops,130WRITE and195READ bytes. Actual parent
  fault0is required at normal statuses; no model host counter feeds proof.
- State-legacy-read001/session87210and write001/session43472: original
  65-byte initiator operations inside the dual wrapper,65READ capture and
  127sentinel bytes. Unconfigured responder cannot emit descriptors/TLPs.
- State-read-error001/session24509and fence-error001/session54393: actual
  generic PCIe UR10, actual parent fault1, protected fault34, no wire success
  or page-release proof.
- State-parent-compile001/session64646: actual patched parent/core/app and
  HLS elaboration, board MAC tags16/external64/synchronous128, global DMA
  tags19/app16. Compile-only, all warnings retained, not full-board traffic.

Additional unchanged original-app regressions on STATE53d25879also pass
(NOT rerun on metadata60c9a20e merely by association):

- RW-read65001/session84158and read4097001/session27428:3messages each,
  initial PSN0xfffffe/wrap, every request/header/ICRC and BAR data/guards.
  The4097case checks12291payload bytes and253untouched sentinel bytes.
- RW-write001/session32372:3x65bytes, cumulative ACK every2, all195wire bytes.
- RW-warm001/session91043:2x4097bytes with distinct data, same QP/PSNs,
  queued stale READ FIRST behind backpressured host frame;8194BAR bytes,
  254sentinels, stale response discarded and host frame retained.
- STATE-timer002/session51070: same original generated-timer assertions,
  Verilator5.036,4ns,8QP ACK-restart/stop phases and armed warm reset;
  first retry250002..250007clocks. Power-up#0delta is ignored by this
  two-state additional check; it is not four-state/native timing evidence.
  Icarus timer001was stopped by the requested60second wall bound, not a
  protocol assertion; its failure log is retained. The compiled timer run
  uses a30second simulation limit, no relaxed protocol-cycle assertion.

Finite MAC/peer/PCIe hard-IP/link/root-complex/host remain MODELS. Original
full large-tail/PMTU/capture/native release coverage must not be relabeled
as rerun merely because these finite cases pass. Full136portable methods
also pass(batch011/session65365,172.001seconds), including6new board input/
snapshot tests whose synthetic files are explicitly NOT functional evidence.

## Frozen FULL-board selection

`rdma/rnic/fpga/prepare_board.py` validates the exact candidate/profile,
generated HLS and current source-bound smoke evidence plus every unchanged
old physical/clock/gate input hash. It selects the pinned board Makefile's
actual source list and replaces ONLY the separately patched parent/core/app
and config. Duplicate/original parents cannot shadow the selected copies.
There are294HDL files,13unchanged constraint files/scripts and3IP generators.
The original VIO/MAC-flow-control constraints and PCIe/PHY generators remain.

All consumed files and provenance are copied to a NEW directory. Paths in
generated `build_inputs.tcl` refer to these frozen copies, not mutable
working files; the full manifest is verified before the tool and at terminal.
Later original-source edits cannot change this analysis snapshot, but they
DO mean its result is historical rather than a current-source release.
The eventual release gate must require the desired exact source hashes.
An existing output is refused; corrupted frozen input is rejected before
project creation. Tcl path quoting prevents substitution by path text.

Original STATE comparison snapshot: `rdma/rnic/build/full-board-analysis-002`.
Its actual Tcl source-only run passes:HDL294/constraints13/IP3,
`IMAGE_AUTHORIZED=0`. It is not Vivado synthesis/route proof.

The actual full-board CAD session5544ran from its frozen driver.
It created the real project, configured PCIe Ethernet class020000/BAR0and
BAR2both16MiB, and launched PCIe/GTY/VIO IP plus full top synthesis. No
terminal/route/physical result is assumed from those launch messages.

That STATE full top synthesis now completed successfully, but its synthesized
resource estimate is188637LUT(115.93% of162720),251154FF/264BRAM tiles/3DSP.
This is an actual full-board synthesis capacity overrun, not just isolated
endpoint risk. Driver5544is now terminal1. Implementation stopped at the
pre-place DRC UTLZ-1 gate:162912LUT-as-logic required versus162720compatible
sites (192excess). The placer did not run; neither route nor physical signoff
exists. No utilization-error waiver, part/clock/constraint change or image
was applied. The frozen810inputs remain unchanged. See
`rocev2-rnic-full-board-state-failure-001.json`; do not relabel this older
comparison as the newer metadata build.

### Current metadata full-board analysis

`prepare_board.py --hls-policy metadata-sequential` additionally requires the
exact one-header derived-source patch/2000-entry capacity,88constructor checks,
8024all-entry/field/reset/append checks, actual parent hierarchy compilation,
and ALL five current native/legacy/UR transport records with explicit
four-state and original-assertion preservation. A compiled two-state record,
partial initialization coverage or other patch set is rejected. Eight portable
board-gate/snapshot units pass(unit003,0.083s); synthetic gate fixtures are
NOT physical/function evidence.

Fresh selected snapshot `rdma/rnic/build/full-board-meta-analysis-001` was
prepared terminal0/session68237. It has1070frozen files,288HDL,13original
constraints and3originalIP generators;138HLS outputs include a different
Verilog/data-file split after removing metadata reset wrappers, not reduced
table capacity/features. Source-only Tcl passes, IMAGE_AUTHORIZED=0. Actual
full META CAD session11803remains live from copied paths. Its actual FULL
top synthesis now completed:138205LUT(84.93%)/213008FF/264BRAM tiles/39URAM/
3DSP, versus STATE188637LUT/251154FF. This removes50432LUT/38146FF in the
actual full board, with unchanged BRAM and original clocks/constraints.
The synthesis estimate is now within device capacity, NOT a placement/route/
timing/CDC/native pass. All1070frozen/1069original inputs remain unchanged;
0synth errors/0critical/363warnings retained. See
`rocev2-rnic-full-board-meta-synth-stage-001.json`. Driver11803continues
physical analysis; no terminal implementation or image is assumed.

Actual post-synthesis UNPLACED timing is now recorded separately:
WNS-3.176ns/TNS-35832.352/35271setup endpoints, WHS-0.661ns/324076hold
endpoints,0pulse failures. Worst path is reset through controller/page/query/
transport-ready to HLS memory-command FIFO RAM CE;13logic levels/6.734ns,
including6.057nsESTIMATED routing.372unconstrained internal endpoints are
also retained as unplaced evidence, not waived or called a release pass.
Optimized pre-place DRC has0errors/critical,31warnings(6DPIP/3DPOP/22RAM
collision advisories). Actual placer is running without the old capacity
waiver; all original clocks/gates remain. Final routed timing/CDC still needed.

Fresh exact60c9a20eoriginal-app regressions now pass on unchanged benches:
READ65/session83235(31.07s), READ4097/session97117(93.49s), WRITE65/session5455
(28.62s) and warm/session2214(79.27s). READ checks3messages/PSN wrap and
all-byte capture;4097checks12291payload+253sentinel bytes. WRITE checks
3x65/cumulative ACK. Warm checks2x4097/distinct data/same QP and PSNs/stale
READ FIRST discard/backpressured host frame,8194payload+254sentinel bytes.
These are four-state original-app tests, not native registered-host-page DMA.
`bounded_original_app.py` keeps original cycle/assertion checks and separate
30scompile/120ssimulation limits, retaining partial logs on failure.

META-timer001/session63696also completed0 on the same generated HLS and
unchanged original timer bench:8621169cycles,8QP ACK restart/stop phases,
26retry events, first retry250002..250007clocks at4ns, warm reset. Its30s
Verilator simulation bound and two-state/power-up-delta scope are explicit;
it is not four-state/native timing evidence. Full old13-size/large capture/
PMTU/release coverage is NOT implied by these selected cases.

This is STILL an analysis-only path. Remaining original initiator release
coverage, original full-board physical/CDC gates and actual native host-memory/
driver ownership remain required. Older STATE coverage is not automatically
transferable; no image command was added.

### Kernel-only work while full META CAD runs

The CSR-only auxiliary candidate now compiles/links with the MR support
module from16pre-frozen source/header inputs against running6.17.0-1033-oem
headers (W=1/gcc13), `rocev2-rnic-kernel-aux-build-001.json`. Its probe is
disabled by default BEFORE dereferencing the private parent structure.
Exact alias/PCI/app/BAR identity checks are not a stable parent-layout proof;
the loaded mqnic binary/header match remains unverified. No module was loaded,
probe/remove/MMIO executed, pages pinned, ib_device/provider registered or
standard verbs implemented. See `ROCEV2_AUX_CONTROL.md`.

Current full portable batch015/session65727passes150methods(173.784s),
source-checks014/session91239completed0. The5new native-attach tests execute
shared identity C/UBSan and static refusal/lifetime-order checks, NOT kernel
probe or real hot-unplug. The earlier kernel-mr-build003 frozen artifact is
historical after the optional auxiliary Makefile addition; aux-build001 is
the source-bound compile/link record at that stage. New WQE support later
changes the Makefile: aux-build001is historical, while aux-build002freezes
20own/header/launcher inputs and links the actual Linux WR conversion APIs.
No runtime driver/verbs capability follows from that compile gate.
None of these kernel-only
changes alter the frozen FPGA CAD inputs or authorize programming.

Separate per-WR HLS716f5d92and explicit transport delivery569df76enow have
fresh table/constructor/per-WR wire/NAK/legacy/protected/error/original-app
tests, described in `ROCEV2_PER_WR_KEY.md`. They are NOT substituted into this
frozen META snapshot or accepted by its current board policy. Whole native
WQ/board integration, complete old release coverage and resulting original
physical/CDC/ownership checks remain mandatory.

## Deliberate analysis/release boundary

The paired `build_board.tcl` runs actual full synthesis and post-route
physical optimization, writes checkpoints and utilization/clocks/setup/
hold/unconstrained/pulse/routing/skew/DRC/CDC/check_timing reports. It uses
the original board constraints, not a slower clock or new false/multicycle
paths. It contains NO bitstream or hardware-programming command and does
not invoke/relax the unchanged old image-release script.

`release_authorized=false` remains explicit. This scoped source/smoke gate
does NOT replace the complete old warm/PMTU/timer/initiator evidence, resulting
original full-board gates, new conditional CDC review or native registered-
memory/driver ownership checks. They remain required before any image/native
trial. A routed checkpoint or old historical positive report alone cannot
authorize programming. Full-parent functional traffic, parent-fault driver
visibility/recovery and standard kernel RDMA/provider/verbs remain open.

Continue the full original goal: registered host pages/real DMA/lifetime,
standard WQ/CQ/per-WR keys, SEND/RECV/immediate/Atomic, bounded concurrency,
wire NAK/RNR/retry/loss/recovery/congestion/network compatibility. Exclude
sustained/many-connection/hardware-addition qualification. No reboot is
currently needed; authenticated exact Codex thread/goal recovery is still
unproven and must be checked before any necessary reboot.
