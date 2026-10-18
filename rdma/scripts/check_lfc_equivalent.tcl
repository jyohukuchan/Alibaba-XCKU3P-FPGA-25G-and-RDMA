# SPDX-License-Identifier: BSD-2-Clause-Views
# Positive/negative assertion tests on disposable checkpoint copies only.
# Never write a DCP/image or access hardware. The positive compiled-mode
# check does not add XDC; intentional faults are injected after clean reports.
if {[llength $argv] != 4 || [lindex $argv 2] ni {compiled annotate} ||
    [lindex $argv 3] ni {0 1}} {
    error "Usage: check_lfc_equivalent.tcl BOARD_DCP NEW_PREFIX compiled|annotate EXPECTED_ALIAS_COUNT"
}
set root [file normalize [file join [file dirname [info script]] ../..]]
set checkpoint [file normalize [lindex $argv 0]]
set prefix [file normalize [lindex $argv 1]]
set mode [lindex $argv 2]
set expected_aliases [lindex $argv 3]
if {![file isfile $checkpoint]} {error "Missing checkpoint"}
if {[llength [glob -nocomplain ${prefix}_*]]} {error "Preserve prior reports: use a new prefix"}
file mkdir [file dirname $prefix]
open_checkpoint $checkpoint
if {[get_property PART [current_design]] ne "xcku3p-ffvb676-1-e" ||
    [get_property TOP [current_design]] ne "fpga"} {error "Expected audited board"}
if {[llength [get_cells -hier -filter {IS_BLACKBOX == 1}]]} {error "Need fully linked checkpoint"}
source [file join $root rdma/scripts/verify_lfc_equivalent.tcl]
proc expect_lfc_failure {pattern label} {
    if {![catch {verify_mac_lfc_equivalent} message] || ![string match $pattern $message]} {
        error "LFC equivalent verifier failed negative control $label: $message"
    }
    puts "LFC_EQ_NEGATIVE_CONTROL $label=1"
}
set negative_controls 0
if {$mode eq "annotate"} {
    # Original uncorrected routed DCP: add only flop annotations first, so
    # the missing first-D exception must still be rejected.
    set destination [get_cells -hier -regexp {^core_inst/mac\[[01]\]\.eth_mac_inst/mac_ctrl\.(tx_lfc_req|rx_lfc_ack)_sync_reg_[23]_reg$}]
    if {[llength $destination] != 8} {error "Missing original destination flops"}
    set_property ASYNC_REG TRUE $destination
    expect_lfc_failure {LFC_EQ_MISSING_FIRST_FALSE_PATH:*} MISSING_FIRST_CUT_REJECTED
    incr negative_controls
    read_xdc [file join $root fpga/mac_flow_control_cdc.xdc]
}
set verification_failed [catch {verify_mac_lfc_equivalent} result]
if {$verification_failed} {
    puts "LFC_EQ_POSITIVE_FAILED=$result"
} elseif {[dict get $result audited_source_aliases] != $expected_aliases} {
    error "Unexpected source-alias count: $result"
}
# Reports describe only the positive design, before deliberate faulty edits.
report_cdc -details -file ${prefix}_cdc.rpt
report_methodology -file ${prefix}_methodology.rpt
report_exceptions -file ${prefix}_exceptions.rpt
if {!$verification_failed} {
    set meta [get_cells -hier -filter {NAME == "core_inst/mac[0].eth_mac_inst/mac_ctrl.tx_lfc_req_sync_reg_2_reg"}]
    set sync [get_cells -hier -filter {NAME == "core_inst/mac[0].eth_mac_inst/mac_ctrl.tx_lfc_req_sync_reg_3_reg"}]
    set previous_async [get_property ASYNC_REG $meta]
    set_property ASYNC_REG FALSE $meta
    expect_lfc_failure {LFC_EQ_MISSING_ASYNC_REG:*} MISSING_ASYNC_REG_REJECTED
    incr negative_controls
    set_property ASYNC_REG $previous_async $meta
    verify_mac_lfc_equivalent
    set_false_path -to [get_pins -of_objects $sync -filter {REF_PIN_NAME == D}]
    expect_lfc_failure {LFC_EQ_SECOND_STAGE_NOT_TIMED:*} SECOND_STAGE_CUT_REJECTED
    incr negative_controls
}
puts "LFC_EQ_CHECK COMPLETE=1 POSITIVE_ANNOTATIONS_VERIFIED=[expr {!$verification_failed}] EXPECTED_ALIASES=$expected_aliases MODE=$mode NEGATIVE_CONTROLS_CHECKED=$negative_controls FINAL_PHYSICAL_GATE=0 HARDWARE_VERIFIED=0 COPY_DISCARDED=1"
close_design
exit $verification_failed
