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

### RNIC development snapshot (2026-10-20)

The new [incremental RNIC sources](rdma/rnic/README.md) include protected host
memory/queues, kernel/provider work, SEND/RECV/Immediate, and an Atomic
CAS/FADD responder candidate with immutable packet ownership and actual shared
PSN/MSN readback completions. The latest [generated Atomic MAC RTL composition](results/2026-10-18/rocev2-rnic-atomic-MAC-generated-002.json)
passes four short simulated cases, including drop then forward progress. It
connects actual Ethernet framing, XGMII/FCS, SFD completion and receipt CDC
RTL to automatic packet retirement; positive MAC receipts are not test-generated.
Physical host ordering, PHY pins and the PTP time input remain models.
Atomic requester/full native integration and standard API runtime remain
incomplete; the driver still advertises `IB_ATOMIC_NONE`.

This is a **work-in-progress source snapshot**, separate from the earlier
hardware-tested READ/WRITE images. Its HLS estimate13.568ns misses the original
4ns target; no new FPGA image, installation or hardware claim is published.
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
