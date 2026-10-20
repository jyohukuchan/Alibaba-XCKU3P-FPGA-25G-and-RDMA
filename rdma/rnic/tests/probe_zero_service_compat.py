#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Prior actual Atomic RTL service and Immediate TX/RX on the new full core.

Reuse the unchanged bounded compatibility runner/oracles. Only its derived
C++ harness adds the ordinary zero-service ports. No legacy source/report
is overwritten and no generated RTL/native/Linux/board proof is inferred.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import probe_zero_request_compat as compat
import probe_zero_service_hls as service

ROOT=service.ROOT;digest=service.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve prior evidence')
    source=a.source.resolve();info=json.loads((source/'source.json').read_text())
    if info.get('HLS_top')!='rocev2_native_zero_service_top' or not info.get('normal_zero_responder_WRITE_READ'):
        p.error('matched complete zero service source required')
    for n,h in info['derived_sources'].items():
        if digest(source/'fns'/n)!=h:raise ValueError('generated source changed: '+n)
    extra=[Path(__file__).resolve(),Path(service.__file__).resolve(),Path(compat.__file__).resolve()]
    before={str(x.relative_to(ROOT)):digest(x)for x in extra}
    run=Path(tempfile.mkdtemp(prefix='zero-service-compat-',dir=ROOT/'rdma/rnic/build'))
    raw=run/'unaltered-runner-report.json';saved_argv=sys.argv;saved_harness=compat.harness
    result=dict(scope=__doc__,pass_test=False,source_sha256=before)
    try:
        # API adaptation of the fixture only. The actual legacy runner still
        # executes all old assertions, real owned-service RTL, independent
        # RAM/operand/owner/wire oracles and its original30s runtime deadline.
        compat.harness=service.harness
        sys.argv=[str(Path(compat.__file__)), '--source',str(source),'--report',str(raw)]
        compat.main()
    finally:
        sys.argv=saved_argv;compat.harness=saved_harness
        if raw.exists():result=json.loads(raw.read_text())
        result.update(scope=__doc__,compatibility_runner_unchanged=True,
            only_derived_harness_extended=True,HLS_top=info['HLS_top'],
            raw_runner_report=str(raw.relative_to(ROOT)),raw_runner_report_sha256=digest(raw)if raw.exists()else None)
        result.setdefault('source_sha256',{}).update(before)
        same=all(digest(ROOT/n)==h for n,h in before.items())
        result['wrapper_and_harness_unchanged']=same
        if not same:result['pass_test']=False;result['source_unchanged']=False
        with a.report.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
    if not result.get('pass_test'):raise ValueError('compatibility not proved')
    print(json.dumps(dict(pass_test=True,report=str(a.report),compile_seconds=result['compile_seconds'],
        simulation_seconds=result['simulation_seconds'],service_RTL_actual=result['service_RTL_actual'])))


if __name__=='__main__':main()
