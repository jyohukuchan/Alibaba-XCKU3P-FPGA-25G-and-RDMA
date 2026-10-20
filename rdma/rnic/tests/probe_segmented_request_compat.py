#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Unchanged actual Atomic RTL service and Immediate TX/RX on segmented HLS.

Only the derived fixture adds internal continuation ports. No independent
receipt, emulated service success, generated RTL or native/board claim.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import probe_zero_request_compat as compat
import probe_segmented_request_hls as segmented

ROOT=segmented.ROOT;digest=segmented.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    source=a.source.resolve();info=json.loads((source/'source.json').read_text())
    if info.get('HLS_top')!='rocev2_native_segmented_request_top' or info.get('large_WRITE_SEND_max_bytes')!=1048576:
        p.error('matched segmented full source required')
    for n,h in info['derived_sources'].items():
        if digest(source/'fns'/n)!=h:raise ValueError('derived source changed:'+n)
    extra=[Path(__file__).resolve(),Path(segmented.__file__).resolve(),Path(compat.__file__).resolve()]
    before={str(x.relative_to(ROOT)):digest(x)for x in extra}
    run=Path(tempfile.mkdtemp(prefix='segmented-request-compat-',dir=ROOT/'rdma/rnic/build'))
    raw=run/'unaltered-runner-report.json';saved_argv=sys.argv;saved_harness=compat.harness
    result=dict(scope=__doc__,pass_test=False,source_sha256=before)
    try:
        compat.harness=segmented.harness
        sys.argv=[str(Path(compat.__file__)), '--source',str(source),'--report',str(raw)]
        compat.main()
    finally:
        sys.argv=saved_argv;compat.harness=saved_harness
        if raw.exists():result=json.loads(raw.read_text())
        result.update(scope=__doc__,compatibility_runner_unchanged=True,only_derived_harness_extended=True,
            HLS_top=info['HLS_top'],raw_runner_report=str(raw.relative_to(ROOT)),
            raw_runner_report_sha256=digest(raw)if raw.exists()else None)
        result.setdefault('source_sha256',{}).update(before)
        same=all(digest(ROOT/n)==h for n,h in before.items());result['wrapper_and_harness_unchanged']=same
        if not same:result['pass_test']=False;result['source_unchanged']=False
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    if not result.get('pass_test'):raise ValueError('compatibility not proved')
    print(json.dumps(dict(pass_test=True,compile_seconds=result['compile_seconds'],
        simulation_seconds=result['simulation_seconds'],service_RTL_actual=result['service_RTL_actual'])))


if __name__=='__main__':main()
