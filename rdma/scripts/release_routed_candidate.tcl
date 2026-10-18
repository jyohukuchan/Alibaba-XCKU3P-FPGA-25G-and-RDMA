# SPDX-License-Identifier: BSD-2-Clause-Views
# Open an immutable full-board DCP and run a separately identified assertion
# revision. No synthesis, routing, constraint edits, JTAG, PCIe or flash writes.
# The original output gate and VIO verifier are copied byte-for-byte; only
# its LFC-verifier child is revised, with independent SHA256 provenance.
if {[llength $argv] != 4} {
    error "Usage: release_routed_candidate.tcl BOARD_DCP NEW_PACKAGE VERIFY_MANIFEST_SHA256 COMPILE_MANIFEST_SHA256"
}
set checkpoint [file normalize [lindex $argv 0]]
set out_dir [file normalize [lindex $argv 1]]
set verification_identity [file join $out_dir verification-source-identity.txt]
set compile_identity [file join $out_dir rocev2-source-identity.txt]
set expected_verification_sha [lindex $argv 2]
set expected_compile_sha [lindex $argv 3]
foreach value [list $expected_verification_sha $expected_compile_sha] {
    if {![regexp {^[0-9a-f]{64}$} $value]} {error "Require explicit expected SHA256 identities"}
}
proc release_inputs_unchanged {} {
    global verification_identity compile_identity expected_verification_sha expected_compile_sha
    foreach manifest [list $verification_identity $compile_identity] expected [list $expected_verification_sha $expected_compile_sha] {
        if {![file isfile $manifest] ||
            [lindex [exec sha256sum -- $manifest] 0] ne $expected ||
            [catch {exec sha256sum --check --status $manifest}]} {
            error "Release provenance is missing or changed: $manifest"
        }
    }
}
release_inputs_unchanged
foreach target {as02mc04_25g.bit as02mc04_25g.ltx} {
    if {[file exists [file join $out_dir $target]]} {error "Refuse to overwrite an existing image/probe file"}
}
open_checkpoint $checkpoint
if {[get_property PART [current_design]] ne "xcku3p-ffvb676-1-e" ||
    [get_property TOP [current_design]] ne "fpga" ||
    [llength [get_cells -hier -filter {IS_BLACKBOX == 1}]]} {
    error "Expected fully linked audited XCKU3P board checkpoint"
}
release_inputs_unchanged
puts "VERIFICATION_ONLY_RELEASE COMPILE_MANIFEST_SHA256=$expected_compile_sha VERIFICATION_MANIFEST_SHA256=$expected_verification_sha CHECKPOINT=$checkpoint HARDWARE_VERIFIED=0"
set roce_enabled 1
set refine_label verification_revision_1
source [file join $out_dir verifiers write_verified_25g_eco.tcl]
release_inputs_unchanged
puts "VERIFICATION_ONLY_RELEASE_STATIC_GATES_PASSED=1 CDC_OPERATING_CONDITION_REVIEW_REQUIRED=1 HARDWARE_VERIFIED=0"
close_design
exit
