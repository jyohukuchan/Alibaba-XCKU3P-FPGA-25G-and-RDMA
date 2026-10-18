#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-2-Clause-Views
# Copyright (c) 2026 jyohukuchan
# Read-only source checks. No compilation, network tests or hardware access.
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"
for required in git bash tclsh jq python3; do
    command -v "$required" >/dev/null || { printf 'Missing tool: %s\n' "$required" >&2; exit 2; }
done
for script in scripts/*.sh fpga/*.sh rdma/scripts/*.sh; do bash -n "$script"; done
tclsh tests/check_tcl_syntax.tcl
tclsh tests/check_lfc_source_allowlist.tcl
AS02_SOURCE_CHECK_ONLY=1 tclsh fpga/build_25g.tcl /tmp/as02-unused-source-check
git -C external/corundum apply --check "$repo_dir/patches/mqnic-linux-6.17.patch"
jq -e '
    .date_utc == "2026-10-17" and .sequential_directions == true and
    (.tests | length) == 4 and
    all(.tests[]; .protocol == "TCP" and .num_streams == 4 and
        .omit_seconds == 3 and .error == null and
        .receiver.seconds >= 19 and .receiver.seconds < 25 and
        .receiver.bits_per_second > 10000000000 and
        .sender.retransmits >= 0)
' results/2026-10-17/tcp-summary.json >/dev/null
jq -e '
    .reference_only == true and .fpga_rdma_implemented == false and
    .throughput_claim == false and .invalid_icrc == 0 and
    (.tests | length) == 16 and
    all(.tests[]; .pass_test == true and .mismatches == 0 and .messages == 16) and
    ([.tests[].messages] | add) == 256 and
    ([.tests[].receiver_verified_bytes] | add) == .total_receiver_verified_bytes and
    .total_receiver_verified_bytes == 661536
' results/2026-10-17/rocev2-reference.json >/dev/null
jq -e '
    .complete == true and .hardware_verified == false and
    (.tests | length) == 3 and all(.tests[]; .pass_test == true) and
    all(.tests[]; .keep_masks_checked == 65536) and
    .tests.test_rx_whole_frame_integrity_and_stalls.header_sum_values_checked == 2097152 and
    .tests.test_cycle_capacity_above_25g.simulated_payload_gbit_s_at_250mhz > 25
' results/2026-10-17/rocev2-icrc-rtl.json >/dev/null
for record in results/2026-10-17/rocev2-transport-{rx,tx}-rtl.json; do
    jq -e '.hardware_verified == false and .wire_ipv4_checksums_valid == true and .wire_icrcs_valid == true' "$record" >/dev/null
done
jq -e '.complete == true and .hardware_verified == false and
    (.tests | length) == 3 and all(.tests[]; .pass_test == true) and
    .tests.test_tx_25g_cycle_capacity.simulated_payload_gbit_s_at_250mhz > 25
' results/2026-10-17/rocev2-ethernet-rtl.json >/dev/null
jq -e '.hardware_verified == false and .ethernet_boundary == true and
    .wire_icrcs_valid == true and .wire_ipv4_checksums_valid == true and
    .consumed_success_ack == 1 and .core_rx_words == 1 and
    .peer_qp_rejected_frames == 1 and .icrc_rejected_frames == 1 and
    .whole_invalid_frame_rejected_before_hls == true
' results/2026-10-17/rocev2-ethernet-transport-tx-rtl.json >/dev/null
# Prevent a green recorded result from silently referring to superseded RTL
# or testbench source. This verifies provenance, not the hardware objective.
assert_record_hash() {
    local record=$1 selector=$2 source=$3 recorded actual
    recorded=$(jq -er "$selector" "$record")
    actual=$(sha256sum "$source")
    if [[ "$recorded" != "${actual%% *}" ]]; then
        printf 'Stale source/test identity: %s -> %s\n' "$record" "$source" >&2
        exit 1
    fi
}
record=results/2026-10-18/rocev2-lfc-equivalent-checks.json
jq -e '.complete == true and .hardware_verified == false and .final_physical_gate_passed == false and
    .source_allowlist.pure_tcl_cases_passed == 14 and .source_allowlist.arbitrary_source_allowed == false and
    .checks.compiled.exit_status == 0 and .checks.compiled.positive_annotations_verified == true and
    .checks.compiled.additional_xdc_loaded_for_positive_case == false and
    .checks.compiled.audited_source_aliases == 1 and .checks.compiled.negative_controls_checked == 2 and
    .checks.original.exit_status == 0 and .checks.original.positive_annotations_verified == true and
    .checks.original.audited_source_aliases == 0 and .checks.original.negative_controls_checked == 3 and
    .checks.original.missing_first_d_cut_rejected == true and
    all(.checks[]; .missing_async_reg_rejected == true and .second_stage_overcut_rejected == true) and
    .negative_control_executions == 5 and .distinct_fault_types == 3 and
    .copies_discarded_without_checkpoint_or_image_write == true' "$record" >/dev/null
while IFS= read -r source; do
    assert_record_hash "$record" ".source_sha256[\"$source\"]" "$source"
done < <(jq -r '.source_sha256 | keys[]' "$record")
record=results/2026-10-18/rocev2-release-provenance-checks.json
jq -e '.complete == true and .exit_status == 0 and .tests_run == 7 and
    .terminal_attestation_required == true and
    .wrong_checkpoint_or_changed_compile_input_rejected == true and
    .unreviewed_gate_or_pinned_alias_assumption_rejected == true and
    .existing_image_preserved_and_alternate_release_refused == true and
    .original_manifest_and_verifier_preserved == true and
    .original_physical_gate_and_vio_copied_byte_identically == true and
    .verification_revision_separately_hash_bound == true and
    .staged_verifier_corruption_rejected_before_checkpoint_open == true and
    .vivado_release_driver_executed_on_real_checkpoint == false and
    .image_generated == false and .final_physical_gate_passed == false and
    .hardware_verified == false' "$record" >/dev/null
while IFS= read -r source; do
    assert_record_hash "$record" ".source_sha256[\"$source\"]" "$source"
done < <(jq -r '.source_sha256 | keys[]' "$record")
record=results/2026-10-18/rocev2-metadata-capacity-rtl.json
jq -e '.tests.test_bad_final_beat_at_full_metadata_fifo_recovers as $t |
    .complete == true and .hardware_verified == false and
    (.tests | length) == 1 and $t.pass_test == true and
    $t.good_frames == 38 and $t.bad_frames == 1 and
    $t.checksum_entries_pushed == 38 and $t.metadata_full_cycles > 0 and
    $t.bad_final_while_metadata_full_cycles > 0 and $t.input_stall_cycles > 0 and
    $t.output_stall_cycles > 0 and $t.checksum_fifo_ram_depth == 32 and
    $t.checksum_fifo_depth_reduced == false and $t.dut_state_forced == false and
    $t.keep_masks_checked == 65536' "$record" >/dev/null
assert_record_hash "$record" .rtl_sha256 rdma/rtl/rocev2_ipv4_icrc.v
assert_record_hash "$record" .test_sha256 rdma/tests/test_metadata_backpressure_rtl.py
assert_record_hash "$record" .base_test_sha256 rdma/tests/test_icrc_rtl.py
record=results/2026-10-18/rocev2-lfc-equivalent-checks.json
while IFS= read -r source; do
    assert_record_hash "$record" ".assumption_source_sha256[\"$source\"]" "$source"
done < <(jq -r '.assumption_source_sha256 | keys[]' "$record")
assert_record_hash "$record" .test_sha256 tests/check_lfc_source_allowlist.tcl
record=results/2026-10-18/rocev2-canonical-lfc-check.json
jq -e '.exit_status == 0 and .inspection_complete == true and .assertion_failed == false and
    .checkpoint_contains_new_input_stage == false and .additional_xdc_loaded == false and
    .design_or_constraint_changes == false and .vio_pairs_verified == 6 and
    .lfc_chains_verified == 4 and .lfc_destination_registers_verified == 8 and
    .audited_source_aliases == 1 and .minimum_lfc_second_stage_setup_slack_ns >= 0 and
    .minimum_lfc_second_stage_hold_slack_ns >= 0 and .other_critical_cdc_findings_not_waived == 18 and
    .physical_gate_passed == false and .hardware_verified == false' "$record" >/dev/null
while IFS= read -r source; do
    assert_record_hash "$record" ".source_sha256[\"$source\"]" "$source"
done < <(jq -r '.source_sha256 | keys[]' "$record")
assert_record_hash results/2026-10-17/rocev2-icrc-rtl.json .rtl_sha256 rdma/rtl/rocev2_ipv4_icrc.v
assert_record_hash results/2026-10-17/rocev2-icrc-rtl.json .test_sha256 rdma/tests/test_icrc_rtl.py
assert_record_hash results/2026-10-17/rocev2-ethernet-rtl.json .test_sha256 rdma/tests/test_ethernet_rtl.py
for direction in rx tx; do
    assert_record_hash results/2026-10-17/rocev2-ethernet-rtl.json ".source_sha256[\"rocev2_ethernet_$direction.v\"]" "rdma/rtl/rocev2_ethernet_$direction.v"
done
for record in results/2026-10-17/rocev2-transport-{rx,tx}-rtl.json results/2026-10-17/rocev2-ethernet-transport-tx-rtl.json; do
    assert_record_hash "$record" .integrity_rtl_sha256 rdma/rtl/rocev2_ipv4_icrc.v
    assert_record_hash "$record" .transport_rtl_sha256 rdma/rtl/rocev2_integrity_transport.v
    assert_record_hash "$record" .padding_rtl_sha256 rdma/rtl/rocev2_tx_padding.v
    assert_record_hash "$record" .test_sha256 rdma/hls/probe/test_integrity_transport.py
done
for suite in padding write-engine control; do
    record="results/2026-10-17/rocev2-$suite-rtl.json"
    jq -e '.hardware_verified == false and
        (if has("tests") then .complete == true and all(.tests[]; .pass_test == true)
         else .pass_test == true end)' "$record" >/dev/null
    while IFS= read -r source; do
        assert_record_hash "$record" ".source_sha256[\"$source\"]" "rdma/rtl/$source"
    done < <(jq -r '.source_sha256 | keys[]' "$record")
done
assert_record_hash results/2026-10-17/rocev2-padding-rtl.json .test_sha256 rdma/tests/test_padding_rtl.py
assert_record_hash results/2026-10-17/rocev2-padding-rtl.json .integrity_test_dependency_sha256 rdma/tests/test_icrc_rtl.py
assert_record_hash results/2026-10-17/rocev2-write-engine-rtl.json .test_sha256 rdma/tests/test_write_engine_rtl.py
assert_record_hash results/2026-10-17/rocev2-control-rtl.json .test_sha256 rdma/tests/test_control_rtl.py
record=results/2026-10-17/rocev2-control-transport-rtl.json
jq -e '.complete == true and .hardware_verified == false and
    .physical_tx_quiescence_verified == false and (.cases | length) == 5 and
    .total_wire_writes == 15 and .total_wire_payload_bytes == 12876 and
    .total_success_ack_events == 14 and
    ([.cases[].wire_writes] | add) == .total_wire_writes and
    ([.cases[].wire_payload_bytes] | add) == .total_wire_payload_bytes and
    ([.cases[].success_ack_events] | add) == .total_success_ack_events and
    all(.cases[]; .pass_test == true and .hardware_verified == false and
        .all_wire_bytes_checked == true and .wire_icrcs_valid == true and
        .wire_ipv4_checksums_valid == true and .separate_tx_peer_psns == true and
        .terminal_counters_preserved == true) and
    (.source_sha256 as $sources | .test_sha256 as $test |
     .generated_rtl_sha256 as $generated | all(.cases[];
        .source_sha256 == $sources and .test_sha256 == $test and
        .generated_rtl_sha256 == $generated))' "$record" >/dev/null
while IFS= read -r source; do
    source_dir=rdma/rtl
    if [[ "$source" == mqnic_app_block.v ]]; then source_dir=rdma/fpga; fi
    assert_record_hash "$record" ".source_sha256[\"$source\"]" "$source_dir/$source"
done < <(jq -r '.source_sha256 | keys[]' "$record")
assert_record_hash "$record" .test_sha256 rdma/hls/probe/test_control_transport.py
assert_record_hash "$record" .axi_test_dependency_sha256 rdma/tests/test_control_rtl.py
assert_record_hash "$record" .boundary_test_dependency_sha256 rdma/hls/probe/app_boundary.py
record=results/2026-10-18/rocev2-tx-guard-rtl.json
jq -e '.complete == true and .hardware_verified == false and
    .integrated_mac_drain_verified == false and (.cases | length) == 6 and
    all(.cases[]; .pass_test == true)' "$record" >/dev/null
assert_record_hash "$record" '.source_sha256["rocev2_tx_guard.v"]' rdma/rtl/rocev2_tx_guard.v
assert_record_hash "$record" .test_sha256 rdma/tests/test_tx_guard_rtl.py
record=results/2026-10-18/rocev2-timer-cmodel.json
jq -e '.pass_test == true and .hardware_verified == false and
    .generated_rtl_verified == false and .clock_ps == 4000 and .max_qps == 8 and
    .first_retry_qps_checked == 8 and .ack_restart_checked == true and
    .ack_stop_checked == true and .table_boundary_checked == true and
    .first_retry_min_clocks >= 250000 and .first_retry_max_clocks <= 250064
' "$record" >/dev/null
for source in test_timer.cpp rocev2_config.hpp; do
    assert_record_hash "$record" ".source_sha256[\"$source\"]" "rdma/hls/probe/$source"
done
assert_record_hash "$record" '.source_sha256["fns-compat.patch"]' rdma/hls/fns-compat.patch
assert_record_hash "$record" .test_sha256 rdma/hls/probe/test_timer.py
record=results/2026-10-18/rocev2-timer-rtl.json
jq -e '.pass_test == true and .hardware_verified == false and
    .core_clock_ps == 4000 and .max_qps == 8 and .simulator == "iverilog" and
    .powerup_zero_delay_delta_ignored == false and .timer_table_storage == "registers" and
    .first_retry_qps_checked == 8 and .ack_restart_scan_phases_checked == 8 and
    .stop_restart_phases_checked == 8 and .warm_reset_checked == true and
    .retry_output_backpressure_checked == true and .ack_stop_checked == true and
    .retry_events_checked == 26 and .first_retry_min_clocks >= 250000 and
    .first_retry_max_clocks <= 250128' "$record" >/dev/null
assert_record_hash "$record" .test_sha256 rdma/hls/probe/test_timer_rtl.py
[[ "$(jq -er .generated_rtl_sha256 "$record")" == "$(jq -er .generated_rtl_sha256 results/2026-10-17/rocev2-control-transport-rtl.json)" ]]
record=results/2026-10-18/rocev2-mac-drain-rtl.json
jq -e '.complete == true and .pass_test == true and .hardware_verified == false and
    .exact_mqnic_port_tx_verified == false and .wire_frames == 3 and
    .admitted_frames == 3 and .completed_frames == 3 and .mac_underflows == 0 and
    .ethernet_fcs_checked == true and .wire_bytes_checked == true and
    .core_clock_hz == 250000000 and .mac_clock_hz == 390625000 and
    (.drain_cycles | length) == 3 and
    all(.drain_cycles[]; .[3] >= .[1]+1024 and .[3] >= .[2]) and
    .drain_cycles[2][2] > .drain_cycles[2][1]' "$record" >/dev/null
assert_record_hash "$record" .test_sha256 rdma/tests/test_mac_drain_rtl.py
for source in rdma/rtl/rocev2_tx_guard.v rdma/rtl/rocev2_ethernet_tx.v \
    external/corundum/fpga/lib/axis/rtl/{axis_adapter,axis_arb_mux,axis_async_fifo,axis_async_fifo_adapter,arbiter,priority_encoder}.v \
    external/corundum/fpga/lib/eth/rtl/{eth_axis_tx,axis_xgmii_tx_64,lfsr}.v; do
    assert_record_hash "$record" ".source_sha256[\"${source##*/}\"]" "$source"
done
for direction in rx tx; do
    assert_record_hash results/2026-10-17/rocev2-ethernet-transport-tx-rtl.json ".ethernet_rtl_sha256[\"rocev2_ethernet_$direction.v\"]" "rdma/rtl/rocev2_ethernet_$direction.v"
done
record=results/2026-10-18/rocev2-host-control-unit.json
jq -e '.pass_test == true and .tests_run == 10 and .failures == 0 and .errors == 0 and
    .hardware_verified == false and .hardware_accessed == false and
    .registered_memory_tested == false' "$record" >/dev/null
assert_record_hash "$record" '.source_sha256["fpga_write_client.py"]' rdma/host/fpga_write_client.py
assert_record_hash "$record" .test_sha256 rdma/tests/test_fpga_write_client.py
record=results/2026-10-18/rocev2-native-preflight.json
jq -e '.inventory_passed == true and .offline_unit_tests_run == 10 and
    .application_required_preflight_refused == true and .application_bar2_present == false and
    .application_registers_read == false and .traffic_generated == false and
    .hardware_configuration_modified == false and .fpga_programmed == false and
    .rdma_qp_created == false and .hardware_rdma_verified == false and
    .timing_verified == false and .temperature_checked == false and
    .peer.pci_class == "020700" and .peer.link_layer == "Ethernet" and
    .peer.gid_type == "RoCE v2" and .peer.active_mtu_checked == false and
    .fpga.reported_speed == null' "$record" >/dev/null
assert_record_hash "$record" '.source_sha256["native_preflight.py"]' rdma/host/native_preflight.py
assert_record_hash "$record" '.source_sha256["fpga_write_client.py"]' rdma/host/fpga_write_client.py
assert_record_hash "$record" .test_sha256 rdma/tests/test_native_preflight.py
record=results/2026-10-18/rocev2-native-runner-unit.json
jq -e '.pass_test == true and .tests_run == 12 and .failures == 0 and .errors == 0 and
    .hardware_verified == false and .hardware_accessed == false and
    .traffic_generated == false and .registered_memory_tested == false and
    .thermal_guard_executed == false' "$record" >/dev/null
for source in native_test.py native_preflight.py fpga_write_client.py; do
    assert_record_hash "$record" ".source_sha256[\"$source\"]" "rdma/host/$source"
done
assert_record_hash "$record" .test_sha256 rdma/tests/test_native_test.py
assert_record_hash "$record" .fixture_dependency_sha256 rdma/tests/test_native_preflight.py
# Native records are historical evidence, not a hardware test performed by CI.
record=results/2026-10-18/rocev2-native-003.json
jq -e '.hardware_rdma_verified == true and .software_rxe_created == false and
    .receiver.device == "mlx5_0" and .receiver.gid_type == "RoCE v2" and
    .total_verified_writes == 16391 and .total_verified_bytes == 67121411 and
    .total_mismatches == 0 and (.cases | length) == 4 and
    all(.cases[]; .all_bytes_verified == true and .tx_quiescence_verified == true and
        .thermal_guard_exit_status == 0 and .issued == .messages and .acknowledged == .messages and
        .verified_bytes == .message_bytes * .messages) and
    .cases[1].local_psn == 16777214 and .cases[1].message_bytes == 65 and
    .cases[3].verified_bytes == 67108864 and .cases[3].elapsed_cycles == 5531559 and
    .cases[3].payload_gbit_per_second > 24 and .cases[3].payload_gbit_per_second < 25 and
    .terminal_application.quiescent == true and .fan_settings_changed == false and .flash_modified == false
' "$record" >/dev/null
for source in rdma/host/native_test.py rdma/host/native_preflight.py rdma/host/fpga_write_client.py rdma/host/rc_write_peer.c; do
    assert_record_hash "$record" ".source_sha256[\"$source\"]" "$source"
done
record=results/2026-10-18/rocev2-mac-rx-fault-unit.json
jq -e '.exit_status == 0 and .new_fault_tests == 16 and .total_python_host_tests == 57 and
    .failures == 0 and .errors == 0 and .hardware_accessed == false and .thermal_guard_executed == false
' "$record" >/dev/null
while IFS= read -r source; do
    assert_record_hash "$record" ".source_sha256[\"$source\"]" "$source"
done < <(jq -r '.source_sha256 | keys[]' "$record")
record=results/2026-10-18/rocev2-native-retry-recovery-003.json
jq -e '.hardware_retry_verified == true and .hardware_expected_timeout_verified == true and
    .hardware_recovery_verified == true and .hls_rto_modified == false and
    .fpga_programmed_or_flash_modified == false and .nic_or_phy_reset == false and
    .fan_settings_changed == false and .management_network_unchanged == true and
    .software_rxe_created == false and (.fault_cases | length) == 2 and
    all(.fault_cases[]; .success == true and .all_receiver_bytes_verified == 65 and
        .fault.rx_restored == true and .fault.deadline_expired == false and
        .fault.retry_observed_before_restore == true and .fault.rx_off_seconds <= 0.1 and
        .fault.before_restore.acknowledged == 0 and .fault.before_restore.read_commands >= 2 and
        .thermal_guard_exit_status == 0) and
    .fault_cases[0].mode == "retry" and .fault_cases[0].native_write_completed == true and
    .fault_cases[0].acknowledged == 1 and .fault_cases[0].error_code == 0 and
    .fault_cases[1].mode == "watchdog" and .fault_cases[1].native_write_completed == false and
    .fault_cases[1].acknowledged == 0 and .fault_cases[1].error_code == 2 and
    .fault_cases[1].elapsed_cycles == 2500002 and
    .recovery.initial_status == 2108 and .recovery.final_status == 1850 and
    .recovery.hardware_rdma_verified == true and .recovery.acknowledged == 1 and
    .final_application.quiescent == true and .final_rx_control.rx_control_raw == 65537
' "$record" >/dev/null
while IFS= read -r source; do
    assert_record_hash "$record" ".source_sha256[\"$source\"]" "$source"
done < <(jq -r '.source_sha256 | keys[] | select(. != "rdma/build/rc_write_peer")' "$record")
accepted_bit=$(jq -er '.artifacts["fpga/builds/as02mc04-25g-rocev2-XnWXCJXt/as02mc04_25g.bit"]' results/2026-10-18/rocev2-board-build-003.json)
for record in results/2026-10-18/rocev2-{sram-bringup,native,native-retry-recovery}-003.json; do
    [[ "$(jq -er .bitstream_sha256 "$record")" == "$accepted_bit" ]]
done
record=results/2026-10-18/rocev2-transport-retry-rtl.json
jq -e '.pass_test == true and .hardware_verified == false and .boundary == "app" and
    .cycles >= 250000 and .wire_transmissions == 2 and .unique_writes == 1 and
    .unique_payload_bytes == 65 and .wire_payload_bytes == 130 and
    .success_ack_events == 1 and .withheld_ack_count == 1 and
    .actual_transport_retransmissions == 1 and .pattern_reads == 2 and
    .replay_key_address_psn_payload_checked == true and .wire_icrcs_valid == true and
    .wire_ipv4_checksums_valid == true and .core_clock_ps == 4000 and
    .original_timer_clock_unmodified == true and .physical_mac_drain_verified == false' "$record" >/dev/null
assert_record_hash "$record" .test_sha256 rdma/hls/probe/test_retry_transport.py
assert_record_hash "$record" '.dependency_sha256["test_control_transport.py"]' rdma/hls/probe/test_control_transport.py
assert_record_hash "$record" '.dependency_sha256["app_boundary.py"]' rdma/hls/probe/app_boundary.py
assert_record_hash "$record" '.dependency_sha256["test_control_rtl.py"]' rdma/tests/test_control_rtl.py
while IFS= read -r source; do
    source_dir=rdma/rtl
    if [[ "$source" == mqnic_app_block.v ]]; then source_dir=rdma/fpga; fi
    assert_record_hash "$record" ".source_sha256[\"$source\"]" "$source_dir/$source"
done < <(jq -r '.source_sha256 | keys[]' "$record")
[[ "$(jq -er .generated_rtl_sha256 "$record")" == "$(jq -er .generated_rtl_sha256 results/2026-10-17/rocev2-control-transport-rtl.json)" ]]
if env -u AS02_ALLOW_TRAFFIC_TEST bash scripts/benchmark_25g.sh >/dev/null 2>&1; then
    printf 'Traffic helper must refuse without explicit opt-in.\n' >&2
    exit 1
fi
if env -u AS02_JTAG_SERIAL bash scripts/read_temperature.sh >/dev/null 2>&1; then
    printf 'Temperature helper must require an explicit adapter serial.\n' >&2
    exit 1
fi
if env -u AS02_ALLOW_REFERENCE_TEST bash rdma/scripts/reference_test.sh >/dev/null 2>&1; then
    printf 'RDMA reference helper must refuse without explicit opt-in.\n' >&2
    exit 1
fi
if env -u AS02_HLS_BUILD bash fpga/build_25g_rocev2.sh >/dev/null 2>&1; then
    printf 'RoCE build must require the explicit tested HLS build.\n' >&2
    exit 1
fi
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s rdma/tests -p test_wire.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s rdma/tests -p test_fpga_write_client.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s rdma/tests -p test_native_preflight.py -v
PYTHONDONTWRITEBYTECODE=1 python3 rdma/host/native_preflight.py --help >/dev/null
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s rdma/tests -p test_native_test.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s rdma/tests -p test_mac_rx_fault.py -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s rdma/tests -p test_native_fault_test.py -v
PYTHONDONTWRITEBYTECODE=1 python3 rdma/host/mac_rx_fault.py --help >/dev/null
PYTHONDONTWRITEBYTECODE=1 python3 rdma/host/native_fault_test.py --help >/dev/null
if env -u AS02_ALLOW_NATIVE_FPGA_RDMA_TEST -u AS02_ALLOW_MAC_RX_FAULT \
    python3 rdma/host/native_fault_test.py --mode retry --psn 0x456789 >/dev/null 2>&1; then
    printf 'Native MAC RX fault test must refuse without explicit opt-in.\n' >&2
    exit 1
fi
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s rdma/tests -p test_release_provenance.py -v
PYTHONDONTWRITEBYTECODE=1 python3 rdma/host/native_test.py --help >/dev/null
if env -u AS02_ALLOW_NATIVE_FPGA_RDMA_TEST python3 rdma/host/native_test.py >/dev/null 2>&1; then
    printf 'Native test runner must refuse without explicit opt-in.\n' >&2
    exit 1
fi
if env -u AS02_PHYSICAL_REVIEW_COMPLETE AS02_ALLOW_NATIVE_FPGA_RDMA_TEST=YES \
    python3 rdma/host/native_test.py >/dev/null 2>&1; then
    printf 'Native test runner must require prior physical review/programming attestation.\n' >&2
    exit 1
fi
PYTHONDONTWRITEBYTECODE=1 python3 rdma/hls/probe/test_integrity_transport.py --help >/dev/null
PYTHONDONTWRITEBYTECODE=1 python3 rdma/hls/probe/test_control_transport.py --help >/dev/null
PYTHONDONTWRITEBYTECODE=1 python3 rdma/hls/probe/test_timer.py --help >/dev/null
PYTHONDONTWRITEBYTECODE=1 python3 rdma/hls/probe/test_timer_rtl.py --help >/dev/null
PYTHONDONTWRITEBYTECODE=1 python3 rdma/hls/probe/check_build.py --help >/dev/null
PYTHONDONTWRITEBYTECODE=1 python3 rdma/hls/probe/test_retry_transport.py --help >/dev/null
PYTHONDONTWRITEBYTECODE=1 python3 rdma/scripts/test_icrc_candidate.py --help >/dev/null
PYTHONDONTWRITEBYTECODE=1 python3 rdma/host/fpga_write_client.py --help >/dev/null
if env -u AS02_ALLOW_FPGA_RDMA python3 rdma/host/fpga_write_client.py \
    --bdf 0000:82:00.0 --local-ip 198.18.10.2 --peer-ip 198.18.10.1 \
    --local-mac 8a:f3:fb:b9:75:31 --peer-mac b8:83:03:67:c5:d0 >/dev/null 2>&1; then
    printf 'Native FPGA RDMA client must refuse without explicit opt-in.\n' >&2
    exit 1
fi
printf 'Source checks passed. No new Vivado route or hardware validation is implied.\n'
