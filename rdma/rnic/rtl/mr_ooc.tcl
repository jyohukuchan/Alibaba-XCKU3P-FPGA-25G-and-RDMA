# SPDX-License-Identifier: BSD-2-Clause-Views
# Isolated4ns probe only: no FPGA programming, flash, NIC or fan changes.
if {![info exists ::env(AS02_RNIC_MR_BUILD)]} {error "Set a fresh AS02_RNIC_MR_BUILD"}
set output [file normalize $::env(AS02_RNIC_MR_BUILD)]
if {[file exists $output]} {error "Refusing to overwrite $output"}
file mkdir $output
set script [file normalize [info script]]
set source [file join [file dirname $script] rocev2_mr_table.v]
set fd [open [file join $output original_inputs.sha256] w]
puts $fd [exec sha256sum $source $script]
close $fd
file copy $source [file join $output rocev2_mr_table.v]
file copy $script [file join $output mr_ooc.tcl]
read_verilog [file join $output rocev2_mr_table.v]
synth_design -top rocev2_mr_table -part xcku3p-ffvb676-1-e -mode out_of_context
create_clock -period 4.000 -name clk [get_ports clk]
# Explicit isolated upstream/downstream model; not full-board constraints.
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
report_timing -delay_type max -max_paths 5 -file [file join $output setup_paths.rpt]
report_timing -delay_type min -max_paths 5 -file [file join $output hold_paths.rpt]
report_drc -file [file join $output drc.rpt]
write_checkpoint [file join $output routed.dcp]
exec sha256sum --check --status [file join $output original_inputs.sha256]
set setup_path [get_timing_paths -delay_type max -max_paths 1]
set hold_path [get_timing_paths -delay_type min -max_paths 1]
if {[llength $setup_path]!=1 || [llength $hold_path]!=1} {error "Missing timed paths"}
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]
puts "RNIC_MR_OOC WNS=$wns WHS=$whs NATIVE_BOARD_SIGNOFF=0"
if {$wns<0 || $whs<0} {error "MR primitive does not meet isolated4ns timing"}
exit
