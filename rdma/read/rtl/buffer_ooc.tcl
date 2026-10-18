# SPDX-License-Identifier: BSD-2-Clause-Views
# Physical resource/timing probe only; never connects to hardware.
if {![info exists ::env(AS02_READ_BUFFER_BUILD)]} {
    error "Set a new AS02_READ_BUFFER_BUILD directory"
}
set output [file normalize $::env(AS02_READ_BUFFER_BUILD)]
if {[file exists $output]} {error "Refusing to overwrite $output"}
file mkdir $output
set source [file join [file dirname [file normalize [info script]]] rocev2_read_buffer.v]
file copy $source [file join $output rocev2_read_buffer.v]
file copy [file normalize [info script]] [file join $output buffer_ooc.tcl]
read_verilog [file join $output rocev2_read_buffer.v]
synth_design -top rocev2_read_buffer -part xcku3p-ffvb676-1-e -mode out_of_context
create_clock -period 4.000 -name clk [get_ports clk]
# Explicit isolated-block driver/receiver model, NOT board signoff:
# 0.2ns minimum upstream clock-to-output and 0.5ns maximum I/O budget.
# The first probe used ideal zero-delay OOC ports, creating unrouteable
# zero-delay port-to-LUTRAM hold paths. Full-board clocks/gates stay unchanged.
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
report_drc -file [file join $output drc.rpt]
write_checkpoint [file join $output routed.dcp]
set setup_path [get_timing_paths -delay_type max -max_paths 1]
set hold_path [get_timing_paths -delay_type min -max_paths 1]
if {[llength $setup_path]!=1 || [llength $hold_path]!=1} {error "Missing timed paths"}
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]
set brams [llength [get_cells -hier -filter {REF_NAME =~ RAMB*}]]
puts "READ_BUFFER_OOC WNS=$wns WHS=$whs BRAM_PRIMITIVES=$brams"
if {$brams==0} {error "Capture RAM did not map to BRAM"}
if {$wns<0 || $whs<0} {error "Protected buffer does not meet 4ns OOC timing"}
exit
