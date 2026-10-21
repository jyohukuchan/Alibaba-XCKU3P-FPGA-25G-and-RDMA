#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual selected-WRITE abort/checkpoint/table/clear plus ALL105 old HLS modes.

Privileged native/MAC/fence and management inputs are MODELS. The actual
HLS consumers run; this is not native/QP/global drain/unpin/physical proof.
Original600s/30s/4ns/8QP/2000 and every old independent oracle remain.
"""
import ast
from pathlib import Path
import tempfile
import probe_control_response_hls as parent

ROOT=parent.ROOT;once=parent.once
POSITIVE=['abort-partial-one','abort-partial-two','abort-empty','abort-empty-after-last','abort-fence-hold',
    'abort-table-hold','abort-msn-hold','abort-reinit','abort-perqp']
MODES=[*POSITIVE,'abort-replay','abort-msn-wrong',*['abort-bad'+str(n)for n in range(24)]]


def abort_harness():
    t=parent.control_harness()
    t=once(t,'hls::stream<as02ControlDone> control_done;',r'''hls::stream<as02ControlDone> control_done;
    hls::stream<as02WriteAbortOwner> write_abort_owners;
    hls::stream<as02WriteAbortDone> write_abort_done;
    hls::stream<as02WriteProof> write_retired;
    hls::stream<ap_uint<24>> write_abort_state_req;
    hls::stream<ap_uint<56>> write_abort_state_rsp;
    ap_uint<1> write_abort_fault=0;''')
    t=once(t,'write_owners,write_notify,recv_fault,',
        'write_owners,write_notify,write_retired,write_abort_owners,write_abort_done,write_abort_fault,write_abort_state_req,write_abort_state_rsp,recv_fault,')
    t=once(t,'write_table_enabled ? write_state_rsp:write_dummy_rsp);',
        'write_table_enabled ? write_state_rsp:write_dummy_rsp,write_abort_state_req,write_abort_state_rsp);')
    return once(t,'write_state_rsp,write_done,write_fault);','write_state_rsp,write_done,write_retired,write_fault);')


def verify_abort(output,mode):
    rows=[s.split()for s in output.splitlines()if s.startswith('WRITE_ABORT_DONE ')]
    if len(rows)!=1 or rows[0][1]!=mode:raise ValueError('one actual complete abort receipt required')
    context=0
    for width,value in [(4,14),(48,0x8af3fbb97531),(48,0xb8830367c5d0),(32,0xc0a81f02),(32,0xc0a81f01),
        (24,196),(64,0xfedcba9889abcdef),(64,0x9123456700000001),(16,17),(24,2)]:context=(context<<width)|value
    empty=mode in ['abort-empty','abort-empty-after-last'];msn=int(mode=='abort-empty-after-last')
    psn=0xfffffe if mode=='abort-empty'else 0 if mode in ['abort-partial-two','abort-empty-after-last']else 0xffffff
    syndrome=0x61 if mode=='abort-partial-one'else 0x63 if mode=='abort-empty'else 0x62
    c=(syndrome<<468)|(psn<<444)|(psn<<420)|((0xa123456700000001)<<356)|context
    p=0
    if not empty:
        off=4096 if mode=='abort-partial-two'else 0;last_psn=(0xfffffe+off//4096)&0xffffff;tag=off//4096+1
        for width,value in [(24,2),(16,17),(64,0x9123456700000001),(64,0xfedcba9876543211),(32,0x81234567),
            (64,0xe23456789abcdef0),(32,8193),(24,0xfffffe),(32,off),(32,4096),(24,last_psn),(16,tag)]:p=(p<<width)|value
    token=p|(c<<424)|(msn<<904)|((0 if empty else 0x6002 if mode=='abort-partial-two'else 0x6001)<<928)|((0 if empty else 15)<<944)
    if len(rows[0])!=6 or list(map(int,rows[0][2:4]))!=[msn,psn]or int(rows[0][4],16)!=token or int(rows[0][5],16)!=(token|(msn<<960)):
        raise ValueError('independent every full960 native-control/last-packet/MSN/MAC and992 abort receipt bit required')
    return dict(owner960=f'{token:0240x}',receipt992=f'{token|(msn<<960):0248x}',actual_MSN=msn,actual_expected_PSN=psn,empty_distinct_from_positive=empty)


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ('from probe_control_response_hls import control_harness,verify_control',
         'from probe_control_response_hls import verify_control\nfrom probe_write_abort_hls import abort_harness,verify_abort'),
        ("info.get('HLS_top')!='rocev2_native_control_response_top'","info.get('HLS_top')!='rocev2_native_write_abort_top'"),
        ("prefix='control-response-hls-'","prefix='write-abort-hls-'"),
        ("prefix='as02-control-response-hls-'","prefix='as02-write-abort-hls-'"),
        ('write_text(control_harness())','write_text(abort_harness())'),
        ("shutil.copy2(hls/'test_control_response.cpp',run/'test.cpp')",
         "(run/'abort_prior.cpp').write_text(once((hls/'test_control_response.cpp').read_text(),'int main(int argc,char **argv) {','int preceding_control_main(int argc,char **argv) {'))\n"
         "    shutil.copy2(hls/'test_write_abort.cpp',run/'test.cpp')"),
        ("['control_response','segmented_write_owned'","['write_abort','control_response','segmented_write_owned'"),
        ("Path(__file__).resolve(),ROOT/'rdma/rnic/tests/probe_control_response_hls.py',",
         "Path(__file__).resolve(),ROOT/'rdma/rnic/tests/probe_write_abort_hls.py',ROOT/'rdma/rnic/tests/probe_control_response_hls.py',"),
        (f'*{parent.MODES!r}]:',f'*{parent.MODES!r},*{MODES!r}]:'),
        ("            elif mode=='control-headers':",'''            elif mode.startswith('abort-bad'):
                if 'WRITE_ABORT_NEGATIVE '+mode[9:]not in r.stdout:raise ValueError('actual invalid abort proof must quarantine')
                markers=[]
            elif mode=='abort-replay':markers=['WRITE_ABORT_REPLAY']
            elif mode=='abort-msn-wrong':markers=['WRITE_ABORT_MSN_NEGATIVE']
            elif mode.startswith('abort-'):
                item['independent_abort_oracles']=verify_abort(r.stdout,mode);markers=['WRITE_ABORT_HLS']
            elif mode=='control-headers':'''),
        ("if len(report['tests'])!=105:raise ValueError('all87 original modes and18 actual control modes required')",
         "if len(report['tests'])!=140:raise ValueError('all105 original modes plus35 actual abort modes required')"),
        ('all87_prior_modes_retained=True,',
         'all87_prior_modes_retained=True,all105_prior_modes_retained=True,typed960_write_abort_owner=True,actual992_write_abort_receipt=True,abort_is_QP_or_global_drain=False,')]:t=once(t,old,new)
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='write-abort-hls-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
