# Build and reproducibility status

## Two different artifacts

1. **Hardware-tested historical image:** generated from the native-25G design
   with a post-route VIO CDC ECO, followed by physical optimization and guarded
   bit generation. Its SHA-256 is
   `83ab714e93a7279d179d773df2ef3787d752cd466cdbf5f48176f395838c14d3`.
2. **Current clean-RTL source:** includes the equivalent six two-stage VIO
   synchronizers before synthesis. Synthesis and placed-checkpoint inspection
   succeeded during bring-up, but that alternative run was intentionally
   stopped after the ECO image passed hardware testing. Its complete routed
   build and hardware validation are **not yet established**.

Relocating scripts and adding publication checks do not constitute a fresh
hardware validation. This initial publication does not promise bit-identical
reproduction, a passing route on every tool version, or a release-ready image.
The tested bitstream/checkpoints remain local and are not in this repository.

## Requirements

- Git, Bash, Tcl, jq; Linux build tools and matching kernel headers for mqnic.
- AMD Vivado Standard **2025.2**, including Kintex UltraScale+ support.
  Vivado Lab Edition can program/debug but cannot build this design.
- The pinned submodules, initialized with `git submodule update --init --recursive`.
- Sufficient RAM, disk space and time for a full implementation run.

The recorded workstation had 192 GB RAM; this is an environment description,
not a measured minimum. Obtain and authenticate Vivado separately from AMD.
No installer, activation file, token, generated IP, bitstream or checkpoint
is supplied here.

## Build-only flow

```bash
bash scripts/check.sh
VIVADO_BIN=/path/to/Vivado/2025.2/bin/vivado bash fpga/build_25g.sh
```

Output goes into a newly created `fpga/builds/as02mc04-25g-*` directory. The
build consumes the existing AS02MC04 Makefile **as a source manifest only**;
it does not execute that Makefile's programming or flash targets. Board XDC
and 25G/CDC RTL are taken from this repository. Vendor IP is generated locally.

The clean build keeps `xcku3p-ffvb676-1-e`, uses a timing-oriented strategy,
checks the actual PCIe class is `020000`, and verifies four native PHY clocks
at **2.560 ns**. It saves reports/checkpoints even if final timing is rejected.
The final output gate checks:

- six connected two-stage `ASYNC_REG` synchronizers on the 4 ns PCIe clock;
- no negative setup/hold path and a passing complete timing summary;
- all routable nets fully routed and no route errors;
- all 38 expected bus-skew constraints passing;
- no Error or Critical Warning in the current DRC report.

The gate does **not** assert zero CDC findings. Review `cdc.rpt` and
[the inherited crossings](CDC.md). No functional Ethernet false paths,
speed-grade substitutions or frequency reductions are used to manufacture a pass.
No build script programs a device or changes the running network.

## Historical ECO helpers

`fpga/fpga_as02mc04_25g.v` retains the pre-CDC top level for comparison. The
default build uses `fpga_as02mc04_25g_cdc.v`; do not substitute the historical
file into a programming flow without the CDC repair.

For researchers who already possess their own matching routed checkpoint:

```tcl
# In Vivado; only edit an offline checkpoint, never a running target.
# eco_vio_cdc.tcl accepts ROUTED_CHECKPOINT OUTPUT_DIR as argv.
set argv [list /path/to/original_routed.dcp /path/to/new_eco_output]
source /path/to/repository/fpga/eco_vio_cdc.tcl
```

This checks the part, expected original probes and non-debug fanout before
adding 12 FDREs. It uses Vivado's supported `modify_debug_ports` operation;
the protected VIO core is not manually rewritten. The initial ECO can still
fail setup timing. Its routed checkpoint is retained on rejection.

Further experiments use `refine_25g_explore.tcl` in an open routed design,
with `out_dir`, a new `refine_label` and an allowed `refine_directive` set.
The final successful historical sequence included Explore, targeted rerouting
of 11 data/control nets, then AggressiveExplore. Several intermediate
strategies did not improve timing. These helpers are not a one-command replay
of every interactive experiment and do not guarantee convergence from another
placement. Never relax functional constraints to bypass a failure.

After inspecting the resulting reports, `write_verified_25g_eco.tcl` applies
the final output gate. A passing static gate still does not prove hardware
link-up, traffic, temperature safety or compatibility with your card revision.

## Linux mqnic patch

`patches/mqnic-linux-6.17.patch` was used with Linux 6.17.0-1033-oem.
It covers timer helper changes, platform remove return type, string helpers,
ethtool signatures and a missing header. It is not a compatibility guarantee
for every kernel. Test in a separate checkout so the pinned FPGA dependency
can remain untouched:

```bash
git clone https://github.com/corundum/corundum.git /path/to/driver-work
git -C /path/to/driver-work checkout 1ca0151b97af85aa5dd306d74b6bcec65904d2ce
git -C /path/to/driver-work apply /path/to/repository/patches/mqnic-linux-6.17.patch
make -C /path/to/driver-work/modules/mqnic
```

Building does not load the module. Installation/loading requires a separate
review of the target device, kernel and existing mqnic users.
