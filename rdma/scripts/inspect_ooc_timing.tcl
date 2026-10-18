# SPDX-License-Identifier: BSD-2-Clause-Views
# Read-only diagnosis of an existing integrity-block routed checkpoint.
# Internal-only slacks are diagnostic, NEVER a replacement for the complete
# timing gate. In particular, OOC ports have no actual surrounding registers
# or top-level clock tree; retain those failing paths in the overall result.
if {[llength $argv]!=1} {error "Usage: vivado -mode batch -source inspect_ooc_timing.tcl -tclargs ROUTED_DCP"}
set checkpoint [file normalize [lindex $argv 0]]
if {![file isfile $checkpoint]} {error "Checkpoint missing"}
open_checkpoint $checkpoint
set registers [all_registers]
if {![llength $registers]} {error "No sequential endpoints"}
foreach kind {max min} {
    set paths [get_timing_paths -delay_type $kind -from $registers -to $registers -max_paths 1 -quiet]
    if {![llength $paths]} {error "Missing internal $kind timing evidence"}
    set path [lindex $paths 0]
    puts "INTERNAL_ONLY TYPE=$kind SLACK_NS=[get_property SLACK $path] SOURCE=[get_property STARTPOINT_PIN $path] DEST=[get_property ENDPOINT_PIN $path]"
}
set input_hold 0
set other_hold 0
foreach path [get_timing_paths -delay_type min -max_paths 1000 -slack_lesser_than 0 -quiet] {
    set source [get_property STARTPOINT_PIN $path]
    if {[llength [get_ports -quiet $source]]} {incr input_hold} else {incr other_hold}
}
puts "HOLD_DIAG INPUT_PORT_PATHS=$input_hold OTHER_PATHS=$other_hold (up to 1000 worst endpoints)"
report_timing -delay_type max -max_paths 3
report_timing -delay_type min -max_paths 3
exit
