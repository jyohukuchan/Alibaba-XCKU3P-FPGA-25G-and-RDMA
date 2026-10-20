# SPDX-License-Identifier: BSD-2-Clause-Views
# Isolated real backend/RAM/clients4ns physical probe; NOT full-board signoff.
if {![info exists ::env(AS02_RNIC_DMA_BUILD)]} {error "Set a fresh AS02_RNIC_DMA_BUILD"}
set output [file normalize $::env(AS02_RNIC_DMA_BUILD)]
if {[file exists $output]} {error "Refusing to overwrite $output"}
set script [file normalize [info script]]
set root [file normalize [file join [file dirname $script] ../../..]]
set sources [list [file join [file dirname $script] rocev2_corundum_dma_backend.v]]
foreach name {dma_psdpram.v dma_client_axis_source.v dma_client_axis_sink.v} {
    lappend sources [file join $root external/corundum/fpga/lib/pcie/rtl $name]
}
lappend sources [file join $root external/corundum/fpga/lib/axis/rtl/axis_register.v]
file mkdir $output
set fd [open [file join $output original_inputs.sha256] w]
puts $fd [exec sha256sum {*}$sources $script]
close $fd
set copied {}
foreach source [concat $sources [list $script]] {
    file copy $source [file join $output [file tail $source]]
}
foreach source $sources {lappend copied [file join $output [file tail $source]]}
cd $output
set_param general.maxThreads 8
read_verilog $copied
synth_design -top rocev2_corundum_dma_backend -part xcku3p-ffvb676-1-e -mode out_of_context -generic {RAM_ADDR_WIDTH=15}
create_clock -name clk -period 4.000 [get_ports clk]
set_input_delay -min 0.200 -clock clk [get_ports -filter {DIRECTION == IN && NAME != clk}]
set_input_delay -max 0.500 -clock clk [get_ports -filter {DIRECTION == IN && NAME != clk}]
set_output_delay -min 0.000 -clock clk [get_ports -filter {DIRECTION == OUT}]
set_output_delay -max 0.500 -clock clk [get_ports -filter {DIRECTION == OUT}]
opt_design
place_design
phys_opt_design
route_design
phys_opt_design -hold_fix
report_utilization -file [file join $output utilization.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -file [file join $output timing.rpt]
report_timing -delay_type max -max_paths 10 -file [file join $output setup_paths.rpt]
report_timing -delay_type min -max_paths 5 -file [file join $output hold_paths.rpt]
report_drc -file [file join $output drc.rpt]
write_checkpoint [file join $output routed.dcp]
exec sha256sum --check --status [file join $output original_inputs.sha256]
set max_path [get_timing_paths -delay_type max -max_paths 1]
set min_path [get_timing_paths -delay_type min -max_paths 1]
if {[llength $max_path]!=1 || [llength $min_path]!=1} {error "Missing timed paths"}
set wns [get_property SLACK $max_path]
set whs [get_property SLACK $min_path]
puts "RNIC_DMA_BACKEND_OOC WNS=$wns WHS=$whs NATIVE_BOARD_SIGNOFF=0"
if {$wns<0 || $whs<0} {error "Backend does not meet isolated4ns timing"}
exit
