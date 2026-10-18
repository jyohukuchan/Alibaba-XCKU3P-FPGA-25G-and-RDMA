# SPDX-License-Identifier: BSD-2-Clause-Views
# Pure allowlist test only: no Vivado commands, design or hardware access.
set root [file normalize [file join [file dirname [info script]] ..]]
source [file join $root rdma/scripts/verify_lfc_equivalent.tcl]
set alias_name {core_inst/core_inst/core_pcie_inst/core_inst/iface[1].interface_inst/port[0].port_inst/rx_lfc_req_sync_1_reg_reg}
set checked 0
foreach port {0 1} {
    foreach signal {tx_lfc_req rx_lfc_ack} {
        set original [format {core_inst/mac[%d].eth_mac_inst/mac_ctrl.%s_sync_reg_1_reg} $port $signal]
        if {![mac_lfc_source_allowed $port $signal $original]} {error "Rejected original source"}
        incr checked
        if {[mac_lfc_source_allowed $port $signal $alias_name] != ($port == 1 && $signal eq "tx_lfc_req")} {
            error "Alias admitted for an unaudited port/signal"
        }
        incr checked
        if {[mac_lfc_source_allowed $port $signal unknown_register]} {error "Arbitrary source admitted"}
        incr checked
    }
}
if {[mac_lfc_source_allowed 2 tx_lfc_req $alias_name] ||
    [mac_lfc_source_allowed 1 unknown_signal $alias_name]} {error "Invalid role admitted"}
incr checked 2
puts "LFC source allowlist tests passed: $checked cases; no hardware/Vivado access."
