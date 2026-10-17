# SPDX-License-Identifier: BSD-2-Clause-Views
# Copyright (c) 2026 jyohukuchan
# Offline implementation only: never program a target or modify networking.
launch_runs impl_1 -to_step {phys_opt_design (Post-Route)} -jobs 8
wait_on_run impl_1
if {![string match "*Complete*" [get_property STATUS [get_runs impl_1]]]} {
    error "Implementation failed: [get_property STATUS [get_runs impl_1]]"
}
open_run impl_1
report_utilization -file [file join $out_dir utilization.rpt]
report_clocks -file [file join $out_dir clocks.rpt]
report_cdc -details -file [file join $out_dir cdc.rpt]
check_timing -verbose -file [file join $out_dir check_timing.rpt]
report_timing -delay_type max -max_paths 20 -file [file join $out_dir setup_paths.rpt]
report_timing -delay_type min -max_paths 20 -file [file join $out_dir hold_paths.rpt]
# Preserve a useful checkpoint even if the final output gate rejects this run.
write_checkpoint -force [file join $out_dir as02mc04_25g_routed.dcp]
set refine_label clean_rtl
source [file join $task_dir write_verified_25g_eco.tcl]
puts "Clean-RTL image generated; review CDC and validate this image in hardware separately."
close_project
