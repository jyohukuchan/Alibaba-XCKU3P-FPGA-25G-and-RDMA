#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh actual native38: old37 plus PSN NAK/suppression/retry/duplicate.

Same actual generated HLS/MR/PTE/PCIe/nonce/fence/ACK/MAC/PSN/CQ graph.
Only host/root/peer/PHY/PTP inputs modeled; original1200s/30s/4ns retained.
"""
import ast
from pathlib import Path
import tempfile
import probe_segmented_write_rnr_native_full as parent
import write_psn_control_native_sources as source
from segmented_write_payload_native_fixture import once

ROOT=source.ROOT


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ('import segmented_write_rnr_native_sources as source','import write_psn_control_native_sources as source\nimport audit_segmented_receive as source_binding'),
        ('import segmented_write_rnr_native_fixture as service','import write_psn_control_native_fixture as service'),
        ("prefix='segmented-write-rnr-native-full-'","prefix='write-psn-control-native-full-'"),
        ("prefix='as02-segmented-write-rnr-native-obj-'","prefix='as02-write-psn-control-native-obj-'"),
        ("prefix='as02-segmented-write-rnr-native-artifacts-'","prefix='as02-write-psn-control-native-artifacts-'"),
        ('planned_cases=37','planned_cases=38'),
        ('    evidence,evidence_bindings=source.validate(a.elaboration_report.resolve())',
         "    preflight,preflight_bindings=source_binding.bindings('write-psn-control-native-fixture-diagnostics-002')\n"
         "    if not preflight['audit_passed'] or not preflight['all37_case_recipes_and_raw_inputs_identical']:\n"
         "        raise ValueError('actual exact old37/new38 fixture preflight required before compilation')\n"
         '    evidence,evidence_bindings=source.validate(a.elaboration_report.resolve())'),
        ('        own.append(previous_path)',
         "        own.extend([previous_path,source_binding.record('write-psn-control-native-fixture-diagnostics-002')])\n"
         "        report['fixture_preflight']=preflight_bindings"),
        ("        cases=[('LARGE_RX_WRITE_RNR',",
         "        cases=[('LARGE_RX_WRITE_PSN',9,0x89abcdef,['+LARGE_WRITE_RX','+LARGE_RX_OP=5','+WRITE_PSN_CONTROL'],False,-3),\n"
         "            ('LARGE_RX_WRITE_RNR',"),
        ("if len(cases)!=37:raise ValueError('all36 unchanged old cases plus real empty-LAST-RQ RNR/same-PSN retry required')",
         "if len(cases)!=38:raise ValueError('all37 unchanged old cases plus real certified PSN NAK/suppression/retry/duplicate required')"),
        ("is_large_write=name in ['LARGE_RX_WRITE','LARGE_RX_WRITE_IMM','LARGE_RX_WRITE_RNR']",
         "is_large_write=name in ['LARGE_RX_WRITE','LARGE_RX_WRITE_IMM','LARGE_RX_WRITE_RNR','LARGE_RX_WRITE_PSN']"),
        ("            if is_large_read:inputs['large-read-input.hex']=",
         "            if name=='LARGE_RX_WRITE_PSN':inputs['write-psn-future-input.hex']=''.join(f'{w:037x}\\n'for w in service.future_input()[0])\n"
         "            if is_large_read:inputs['large-read-input.hex']="),
        ("            result.update(service.verify_large_write_rnr(output,rx_records,run)if name=='LARGE_RX_WRITE_RNR'else",
         "            result.update(service.verify_large_write_psn(output,rx_records,run)if name=='LARGE_RX_WRITE_PSN'else\n"
         "                service.verify_large_write_rnr(output,rx_records,run)if name=='LARGE_RX_WRITE_RNR'else"),
        ('complete_native_RNR_retry_runtime=True,all36_prior_cases_retained=True,real_peer_RNR_retry=False)',
         'complete_native_RNR_retry_runtime=True,all36_prior_cases_retained=True,real_peer_RNR_retry=False,\n'
         '            complete_native_PSN_control_runtime=True,all37_prior_cases_retained=True,real_peer_PSN_retry=False)')]:t=once(t,old,new)
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='write-psn-control-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
