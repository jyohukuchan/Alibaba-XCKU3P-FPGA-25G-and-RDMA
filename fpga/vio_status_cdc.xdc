# SPDX-License-Identifier: BSD-2-Clause-Views
# Copyright (c) 2026 jyohukuchan
# Six independent asynchronous status bits, each with a two-flop synchronizer.
# Do NOT false-path any functional Ethernet data, second-stage, or VIO path.
set vio_meta [get_cells -hier -regexp {.*vio_status_meta_reg_reg\[[0-5]\]}]
set vio_sync [get_cells -hier -regexp {.*vio_status_sync_reg_reg\[[0-5]\]}]
# XDC uses a restricted Tcl parser: checks belong in the implementation helper.
set_property ASYNC_REG TRUE $vio_meta
set_property ASYNC_REG TRUE $vio_sync
set_false_path -to [get_pins -of_objects $vio_meta -filter {REF_PIN_NAME == D}]
