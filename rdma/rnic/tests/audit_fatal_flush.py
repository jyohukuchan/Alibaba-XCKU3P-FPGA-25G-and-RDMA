#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause-Views
"""Bind paired75 source, actual-C flush236/parent36 and distinct native42 proof.

Linux/IB-core/MMIO/certificate/pins/DMA/workqueue executions are MODELS.
No live Linux/native coupling or whole QP/SQ/device STOP/unpin inference.
"""
import argparse
import json
from pathlib import Path
import sys
import audit_segmented_receive as binding
sys.path.insert(0,str(binding.ROOT/'rdma/rnic/kernel'))
import fatal_flush_candidate as candidate

ROOT=binding.ROOT;digest=binding.digest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('preserve all earlier evidence')
    names=['fatal-flush-kernel-build-001','fatal-flush-callbacks-002','fatal-flush-parent-graph-001',
        'fatal-parent-kernel-build-001','fatal-parent-callbacks-001','fatal-parent-graph-002',
        'fatal-rq-lease-native-full-001','fatal-rq-lease-native-runtime-diagnostics-001',
        'fatal-flush-callbacks-001','fatal-flush-counter-diagnostic-001']
    records={};ids={}
    pre='rdma/rnic/build/fatal-flush-callbacks-001-preimages-qgXGTFUg'
    for n in names:
        fallback={'rdma/rnic/tests/kernel_fatal_flush_cases.c':pre}if n=='fatal-flush-callbacks-001'else None
        records[n],ids[n]=binding.bindings(n,fallback)
    kernel,callbacks,graph,parent,oldcallbacks,oldgraph,native,runtime,failed,debug=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in [kernel,callbacks,graph,parent,oldcallbacks,oldgraph,native,runtime])or \
       failed['pass_test']or not debug['diagnostic_completed']or not debug['original_test_still_failed']:
        raise ValueError('separate actual successes and unchanged first false callback report required')
    files,_,_=candidate.inputs();base=ROOT/kernel['directory'];prior=ROOT/parent['directory']
    if len(files)!=75 or kernel['actual_total_inputs']!=75 or parent['actual_total_inputs']!=75 or \
       kernel['only_modified_parent_inputs']!=candidate.MODIFIED or kernel['exact_optional_FEC_features']!=[15,31]:
        raise ValueError('exact complete75 inputs/only five modified/exact15-or31 required')
    original={str(Path(n).relative_to(Path(parent['directory']))):(ROOT/n).read_text()for n in parent['derived_sha256']}
    if files!=candidate.derive(original):raise ValueError('exact optional paired policy derivation required')
    if sorted(n for n in files if files[n]!=original[n])!=sorted(candidate.MODIFIED):raise ValueError('only five parent files may change')
    for n,t in files.items():
        if(base/n).read_text()!=t:raise ValueError('actual kernel input differs from derived source:'+n)
        if '/'not in n and Path(n).suffix in ['.c','.h']:
            for record in [callbacks,graph]:
                if(ROOT/record['directory']/'kernel'/n).read_bytes()!=(base/n).read_bytes():
                    raise ValueError('kernel/model production C or header mismatch:'+n)
    verbs=(base/'verbs.c').read_text()
    restored=candidate.once(verbs,candidate.POLICY+'\nstatic int progress_error','static int progress_error')
    restored=candidate.once(restored,'    ret=fatal_receive_flush(d,q);if(ret)return ret;\n','')
    if restored!=original['verbs.c']:raise ValueError('all original QP STOP/SQ/graph/ref lifecycle code must remain byte-identical')
    decoder=lambda s:s[:s.index('int as02_fatal_io_init(')]
    if decoder(files['fatal_io.c'])!=decoder(original['fatal_io.c']):raise ValueError('entire owner/record decoder must stay unchanged')
    if kernel['compile_exit']or kernel['compile_limit_seconds']!=180 or kernel['compile_seconds']>180 or \
       not kernel['native_attach_and_fatal_events_default_denied']or kernel['installed']or kernel['module_load_performed']:
        raise ValueError('real-header build180s/no install/load/default gates required')
    for record,count in [(callbacks,236),(graph,36)]:
        limit=record.get('runtime_limit_seconds',record.get('simulation_limit_seconds'))
        if len(record['tests'])!=count or limit!=10 or record['compile_seconds']>30 or \
           any(t['exit']or t['seconds']>10 for t in record['tests'].values()):
            raise ValueError('actual complete bounded compile30/runtime10 model cases required')
    for n,t in oldcallbacks['tests'].items():
        if callbacks['tests'][n]['summary']!=t['summary']:raise ValueError('any old220 full summary changed:'+n)
    for n,t in oldgraph['tests'].items():
        if graph['tests'][n]['summary']!=t['summary']:raise ValueError('any old36 parent full summary changed:'+n)
    if set(callbacks['tests'])!=set(oldcallbacks['tests'])|{'FLUSH'+str(n)for n in range(16)}:
        raise ValueError('all220 old cases plus16 new required')
    raw=(ROOT/'rdma/rnic/tests/kernel_fatal_verbs_cases.c').read_text()
    rendered=(ROOT/callbacks['directory']/'models/kernel_fatal_verbs_cases.c').read_text()
    rendered=candidate.once(rendered,'\nstatic u32 flush_fec_features=AS02_FEC_FEATURE_VALUE;','')
    rendered=candidate.once(rendered,'case AS02_FEC_FEATURES:return flush_fec_features;','case AS02_FEC_FEATURES:return AS02_FEC_FEATURE_VALUE;')
    rendered=candidate.once(rendered,'int fatal_legacy_main(int argc,char **argv)','int main(int argc,char **argv)')
    if rendered!=raw:raise ValueError('entire original fatal cases/assertions retained except entry name and explicit default15 capability selector')
    if failed['compile_seconds']>30 or set(failed['tests'])!={'FLUSH0'}or failed['tests']['FLUSH0']['exit']!=-6 or \
       debug['actual_STOP_count']!=2 or debug['STOP_index_from_rnic_regs_h']!=8 or debug['actual_ctl_qp_pd']!=1 or \
       debug['actual_send_CQ_pending']or debug['actual_recv_CQ_pending']:
        raise ValueError('actual initial counter-oracle failure must remain explicit')
    before=(ROOT/pre/'rdma/rnic/tests/kernel_fatal_flush_cases.c').read_text()
    before=candidate.once(before,'unsigned n,refs,frees,bells,handlers;','unsigned n,refs,frees,bells,handlers,stop_base;')
    before=candidate.once(before,'    create_objects();activate();',
        '    create_objects();activate();\n    /* The actual QP-open path already performs its mandatory STOP. The\n'
        '     * tested error path must add exactly one, never borrow that old proof. */\n'
        '    stop_base=ctl_commands[AS02_CMD_STOP];CHECK(stop_base==1);')
    before=before.replace('!ctl_commands[AS02_CMD_STOP]','ctl_commands[AS02_CMD_STOP]==stop_base').replace(
        'ctl_commands[AS02_CMD_STOP]==1 &&','ctl_commands[AS02_CMD_STOP]==stop_base+1 &&')
    if before!=(ROOT/'rdma/rnic/tests/kernel_fatal_flush_cases.c').read_text():raise ValueError('only new oracle counter baseline correction allowed')
    qp=(base/'qp_hw.c').read_text();open_start=qp.index('int as02_qp_hw_open(');close_start=qp.index('int as02_qp_hw_set_tx(')
    if 'command(q, AS02_CMD_STOP, NULL)'not in qp[open_start:close_start]:raise ValueError('actual mandatory initialization STOP must explain baseline')
    if len(native['tests'])!=42 or native['FEC_features']!=31 or not runtime['all40_old_full_outcomes_except_seconds_identical']or \
       not runtime['full19_word_owner_nonce_flags63_consumer_receipts']:raise ValueError('actual native42/RQC19 independently qualified')
    inputs=[Path(__file__).resolve(),Path(candidate.__file__).resolve(),ROOT/'rdma/rnic/tests/kernel_fatal_flush_cases.c',
        ROOT/'rdma/rnic/tests/probe_fatal_flush_callbacks.py',ROOT/'rdma/rnic/tests/probe_fatal_flush_parent_graph.py']
    r=dict(scope=__doc__,audit_passed=True,evidence=ids,verified_bindings=sum(v['bindings_verified']for v in ids.values()),
        source_sha256={str(p.relative_to(ROOT)):digest(p)for p in inputs},
        exact75_inputs_only_five_parent_files_changed=True,all220_old_full_callback_summaries_identical=True,
        all36_old_full_parent_summaries_identical=True,whole_original_fatal_assertion_body_preserved=True,
        old15_behavior_retained_and_unknown_features_rejected=True,
        per_RQ_standard_flush_CQ_and_WR_refs_under_explicit_models=True,
        full_CQ_retains_unreported_refs_and_no_duplicate_retired_RQC=True,
        pending_SEND_and_QP_SQ_parent_refs_remain=True,whole_original_STOP_and_lifecycle_code_preserved=True,
        immutable_first_failure_only_new_counter_baseline_corrected=True,native_RQC_receipts_independently_proven=True,
        actual_native42_to_running_Linux_execution=False,live_Linux_FPGA_coupling=False,
        whole_QP_device_STOP_global_drain_unpin_recovery_proven=False,original_timing_met=False,
        hardware_verified=False,full_board_timing=False,overall_goal_complete=False,hardware_or_default_actions=[],commit_or_push=False)
    with a.report.open('x')as f:f.write(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(audit_passed=True,verified_bindings=r['verified_bindings'],callbacks=236,parent_cases=36,live_Linux=False)))


if __name__=='__main__':main()
