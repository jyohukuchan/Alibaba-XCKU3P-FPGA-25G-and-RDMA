# SPDX-License-Identifier: BSD-2-Clause-Views
set frozen [file normalize $::env(AS02_OWNED_RETRANS_INPUT)]
set output [file normalize $::env(AS02_OWNED_RETRANS_BUILD)]
if {[file exists $output]} {error "Never overwrite retained HLS output"}
cd $frozen
exec sha256sum --check inputs.sha256
set flags "-I[file join $frozen adapter] -I[file join $frozen fns hls] -DFNS_DATA_WIDTH=64 -DFNS_ROCE_STACK_MAX_QPS=8 -D__VITIS_HLS__"
cd [file dirname $output]
open_project [file tail $output]
set_top as02_owned_retrans_top
add_files [file join $frozen owned_retrans_top.cpp] -cflags $flags
open_solution solution1 -flow_target vivado
set_part xcku3p-ffvb676-1-e
create_clock -period 4.0 -name default
config_rtl -reset state -reset_level low
csynth_design
cd $frozen
exec sha256sum --check inputs.sha256
exit
