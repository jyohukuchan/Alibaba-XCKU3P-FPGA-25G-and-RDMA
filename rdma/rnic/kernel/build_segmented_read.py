#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Freeze/build private RNC16383/CQC63/profile5 against real running headers.

Require exact actual all30 native READ/old-case success; preserve all source
gates/defaults. No install/load/live callbacks/physical/timing qualification.
"""
import ast
from pathlib import Path
import build_segmented as parent
import derive_segmented_read_kernel as candidate


def runner_source():
    t=parent.runner_source();once=candidate.once
    a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    t=once(t,'import derive_segmented_kernel as candidate','import derive_segmented_read_kernel as candidate')
    t=once(t,"'verbs_segmented_wqe.c','verbs_segmented_wqe.h']))",
        "'verbs_segmented_wqe.c','verbs_segmented_wqe.h','wqe_segmented_read.c','wqe_segmented_read.h',"
        "'verbs_segmented_read_wqe.c','verbs_segmented_read_wqe.h']))")
    t=once(t,"prefix='segmented-kernel-frozen-'","prefix='segmented-read-kernel-frozen-'")
    t=once(t,'private_segmented_profile=4,matched_RNC_features=8191,matched_CQC_features=31,large_WRITE_SEND_max_bytes=1048576)',
        'private_segmented_profile=5,matched_RNC_features=16383,matched_CQC_features=63,large_WRITE_SEND_max_bytes=1048576,large_READ_max_bytes=1048576)')
    t=once(t,"wanted=['as02_segmented_wqe_validate'",
        "wanted=['as02_segmented_read_wqe_validate','as02_segmented_read_wqe_encode','as02_segmented_read_wqe_decode',\n"
        "            'as02_segmented_read_wqe_from_ib_send_wr','as02_segmented_wqe_validate'")
    t=once(t,"p.add_argument('--report',type=Path,required=True);a=p.parse_args()",
        "p.add_argument('--report',type=Path,required=True);p.add_argument('--native-report',type=Path,required=True);a=p.parse_args()")
    t=once(t,"    parent=ROOT/'external/corundum/modules/mqnic'",r'''
    native=json.loads(a.native_report.read_text())
    if not native.get('pass_test')or not native.get('source_unchanged')or len(native.get('tests',{}))!=30 or \
       (native.get('RNC_features'),native.get('CQC_features'))!=(16383,63)or not native.get('large_READ_native_runtime'):
        raise ValueError('exact actual all30 native READ profile required')
    for field in ['source_sha256','artifact_sha256','RAM_artifact_sha256']:
        for n,h in native[field].items():
            q=Path(n);q=q if q.is_absolute()else ROOT/q
            if digest(q)!=h:raise ValueError('native source/model evidence changed:'+n)
    parent=ROOT/'external/corundum/modules/mqnic' ''')
    t=once(t,'before,frozen=freeze(run,parent);report.update(source_sha256=before,frozen_input_sha256=frozen)',
        'before,frozen=freeze(run,parent);before[str(a.native_report.resolve().relative_to(ROOT))]=digest(a.native_report.resolve());\n'
        '        report.update(source_sha256=before,frozen_input_sha256=frozen)')
    ast.parse(t);return t


def main():
    exec(compile(runner_source(),str(Path(__file__).resolve()),'exec'),
        dict(__name__='__main__',__file__=str(Path(__file__).resolve())))


if __name__=='__main__':main()
