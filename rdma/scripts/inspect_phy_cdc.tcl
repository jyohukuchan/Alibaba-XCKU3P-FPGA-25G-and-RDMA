# SPDX-License-Identifier: BSD-2-Clause-Views
# Read-only board-checkpoint inspection of the inherited PHY/DRP CDCs.
# No constraint edits, design changes, placement, checkpoint/image write or
# hardware access. This does not waive findings or prove runtime stability.
if {[llength $argv] != 2} {
    error "Usage: inspect_phy_cdc.tcl BOARD_DCP NEW_OUTPUT_PREFIX"
}
set checkpoint [file normalize [lindex $argv 0]]
set prefix [file normalize [lindex $argv 1]]
if {![file isfile $checkpoint]} {error "Missing full board checkpoint"}
if {[llength [glob -nocomplain ${prefix}_*]]} {error "Preserve existing inspection: use a new prefix"}
file mkdir [file dirname $prefix]
open_checkpoint $checkpoint
if {[get_property PART [current_design]] ne "xcku3p-ffvb676-1-e" ||
    [get_property TOP [current_design]] ne "fpga"} {error "Expected audited full board"}

proc phy_cell {name} {
    set cell [get_cells -hier -filter [format {NAME == "%s"} $name]]
    if {[llength $cell] != 1} {error "Missing exact PHY/DRP cell: $name"}
    return $cell
}
proc phy_pin {cell ref} {
    set pin [get_pins -of_objects $cell -filter [format {REF_PIN_NAME == "%s"} $ref]]
    if {[llength $pin] != 1} {error "Missing pin $ref at $cell"}
    return $pin
}
proc phy_clock {cell period} {
    set clock [get_clocks -of_objects [phy_pin $cell C]]
    if {[llength $clock] != 1 || abs([get_property PERIOD $clock] - $period) > 0.001} {
        error "Unexpected PHY/DRP clock at $cell"
    }
    return $clock
}
proc phy_nets {pin} {
    set nets [get_nets -segments -of_objects $pin]
    if {![llength $nets]} {error "Disconnected PHY pin: $pin"}
    return $nets
}
proc phy_direct {src dst} {
    if {[lsort [get_property NAME [phy_nets [phy_pin $src Q]]]] ne
        [lsort [get_property NAME [phy_nets [phy_pin $dst D]]]]} {
        error "Expected direct register connection: $src -> $dst"
    }
}
proc phy_constant {pin expected} {
    set drivers [get_pins -of_objects [phy_nets $pin] -filter {IS_LEAF && DIRECTION == OUT}]
    set cells [get_cells -of_objects $drivers]
    if {[llength $cells] != 1 || [get_property REF_NAME $cells] ne $expected} {
        error "Expected $expected constant driver at $pin; got $cells"
    }
    puts "PHY_CONSTANT PIN=$pin DRIVER=$cells PRIMITIVE=[get_property REF_NAME $cells]"
}
proc phy_max_datapath {src dst period} {
    set path [get_timing_paths -delay_type max -no_report_unconstrained -from $src -to $dst -max_paths 1]
    # The path property spells out the applied command/value, unlike the
    # shorter "Max Delay Datapath Only" category in report_cdc.
    set expected_exception [format {MaxDelay Path %.3fns -datapath_only} $period]
    if {[llength $path] != 1 ||
        [get_property EXCEPTION $path] ne $expected_exception ||
        ![string is double -strict [get_property SLACK $path]] ||
        abs([get_property REQUIREMENT $path] - $period) > 0.001 ||
        [get_property SLACK $path] < 0} {
        if {[llength $path]} {report_property -all $path}
        error "Missing/unmet scoped max-delay-datapath-only constraint: $src -> $dst"
    }
    puts "PHY_SCOPED_MAX FROM=$src TO=$dst REQUIREMENT_NS=[get_property REQUIREMENT $path] SLACK_NS=[get_property SLACK $path] EXCEPTION=[get_property EXCEPTION $path]"
}

puts "PHY_CDC_INSPECT CHECKPOINT=$checkpoint READ_ONLY_DESIGN=1 HARDWARE_VERIFIED=0"
set channels [get_cells -hier -filter {REF_NAME == GTYE4_CHANNEL && NAME =~ sfp_phy_quad_inst/*}]
if {[llength $channels] != 2} {error "Expected two physical GTYE4 Ethernet channels"}
foreach channel $channels {
    # UG578 Table 3-39: mode 1 permits asynchronous TXELECIDLE/TXPD.
    phy_constant [phy_pin $channel TXPDELECIDLEMODE] VCC
    puts "PHY_GT_ASYNC_CONTROL CHANNEL=$channel LOC=[get_property LOC $channel] MODE_PIN_TIED_HIGH=1 CDC13_ENDPOINTS=3"
}

set rb core_inst/sfp_rb_drp_inst
set rb_we [phy_cell $rb/rb_we_reg_reg]
set drp_we [phy_cell $rb/drp_we_reg_reg]
phy_clock $rb_we 4.0
phy_clock $drp_we 8.0
phy_max_datapath $rb_we $drp_we 8.0
report_timing -delay_type max -from $rb_we -to $drp_we -max_paths 1 -file ${prefix}_drp_we.rpt
set request [phy_cell $rb/rb_flag_reg_reg]
set req_meta [phy_cell $rb/rb_flag_sync_reg_1_reg]
set req_sync [phy_cell $rb/rb_flag_sync_reg_2_reg]
phy_clock $request 4.0
foreach cell [list $req_meta $req_sync] {
    phy_clock $cell 8.0
    if {![string is true -strict [get_property ASYNC_REG $cell]]} {error "Missing DRP request ASYNC_REG"}
}
phy_direct $request $req_meta
phy_direct $req_meta $req_sync
phy_max_datapath $request $req_meta 8.0
puts "PHY_DRP_BUNDLE REQUEST_STAGES=2 WE_DATAPATH_MAX_NS=8 SOURCE_HOLD_HANDSHAKE_REQUIRES_RTL_REVIEW=1 FINAL_BUS_SKEW_REVIEW_REQUIRED=1"

set config_bits 0
foreach port {1 2} {
    set inst [format {sfp_phy_quad_inst/phy%d.eth_xcvr_phy_%d} $port $port]
    foreach {signal width domain} {gt_txinhibit 1 tx gt_txpolarity 1 tx gt_rxpolarity 1 rx gt_txprbssel 4 tx gt_rxprbssel 4 rx} {
        for {set bit 0} {$bit < $width} {incr bit} {
            set suffix [expr {$width == 1 ? "" : [format {[%d]} $bit]}]
            set src [phy_cell ${inst}/${signal}_drp_reg_reg${suffix}]
            set dst [phy_cell ${inst}/${signal}_sync_reg_reg${suffix}]
            phy_clock $src 8.0
            phy_clock $dst 2.56
            phy_direct $src $dst
            phy_max_datapath $src $dst 8.0
            puts "PHY_STATIC_CONFIG PORT=$port SIGNAL=$signal BIT=$bit DOMAIN=$domain SOURCE_INIT=[get_property INIT $src] DEST_INIT=[get_property INIT $dst] DESTINATION_STAGES=1 RUNTIME_STABILITY_PROVEN=0"
            incr config_bits
        }
    }
}
if {$config_bits != 22} {error "Expected 22 static-control bits across ten grouped CDC findings"}

set reset_inst sfp_phy_quad_inst/phy1.eth_xcvr_phy_1/sync_reset_common_reset_inst
set source_reset [phy_cell {sfp_sync_reset_inst/sync_reg_reg[3]}]
set previous {}
set common_presets {}
foreach stage {0 1 2 3} {
    set cell [phy_cell [format {%s/sync_reg_reg[%d]} $reset_inst $stage]]
    phy_clock $cell 8.0
    if {![string is true -strict [get_property ASYNC_REG $cell]]} {error "Missing PHY reset ASYNC_REG"}
    if {$stage == 0} {phy_constant [phy_pin $cell D] GND} else {phy_direct $previous $cell}
    set pre [phy_pin $cell PRE]
    set nets [lsort [get_property NAME [phy_nets $pre]]]
    if {$stage > 0 && $nets ne $common_presets} {error "PHY reset stages do not share their asynchronous preset"}
    set common_presets $nets
    set ignored [get_timing_paths -delay_type max -user_ignored -from $source_reset -to $pre -max_paths 1]
    if {[llength $ignored] != 1 || [get_property EXCEPTION $ignored] ne "False Path"} {
        error "Missing exact asynchronous-reset preset exception at $pre"
    }
    puts "PHY_RESET_STAGE STAGE=$stage CELL=$cell INIT=[get_property INIT $cell] ASYNC_REG=1 PRESET_EXCEPTED=1"
    set previous $cell
}
puts "PHY_CDC_INSPECT COMPLETE=1 GT_ASYNC_MODE_PINS=2 STATIC_CONFIG_BITS=22 RESET_STAGES=4 RUNTIME_STABILITY_PROVEN=0 ALL_CDC_SAFE=0 FINAL_PHYSICAL_GATE=0 HARDWARE_VERIFIED=0"
close_design
exit
