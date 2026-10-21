#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual typed WRITE RTL generation/port/clock provenance, NOT native release.

A successful audit may verify that generation succeeded AND original timing
failed. Keep those facts separate; do not call synthesis an on-board or
full-native functional pass, and never replace the original clock gates.
"""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import audit_segmented_receive as binding

ROOT=binding.ROOT;PREFIX=binding.PREFIX;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all earlier evidence')
    generated,g_id=binding.bindings('segmented-write-owned-generated-hls-001')
    consumer,c_id=binding.bindings('segmented-write-owned-diagnostics-001')
    if not consumer.get('audit_passed')or not all(generated.get(k)for k in ['pass_test','source_and_frozen_inputs_unchanged',
        'parent_builder_unchanged','wrapper_and_builder_unchanged','whole_receive_port776_verified',
        'write_owner424_and_receipt456_verified','all87_CPP_modes_required']):raise ValueError('actual same-source generation/consumer gates required')
    if generated['exit_code']!=0 or generated['HLS_top']!='rocev2_native_segmented_write_owned_top'or \
       generated['source_directory']!='rdma/rnic/build/native-segmented-write-owned-transport-002'or \
       (generated['MAX_QPS'],generated['metadata_entries'],generated['HLS_free_space_guard_bytes'])!=(8,2000,1572864000)or \
       generated['free_bytes_at_start']<1572864000 or generated['elapsed_seconds']>7200:
        raise ValueError('all original source/geometry/free-space/runtime gates required')
    run=ROOT/generated['directory'];rtl=run/'project/solution1/syn/verilog';top=(rtl/(generated['HLS_top']+'.v')).read_text()
    ports={**generated['generated_port_bits'],'s_axis_write_owner_TDATA':424,'m_axis_write_done_TDATA':456,'m_axis_recv_message_TDATA':776}
    for name,width in ports.items():
        if not re.search(r'\[\s*'+str(width-1)+r'\s*:\s*0\s*\]\s*'+name+r'\s*;',top):raise ValueError('actual generated old/new port changed:'+name)
    if not re.search(r'output\s+\[\s*0\s*:\s*0\s*\]\s*regWriteFault\s*;',top)or 'as02_write_packet_retire_join'not in top:
        raise ValueError('actual sticky fault and new same-consumer receipt RTL required')
    xml_path=run/'project/solution1/syn/report'/(generated['HLS_top']+'_csynth.xml')
    xml=ET.parse(xml_path).getroot();period=float(xml.findtext('.//TargetClockPeriod'))
    uncertainty=float(xml.findtext('.//ClockUncertainty'));estimate=float(xml.findtext('.//EstimatedClockPeriod'))
    if (period,uncertainty)!=(4.0,1.08)or float(generated['estimated_clock_period'])!=estimate or \
       generated['original_effective_period_met']!=(estimate<=period-uncertainty):raise ValueError('original timing observation must remain exact')
    resources={n:xml.findtext('.//AreaEstimates/Resources/'+n)for n in ['LUT','FF','BRAM_18K','DSP']}
    if resources!=generated['resources']:raise ValueError('actual synthesis resource estimate changed')
    frozen=run/'inputs';snapshot=generated['frozen_sha256']
    for name,h in snapshot.items():
        if digest(frozen/name)!=h:raise ValueError('frozen source changed:'+name)
    log=run/'synthesis.log';text=log.read_text()
    if 'Generating Verilog RTL for '+generated['HLS_top']not in text or 'Finished Command csynth_design'not in text:
        raise ValueError('actual terminal tool log required')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected raw source changed:'+n)
    result=dict(scope=__doc__,audit_passed=True,overall_goal_complete=False,actual_generation=g_id,actual_consumer_audit=c_id,
        verified_bindings=g_id['bindings_verified']+c_id['bindings_verified'],
        source_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},
        artifact_sha256={str(p.relative_to(ROOT)):digest(p)for p in [xml_path,log]},protected_raw_sha256=binding.PROTECTED,
        actual_new_generated_RTL=True,old_and_new_generated_ports_verified=ports,write_fault_output_verified=True,
        original_clock_period_ns=period,original_uncertainty_ns=uncertainty,original_effective_period_ns=period-uncertainty,
        estimated_period_ns=estimate,original_effective_period_met=estimate<=period-uncertainty,
        timing_status='PASS'if estimate<=period-uncertainty else'FAIL',resources=resources,synthesis_seconds=generated['elapsed_seconds'],
        MAX_QPS=8,metadata_entries=2000,source_cohort=generated['source_directory'],generated_directory=generated['directory'],
        full_native_elaboration=False,new_generated_RTL_functional_runtime=False,full_native_payload_DMA_MAC_CQ=False,
        live_Linux_RTL_coupling=False,full_board_implementation=False,hardware_verified=False,
        remaining=['All11 original requirements retained; goal incomplete.',
            'Integrate actual generated typed424/456 RTL with checked frontend/sharedMR/PTE/DMA/nonces/fences and ONE dual-owner ACK allocator, true SFD/EOF/tail/CQ fanout; preserve all old/default paths.',
            'Prove safe partial-message HLS teardown without forged parent drain/reset/unpin, complete native1MiB/matched software/multiSGE/liveLinux/short real-peer recovery/RNR/MSN/congestion.',
            'Original4ns/default1.08ns timing fails at this exact estimate; full-board fit/setup/hold/CDC/DRC/routing and short supervised physical qualification remain.',
            'No reboot needed; restore all archived RAM caches and prove authenticated exact-thread/active-goal revival before any necessary reboot.'],
        hardware_install_load_network_fan_BIOS_flash_reboot_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,generated=True,verified_bindings=result['verified_bindings'],timing_status=result['timing_status'],native_or_physical=False)),flush=True)


if __name__=='__main__':main()
