# SPDX-License-Identifier: BSD-2-Clause-Views
# Selected only by the separate RW build driver. No board-gate changes.
foreach name {AS02_HLS_BUILD AS02_FNS_SOURCE} {
    if {![info exists env($name)] || $env($name) eq ""} {error "Set $name for the verified READ profile"}
}
set rw_root [file normalize [file join [file dirname [info script]] ../../..]]
set roce_hls_build [file normalize $env(AS02_HLS_BUILD)]
set roce_hls_rtl [file join $roce_hls_build solution1/syn/verilog]
set rw_verification_inputs [split [exec python3 [file join $rw_root rdma/read/fpga/check_build.py] \
    --hls-build $roce_hls_build --fns-source [file normalize $env(AS02_FNS_SOURCE)] --list-inputs] \n]
puts "VERIFIED_RW_FUNCTIONAL_SOURCE_PREFLIGHT=1 INPUTS=[llength $rw_verification_inputs]"
set rw_sources {}
foreach name {
    rocev2_write_engine.v rocev2_pattern_source.v rocev2_ethernet_tx.v
    rocev2_ipv4_icrc.v rocev2_tx_padding.v rocev2_integrity_transport.v rocev2_tx_guard.v
} {lappend rw_sources [file join $rw_root rdma/rtl $name]}
foreach name {
    rocev2_read_engine.v rocev2_read_buffer.v rocev2_rw_control.v
    rocev2_rw_ethernet_rx.v rocev2_rw_endpoint.v
} {lappend rw_sources [file join $rw_root rdma/read/rtl $name]}
lappend rw_sources [file join $rw_root rdma/read/fpga/mqnic_app_block.v]
foreach path [concat $rw_sources [glob [file join $roce_hls_rtl *.v]] \
        [list [file join $corundum fpga/lib/eth/rtl/eth_axis_rx.v] \
        [file join $corundum fpga/lib/eth/rtl/eth_axis_tx.v]]] {
    if {![file isfile $path]} {error "Missing RW source: $path"}
    if {[lsearch -exact $sources $path]<0} {lappend sources $path}
}
set roce_memory_init [glob -nocomplain [file join $roce_hls_rtl *.dat]]
