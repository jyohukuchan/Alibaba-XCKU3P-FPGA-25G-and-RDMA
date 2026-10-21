#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh actual native37: all36 old cases plus retained-WRITE RNR/retry.

Actual generated HLS, same MR/PTE/PCIe/nonce/fence/shared ACK/MAC/PSN/CQ.
Only physical host/root/peer/PHY/PTP are modeled. Original1200s/30s/4ns,
identities, old raw inputs/oracles and all11 remaining requirements stay.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_write_profile_native_full as parent
import segmented_write_rnr_native_sources as source
from segmented_write_payload_native_fixture import once

ROOT=source.ROOT


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ('import segmented_write_profile_native_sources as source','import segmented_write_rnr_native_sources as source'),
        ('import segmented_write_profile_native_fixture as service','import segmented_write_rnr_native_fixture as service'),
        ("prefix='segmented-write-profile-native-full-'","prefix='segmented-write-rnr-native-full-'"),
        ("prefix='as02-segmented-write-profile-native-obj-'","prefix='as02-segmented-write-rnr-native-obj-'"),
        ("prefix='as02-segmented-write-profile-native-artifacts-'","prefix='as02-segmented-write-rnr-native-artifacts-'"),
        ('planned_cases=36','planned_cases=37'),
        ("        cases=[('LARGE_RX_WRITE',8,0,",
         "        cases=[('LARGE_RX_WRITE_RNR',9,0x89abcdef,['+LARGE_WRITE_RX','+LARGE_RX_OP=5','+WRITE_RNR_RETRY'],False,-3),\n"
         "            ('LARGE_RX_WRITE',8,0,"),
        ("if len(cases)!=36:raise ValueError('all34 unchanged prior cases plus actual8193 incoming WRITE/Immediate required')",
         "if len(cases)!=37:raise ValueError('all36 unchanged old cases plus real empty-LAST-RQ RNR/same-PSN retry required')"),
        ("is_large_write=name in ['LARGE_RX_WRITE','LARGE_RX_WRITE_IMM']",
         "is_large_write=name in ['LARGE_RX_WRITE','LARGE_RX_WRITE_IMM','LARGE_RX_WRITE_RNR']"),
        ('            result.update(service.verify_large_write(output,rx_records,bool(immediate),run)if is_large_write else',
         "            result.update(service.verify_large_write_rnr(output,rx_records,run)if name=='LARGE_RX_WRITE_RNR'else\n"
         '                service.verify_large_write(output,rx_records,bool(immediate),run)if is_large_write else'),
        ('private_WRITE_profile_identity=True,SQC_features=13,RQC_features=63,software_profile=8)',
         'private_WRITE_profile_identity=True,SQC_features=13,RQC_features=63,software_profile=8,\n'
         '            complete_native_RNR_retry_runtime=True,all36_prior_cases_retained=True,real_peer_RNR_retry=False)')]:t=once(t,old,new)
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='segmented-write-rnr-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
