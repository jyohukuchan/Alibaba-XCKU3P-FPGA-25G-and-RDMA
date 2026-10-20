# Native control integration candidate (not released)

For the subsequent separately patched real parent/app candidate, actual
parent-proof RTL, offered-frame fault ownership and their explicitly scoped
tests/elaboration, see `ROCEV2_NATIVE_PARENT.md`. No resulting board release
or runtime RDMA success is implied by that later source progress.

`rocev2_native_endpoint.v` now composes the actual AXI crossbar, enforcing
Ethernet configuration CSR and same-port initiator/protected responder.
There is one external24-bit AXI-Lite slave; no raw Ethernet/MR/PTE/QP config
ports escape it. This is NOT yet a full`mqnic_app_block`/parent/native board
profile, registered RDMA device or runtime DMA pass. Never write this new
map to the old running bitstream. Actual board/app identification and kernel
binding still need integration before those writes are allowed.

## Address map

`kernel/native_regs.h` defines these region-relative mappings:

| Native aperture offset | Size | Target |
| --- | --- | --- |
|0x000000 |1MiB | Unchanged version2 READ/WRITE API and capture RAM |
|0x400000 |4KiB | Registered-memory/QP mailbox, ID`0x524e4331` |
|0x401000 |4KiB | Ethernet configuration, ID`0x524e4531` |

The actual Corundum crossbar checks the FULL address before the two new
4KiB slave offsets are narrowed. Unmapped addresses return retained AXI
DECERR/zero, not truncated aliases into the old or new control regions.
The1MiB old region covers its original registers and0x10000capture RAM
without moving either. Unsupported addresses within that original window
retain the original slave's error behavior.

## Ethernet CSR

All words are32-bit little-endian MMIO. Conventional/network-order numeric
MAC and IPv4 values are used, not AXIS lane order. Example local MAC is
`48'h8af3fbb97531`, represented low word`0xfbb97531` and high word`0x8af3`.

| CSR offset | Meaning |
| --- | --- |
|00/04 | ID`0x524e4531`/ABI`0x00010000` |
|08 | ENABLED/SAFE/ERROR/COMMITTED/EXHAUSTED bits0..4 |
|0c | Current nonwrapping route epoch |
|10 | Full-strobe write1 COMMIT |
|14 | Full-strobe write1 CLEAR_ERROR, only at SAFE |
|18 | Last definite parser/validation error code |
|20..34 | Six staging words |
|40..54 | Six active words, read only |

Word order: local MAC low/high, peer MAC low/high, local IPv4, enable0/1.
Staging respects individual byte strobes and may be edited during traffic;
it never changes the active configuration by itself. High/reserved bits are
validated BEFORE narrowing. Enabled addresses must be nonzero unicast MACs
and a nonzero/nonbroadcast/nonmulticast local IPv4. Trusted peer IP/QP/PD/
PSN/key/access checks remain in the independent protected-QP path.

COMMIT copies ALL fields in one clock, increments the epoch without wrap,
and is accepted only at the real wrapper `config_safe` boundary: RUN stopped,
admission paused, no controller transaction/building/tainted state, actual
endpoint/request FIFO/response-MAC drain and actual parent PCIe proof.
No configuration may change underneath an offered/in-flight response or
partially received request. Generation exhaustion refuses further commits;
CLEAR_ERROR never resets the epoch, active configuration, QPs or DMA.

A rejected COMMIT changes no active field. Parser error is sticky and must
be explicitly cleared at SAFE before retry; writes during active traffic
leave the previous route intact. This definite configuration validation
error is NOT a DMA-engine error and does not pretend to cancel accepted
work or unpin pages. Sticky error can come from a different access, so
software must also inspect epoch and ALL active readback. The caller must
serialize this control with the registered-memory mailbox and use actual
new-profile identification before writing. A concurrent bad read prevents
COMMIT and wins over an attempted error clear.

This pinned `axil_reg_if` returns OKAY even for internal register timeout.
AXI response alone is not successful configuration. Unknown/unaligned/
read-only writes and malformed COMMIT/clear requests set sticky error.
No reset, key-reseed, revoke, cancel or page-release operation exists here.

## Evidence and unresolved integration

Ethernet-config002passes6actual CSR/Corundum AXI tests (safe boundary MODEL),
including byte strobes/AW-W independence/R-B stalls, atomic active fields,
unsafe/sticky/partial/high/unaligned denial, enabled/disabled transitions and
finite epoch exhaustion at test limit3(the production limit is0xffffffff).
The previous full101batch006passes on unchanged production sources.

Native-decode005passes3actual native crossbar/Ethernet-CSR tests; the old/
new mailbox/datapath are explicit MODELS. It checks distinct IDs, real
unmapped DECERR and actual Ethernet writes/readback without aliasing.
Full104batch007also passes on those sources; later probe-only diagnostic
edits must be bound separately, never mistaken for another full RTL run.

The first whole-path native-control001/002attempts fail at old-ID read due
to Icarus register-slice combinational-next initialization under a reset
asserted before the first clock. Pinned Corundum testbenches instead clock
an initial unreset phase then assert/release reset. That actual clocked-reset
fixture makes the standalone decode pass; no IP was changed or force used.
New AXI drivers require known1handshakes and known error responses; unknown
simulation values are never silently accepted.

Whole-path native-control003then reaches actual protection/HLS/DMA and fails
at the first WRITE with guard fault35(ERR_UNEXPECTED), before success or
page-release proof. Diagnostics18724/13883are both terminal1and show only
actual HLS TX integrity failure: RX bad0, overflow0, expected command/data
already completed, no duplicate command/data. The actual same-port path
WITHOUT the new native decode fails too under clocked reset; cold-reset
same-port diagnostic32568passes all five operations. No decode corruption
or protection bypass is needed to explain this difference.

The old generated IPv4 block has a once-only C++ static-constructor flag
which is NOT reset. It becomes1before the later pipelined write of fixed
version/IHL0x45and TTL0x64. A reset interrupting that pipeline can permanently
leave header constants zero. Actual HLS TX logs19583(clock-reset failure)
and32568(cold pass) expose those exact raw bytes. Narrow generated-module
characterization003confirms valid cold startup and8bad state observations
out of88across startup/repeated-reset cases. The narrow scalar FIFO is a
MODEL and its precise failing cycle differs from full dataflow latency;
it is not another full-path or native pass. Earlier characterization001/002
had incomplete stimulus/over-specific expected latency and are retained as
failed test-development evidence, not selected release results.

`rdma/rnic/hls/build_reset_profile.py` now freezes a separate exact pinned
READ-capable source snapshot and runs a new HLS profile with synchronous
active-low `config_rtl -reset all`. This resets pipeline data and static
state rather than healing bad headers or suppressing integrity checks.
AMD documents the default control-only versus state/all behavior in
[UG1399 config_rtl](https://docs.amd.com/r/2025.2-English/ug1399-vitis-hls/config_rtl).
The original checkout/generated baseline and old rollback image are never
overwritten. Actual generated reset behavior, full-path/native-control,
old initiator READ/WRITE and physical area/timing must all be rechecked;
the new policy is a candidate, not yet proof of a repair.

Reset-all HLS build001/session6858is now terminal0. All frozen/original
inputs remain unchanged;138generated files have aggregate SHA256
`5fab3e92f5b7d08f03c3b7c0dc1d85dfbbb84faca43a2f062dd5357104ee3a96`.
Generated constructor flag/header/FSM now have actual reset branches.
Narrow IPv4 reset-all001passes all88observations (old baseline had8bad).
HLS estimates32097LUT/84023FF/77BRAM18K and4.043ns; those are estimates,
NOT a4ns physical timing pass. Whole-path native-control004/session14582
is terminal0on this distinct hash and the stricter backend drain. Actual
single-AXI decode/config CSR/mailbox and same-port HLS/page/staging/mux/PCIe
RTL pass21control replies,19frames/13rejections/1ICRCdrop/5ops,130WRITE and
195READ bytes,8read/4write TLPs/2fences,23574cycles. Safe commit reaches
epoch2after STOP; unsafe COMMIT preserves active route/epoch; original
capture RAM and old API ID remain intact. Host RX/TX all sidebands and
MAC completion routing are checked. No raw Ethernet/MR/PTE/QP bypass.
Legacy READ002/session47457and WRITE002/session54921are also terminal0:
65-byte real initiator operations, READ65capture/127sentinel bytes.
Actual-PCIe UR read/fence004sessions4539/46229are terminal0: guard34, no
wire success or page-release proof. Hard-IP/link/root-complex/host/AXI and
MAC completions are still MODELS; no runtime pins/native traffic proof.
Do not substitute old physical results for this new candidate.

This is successful offline whole-path control/RTL evidence, NOT a native
hardware control/DMA/interoperability pass. Do not release/program it based
on simulation or isolated unit tests.

The original controlled-top physical route001is terminal1:4ns WNS-1.174ns,
WHS+0.012ns,7173setup failures, no hold/pulse failures, all108018routable nets
routed. Record`rocev2-rnic-controlled-responder-route-001.json` binds all162
unchanged source inputs at terminal. Worst path is external DMA RAM address
through full enabled-byte guards/predicted pending-after/drain/endpoint quiet
to controller command-valid,20logic levels. It is NOT a physical pass, and
it does not include this larger dual/native wrapper.

The subsequent public backend drain proof is now stricter and no longer
address-dependent: require registered pending counts zero and no current
RAM/status offer. Predicted pending-after remains unchanged for actual DMA
status retirement, as do all byte/tag/range/fence checks. Backend011passes18
methods including four pre-fault-clock unsolicited-offer tests; full108
method batch008/session4644is terminal0and backend012binds the same source.
New physical evidence is still needed; the earlier failed route is historical for this
changed source, not silently promoted to a pass.

New `native_endpoint_synth.tcl` freezes the actual full single-AXI/dual top
and reset-all HLS, preserving4ns and original isolated I/O min/max delays.
Attempt001/session60748failed before synthesis because an optional external
`.dat` list was empty;002/session35007is running after accepting that valid
empty list. Its scope still excludes the actual PCIe parent/hard-IP/native
board; it cannot replace the resulting full-board clock/route/skew/DRC/CDC
gate. Do not edit its frozen production inputs or restart a live CAD process
solely because its log is quiet.

That endpoint synthesis002/session35007has since completed terminal0with
all186inputs unchanged. Unplaced estimate is135454LUT/192514FF/168BRAM
tiles,4ns WNS-1.011ns/WHS+0.016ns/2914setup failures. It is not a route/
native signoff. A separately frozen state-reset HLS candidate is now being
compared for resource use; see `ROCEV2_NATIVE_PARENT.md`. Do not infer that
this new reset policy passes the tested reset-all candidate's gates.

Next: close actual physical timing on the reset-correct native candidate
without weakening data/integrity/lifetime checks; implement full native app/real parent
wiring with19-bit engine tags, resulting full-board clocks/route/skew/DRC/
conditionalCDC gate, short thermal-supervised native checks, real kernel/
runtime pins/DMA/standard verbs/provider and all remaining broad requirements.
