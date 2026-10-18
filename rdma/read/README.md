# Protected native RoCEv2 READ/WRITE implementation

This directory adds protected RoCEv2 READ reception without editing the
accepted WRITE build003 sources. **The combined version2 image has passed the
full board/conditional CDC review, been SRAM-loaded and verified on hardware.**
Eight finite native CX455A READ cases compare all565515returned bytes and
259061sentinels through actual PCIe BAR accesses; two same-image WRITE cases
verify all12483receiver bytes. All mismatches are zero. This is not a full
verbs provider, sustained-performance result or unconditional CDC safety claim.
See [the native results and use guide](../../docs/ROCEV2_READ_RESULTS.md).

Current components are a fixed READ-capable HLS profile, a256KiB protected
BRAM capture buffer, a finite READ controller, byte-exact protocol vectors,
and actual generated-RTL/controller/RAM integration probes. No host DMA,
inbound WRITE/SEND MR, or READ responder is introduced.

## Offline tests

From the repository root:

```sh
make -C rdma/read check
```

These are wire-oracle, real buffer RTL and controller RTL tests. The buffer
suite verifies host readback, padding/sentinels, descriptor FIFO capacity,
range/QP/flags/keep/TLAST failures and recovery. Controller unit tests use
explicitly modeled completion/capture inputs, not an RNIC.
The suite also covers version2 BAR ownership/locking, READ-only Ethernet
admission, queued old-run response isolation, and build-gate negative controls.
Native-host protocol, provider/thermal supervision and error/CLEAR recovery
models are included as well; these never access the actual devices.

## Combined board-application probes

`tests/probe_rw_write.py`, `tests/probe_rw_read.py` and
`tests/probe_rw_warm.py` instantiate the actual new `mqnic_app_block` and
generated HLS. READ probes compare every byte through AXI-Lite BAR accesses,
including prefilled complements and untouched sentinels. Warm testing reuses
QP/PSNs with different data and holds an old response behind host traffic.
MAC completions and the RNIC remain models, not physical hardware.

`tests/probe_rw_recovery.py` adds a one-byte-short advertised source range,
checks ERR_CONFIG without QP/connection/SQ/network activity, and then performs
app-local CLEAR and a valid multi-READ using the same real app/HLS. All RAM
prefill bytes must survive ERROR/CLEAR; all returned payload/sentinels are
then checked through the BAR model. No post-boot global reset is permitted.

`tests/probe_rw_read_compiled.py` is an additional experimental two-state
backend for the unchanged READ probe/bench; select a private Verilator5.036+
with `AS02_RW_VERILATOR=/absolute/path/to/bin/verilator`. It retains all
clocks, device deadlines, protocol/data assertions and source identities.
System5.020 has reproduced a coroutine-runtime crash even on the known small
case, so the new backend refuses it. A private5.036 build passes the identical
known65-byte x3 case (cross-checked against Icarus) and65536bytes x4: all256KiB
are returned through modeled BAR accesses, with64response packets and PSN
wrap. These two-state results do not replace Icarus, physical timing or
native tests; the earlier Icarus full-buffer timeout remains preserved.

The deployed API is described in
[the version2 BAR specification](../../docs/ROCEV2_RW_API.md).

## Actual HLS probes

The selected HLS directory must contain the complete generated
`solution1/syn/verilog` outputs. Run separately with new report paths:

```sh
python3 rdma/read/tests/probe_read_transport.py \
  --hls-build /path/to/read-hls-build --report /tmp/new-read-transport.json
python3 rdma/read/tests/probe_read_capture.py \
  --hls-build /path/to/read-hls-build --report /tmp/new-read-capture.json
python3 rdma/read/tests/probe_read_control.py \
  --hls-build /path/to/read-hls-build --report /tmp/new-read-control.json
```

The first checks READ request/response semantics at the direct IP boundary.
The second adds real capture RAM and byte-exact RTL-host-port readback.
The third also uses the actual READ controller, including the distinction
between an early HLS completion and a completed RAM write. None accesses
hardware, the network, PCIe, or the final Ethernet application.

## HLS source and physical probes

`hls/synth.tcl` requires a separate checkout at FNS commit
`75c32bae73f5c336b5c46c9de35ae0cb9cb7cc1c`, with both
`../hls/fns-compat.patch` and `hls/fns-read-fixes.patch` applied.
It targets the KU3P at4ns/512bits/8QPs and refuses existing output directories.
Do not patch or overwrite the accepted HLS010 checkout/build.

`hls/check_sources.py` independently reconstructs both patches and records
the input and generated-RTL identities. `rtl/buffer_ooc.tcl` is only an
isolated resource/timing probe and freezes its inputs. Its I/O assumptions
are explicit; passing it is not full-board timing or CDC approval.

`fpga/build_board.sh` is the separate full-board candidate driver. It checks
actual new-app/HLS tests and the unchanged accepted003 native25 gate/clock
hashes before creating a fresh build. Never edit compile/verification inputs
while that build is active. It does not load the isolated OOC constraints,
program SRAM/flash, change fan settings, or modify networking.

The independent native tools are documented in [host/README.md](host/README.md).
They were used for the recorded native tests. Version1/unknown images are
still refused: a matching API alone does not prove physical/source identity.
Every different build needs its own reviewed programming and native evidence.

Build the READ-capable HLS profile first, then run the separate combined flow:

```sh
AS02_HLS_BUILD=/path/to/tested-read-hls-build \
AS02_FNS_SOURCE=/path/to/separate-pinned-read-fns-checkout \
VIVADO_BIN=/path/to/Vivado/2025.2/bin/vivado \
  bash rdma/read/fpga/build_board.sh
```

This is build-only. The original `fpga/build_25g_rocev2.sh` remains WRITE-only.
Do not overwrite the preserved accepted WRITE003 inputs/artifacts.

Current evidence and remaining work are recorded in
[the READ progress log](../../docs/ROCEV2_READ_PROGRESS.md).
