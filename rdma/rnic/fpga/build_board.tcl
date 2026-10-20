# SPDX-License-Identifier: BSD-2-Clause-Views
# FULL-board ANALYSIS ONLY. Stops at routed checkpoint, never writes an image.
# Original physical/source gates remain immutable; this is NOT their release.
if {[llength $argv]!=1} {error "Usage: frozen build_board.tcl OUTPUT_DIRECTORY"}
set out_dir [file normalize [lindex $argv 0]]
set frozen [file join $out_dir inputs]
set manifest [file join $frozen inputs.sha256]
if {![file isfile [file join $out_dir analysis-inputs.json]]} {error "Use prepare_board.py first"}
cd $frozen
exec sha256sum --check --status $manifest
source [file join $frozen build_inputs.tcl]
foreach path [concat $sources $constraints $ip_scripts $memory_init [list $config_script]] {
    if {![file isfile $path]} {error "Missing frozen board input $path"}
}
if {[info exists ::env(AS02_RNIC_SOURCE_ONLY)] && $::env(AS02_RNIC_SOURCE_ONLY) eq "1"} {
    puts "RNIC_BOARD_SOURCE_ONLY HDL=[llength $sources] CONSTRAINTS=[llength $constraints] IP=[llength $ip_scripts] IMAGE_AUTHORIZED=0"
    exit
}
set project_dir [file join $out_dir project]
if {[file exists $project_dir]} {error "Refusing to overwrite an existing board project"}
cd $out_dir
create_project as02mc04_rnic_analysis $project_dir -part xcku3p-ffvb676-1-e
set_property target_language Verilog [current_project]
set_property top fpga [get_filesets sources_1]
add_files -fileset sources_1 $sources
add_files -fileset constrs_1 $constraints
foreach script $ip_scripts {source $script}
# Build ID still identifies pinned upstream; ASN1 and the independent frozen
# manifest identify our explicitly patched source/profile, not a fake commit.
cd $corundum
set ::env(AS02_ENABLE_ROCE) 1
source $config_script
cd $out_dir
if {[get_property CONFIG.PF0_CLASS_CODE [get_ips pcie4_uscale_plus_0]] ne "020000"} {
    error "PCIe Ethernet class changed"
}
update_compile_order -fileset sources_1
set_property strategy Performance_ExplorePostRoutePhysOpt [get_runs impl_1]
set_property STEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE AggressiveExplore [get_runs impl_1]
set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.ARGS.DIRECTIVE AggressiveExplore [get_runs impl_1]
set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
set run_dir [get_property DIRECTORY [get_runs synth_1]]
file mkdir $run_dir
foreach path $memory_init {file copy $path [file join $run_dir [file tail $path]]}
launch_runs synth_1 -jobs 8
wait_on_run synth_1
if {![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} {
    error "Full-board synthesis failed: [get_property STATUS [get_runs synth_1]]"
}
open_run synth_1
report_utilization -file [file join $out_dir synthesis_utilization.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -file [file join $out_dir synthesis_timing.rpt]
write_checkpoint [file join $out_dir full_board_post_synth.dcp]
close_design
launch_runs impl_1 -to_step {phys_opt_design (Post-Route)} -jobs 8
wait_on_run impl_1
if {![string match "*Complete*" [get_property STATUS [get_runs impl_1]]]} {
    error "Full-board implementation failed: [get_property STATUS [get_runs impl_1]]"
}
open_run impl_1
report_utilization -file [file join $out_dir utilization.rpt]
report_clocks -file [file join $out_dir clocks.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -file [file join $out_dir timing.rpt]
report_timing -delay_type max -max_paths 20 -file [file join $out_dir setup_paths.rpt]
report_timing -delay_type min -max_paths 20 -file [file join $out_dir hold_paths.rpt]
report_route_status -file [file join $out_dir routing.rpt]
report_bus_skew -file [file join $out_dir bus_skew.rpt]
report_drc -file [file join $out_dir drc.rpt]
report_cdc -details -file [file join $out_dir cdc.rpt]
check_timing -verbose -file [file join $out_dir check_timing.rpt]
write_checkpoint [file join $out_dir full_board_routed.dcp]
cd $frozen
exec sha256sum --check --status $manifest
puts "RNIC_FULL_BOARD_ANALYSIS_COMPLETE=1 IMAGE_WRITTEN=0 PHYSICAL_RELEASE_AUTHORIZED=0 HARDWARE_VERIFIED=0"
close_project
exit
