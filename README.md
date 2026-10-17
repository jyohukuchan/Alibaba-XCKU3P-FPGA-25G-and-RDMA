# Alibaba XCKU3P FPGA 25G and RDMA

[日本語](README.ja.md)

Experimental **Corundum-based 25GbE NIC port for the Alibaba AS02MC04 / XCKU3P**.
Native 25GbE has been demonstrated against a ConnectX-4 CX455A through a QSA28
and passive SFP28 DAC. **RDMA / RoCEv2 and InfiniBand are not implemented.**
They are future research goals, not capabilities of the current image.

## Status

| Area | Current status |
| --- | --- |
| Hardware | AS02MC04, `xcku3p-ffvb676-1-e`, PCIe Gen3 x8 |
| Ethernet | One connected SFP28 port tested at native 25GbE, FEC off, AN off |
| Jumbo TCP | CX455A → FPGA **24.75 Gbit/s**; FPGA → CX455A **24.54 Gbit/s** |
| ICMP | 100/100 received in each direction; full-MTU DF packets also tested |
| Static timing | Tested ECO image meets setup, hold and pulse-width constraints |
| Clean-RTL build | CDC fix is in RTL; full clean-build hardware validation remains open |
| RDMA / RoCEv2 | Planned; no verbs provider or RDMA engine yet |
| Persistence | SRAM programming only; flash was not modified |

The two throughput measurements were **sequential**, not simultaneous full
duplex, using MTU 9000, four TCP streams and 20 measured seconds per direction.
TCP retransmissions occurred. MTU 1500 has a substantial reverse-direction
performance limitation. See [the complete results and caveats](docs/RESULTS.md).

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
- Measured hardware results, remaining issues and a future RDMA roadmap.

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

## Hardware and safety

Read [hardware and bring-up notes](docs/HARDWARE.md) before attempting programming.
Identify your exact FPGA, adapter and PCIe bridge; never copy another host's
PCIe addresses. Keep a known-good rollback image and adequate direct airflow.

The recorded load test stayed below approximately **55°C** with the test
workstation's fans set high. This is not a thermal guarantee for another host
or design. The optional temperature reader requires an explicitly selected
JTAG adapter serial number. Never use it concurrently with programming.

Do **not** run the dependency port's flash targets or DRP-tuning script
unreviewed: they contain assumptions that do not match every board/host.

## Layout

- `fpga/`: board RTL, XDC, 25G configuration and offline build/ECO Tcl.
- `external/`: pinned upstream Git submodules; not a fork of their ownership.
- `patches/`: mqnic Linux compatibility patch.
- `scripts/`: source checks and opt-in host test/temperature helpers.
- `results/2026-10-17/`: derived measurement JSON and selected report excerpts.
- `docs/`: build, hardware, CDC, results and RDMA roadmap.

An optional [traffic test guide](docs/TESTING.md) explains the explicit opt-in,
device selection and thermal monitoring required for the adapted helper.

## License

Original additions use **BSD-2-Clause-Views**. Preserve upstream file notices
and the MIT board-constraint notices. See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Future RDMA dependencies will
require a separate license review. This is community research without any
vendor affiliation or production-readiness guarantee.
