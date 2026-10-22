#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Wire real native selected1000 to optional retained FEC1 AXI aperture.

Keep the qualified207-file HLS and every other native leaf unchanged. The
old certificate observer and the mailbox consume once each; real native
quarantine, not mailbox visibility, guards SQC/RQC after host ACK. Source/
elaboration only: no mailbox runtime, Linux callbacks, STOP or unpin proof.
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
from check_immediate_native_elaboration import FEATURES
from segmented_write_payload_native_fixture import once

ROOT=binding.ROOT;digest=binding.digest
FEC=ROOT/'rdma/rnic/rtl/rocev2_fatal_event_mmio.v'
FANOUT=ROOT/'rdma/rnic/rtl/rocev2_fatal_event_fanout.v'
EXTRA=[('input','[999:0]','s_fatal_selected'),('input','','s_fatal_selected_valid'),
    ('output','','s_fatal_selected_ready'),('input','[7:0]','s_fatal_quarantined')]


def derive(top,sq):
    top=once(top,'.m_done(m_write_fatal_selected),','.m_done(fatal_join_selected),')
    top=once(top,'.m_done_valid(m_write_fatal_selected_valid),','.m_done_valid(fatal_join_valid),')
    top=once(top,'.m_done_ready(m_write_fatal_selected_ready),','.m_done_ready(fatal_join_ready),')
    logic='''wire [999:0] fatal_join_selected,fatal_mailbox_selected;
wire fatal_join_valid,fatal_join_ready,fatal_mailbox_valid,fatal_mailbox_ready;
// Each receiver retains valid under its own stall, independently of the
// other READY. The genuine upstream lease ends only after BOTH accept.
rocev2_fatal_event_fanout fatal_event_split(
 .clk(clk),.rst(rst),.s_data(fatal_join_selected),.s_valid(fatal_join_valid),.s_ready(fatal_join_ready),
 .m_observer_data(m_write_fatal_selected),.m_observer_valid(m_write_fatal_selected_valid),
 .m_observer_ready(m_write_fatal_selected_ready),.m_mailbox_data(fatal_mailbox_selected),
 .m_mailbox_valid(fatal_mailbox_valid),.m_mailbox_ready(fatal_mailbox_ready));
'''
    top=once(top,'reg write_fault_latched=0;',logic+'reg write_fault_latched=0;')
    matches=list(re.finditer(r'(?<!\w)native\s*\(',top))
    if len(matches)!=1:raise ValueError('one actual native SQ child required')
    i=matches[0].end();top=top[:i]+'''\n.s_fatal_selected(fatal_mailbox_selected),
.s_fatal_selected_valid(fatal_mailbox_valid),
.s_fatal_selected_ready(fatal_mailbox_ready),.s_fatal_quarantined(write_abort_quarantined),'''+top[i:]
    ports='\n'.join('    '+d+' wire '+(w+' 'if w else'')+n+','for d,w,n in EXTRA)
    sq=once(sq,'    input wire clk,',ports+'\n    input wire clk,')
    sq=once(sq,'localparam CONTROL_PORTS=SEPARATE_RQ_ENABLE ? 5 :',
        'wire fatal_event_guard,fatal_event_fault;wire [7:0] fatal_event_queue_guard,fatal_event_fault_code;\n'
        'localparam CONTROL_PORTS=SEPARATE_RQ_ENABLE ? 6 :')
    sq=once(sq,".M_BASE_ADDR(SEPARATE_RQ_ENABLE ?\n  {24'd0,24'd0,24'h405000,",
        ".M_BASE_ADDR(SEPARATE_RQ_ENABLE ?\n  {24'd0,24'd0,24'h406000,24'd0,24'd0,24'h405000,")
    sq=once(sq,".M_ADDR_WIDTH(SEPARATE_RQ_ENABLE ?\n  {32'd0,32'd0,32'd12,",
        ".M_ADDR_WIDTH(SEPARATE_RQ_ENABLE ?\n  {32'd0,32'd0,32'd12,32'd0,32'd0,32'd12,")
    sq=once(sq,'assign local_work_guard=',
        'assign local_work_guard=fatal_event_guard || (|s_fatal_quarantined) || ')
    sq=once(sq,'assign fault=','assign fault=fatal_event_fault || ')
    sq=once(sq,'assign fault_code=',"assign fault_code=fatal_event_fault ? 8'he6 : ")
    old='.wire_queue_guard(wire_queue_guard | atomic_binding_queue_guard),'
    if sq.count(old)!=2:raise ValueError('both actual SQC/RQC configuration guards required')
    sq=sq.replace(old,'.wire_queue_guard(wire_queue_guard | atomic_binding_queue_guard | fatal_event_queue_guard | s_fatal_quarantined),')
    pins={'clk':'clk','rst':'rst','parent_fault':'parent_fault','s_selected':'s_fatal_selected',
        's_selected_valid':'s_fatal_selected_valid','s_selected_ready':'s_fatal_selected_ready',
        'configuration_guard':'fatal_event_guard','queue_guard':'fatal_event_queue_guard',
        'fault':'fatal_event_fault','fault_code':'fatal_event_fault_code'}
    widths={'awaddr':24,'awprot':3,'awvalid':1,'awready':1,'wdata':32,'wstrb':4,'wvalid':1,'wready':1,
        'bresp':2,'bvalid':1,'bready':1,'araddr':24,'arprot':3,'arvalid':1,'arready':1,
        'rdata':32,'rresp':2,'rvalid':1,'rready':1}
    for name,width in widths.items():
        pins['s_axil_'+name]=f'bus_{name}[{width}*5+:{12 if name in ["awaddr","araddr"]else width}]'
    instance='''// Explicit private profile8 FEC1 extension. No default source change.
initial if(!SEPARATE_RQ_ENABLE || !CQ_MMIO_ENABLE || !RETRY_MMIO_ENABLE)
    $fatal(1,"fatal-event aperture requires reviewed full native profile");
rocev2_fatal_event_mmio fatal_events(
'''+',\n'.join(' .'+n+'('+v+')'for n,v in pins.items())+'\n);\n'
    sq=once(sq,'rocev2_native_endpoint #(',instance+'rocev2_native_endpoint #(')
    return top,sq


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all earlier evidence')
    if min(shutil.disk_usage(ROOT).free,shutil.disk_usage('/dev/shm').free)<1024**3:
        raise ValueError('original native root/RAM1GiB guard')
    names=['write-abort-event-native-elaboration-001','write-abort-event-native-full-001',
        'write-abort-event-native-runtime-diagnostics-001','fatal-event-mmio-diagnostics-001','fatal-event-fanout-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    parent,native,runtime,component,fanout=[records[n]for n in names]
    if not parent['pass_test']or not native['pass_test']or len(native['tests'])!=40 or \
       not runtime['audit_passed']or not component['audit_passed']or component['new_mailbox_native_wiring']or not fanout['pass_test']:
        raise ValueError('actual complete native40/old38 regression and separately qualified recorded MMIO component required')
    original=[ROOT/n for n in parent['selected_RTL']];data=[ROOT/n for n in parent['selected_HLS_data']]
    top=next(q for q in original if q.name=='rocev2_native_rnic_endpoint.v')
    sq=next(q for q in original if q.name=='rocev2_native_sq_endpoint.v')
    newtop,newsq=derive(top.read_text(),sq.read_text())
    before={str(q.relative_to(ROOT)):digest(q)for q in [*original,*data,FEC,FANOUT,Path(__file__).resolve(),*[binding.record(n)for n in names]]}
    if digest(FEC)!=component['source_sha256'][str(FEC.relative_to(ROOT))]:raise ValueError('same actual tested retained mailbox RTL required')
    if digest(FANOUT)!=fanout['source_sha256'][str(FANOUT.relative_to(ROOT))]:raise ValueError('same actual independently stalled fanout RTL required')
    run=Path(tempfile.mkdtemp(prefix='fatal-event-native-',dir=ROOT/'rdma/rnic/build'))
    ram=Path(tempfile.mkdtemp(prefix='as02-fatal-event-native-',dir='/dev/shm'))
    (run/top.name).write_text(newtop);(run/sq.name).write_text(newsq)
    replace={top:run/top.name,sq:run/sq.name};src=[replace.get(q,q)for q in original]+[FEC,FANOUT]
    for q in replace.values():before[str(q.relative_to(ROOT))]=digest(q)
    r=dict(scope=__doc__,pass_test=False,directory=str(run.relative_to(ROOT)),source_sha256=before,evidence=ids,
        selected_RTL=[str(q.relative_to(ROOT))for q in src],selected_HLS_data=parent['selected_HLS_data'],
        compile_limit_seconds=180,root_RAM_guard_bytes=1024**3,clock_ns=4,full_board_timing=False,hardware_verified=False,
        optional_native_FEC_base=0x406000,optional_native_FEC_bytes=0x1000,software_record_bytes=0xc0,
        actual_mailbox_native_runtime=False,actual_Linux_callbacks=False,standard_error_CQ_STOP_global_drain_unpin=False,
        RNC_features=parent['RNC_features'],CQC_features=parent['CQC_features'],software_profile=8,
        default_or_driver_capability_changed=False,both_global_HLS_drains_zero=True,
        hardware_or_default_actions=[],commit_or_push=False)
    try:
        target='rocev2_native_rnic_endpoint';cmd=['iverilog','-g2012','-s',target,'-o',str(ram/'native.vvp')]
        cmd+=['-P'+target+'.'+n+'_ENABLE=1'for n in FEATURES];cmd+=list(map(str,src));r['command']=cmd
        start=time.monotonic();c=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        (run/'compile.log').write_text(c.stdout+c.stderr);r.update(compile_seconds=time.monotonic()-start,exit=c.returncode)
        if c.returncode or any('expects'in l and 'bits'in l for l in c.stderr.splitlines()):raise ValueError('actual native FEC hierarchy/width failure')
        vvp=(ram/'native.vvp').read_text();wanted=dict(parent['module_counts'],rocev2_fatal_event_mmio=1,rocev2_fatal_event_fanout=1)
        counts={n:len(re.findall(r'\.scope module, "[^"]+" "'+re.escape(n)+r'"',vvp))for n in wanted}
        if counts!=wanted:raise ValueError('sole actual HLS/MR/PTE/nonce/ACK/FEC namespaces changed')
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('original or actual source changed:'+n)
        r.update(pass_test=True,full_native_elaboration=True,module_counts=counts,
            only_two_native_leaves_changed=True,whole_qualified_HLS207_unchanged=True,
            actual_selected_join_tracked_observer_mailbox_fanout=True,
            native_quarantine_not_mailbox_ACK_guards_actual_SQC_RQC=True,
            remaining=['Real new native mailbox route/readback/ACK and all40 regressions; compilation/format replay is not live functional proof.',
                'Actual Linux QP/SQC identity/event delivery and standard error CQ/STOP/ref lifetime/recovery/timing/physical remain.'])
    except Exception as e:r.update(error_type=type(e).__name__,error=str(e));raise
    finally:
        r['artifact_sha256']={str(q.relative_to(ROOT)):digest(q)for q in run.iterdir()if q.is_file()}
        r['RAM_artifact_sha256']={str(q):digest(q)for q in ram.iterdir()if q.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,full_native_elaboration=True,compile_seconds=r['compile_seconds'],actual_mailbox_runtime=False)))


if __name__=='__main__':main()
