#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Generate typed WRITE packet receipts with all87 actual consumers retained.

All65 prior modes and22 typed-WRITE cases, independent full tokens/bytes/
ACK/whole-RQ oracles and real owned-service RTL compatibility are required.
Keep original1500MiB/7200s/4ns/default1.08ns/8QP/2000/old port gates. New
424 owner/456 receipt ports are additional checks, not native/MAC/physical
or whole-board timing qualification. Never install/load/program hardware.
"""
import ast
import json
from pathlib import Path
import tempfile
import build_native_segmented_receive as base

ROOT=base.ROOT;digest=base.digest


def verify_write_owned_evidence(r):
    import sys
    sys.path.insert(0,str(ROOT/'rdma/rnic/tests'))
    from probe_segmented_write_owned_hls import verify_packet_receipts
    from probe_segmented_write_receive_hls import verify_write_receive
    if not r.get('all65_prior_modes_retained')or not r.get('typed424_remote_write_owner')or not r.get('actual456_write_packet_receipt')or len(r['tests'])!=87:
        raise ValueError('all87 actual full-core modes and typed424/456 required')
    for mode in ['write-rx','write-rx-imm']:
        log=(ROOT/r['directory']/(mode+'.log')).read_text();t=r['tests'][mode]
        if t.get('independent_write_packet_oracles')!=verify_packet_receipts(log)or \
           t.get('independent_write_receive_oracles')!=verify_write_receive(log,mode=='write-rx-imm'):
            raise ValueError('actual full-token and complete byte/ACK/whole-RQ oracles required')
        s=t['summaries']['WRITE_PACKET_HLS']
        if (s['packets'],s['max_bytes'])!=(284,1048576)or not all(s.get(k)for k in ['full424_owner','actual_payload_EOF_ACK_MSN_same_PSN_table','RQ_not_remote_packet_owner']):
            raise ValueError('actual same consumers and distinct native424 owner required')
    hold=r['tests']['write-owned-hold']['summaries']['WRITE_PACKET_HOLD']
    if not all(hold.get(k)for k in ['missing_owner_blocks','actual_payload_EOF_required','actual_ACK_MSN_required',
        'actual_same_PSN_table_required','consumer_withholding_blocks']):raise ValueError('withheld actual consumers must block new receipt')
    for kind in range(21):
        mode='write-owned-bad'+str(kind)
        if r['tests'][mode]['exit']!=0 or 'WRITE_PACKET_NEGATIVE '+str(kind)not in (ROOT/r['directory']/(mode+'.log')).read_text():
            raise ValueError('all actual typed owner/message/RQ negatives required')


def builder_source():
    from segmented_write_owned_transport import once
    t=base.builder_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'from build_native_segmented_receive import verify_receive_evidence',
        'from build_native_segmented_receive import verify_receive_evidence\nfrom build_native_segmented_write_owned import verify_write_owned_evidence')
    t=once(t,'    verify_receive_evidence(r)',
        "    modes|={'write-rx','write-rx-imm',*['write-rx-bad'+str(i)for i in range(19)],'write-owned-hold',*['write-owned-bad'+str(i)for i in range(21)]}\n"
        '    verify_receive_evidence(r)\n    verify_write_owned_evidence(r)')
    t=once(t,'all44 actual old and new consumer modes','all87 actual old and new consumer modes')
    t=once(t,"inputs=[Path(__file__).resolve(),ROOT/'rdma/rnic/hls/build_native_segmented_receive.py'",
        "inputs=[Path(__file__).resolve(),ROOT/'rdma/rnic/hls/build_native_segmented_write_owned.py',ROOT/'rdma/rnic/hls/segmented_write_owned_transport.py',"
        "ROOT/'rdma/rnic/tests/probe_segmented_write_owned_hls.py',ROOT/'rdma/rnic/hls/build_native_segmented_receive.py'")
    t=once(t,"prefix='segmented-receive-HLS-wrapper-'","prefix='segmented-write-owned-HLS-wrapper-'")
    t=once(t,"parent.TOP='rocev2_native_segmented_receive_top'","parent.TOP='rocev2_native_segmented_write_owned_top'")
    t=once(t,'        extra_port=True',r'''
        for name,width in [('s_axis_write_owner_TDATA',424),('m_axis_write_done_TDATA',456)]:
            if not re.search(r'\[\s*'+str(width-1)+r'\s*:\s*0\s*\]\s*'+name+r'\s*;',top):
                raise ValueError('actual distinct typed WRITE port required:'+name)
        if not re.search(r'\bregWriteFault\b',top):raise ValueError('actual sticky WRITE fault output required')
        extra_port=True''')
    t=once(t,'segmented_WRITE_Immediate_receive=False,whole_receive_port776_verified=extra_port,',
        'segmented_WRITE_Immediate_receive=True,write_owner424_and_receipt456_verified=extra_port,all87_CPP_modes_required=True,whole_receive_port776_verified=extra_port,')
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='segmented-write-owned-builder-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'builder.py';frozen.write_text(builder_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
