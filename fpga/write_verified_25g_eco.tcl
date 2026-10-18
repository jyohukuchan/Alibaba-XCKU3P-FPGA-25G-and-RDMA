# SPDX-License-Identifier: BSD-2-Clause-Views
# Copyright (c) 2026 jyohukuchan
# Final output gate for an already refined, routed native-25G CDC ECO.
# Does not program any hardware. Do not source until CDC review is complete.
if {![info exists out_dir] || ![info exists refine_label] ||
    [get_property PART [current_design]] ne "xcku3p-ffvb676-1-e" ||
    [get_property TOP [current_design]] ne "fpga"} {
    error "Expected the inspected native-25G CDC ECO"
}
set final_prefix ${refine_label}_final
source [file join [file dirname [file normalize [info script]]] verify_vio_status_cdc.tcl]
if {[info exists roce_enabled] && $roce_enabled} {
    set source_identity [file join $out_dir rocev2-source-identity.txt]
    if {![file isfile $source_identity] ||
        [catch {exec sha256sum --check --status $source_identity}]} {
        error "RoCE build inputs changed or manifest is missing; refusing bitstream output"
    }
    puts "VERIFIED_ROCE_BUILD_INPUTS_UNCHANGED=1"
    source [file join [file dirname [file normalize [info script]]] verify_mac_flow_control_cdc.tcl]
}
foreach direction {TXOUTCLK RXOUTCLK} {
    set pins [get_pins -hier -filter "NAME =~ sfp_phy_quad_inst/* && REF_PIN_NAME == $direction"]
    if {[llength $pins] != 2} {error "Expected two Ethernet $direction pins"}
    foreach pin $pins {
        set clocks [get_clocks -of_objects $pin]
        if {[llength $clocks] != 1 || abs([get_property PERIOD $clocks] - 2.56) > 0.001} {
            error "Native 25G clock check failed at $pin"
        }
    }
}
foreach type {max min} {
    if {![llength [get_timing_paths -delay_type $type -max_paths 1]] ||
        [llength [get_timing_paths -delay_type $type -slack_lesser_than 0 -max_paths 1]]} {
        error "Timing gate failed ($type); refusing bitstream output"
    }
}
report_timing_summary -delay_type min_max -report_unconstrained -file [file join $out_dir ${final_prefix}_timing_summary.rpt]
set fd [open [file join $out_dir ${final_prefix}_timing_summary.rpt] r]
set final_timing [read $fd]
close $fd
if {![string match {*All user specified timing constraints are met.*} $final_timing]} {
    error "Full final timing summary did not pass"
}
report_route_status -file [file join $out_dir ${final_prefix}_route_status.rpt]
set fd [open [file join $out_dir ${final_prefix}_route_status.rpt] r]
set final_route [read $fd]
close $fd
if {![regexp {# of routable nets[.]+[[:space:]]*:[[:space:]]*([0-9]+)} $final_route -> routable] ||
    ![regexp {# of fully routed nets[.]+[[:space:]]*:[[:space:]]*([0-9]+)} $final_route -> routed] ||
    ![regexp {# of nets with routing errors[.]+[[:space:]]*:[[:space:]]*([0-9]+)} $final_route -> route_errors] ||
    $routable != $routed || $route_errors != 0} {
    error "Not all native-25G nets are fully routed without errors"
}
report_bus_skew -file [file join $out_dir ${final_prefix}_bus_skew.rpt]
set fd [open [file join $out_dir ${final_prefix}_bus_skew.rpt] r]
set final_skew [read $fd]
close $fd
set skew_count 0
foreach line [split $final_skew \n] {
    if {[string match {Slack (*} $line]} {
        if {![regexp {^Slack \(MET\)[[:space:]]*:[[:space:]]*([0-9]+\.[0-9]+)ns} $line -> slack] || $slack < 0} {
            error "Unmet/unknown bus-skew requirement: $line"
        }
        incr skew_count
    }
}
if {$skew_count != 38} {error "Expected all 38 bus-skew constraints, found $skew_count"}
report_drc -file [file join $out_dir ${final_prefix}_drc.rpt]
if {[llength [get_drc_violations -filter {SEVERITY == "Error" || SEVERITY == "Critical Warning"}]]} {
    error "Final DRC has errors/critical warnings"
}
write_bitstream -force [file join $out_dir as02mc04_25g.bit]
write_debug_probes -force [file join $out_dir as02mc04_25g.ltx]
puts "VERIFIED_NATIVE_25G_BITSTREAM=[file join $out_dir as02mc04_25g.bit]"
puts "Final static gate passed. This newly generated image still requires hardware validation."
