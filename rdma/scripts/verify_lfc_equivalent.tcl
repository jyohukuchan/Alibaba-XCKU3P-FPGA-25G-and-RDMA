# SPDX-License-Identifier: BSD-2-Clause-Views
# Candidate assertion revision, separate from the frozen live-build verifier.
# No design/constraint/property changes and no hardware access. A structural
# pass is not physical timing acceptance. Do not automatically release an image.
proc mac_lfc_source_allowed {port signal source} {
    if {$port ni {0 1} || $signal ni {tx_lfc_req rx_lfc_ack}} {return 0}
    set original [format {core_inst/mac[%d].eth_mac_inst/mac_ctrl.%s_sync_reg_1_reg} $port $signal]
    if {$source eq $original} {return 1}
    # Only this additional source was audited against the linked candidate
    # and pinned RTL with board MAC_CTRL_ENABLE=0, identical RX clk/rst/input.
    return [expr {$port == 1 && $signal eq "tx_lfc_req" &&
        $source eq {core_inst/core_inst/core_pcie_inst/core_inst/iface[1].interface_inst/port[0].port_inst/rx_lfc_req_sync_1_reg_reg}}]
}

proc verify_mac_lfc_equivalent {} {
    set annotated [get_cells -hier -regexp {^core_inst/mac\[[01]\]\.eth_mac_inst/mac_ctrl\.(tx_lfc_req|rx_lfc_ack)_sync_reg_[23]_reg$}]
    if {[llength $annotated] != 8} {error "LFC_EQ_EXPECTED_EIGHT_DESTINATIONS"}
    set aliases 0
    foreach port {0 1} {
        set suffix [expr {$port == 0 ? "" : "_1"}]
        set rx_clock [format {gtwiz_userclk_rx_srcclk_out[0]%s} $suffix]
        set tx_clock [format {gtwiz_userclk_tx_srcclk_out[0]%s} $suffix]
        foreach signal {tx_lfc_req rx_lfc_ack} {
            set destinations {}
            foreach stage {2 3} {
                set name [format {core_inst/mac[%d].eth_mac_inst/mac_ctrl.%s_sync_reg_%d_reg} $port $signal $stage]
                set cell [get_cells -hier -filter [format {NAME == "%s"} $name]]
                if {[llength $cell] != 1} {error "LFC_EQ_MISSING_DESTINATION: $name"}
                if {![string is true -strict [get_property ASYNC_REG $cell]]} {error "LFC_EQ_MISSING_ASYNC_REG: $name"}
                lappend destinations $cell
            }
            lassign $destinations meta sync
            set meta_d [get_pins -of_objects $meta -filter {REF_PIN_NAME == D}]
            set drivers [get_pins -of_objects [get_nets -segments -of_objects $meta_d] -filter {IS_LEAF && DIRECTION == OUT}]
            set first [get_cells -of_objects $drivers]
            if {[llength $drivers] != 1 || [llength $first] != 1 ||
                [get_property REF_PIN_NAME $drivers] ne "Q" ||
                ![mac_lfc_source_allowed $port $signal [get_property NAME $first]]} {
                error "LFC_EQ_UNAUDITED_SOURCE: port=$port signal=$signal driver=$drivers"
            }
            set original [format {core_inst/mac[%d].eth_mac_inst/mac_ctrl.%s_sync_reg_1_reg} $port $signal]
            if {[get_property NAME $first] ne $original} {incr aliases}
            set expected_source [expr {$signal eq "tx_lfc_req" ? $rx_clock : $tx_clock}]
            set expected_destination [expr {$signal eq "tx_lfc_req" ? $tx_clock : $rx_clock}]
            foreach cell [list $first $meta $sync] expected [list $expected_source $expected_destination $expected_destination] {
                if {[get_property REF_NAME $cell] ne "FDCE" || [get_property INIT $cell] ne "1'b0"} {
                    error "LFC_EQ_WRONG_REGISTER: $cell"
                }
                set clock [get_clocks -of_objects [get_pins -of_objects $cell -filter {REF_PIN_NAME == C}]]
                if {[llength $clock] != 1 || [get_property NAME $clock] ne $expected ||
                    abs([get_property PERIOD $clock] - 2.56) > 0.001} {
                    error "LFC_EQ_WRONG_NATIVE_CLOCK: $cell expected=$expected"
                }
            }
            foreach src [list $first $meta] dst [list $meta $sync] {
                set q [get_nets -segments -of_objects [get_pins -of_objects $src -filter {REF_PIN_NAME == Q}]]
                set d [get_nets -segments -of_objects [get_pins -of_objects $dst -filter {REF_PIN_NAME == D}]]
                if {![llength $q] || ![llength $d] ||
                    [lsort [get_property NAME $q]] ne [lsort [get_property NAME $d]]} {
                    error "LFC_EQ_NOT_DIRECT: $src -> $dst"
                }
            }
            set meta_reset [get_nets -segments -of_objects [get_pins -of_objects $meta -filter {REF_PIN_NAME == CLR}]]
            set sync_reset [get_nets -segments -of_objects [get_pins -of_objects $sync -filter {REF_PIN_NAME == CLR}]]
            if {![llength $meta_reset] || ![llength $sync_reset] ||
                [lsort [get_property NAME $meta_reset]] ne [lsort [get_property NAME $sync_reset]]} {
                error "LFC_EQ_DIFFERENT_DESTINATION_RESETS"
            }
            foreach kind {max min} {
                set ignored [get_timing_paths -delay_type $kind -user_ignored -from $first -to $meta -max_paths 1]
                if {[llength $ignored] != 1 || [get_property EXCEPTION $ignored] ne "False Path" ||
                    [get_property STARTPOINT_PIN $ignored] ne "${first}/C" ||
                    [get_property ENDPOINT_PIN $ignored] ne "${meta}/D"} {
                    error "LFC_EQ_MISSING_FIRST_FALSE_PATH: $first -> $meta ($kind)"
                }
                set timed [get_timing_paths -delay_type $kind -no_report_unconstrained -from $meta -to $sync -max_paths 1]
                if {[llength $timed] != 1 || ![string is double -strict [get_property SLACK $timed]] ||
                    abs([get_property SLACK $timed]) >= 1.0e6 || [get_property EXCEPTION $timed] ne "" ||
                    [get_property STARTPOINT_PIN $timed] ne "${meta}/C" ||
                    [get_property ENDPOINT_PIN $timed] ne "${sync}/D" ||
                    [llength [get_timing_paths -delay_type $kind -user_ignored -from $meta -to $sync -max_paths 1]]} {
                    error "LFC_EQ_SECOND_STAGE_NOT_TIMED: $meta -> $sync ($kind)"
                }
                puts "VERIFIED_LFC_EQ_PATH PORT=$port SIGNAL=$signal TYPE=$kind SOURCE=$first SECOND_SLACK=[get_property SLACK $timed]"
            }
        }
    }
    puts "VERIFIED_LFC_EQ_CDC CHAINS=4 DEST_REGISTERS=8 AUDITED_SOURCE_ALIASES=$aliases CLOCKS_AND_RESETS_VERIFIED=1 FIRST_D_ONLY=1 SECOND_STAGE_TIMED=1 FINAL_PHYSICAL_GATE=0"
    return [dict create chains 4 destination_registers 8 audited_source_aliases $aliases]
}
