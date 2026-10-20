# SPDX-License-Identifier: BSD-2-Clause-Views
# Isolated synthesis/resource/retention wiring, NOT full-board physical signoff.
set frozen [file normalize $::env(AS02_POOL_SYNTH_INPUT)]
set output [file normalize $::env(AS02_POOL_SYNTH_OUTPUT)]
if {[file exists $output]} {error "Preserve earlier output"}
file mkdir $output
cd $frozen
exec sha256sum --check inputs.sha256
if {[info exists ::env(AS02_POOL_SYNTH_REPLAY_DCP)]} {
    # Reopen only an exactly hashed retained synthesis checkpoint. This is
    # not a fresh synthesis/implementation or a changed design/clock.
    open_checkpoint [file normalize $::env(AS02_POOL_SYNTH_REPLAY_DCP)]
} else {
    create_project -in_memory -part xcku3p-ffvb676-1-e
    read_verilog [file join $frozen rocev2_retrans_pool.v]
    synth_design -top rocev2_retrans_pool -mode out_of_context -part xcku3p-ffvb676-1-e -flatten_hierarchy rebuilt
}
set part [get_parts xcku3p-ffvb676-1-e]
set part_fd [open [file join $output part-properties.rpt] w]
foreach property [lsort [list_property $part]] {puts $part_fd "$property\t[get_property $property $part]"}
close $part_fd
if {[llength [get_clocks -quiet pool_clk]]==0} {
    create_clock -name pool_clk -period 4.0 [get_ports clk]
} elseif {[get_property PERIOD [get_clocks pool_clk]]!=4.0} {error "Retained clock changed"}
report_utilization -file [file join $output utilization.rpt]
report_timing_summary -file [file join $output synthesis-timing-NOT-physical.rpt]
report_drc -file [file join $output synthesis-drc.rpt]
write_checkpoint [file join $output pool-synth.dcp]
set fd [open [file join $output retention.tsv] w]
set gens [get_cells -hier -filter {NAME =~ *next_generation_reg* && REF_NAME =~ FD*}]
puts $fd "generation_registers\t[llength $gens]"
if {[llength $gens]!=64} {error "Expected ALL64 generation bits to survive synthesis"}
set pins [get_pins -of_objects $gens -filter {REF_PIN_NAME == R || REF_PIN_NAME == S || REF_PIN_NAME == CLR || REF_PIN_NAME == PRE}]
puts $fd "generation_reset_pins\t[llength $pins]"
if {[llength $pins]!=64} {error "Unexpected generation register/reset mapping"}
foreach p $pins {
    set nets [get_nets -of_objects $p]
    if {[llength $nets]!=1} {error "Generation reset pin not uniquely driven: $p"}
    set n [lindex $nets 0]
    # IS_GND is not a net property in this Vivado version. Prove actual
    # connectivity to primitive GND drivers, never infer from a net's name.
    set drivers [get_cells -of_objects [get_pins -leaf -of_objects $n -filter {DIRECTION == OUT}]]
    set gnd [expr {[llength $drivers]>0}]
    foreach d $drivers {if {[get_property REF_NAME $d] ne "GND"} {set gnd 0}}
    puts $fd "generation_pin\t$p\t$n\t$drivers\t$gnd"
    if {!$gnd} {error "Local reset reaches generation reset pin: $p $n"}
}
set rams [get_cells -hier -filter {REF_NAME =~ RAMB*}]
set lease_rams [get_cells -hier -filter {REF_NAME =~ RAMB* && NAME =~ *leases*}]
set ring_rams [get_cells -hier -filter {REF_NAME =~ RAMB* && NAME =~ *free_ring*}]
puts $fd "BRAM_primitives\t[llength $rams]"
puts $fd "lease_BRAM_primitives\t[llength $lease_rams]"
puts $fd "ring_BRAM_primitives\t[llength $ring_rams]"
foreach ram $rams {puts $fd "BRAM\t$ram\t[get_property REF_NAME $ram]"}
close $fd
if {[llength $lease_rams]==0 || [llength $ring_rams]==0} {error "Expected REAL lease/ring BRAM, not a register/shadow substitute"}
exec sha256sum --check inputs.sha256
exit
