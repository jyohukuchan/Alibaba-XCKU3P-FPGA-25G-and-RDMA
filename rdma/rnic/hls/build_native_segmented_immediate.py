#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Generate same READ/WRITE/SEND/Immediate HLS after all real consumers pass.

Original builder/1500MiB free-space guard/frozen identity/ports/4ns/default
1.08ns/8QP/2000-entry gates remain. Generation is NOT timing/native/physical
qualification. Retain all11 prior READ modes and add actual Immediate modes.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import build_native_zero_service as parent

ROOT=parent.ROOT;digest=parent.digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['source','request-report','compat-report','report']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--tool',type=Path,default=Path('/home/user/amd/2025.2/Vitis/bin/vitis-run'));a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    r=json.loads(a.request_report.read_text());tests=r.get('tests',{})
    modes={'prior','read',*['bad'+str(i)for i in range(9)],'imm-send','imm-write',*['imm-bad'+str(i)for i in range(8)]}
    if not all(r.get(n)for n in ['pass_test','source_unchanged','full_top_CPP_compiled','all11_prior_modes_retained'])or \
       set(tests)!=modes or any(t.get('exit')!=0 or t.get('seconds',31)>30 for t in tests.values())or r.get('runtime_limit_seconds')!=30:
        raise ValueError('all21 actual old and new consumer modes within original30s limits required')
    for mode,op in [('imm-send',5),('imm-write',6)]:
        s=tests[mode].get('summaries',{}).get('SEGMENTED_IMMEDIATE_HLS',{})
        if (s.get('WR_opcode'),s.get('whole_WRs'),s.get('packets'),s.get('stored_replays'),s.get('max_bytes'))!=(op,6,284,13,1048576)or \
           not all(s.get(n)for n in ['Immediate_only_on_LAST','whole_owner_and_shared_PSN','actual_ACK_pointer_pool_timer_consumers','withheld_ACK_timer_state_blocks_next'])or \
           len(tests[mode].get('independent_immediate_wire_oracles',[]))!=297:
            raise ValueError('actual whole Immediate/replay/timer/full independent wire evidence required:'+mode)
    read=tests['read'].get('summaries',{}).get('SEGMENTED_READ_HLS',{})
    if (read.get('whole_WRs'),read.get('response_packets'),read.get('stored_request_replays'),read.get('max_bytes'))!=(4,278,4,1048576)or \
       not all(read.get(n)for n in ['one_request_and_whole_WR_receipt','actual_header_parser_payload_pointer_pool_timer_state','withheld_payload_timers_state_block_completion'])or \
       tests['read'].get('independent_read_oracles')!={'requests':8,'response_packets':278,'independent_wire_payload_oracles':True}:
        raise ValueError('all actual old READ consumers required')
    prior=tests['prior'].get('summaries',{});large=prior.get('SEGMENTED_REQUEST_HLS',{})
    if (large.get('whole_WRs'),large.get('packets'),large.get('stored_replays'))!=(6,284,7)or \
       not all(large.get(n)for n in ['actual_FIRST_MIDDLE_LAST','single_whole_WR_receipt','exact_RETH_payload_zero_padding_BTH_PSN','same_domain_PSN_wrap','withheld_ACK_timer_state_blocks_next'])or \
       prior.get('SEGMENTED_REQUEST_POLICY',{}).get('actual_no_issue_negatives')!=5 or len(tests['prior'].get('prior_wire_oracles',[]))!=291:
        raise ValueError('all original segmented WRITE/SEND consumers required')
    inputs=[Path(__file__).resolve(),Path(parent.__file__).resolve(),Path(__file__).with_name('segmented_immediate_transport.py'),a.request_report.resolve(),a.compat_report.resolve()]
    before={str(n.relative_to(ROOT)):digest(n)for n in inputs}
    run=Path(tempfile.mkdtemp(prefix='segmented-immediate-HLS-wrapper-',dir=ROOT/'rdma/rnic/build'))
    raw=run/'unaltered-builder-report.json';view=run/'checked-request-report-view.json'
    # Only adapt the old report schema. Every value, oracle and source/artifact
    # binding comes verbatim from the checked21 real process executions.
    converted=dict(r,summaries=prior,wire_oracles=tests['prior']['prior_wire_oracles'],
        original_report=str(a.request_report.resolve()),original_report_sha256=digest(a.request_report))
    view.write_text(json.dumps(converted,indent=2)+'\n')
    argv=sys.argv;top=parent.TOP;result=dict(scope=__doc__,pass_test=False,source_sha256=before)
    try:
        parent.TOP='rocev2_native_segmented_immediate_top'
        sys.argv=[str(Path(parent.__file__)),'--source',str(a.source),'--request-report',str(view),
            '--compat-report',str(a.compat_report),'--report',str(raw),'--tool',str(a.tool)]
        parent.main()
    finally:
        sys.argv=argv;parent.TOP=top
        if raw.exists():result=json.loads(raw.read_text())
        result.update(scope=__doc__,parent_builder_unchanged=True,parent_builder_report=str(raw.relative_to(ROOT)),
            parent_builder_report_sha256=digest(raw)if raw.exists()else None,
            checked_request_report_view=str(view.relative_to(ROOT)),checked_request_report_view_sha256=digest(view),
            large_READ_max_bytes=1048576,large_WRITE_SEND_max_bytes=1048576,Immediate_max_bytes=1048576,
            receive_buffer_max_bytes=4096,true_segmented_Immediate_LAST_only=True,
            physical_or_native_integration=False,multi_SGE_implemented=False)
        result.setdefault('source_sha256',{}).update(before)
        same=all(digest(ROOT/n)==h for n,h in before.items());result['wrapper_and_builder_unchanged']=same
        if not same:result['pass_test']=False
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    if not result.get('pass_test'):raise ValueError('actual HLS generation not proved')


if __name__=='__main__':main()
