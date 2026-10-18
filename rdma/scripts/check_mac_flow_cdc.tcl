# SPDX-License-Identifier: BSD-2-Clause-Views
# Validate the narrowly scoped annotation on a disposable in-memory copy of
# an old checkpoint. No placement/routing/checkpoint write or hardware access.
if {[llength $argv] < 2 || [llength $argv] > 3 ||
    ([llength $argv] == 3 && [lindex $argv 2] ne "--negative-controls")} {
    error "Usage: check_mac_flow_cdc.tcl BOARD_DCP NEW_OUTPUT_PREFIX ?--negative-controls?"
}
set root [file normalize [file join [file dirname [info script]] ../..]]
set checkpoint [file normalize [lindex $argv 0]]
set prefix [file normalize [lindex $argv 1]]
if {![file isfile $checkpoint]} {error "Missing checkpoint"}
if {[llength [glob -nocomplain ${prefix}_*]]} {error "Preserve existing diagnosis: use a new prefix"}
file mkdir [file dirname $prefix]
open_checkpoint $checkpoint
if {[get_property PART [current_design]] ne "xcku3p-ffvb676-1-e" ||
    [get_property TOP [current_design]] ne "fpga"} {error "Expected audited full board"}
set verifier [file join $root fpga/verify_mac_flow_control_cdc.tcl]
set negative_controls_checked 0
if {[llength $argv] == 3} {
    # This option needs the original DCP with no LFC false-path correction.
    # Annotate the existing flops but deliberately omit the first-D cuts.
    set destination [get_cells -hier -regexp {^core_inst/mac\[[01]\]\.eth_mac_inst/mac_ctrl\.(tx_lfc_req|rx_lfc_ack)_sync_reg_[23]_reg$}]
    if {[llength $destination] != 8} {error "Missing negative-control registers"}
    set_property ASYNC_REG TRUE $destination
    if {![catch {source $verifier} message] ||
        ![string match {LFC first destination D does not have the required false path:*} $message]} {
        error "Verifier failed to reject missing first-D exceptions: $message"
    }
    incr negative_controls_checked
    puts "MAC_LFC_NEGATIVE_CONTROL MISSING_FIRST_CUT_REJECTED=1"
}
read_xdc [file join $root fpga/mac_flow_control_cdc.xdc]
set verification_failed [catch {source $verifier} verification_message]
if {$verification_failed} {puts "MAC_LFC_ANNOTATION_CHECK ASSERTION_FAILED=$verification_message"}
report_cdc -details -file ${prefix}_cdc.rpt
report_methodology -file ${prefix}_methodology.rpt
report_exceptions -file ${prefix}_exceptions.rpt
if {[llength $argv] == 3 && !$verification_failed} {
    # Save only clean-annotation reports above. Deliberately over-cut one
    # second stage in this disposable copy; never write a checkpoint/image.
    set second [get_cells -hier -filter {NAME == "core_inst/mac[0].eth_mac_inst/mac_ctrl.tx_lfc_req_sync_reg_3_reg"}]
    set_false_path -to [get_pins -of_objects $second -filter {REF_PIN_NAME == D}]
    if {![catch {source $verifier} message] ||
        ![string match {LFC second-stage path was excluded or unconstrained:*} $message]} {
        error "Verifier failed to reject an over-broad second-stage cut: $message"
    }
    incr negative_controls_checked
    puts "MAC_LFC_NEGATIVE_CONTROL SECOND_STAGE_CUT_REJECTED=1 COPY_DISCARDED=1"
}
puts "MAC_LFC_ANNOTATION_CHECK REPORTS_COMPLETE=1 ASSERTION_FAILED=$verification_failed NEGATIVE_CONTROLS_CHECKED=$negative_controls_checked NEW_PLACEMENT_VERIFIED=0 FINAL_PHYSICAL_GATE=0 HARDWARE_VERIFIED=0"
close_design
exit $verification_failed
