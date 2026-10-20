#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Run unchanged36 SQC regression cases on the new read-only lookup derivative.

Actual CSR/mailbox/fetch, physical backend/guard sources modeled as before.
No original source edit, weakened old assertion, hardware or native proof.
"""
import argparse
import json
from pathlib import Path
import tempfile
import time
import unittest
import test_sq_control_regs_rtl as legacy
import derive_atomic_owner_lookup as lookup
from wrkey_delivery_sim import digest

ROOT=legacy.ROOT


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve previous evidence')
    run=Path(tempfile.mkdtemp(prefix='atomic-sqc-regression-',dir=ROOT/'rdma/rnic/build'))
    derived=run/'rocev2_sq_control_regs.v';derived.write_text(lookup.derive())
    sources=[*legacy.SOURCES,legacy.HEADER,Path(legacy.__file__).resolve(),Path(lookup.__file__).resolve(),
        Path(__file__).resolve(),derived]
    before={str(x.relative_to(ROOT)):digest(x)for x in sources}
    old_rtl,old_sources=legacy.RTL,legacy.SOURCES
    report=dict(scope=__doc__,pass_test=False,source_sha256=before,directory=str(run.relative_to(ROOT)),
        hardware_verified=False,native_integrated=False)
    try:
        legacy.RTL=derived;legacy.SOURCES=[derived,*old_sources[1:]]
        legacy.SQControlRegsTests.reports={}
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(legacy.SQControlRegsTests)
        start=time.monotonic()
        with(run/'tests.log').open('x')as log:r=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
        report.update(seconds=time.monotonic()-start,methods=r.testsRun,
            simulations=sum(map(len,legacy.SQControlRegsTests.reports.values())),
            tests=legacy.SQControlRegsTests.reports)
        if not r.wasSuccessful()or report['methods']!=9 or report['simulations']!=36:
            raise ValueError('unchanged SQC assertions failed on lookup derivative: '+str(run/'tests.log'))
        for n,h in before.items():
            if digest(ROOT/n)!=h:raise ValueError('source changed: '+n)
        report.update(pass_test=True,source_unchanged=True)
    except Exception as e:report['error']=str(e);raise
    finally:
        legacy.RTL,legacy.SOURCES=old_rtl,old_sources
        report['artifact_sha256']={str(x.relative_to(ROOT)):digest(x)for x in run.iterdir()if x.is_file()}
        with a.report.open('x')as f:f.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(pass_test=True,methods=report['methods'],simulations=report['simulations'],seconds=report['seconds'])))


if __name__=='__main__':main()
