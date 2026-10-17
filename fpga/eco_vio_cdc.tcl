# SPDX-License-Identifier: BSD-2-Clause-Views
# Copyright (c) 2026 jyohukuchan
# Add the same 12 FDREs described in fpga_as02mc04_25g_cdc.v to a saved
# routed netlist. Preserve all functional Ethernet/PCIe connections and reuse
# placement/routing. AMD UG904/UG986 ECO flow; no hardware programming.
if {[llength $argv] != 2} {error "Expected ROUTED_CHECKPOINT OUTPUT_DIR"}
set task_dir [file dirname [file normalize [info script]]]
set checkpoint [file normalize [lindex $argv 0]]
set out_dir [file normalize [lindex $argv 1]]
file mkdir $out_dir
cd $out_dir
if {[info exists env(AS02_ECO_REUSE_OPEN)] && $env(AS02_ECO_REUSE_OPEN) eq "1"} {
    puts "REUSING_OPEN_CHECKPOINT=$checkpoint"
} else {
    open_checkpoint $checkpoint
}
if {[get_property PART [current_design]] ne "xcku3p-ffvb676-1-e"} {error "Unexpected part"}
if {[llength [get_cells -quiet vio_status_meta_reg_reg*]]} {error "CDC fix already present"}

proc exactly_one {objects label} {
    if {[llength $objects] != 1} {error "Expected one $label, got [llength $objects]"}
    return $objects
}
proc non_debug_leaf_pins {net} {
    set pins [get_pins -leaf -of_objects [get_nets -segments $net] -filter {NAME !~ vio_status_inst/*}]
    return [lsort -unique [get_property NAME $pins]]
}

set initial_primitive_count [llength [get_cells -hier -filter {IS_PRIMITIVE == 1}]]
set vio [exactly_one [get_cells vio_status_inst] "VIO instance"]
# The debug core itself is tool-protected. Never override that protection;
# use modify_debug_ports for its input changes after placing the added FFs.
set clock_net [exactly_one [get_nets pcie_user_clk] "PCIe user clock net"]
if {abs([get_property PERIOD [get_clocks pcie_user_clk]] - 4.0) > 0.001} {error "Unexpected VIO clock"}

create_cell -reference GND vio_cdc_gnd_inst
create_net vio_cdc_gnd
connect_net -net vio_cdc_gnd -objects [get_pins vio_cdc_gnd_inst/G]
create_cell -reference VCC vio_cdc_vcc_inst
create_net vio_cdc_vcc
connect_net -net vio_cdc_vcc -objects [get_pins vio_cdc_vcc_inst/P]

set expected_signals {sfp_1_rx_block_lock sfp_1_rx_status sfp_1_rx_high_ber sfp_2_rx_block_lock sfp_2_rx_status sfp_2_rx_high_ber}
set probe_changes {}
for {set index 0} {$index < 6} {incr index} {
    set probe [exactly_one [get_pins vio_status_inst/probe_in$index] "VIO probe $index"]
    set original_net [exactly_one [get_nets -of_objects $probe] "probe source net"]
    set expected [exactly_one [get_nets [lindex $expected_signals $index]] "expected PHY status"]
    set original_segments [lsort [get_property NAME [get_nets -segments $original_net]]]
    if {[lsort [get_property NAME [get_nets -segments $expected]]] ne $original_segments} {
        error "VIO probe $index is not the expected PHY status"
    }
    set untouched_pins [non_debug_leaf_pins $original_net]
    set source_nets($index) $original_net
    set preserved_pins($index) $untouched_pins
    # MARK_DEBUG implies a writable DONT_TOUCH on these external source nets.
    # Clear that external net hint to add the synchronizer input connection.
    # The debug core's tool-enforced protection remains intact throughout.
    set_property DONT_TOUCH false [get_nets -segments $original_net]
    set meta [format {vio_status_meta_reg_reg[%d]} $index]
    set sync [format {vio_status_sync_reg_reg[%d]} $index]
    set meta_net [format {vio_status_meta[%d]} $index]
    set sync_net [format {vio_status_sync_%d} $index]
    foreach cell [list $meta $sync] {
        create_cell -reference FDRE $cell
        set_property INIT 1'b0 [get_cells $cell]
        set_property ASYNC_REG true [get_cells $cell]
        set_property DONT_TOUCH true [get_cells $cell]
        connect_net -net $clock_net -objects [get_pins $cell/C]
        connect_net -net vio_cdc_vcc -objects [get_pins $cell/CE]
        connect_net -net vio_cdc_gnd -objects [get_pins $cell/R]
    }
    create_net $meta_net
    create_net $sync_net
    connect_net -hierarchical -net $original_net -objects [get_pins $meta/D]
    connect_net -net $meta_net -objects [get_pins [list $meta/Q $sync/D]]
    connect_net -net $sync_net -objects [get_pins $sync/Q]
    set_property KEEP true [get_nets $sync_net]
    lappend probe_changes [list vio_status_inst/probe_in$index 0 $sync_net]
    # Every pre-existing non-debug driver/load must be preserved exactly.
    set observed [non_debug_leaf_pins $original_net]
    set expected_pins [lsort -unique [concat $untouched_pins [list $meta/D]]]
    if {$observed ne $expected_pins} {error "Functional fanout changed for probe $index"}
    puts "ADDED_CDC_STAGES=$index source=[lindex $expected_signals $index] stages=$meta,$sync functional_fanout_unchanged=1"
}
if {[llength [get_cells -hier -filter {IS_PRIMITIVE == 1}]] != $initial_primitive_count + 14} {
    error "Unexpected primitive count change (expected 12 FDRE + GND/VCC)"
}
source [file join $task_dir vio_status_cdc.xdc]
write_checkpoint -force [file join $out_dir cdc_edited.dcp]
report_drc -file [file join $out_dir drc_before_incremental_route.rpt]
# Vivado automatically selects incremental ECO placement/routing on an
# implemented checkpoint that has been edited; existing work is reused.
place_design
route_design
source [file join $task_dir finish_vio_cdc.tcl]
