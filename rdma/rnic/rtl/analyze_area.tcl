# SPDX-License-Identifier: BSD-2-Clause-Views
# Read-only hierarchical resource diagnosis of an existing checkpoint.
# No constraint/netlist/checkpoint mutation and no hardware access.
if {[llength $argv]!=2} {error "Usage: analyze_area.tcl CHECKPOINT NEW_REPORT_DIR"}
set checkpoint [file normalize [lindex $argv 0]]
set output [file normalize [lindex $argv 1]]
if {![file isfile $checkpoint] || [file exists $output]} {error "Require existing checkpoint/new reports"}
set script [file normalize [info script]]
set before [exec sha256sum $checkpoint $script]
file mkdir $output
set fd [open [file join $output inputs.sha256] w]
puts $fd $before
close $fd
open_checkpoint $checkpoint
report_utilization -hierarchical -hierarchical_depth 6 -file [file join $output hierarchy.rpt]
exec sha256sum --check --status [file join $output inputs.sha256]
puts "RNIC_AREA_AUDIT CHECKPOINT_UNCHANGED=1 ANALYSIS_ONLY=1 PHYSICAL_SIGNOFF=0"
close_design
exit
