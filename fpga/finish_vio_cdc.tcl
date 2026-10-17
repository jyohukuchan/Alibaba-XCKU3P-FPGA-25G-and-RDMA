# SPDX-License-Identifier: BSD-2-Clause-Views
# Copyright (c) 2026 jyohukuchan
# Finish an already edited/placed CDC ECO. Keeps its in-memory fanout
# invariants and probe_changes table; never re-adds cells or resets a run.
# modify_debug_ports requires a fully routed design before it can swap probes.
modify_debug_ports -probes $probe_changes
for {set index 0} {$index < 6} {incr index} {
    set meta [format {vio_status_meta_reg_reg[%d]} $index]
    set sync_net [format {vio_status_sync_%d} $index]
    set probe [get_pins vio_status_inst/probe_in$index]
    set new_probe_net [get_nets -of_objects $probe]
    if {[lsort [get_property NAME [get_nets -segments $new_probe_net]]] ne [lsort [get_property NAME [get_nets -segments $sync_net]]]} {
        error "Probe $index was not moved to the second synchronizer stage"
    }
    set observed [non_debug_leaf_pins $source_nets($index)]
    set expected [lsort -unique [concat $preserved_pins($index) [list $meta/D]]]
    if {$observed ne $expected} {error "Functional source fanout changed for probe $index"}
    puts "VERIFIED_CDC_PROBE=$index two_stages=1 functional_fanout_unchanged=1"
}
route_design
phys_opt_design -directive AggressiveExplore
report_route_status -file [file join $out_dir route_status.rpt]
report_utilization -file [file join $out_dir utilization.rpt]
report_clocks -file [file join $out_dir clocks.rpt]
report_timing_summary -delay_type min_max -report_unconstrained -file [file join $out_dir timing_summary.rpt]
report_timing -delay_type max -max_paths 20 -file [file join $out_dir setup_paths.rpt]
report_timing -delay_type min -max_paths 20 -file [file join $out_dir hold_paths.rpt]
check_timing -verbose -file [file join $out_dir check_timing.rpt]
report_bus_skew -file [file join $out_dir bus_skew.rpt]
report_cdc -details -file [file join $out_dir cdc.rpt]
report_drc -file [file join $out_dir drc.rpt]
write_checkpoint -force [file join $out_dir as02mc04_25g_routed.dcp]
foreach direction {TXOUTCLK RXOUTCLK} {
    set pins [get_pins -hier -filter "NAME =~ sfp_phy_quad_inst/* && REF_PIN_NAME == $direction"]
    if {[llength $pins] != 2} {error "Expected two Ethernet $direction pins"}
    foreach pin $pins {
        set clocks [get_clocks -of_objects $pin]
        if {[llength $clocks] != 1 || abs([get_property PERIOD $clocks] - 2.56) > 0.001} {
            error "Incorrect native 25G timing clock at $pin"
        }
    }
}
foreach type {max min} {
    if {![llength [get_timing_paths -delay_type $type -max_paths 1]]} {error "No timed $type paths"}
    if {[llength [get_timing_paths -delay_type $type -slack_lesser_than 0 -max_paths 1]]} {
        error "Timing failed ($type); refusing bitstream output"
    }
}
set fd [open [file join $out_dir timing_summary.rpt] r]
set timing_text [read $fd]
close $fd
if {![string match {*All user specified timing constraints are met.*} $timing_text]} {
    error "Full timing summary did not pass; refusing bitstream output"
}
if {[llength [get_drc_violations -filter {SEVERITY == "Error" || SEVERITY == "Critical Warning"}]]} {
    error "DRC has errors/critical warnings; refusing bitstream output"
}
write_bitstream -force [file join $out_dir as02mc04_25g.bit]
write_debug_probes -force [file join $out_dir as02mc04_25g.ltx]
puts "BUILD COMPLETE (VIO CDC ECO): [file join $out_dir as02mc04_25g.bit]"
puts "Hardware remains unchanged; bus-skew/CDC reports require review before programming."
close_design
