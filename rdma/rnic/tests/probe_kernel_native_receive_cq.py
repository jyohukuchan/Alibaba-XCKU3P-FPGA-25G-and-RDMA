#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual kernel CQ/SQ/MR consumes exact whole generated-HLS/native CQ bytes.

Require successful current-source native CQ evidence (two RECVs, or separate
READ/WRITE/SEND requester runs). Software WQE
encoding and full-owner matching are real C; Linux primitives, physical page
pins/DMA/MMIO and teardown controller are explicit models. Not a registered
ib_device, loaded kernel driver, live physical host or hardware assertion.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

import test_kernel_cq as original

ROOT, TESTS, KERNEL = original.ROOT, original.TESTS, original.KERNEL


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-report', required=True, type=Path)
    p.add_argument('--report', required=True, type=Path)
    p.add_argument('--request-cq', action='store_true')
    a = p.parse_args()
    if a.report.exists():
        p.error('preserve previous evidence')
    native = json.loads(a.native_report.read_text())
    if not native.get('pass_test') or not native.get('source_unchanged') or not native.get('native_request_CQ_enabled' if a.request_cq else 'native_receive_CQ_enabled') or not native.get('actual_matched_generated_HLS'):
        raise ValueError('current whole actual-generated-HLS matched CQ evidence required')
    for n, h in native['source_sha256'].items():
        if digest(ROOT/n) != h:
            raise ValueError('native source changed: '+n)
    run = ROOT / native['directory']
    cases = ([(name,[run/(name+'-event.hex'),run/(name+'-records.hex'),str(op)])
        for name,op in [('READ',2),('WRITE',1),('SEND',3)]] if a.request_cq else
        [('RECV',[run/'receive-event1.hex',run/'receive-event2.hex',run/'records.hex'])])
    snapshots = list(dict.fromkeys(x for _,args in cases for x in args if isinstance(x,Path)))
    sources = original.SOURCES[:-1] + [TESTS/('kernel_native_request_cq.c' if a.request_cq else 'kernel_native_receive_cq.c')]
    inputs = sources + list(KERNEL.glob('*.h')) + [TESTS/n for n in
        ['kernel_cq_cases.c', 'kernel_cq_model.h', 'kernel_sq_hw_cases.c',
         'kernel_queue_model.h', 'kernel_sq_hw_model.h']]
    inputs += snapshots + [a.native_report.resolve(), Path(__file__).resolve()]
    before = {str(x.relative_to(ROOT)): digest(x) for x in inputs}
    report = dict(scope=__doc__, pass_test=False, hardware_verified=False,requester_CQ=a.request_cq,
        source_sha256=before, native_report=str(a.native_report), native_CQ_snapshots_unedited=True,
        real_Linux_kernel_primitives=False, ib_device_registered=False, simulation_limit_seconds=10)
    try:
        with tempfile.TemporaryDirectory(prefix='as02-kernel-native-recv-') as directory:
            d = Path(directory)
            for name in original.original.HEADERS + ['linux/io.h', 'linux/ktime.h', 'linux/lockdep.h',
                'asm/processor.h', 'linux/irq_work.h', 'linux/atomic.h', 'linux/workqueue.h', 'linux/jiffies.h']:
                h = d/'include'/name;h.parent.mkdir(parents=True, exist_ok=True)
                h.write_text('#include "kernel_cq_model.h"\n')
            command = ['cc', '-std=c11', '-D_GNU_SOURCE', '-D__KERNEL__', '-O1', '-g',
                '-Wall', '-Wextra', '-Werror', '-pthread', '-fsanitize=address,undefined',
                '-fno-sanitize-recover=undefined', '-I', str(d/'include'), '-I', str(TESTS),
                '-I', str(KERNEL), '-include', str(TESTS/'kernel_cq_model.h'),
                *map(str, sources), '-o', str(d/'cases')]
            started = time.monotonic()
            c = subprocess.run(command, capture_output=True, text=True, timeout=30)
            report['compile_seconds'] = time.monotonic()-started
            if c.returncode:
                raise RuntimeError(c.stdout+c.stderr)
            env = os.environ.copy();env['ASAN_OPTIONS'] = 'detect_leaks=1:halt_on_error=1'
            report['tests']={};total=0
            for name,args in cases:
                started = time.monotonic()
                r = subprocess.run([str(d/'cases'), *map(str, args)], env=env,
                    capture_output=True, text=True, timeout=10)
                elapsed=time.monotonic()-started;total+=elapsed
                report['tests'][name]=dict(simulation_seconds=elapsed,output=r.stdout+r.stderr)
                if r.returncode:
                    raise RuntimeError(r.stdout+r.stderr)
                prefix='KERNEL_NATIVE_REQUEST_CQ_RESULT ' if a.request_cq else 'KERNEL_NATIVE_RECV_CQ_RESULT '
                rows = [json.loads(l.split(' ', 1)[1]) for l in r.stdout.splitlines()
                    if l.startswith(prefix)]
                if len(rows) != 1 or not rows[0]['pass_test']:
                    raise ValueError('missing actual kernel native CQ result')
                report['tests'][name]['summary']=rows[0]
            after = {n: digest(ROOT/n) for n in before}
            if before != after:
                raise ValueError('consumed native/kernel evidence changed')
            report.update(pass_test=True, source_unchanged=True, simulation_seconds=total,
                summary={name:item['summary'] for name,item in report['tests'].items()})
    except Exception as e:
        report.update(error_type=type(e).__name__, error=str(e));raise
    finally:
        with a.report.open('x') as out:
            out.write(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ['pass_test', 'compile_seconds', 'simulation_seconds', 'summary']}))


if __name__ == '__main__':
    main()
