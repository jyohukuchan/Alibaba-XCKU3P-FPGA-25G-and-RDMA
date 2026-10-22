#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Bind real profile8 kernel build and actual fatal/old202 callback C tests.

Linux object/locking/MMIO/certificate/pins/DMA/workqueue execution primitives
remain MODELS. No running-kernel/native coupling, event IRQ registration,
standard error WC/whole-QP STOP/reference retirement or physical proof.
"""
import argparse
import json
from pathlib import Path
import sys
import audit_segmented_receive as binding
from audit_segmented_write_native_software import kernel_build_bindings
sys.path.insert(0,str(binding.ROOT/'rdma/rnic/kernel'))
import fatal_verbs_candidate as candidate

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    names=['fatal-verbs-kernel-build-001','fatal-verbs-callbacks-002',
        'segmented-write-kernel-post-001','fatal-verbs-callbacks-001','fatal-verbs-callback-startup-001']
    records={};ids={}
    fallback={'rdma/rnic/tests/kernel_fatal_verbs_cases.c':'rdma/rnic/build/fatal-verbs-callbacks-001-preimages-PN9khNhd'}
    for n in names:records[n],ids[n]=binding.bindings(n,fallback if n=='fatal-verbs-callbacks-001'else None)
    parent,pid=kernel_build_bindings(candidate.PARENT);ids[candidate.PARENT]=pid
    kernel,callbacks,old,failed,startup=[records[n]for n in names]
    if not all(r['pass_test']for r in [kernel,callbacks,old,parent])or failed['pass_test']or startup['pass_test']:
        raise ValueError('actual successful kernel/new220/old202 and immutable failed first attempts required')
    files,before,_=candidate.inputs();base=ROOT/kernel['directory'];test=ROOT/callbacks['directory']
    if len(files)!=73 or len(parent['frozen_input_sha256'])!=68 or kernel['actual_total_inputs']!=73:
        raise ValueError('same entire73-input kernel candidate/actual68-input parent required')
    for name,text in files.items():
        if (base/name).read_text()!=text:raise ValueError('exact source derivation mismatch:'+name)
        if '/'not in name and Path(name).suffix in ['.c','.h']:
            if (test/'kernel'/name).read_bytes()!=(base/name).read_bytes():
                raise ValueError('actual callback C/header differs from real built module:'+name)
    if kernel['compile_exit'] or kernel['compile_seconds']>180 or kernel['compile_limit_seconds']!=180 or \
       kernel['private_identity']!=[131071,511,13,63,8]or not kernel['actual_driver_fatal_reader_QP_callback_guards_linked']:
        raise ValueError('actual full matching-profile real-header build within original180s required')
    if len(callbacks['tests'])!=220 or len(old['tests'])!=202 or callbacks['simulation_limit_seconds']!=10 or \
       callbacks['compile_seconds']>30 or any(t['exit']or t['seconds']>10 for t in callbacks['tests'].values()):
        raise ValueError('all220 bounded C callbacks under30s compile/10s each required')
    if set(callbacks['tests'])!=set(old['tests'])|{'FATAL'+str(n)for n in range(18)}:
        raise ValueError('all202 original names plus18 new cases required')
    for n,t in old['tests'].items():
        if callbacks['tests'][n]['summary']!=t['summary']:raise ValueError('original202 full summary/oracle changed:'+n)
    if list(failed['tests'])!=['FATAL'+str(n)for n in range(6)]or failed['tests']['FATAL5']['exit']!=-6:
        raise ValueError('first actual owner-mutation assertion failure remains false')
    for n in range(5):
        if failed['tests']['FATAL'+str(n)]['summary']!=callbacks['tests']['FATAL'+str(n)]['summary']:
            raise ValueError('original successful new fatal outcome changed')
    oldcase=ROOT/fallback['rdma/rnic/tests/kernel_fatal_verbs_cases.c']/'rdma/rnic/tests/kernel_fatal_verbs_cases.c'
    newcase=ROOT/'rdma/rnic/tests/kernel_fatal_verbs_cases.c'
    oldmut='''    if(fatal_case==5)fatal_record.word[528/32]^=1U<<(528%32);
    if(fatal_case==6)fatal_record.word[464/32]^=1U<<(464%32);
    if(fatal_case==7)fatal_record.word[448/32]^=1U<<(448%32);'''
    newmut='''    /* Keep the record structurally valid/nonzero so these exercise the
     * actual full Linux owner match, not the earlier envelope decoder. */
    if(fatal_case==5)fatal_record.word[(528+63)/32]^=1U<<((528+63)%32);
    if(fatal_case==6)fatal_record.word[(464+63)/32]^=1U<<((464+63)%32);
    if(fatal_case==7){fatal_record.word[449/32]^=1U<<(449%32);fatal_record.word[385/32]^=1U<<(385%32);}'''
    if candidate.once(oldcase.read_text(),oldmut,newmut)!=newcase.read_text():
        raise ValueError('only exact new-case owner mutation construction correction allowed; no assertion waiver')
    if startup['error_type']!='AttributeError'or startup['compilation_started']or startup['callback_cases_executed']:
        raise ValueError('first actual module-root startup failure remains explicit')
    cmd=callbacks['compiler_command']
    for n in ['fatal_io.c','fatal_verbs.c','verbs.c']:
        if str(test/'kernel'/n)not in cmd:raise ValueError('same actual production C body missing:'+n)
    if '-fsanitize=address,undefined'not in cmd or '-fno-sanitize-recover=undefined'not in cmd:
        raise ValueError('actual ASan/UBSan required')
    v=(base/'verbs.c').read_text();c=(base/'fatal_verbs.c').read_text()
    # Require actual provider destruction AND progress guards plus attachment
    # unbind exclusion; a bare usecnt increment is not this proof.
    for marker in ['if(q->fatal_event_callback_pending || q->fatal_event_callback_active)return -EAGAIN;',
        'if(q->fatal_event_callback_pending || q->fatal_event_callback_active){ret=-EBUSY;goto out;}',
        'if (d->fatal || d->published']:
        if marker not in v:raise ValueError('mandatory real lifetime hook missing:'+marker)
    if 'if(q && handler)handler(&event,context);'not in c or 'h->notification_qp=q;ret=0;'not in c:
        raise ValueError('actual per-QP notification/recorded allocation ownership required')
    for n,h in binding.PROTECTED.items():
        if digest(ROOT/n)!=h:raise ValueError('protected raw source changed:'+n)
    r=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        exact_parent_inputs=68,exact_candidate_inputs=73,actual_new_fatal_cases=18,all202_previous_full_summaries_identical=True,
        actual_same_driver_reader_QP_callback_and_lifetime_guards_tested=True,
        real_header_build_seconds=kernel['compile_seconds'],callback_compile_seconds=callbacks['compile_seconds'],
        maximum_case_seconds=max(t['seconds']for t in callbacks['tests'].values()),
        accepted_callback_not_repeated_after_ambiguous_ACK=True,actual_ERR_and_posting_closure=True,
        handler_outside_driver_locks_with_reentry_and_real_destroy_progress_exclusion=True,
        stale_full_cookie_epoch_PD_QPN_and_malformed_event_unacked=True,
        actual_error_worker_failed_STOP_preserves_QP_PD_MR_RQ_refs=True,
        logical_detach_performs_no_MMIO_and_retains_attachment=True,
        immutable_failed_startup_and_bad_new_owner_mutation_preserved=True,
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in [Path(__file__).resolve(),Path(candidate.__file__).resolve(),newcase]},
        protected_raw_sha256=binding.PROTECTED,
        primary_references=[dict(url='https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/infiniband/hw/mlx5/qp.c',
            use='QP-specific event_handler and device/element/event convention; no source copied.'),
            dict(url='https://raw.githubusercontent.com/torvalds/linux/v6.17/drivers/infiniband/core/verbs.c',
            use='Provider destroy return controls deallocation. Real device-lock/driver destroy guards required, not only core usecnt.')],
        Linux_primitives_MMIO_certificate_producer_DMA_pins_workqueue_execution_modeled=True,
        live_Linux_native_attachment=False,standard_error_WC_STOP_reference_retirement=False,
        hardware_verified=False,full_board_timing=False,overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False,
        remaining=['Actual privileged FEC attachment/poll source and registered Linux/provider event/ref behavior remain unqualified.',
            'Standard error/flush CQ, full QP STOP/recovery and legitimate reference retirement/quarantine release remain.',
            'Original11/timing/full-board/physical and authenticated exact reboot revival remain.'])
    with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=r['verified_bindings'],fatal18=True,all202_original=True,live_Linux=False)))


if __name__=='__main__':main()
