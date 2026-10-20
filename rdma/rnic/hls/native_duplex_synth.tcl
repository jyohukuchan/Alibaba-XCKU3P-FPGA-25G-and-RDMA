# SPDX-License-Identifier: BSD-2-Clause-Views
if {![info exists ::env(AS02_RNIC_HLS_INPUT)] || ![info exists ::env(AS02_HLS_BUILD)]} {
    error "Use build_native_duplex.py with fresh frozen inputs"
}
set frozen [file normalize $::env(AS02_RNIC_HLS_INPUT)]
set output [file normalize $::env(AS02_HLS_BUILD)]
if {[file exists $output]} {error "Refusing to overwrite prior HLS output"}
cd $frozen
exec sha256sum --check inputs.sha256
set src [file join $frozen fns hls]
set adapter [file join $frozen adapter]
cd [file dirname $output]
open_project [file tail $output]
set_top rocev2_native_duplex_top
set flags "-I$adapter -I$src -DFNS_DATA_WIDTH=64 -DFNS_ROCE_STACK_MAX_QPS=8 -D__VITIS_HLS__ -DAS02_SMALL_FIFO_SRL=1"
foreach source {
    axi_utils.cpp ipv4/ipv4_utils.cpp ipv4/ipv4.cpp ipv6/ipv6.cpp udp/udp.cpp
    crc/crc.cpp ib_transport_protocol/ib_utils.cpp
    ib_transport_protocol/ib_transport_protocol.cpp rocev2/rocev2.cpp
} {
    add_files [file join $src $source] -cflags $flags
}
open_solution solution1 -flow_target vivado
set_part xcku3p-ffvb676-1-e
create_clock -period 4.0 -name default
config_rtl -reset state -reset_level low
csynth_design
cd $frozen
exec sha256sum --check inputs.sha256
exit
