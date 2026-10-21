#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh actual native40: every38 old case plus fatal access62/partial61.

Same actual generated208 HLS/MR/PTE/PCIe/nonce/fence/MAC/PSN/cancel graph.
Only host/root/peer/PHY/PTP modeled; original1200s/30s/4ns gates remain.
Selected1000/retained RQ/quarantine are NOT error CQ/STOP/global drain/unpin.
"""
import ast
from pathlib import Path
import tempfile
import probe_write_psn_control_native_full as parent
import write_fatal_native_sources as source
from segmented_write_payload_native_fixture import once
ROOT=source.ROOT


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ('import argparse','import argparse\nimport hashlib'),
        ('import write_psn_control_native_sources as source','import write_fatal_native_sources as source'),
        ('import write_psn_control_native_fixture as service','import write_fatal_native_fixture as service'),
        ("prefix='write-psn-control-native-full-'","prefix='write-fatal-native-full-'"),
        ("prefix='as02-write-psn-control-native-obj-'","prefix='as02-write-fatal-native-obj-'"),
        ("prefix='as02-write-psn-control-native-artifacts-'","prefix='as02-write-fatal-native-artifacts-'"),
        ('planned_cases=38','planned_cases=40'),
        ("'write-psn-control-native-fixture-diagnostics-002'","'write-fatal-native-fixture-diagnostics-001'"),
        ("preflight['all37_case_recipes_and_raw_inputs_identical']","preflight['all38_case_recipes_and_raw_inputs_identical']"),
        ('actual exact old37/new38 fixture preflight required before compilation','actual exact old38/new40 fixture preflight required before compilation'),
        ('    evidence,evidence_bindings=source.validate(a.elaboration_report.resolve())',
         "    checked_bench=service.bench()\n    if preflight['planned_native_cases']!=40 or hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=preflight['exact_new_runner_sha256'] or hashlib.sha256(checked_bench.encode()).hexdigest()!=preflight['exact_new_bench_sha256']:\n"
         "        raise ValueError('exact preflight frozen runner/whole bench required before build/object creation')\n"
         '    evidence,evidence_bindings=source.validate(a.elaboration_report.resolve())'),
        ("(run/'tb.v').write_text(service.bench())","(run/'tb.v').write_text(checked_bench)"),
        ("        cases=[('LARGE_RX_WRITE_PSN',", "        cases=[('LARGE_RX_WRITE_FATAL_ACCESS',9,0x89abcdef,['+LARGE_WRITE_RX','+LARGE_RX_OP=5','+WRITE_FATAL_ACCESS'],False,-3),\n"
         "            ('LARGE_RX_WRITE_FATAL_PARTIAL',9,0x89abcdef,['+LARGE_WRITE_RX','+LARGE_RX_OP=5','+WRITE_FATAL_PARTIAL'],False,-3),\n"
         "            ('LARGE_RX_WRITE_PSN',"),
        ("if len(cases)!=38:raise ValueError('all37 unchanged old cases plus real certified PSN NAK/suppression/retry/duplicate required')",
         "if len(cases)!=40:raise ValueError('all38 unchanged old cases plus genuine fatal62/partial61 native scenarios required')"),
        ("            is_large_write=name in ['LARGE_RX_WRITE','LARGE_RX_WRITE_IMM','LARGE_RX_WRITE_RNR','LARGE_RX_WRITE_PSN']",
         "            is_fatal=name in ['LARGE_RX_WRITE_FATAL_ACCESS','LARGE_RX_WRITE_FATAL_PARTIAL']\n"
         "            is_large_write=is_fatal or name in ['LARGE_RX_WRITE','LARGE_RX_WRITE_IMM','LARGE_RX_WRITE_RNR','LARGE_RX_WRITE_PSN']"),
        ("            if name=='LARGE_RX_WRITE_PSN':inputs['write-psn-future-input.hex']=",
         "            if is_fatal:inputs['write-fatal-input.hex']=''.join(f'{w:037x}\\n'for w in service.fatal_input(name=='LARGE_RX_WRITE_FATAL_PARTIAL')[0])\n"
         "            if name=='LARGE_RX_WRITE_PSN':inputs['write-psn-future-input.hex']="),
        ("            result.update(service.verify_large_write_psn(output,rx_records,run)if name=='LARGE_RX_WRITE_PSN'else",
         "            result.update(service.verify_fatal(output,rx_records,name=='LARGE_RX_WRITE_FATAL_PARTIAL',run)if is_fatal else\n"
         "                service.verify_large_write_psn(output,rx_records,run)if name=='LARGE_RX_WRITE_PSN'else"),
        ("                for suffix in ['host',*(['event']if immediate else[])]:shutil.copy2(run/f'large-write-receive-{suffix}.hex',run/(name+'-'+suffix+'.hex'))",
         "                for suffix in ['host',*(['event']if immediate and not is_fatal else[])]:shutil.copy2(run/f'large-write-receive-{suffix}.hex',run/(name+'-'+suffix+'.hex'))\n"
         "                if is_fatal:\n                    for suffix in ['selected','rq-owner']:shutil.copy2(run/f'write-fatal-{suffix}.hex',run/(name+'-'+suffix+'.hex'))"),
        ('complete_native_PSN_control_runtime=True,all37_prior_cases_retained=True,real_peer_PSN_retry=False)',
         'complete_native_PSN_control_runtime=True,all37_prior_cases_retained=True,real_peer_PSN_retry=False,\n'
         '            complete_native_fatal61_62_selected_runtime=True,all38_prior_cases_retained=True,real_peer_fatal_recovery=False,\n'
         '            fatal63_or_error_CQ_STOP_global_drain_unpin_qualified=False)')]:
        if old=="'write-psn-control-native-fixture-diagnostics-002'":
            if t.count(old)!=2:raise ValueError('both strict preflight bindings required')
            t=t.replace(old,new)
        else:t=once(t,old,new)
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='write-fatal-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
