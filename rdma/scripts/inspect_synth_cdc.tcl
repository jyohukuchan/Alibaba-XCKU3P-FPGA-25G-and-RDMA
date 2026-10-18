# SPDX-License-Identifier: BSD-2-Clause-Views
# Verify annotations already compiled into an immutable, fully linked board
# checkpoint. In the OOC-IP project flow use post-opt or later: a standalone
# top synthesis DCP leaves four IPs unresolved and cannot prove their clocks.
# Unlike check_mac_flow_cdc.tcl, this NEVER reads an additional XDC, changes
# a property/constraint, or writes a checkpoint/image. Not a physical gate.
if {[llength $argv] != 2} {error "Usage: inspect_synth_cdc.tcl BOARD_DCP NEW_OUTPUT_PREFIX"}
set root [file normalize [file join [file dirname [info script]] ../..]]
set checkpoint [file normalize [lindex $argv 0]]
set prefix [file normalize [lindex $argv 1]]
if {![file isfile $checkpoint]} {error "Missing completed board checkpoint"}
if {[llength [glob -nocomplain ${prefix}_*]]} {error "Preserve prior inspection: use a new prefix"}
file mkdir [file dirname $prefix]
open_checkpoint $checkpoint
if {[get_property PART [current_design]] ne "xcku3p-ffvb676-1-e" ||
    [get_property TOP [current_design]] ne "fpga"} {error "Expected audited full board"}
set unresolved [get_cells -hier -filter {IS_BLACKBOX == 1}]
if {[llength $unresolved]} {
    error "Unresolved OOC IPs in checkpoint ($unresolved); use a completed, fully linked post-opt or later board checkpoint"
}
puts "SYNTH_CDC_INSPECT CHECKPOINT=$checkpoint READ_ONLY_DESIGN=1 ADDITIONAL_XDC_LOADED=0"
set vio_failed [catch {source [file join $root fpga/verify_vio_status_cdc.tcl]} vio_message]
set lfc_failed [catch {source [file join $root fpga/verify_mac_flow_control_cdc.tcl]} lfc_message]
if {$vio_failed} {puts "COMPILED_VIO_ASSERTION_FAILED=$vio_message"}
if {$lfc_failed} {puts "COMPILED_LFC_ASSERTION_FAILED=$lfc_message"}
# Report actual first-capture D drivers, even when a named source preregister
# was merged/renamed. Diagnostics only: do not reinterpret a failed assertion
# as success, add exceptions, or change the frozen build's final verifier.
foreach port {0 1} {
    foreach signal {tx_lfc_req rx_lfc_ack} {
        set name [format {core_inst/mac[%d].eth_mac_inst/mac_ctrl.%s_sync_reg_2_reg} $port $signal]
        set meta [get_cells -hier -filter [format {NAME == "%s"} $name]]
        if {[llength $meta] != 1} {puts "COMPILED_LFC_DRIVER PORT=$port SIGNAL=$signal MISSING_META=1"; continue}
        set nets [get_nets -segments -of_objects [get_pins -of_objects $meta -filter {REF_PIN_NAME == D}]]
        set drivers [get_pins -of_objects $nets -filter {IS_LEAF && DIRECTION == OUT}]
        set sources [get_cells -of_objects $drivers]
        foreach src $sources {
            set clocks [get_clocks -of_objects [get_pins -of_objects $src -filter {REF_PIN_NAME == C}]]
            puts "COMPILED_LFC_DRIVER PORT=$port SIGNAL=$signal META=$meta DRIVER=$src DRIVER_PIN=$drivers PRIMITIVE=[get_property REF_NAME $src] SOURCE_CLOCKS=$clocks"
        }
    }
}
report_utilization -file ${prefix}_utilization.rpt
report_cdc -details -file ${prefix}_cdc.rpt
report_methodology -file ${prefix}_methodology.rpt
report_timing_summary -delay_type min_max -report_unconstrained -file ${prefix}_timing_summary.rpt
set failed [expr {$vio_failed || $lfc_failed}]
puts "SYNTH_CDC_INSPECT COMPLETE=1 COMPILED_VIO_LFC_ANNOTATIONS_VERIFIED=[expr {!$failed}] ASSERTION_FAILED=$failed FINAL_PHYSICAL_GATE=0 HARDWARE_VERIFIED=0"
close_design
exit $failed
