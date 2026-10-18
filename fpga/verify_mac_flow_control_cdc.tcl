# SPDX-License-Identifier: BSD-2-Clause-Views
# Assertions only. The tested shared checker accepts the pinned board's one
# audited equivalent source merge while retaining clock/reset/topology,
# ASYNC_REG and first-D-only exception requirements. This helper's source is
# explicitly captured in the new complete-board compile manifest.
source [file join [file dirname [file normalize [info script]]] ../rdma/scripts/verify_lfc_equivalent.tcl]
proc verify_mac_flow_control_cdc {} {
    verify_mac_lfc_equivalent
}
verify_mac_flow_control_cdc
