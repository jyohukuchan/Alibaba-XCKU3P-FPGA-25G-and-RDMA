# SPDX-License-Identifier: BSD-2-Clause-Views
# Actual single-AXI CSR + dual Ethernet/protected endpoint OOC estimate.
# NOT the board, mqnic_app_block, PCIe parent/hard-IP, or hardware signoff.
foreach name {AS02_RNIC_NATIVE_BUILD AS02_RNIC_HLS_BUILD} {
    if {![info exists ::env($name)]} {error "Set $name"}
}
set output [file normalize $::env(AS02_RNIC_NATIVE_BUILD)]
if {[file exists $output]} {error "Refusing to overwrite $output"}
set script [file normalize [info script]]
set root [file normalize [file join [file dirname $script] ../../..]]
set generated [file normalize [file join $::env(AS02_RNIC_HLS_BUILD) solution1/syn/verilog]]
if {![file isfile [file join $generated rocev2_top.v]]} {error "Missing actual generated HLS"}
set sources [lsort [glob -directory $generated *.v]]
foreach name {
    rocev2_mr_table.v rocev2_protected_responder.v rocev2_paged_responder.v
    rocev2_paged_memory_backend.v rocev2_corundum_dma_backend.v
    rocev2_page_dma_engine.v rocev2_mr_page_table.v rocev2_mr_control.v
    rocev2_control_regs.v rocev2_controlled_responder.v
    rocev2_responder_ethernet_rx.v rocev2_dual_ethernet_endpoint.v
    rocev2_ethernet_config_regs.v rocev2_native_endpoint.v
} {lappend sources [file join [file dirname $script] $name]}
foreach name {
    rocev2_write_engine.v rocev2_pattern_source.v rocev2_ethernet_tx.v
    rocev2_ipv4_icrc.v rocev2_tx_padding.v rocev2_integrity_transport.v rocev2_tx_guard.v
} {lappend sources [file join $root rdma/rtl $name]}
foreach name {
    rocev2_read_engine.v rocev2_read_buffer.v rocev2_rw_control.v
    rocev2_rw_ethernet_rx.v rocev2_rw_endpoint.v
} {lappend sources [file join $root rdma/read/rtl $name]}
foreach name {dma_psdpram.v dma_client_axis_source.v dma_client_axis_sink.v} {
    lappend sources [file join $root external/corundum/fpga/lib/pcie/rtl $name]
}
foreach name {
    axil_reg_if.v axil_reg_if_wr.v axil_reg_if_rd.v axil_crossbar.v
    axil_crossbar_rd.v axil_crossbar_wr.v axil_crossbar_addr.v
    axil_register_rd.v axil_register_wr.v
} {lappend sources [file join $root external/corundum/fpga/lib/axi/rtl $name]}
foreach name {axis_fifo.v axis_register.v axis_adapter.v axis_arb_mux.v arbiter.v priority_encoder.v} {
    lappend sources [file join $root external/corundum/fpga/lib/axis/rtl $name]
}
foreach name {eth_axis_rx.v eth_axis_tx.v lfsr.v} {
    lappend sources [file join $root external/corundum/fpga/lib/eth/rtl $name]
}
set data [lsort [glob -nocomplain -directory $generated *.dat]]
file mkdir $output
set inputs [concat $sources $data [list $script]]
set fd [open [file join $output original_inputs.sha256] w]
puts $fd [exec sha256sum {*}$inputs]
close $fd
set copied {}
foreach source $inputs {
    set target [file join $output [file tail $source]]
    if {[file exists $target]} {error "Input basename collision $target"}
    file copy $source $target
}
foreach source $sources {lappend copied [file join $output [file tail $source]]}
cd $output
set fd [open frozen_inputs.sha256 w]
puts $fd [exec sha256sum {*}[glob -nocomplain *.v *.dat *.tcl]]
close $fd
set_param general.maxThreads 8
read_verilog $copied
# Default geometry is exactly the native candidate: RAM address15, two256bit
# segments, one RAM-select bit and16full application DMA-tag bits.
synth_design -top rocev2_native_endpoint -part xcku3p-ffvb676-1-e -mode out_of_context
create_clock -name clk -period 4.000 [get_ports clk]
set_input_delay -min 0.200 -clock clk [get_ports -filter {DIRECTION == IN && NAME != clk}]
set_input_delay -max 0.500 -clock clk [get_ports -filter {DIRECTION == IN && NAME != clk}]
set_output_delay -min 0.000 -clock clk [get_ports -filter {DIRECTION == OUT}]
set_output_delay -max 0.500 -clock clk [get_ports -filter {DIRECTION == OUT}]
report_utilization -file utilization.rpt
report_timing_summary -delay_type min_max -report_unconstrained -file timing.rpt
report_timing -delay_type max -max_paths 10 -file setup_paths.rpt
report_drc -file drc.rpt
write_checkpoint post_synth.dcp
exec sha256sum --check --status original_inputs.sha256
exec sha256sum --check --status frozen_inputs.sha256
puts "RNIC_NATIVE_ENDPOINT_SYNTH SOURCE_UNCHANGED=1 SYNTHESIS_ONLY=1 PHYSICAL_SIGNOFF=0 NATIVE_BOARD_SIGNOFF=0"
exit
