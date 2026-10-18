# SPDX-License-Identifier: BSD-2-Clause-Views
# Copyright (c) 2026 jyohukuchan
# Completeness checks only: never execute Vivado/OpenOCD commands.
set root [file normalize [file join [file dirname [info script]] ..]]
set count 0
foreach pattern {fpga/*.tcl fpga/*.xdc scripts/*.cfg tests/*.tcl rdma/hls/probe/*.tcl rdma/scripts/*.tcl rdma/fpga/*.tcl} {
    foreach path [glob -directory $root $pattern] {
        set fd [open $path r]
        set contents [read $fd]
        close $fd
        if {![info complete $contents]} {error "Incomplete Tcl syntax: $path"}
        incr count
    }
}
puts "Tcl completeness checks passed: $count files (not Vivado elaboration)."
