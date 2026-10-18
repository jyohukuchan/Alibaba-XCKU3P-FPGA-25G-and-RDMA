# SPDX-License-Identifier: BSD-2-Clause-Views
# Four existing LFC source-preregister -> two destination-stage chains.
# Stage 1 belongs to the SOURCE clock, stages 2/3 to the destination clock.
# Only the asynchronous first destination D pin is excepted. Never cut the
# second-stage path or any packet-data path, or group whole RX/TX clocks.
set mac_lfc_meta [get_cells -hier -regexp {^core_inst/mac\[[01]\]\.eth_mac_inst/mac_ctrl\.(tx_lfc_req|rx_lfc_ack)_sync_reg_2_reg$}]
set mac_lfc_sync [get_cells -hier -regexp {^core_inst/mac\[[01]\]\.eth_mac_inst/mac_ctrl\.(tx_lfc_req|rx_lfc_ack)_sync_reg_3_reg$}]
set_property ASYNC_REG TRUE $mac_lfc_meta
set_property ASYNC_REG TRUE $mac_lfc_sync
set_false_path -to [get_pins -of_objects $mac_lfc_meta -filter {REF_PIN_NAME == D}]
