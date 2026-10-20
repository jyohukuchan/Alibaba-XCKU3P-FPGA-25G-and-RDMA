# SPDX-License-Identifier: BSD-2-Clause-Views
# Source-frozen actual SQ/paged/router/RAM 4ns analysis, NOT board signoff.
# No bitstream, device access, constraints waiver or runtime state change.
if {![info exists ::env(AS02_RNIC_SHARED_DMA_BUILD)]} {error "Set a fresh AS02_RNIC_SHARED_DMA_BUILD"}
set output [file normalize $::env(AS02_RNIC_SHARED_DMA_BUILD)]
if {[file exists $output]} {error "Refusing to overwrite $output"}
set script [file normalize [info script]]
set root [file normalize [file join [file dirname $script] ../../..]]
set sources {}
foreach name {rocev2_sq_paged_dma.v rocev2_dma_client_router.v rocev2_sq_dma_fetch.v rocev2_sq_fetch.v rocev2_paged_memory_backend.v rocev2_page_dma_engine.v rocev2_mr_page_table.v rocev2_corundum_dma_backend.v} {
    lappend sources [file join [file dirname $script] $name]
}
foreach name {dma_psdpram.v dma_client_axis_source.v dma_client_axis_sink.v} {
    lappend sources [file join $root external/corundum/fpga/lib/pcie/rtl $name]
}
lappend sources [file join $root external/corundum/fpga/lib/axis/rtl/axis_register.v]
set all_inputs [concat $sources [list $script]]
set hashes [exec sha256sum {*}$all_inputs]
file mkdir $output
set fd [open [file join $output original_inputs.sha256] w]
puts $fd $hashes
close $fd
set frozen_hashes {}
foreach line [split $hashes "\n"] {
    if {![regexp {^([0-9a-f]{64})  (.*)$} $line unused hash source]} {error "Invalid source identity row"}
    file copy $source [file join $output [file tail $source]]
    lappend frozen_hashes "$hash  [file tail $source]"
}
set fd [open [file join $output frozen_inputs.sha256] w]
puts $fd [join $frozen_hashes "\n"]
close $fd
set copied {}
foreach source $sources {lappend copied [file join $output [file tail $source]]}
cd $output
exec sha256sum --check --status original_inputs.sha256
exec sha256sum --check --status frozen_inputs.sha256
set_param general.maxThreads 8
read_verilog $copied
synth_design -top rocev2_sq_paged_dma -part xcku3p-ffvb676-1-e -mode out_of_context
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
report_route_status -file [file join $output routing.rpt]
report_drc -file [file join $output drc.rpt]
check_timing -verbose -file [file join $output check_timing.rpt]
write_checkpoint [file join $output routed.dcp]
exec sha256sum --check --status original_inputs.sha256
exec sha256sum --check --status frozen_inputs.sha256
set max_path [get_timing_paths -delay_type max -max_paths 1]
set min_path [get_timing_paths -delay_type min -max_paths 1]
if {[llength $max_path]!=1 || [llength $min_path]!=1} {error "Missing timed paths"}
set wns [get_property SLACK $max_path]
set whs [get_property SLACK $min_path]
puts "RNIC_SHARED_DMA_OOC WNS=$wns WHS=$whs ORIGINAL_AND_FROZEN_INPUTS_UNCHANGED=1 IMAGE_WRITTEN=0 NATIVE_BOARD_SIGNOFF=0"
set fd [open [file join $output check_timing.rpt] r]
set checks [read $fd]
close $fd
foreach category {no_clock constant_clock pulse_width_clock unconstrained_internal_endpoints no_input_delay no_output_delay multiple_clock generated_clocks loops partial_input_delay partial_output_delay latch_loops} {
    if {![regexp "checking $category \\(0\\)" $checks]} {error "Isolated check_timing failure: $category"}
}
set fd [open [file join $output drc.rpt] r]
set drc [read $fd]
close $fd
if {[regexp {\|[^|\n]+\|[[:space:]]+(Error|Critical Warning)[[:space:]]+\|} $drc]} {error "Isolated DRC error/critical warning"}
if {$wns<0 || $whs<0} {error "Shared DMA does not meet isolated4ns timing"}
exit
