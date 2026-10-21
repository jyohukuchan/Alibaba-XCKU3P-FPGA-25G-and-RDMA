#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Private large Linux-WR adapter: real-header build plus ASan/UBSan C.

Compile/link against running kernel headers; never install/load or post.
Execute actual adapter/codec C under explicitly modeled Linux WR types.
No MR/DMA/SQ/CQ/native Linux callback or hardware-runtime claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import atomic128_kernel_models as model

ROOT = model.ROOT
KERNEL = ROOT/'rdma/rnic/kernel'
TESTS = ROOT/'rdma/rnic/tests'
NAMES = ['wqe.c', 'wqe_atomic.c', 'wqe_zero.c', 'wqe_segmented.c', 'verbs_wqe.c',
         'verbs_atomic_wqe.c', 'verbs_zero_wqe.c', 'verbs_segmented_wqe.c']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('preserve earlier evidence')
    if shutil.disk_usage(ROOT).free < 1024**3:
        raise RuntimeError('unchanged 1GiB source-build guard')
    run = Path(tempfile.mkdtemp(prefix='segmented-verbs-adapter-', dir=ROOT/'rdma/rnic/build'))
    frozen = run/'kernel'
    frozen.mkdir()
    inputs = [*[KERNEL/name for name in NAMES], *KERNEL.glob('*.h'), TESTS/'kernel_segmented_wqe.c',
              Path(__file__).resolve(), Path(model.__file__).resolve(),
              *[TESTS/name for name in ['kernel_verbs_model.h', 'kernel_cq_model.h',
                                       'kernel_sq_hw_model.h', 'kernel_queue_model.h']]]
    before = {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    for p in inputs:
        if p.parent == KERNEL:
            shutil.copy2(p, frozen/p.name)
    (frozen/'module_marker.c').write_text('#include <linux/module.h>\nMODULE_LICENSE("Dual BSD/GPL");\n')
    (frozen/'Makefile').write_text('obj-m += as02_segmented_codec_check.o\n'
        'as02_segmented_codec_check-y := '+ ' '.join(name[:-2]+'.o' for name in NAMES)+' module_marker.o\n'
        'ccflags-y += -Werror\n')
    frozen_before = {str(p.relative_to(ROOT)): digest(p) for p in frozen.iterdir() if p.is_file()}
    report = dict(scope=__doc__, pass_test=False, directory=str(run.relative_to(ROOT)), source_sha256=before,
                  frozen_input_sha256=frozen_before, actual_running_kernel_callback_execution=False,
                  installed=False, module_load_performed=False, actual_posting=False,
                  hardware_verified=False, ASan=True, UBSan=True, simulation_limit_seconds=10)
    try:
        compiler = Path(shutil.which('x86_64-linux-gnu-gcc-13')).resolve()
        command = ['make', '-C', '/lib/modules/'+os.uname().release+'/build', 'M='+str(frozen),
                   '-j4', 'CC='+str(compiler), 'W=1', 'modules']
        start = time.monotonic()
        c = subprocess.run(command, capture_output=True, text=True, timeout=120)
        (run/'kernel-build.log').write_text(c.stdout+c.stderr)
        report.update(kernel_build_command=command, kernel_build_seconds=time.monotonic()-start,
                      kernel_build_exit=c.returncode, kernel=os.uname().release)
        if c.returncode:
            raise ValueError('running-header adapter module compile/link failed')
        module = frozen/'as02_segmented_codec_check.ko'
        vermagic = subprocess.check_output(['modinfo', '-F', 'vermagic', str(module)], text=True).strip()
        if not vermagic.startswith(os.uname().release+' '):
            raise ValueError('wrong kernel module ABI')
        symbols = subprocess.check_output(['nm', '-g', '--defined-only', str(module)], text=True)
        wanted = ['as02_segmented_wqe_from_ib_send_wr', 'as02_segmented_wqe_validate',
                  'as02_segmented_wqe_encode', 'as02_segmented_wqe_decode',
                  'as02_zero_wqe_from_ib_send_wr', 'as02_atomic_wqe_from_ib_send_wr']
        if not set(wanted) <= {line.split()[-1] for line in symbols.splitlines() if line.split()}:
            raise ValueError('actual kernel adapter/codec symbols missing')
        report.update(actual_kernel_header_link=True, module_vermagic=vermagic, actual_kernel_symbols=wanted)
        headers = run/'include'
        # glibc errno.h itself includes linux/errno.h: leave that real UAPI
        # header intact, as in the existing kernel-C boundary fixtures.
        for name in ['linux/export.h', 'linux/string.h', 'linux/types.h', 'rdma/ib_verbs.h']:
            p = headers/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('#include "kernel_atomic128_model.h"\n')
        (run/'kernel_atomic128_model.h').write_text(model.MODEL)
        command = ['cc', '-std=c11', '-D_GNU_SOURCE', '-D__KERNEL__', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                   '-fsanitize=address,undefined', '-fno-sanitize-recover=undefined',
                   '-I'+str(headers), '-I'+str(run), '-I'+str(TESTS), '-I'+str(frozen),
                   '-include', str(run/'kernel_atomic128_model.h'),
                   *[str(frozen/name) for name in NAMES], str(TESTS/'kernel_segmented_wqe.c'), '-o', str(run/'cases')]
        start = time.monotonic()
        c = subprocess.run(command, capture_output=True, text=True, timeout=60)
        (run/'model-build.log').write_text(c.stdout+c.stderr)
        report.update(model_build_command=command, model_build_seconds=time.monotonic()-start, model_build_exit=c.returncode)
        if c.returncode:
            raise ValueError('actual C adapter/model compile failed')
        env = os.environ.copy()
        env['ASAN_OPTIONS'] = 'detect_leaks=1:halt_on_error=1'
        start = time.monotonic()
        c = subprocess.run([str(run/'cases')], capture_output=True, text=True, env=env, timeout=10)
        (run/'model-execution.log').write_text(c.stdout+c.stderr)
        report.update(simulation_seconds=time.monotonic()-start, simulation_exit=c.returncode)
        if c.returncode:
            raise ValueError('actual C adapter/oracles failed')
        summaries = [json.loads(line.split(' ', 1)[1]) for line in c.stdout.splitlines()
                     if line.startswith('SEGMENTED_VERBS_ADAPTER ')]
        if summaries != [dict(pass_test=True, positive_cases=54, negative_cases=14, base_SEND_ASan_guarded=True,
                              Linux_WR_types_modeled=True, actual_posting=False)]:
            raise ValueError('complete actual adapter proof absent')
        for name, expected in {**before, **frozen_before}.items():
            if digest(ROOT/name) != expected:
                raise ValueError('adapter input changed: '+name)
        report.update(pass_test=True, summary=summaries[0], source_and_frozen_inputs_unchanged=True)
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        report['artifact_sha256'] = {str(p.relative_to(ROOT)): digest(p) for p in run.iterdir() if p.is_file()}
        module = frozen/'as02_segmented_codec_check.ko'
        if module.exists():
            report['artifact_sha256'][str(module.relative_to(ROOT))] = digest(module)
        args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({key: report[key] for key in ['pass_test', 'kernel_build_seconds', 'simulation_seconds', 'summary', 'directory']}))


if __name__ == '__main__':
    main()
