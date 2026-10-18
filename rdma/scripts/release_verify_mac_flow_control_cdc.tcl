# SPDX-License-Identifier: BSD-2-Clause-Views
# Verification-only revision for a separately identified release package.
# Never overwrite the verifier in the original compile-input manifest.
# The one alternate source is audited against pinned MAC_CTRL_ENABLE=0 RTL;
# all destination/clock/reset/connectivity/exception assertions still apply.
source [file join [file dirname [file normalize [info script]]] verify_lfc_equivalent.tcl]
set lfc_release_result [verify_mac_lfc_equivalent]
puts "VERIFICATION_ONLY_LFC_REVISION=1 RESULT=$lfc_release_result HARDWARE_VERIFIED=0"
