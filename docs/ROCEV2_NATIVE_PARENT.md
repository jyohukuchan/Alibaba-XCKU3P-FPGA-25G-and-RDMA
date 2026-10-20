# Native app/PCIe-parent candidate (offline, not released)

The subsequent tested STATE-reset candidate and actual frozen FULL-board
analysis path are recorded in `ROCEV2_BOARD_ANALYSIS.md`. The latter creates
no bitstream and is not a replacement for full original release/CDC/native
requirements. Read its terminal/live handle state before treating older
running-build descriptions below as current.

This stage connects the actual parent engine signals and application DMA in
separate source copies. It is NOT a resulting full-board build, physical
signoff, hardware DMA/pinned-page pass or standard RDMA device/provider.
The running READ/WRITE image, original Corundum parents/application/config,
network, BIOS/fans, drivers and rollback artifacts remain unchanged.

## Separate source preparation

`rdma/rnic/fpga/prepare_native.py` checks exact SHA256 of four immutable
inputs, creates a NEW output directory and mechanically applies
`native-integration.patch` only to those copies. The patch target set must
be exactly the four expected basenames; changed inputs or an existing output
directory are refused. It does not touch the Git index or pinned source.

The selected prepared profile is `rdma/rnic/build/native-profile-004`:

- Application ID becomes `0x41534e31` (ASN1), distinct from old ASR2.
- Application DMA is enabled; global parent descriptor tag width is19.
  The actual3-port interface/app mux and2-port data/control mux consume3
  routing bits, preserving all16application tag bits without truncation.
- Actual data descriptors/status and segmented RAM connect to
  `rocev2_native_endpoint`; they are not tied off or replaced by fake status.
- The unused application-control DMA emits no descriptors and refuses RAM
  commands: ready/done/response-valid0, never a fabricated successful reply.
- The actual global PCIe DMA busy outputs are connected to a parent guard,
  whose proof/fault cross `mqnic_core` to the app through dedicated ports.
  No GPIO/configuration constant substitutes for those signals.

The board top explicitly sets MAC `TX_TAG_WIDTH=16`, despite the lower core's
default6derived from its descriptor table. Compile005uses16, external Ethernet
data64and synchronous Ethernet data128, matching those board-top widths.
Earlier compile002/003/004used the narrower lower-core defaults as partial
elaboration cases; they are NOT the actual board-width gate. The existing
16-bit full-path MAC ownership tests retain the correct board tag classes.

## Actual parent proof

`rocev2_pcie_parent_guard.v` observes the real engine boundary:

- actual registered read/write busy;
- accepted descriptors versus actual status outputs, with retained
  overflow/underflow/error faults;
- each RAM segment's accepted commands versus done/accepted responses;
- current descriptor/status/RAM/TLP offers, including stalled responses;
- actual PCIe correctable/uncorrectable error pulses and completion errors.

It requires registered-zero outstanding counts and no current offers. Fault
is sticky until coordinated global reset; a current error also withdraws
proof before the fault clock. Actual TX-sequence tracking is mandatory;
the parent profile refuses `TX_SEQ_NUM_ENABLE=0`. No timer or model host-
outstanding variable feeds this public proof. Global parent quiet is then
ANDed with actual descriptor-mux/status stages and app RAM offers before
it reaches the endpoint. The existing protected backend, frame/MAC drain
and post-reply invalidation checks remain independent requirements.

Reset is NOT revocation: resetting these counters never certifies release
of old registered pages. The eventual runtime driver must retain old
ownership/quarantine through reset, lost replies and removal until a real
outer recovery certificate exists. Parent fault diagnostics/recovery also
still need a driver-visible control interface; waiting on a withheld proof
must not be confused with successful invalidation.

## Fault-time receive ownership

`rocev2_parent_rx_admission.v` stops NEW MAC-frame offers after parent fault
but preserves an already offered first beat, even if its ready was0, and
the remainder of that frame through gaps/backpressure. Ownership starts on
offer, not just acceptance. Otherwise, gating valid with fatal could
withdraw a stalled beat. Data/keep/user/last paths remain direct and are
owned by the upstream AXIS source. Already queued/admitted work may drain;
this boundary does not pretend to cancel it or free its memory.

## Finite evidence

- Parent-guard-unit001passes12actual-RTL cases with explicit engine/RAM/TLP
  input models: busy/status ordering, each segment, stalls, current TLP/error,
  descriptor/RAM overflow/underflow and error-completion retention.
- Parent-RX-unit001passes6actual ownership/admission cases, including fault
  while the FIRST offered beat has not yet been accepted, partial-frame
  gaps, last-beat stall and denial of a new frame.
- Native-profile tests check copy/patch preservation, required actual signal
  wiring, no old data-DMA tieoff, refused control RAM, strict source hashes
  and no-overwrite/target-set behavior. These are not functional PCIe tests.
- Native-parent-compile005elaborates the ACTUAL patched parent/core/app,
  endpoint/HLS and pinned round-robin scheduler/dependencies, no parent/
  core/datapath stub. It is compile-only: no parameter assertions or traffic
  run, no full board. Compiler width warnings are retained, not globally
  waived; the prior source contains many constant/unused/PTP warnings.
- Parent-guard-native-control001/session16744is terminal0. Actual guard
  replaces the old testbench drain expression in the existing full native
  CSR/same-port/protected HLS/mux/generic PCIe test. Host-model counters remain
  independent ASSERTIONS but are NOT proof inputs. All21control replies,
  19frames/5ops,130WRITE/195READ bytes, actual TLP/fence/TX-sequence and host
  Ethernet/completion checks still pass. This is NOT simulation of the
  entire patched `mqnic_core_pcie` hierarchy; compile005is separately scoped.
- Parent-guard-read-error001/session57134and fence-error001/session87495
  are terminal0: actual generic-engine UR completion reaches guarded
  fault34, with zero wire success and no page-release proof. The real
  parent guard, not a model integer, retains its proof.

Full124method batch009passes on its earlier source snapshot. After the
offered-first-beat/control-RAM refinement, the full130method batch010is
terminal0(session40553,172.842seconds), with fresh parent-guard-unit003and
parent-RX-unit002reports. Do not silently describe the
earlier124run as exercising the later six RX cases.

The parent transport probe now additionally asserts the actual parent fault
is latched when the guarded error status arrives, and is absent for normal
successful statuses. Enhanced read/fence002sessions72353/63477are terminal0
and print `PARENT_GUARD_STATUS fault1 error10`. Enhanced normal002/session
60586is terminal0and prints five normal status observations with fault0.
All original assertions remain. The earlier001transport results are
historical after that assertion-only probe change, not silently treated as
current-source reruns.

The earlier native-endpoint OOC synthesis002/session35007is now terminal0;
`rocev2-rnic-native-endpoint-synth-002.json` verifies all186original/frozen
inputs at terminal. It uses tested reset-all HLS but predates this parent/app
adapter and excludes actual parent/hard-IP/board. Estimate:135454LUT(83.24%),
192514FF,168BRAM tiles,3DSP. At unchanged4ns, WNS-1.011ns/WHS+0.016ns,
2914setup failures/no hold or pulse failures. Worst path remains external
RAM write address through enabled-byte validation to backend/source state,
16logic levels. This is UNPLACED synthesis timing, not physical signoff.
DRC has9DSP-pipeline warnings and no errors/criticals, with OOC checking
limitations. No route/image is authorized by these estimates.

Area before opt_design is concerning for adding the remaining NIC parent,
not a proven final capacity failure: the synthesis report itself warns final
LUT usage may be lower. A separate frozen STATE-reset HLS candidate has been
started with `build_state_profile.py`/`state_synth.tcl`, session40530under
`rdma/rnic/build/state-reset-hls-ow6h8r42`. It resets static/global and control
state without forcing reset on every pipeline data register. This is a
RESOURCE CANDIDATE, not a demonstrated equivalent fix: inspect generated
constructor/header/FSM reset, rerun all88constructor observations and actual
native/control/legacy READ-WRITE/UR checks, compare resulting physical area/
timing and preserve full board gates before selecting it. No header healing,
reduced clock, protection bypass or unpin-on-reset is allowed. The tested
reset-all candidate and original control-only baseline are retained intact.

## Next integration requirements

Finish source-bound synthesis/route and actual failing-path closure, then
create the separate FULL board build with these parent/app/config copies,
preserved original clocks/setup/hold/pulse/skew/routing/DRC gates and reviewed
conditional CDC. Parent fault must reach actual driver diagnosis/admission/
recovery; no timeout release or reset shortcut. Only after resulting full-
board release gates may a short thermally supervised SRAM/native check run.

The pinned Linux mqnic driver already creates an auxiliary bus device named
`mqnic.app_<application-ID>` (`mqnic_main.c`, application registration). A
future ASN1 driver can attach to that app child rather than replacing the
whole PF's existing network driver. This is a source-based integration path,
not an implemented/runtime-bound RDMA device. Complete actual runtime
MMIO/pins/DMA/ib_device lifecycle, standard WQ/CQ/provider/verbs/per-WR keys,
all required SEND/RECV/immediate/Atomic, bounded concurrency and wire
error/recovery/congestion/network requirements. No sustained/many-connection
qualification or hardware additions are included.
