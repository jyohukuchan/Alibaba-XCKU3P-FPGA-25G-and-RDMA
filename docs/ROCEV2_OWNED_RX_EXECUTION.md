# Owned RX execution — source/offline candidate (progress052)

The actual FNS `rx_ibh_fsm` and `rx_exh_fsm` now have an opt-in derivative
that retains the exact1024-bit wire/lookup token and588-bit native WQE context
through their state, MSN, timer, retransmission, packet-policy and memory
effects. This is **not selected in the ONE shared/native/board graph** yet.
There is no new FPGA image, hardware test, native admission, CQ publisher or
permission to release WR/MR references.

## Implementation

`rdma/rnic/hls/owned_rx_execution_profile.py` extracts the real functions from
the immutable per-WR-key FNS input and preserves its original license and
positive RX logic. It does not replace them with a packet-response model.

The new local-response contract is:

1. Pair one real wire/lookup token with one already-retained native context.
   The caller must supply the genuine native WR/MR/PD/QP lifetime; an
   `authorized` bit in a synthetic test vector is not runtime authentication.
2. Before the first real RX state request, check full QPN/PSN/epoch/sequence,
   full selected248-bit lease, raw BTH/EXH, descriptor length/PKey, original
   reserved bits, error provenance and native range endpoints. The lookup
   head flag is not required; a late current-head lookup is not substituted.
3. Carry the SAME1612-bit packet/native owner on every IBH/EXH effect and
   require it on state/MSN/read-init responses. A mismatched response enters
   a sticky fault instead of updating a different WR. These typed ports
   cannot be connected directly to the legacy unowned services.
4. Reconstruct EXH and UDP length from the retained packet, not independent
   header/length queues. The actual UDP16 length must fit: BTH/EXH/body length
   plus UDP8/ICRC4 may not wrap. This does not reduce the separate raw parser's
   original full uint16 contract.
5. Preserve the full64-bit VA **before** the original `memCmd` constructor's
   48-bit address/28-bit length/10-bit QP packing. The new memory effect also
   retains full32-bit length and full24-bit QPN. It validates the actual
   generated address against the retained WR/packet offset, never a current
   QP address.

The memory effect distinguishes raw transport `length`, `payload_length` and
`pad_bytes`. Raw length includes wire padding and is **not native DMA
authority**. Checked unpad must consume the padding; the real native executor
must use the payload length and the retained MR/PTE. In particular, a65-byte
READ at the end of the64-bit address space must not turn its68 raw bytes into
a68-byte native write.

All eight syndrome classes are retained. Low five ACK-credit bits are not
treated as errors. Nonpositive classes are emitted on a dedicated owned
control stream **before any state/MSN/timer/retransmission/memory effects**.
This is not yet an implementation of RNR backoff, NAK recovery, congestion or
all retry policies, and must not be called one.

The derivative currently accepts local READ responses and WRITE ACKs plus
their owned control notifications. It does not replace the existing remote
WRITE/READ request path. SEND/RECV/immediate/Atomic/zero-length READ/multi-SGE
remain required and incomplete. Accepting a zero-length WRITE ACK fixture is
not native zero-length WR execution or CQ completion. There is no new4096B
WR limit: the retained32-bit WR length is used with actual4096B PMTU packet
offsets, including `0xffffffff` and24-bit PSN wrap.

## Current bounded evidence

Authoritative current records:

- `results/2026-10-18/rocev2-rnic-owned-rx-execution-C-008.json`
- `results/2026-10-18/rocev2-rnic-owned-rx-execution-derivation-007.json`

The actual derived C++ functions run with assertions and UBSan enabled,
without suppressing sanitizer failures. The full run is approximately0.11s
under the unchanged30s simulation bound; its C++ build takes about26s.

- 12 positive transactions: READ ONLY/FIRST/MIDDLE/LAST, all four padding
  counts, high64-bit VAs, exact2^64 exclusive endpoint, zero/maximum WRITE
  lengths and maximum32-bit segmented READ length.
- 256 distinct AETH values across736 packet vectors: WRITE ACK, READ response
  and READ-request control ACK.672 nonpositive controls cause no positive
  state/MSN/timer/retransmission/memory effects in the tested IBH path.
- 18 rejection cases, including actual FSM faults for mismatched EXH owner,
  state response, MSN owner/address, read-init owner/address, wide-QPN alias
  and control incorrectly entering EXH. Other cases exercise admission/range
  helpers. Every one of the1612 retained owner bits is compared independently.
- 11 derivation/source-invariant tests, including actual licensed function
  extraction, exact ownership ports, all10 actual memory-write sites, fail-
  closed anchors, native64-bit addressing and raw-padding separation.

State/MSN/read-init services, native contexts and references in these tests
are **models**. C streams are not RTL backpressure evidence. No test here
proves persistent epochs, actual host pins/IOMMU, DMA visibility, MAC ownership,
CQ publication, safe reset/abort/flush, native throughput or physical timing.
Prior22 FOUR-STATE wire-RX cases remain evidence for the unchanged wire-RX
component only; they have not tested these new execution interfaces.

Historical C001–006 records and their exact frozen inputs/logs are preserved:
literal-tokenization failure, signed-negative vendor-model sanitizer failures,
PSN-wrap sanitizer failure, JSON numeric-format failure and a relative-report
path failure. They are not promoted to current success. In particular, C006
has `pass_test=true` but terminal status1 because reporting failed after the
test. Its contradictory flag is retained unchanged and is **not an eligible
pass**. The driver now clears `pass_test` on every caught failure. C007 is a
passing prior version before explicit raw/payload-length separation.

## Remaining integration and safety gates

All11 original requirements remain active, as tracked in progress052 and its
authenticated parent051. Next connect the owned requests to the SAME actual
state/MSN/retransmission/pool services in the ONE shared HLS/MR/native
SQ/PTE/PCIe/executor/MAC graph. Do not add duplicate shadow ownership tables
or strip the owner to adapt these streams to a bare-QP interface. Coalesced
ACK processing must return each actual predecessor lease, not blindly update
the old head or release only the selected final lease.

Genuine native admission, standard ib_device/QP/WQ/CQ/provider, remaining
verbs, recovery, exact full-board original-clock timing/CDC and short
thermally supervised native READ/WRITE tests remain incomplete. The prior
3.947ns wire-RX HLS estimate does not qualify this expanded candidate. No HLS
or RTL build was started for these interfaces: disk is about1.3GiB free and
the existing1500MiB HLS/XSIM admission guard was not relaxed.

`local_core_drained` remains0; WR/MR references remain HELD. No fake CQ,
default-success hardware callback, CPU payload copy or empty ib_device is
introduced. BIOS Medium, management networking, fans and other devices were
untouched. No programming/JTAG/flash/module install-load-probe/traffic/reset/
reboot/commit/push or evidence deletion occurred in this turn. Exact
authenticated Codex thread/active-goal reboot restoration remains unproven;
no reboot is currently needed or performed.
