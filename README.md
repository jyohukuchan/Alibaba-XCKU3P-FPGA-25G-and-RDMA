# Alibaba XCKU3P FPGA 25G and RDMA

[日本語](README.ja.md)

Experimental **Corundum-based 25GbE NIC port for the Alibaba AS02MC04 / XCKU3P**.
Native 25GbE and experimental **FPGA RoCEv2 RC READ/WRITE initiators** have been
demonstrated against a ConnectX-4 CX455A through a QSA28 and passive SFP28 DAC.
The combined version2 image reads native CX455A memory into256KiB of protected
FPGA RAM, with every requested byte verified through actual PCIe BAR readback.
A finite 64 MiB WRITE test on the preserved WRITE003 image verified every receiver byte at **24.264 Gbit/s**
payload rate using the FPGA time counter, including initialization/drain.
This is a bounded experimental initiator, not a complete FPGA verbs provider,
inbound SEND/WRITE target, READ responder, native InfiniBand or production-reliability claim.

## Status

| Area | Current status |
| --- | --- |
| Hardware | AS02MC04, `xcku3p-ffvb676-1-e`, PCIe Gen3 x8 |
| Ethernet | One connected SFP28 port tested at native 25GbE, FEC off, AN off |
| Jumbo TCP | CX455A → FPGA **24.75 Gbit/s**; FPGA → CX455A **24.54 Gbit/s** |
| ICMP | 100/100 received in each direction; full-MTU DF packets also tested |
| Static timing | Tested clean RoCE RTL image passes setup/hold, native clocks, routing, 38 bus skews and DRC gates |
| Clean-RTL build | Combined READ/WRITE001 SRAM-loaded; accepted WRITE003 preserved as rollback |
| RDMA / RoCEv2 | Native READ/all-byte BAR capture, segmentation/tails/PSN wrap/error-CLEAR recovery and same-image WRITE regression verified; WRITE003 separately has ACK-loss/watchdog evidence |
| Incremental RNIC source | Offline native queue/MR/DMA/kernel/provider development, SEND/RECV/Immediate and Atomic responder candidates; not a new hardware-qualified image |
| Persistence | SRAM programming only; flash was not modified |

### RNIC development snapshot (2026-10-21)

Publication update: this snapshot includes progress154–156 source and both
successful and failed reports. References below to local/unpushed work or
the previous public HEAD are historical. Native integration and original
timing qualification remain incomplete; this is not a hardware release.
`scripts/check.sh` still rejects the historical TX-padding source/test
identity mismatch; no overall-green claim is made.

Progress156 adds an actual HLS WRITE-packet execution path: protected424
identity -> actual parser/payload EOF/ACK-MSN/SAME PSN-table readback ->
distinct456 receipt. ALL87 C++ modes pass, every65 old mode/summary retained;
both WRITE modes check6 messages/284 full tokens through1MiB with unchanged
complete data/ACK/whole-RQ oracles (new4.642/4.732s, original30s bounds).
Actual owned Atomic service RTL and prior Immediate consumers also pass.
[1116-binding scope audit](results/2026-10-18/rocev2-rnic-segmented-write-owned-diagnostics-001.json).
Exact new RTL generation PASSES497.799s under original4ns/default1.08ns/
8QP/2000 and1500MiB/7200s gates; all old/new424/456/776 ports verify.
The15.571ns estimate still FAILS the original timing requirement.
[Generated-RTL provenance](results/2026-10-18/rocev2-rnic-segmented-write-owned-generated-diagnostics-001.json).
This is NOT native/physical success. Typed424 is never a fake posted620 RQ. Actual backend/
MAC/CQ coupling and safe message teardown still remain. Local/unpushed.

Progress155 adds the checked-frame WRITE frontend: actual IPv4/ICRC ->
parsed full-context MR authorization -> late-RQ -> registered owned replay.
ALL47 component cases pass, max2.077s under original10s/4ns/100000 cycles.
8193-byte WRITE/Immediate replay every input byte unchanged; RQ shortage
retries the same frame without duplicate replay. Bad ICRC never reaches MR;
an owner is required before replay and replay EOF before an execution proof.
Backend/HLS/MAC/CQ consumers remain MODELS; this is not full-native/DMA/
Linux/physical proof. The1MiB case is FIRST+safe cancellation, NOT full1MiB.
Host-only CRC constant memoization matches every448 original vendor mask /
55296 coefficients; hardware sources/gates stay unchanged.
[902-binding scope/failure audit](results/2026-10-18/rocev2-rnic-segmented-write-rx-front-diagnostics-001.json).
New work remains local/unpushed; original timing qualification stays open.

Progress154 connects the segmented-WRITE guard to the actual MR table and
late-notice RQ in46 four-state component cases (max0.122s), plus all62 old
queue modes on the new queue variant (max0.165s). Full-message/per-packet
checks, up to1MiB, distinct remote/RQ owners, late-RNR same-PSN/offset retry
and joint CQ retirement pass. An actual notice/head-VALID combinational
loop was fixed with a non-authorizing posted-head peek; every original
take/protocol/proof/CQ/retirement gate is byte-identical. Backend/HLS/MAC/
CQ and posted-admission producers remain models; this is NOT native or
physical proof. [Scope/failure audit](results/2026-10-18/rocev2-rnic-remote-write-mr-notice-diagnostics-001.json).
This addition is local/unpushed; prior publication/history follows.

This publication includes progress152/153 source and successful/failed
reports, plus the unfinished `rocev2_remote_write_message_guard` leaf.
That leaf passes syntax compilation only: its actual MR/RQ functional
tests and native integration have not run. No new hardware or timing
qualification is claimed. Uncommitted/unpushed descriptions below are
historical states, superseded by this explicit publication.

The new [incremental RNIC sources](rdma/rnic/README.md) include protected host
memory/queues, kernel/provider work, SEND/RECV/Immediate and Atomic candidates.
The [retained-source dispatcher native regression](results/2026-10-18/rocev2-rnic-segmented-executor-native-full-001.json)
passes all27 simulated cases, each under25s, including ordinary WRITE/SEND,
zero-length services, RQ/RNR, requester Atomic and permission checks. It uses
actual generated HLS, MR/PTE/DMA and XGMII/FCS/SFD/CDC/MAC/CQ RTL for the new
ordinary source cases; physical host/root/peer/PHY/PTP endpoints remain
models, and ordinary READ/SEND_IMM retain prior MAC-receipt models.

The [matched large-wire native regression](results/2026-10-18/rocev2-rnic-segmented-profile-native-full-001.json)
now passes all29 simulated cases, including8193-byte WRITE/SEND and all27
prior cases, each in18.05..26.61s. Its8191/13/15/31 RNC/SQC/RQC/CQC tuple matches
the private large-WR kernel cohort. The new cases exercise actual generated
HLS, scattered-page MR/PTE/DMA, board-faithful TX FIFO/CDC, XGMII/FCS/SFD/MAC
and one final whole-WR CQ, with independent wire/data/owner checks. Physical
host/root/peer/PHY/PTP endpoints remain models. Earlier failed runs and their
FIFO, PCIe3DW-model and pre-padded-LAST diagnoses are retained separately.
Up to1MiB remains HLS/component evidence, not this full-native runtime test.

A private RNC8191/CQC31/profile4 Linux source cohort builds against
the running kernel headers. Its [actual C posting/MR/SQ/CQ tests](results/2026-10-18/rocev2-rnic-segmented-kernel-post-003.json)
pass65 ASan/UBSan cases, including8193-byte/1MiB WRITE/SEND and all47 prior
cases, under explicit Linux/MMIO/DMA/completion models. This is not execution
inside Linux. A separate [actual kernel/native SQ-CQ integration test](results/2026-10-18/rocev2-rnic-segmented-kernel-native-cq-001.json)
passes65 cases:13 unedited native snapshot pairs plus52 explicit corrupt-copy
controls. Real C posting/coherent128-byte SQ/full-owner CQ/WC/ref retirement
execute under Linux/MMIO/DMA models. Native and C page tables remain separate;
this is not live kernel/RTL coupling. A private standard-provider cohort also
passes all five firmware profiles through real libibverbs serialization,
but actual Linux/provider/API/physical runtime, large receive/READ/Immediate
and multi-SGE remain incomplete. No module is installed/loaded; defaults and
`IB_ATOMIC_NONE` are unchanged.

A new private protected segmented READ-response RX candidate now passes
[all17 methods/60 component cases](results/2026-10-18/rocev2-rnic-segmented-read-response-002.json),
including59 four-state cases and an explicit1MiB/256-packet two-state case.
The first failed suite and its diagnostic evidence are preserved separately.
A separate true segmented READ HLS candidate now passes its
[actual C++ consumer tests](results/2026-10-18/rocev2-rnic-segmented-read-hls-003.json):
four whole READs4097 bytes..1MiB,278 response packets, stored replays, prior
regressions and nine negative cases. Its first failed run is preserved; the
correction distinguishes validated nonterminal READ timer progress from final
completion. Actual owned Atomic RTL-service/Immediate compatibility also
passes. [New HLS generation](results/2026-10-18/rocev2-rnic-segmented-read-generated-hls-001.json)
and exact generated-RTL elaboration pass, but its13.885ns estimate fails the
original4ns/default1.08ns conditions; no generated-RTL runtime pass is claimed.
The previous/default8191/31 profile keeps READ4096. A separately named
experimental16383/63 candidate below now admits larger READs, but actual
end-to-end native DMA/whole-WR completion and kernel/provider support for
that profile remain unverified. See
[exact evidence and limits](docs/ROCEV2_ATOMIC.md).

A new retained-owner READ memory controller passes35 four-state component
cases, including1MiB/256 fragments. A separate
[actual HLS C++ output-snapshot integration test](results/2026-10-18/rocev2-rnic-segmented-read-dma-hls-001.json)
passes four whole READs/278 fragments through the real origin router, bounded
unpad and executor RTL. Placement, backend visibility/status and CQ are models;
this is not live HLS/native DMA, generated-RTL runtime or physical proof.
The new READ memory selection is now wired into a separate complete native
hierarchy with the actual new HLS and common MR/PTE/physical-nonce/backend
ports. New/old route tests pass17 cases and whole-graph elaboration passes.
This is still compile-only native evidence; that earlier memory-only cohort
keeps READ4096 pending the separate profile/runtime work below.

The experimental expected-remote-MSN tracker now passes
[12 component cases](results/2026-10-18/rocev2-rnic-expected-remote-msn-007.json)
using genuine SQC cookie/epoch/PD lookups. Two genuinely allocated QPs retain
independent MSN history without route reconfiguration. Accepted-QP/SQC/MSN
wiring also passes [complete-native elaboration](results/2026-10-18/rocev2-rnic-expected-remote-msn-native-elaboration-002.json).
The component's route/WR/TX/CQ endpoints remain models; native evidence is
compile-only, not wire/MSN interoperability. Fresh remote RC peers are required;
its original8191/31 cohort keeps READ4096 and failed evidence is preserved.

The separate READ RX/MSN/memory/whole-WR lifetime graph is now connected and
passes [complete-native elaboration](results/2026-10-18/rocev2-rnic-segmented-read-lifetime-native-elaboration-001.json).
[Lifetime component tests](results/2026-10-18/rocev2-rnic-segmented-read-lifetime-002.json)
pass29 cases, including19 READ controls and all10 original WRITE/SEND cases.
One READ request retains its replay cache through FIRST/MIDDLE and joins
LAST, final HLS ACK/whole receipt, aggregate memory and actual MAC ownership
before CQ. RX/HLS/memory/CQ/MAC-pin endpoints are modeled in these component
tests;1MiB READ means256 modeled response events, not actual native payload
runtime. That original8191/31 cohort keeps READ4096; defaults are unchanged.

A distinct experimental RNC16383/CQC63 source profile now opens READ admission
up to1MiB through checked SQ/MR/HLS-SQ/CQ gates. Its actual C128 codec passes20
methods; real local-MR admission26 cases, HLS-SQ staging21 cases and register/
CQ27 cases pass. [Complete-native elaboration](results/2026-10-18/rocev2-rnic-segmented-read-profile-native-elaboration-001.json)
passes with the exact RX/MSN/memory/lifetime/HLS graph. These are component
runtime plus native COMPILE results, not execution of a genuinely fetched
large READ through native RX/DMA/host visibility/CQ. No installed/default
driver/provider selects this profile.

The [first full-runtime attempt](results/2026-10-18/rocev2-rnic-segmented-read-native-full-002.json)
now compiles the actual new graph successfully, but **fails during QP setup,
before a fetched READ/data transfer** (`main native RNIC fault 00`). The new
runner plans one8193-byte READ plus all29 previous cases; only the first READ
case was attempted, and none passed in this batch. The failure, exact hashes
and [audit](results/2026-10-18/rocev2-rnic-segmented-read-native-diagnostics-002.json)
are retained. At that historical checkpoint the root cause was unconfirmed;
the route correction and subsequent native success are recorded below.

A separate route-observer correction now passes six short real-controller
cases: the old fault is reproduced, while the corrected observer retains the
peer/IP route across a PSN-only QP_TX command. Invalid commands and stalled
acceptance remain checked. [Complete-native elaboration](results/2026-10-18/rocev2-rnic-segmented-read-route-native-elaboration-001.json)
passes with only two observer lines changed; all original gates remain.
The [fresh corrected native build](results/2026-10-18/rocev2-rnic-segmented-read-route-native-full-001.json)
passes compilation and reaches genuine SQ fetch, actual READ request emission
and the first4096-byte paged-write/fence descriptors, but times out at the
unchanged30s limit. A separate same-binary diagnostic reaches cycle24000 with
no fault,33 write TLPs and no second fragment's physical write descriptor: completion and absence
of a functional stall are NOT proved. The later optimized -O1 run reaches the
original cycle deadline in9.436s and confirms a real stall: first fragment
completes, but the second waits for2176 payload bytes while the next command
is blocked. Neither historical batch proves full READ/CQ or the old29 cases;
the subsequent command-queue batch below does.

A new owner-checked two-command metadata queue breaks that
command/data dependency without changing serial DMA/status/fence/CQ ownership.
[Component tests](results/2026-10-18/rocev2-rnic-segmented-read-command-queue-001.json)
pass23 cases, retaining all17 prior cases, with explicitly modeled HLS/backend/
CQ endpoints. The [fresh complete-native run](results/2026-10-18/rocev2-rnic-segmented-read-command-queue-native-full-001.json)
now PASSES all30 cases: new8193-byte READ plus all29 old cases. New READ uses
actual generated HLS/SQ/MR/PTE/protected RX/MSN/DMA/shared nonce/status/fence/
board-MAC/FCS/SFD/CDC/CQ RTL and passes in6.078s, including every host byte and
one whole-owner CQ. All cases take4.175..6.279s under the unchanged30s limit;
[audit](results/2026-10-18/rocev2-rnic-segmented-read-command-queue-native-diagnostics-001.json)
verifies1665 bindings. Physical host/root/peer/PHY/PTP remain MODELS; old ordinary
READ/Immediate cases retain their old MAC-pin completion models. This is not
Linux/physical/timing qualification or a native1MiB READ test. Separate matched
16383/63 kernel/provider support now has a separate source cohort below;
old/default8191/31 keeps READ4096.

New explicit software profile5 binds exact16383/63/SQC13/RQC15/stride128.
Its actual kernel source builds against running headers; actual WR/SQ/MR/CQ
C passes90 modeled-boundary cases (all65 old retained), and70 cases consume
unedited native SQ/CQ captures, including8193 READ, with exact posted bytes/
MR retirement. The actual installed libibverbs/private provider passes all
six identities and4097/8193/1MiB READ chains under fake-fd/WC models.
[Software audit](results/2026-10-18/rocev2-rnic-segmented-read-software-diagnostics-001.json)
verifies626 new successful bindings and preserves failed fixtures/preimages.
This is not installed/live Linux/RTL or physical proof. Single SGE and4KiB
Immediate/RQ remain; native1MiB READ and original timing remain unqualified.

A further separate RNC32767/CQC127 candidate now PASSES actual8193-byte
segmented SEND/WRITE Immediate and ALL30 prior native cases:32 total, each
4.125..6.430s. Immediate appears only on LAST; real SQ/MR/PTE/generated HLS/
DMA/shared nonce/status/board-MAC-FCS-SFD-CDC/CQ and all source/sentinel bytes
are checked. Physical host/root/peer/PHY/PTP remain MODELS; native1MiB is not
tested. Separate matched source-only kernel/profile6/provider builds and
passes134 standard-C callback cases,80 untouched native-SQ/CQ snapshot cases
and all7 provider identities with modeled Linux/syscall boundaries.
[Current audit and failures](results/2026-10-18/rocev2-rnic-segmented-immediate-native-software-diagnostics-001.json)
verify2586 fresh bindings. This is not live Linux/RTL or physical/timing
qualification. Source/C++/API models allow1MiB; incoming RQ stays4KiB/single
SGE, old/default/profile5 stay unchanged. The earlier
[source/component audit](results/2026-10-18/rocev2-rnic-segmented-immediate-diagnostics-001.json)
is retained separately, not relabeled as a native-runtime result.

This is a **work-in-progress source snapshot**, separate from the earlier
hardware-tested READ/WRITE images. Its latest HLS estimate13.885ns misses the original
4ns target; no new FPGA image, installation or hardware claim is published.

A separate incoming SEND/Immediate HLS candidate now passes44 C++ modes
(all21 previous retained), testing full payloads through1MiB. Actual message
RQ/ACK/CQC component coupling also passes8193-byte/3-packet ACK lifetimes and
one CQ publication/full AXI snapshot; queue units pass48 cases. HLS/MR/DMA/
PHY/host boundaries remain models in those RTL component executions. The
SAME new full HLS synthesis is still running; the new native source graph's
syntax check ignores missing leaves and is NOT complete native elaboration.
[Evidence and remaining work](results/2026-10-18/rocev2-rnic-receive-message-native-components-diagnostics-001.json).
Existing native/software profile6 incoming RQ4096/defaults are unchanged;
actual new generated-HLS/MR/PTE/DMA/native/standard API/timing work remains.

Progress149 subsequently generates actual source007 RTL in 399.510 seconds
and passes complete application-native elaboration with every leaf present,
one shared MR/PTE/HLS/message-RQ and the actual 776-bit whole output. Four
additional actual PCIe-DMA-to-MR-to-RQ cases pass (maximum 0.367 seconds),
with no descriptor/status/RAM/MR substitute. Physical host/root/link/config
and the error sink remain models; no received-payload/HLS/MAC/CQ runtime is
inferred from descriptor posting. The HLS estimate is 15.571 ns: original
4 ns timing is NOT met. A fresh new-graph build for all 32 old native cases
is running; new large incoming native transfer and matched software remain
unproved. [Generated/native-connection audit](results/2026-10-18/rocev2-rnic-segmented-receive-generated-diagnostics-001.json).

Progress150 completes all 32 exact old native cases on that new graph
(4.476..6.831 seconds each, fresh compile642.135s). The separate original
source004 HLS run times out at its unchanged7200s limit; its child processes
subsequently exit naturally. Failures/logs stay intact. New whole-native
8193-byte incoming SEND/Immediate tests on one8194-byte RQ, with genuine
three packet/fence/ACK-MAC lives and one whole CQ, are now building003.
Its actual full bench elaborates without width/missing-leaf waivers, but
no new incoming payload/runtime pass is claimed yet. Failed001 anchor and
002 observer-port binding attempts are retained with exact preimages.
[Native old32/timeout/failure audit](results/2026-10-18/rocev2-rnic-segmented-receive-native-regressions-diagnostics-001.json).

Publication after progress151 records that full-native003 compiled but
FAILED at the original second-packet deadline. Read-only inspection of the
unchanged DUT objects identified the raw reference entrance blocking a held
receive group's continuation. A separate derived fix changes only that
entrance; pending ownership, MR, HLS, MAC and whole-CQ checks stay intact.
[Reference gate tests](results/2026-10-18/rocev2-rnic-receive-continuation-gate-001.json)
pass nine current cases plus the expected old-gate negative control.
[Complete native elaboration002](results/2026-10-18/rocev2-rnic-segmented-receive-native-elaboration-002.json)
passes with actual generated HLS and no missing-leaf/width waivers.
The corrected full-native34-case run has NOT started; new incoming8193
runtime, matched software, original4ns timing and physical proof remain
unverified. No hardware or installed/default profile is changed. Earlier
progress149/150 build-state descriptions above are historical snapshots.

Progress152 now PASSES all34 fresh corrected-graph native cases, including
8193-byte incoming SEND/Immediate on one8194-byte RQ, three real packet/MR/
DMA/fence/ACK-MAC releases and exactly one whole HLS/CQ/host ACK. Compile
798.354s; new cases8.534/8.584s, original1200s/30s limits unchanged. Separate
exact65535/255/13/31/profile7 kernel source builds against running headers
and passes170 actual C callback model cases (all134 old retained),2442 IO
identity/geometry cases and90 unedited native SQ/RQ/CQ snapshot cases. The
private provider passes all8 identities and new standard RECV marshalling.
[Native/software scope audit](results/2026-10-18/rocev2-rnic-segmented-receive-native-software-diagnostics-001.json).
Linux/MMIO/pins/DMA/completion boundaries are models; snapshots are separate
executions, not live Linux/RTL or matching physical-page-table coupling.
Default/installed profile6 incoming4096 and IB_ATOMIC_NONE are unchanged.
Native1MiB, multi-SGE, segmented WRITE Immediate, recovery/interop and original
4ns full-board timing/physical work remain open. Source004 timeout, full003
failure and the first callback-vector error stay recorded with exact preimages.
This progress152 addition is local/uncommitted, with no automatic push.

Progress153 adds a separate segmented incoming WRITE/WRITE Immediate HLS
source and late-notification RQ component. Actual C++ passes65 modes (all44
old retained), including6 messages/284 packets per new operation through1MiB,
independent complete data/ACK oracles, LAST-only MSN, PSN wrap, distinct RETH
target and late RQ capacity0/1/17/etc. The RQ component passes62 cases (all48
old retained), keeping separate320-bit remote and620-bit posted identities,
whole bytes rather than LAST bytes/capacity, and remote-retirement backpressure.
[Scope/failure audit](results/2026-10-18/rocev2-rnic-segmented-write-receive-diagnostics-001.json).
Peer/memory/posted-RQ boundaries and the component's trusted remote-MR/HLS/
MAC/visibility producers are MODELS. These separate tests are NOT connected
native proof; the new source has no generated RTL, native MR/DMA/CQ coupling,
matched software or physical qualification. All old/default sources and
original timing gates remain. No automatic commit/push.

The current source checkpoint also adds a 1 MiB posted-RECV codec and a
correctly typed `ib_recv_wr` adapter: 37 codec methods, 78 admission/staging
cases, four actual MR-to-message-RQ handoff cases, and a real-kernel-header
adapter build pass. These are not installed callbacks or a matched new
driver/provider profile. A separate balanced KEEP checker passes 103,665
finite old/new behavioral comparisons, all 44 C++ modes and unchanged
Atomic/Immediate compatibility. Candidate 005 is rejected for narrowing
short-beat acceptance; candidate 006 compile failures are retained, not
relabeled by candidate 007's success. No new synthesis/timing benefit is
claimed for 007. Original source004 synthesis was still active at
2026-10-21 09:16 UTC; it was not stopped or restarted for publication.
[Publication integrity and scope](results/2026-10-18/rocev2-rnic-segmented-receive-publication-diagnostics-001.json).
The recorded-data part of `bash scripts/check.sh` currently detects a stale
historical `rocev2_tx_padding.v` SHA after adding44-byte SEND support. The old
evidence and strict check are retained, not relabeled or waived. See
[current scope and limitations](docs/ROCEV2_RNIC_PROGRESS.md).
The focused Atomic RTL suite passes21 methods (73 internal simulations). A broader RNIC suite is not
green: native MAC-lifetime and QP-TX cases reported errors/failure, and the
remaining full-suite run was stopped. This snapshot is not a passing release
or a claim that every older test matches the current development profile.

The two throughput measurements were **sequential**, not simultaneous full
duplex, using MTU 9000, four TCP streams and 20 measured seconds per direction.
TCP retransmissions occurred. MTU 1500 has a substantial reverse-direction
performance limitation. See [the complete results and caveats](docs/RESULTS.md).

The new RoCE measurements use a different clean-RTL image and finite tests,
not the historical TCP/ECO image. See [native WRITE evidence](results/2026-10-18/rocev2-native-003.json)
and [current milestones](docs/ROCEV2_PROGRESS.md). No software RXE endpoint
stands in for the FPGA in these native tests. Do not treat a single short
measurement as sustained-load qualification. Separate finite
[ACK-loss/watchdog/recovery evidence](results/2026-10-18/rocev2-native-retry-recovery-003.json)
covers controlled faults, not arbitrary network failures or production reliability.

The newer combined READ/WRITE image has its own [native evidence](results/2026-10-18/rocev2-rw-native-001.json)
and [READ results/use guide](docs/ROCEV2_READ_RESULTS.md):8READ cases, including
65536bytes x4 (all256KiB),4096operations and error/CLEAR recovery, plus2WRITE
regressions, all-byte zero mismatches. These are finite functional tests,
not a new throughput measurement or a repeat of WRITE003's ACK-loss tests.

## What this project adds

- Native 25G configuration for this board's fixed **156.25 MHz** reference,
  a 25.78125 Gbaud GTY link and fractional QPLL feedback of 82.5.
- A six-bit, independent two-stage synchronization fix for PHY-status signals
  entering VIO's PCIe clock domain. Functional Ethernet paths are not waived.
- Vivado 2025.2 PCIe class-code configuration and implementation-flow fixes.
- Timing-oriented build recipes, guarded output gates, and historical ECO
  helpers used during bring-up.
- A Linux 6.17 mqnic compatibility patch, explicit test configuration and
  read-only JTAG temperature diagnostics.
- Scoped RoCEv2 READ/WRITE endpoints, protected capture RAM, packet-integrity/control/guard integration,
  measured hardware results and an explicit remaining-work roadmap.

The Ethernet MAC/PCS, PCIe DMA and NIC architecture remain **Corundum**.
The initial board adaptation comes from **quake0day's AS02MC04 port**, with
board constraints referenced from **FPGA Ninja / Taxi**. This is a board port
and engineering validation, not a new Ethernet protocol implementation.

## Get the source and check it

```bash
git clone --recurse-submodules https://github.com/jyohukuchan/Alibaba-XCKU3P-FPGA-25G-and-RDMA.git
cd Alibaba-XCKU3P-FPGA-25G-and-RDMA
bash scripts/check.sh
```

Dependencies are pinned to the revisions in [third-party notices](THIRD_PARTY_NOTICES.md).
Checks need Git, Bash, Tcl and jq, but do not need Vivado or access hardware.

To build, install Vivado **Standard 2025.2** with Kintex UltraScale+ device
support (Lab Edition cannot synthesize), then run:

```bash
VIVADO_BIN=/path/to/Vivado/2025.2/bin/vivado bash fpga/build_25g.sh
```

This is **build-only**. It does not load a driver, program JTAG, write flash,
change networking or reset PCIe. See [build status and instructions](docs/BUILD.md)
before relying on a new image. Prebuilt vendor-generated binaries are not
distributed in this initial source publication.
The RoCE-enabled build additionally needs the pinned generated HLS profile;
see [RoCE build and test instructions](rdma/README.md).
The separate combined READ/WRITE build is documented in [rdma/read](rdma/read/README.md);
the original default RoCE build remains the WRITE-only profile.

## Hardware and safety

Read [hardware and bring-up notes](docs/HARDWARE.md) before attempting programming.
Identify your exact FPGA, adapter and PCIe bridge; never copy another host's
PCIe addresses. Keep a known-good rollback image and adequate direct airflow.

The recorded load test stayed below approximately **55°C** with the test
workstation's fans set high. This is not a thermal guarantee for another host
or design. The optional temperature reader requires an explicitly selected
JTAG adapter serial number. Never use it concurrently with programming.
The later finite native 64 MiB RoCE case, with BIOS Medium retained, sampled
**60.32..60.62°C**; it is not a sustained-traffic thermal test.

Do **not** run the dependency port's flash targets or DRP-tuning script
unreviewed: they contain assumptions that do not match every board/host.

## Layout

- `fpga/`: board RTL, XDC, 25G configuration and offline build/ECO Tcl.
- `external/`: pinned upstream Git submodules; not a fork of their ownership.
- `patches/`: mqnic Linux compatibility patch.
- `scripts/`: source checks and opt-in host test/temperature helpers.
- `rdma/`: experimental endpoint/HLS integration, native peer/controller and tests.
- `results/YYYY-MM-DD/`: scoped measurement/provenance JSON and report excerpts.
- `docs/`: build, hardware, CDC, results and RDMA roadmap.

An optional [traffic test guide](docs/TESTING.md) explains the explicit opt-in,
device selection and thermal monitoring required for the adapted helper.

## License

Original additions use **BSD-2-Clause-Views**. Preserve upstream file notices
and the MIT board-constraint notices. See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), including the selected HLS
transport's own license. Future dependencies require their own review. This is community research without any
vendor affiliation or production-readiness guarantee.
