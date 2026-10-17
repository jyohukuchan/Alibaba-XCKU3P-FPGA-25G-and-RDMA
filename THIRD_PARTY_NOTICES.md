# Third-party notices and provenance

Original additions in this repository use **BSD-2-Clause-Views**, unless a file
says otherwise. This does not replace any third-party license or copyright.

## Corundum

- Project: <https://github.com/corundum/corundum>
- Pinned revision: `1ca0151b97af85aa5dd306d74b6bcec65904d2ce`
- Authors: Alex Forencich and contributors.
- Relevant copyright: 2019–2023 The Regents of the University of California.
- License: BSD-2-Clause-Views for the reused top-level/configuration code and
  mqnic source; retain all individual file headers. The mqnic kernel module
  also declares `MODULE_LICENSE("Dual BSD/GPL")`; that declaration is retained.
- The NIC, Ethernet MAC/PCS, PCIe DMA, queues and Linux networking integration
  are upstream technology, not new implementations by this project.

`fpga/fpga_as02mc04_25g*.v` and `fpga/config_25g.tcl` are modified descendants
of the Nexus_K3P_S design through the AS02MC04 port below. The driver patch
modifies Corundum's existing files and does not replace their license notices.
The upstream license text is reproduced in `LICENSES/BSD-2-Clause-Views.txt`.

## Existing AS02MC04 Corundum port

- Project: <https://github.com/quake0day/alibaba-as02mc04-corundum>
- Pinned revision: `b00e73a136170604e40341b13b9b1fb9df9304fb`
- Its README describes a verified 10G port and supplies the initial board
  adaptation, source manifest and VIO IP generator used here.
- Its README states that ported RTL/constraints follow Corundum's licensing,
  and original glue/DRP-tool code is MIT. This repository does not relicense
  that submodule. Keep its notices when reusing those files.

## FPGA Ninja / Taxi board constraints

- Project: <https://github.com/fpganinja/taxi>
- Authors: Alex Forencich / FPGA Ninja, LLC.
- The six reference board XDC files mirrored in the pinned AS02MC04 port's
  `docs/` directory explicitly say `SPDX-License-Identifier: MIT` and
  `Copyright (c) 2025-2026 FPGA Ninja, LLC`.
- `fpga/as02mc04.xdc` combines the Corundum port's constraints and this board
  reference. It retains notices for **BSD-2-Clause-Views AND MIT**;
  `LICENSES/MIT.txt` supplies the MIT notice.

This is not a blanket assertion that Taxi is MIT-licensed. Its other RTL can
have different terms, including CERN-OHL-S-2.0. Any future Taxi or RDMA core
must be reviewed separately before integration.

## AMD / Xilinx tools and generated IP

Vivado, its installers, license files, authentication data, generated vendor
IP products, bitstreams and implementation checkpoints are **not included**.
Vivado generates the required IP locally from the Tcl recipes in the pinned
dependencies. Those vendor components remain subject to their own terms.
Tool-generated report excerpts retain their existing copyright notices and
are evidence of this experiment, not a grant of rights to vendor IP.

## Other acknowledgements

- AS02MC04 community research: <https://github.com/dkozel/Alibaba-Cloud-FPGA>
- JTAG SRAM programming: <https://github.com/trabucayre/openFPGALoader>
- Temperature access uses AMD UG580 SYSMON status reads through OpenOCD.

No affiliation with or endorsement by Alibaba, AMD, NVIDIA, Dell or the
upstream projects is implied. Future third-party RDMA code keeps its own
license; this project's default cannot override it.
