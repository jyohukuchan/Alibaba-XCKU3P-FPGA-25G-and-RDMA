# SPDX-License-Identifier: BSD-2-Clause-Views
# Read-only diagnosis of an existing complete board checkpoint. Never alter
# clocks, exceptions, design cells, routes or the saved checkpoint. Reports
# are not a replacement for final full-board timing/CDC/hardware review.
if {[llength $argv] != 2} {
    error "Usage: vivado -mode batch -source inspect_board_clocks.tcl -tclargs BOARD_DCP OUTPUT_PREFIX"
}
set checkpoint [file normalize [lindex $argv 0]]
set prefix [file normalize [lindex $argv 1]]
if {![file isfile $checkpoint]} {error "Complete board checkpoint is required"}
file mkdir [file dirname $prefix]
if {[llength [glob -nocomplain ${prefix}_*]]} {error "Diagnostic output prefix already exists; preserve prior evidence"}
open_checkpoint $checkpoint
if {[get_property PART [current_design]] ne "xcku3p-ffvb676-1-e" ||
    [get_property TOP [current_design]] ne "fpga"} {
    error "Expected the audited full-board design"
}
puts "BOARD_CLOCK_DIAG CHECKPOINT=$checkpoint READ_ONLY_DESIGN=1 FINAL_GATE=0"
report_clock_interaction -delay_type min_max -file ${prefix}_interaction.rpt
report_timing -delay_type max -max_paths 10 -file ${prefix}_setup.rpt
report_timing -delay_type min -max_paths 10 -file ${prefix}_hold.rpt
foreach kind {max min} {
    set paths [get_timing_paths -delay_type $kind -max_paths 1 -quiet]
    if {![llength $paths]} {error "Missing full-board $kind path evidence"}
    set path [lindex $paths 0]
    puts "BOARD_CLOCK_DIAG TYPE=$kind SLACK_NS=[get_property SLACK $path] SOURCE=[get_property STARTPOINT_PIN $path] DEST=[get_property ENDPOINT_PIN $path]"
}
set channel 0
foreach suffix {{} _1} {
    set rx_name [format {gtwiz_userclk_rx_srcclk_out[0]%s} $suffix]
    set tx_name [format {gtwiz_userclk_tx_srcclk_out[0]%s} $suffix]
    set rx [get_clocks -quiet -filter [format {NAME == "%s"} $rx_name]]
    set tx [get_clocks -quiet -filter [format {NAME == "%s"} $tx_name]]
    if {[llength $rx] != 1 || [llength $tx] != 1} {
        error "Expected exact RX/TX clock pair for channel $channel"
    }
    foreach direction {rx_to_tx tx_to_rx} {
        if {$direction eq "rx_to_tx"} {set src $rx; set dst $tx} else {set src $tx; set dst $rx}
        foreach kind {max min} {
            set paths [get_timing_paths -delay_type $kind -from $src -to $dst -max_paths 10 -quiet]
            puts "BOARD_CLOCK_PAIR CHANNEL=$channel DIRECTION=$direction TYPE=$kind PATHS=[llength $paths]"
            report_timing -delay_type $kind -from $src -to $dst -max_paths 10 \
                -file ${prefix}_ch${channel}_${direction}_${kind}.rpt
        }
    }
    incr channel
}
report_exceptions -file ${prefix}_exceptions.rpt
report_cdc -details -file ${prefix}_cdc.rpt
puts "BOARD_CLOCK_DIAG COMPLETE=1 HARDWARE_VERIFIED=0 FINAL_GATE=0"
close_design
exit
