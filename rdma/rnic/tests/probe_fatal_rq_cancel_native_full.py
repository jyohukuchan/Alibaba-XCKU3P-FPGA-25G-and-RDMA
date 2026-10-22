#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Fresh full native42: old40 unchanged plus actual fatal RQC command4 receipts.

Entire qualified207 HLS and new explicit FEC31/RQC authority graph. Genuine
owner/nonce/parent/fetch/posted-queue cancellation; never CQ/STOP/global unpin.
Original1200/30/180s/4ns/j4/O1/process-group/resource gates remain.
"""
import ast
from pathlib import Path
import tempfile
import probe_fatal_event_native_full as parent
import fatal_rq_cancel_native_sources as source
from segmented_write_payload_native_fixture import once

ROOT=source.ROOT


def runner_source():
    t=parent.runner_source();a=t.index('"""');b=t.index('"""',a+3)+3;t=t[:a]+'"""'+__doc__+'"""'+t[b:]
    for old,new in [
        ('import fatal_event_native_sources as source','import fatal_rq_cancel_native_sources as source'),
        ('import fatal_event_native_fixture as service','import fatal_rq_cancel_native_fixture as service'),
        ("prefix='fatal-event-native-full-'","prefix='fatal-rq-cancel-native-full-'"),
        ("prefix='as02-fatal-event-native-obj-'","prefix='as02-fatal-rq-cancel-native-obj-'"),
        ("prefix='as02-fatal-event-native-artifacts-'","prefix='as02-fatal-rq-cancel-native-artifacts-'"),
        ('planned_cases=40','planned_cases=42'),
        ("preflight['planned_native_cases']!=40","preflight['planned_native_cases']!=42"),
        ("        if len(cases)!=40:raise ValueError('all38 unchanged old cases plus genuine fatal62/partial61 native scenarios required')",
         "        cases += [('FATAL_RQC_ACCESS',9,0x89abcdef,['+LARGE_WRITE_RX','+LARGE_RX_OP=5','+WRITE_FATAL_ACCESS','+FATAL_RQ_CANCEL'],False,-3),\n"
         "            ('FATAL_RQC_PARTIAL',9,0x89abcdef,['+LARGE_WRITE_RX','+LARGE_RX_OP=5','+WRITE_FATAL_PARTIAL','+FATAL_RQ_CANCEL'],False,-3)]\n"
         "        if len(cases)!=42:raise ValueError('all40 original recipes plus two genuine fatal-RQC receipt scenarios required')"),
        ("            is_fatal=name in ['LARGE_RX_WRITE_FATAL_ACCESS','LARGE_RX_WRITE_FATAL_PARTIAL']",
         "            is_fatal_cancel=name in ['FATAL_RQC_ACCESS','FATAL_RQC_PARTIAL']\n"
         "            is_fatal=is_fatal_cancel or name in ['LARGE_RX_WRITE_FATAL_ACCESS','LARGE_RX_WRITE_FATAL_PARTIAL']\n"
         "            is_partial_fatal=name in ['LARGE_RX_WRITE_FATAL_PARTIAL','FATAL_RQC_PARTIAL']"),
        ("service.fatal_input(name=='LARGE_RX_WRITE_FATAL_PARTIAL')[0]","service.fatal_input(is_partial_fatal)[0]"),
        ("            result.update(service.verify_fatal(output,rx_records,name=='LARGE_RX_WRITE_FATAL_PARTIAL',run)if is_fatal else",
         "            result.update(service.verify_fatal_cancel(output,rx_records,is_partial_fatal,run)if is_fatal_cancel else\n"
         "                service.verify_fatal(output,rx_records,is_partial_fatal,run)if is_fatal else"),
        ("            if is_large_rx:\n                for suffix in ['event','host']:",
         "            if is_fatal_cancel:shutil.copy2(run/'fatal-rqc-reply.hex',run/(name+'-rqc-reply.hex'))\n"
         "            if is_large_rx:\n                for suffix in ['event','host']:"),
        ('all40_prior_cases_retained=True)',
         'all40_prior_cases_retained=True,actual_fatal_RQC_command4_receipts=True,FEC_features=31)')]:t=once(t,old,new)
    old="'fatal-event-native-fixture-diagnostics-001'"
    if t.count(old)!=2:raise ValueError('both exact new fixture preflight bindings required')
    t=t.replace(old,"'fatal-rq-cancel-native-fixture-diagnostics-001'")
    ast.parse(t);return t


if __name__=='__main__':
    run=Path(tempfile.mkdtemp(prefix='fatal-rq-cancel-native-runner-',dir=ROOT/'rdma/rnic/build'))
    frozen=run/'native_runner.py';frozen.write_text(runner_source())
    exec(compile(frozen.read_text(),str(frozen),'exec'),dict(__name__='__main__',__file__=str(frozen)))
