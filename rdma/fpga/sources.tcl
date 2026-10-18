# SPDX-License-Identifier: BSD-2-Clause-Views
# Sourced only by the explicit native25 RoCE variant, before Vivado commands.
if {![info exists env(AS02_HLS_BUILD)] || $env(AS02_HLS_BUILD) eq ""} {
    error "RoCE build requires AS02_HLS_BUILD from the verified HLS probe"
}
set roce_root [file normalize [file join [file dirname [info script]] ../..]]
set roce_hls_build [file normalize $env(AS02_HLS_BUILD)]
puts [exec python3 [file join $roce_root rdma/hls/probe/check_build.py] --hls-build $roce_hls_build]
set roce_hls_rtl [file join $roce_hls_build solution1/syn/verilog]
foreach path [concat [glob [file join $roce_root rdma/rtl/*.v]] \
        [glob [file join $roce_hls_rtl *.v]] \
        [list [file join $roce_root rdma/fpga/mqnic_app_block.v] \
        [file join $corundum fpga/lib/eth/rtl/eth_axis_rx.v] \
        [file join $corundum fpga/lib/eth/rtl/eth_axis_tx.v]]] {
    if {![file isfile $path]} {error "Missing RoCE HDL: $path"}
    if {[lsearch -exact $sources $path]<0} {lappend sources $path}
}
set roce_memory_init [glob -nocomplain [file join $roce_hls_rtl *.dat]]
