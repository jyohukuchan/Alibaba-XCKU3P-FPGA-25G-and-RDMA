# SPDX-License-Identifier: BSD-2-Clause-Views
# Read-only primitive attribution of HLS storage in an existing checkpoint.
# Rebuilt hierarchy totals can include absorbed logic; inspect actual names.
if {[llength $argv] != 2} {
    error "Usage: analyze_hls_storage.tcl CHECKPOINT NEW_REPORT_DIR"
}
set checkpoint [file normalize [lindex $argv 0]]
set output [file normalize [lindex $argv 1]]
if {![file isfile $checkpoint] || [file exists $output]} {
    error "Require existing checkpoint and new report directory"
}
set script [file normalize [info script]]
set before [exec sha256sum $checkpoint $script]
file mkdir $output
set fd [open [file join $output inputs.sha256] w]
puts $fd $before
close $fd
open_checkpoint $checkpoint
set fd [open [file join $output storage.txt] w]
foreach leaf {rt_metaReqFifo_U rx_process2dropFifo_U retrans_meta_table_0_U0} {
    set parents [get_cells -quiet -hier -filter "NAME =~ */$leaf"]
    puts $fd "GROUP $leaf INSTANCES [llength $parents]"
    foreach parent $parents {
        set counts [dict create]
        set samples [dict create]
        set name [get_property NAME $parent]
        set primitives [get_cells -quiet -hier -filter "NAME =~ $name/* && IS_PRIMITIVE"]
        foreach cell $primitives {
            set ref [get_property REF_NAME $cell]
            dict incr counts $ref
            if {![dict exists $samples $ref] || [llength [dict get $samples $ref]] < 12} {
                dict lappend samples $ref [get_property NAME $cell]
            }
        }
        puts $fd "INSTANCE $name PRIMITIVES [llength $primitives]"
        foreach ref [lsort [dict keys $counts]] {
            puts $fd "REF $ref COUNT [dict get $counts $ref]"
            foreach sample [dict get $samples $ref] {puts $fd "  SAMPLE $sample"}
        }
    }
}
close $fd
exec sha256sum --check --status [file join $output inputs.sha256]
puts "RNIC_STORAGE_AUDIT CHECKPOINT_UNCHANGED=1 ANALYSIS_ONLY=1 PHYSICAL_SIGNOFF=0"
close_design
exit
