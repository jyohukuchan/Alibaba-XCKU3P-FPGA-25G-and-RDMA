# SPDX-License-Identifier: BSD-2-Clause-Views
# Physical integrity-block check only. No device connection/programming.
if {[llength $argv] != 2} {error "Usage: vivado -mode batch -source ooc_integrity.tcl -tclargs NEW_OUTPUT_DIR TX_MODE"}
set output [file normalize [lindex $argv 0]]
set tx [lindex $argv 1]
if {$tx ni {0 1}} {error "TX_MODE must be 0 (RX) or 1 (TX)"}
if {[file exists $output]} {error "Refusing to overwrite existing output directory"}
set root [file normalize [file join [file dirname [info script]] ../..]]
file mkdir $output
cd $output
set sources [list \
    [file join $root rdma/rtl/rocev2_ipv4_icrc.v] \
    [file join $root external/corundum/fpga/lib/eth/lib/axis/rtl/axis_fifo.v] \
    [file join $root external/corundum/fpga/lib/eth/lib/axis/rtl/axis_register.v] \
    [file join $root external/corundum/fpga/lib/eth/rtl/lfsr.v]]
set source_identity "TX_MODE=$tx\n[exec sha256sum {*}$sources]\n"
set routed_resume [info exists ::env(AS02_ROUTED_CHECKPOINT)]
if {$routed_resume && [info exists ::env(AS02_SYNTH_CHECKPOINT)]} {
    error "Select synthesis OR routed resume, not both"
}
if {$routed_resume || [info exists ::env(AS02_SYNTH_CHECKPOINT)]} {
    if {$routed_resume} {
        set checkpoint [file normalize $::env(AS02_ROUTED_CHECKPOINT)]
    } else {
        set checkpoint [file normalize $::env(AS02_SYNTH_CHECKPOINT)]
    }
    set manifest [file join [file dirname $checkpoint] synthesis-source.txt]
    if {![file isfile $checkpoint] || ![file isfile $manifest]} {error "Missing explicit synthesis checkpoint/identity"}
    set fd [open $manifest r]; set recorded [read $fd]; close $fd
    if {$recorded ne $source_identity} {error "Checkpoint mode/source identity does not match current RTL"}
    open_checkpoint $checkpoint
} else {
    create_project -in_memory -part xcku3p-ffvb676-1-e
    read_verilog $sources
    synth_design -top rocev2_ipv4_icrc -part xcku3p-ffvb676-1-e -mode out_of_context -generic TX_MODE=$tx
}
# Persist the expensive synthesis before any constraints/physical commands.
# A routed resume preserves the old constraints and is not labelled synthesis.
if {!$routed_resume} {write_checkpoint [file join $output synthesized.dcp]}
set fd [open [file join $output synthesis-source.txt] w]
puts -nonewline $fd $source_identity
close $fd
if {!$routed_resume} {
    create_clock -name core_clk -period 4.000 [get_ports clk]
    set_input_delay -clock core_clk 0.000 [get_ports -filter {DIRECTION == IN && NAME != clk}]
    set_output_delay -clock core_clk 0.000 [all_outputs]
    opt_design
    place_design
    phys_opt_design
    route_design
} else {
    if {[llength [get_clocks core_clk]]!=1 || [get_property PERIOD [get_clocks core_clk]]!=4.000} {
        error "Routed checkpoint must retain the 4ns core clock"
    }
}
# Physical delay insertion, not relaxed I/O budgets, false paths or a slower
# target clock. A fully routed OOC check must pass both setup AND hold.
phys_opt_design -hold_fix
route_design
report_utilization -file [file join $output utilization.rpt]
report_timing_summary -report_unconstrained -warn_on_violation -file [file join $output timing.rpt]
report_route_status -file [file join $output route.rpt]
report_drc -file [file join $output drc.rpt]
write_checkpoint [file join $output routed.dcp]
set setup [get_timing_paths -delay_type max -max_paths 1 -quiet]
set hold [get_timing_paths -delay_type min -max_paths 1 -quiet]
if {![llength $setup] || ![llength $hold]} {error "Missing setup/hold timing evidence"}
set wns [get_property SLACK $setup]
set whs [get_property SLACK $hold]
puts "INTEGRITY_OOC TX_MODE=$tx WNS_NS=$wns WHS_NS=$whs (not board-level timing)"
set severe [get_drc_violations -quiet -filter {SEVERITY == Error || SEVERITY == "Critical Warning"}]
if {$wns < 0 || $whs < 0 || [llength $severe]} {error "Integrity-block timing/DRC gate failed"}
exit
