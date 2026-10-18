# SPDX-License-Identifier: BSD-2-Clause-Views
# Isolated control/pattern physical sizing, never a board timing certificate.
if {[llength $argv]!=1} {error "Usage: vivado -mode batch -source ooc_control.tcl -tclargs NEW_OUTPUT_DIR"}
set output [file normalize [lindex $argv 0]]
if {[file exists $output]} {error "Refusing to overwrite existing output"}
set root [file normalize [file join [file dirname [info script]] ../..]]
set sources {}
foreach source {rocev2_control.v rocev2_write_engine.v rocev2_pattern_source.v} {
    lappend sources [file join $root rdma/rtl $source]
}
file mkdir $output
cd $output
set fd [open source-identity.txt w]
puts $fd [exec sha256sum {*}$sources]
close $fd
create_project -in_memory -part xcku3p-ffvb676-1-e
read_verilog $sources
synth_design -top rocev2_control -part xcku3p-ffvb676-1-e -mode out_of_context
write_checkpoint synthesized.dcp
create_clock -name core_clk -period 4.000 [get_ports clk]
set_input_delay -clock core_clk 0.000 [get_ports -filter {DIRECTION == IN && NAME != clk}]
set_output_delay -clock core_clk 0.000 [all_outputs]
opt_design
place_design
phys_opt_design
route_design
report_utilization -file utilization.rpt
report_timing_summary -report_unconstrained -warn_on_violation -file timing.rpt
report_route_status -file route.rpt
report_drc -file drc.rpt
write_checkpoint routed.dcp
foreach kind {max min} {
    set paths [get_timing_paths -delay_type $kind -max_paths 1 -quiet]
    if {![llength $paths]} {error "Missing overall timing paths"}
    set slack($kind) [get_property SLACK [lindex $paths 0]]
}
puts "CONTROL_OOC WNS_NS=$slack(max) WHS_NS=$slack(min) (not board-level timing)"
set severe [get_drc_violations -quiet -filter {SEVERITY == Error || SEVERITY == "Critical Warning"}]
if {$slack(max)<0 || $slack(min)<0 || [llength $severe]} {error "Control-block overall timing/DRC gate failed"}
exit
