#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Generate actual segmented WRITE/SEND HLS, retaining every parent gate.

Original1500MiB/4ns/default1.08ns/8QP/2000-entry and old source/compatibility
gates remain mandatory. Parent builder selects this exact new top; no native
MAC/CQ/kernel/provider/physical or board-timing success is implied.
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
    request=json.loads(a.request_report.read_text());large=request.get('summaries',{}).get('SEGMENTED_REQUEST_HLS',{})
    if not request.get('pass_test') or (large.get('whole_WRs'),large.get('packets'),large.get('stored_replays'))!=(6,284,7) or \
       not all(large.get(n)for n in ['actual_FIRST_MIDDLE_LAST','single_whole_WR_receipt',
           'exact_RETH_payload_zero_padding_BTH_PSN','same_domain_PSN_wrap','withheld_ACK_timer_state_blocks_next']) or \
       request['summaries']['SEGMENTED_REQUEST_POLICY'].get('actual_no_issue_negatives')!=5 or len(request.get('wire_oracles',[]))!=291:
        raise ValueError('complete actual segmented consumers/independent wire/negative evidence required')
    inputs=[Path(__file__).resolve(),Path(parent.__file__).resolve(),Path(__file__).with_name('segmented_request_transport.py')]
    before={str(n.relative_to(ROOT)):digest(n)for n in inputs}
    run=Path(tempfile.mkdtemp(prefix='segmented-HLS-wrapper-',dir=ROOT/'rdma/rnic/build'));raw=run/'unaltered-builder-report.json'
    argv=sys.argv;top=parent.TOP;result=dict(pass_test=False,scope=__doc__,source_sha256=before)
    try:
        parent.TOP='rocev2_native_segmented_request_top'
        sys.argv=[str(Path(parent.__file__)), '--source',str(a.source),'--request-report',str(a.request_report),
            '--compat-report',str(a.compat_report),'--report',str(raw),'--tool',str(a.tool)]
        parent.main()
    finally:
        sys.argv=argv;parent.TOP=top
        if raw.exists():result=json.loads(raw.read_text())
        result.update(scope=__doc__,parent_builder_unchanged=True,
            parent_builder_report=str(raw.relative_to(ROOT)),parent_builder_report_sha256=digest(raw)if raw.exists()else None,
            large_WRITE_SEND_max_bytes=1048576,multi_SGE_implemented=False,READ_Immediate_max_bytes=4096,
            true_segmented_wire=True,one_full_WR_receipt=True,physical_or_native_integration=False)
        result.setdefault('source_sha256',{}).update(before)
        same=all(digest(ROOT/n)==h for n,h in before.items());result['wrapper_and_builder_unchanged']=same
        if not same:result['pass_test']=False
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    if not result.get('pass_test'):raise ValueError('segmented HLS generation not proved')


if __name__=='__main__':main()
