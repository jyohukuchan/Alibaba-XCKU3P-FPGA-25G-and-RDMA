#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Generate same full READ/WRITE/SEND/Immediate plus segmented SEND RX HLS.

All44 actual old/new modes and unchanged owned Atomic RTL compatibility are
required. Preserve every inherited synthesis/source/1500MiB/4ns/default1.08ns/
8QP/2000/port gate, plus the distinct whole-receive output. Not native/Linux/
physical/timing qualification; never installs, loads or programs hardware.
"""
import ast
import json
from pathlib import Path
import re
import tempfile
import build_native_segmented_immediate as base

ROOT=base.ROOT;digest=base.digest


def verify_receive_evidence(report):
    import sys
    sys.path.insert(0,str(ROOT/'rdma/rnic/tests'))
    from probe_segmented_receive_hls import verify_receive
    tests=report.get('tests',{})
    if not report.get('all21_prior_modes_retained') or report.get('receive_buffer_max_bytes')!=1048576:
        raise ValueError('all prior modes and new receive extent required')
    for mode,op in [('rx-send',3),('rx-imm',5)]:
        t=tests[mode];s=t.get('summaries',{}).get('SEGMENTED_RECEIVE_HLS',{})
        if (s.get('opcode'),s.get('whole_messages'),s.get('packets'),s.get('max_bytes'))!=(op,6,284,1048576) or \
           not all(s.get(n)for n in ['full620_posted_context','capacity_not_actual_length','MSN_only_on_LAST',
               'actual_payload_ACK_PSN_required','separate_packet_and_whole_receipts','PSN_wrap']):
            raise ValueError('actual receive payload/ACK/PSN/whole ownership required:'+mode)
        actual=verify_receive((ROOT/report['directory']/(mode+'.log')).read_text(),op)
        if t.get('independent_receive_oracles')!=actual:raise ValueError('unedited full receive log oracle required')
    for kind in range(21):
        mode='rx-bad'+str(kind)
        if tests[mode].get('exit')!=0 or 'SEGMENTED_RECEIVE_NEGATIVE '+str(kind) not in (ROOT/report['directory']/(mode+'.log')).read_text():
            raise ValueError('actual owner/sequence/extent/padding rejection required:'+mode)


def builder_source():
    import segmented_receive_transport as candidate
    once=candidate.once;t=Path(base.__file__).read_text();a=t.index('"""');b=t.index('"""',a+3)+3
    t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import build_native_zero_service as parent',
        'import build_native_zero_service as parent\nimport re\nfrom build_native_segmented_receive import verify_receive_evidence')
    t=once(t,"    if not all(r.get(n)",
        "    modes|={'rx-send','rx-imm',*['rx-bad'+str(i)for i in range(21)]}\n    verify_receive_evidence(r)\n    if not all(r.get(n)")
    t=once(t,'all21 actual old and new consumer modes','all44 actual old and new consumer modes')
    t=once(t,"inputs=[Path(__file__).resolve(),Path(parent.__file__).resolve(),Path(__file__).with_name('segmented_immediate_transport.py')",
        "inputs=[Path(__file__).resolve(),ROOT/'rdma/rnic/hls/build_native_segmented_receive.py',ROOT/'rdma/rnic/hls/build_native_segmented_immediate.py',"
        "Path(parent.__file__).resolve(),ROOT/'rdma/rnic/hls/segmented_immediate_transport.py',ROOT/'rdma/rnic/hls/segmented_receive_transport.py',"
        "ROOT/'rdma/rnic/tests/probe_segmented_receive_hls.py'")
    t=once(t,"prefix='segmented-immediate-HLS-wrapper-'","prefix='segmented-receive-HLS-wrapper-'")
    t=once(t,"argv=sys.argv;top=parent.TOP;result=", "argv=sys.argv;top=parent.TOP;extra_port=False;result=")
    t=once(t,"parent.TOP='rocev2_native_segmented_immediate_top'","parent.TOP='rocev2_native_segmented_receive_top'")
    t=once(t,'        parent.main()',r'''
        parent.main()
        checked=json.loads(raw.read_text());rtl=ROOT/checked['directory']/'project/solution1/syn/verilog'
        top=(rtl/(parent.TOP+'.v')).read_text()
        if not re.search(r'\[\s*775\s*:\s*0\s*\]\s*m_axis_recv_message_TDATA\s*;',top):
            raise ValueError('actual distinct byte-rounded776-bit whole receive port required')
        extra_port=True''')
    t=once(t,'receive_buffer_max_bytes=4096,true_segmented_Immediate_LAST_only=True,',
        'receive_buffer_max_bytes=1048576,true_segmented_Immediate_LAST_only=True,segmented_SEND_Immediate_receive=True,segmented_WRITE_Immediate_receive=False,whole_receive_port776_verified=extra_port,')
    t=once(t,"        if not same:result['pass_test']=False", "        if not same or not extra_port:result['pass_test']=False")
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='segmented-receive-builder-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'builder.py';frozen.write_text(builder_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
