# SPDX-License-Identifier: BSD-2-Clause-Views
# Route the source-bound synthesized protected top; no native board signoff.
foreach name {AS02_RNIC_RESPONDER_SYNTH AS02_RNIC_RESPONDER_ROUTE} {
    if {![info exists ::env($name)]} {error "Set $name"}
}
set input [file normalize $::env(AS02_RNIC_RESPONDER_SYNTH)]
set output [file normalize $::env(AS02_RNIC_RESPONDER_ROUTE)]
if {[file exists $output]} {error "Refusing to overwrite $output"}
set script [file normalize [info script]]
set checkpoint [file join $input post_synth.dcp]
set manifest [file join $input original_inputs.sha256]
if {![file isfile $checkpoint] || ![file isfile $manifest]} {error "Missing source-bound synthesized checkpoint"}
exec sha256sum --check --status $manifest
file mkdir $output
set fd [open [file join $output route_inputs.sha256] w]
puts $fd [exec sha256sum $checkpoint $manifest $script]
close $fd
file copy $checkpoint [file join $output seed.dcp]
file copy $manifest [file join $output synthesis_inputs.sha256]
file copy $script [file join $output responder_route.tcl]
cd $output
set_param general.maxThreads 8
open_checkpoint [file join $output seed.dcp]
if {[llength [get_clocks clk]]!=1 || [get_property PERIOD [get_clocks clk]]!=4.000} {
    error "Unexpected isolated clock; preserve original4ns constraints"
}
opt_design
place_design
phys_opt_design
route_design
phys_opt_design -hold_fix
report_utilization -file [file join $output utilization.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -file [file join $output timing.rpt]
report_timing -delay_type max -max_paths 10 -file [file join $output setup_paths.rpt]
report_timing -delay_type min -max_paths 5 -file [file join $output hold_paths.rpt]
report_route_status -file [file join $output routing.rpt]
report_drc -file [file join $output drc.rpt]
write_checkpoint [file join $output routed.dcp]
exec sha256sum --check --status [file join $output synthesis_inputs.sha256]
exec sha256sum --check --status [file join $output route_inputs.sha256]
set max_path [get_timing_paths -delay_type max -max_paths 1]
set min_path [get_timing_paths -delay_type min -max_paths 1]
if {[llength $max_path]!=1 || [llength $min_path]!=1} {error "Missing timed paths"}
set wns [get_property SLACK $max_path]
set whs [get_property SLACK $min_path]
puts "RNIC_RESPONDER_ROUTE WNS=$wns WHS=$whs NATIVE_BOARD_SIGNOFF=0"
if {$wns<0 || $whs<0} {error "Protected responder does not meet isolated4ns physical timing"}
exit
