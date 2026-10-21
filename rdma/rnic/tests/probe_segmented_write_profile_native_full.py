#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh matching131071/511/13/63 execution of ALL36 actual native cases.

Only EXPECTED identity words differ. Every actual payload/owner/MR/PCIe/
fence/HLS/ACK/PSN/CQ oracle and original1200s/30s/4ns stays. No old binary,
event normalization, installed software or physical/timing qualification.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_write_native_full as parent
import segmented_write_profile_native_sources as source
from segmented_write_payload_native_fixture import once

ROOT=source.ROOT


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [('import segmented_write_native_sources as source','import segmented_write_profile_native_sources as source'),
        ('import segmented_write_payload_native_fixture as service','import segmented_write_profile_native_fixture as service'),
        ("prefix='segmented-write-native-full-'","prefix='segmented-write-profile-native-full-'"),
        ("prefix='as02-segmented-write-native-obj-'","prefix='as02-segmented-write-profile-native-obj-'"),
        ("prefix='as02-segmented-write-native-artifacts-'","prefix='as02-segmented-write-profile-native-artifacts-'"),
        ('RNC_features=65535,CQC_features=255','RNC_features=131071,CQC_features=511'),
        ('native_1MiB_WRITE_runtime=False,new_software_capability_advertised=False)',
         'native_1MiB_WRITE_runtime=False,new_software_capability_advertised=False,\n'
         '            private_WRITE_profile_identity=True,SQC_features=13,RQC_features=63,software_profile=8)')]:t=once(t,old,new)
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='segmented-write-profile-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
