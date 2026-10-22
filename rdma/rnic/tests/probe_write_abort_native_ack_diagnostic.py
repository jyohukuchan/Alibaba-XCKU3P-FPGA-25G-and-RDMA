#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Observe requester ACK progress using immutable, already compiled RTL objects.

Only a new host simulation main is compiled/linked. The exact RTL/testbench
archive and all original assertions remain, with no signal writes or input/
deadline changes. This diagnostic is NOT a fresh native regression pass.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import audit_segmented_receive as binding
import probe_immediate_native_request as tool

ROOT=binding.ROOT
VERILATOR=Path('/home/user/fpga-rocev2-research/verilator-v5.036-install/share/verilator')
TOP='tb__DOT__dut__DOT__'
NAMES=['tx_response_admission_ready','tx_m_expect_psn','tx_frame_count',
    'tx_receipt_count','tx_mac_proof_count','rx_accepted_count','rx_rejected_count',
    'rx_m_axis_hls_rx_tvalid','rx_m_response_event_valid','rx_m_response_event_ready',
    'rx_m_response_event_syndrome','rx_fault','rx_fault_code','tx_fault','tx_fault_code',
    'h_request_done_valid','h_request_done_ready','h_local_hls_active',
    'write_control_fault','write_control_fault_code','write_abort_quarantined',
    'write_abort_fault','write_abort_fault_code','s_write_abort_owner_valid']


def observer(header):
    fields=set(re.findall(r'^\s*(?:CData|SData|IData|QData)/\*[^*]+\*/ (\w+);',header,re.M))
    names={n:TOP+n for n in NAMES if TOP+n in fields}
    for n in ['pe_fsmState','abort_fault','recv_bind_fault','request_fault']:
        found=[f for f in fields if f.startswith(TOP) and 'native_request_core' in f and
            f.endswith('rx_exh_fsm_512_0_U0__DOT__'+n)]
        if not found and n=='abort_fault':continue
        if len(found)!=1:raise ValueError('one real HLS parser state required:'+n)
        names['HLS_'+n]=found[0]
    for f in sorted(fields):
        if not f.startswith(TOP)or 'native_request_core__DOT__transport__DOT__'not in f:continue
        n=f.split('native_request_core__DOT__transport__DOT__')[1]
        if (re.fullmatch(r'(rx_ibh_fsm_0_U0__DOT__fsmState_\d+|as02_request_retire_join_0_U0__DOT__phase_\d+)',n) or
            re.fullmatch(r'(retrans_meta_table_0_U0|as02_request_retire_join_0_U0|merge_retrans_request_U0|retrans_pointer_table_0_U0|process_retransmissions_0_U0)__DOT__(request_fault_\d+|fault_\d+|receipt_phase_?\d*|receipt_index_?\d*|clear_index|clear_complete|receipt_entry_\w+)',n) and not any(w in n for w in ('_reg_','_fu_')) or
            re.fullmatch(r'(request_(rx_owners|ack_consumed|pointer_done|pool_done|tx_timer_done|rx_timer_done|segment_continue|inserted|issued))_U__DOT__(empty_n|full_n|push|pop)',n)):
            names['HLS_'+n]=f
    if not all(n in names for n in NAMES[:7]):raise ValueError('actual request/response counters required')
    format_string='AS02_ACK_OBSERVATION {"time_ps":%llu'+''.join(',"'+n+'":%llu'for n in names)+'}\n'
    args=['(unsigned long long)contextp->time()']+['(unsigned long long)topp->rootp->'+n for n in names.values()]
    observe='fprintf(observations,'+json.dumps(format_string)+','+','.join(args)+');fflush(observations);'
    return '''#include "verilated.h"
#include "Vtb.h"
#include "Vtb___024root.h"
#include <cstdio>
int main(int argc,char** argv,char**) {
    Verilated::debug(0);
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->commandArgs(argc,argv);
    const std::unique_ptr<Vtb> topp{new Vtb{contextp.get(),""}};
    FILE* observations=fopen("observations.jsonl","wx");
    if(!observations)return 3;
    uint64_t next_observation=0;
    while(!contextp->gotFinish()) {
        topp->eval();
        if(contextp->time()>=next_observation) {
            '''+observe+'''
            next_observation=contextp->time()+100000;
        }
        if(!topp->eventsPending())break;
        contextp->time(topp->nextTimeSlot());
    }
    topp->final();contextp->statsPrintSummary();fclose(observations);return 0;
}
''',names


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-report',required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all earlier evidence')
    native,nid=binding.bindings(a.native_report)
    if native.get('compile_exit')!=0 or native['compilation_seconds']>1200:
        raise ValueError('actual original successful native compiler required')
    previous=ROOT/native['directory'];obj=Path(native['compile_directory'])
    case=native['tests']['LARGE_SEND_IMM'];expected=case['runtime_input_sha256']
    fixed=[obj/n for n in ['Vtb__ALL.a','verilated.o','verilated_timing.o','verilated_threads.o','Vtb___024root.h','Vtb.h']]
    fixed+=[Path(native['frozen_binary_path']),Path(__file__).resolve(),binding.record(a.native_report)]
    before={str(q):binding.digest(q)for q in fixed}
    if binding.digest(Path(native['frozen_binary_path']))!=native['binary_sha256']:
        raise ValueError('original binary changed')
    if shutil.disk_usage('/dev/shm').free<1024**3:raise ValueError('1GiB RAM diagnostic guard')
    run=Path(tempfile.mkdtemp(prefix='write-abort-ack-diagnostic-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-write-abort-ack-diagnostic-',dir='/dev/shm'))
    for n,h in expected.items():
        shutil.copy2(previous/('LARGE_SEND_IMM-'+n),run/n)
        if binding.digest(run/n)!=h:raise ValueError('exact original failing-case bytes required:'+n)
    for f in [previous/'atomic-input.hex',*previous.glob('*.dat')]:shutil.copy2(f,run/f.name)
    source,names=observer((obj/'Vtb___024root.h').read_text());(run/'observer.cpp').write_text(source)
    inputs={str(q.relative_to(ROOT)):binding.digest(q)for q in run.iterdir()if q.is_file()}
    r=dict(scope=__doc__,diagnostic_completed=False,original_native_report=a.native_report,
        original_native_pass_test=native['pass_test'],original_case_exit=case['exit'],evidence=nid,
        directory=str(run.relative_to(ROOT)),RAM_directory=str(ram),source_sha256=before,
        diagnostic_input_sha256=inputs,observed_signal_fields=names,
        all_original_RTL_testbench_objects_reused=True,signal_injection=False,
        runtime_limit_seconds=30,original_deadlines_unchanged=True,
        fresh_native40_qualified=False,hardware_verified=False,full_board_timing=False,
        overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False)
    try:
        flags=['g++','-O1','-fcoroutines','-faligned-new','-fcf-protection=none','-Wno-subobject-linkage',
            '-DVM_TIMING=1','-DVM_COVERAGE=0','-DVM_SC=0','-DVM_TRACE=0','-DVM_TRACE_FST=0',
            '-DVM_TRACE_VCD=0','-DVM_TRACE_SAIF=0','-DVL_TIME_CONTEXT','-I'+str(obj),
            '-I'+str(VERILATOR/'include'),'-I'+str(VERILATOR/'include/vltstd')]
        commands=[[*flags,'-c',str(run/'observer.cpp'),'-o',str(ram/'observer.o')],
            ['g++',str(ram/'observer.o'),*[str(obj/n)for n in ['verilated.o','verilated_timing.o','verilated_threads.o','Vtb__ALL.a']],
             '-pthread','-lpthread','-latomic','-o',str(ram/'Vtb-observe')]]
        r['observer_build_commands']=commands;start=time.monotonic()
        with(run/'observer-build.log').open('x')as log:
            for cmd in commands:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        r['observer_build_seconds']=time.monotonic()-start
        cmd=[str(ram/'Vtb-observe'),'+SEND_IMM','+IMM=89abcdef','+SEGMENTED'];r['command']=cmd;start=time.monotonic()
        with(run/'ack.log').open('x')as log:
            c=subprocess.run(cmd,cwd=run,stdout=log,stderr=subprocess.STDOUT,timeout=30,preexec_fn=tool.no_core)
        r.update(seconds=time.monotonic()-start,exit=c.returncode)
        out=(run/'ack.log').read_text();observations=[json.loads(l.split(' ',1)[1])for l in(run/'observations.jsonl').read_text().splitlines()if l.startswith('AS02_ACK_OBSERVATION ')]
        if not observations or c.returncode!=case['exit']:
            raise ValueError('diagnostic must retain actual original case outcome')
        if c.returncode and 'large actual packet issue deadline packet1 flags00 fault00'not in out:
            raise ValueError('actual original failure signature changed')
        r.update(diagnostic_completed=True,actual_original_failure_reproduced=c.returncode!=0,
            observations=observations,original_assertions_unchanged=True)
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        for n,h in {**before,**inputs}.items():
            if binding.digest(Path(n)if Path(n).is_absolute()else ROOT/n)!=h:
                raise ValueError('diagnostic mutated an original/input:'+n)
        r['artifact_sha256']={str(q.relative_to(ROOT)):binding.digest(q)for q in run.iterdir()if q.is_file()}
        r['RAM_artifact_sha256']={str(q):binding.digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(diagnostic_completed=True,exit=r['exit'],seconds=r['seconds'],last_observation=observations[-1])))


if __name__=='__main__':main()
