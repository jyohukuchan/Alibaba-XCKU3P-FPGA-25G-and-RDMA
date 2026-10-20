# SPDX-License-Identifier: BSD-2-Clause-Views
# Source-frozen isolated resource/timing estimate, NOT native board signoff.
# No programming, DMA, traffic, kernel/fan/network changes or reboot.
foreach name {AS02_RNIC_RESPONDER_BUILD AS02_RNIC_HLS_BUILD} {
    if {![info exists ::env($name)]} {error "Set $name"}
}
set output [file normalize $::env(AS02_RNIC_RESPONDER_BUILD)]
if {[file exists $output]} {error "Refusing to overwrite $output"}
set script [file normalize [info script]]
set root [file normalize [file join [file dirname $script] ../../..]]
set generated [file normalize [file join $::env(AS02_RNIC_HLS_BUILD) solution1/syn/verilog]]
if {![file isfile [file join $generated rocev2_top.v]]} {error "Missing generated HLS"}
set sources [lsort [glob -directory $generated *.v]]
foreach name {rocev2_mr_table.v rocev2_protected_responder.v} {
    lappend sources [file join [file dirname $script] $name]
}
foreach name {rocev2_ipv4_icrc.v rocev2_tx_padding.v rocev2_integrity_transport.v} {
    lappend sources [file join $root rdma/rtl $name]
}
foreach name {axis_fifo.v axis_register.v axis_adapter.v} {
    lappend sources [file join $root external/corundum/fpga/lib/axis/rtl $name]
}
lappend sources [file join $root external/corundum/fpga/lib/eth/rtl/lfsr.v]
set data [lsort [glob -directory $generated *.dat]]
file mkdir $output
set inputs [concat $sources $data [list $script]]
set fd [open [file join $output original_inputs.sha256] w]
puts $fd [exec sha256sum {*}$inputs]
close $fd
set copied {}
foreach source $inputs {
    set target [file join $output [file tail $source]]
    if {[file exists $target]} {error "Source basename collision $target"}
    file copy $source $target
}
foreach source $sources {lappend copied [file join $output [file tail $source]]}
cd $output
set_param general.maxThreads 8
read_verilog $copied
synth_design -top rocev2_protected_responder -part xcku3p-ffvb676-1-e -mode out_of_context
create_clock -name clk -period 4.000 [get_ports clk]
set_input_delay -min 0.200 -clock clk [get_ports -filter {DIRECTION == IN && NAME != clk}]
set_input_delay -max 0.500 -clock clk [get_ports -filter {DIRECTION == IN && NAME != clk}]
set_output_delay -min 0.000 -clock clk [get_ports -filter {DIRECTION == OUT}]
set_output_delay -max 0.500 -clock clk [get_ports -filter {DIRECTION == OUT}]
report_utilization -file [file join $output utilization.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -file [file join $output timing.rpt]
report_timing -delay_type max -max_paths 10 -file [file join $output setup_paths.rpt]
report_drc -file [file join $output drc.rpt]
write_checkpoint [file join $output post_synth.dcp]
exec sha256sum --check --status [file join $output original_inputs.sha256]
puts "RNIC_RESPONDER_SYNTH SOURCE_UNCHANGED=1 SYNTHESIS_ONLY=1 PHYSICAL_SIGNOFF=0 NATIVE_BOARD_SIGNOFF=0"
exit
