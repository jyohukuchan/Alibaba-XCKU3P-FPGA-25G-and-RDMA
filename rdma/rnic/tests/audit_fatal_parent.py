#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Actual optional parent75/source/model36/callback220/native40 source audit.

Models include threaded workqueue cancellation, IB core/MMIO/certificates/
pins/DMA. This is NOT running-kernel/native or physical lifetime proof.
Logical poll stop never certifies whole-device STOP/drain/unpin/safe removal.
"""
import argparse
import json
from pathlib import Path
import sys
import audit_segmented_receive as binding
import fatal_parent_kernel_models as models
sys.path.insert(0,str(binding.ROOT/'rdma/rnic/kernel'))
import fatal_parent_candidate as candidate

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve earlier evidence')
    names=['fatal-parent-kernel-build-001','fatal-parent-graph-002','fatal-parent-callbacks-001',
        'fatal-parent-graph-001','immediate-profile-native-graph-001','fatal-verbs-kernel-build-001',
        'fatal-verbs-callbacks-002','fatal-event-native-full-001','fatal-event-native-runtime-diagnostics-001',
        'fatal-event-native-software-diagnostics-001','fatal-event-native-elaboration-002']
    records={};ids={}
    pre='rdma/rnic/build/fatal-parent-graph-001-preimages-R75HUyuu'
    fallback={n:pre for n in ['rdma/rnic/tests/fatal_parent_kernel_models.py','rdma/rnic/tests/kernel_fatal_parent_cases.c']}
    for n in names:records[n],ids[n]=binding.bindings(n,fallback if n=='fatal-parent-graph-001'else None)
    kernel,graph,callbacks,failed,oldgraph,parent,oldcallbacks,native,runtime,coupling,native_source=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for n,r in records.items()if n!='fatal-parent-graph-001')or failed['pass_test']:
        raise ValueError('actual successful separately scoped evidence and immutable failed compile required')
    files,_,_=candidate.inputs();base=ROOT/kernel['directory'];old=ROOT/parent['directory']
    if len(files)!=75 or kernel['actual_total_inputs']!=75 or parent['actual_total_inputs']!=73:
        raise ValueError('same complete actual75-input candidate and73-input parent required')
    for n,text in files.items():
        if(base/n).read_text()!=text:raise ValueError('exact parent candidate derivation changed:'+n)
        if '/'not in n and Path(n).suffix in ['.c','.h']:
            for test in [graph,callbacks]:
                if(ROOT/test['directory']/'kernel'/n).read_bytes()!=(base/n).read_bytes():
                    raise ValueError('actual kernel/test C/header differs:'+n)
    changed={'native_graph.c','native_graph.h','mqnic_graph.c','Makefile'}
    for n in parent['derived_sha256']:
        name=str(Path(n).relative_to(Path(parent['directory'])))
        if name not in changed and(base/name).read_bytes()!=(ROOT/n).read_bytes():
            raise ValueError('unrelated parent73 input changed:'+name)
    if kernel['compile_exit']or kernel['compile_seconds']>180 or kernel['compile_limit_seconds']!=180 or \
       not kernel['both_native_attach_and_fatal_events_default_denied']:
        raise ValueError('actual full real-header build180s/default-denied gate required')
    for r,expected in [(graph,36),(callbacks,220)]:
        limit=r.get('runtime_limit_seconds',r.get('simulation_limit_seconds'))
        if len(r['tests'])!=expected or limit!=10 or r['compile_seconds']>30 or \
           any(t['exit']or t['seconds']>10 for t in r['tests'].values()):
            raise ValueError('same bounded compile30s/runtime10s complete model/regression cases required')
    for i in range(20):
        if graph['tests']['GRAPH'+str(i)]['summary']!=oldgraph['tests'][str(i)]['summary']:
            raise ValueError('original20 graph full summary changed:'+str(i))
    if set(callbacks['tests'])!=set(oldcallbacks['tests']):raise ValueError('all220 prior callbacks required')
    for n,t in oldcallbacks['tests'].items():
        if callbacks['tests'][n]['summary']!=t['summary']:raise ValueError('original220 full callback summary changed:'+n)
    if failed['compile_exit']!=1 or failed['tests']:
        raise ValueError('first strict model compile failure remains false/zero runtime cases')
    log=(ROOT/failed['directory']/'compile.log').read_text()
    if '-Werror=misleading-indentation'not in log or '-Werror=return-type'not in log:
        raise ValueError('actual first model compile diagnostics must remain')
    prior_case=(ROOT/pre/'rdma/rnic/tests/kernel_fatal_parent_cases.c').read_text()
    current_case=(ROOT/'rdma/rnic/tests/kernel_fatal_parent_cases.c').read_text()
    before='        while(!w->cancel_waiters)CHECK(!pthread_cond_wait(&w->model_condition,&w->model_lock));CHECK(w->running);CHECK(!pthread_mutex_unlock(&w->model_lock));'
    after='        while(!w->cancel_waiters){CHECK(!pthread_cond_wait(&w->model_condition,&w->model_lock));}\n        CHECK(w->running);CHECK(!pthread_mutex_unlock(&w->model_lock));'
    if candidate.once(prior_case,before,after)!=current_case:raise ValueError('only exact model wait braces correction allowed; no assertion weakening')
    original=(ROOT/'rdma/rnic/tests/kernel_native_graph_cases.c').read_text()
    rendered=(ROOT/graph['directory']/'models/kernel_native_graph_cases.c').read_text()
    if rendered!=models.graph_model():raise ValueError('exact actually compiled graph boundary model required')
    original_exercise=original[original.index('static void exercise('):original.index('int main(')]
    rendered_exercise=rendered[rendered.index('static void exercise('):rendered.index('int old_native_graph_main(')]
    if original_exercise!=rendered_exercise:raise ValueError('ENTIRE original graph work/ref/CQ/cleanup assertion body required')
    source=(base/'native_graph.c').read_text();parent_code=(base/'fatal_parent.c').read_text();adapter=(base/'mqnic_graph.c').read_text()
    positions=[source.index(s)for s in ['as02_fatal_parent_check(bar+', 'as02_mr_pool_start_epoch(',
        'as02_fatal_parent_bind(&g->fatal,','as02_device_publish(', 'as02_fatal_parent_start(&g->fatal)']]
    if positions!=sorted(positions):raise ValueError('read-only FEC preflight before epoch, bind before publish, start after publish required')
    close=source[source.index('int as02_native_graph_close('):]
    if close.index('if(g->fatal.initialized)')>close.index('as02_device_unpublish('):
        raise ValueError('attached graph must retain before any unpublish/teardown')
    stop=source[source.index('int as02_native_graph_stop_fatal_polling('):]
    if 'mutex_lock('in stop:raise ValueError('no graph/lease lock held across synchronous worker cancellation')
    for marker in ['if(current_work()==&h->poll_work.work)return -EDEADLK;',
        'h->stop_requested=true;mutex_unlock(&h->lock);','cancel_delayed_work_sync(&h->poll_work);',
        'if(h->started && !h->stop_requested && !h->terminal)',
        'schedule_delayed_work(&h->poll_work,msecs_to_jiffies(1));']:
        if marker not in parent_code:raise ValueError('mandatory real worker/stop/lifetime structure missing:'+marker)
    if 'notify_users'in parent_code or 'static bool enable_fatal_events;'not in adapter or 'b.fatal_events=enable_fatal_events;'not in adapter:
        raise ValueError('dedicated poll independent of CQ users and explicit default-denied adapter flag required')
    if adapter.index('if(!enable_native_attach)return -EACCES;')>adapter.index('app=container_of('):
        raise ValueError('default denial before private parent layout access required')
    if len(native['tests'])!=40 or not runtime['actual_native_packet_HLS_abort_cancel_FEC_AXI_readback_ACK']or \
       native_source['optional_native_FEC_base']!=0x406000 or kernel['private_identity']!=[131071,511,13,63,8]:
        raise ValueError('same real qualified native FEC aperture and exact private kernel identity required')
    # This accessor name belongs to the actual source/elaboration report;
    # source proof and native runtime remain separately scoped evidence.
    inputs=[Path(__file__).resolve(),Path(candidate.__file__).resolve(),Path(models.__file__).resolve(),ROOT/'rdma/rnic/tests/kernel_fatal_parent_cases.c']
    r=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        full_kernel_inputs=75,new_parent_cases=16,all20_old_graph_full_summaries_identical=True,
        callback_cases=220,all220_old_full_callback_summaries_identical=True,
        entire_original_graph_work_reference_assertion_body_unchanged=True,
        real_parent_readonly_FEC_preflight_before_epoch_bind_before_publish_start_after_publish=True,
        dedicated_poll_progress_without_CQ_arming=True,worker_self_stop_rejected_without_deadlock=True,
        threaded_model_stop_joins_active_handler_and_excludes_requeue=True,
        unknown_event_halts_unacked_retains_refs=True,ambiguous_ACK_no_duplicate_handler=True,
        logical_stop_retains_complete_graph_lease_parent_netdev_BAR_and_refs=True,
        default_disabled_path_never_probes_FEC_and_normal_close_preserved=True,
        immutable_first_model_compile_failure_preserved=True,
        real_header_compile_seconds=kernel['compile_seconds'],graph_compile_seconds=graph['compile_seconds'],
        maximum_graph_case_seconds=max(t['seconds']for t in graph['tests'].values()),
        callback_compile_seconds=callbacks['compile_seconds'],maximum_callback_case_seconds=max(t['seconds']for t in callbacks['tests'].values()),
        source_sha256={str(q.relative_to(ROOT)):digest(q)for q in inputs},
        primary_reference=dict(url='https://docs.kernel.org/6.17/core-api/workqueue.html',
            use='current_work context and cancel_delayed_work_sync semantics; no source copied. No graph/device/lease lock held across cancellation.'),
        Linux_workqueue_MMIO_IB_core_certificate_pins_DMA_execution_modeled=True,
        installed_or_running_kernel_native_coupling=False,hardware_verified=False,full_board_timing=False,overall_goal_complete=False,
        hardware_or_default_actions=[],commit_or_push=False,
        remaining=['Real registered Linux/native/provider/physical lifetime and poll delivery remain unqualified.',
            'Whole-device STOP/reference retirement/safe unbind/removal is not implemented; bound FEC graphs deliberately remain retained after logical stop.',
            'Standard error/flush CQ/full QP STOP/recovery/quarantine release/original11/timing/physical/reboot-revival remain.'])
    with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=r['verified_bindings'],parent36=True,callback220=True,live_Linux=False)))


if __name__=='__main__':main()
