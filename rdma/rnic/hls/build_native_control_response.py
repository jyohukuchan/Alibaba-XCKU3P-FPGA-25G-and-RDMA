#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Generate same full WRITE/RNR plus typed480/512 control ACK/NAK HLS.

All87 previous actual modes plus18 control modes/independent full identities
and real legacy service compatibility required. Preserve original1500MiB/
7200s/4ns/default1.08ns/8QP/2000/old ports. NOT native/physical/timing proof.
"""
import ast
import json
from pathlib import Path
import sys
import tempfile
import build_native_segmented_write_owned as parent

ROOT=parent.ROOT;digest=parent.digest


def verify_control_evidence(r):
    sys.path.insert(0,str(ROOT/'rdma/rnic/tests'))
    from probe_control_response_hls import MODES,verify_control
    from audit_segmented_receive import bindings
    old,_=bindings('segmented-write-owned-hls-001')
    if len(old['tests'])!=87 or not old['pass_test']or len(r.get('tests',{}))!=105 or set(r['tests'])!=set(old['tests'])|set(MODES)or \
       not all(r.get(n)for n in ['typed480_control_owner','actual512_control_header_receipt','all87_prior_modes_retained']):
        raise ValueError('all87 original plus18 actual control consumers required')
    # Exact subset view for the unchanged87-mode verifier; new105 modes are
    # independently mandatory. No observed output/token/snapshot is rewritten.
    parent.verify_write_owned_evidence(dict(r,tests={n:r['tests'][n]for n in old['tests']}))
    for n,t in old['tests'].items():
        for key in ['summaries','prior_wire_oracles','independent_read_oracles','independent_receive_oracles',
            'independent_immediate_wire_oracles','independent_write_receive_oracles','independent_write_packet_oracles']:
            if key in t and r['tests'][n].get(key)!=t[key]:raise ValueError('original actual consumer outcome changed:'+n+':'+key)
    actual=verify_control((ROOT/r['directory']/'control-headers.log').read_text())
    if r['tests']['control-headers']['independent_control_oracles']!=actual:raise ValueError('every actual control identity/header/MSN byte required')
    s=r['tests']['control-headers']['summaries']['CONTROL_RESPONSE_HLS']
    if (s['events'],s['owner_bits'],s['receipt_bits'],s['actual_MSN'])!=(5,480,512,1)or \
       not all(s.get(n)for n in ['same_actual_PSN_table_unchanged','actual_ACK_consumer_required','no_payload_RQ_DMA_CQ_completion']):
        raise ValueError('actual nonzeroMSN/samePSN/control-only header proof required')
    for kind in range(15):
        if 'CONTROL_NEGATIVE '+str(kind)not in (ROOT/r['directory']/('control-bad'+str(kind)+'.log')).read_text():
            raise ValueError('all invalid full control owners must quarantine')


def builder_source():
    from segmented_control_response_transport import once
    t=parent.builder_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [('from build_native_segmented_write_owned import verify_write_owned_evidence',
        'from build_native_control_response import verify_control_evidence'),
        ('    verify_write_owned_evidence(r)',
         "    modes|={'control-headers','control-priority','control-rnr-bad',*['control-bad'+str(i)for i in range(15)]}\n    verify_control_evidence(r)"),
        ('all87 actual old and new consumer modes','all105 actual old and new consumer modes'),
        ("inputs=[Path(__file__).resolve(),ROOT/'rdma/rnic/hls/build_native_segmented_write_owned.py'",
         "inputs=[Path(__file__).resolve(),ROOT/'rdma/rnic/hls/build_native_control_response.py',ROOT/'rdma/rnic/hls/segmented_control_response_transport.py',"
         "ROOT/'rdma/rnic/hls/test_control_response.cpp',ROOT/'rdma/rnic/tests/probe_control_response_hls.py',ROOT/'results/2026-10-18/rocev2-rnic-segmented-write-owned-hls-001.json',ROOT/'rdma/rnic/hls/build_native_segmented_write_owned.py'"),
        ("prefix='segmented-write-owned-HLS-wrapper-'","prefix='control-response-HLS-wrapper-'"),
        ("parent.TOP='rocev2_native_segmented_write_owned_top'","parent.TOP='rocev2_native_control_response_top'"),
        ('        extra_port=True',r'''
        for name,width in [('s_axis_control_owner_TDATA',480),('m_axis_control_done_TDATA',512)]:
            if not re.search(r'\[\s*'+str(width-1)+r'\s*:\s*0\s*\]\s*'+name+r'\s*;',top):
                raise ValueError('actual separate control-response port required:'+name)
        if not re.search(r'\bregControlFault\b',top):raise ValueError('actual sticky control fault output required')
        extra_port=True'''),
        ('all87_CPP_modes_required=True,','all87_CPP_modes_required=True,all105_CPP_modes_required=True,control_owner480_and_receipt512_verified=extra_port,control_is_payload_completion=False,')]:t=once(t,old,new)
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='control-response-builder-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'builder.py';frozen.write_text(builder_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
