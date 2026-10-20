# Same-port initiator/responder integration (offline)

This is source and short RTL-simulation progress, NOT a native board profile,
registered RDMA device, runtime host-page DMA or physical timing pass. The
running version2 READ/WRITE bitstream and every rollback source are unchanged.

`rdma/rnic/rtl/rocev2_dual_ethernet_endpoint.v` composes the unchanged original
`rocev2_rw_endpoint` with the actual controlled/paged protected responder.
The new request router is placed BEFORE the legacy ingress so incoming
requests are not discarded by that ingress's deliberate initiator-only policy.
Both paths use the same128-bit/250MHz Ethernet interface. No recabling or
second physical port is substituted for the requested same-port integration.

## Ownership and routing

`rocev2_responder_ethernet_rx.v` buffers complete Ethernet frames and steers
plain IPv4/UDP4791 RC request opcodes addressed to the configured local MAC/IP
from the configured peer MAC. Trusted peer IP/QP/PD/full-key/PSN/range/access
authority remains in the protected responder, after actual packet integrity.
ACK/READ/Atomic responses and ordinary Ethernet retain every RX sideband bit
and pass into the unchanged initiator/host path. This classifier is NOT an
ICRC/checksum checker or permission substitute. Unsupported requests still
produce local rejections rather than complete wire NAK/RNR behavior.

Metadata/epoch ownership, dense keep/oversize rules, frame FIFO and actual
128-bit Ethernet strip logic derive from the original ingress without editing
it. Output route is held for an already-started frame; no mid-frame valid
withdrawal. RX quiescence includes partial input, queued metadata/data and the
stripper/output pipeline. Privileged Ethernet configuration may change ONLY
at the wrapper's `config_safe` boundary: stopped admission/RUN, protected
quiescence, real parent drain, request-router drain and response MAC drain.

Separate AXI slave ports expose the unchanged version2 API and new responder
mailbox. This bare wrapper has no nonaliasing BAR decoder/enforcing config
CSR owner. A successor actual single-AXI wrapper now implements both; see
`ROCEV2_NATIVE_CONTROL.md` for its still-failing whole-path reset test and
unresolved native board integration. The bare-wrapper simulation drives stable privileged
MAC/IP/epoch inputs; these are not safe to expose as arbitrary live controls.
Do not release this wrapper as a programmable native board image yet.

MAC completion tags are unambiguous:

| Tag class (16-bit native tag) | Consumer |
| --- | --- |
| MSB1, including host tags with bit14set | Original host completion path; full tag/timestamp retained |
|0 | Original initiator TX guard |
|0x4000 | New responder TX guard only |

The outer frame arbiter never interleaves packets. Reserved-class/tag
collisions latch a fault, block first-beat request admission and withhold
release proof; an already-started request still drains. Invalid completion
tags are not redirected into another role. Error-injection coverage of every
new MAC routing fault path remains required; normal-role tests are not that
proof.

The responder's actual original TX guard retains SFD completion ownership and
its conservative1024-cycle wire-tail interval; accepting the final IP beat
does NOT alone prove MAC/wire drain. STOP/invalidation cannot halt the response
to an already-admitted request. Parent drain supplied to the controller is
the actual external PCIe proof AND response-TX drain with no outer fault.
The original initiator's private per-run core reset never resets this state,
the new responder, registered mappings or shared Ethernet routing. Only the
coordinated whole-NIC reset applies to the composition; reset is not revocation.

## Current finite evidence

`rocev2-rnic-dual-ethernet-001.json`/session69023is terminal0. Actual AXI/
controller/HLS/protection/page table/staging and both native-shaped DMA muxes/
generic PCIe engine are included.19request frames yield13local rejections,
1ICRC drop and5successful operations;20actual control replies include active-
WRITE invalidation, stale-key denial and fresh-key reuse. All130WRITE and
195network READ bytes and all five complete Ethernet responses are checked.
One ordinary64-byte frame passes host RX and host TX with all97RX sideband
bits/full TX tag unchanged;5responder MAC completions and1host completion go
to the correct roles. Host tag0x9234 deliberately also has bit14set.
Actual request/response checksums and ICRCs, complete host guards, actual
generic TLPs and the prior delayed TX-sequence test remain checked.

The old initiator is not merely instantiated:

- `rocev2-rnic-dual-legacy-write-001.json`/session28507, terminal0: one original
  65-byte WRITE, every emitted header/payload/checksum/ICRC and peer ACK checked;
  actual original version2 control/transport/TX-drain behavior,6125cycles.
- `rocev2-rnic-dual-legacy-read-001.json`/session34679, terminal0: one original
  65-byte READ request/response and protected capture; every payload byte plus
  127untouched sentinel bytes read through the actual version2 BAR RTL,
  6649cycles. Early completion waits for actual capture commit.

Both legacy cases include the actual new router, protected responder and
native-shape mux/generic PCIe engine. The responder has no published MR/QP
and MUST emit zero descriptors/TLPs; no fabricated successful DMA response
is supplied. Roles are exercised in separate finite cases, not a simultaneous
concurrency/large-connection test.

All MAC completions, the remote RNIC, AXI host, stable privileged Ethernet
configuration and PCIe hard-IP/link/root-complex/host memory remain MODELS.
No module is loaded, real page pinned, FPGA programmed or native traffic sent.
These selected baseline-HLS passes use cold startup. A later clocked-reset
case exposes an actual HLS static-constructor/header defect; do not claim
warm-reset correctness from the earlier cold-start results. A separate
source-frozen resettable HLS candidate is being synthesized, not yet released.

```sh
python3 rdma/rnic/tests/probe_dual_ethernet.py \
  --hls-build /path/to/tested-read-hls-build --report /path/to/fresh-report.json
python3 rdma/rnic/tests/probe_dual_legacy.py --operation write \
  --hls-build /path/to/tested-read-hls-build --report /path/to/fresh-write.json
python3 rdma/rnic/tests/probe_dual_legacy.py --operation read \
  --hls-build /path/to/tested-read-hls-build --report /path/to/fresh-read.json
```

Next: enforcing/nonaliasing control and Ethernet-configuration ownership,
actual native `mqnic_app_block`/parent wiring with19-bit engine tags preserving
16application bits, resulting full-board clocks/setup/hold/skew/routing/DRC/
conditionalCDC gate, then short thermally supervised native checks. Real bus/
kernel ib_device/runtime pins/DMA and standard WQ/CQ/provider/verbs, persistent
key epochs and proven error/reset/hot-unplug cleanup remain part of the full
goal. This same-port simulation is not a smaller replacement for that goal.
