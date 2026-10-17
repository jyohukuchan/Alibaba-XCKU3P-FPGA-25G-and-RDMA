# SPDX-License-Identifier: BSD-2-Clause-Views
# Copyright (c) 2026 jyohukuchan
# Source only after adapting every value to your isolated test setup.
export AS02_CX_NS=fpga25g-cx4
export AS02_FPGA_NS=fpga25g-fpga
export AS02_CX_IF=REPLACE_WITH_PEER_INTERFACE
export AS02_FPGA_IF=REPLACE_WITH_FPGA_INTERFACE
export AS02_CX_BDF=REPLACE_WITH_FULL_PEER_BDF
export AS02_FPGA_BDF=REPLACE_WITH_FULL_FPGA_BDF
export AS02_CX_ADDR=198.18.10.1
export AS02_FPGA_ADDR=198.18.10.2
export AS02_MQNIC_DUMP=/absolute/path/to/corundum/utils/mqnic-dump
export AS02_MQNIC_DEV=/dev/REPLACE_WITH_MQNIC_DEVICE
# Recorded FPGA SFP2 mapping; recheck if changing the design or port.
export AS02_MQNIC_PORT=1
export AS02_TX_CLOCK_CHANNEL=2
export AS02_RX_CLOCK_CHANNEL=3
# Intentionally do not enable AS02_ALLOW_TRAFFIC_TEST here.
