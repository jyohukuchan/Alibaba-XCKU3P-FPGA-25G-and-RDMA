#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual mapped native SQC1/coherent SQ fetch -> SAME MR, shared physical DMA.

Forward case also retains all original5incoming HLS READ/WRITE/ordinary-host
assertions. Physical MAC/AXI/root/link/host and downstream executor/CQ lifetime
are MODELS. No local payload execution/real CQ/verbs/kernel pins/board claim.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

import native_sq_fixture as fixture
import native_memory_fixture as memory
import test_native_sq_rtl as unit
import test_shared_mr_responder_rtl as shared
import wrkey_delivery_sim as delivery

ROOT=fixture.ROOT


def make_case(case,instance,local_memory=False):
    if case=='forward':
        words,body,cases,ordinary=fixture.native.dual.stimulus()
        suffix=memory.body(False)if local_memory else fixture.forward_body()
        if suffix.count('$finish;')!=1:raise ValueError('forward final marker changed')
        # Preserve ALL original native HLS assertions at the end of the bench.
        # Added real SQ READ changes exact physical counts by ONE, never the
        # existing byte/range/fence/PSN/integrity/ordinary-host requirements.
        tb=fixture.make_tb(words,'enable=1;\n'+body+'\nexpected_work_key=16;\n'+suffix.replace('$finish;',''))
        read_count=11 if local_memory else 9;tag_count=15 if local_memory else 13
        for old,new in [('read_tlps!=8',f'read_tlps!={read_count}'),('read_completions!=8',f'read_completions!={read_count}'),
                        ('pcie_physical_reads!=8',f'pcie_physical_reads!={read_count}'),('pcie_last_tag!=12',f'pcie_last_tag!={tag_count}')]:
            tb=fixture.once(tb,old,new)
        if local_memory:
            tb=memory.enable_memory(tb)
            for old,new in [('command_count!=5','command_count!=6'),('completion_count!=5','completion_count!=6')]:
                tb=fixture.once(tb,old,new)
        records=instance.records(key=16)
    else:
        words=fixture.local.fixture.packet();cases=[];ordinary=b''
        tb=fixture.make_tb(words,fixture.priority_body());records=instance.records(key=8)
    return tb,words,records,cases,ordinary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',required=True,choices=['forward','priority'])
    p.add_argument('--hls-build',required=True,type=Path)
    p.add_argument('--report',required=True,type=Path)
    p.add_argument('--local-memory',action='store_true',help='actual SAME payload backend local source DMA, with explicit transport/executor/WR-CQ lifetime MODEL')
    p.add_argument('--compiled-two-state',action='store_true',help='additional compiled full-assertion run, NOT X/Z/reset or four-state proof')
    p.add_argument('--verilator',type=Path,default=Path('/home/user/fpga-rocev2-research/verilator-v5.036-install/bin/verilator'))
    args=p.parse_args()
    if args.report.exists():p.error('preserve prior evidence; use a fresh report')
    if args.local_memory and args.case!='forward':p.error('local memory case requires forward')
    selected,manifest=delivery.verify_delivery(args.hls_build)
    instance=unit.NativeSQRTLTests();instance.setUpClass()
    try:tb,words,records,cases,ordinary=make_case(args.case,instance,args.local_memory)
    finally:instance.directory.cleanup()
    if 'force 'in tb:raise ValueError('internal forcing forbidden')
    sources,data=delivery.ORIGINAL_MODULES(args.hls_build)
    if sources.count(delivery.OLD_BRIDGE)!=1:raise ValueError('old bridge selection changed')
    sources.remove(delivery.OLD_BRIDGE);sources+=shared.SOURCES[:2]
    if len(sources)!=len(set(sources)):raise ValueError('duplicate compiler sources')
    paths=unit.input_paths(tb)+sources+data+[manifest,Path(delivery.__file__).resolve(),
        Path(__file__).resolve(),ROOT/'rdma/read/tests/rw_sim.py',ROOT/'rdma/host/rocev2_wire.py',
        ROOT/'rdma/read/host/read_wire.py',ROOT/'rdma/tests/test_icrc_rtl.py']
    if args.local_memory:paths += [Path(memory.__file__).resolve(),memory.ARBITER]
    before={str(q.relative_to(ROOT)):delivery.digest(q)for q in paths}
    run=Path(tempfile.mkdtemp(prefix='native-sq-'+args.case+'-',dir=ROOT/'rdma/rnic/build'))
    (run/'tb.v').write_text(tb);(run/'input.hex').write_text(''.join(f'{v:x}\n'for v in words))
    (run/'records.hex').write_text(''.join(f'{int.from_bytes(r,"little"):0128x}\n'for r in records))
    for q in data:shutil.copy2(q,run/q.name)
    command=['iverilog','-g2012','-s','tb','-o',str(run/'test.vvp'),str(run/'tb.v'),*map(str,sources)]
    report=dict(scope=__doc__,case=args.case,pass_test=False,terminal_exit_status=None,
        hardware_verified=False,board_integrated=False,local_payload_executor=False,native_CQ=False,
        actual_kernel_pins_or_coherent_allocation=False,standard_verbs=False,completion_claim=False,
        actual_C_UBSan_encoded_ring=True,actual_SQC1_native_decode=True,raw_SQ_MR_PTE_config_bypass=False,
        actual_native_SQ_MR_RAM_router_mux_generic_PCIe_parent_guard=True,
        actual_shared_payload_backend_local_memory_DMA=args.local_memory,
        local_transport_executor_and_WR_CQ_lifetime_model=True,
        constant_parent_proof_or_descriptor_status_RAM_agents=False,
        physical_MAC_host_AXI_root_link_host_memory_and_downstream_lifetime_models=True,
        transport_stub=False,original_generated_HLS_sha256=selected['original_generated_HLS_sha256'],
        delivery_sha256=selected['delivery_sha256'],generated_files=138,delivery_files=140,
        compiler_command=command,source_sha256=before,retained_directory=str(run.relative_to(ROOT)),
        compile_timeout_seconds=90,simulation_timeout_seconds=120,
        four_state_simulation=not args.compiled_two_state,
        compiled_two_state_additional_only=args.compiled_two_state,
        X_Z_reset_behavior_verified=False,
        original_native_protocol_byte_integrity_ownership_assertions_preserved=True,
        exact_physical_count_change=('+1actual64BcoherentSQREAD+2actualscattered65BsourceREADs'if args.local_memory else '+1actual64BcoherentSQREADonly')if args.case=='forward'else'no network payload operation')
    started=time.monotonic()
    try:
        c=subprocess.run(command,capture_output=True,text=True,timeout=90)
        (run/'compile.log').write_text(c.stdout+c.stderr);report['compiler_returncode']=c.returncode
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        vvp=(run/'test.vvp').read_text()
        names=['rocev2_native_sq_endpoint','rocev2_native_endpoint','rocev2_sq_wqe_admission',
            'rocev2_sq_dma_fetch','rocev2_sq_fetch','rocev2_sq_control_regs','rocev2_dma_client_router',
            'rocev2_mr_table','rocev2_mr_query_arbiter','rocev2_paged_memory_backend','rocev2_pcie_parent_guard']
        if args.local_memory:names.append('rocev2_memory_client_arbiter')
        counts={n:len(re.findall(r'\.scope module, "[^\"]+" "'+n+r'"',vvp))for n in names}
        if not all(v==1 for v in counts.values()):raise ValueError('actual fused hierarchy mismatch: '+str(counts))
        report['actual_elaborated_module_counts']=counts
        sim_started=time.monotonic()
        if args.compiled_two_state:
            # Reuse the established5.036bounded compiler/fork settings. The
            # prior Icarus compile above separately verifies the EXACT enabled
            # hierarchy; it is elaboration only, not four-state execution.
            import fast_transport_sim as fast
            old_modules=fast.rw_sim.modules;old_tempfile=fast.tempfile
            def selected_modules(project):
                if project.resolve()!=args.hls_build.resolve():raise ValueError('unexpected compiled delivery')
                v,d=delivery.ORIGINAL_MODULES(project)
                if v.count(delivery.OLD_BRIDGE)!=1:raise ValueError('compiled old bridge selection changed')
                v.remove(delivery.OLD_BRIDGE);return v,d
            class ExistingRun:
                @staticmethod
                def mkdtemp(**kwargs):return str(run)
            fast.TOOL=args.verilator.resolve();fast.rw_sim.modules=selected_modules;fast.tempfile=ExistingRun
            # The helper owns fresh compile.log/simulation.log paths itself.
            # Preserve the earlier independent Icarus elaboration diagnostics.
            (run/'compile.log').rename(run/'iverilog-elaboration.log')
            report.update(compile_timeout_seconds=600,simulation_timeout_seconds=30,
                iverilog_elaboration_command=command,iverilog_elaboration_only=True)
            try:output,identity=fast.simulate(tb,{'input.hex':words,'records.hex':[int.from_bytes(r,'little')for r in records]},args.hls_build)
            finally:fast.rw_sim.modules=old_modules;fast.tempfile=old_tempfile
            report['compiled_identity']=identity
            report['compiled_helper_aggregate_scope']='all140delivered files; raw138aggregate separately verified'
            report['compiler_command']=json.loads((run/'inputs.json').read_text())['command']
            report['simulation_seconds']=identity['simulation_seconds'];report['simulator_returncode']=0
            report['artifact_compiled_binary_sha256']=identity['compiled_binary_sha256']
        else:
            try:s=subprocess.run(['vvp',str(run/'test.vvp')],cwd=run,capture_output=True,text=True,timeout=120)
            except subprocess.TimeoutExpired as error:
                def decoded(x):return x.decode(errors='replace')if isinstance(x,bytes)else(x or '')
                (run/'simulation.log').write_text(decoded(error.stdout)+decoded(error.stderr)+'\nHARNESS_WALL_TIMEOUT_WITHOUT_FUNCTIONAL_RESULT\n')
                report.update(simulation_seconds=time.monotonic()-sim_started,observation_timeout=True);raise
            report['simulation_seconds']=time.monotonic()-sim_started
            (run/'simulation.log').write_text(s.stdout+s.stderr);report['simulator_returncode']=s.returncode
            if s.returncode or 'ERROR:'in s.stdout+s.stderr:raise ValueError('actual native SQ/HLS assertions failed')
            output=s.stdout
        print(output,flush=True)
        def rows(prefix):return [json.loads(l[len(prefix)+1:])for l in output.splitlines()if l.startswith(prefix+' ')]
        result=rows('NATIVE_SQ_RESULT')
        if len(result)!=1 or not result[0]['pass_test']or result[0]['work_results']!=1 or result[0]['fetches']!=1 or result[0]['SQ_CSR_commands']!=4:
            raise ValueError('missing actual SQ/owner result')
        report['SQ_summary']=result[0]
        # Independent all128coherent bytes were also checked against real C
        # records inside the runtime model, not just the first decoded WQE.
        if args.case=='forward':
            base=rows('RESULT');pci=rows('PCIE_RESULT');eth=rows('ETH_RESULT')
            if len(base)!=1 or len(pci)!=1 or len(eth)!=1 or not all(r[0]['pass_test']for r in [base,pci,eth]):
                raise ValueError('original native incoming assertions missing')
            frames=fixture.native.dual.probe.rw_sim.ethernet_frames(output)
            good=[c for c in cases if not c.get('expected_error')and not c.get('expected_integrity_drop')]
            if len(frames)!=len(good)or len(frames)!=5:raise ValueError('original native response count')
            checked=[]
            for frame,case in zip(frames,good):
                if frame[:14]!=bytes.fromhex('b8830367c5d08af3fbb975310800')or shared.fixture.probe.rocev2_wire.internet_checksum(frame[14:34]):
                    raise ValueError('wire Ethernet/IPv4 checksum')
                if case['operation']=='read':
                    d=shared.fixture.probe.read_wire.decode(frame)
                    if d['opcode']!=shared.fixture.probe.read_wire.ONLY or d['payload']!=shared.fixture.probe.PAYLOAD or d['syndrome']&0xe0:
                        raise ValueError('READ payload/ACK')
                else:
                    d=shared.fixture.probe.rocev2_wire.decode_ethernet(frame)
                    if d['opcode']!=0x11 or not d['icrc_valid']or d['aeth_syndrome']&0xe0:raise ValueError('WRITE ACK')
                if d['psn']!=case['psn']or d['destination_qpn']!=196:raise ValueError('wire peer/PSN')
                checked.append(dict(operation=case['operation'],PSN=case['psn'],Ethernet_hex=frame.hex(),
                    read_payload_bytes_verified=65 if case['operation']=='read'else 0,IPv4_ICRC_QPN_PSN_AETH_checked=True))
            rx=fixture.native.dual.frames(output,'HOST_RX');tx=fixture.native.dual.frames(output,'HOST_TX')
            if len(rx)!=1 or len(tx)!=1 or rx[0][0]!=ordinary or tx[0][0]!=ordinary or not all(u==0x0123456789abcdef012345678 for u in rx[0][1])or not all(u==0x9234<<1 for u in tx[0][1]):
                raise ValueError('ordinary host payload/sidebands')
            if result[0]['physical_descriptors']!=(15 if args.local_memory else 13):raise ValueError('native+SQ physical count')
            if args.local_memory:
                local=rows('NATIVE_MEMORY_RESULT')
                if len(local)!=1 or not local[0]['pass_test']or local[0]['payload_bytes_checked']!=65 or local[0]['local_memory_operations']!=1 or local[0]['native_RDMA_completion']:
                    raise ValueError('actual local payload DMA result missing or false RDMA completion')
                report['local_memory_summary']=local[0]
            report.update(summary=base[0],PCIe_summary=pci[0],Ethernet_summary=eth[0],responses=checked,
                WRITE_bytes_verified=130,READ_bytes_verified=195,all_ordinary_host_sidebands_checked=True)
        else:
            if result[0]['physical_descriptors']!=1 or not result[0]['stale_key_denied_after_actual_MR_invalidate']:
                raise ValueError('actual pre-MR fetch priority case')
        delivery.verify_delivery(args.hls_build)
        if before!={n:delivery.digest(ROOT/n)for n in before}:raise ValueError('consumed source changed')
        report.update(pass_test=True,terminal_exit_status=0,source_sha256_before_after_equal=True,
            coherent_ring_bytes_verified=128,actual_native_kernel_callbacks_or_payload_execution=False)
    except Exception as error:
        report.update(error_type=type(error).__name__,error=str(error),terminal_exit_status=1);raise
    finally:
        report['elapsed_seconds']=time.monotonic()-started
        report['artifact_sha256']={str(q.relative_to(ROOT)):delivery.digest(q)for q in run.iterdir()if q.is_file()}
        if (run/'obj/Vtb').is_file():report['artifact_sha256'][str((run/'obj/Vtb').relative_to(ROOT))]=delivery.digest(run/'obj/Vtb')
        with args.report.open('x')as out:json.dump(report,out,indent=2);out.write('\n')


if __name__=='__main__':main()
