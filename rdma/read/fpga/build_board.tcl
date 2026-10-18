# SPDX-License-Identifier: BSD-2-Clause-Views
# Copyright (c) 2026 jyohukuchan
# Build only: this script never programs a device or flash.
# Invoke via build_25g.sh after installing Vivado Standard and KU3P device files.
set rw_profile_dir [file dirname [file normalize [info script]]]
set task_dir [file normalize [file join $rw_profile_dir ../../../fpga]]
if {[llength $argv] != 1} {error "Usage: vivado -mode batch -source build_25g.tcl -tclargs OUTPUT_DIR"}
set out_dir [file normalize [lindex $argv 0]]
set corundum [file normalize [file join $task_dir ../external/corundum]]
set port [file normalize [file join $task_dir ../external/as02mc04-port]]
set board [file join $corundum fpga/mqnic/Nexus_K3P_S/fpga_25g]
foreach {dependency expected} [list $corundum 1ca0151b97af85aa5dd306d74b6bcec65904d2ce $port b00e73a136170604e40341b13b9b1fb9df9304fb] {
    if {[catch {exec git -C $dependency rev-parse HEAD} actual] || $actual ne $expected} {
        error "Missing/wrong dependency revision at $dependency; initialize the pinned submodules"
    }
}

proc make_files {makefile name} {
    set fd [open $makefile r]
    set content [read $fd]
    close $fd
    set result {}
    foreach line [split $content \n] {
        if {[regexp {^([A-Z_]+)\s*(\+?=)\s*(.+)$} $line -> key op values] && $key eq $name} {
            if {$op eq "="} {set result {}}
            foreach value $values {lappend result $value}
        }
    }
    if {![llength $result]} {error "No $name entries in $makefile"}
    return $result
}

set sources {}
foreach rel [make_files [file join $port Makefile] SYN_FILES] {
    if {$rel eq "rtl/fpga_as02mc04.v"} {
        set path [file join $task_dir fpga_as02mc04_25g_cdc.v]
    } else {
        set path [file normalize [file join $board $rel]]
    }
    if {![file isfile $path]} {error "Missing HDL source: $path"}
    lappend sources $path
}
set constraints {}
foreach rel [make_files [file join $port Makefile] XDC_FILES] {
    if {$rel eq "as02mc04.xdc"} {
        set path [file join $task_dir as02mc04.xdc]
    } else {
        set path [file normalize [file join $board $rel]]
    }
    if {![file isfile $path]} {error "Missing constraint: $path"}
    lappend constraints $path
}
set ip_scripts {}
lappend constraints [file join $task_dir vio_status_cdc.xdc]
foreach rel [make_files [file join $port Makefile] IP_TCL_FILES] {
    if {$rel eq "ip/vio_status.tcl"} {
        set path [file join $port $rel]
    } else {
        set path [file normalize [file join $board $rel]]
    }
    if {![file isfile $path]} {error "Missing IP generator: $path"}
    lappend ip_scripts $path
}

set roce_enabled [expr {[info exists env(AS02_ENABLE_ROCE)] && $env(AS02_ENABLE_ROCE) eq "1"}]
if {!$roce_enabled} {error "Use the separate RW build_board.sh driver"}
if {$roce_enabled} {
    source [file join $rw_profile_dir sources.tcl]
    lappend constraints [file join $task_dir mac_flow_control_cdc.xdc]
}

if {[info exists env(AS02_SOURCE_CHECK_ONLY)] && $env(AS02_SOURCE_CHECK_ONLY) eq "1"} {
    puts "Source check passed: [llength $sources] HDL, [llength $constraints] constraints, [llength $ip_scripts] IP generators."
    exit 0
}

file mkdir $out_dir
cd $out_dir
create_project as02mc04_25g $out_dir -part xcku3p-ffvb676-1-e
set_property target_language Verilog [current_project]
set_property top fpga [get_filesets sources_1]
add_files -fileset sources_1 $sources
add_files -fileset constrs_1 $constraints
foreach script $ip_scripts {source $script}
# Run the config in the Corundum checkout so its build ID identifies the RTL.
cd $corundum
source [file join $task_dir config_25g.tcl]
cd $out_dir
set actual_class [get_property CONFIG.PF0_CLASS_CODE [get_ips pcie4_uscale_plus_0]]
if {$actual_class ne "020000"} {error "PCIe Ethernet class code was not applied: $actual_class"}
puts "VERIFIED_PCIE_CLASS=$actual_class"
update_compile_order -fileset sources_1
# The native 390.625 MHz MACs need a timing-oriented clean implementation.
# Keep the original clock/temperature/speed-grade constraints unchanged.
set_property strategy Performance_ExplorePostRoutePhysOpt [get_runs impl_1]
set_property STEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE AggressiveExplore [get_runs impl_1]
set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.ARGS.DIRECTIVE AggressiveExplore [get_runs impl_1]
set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
if {$roce_enabled} {
    # HLS readmemh names are relative to the synthesis run working directory.
    # Keep the generated sources intact; copy only their exact initialization
    # files into this new run, never into another build or the source checkout.
    set roce_run_dir [get_property DIRECTORY [get_runs synth_1]]
    file mkdir $roce_run_dir
    foreach path $roce_memory_init {file copy $path [file join $roce_run_dir [file tail $path]]}
    set fd [open [file join $out_dir rocev2-source-identity.txt] w]
    puts $fd [exec sha256sum {*}$sources {*}$roce_memory_init {*}$constraints {*}$ip_scripts \
        [file join $task_dir build_25g.tcl] [file join $task_dir config_25g.tcl] \
        [file join $task_dir implement_25g.tcl] [file join $task_dir write_verified_25g_eco.tcl] \
        [file join $task_dir verify_vio_status_cdc.tcl] [file join $task_dir verify_mac_flow_control_cdc.tcl] \
        [file join $task_dir ../rdma/scripts/verify_lfc_equivalent.tcl] \
        [file join $task_dir ../rdma/fpga/sources.tcl] \
        [file join $task_dir ../rdma/hls/probe/check_build.py] \
        [file join $rw_profile_dir build_board.tcl] [file join $rw_profile_dir build_board.sh] \
        [file join $rw_profile_dir sources.tcl] {*}$rw_verification_inputs]
    close $fd
}
launch_runs synth_1 -jobs 8
wait_on_run synth_1
if {![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} {
    error "Synthesis failed: [get_property STATUS [get_runs synth_1]]"
}
source [file join $task_dir implement_25g.tcl]
