# SPDX-License-Identifier: BSD-2-Clause-Views
# Copyright (c) 2026 jyohukuchan
# Procedural design assertions belong in Tcl, not restricted XDC syntax.
proc verify_vio_status_cdc {} {
    set meta [get_cells -hier -regexp {.*vio_status_meta_reg_reg\[[0-5]\]}]
    set sync [get_cells -hier -regexp {.*vio_status_sync_reg_reg\[[0-5]\]}]
    if {[llength $meta] != 6 || [llength $sync] != 6} {
        error "Expected six complete two-stage VIO status synchronizers"
    }
    foreach cell [concat $meta $sync] {
        if {![string is true -strict [get_property ASYNC_REG $cell]]} {
            error "Missing ASYNC_REG on $cell"
        }
    }
    for {set i 0} {$i < 6} {incr i} {
        set first [get_cells [format {vio_status_meta_reg_reg[%d]} $i]]
        set second [get_cells [format {vio_status_sync_reg_reg[%d]} $i]]
        set first_q [get_nets -of_objects [get_pins -of_objects $first -filter {REF_PIN_NAME == Q}]]
        set second_d [get_nets -of_objects [get_pins -of_objects $second -filter {REF_PIN_NAME == D}]]
        if {![llength $first_q] || ![llength $second_d] ||
            [lsort [get_property NAME [get_nets -segments $first_q]]] ne
            [lsort [get_property NAME [get_nets -segments $second_d]]]} {
            error "VIO status bit $i does not have its expected two-stage connection"
        }
        foreach cell [list $first $second] {
            set clock [get_clocks -of_objects [get_pins -of_objects $cell -filter {REF_PIN_NAME == C}]]
            if {[llength $clock] != 1 || [get_property NAME $clock] ne "pcie_user_clk" ||
                abs([get_property PERIOD $clock] - 4.0) > 0.001} {
                error "Incorrect VIO status synchronizer clock on $cell"
            }
        }
    }
    puts "VERIFIED_VIO_CDC=6 two_stage_pairs ASYNC_REG=1 clock=pcie_user_clk"
}
verify_vio_status_cdc
