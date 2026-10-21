#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Unchanged old owned Atomic RTL service and Immediate TX/RX on new RX HLS.

Same actual service RTL/consumer assertions and30s limit. Only the existing
READ-capable harness supplies the current internal type signatures. No new
native, physical, live Linux or whole-board timing qualification.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import probe_zero_request_compat as compat
import probe_segmented_read_hls as read

ROOT=read.ROOT;digest=read.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    source=a.source.resolve();info=json.loads((source/'source.json').read_text())
    if info.get('HLS_top')!='rocev2_native_segmented_receive_top' or not info.get('segmented_SEND_Immediate_receive') or \
       (info.get('receive_buffer_max_bytes'),info.get('receive_message_bits'))!=(1048576,772):
        raise ValueError('exact new complete receive source required')
    for n,h in info['derived_sources'].items():
        if digest(source/'fns'/n)!=h:raise ValueError('source changed:'+n)
    extra=[Path(__file__).resolve(),Path(read.__file__).resolve(),Path(read.old.__file__).resolve(),Path(compat.__file__).resolve()]
    before={str(n.relative_to(ROOT)):digest(n)for n in extra}
    run=Path(tempfile.mkdtemp(prefix='segmented-receive-compat-',dir=ROOT/'rdma/rnic/build'))
    raw=run/'unaltered-runner-report.json';argv=sys.argv;saved=compat.harness
    result=dict(scope=__doc__,pass_test=False,source_sha256=before)
    try:
        compat.harness=read.harness
        sys.argv=[str(Path(compat.__file__)),'--source',str(source),'--report',str(raw)]
        compat.main()
    finally:
        sys.argv=argv;compat.harness=saved
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
