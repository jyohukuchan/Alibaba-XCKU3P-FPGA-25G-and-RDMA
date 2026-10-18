# SPDX-License-Identifier: BSD-2-Clause-Views
# Offline resource/compatibility probe; never connects to hardware.
if {![info exists ::env(AS02_FNS_SOURCE)] || ![info exists ::env(AS02_HLS_BUILD)]} {
    error "Set AS02_FNS_SOURCE and a new AS02_HLS_BUILD directory"
}
set src [file normalize $::env(AS02_FNS_SOURCE)]
set output [file normalize $::env(AS02_HLS_BUILD)]
set adapter [file dirname [file normalize [info script]]]
if {[file exists $output]} {error "Refusing to overwrite existing HLS build: $output"}
set commit [string trim [exec git -C $src rev-parse HEAD]]
if {$commit ne "75c32bae73f5c336b5c46c9de35ae0cb9cb7cc1c"} {error "Unexpected FNS source revision"}
exec git -C $src apply --reverse --check [file join $adapter .. fns-compat.patch]
cd [file dirname $output]
open_project [file tail $output]
set_top rocev2_top
set flags "-I$adapter -I$src/hls -DFNS_DATA_WIDTH=64 -DFNS_ROCE_STACK_MAX_QPS=8 -D__VITIS_HLS__ -DAS02_SMALL_FIFO_SRL=1"
foreach source {
    axi_utils.cpp ipv4/ipv4_utils.cpp ipv4/ipv4.cpp ipv6/ipv6.cpp
    udp/udp.cpp crc/crc.cpp ib_transport_protocol/ib_utils.cpp
    ib_transport_protocol/ib_transport_protocol.cpp rocev2/rocev2.cpp
} {
    add_files $src/hls/$source -cflags $flags
}
open_solution solution1 -flow_target vivado
set_part xcku3p-ffvb676-1-e
create_clock -period 4.0 -name default
if {[info exists ::env(AS02_HLS_ACTION)] && $::env(AS02_HLS_ACTION) eq "csim"} {
    add_files -tb [file join $adapter test_rx_write.cpp] -cflags $flags
    csim_design
} else {
    csynth_design
}
exit
