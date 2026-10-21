#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Generate SAME full HLS with typed960 WRITE-abort/992 receipt, never QP drain.

Require all105 old outcomes/oracles and35 actual abort modes plus unchanged
legacy owned Atomic/Immediate service. Keep1500MiB/7200s/4ns/default1.08ns/
8QP/2000 and all old ports. No native/global drain/physical/timing claim.
"""
import ast
import json
from pathlib import Path
import sys
import tempfile
import build_native_control_response as parent

ROOT=parent.ROOT;digest=parent.digest


def verify_abort_evidence(r):
    sys.path.insert(0,str(ROOT/'rdma/rnic/tests'))
    from probe_write_abort_hls import MODES,POSITIVE,verify_abort
    from audit_segmented_receive import bindings
    old,_=bindings('control-response-hls-003')
    if not old['pass_test']or len(old['tests'])!=105 or len(r.get('tests',{}))!=140 or \
       set(r['tests'])!=set(old['tests'])|set(MODES)or not all(r.get(k)for k in
       ['pass_test','source_unchanged','full_top_CPP_compiled','all105_prior_modes_retained',
        'typed960_write_abort_owner','actual992_write_abort_receipt'])or r.get('abort_is_QP_or_global_drain')is not False:
        raise ValueError('actual all105 original plus35 abort modes, distinct960/992 not a QP/global drain required')
    if (r['compile_limit_seconds'],r['runtime_limit_seconds'])!=(600,30)or r['compile_seconds']>600 or \
       any(t['exit']or t['seconds']>30 for t in r['tests'].values()):raise ValueError('all original600s/30s gates required')
    # Exact old105 subset for the unmodified verifier, not a rewritten result.
    parent.verify_control_evidence(dict(r,tests={n:r['tests'][n]for n in old['tests']}))
    for n,t in old['tests'].items():
        for key,value in t.items():
            if key=='summaries'or 'oracle'in key:
                if r['tests'][n].get(key)!=value:raise ValueError('original actual outcome changed:'+n+':'+key)
    for n in POSITIVE:
        t=r['tests'][n];output=(ROOT/r['directory']/(n+'.log')).read_text()
        if t.get('independent_abort_oracles')!=verify_abort(output,n):raise ValueError('independent every960/992 bit required:'+n)
        s=t['summaries']['WRITE_ABORT_HLS']
        if (s['owner_bits'],s['receipt_bits'])!=(960,992)or not all(s.get(k)for k in
            ['pass_test','actual_retire_checkpoint_and_same_tables','actual_selected_state_clear_verified','not_QP_global_or_native_DMA_drain']):
            raise ValueError('actual checkpoint/table/selected state clear consumers required:'+n)
    for n,marker in [('abort-replay','WRITE_ABORT_REPLAY'),('abort-msn-wrong','WRITE_ABORT_MSN_NEGATIVE')]:
        if not r['tests'][n]['summaries'][marker]['pass_test']:raise ValueError('actual replay/MSN negative required')
    for kind in range(24):
        if 'WRITE_ABORT_NEGATIVE '+str(kind)not in (ROOT/r['directory']/('abort-bad'+str(kind)+'.log')).read_text():
            raise ValueError('all invalid abort owners must quarantine')


def builder_source():
    from segmented_write_abort_transport import once
    t=parent.builder_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ('from build_native_control_response import verify_control_evidence','from build_native_write_abort import verify_abort_evidence'),
        ('    verify_control_evidence(r)',
         "    verify_abort_evidence(r)\n    from probe_write_abort_hls import MODES as abort_modes\n    modes|=set(abort_modes)"),
        ('all105 actual old and new consumer modes','all140 actual old and new consumer modes'),
        ("inputs=[Path(__file__).resolve(),ROOT/'rdma/rnic/hls/build_native_control_response.py'",
         "inputs=[Path(__file__).resolve(),ROOT/'rdma/rnic/hls/build_native_write_abort.py',ROOT/'rdma/rnic/hls/segmented_write_abort_transport.py',"
         "ROOT/'rdma/rnic/hls/test_write_abort.cpp',ROOT/'rdma/rnic/tests/probe_write_abort_hls.py',ROOT/'rdma/rnic/tests/probe_write_abort_compat.py',"
         "ROOT/'results/2026-10-18/rocev2-rnic-control-response-hls-003.json',ROOT/'rdma/rnic/hls/build_native_control_response.py'"),
        ("prefix='control-response-HLS-wrapper-'","prefix='write-abort-HLS-wrapper-'"),
        ("parent.TOP='rocev2_native_control_response_top'","parent.TOP='rocev2_native_write_abort_top'"),
        ('        extra_port=True',r'''
        for name,width in [('s_axis_write_abort_owner_TDATA',960),('m_axis_write_abort_done_TDATA',992)]:
            if not re.search(r'\[\s*'+str(width-1)+r'\s*:\s*0\s*\]\s*'+name+r'\s*;',top):
                raise ValueError('actual distinct WRITE-abort port required:'+name)
        if not re.search(r'\bregWriteAbortFault\b',top):raise ValueError('actual sticky abort fault required')
        extra_port=True'''),
        ('all105_CPP_modes_required=True,',
         'all105_CPP_modes_required=True,all140_CPP_modes_required=True,write_abort_owner960_and_receipt992_verified=extra_port,abort_is_QP_or_global_drain=False,')]:t=once(t,old,new)
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='write-abort-builder-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'builder.py';frozen.write_text(builder_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
