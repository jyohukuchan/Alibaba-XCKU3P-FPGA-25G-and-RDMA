# SPDX-License-Identifier: BSD-2-Clause-Views
"""Optional paired FEC31 per-RQ flush; never shortcut whole QP/device STOP.

Accept only explicit old15/new31, cache that exact immutable attachment
feature, preserve old15 behavior. Real RQC cancel receipt precedes each
standard flush WC/per-WR ref put. Whole STOP/SQ/graph ownership stays gated.
UNBUILT DRAFT: native42 currently fails its new RQC case. Generation/build
is deliberately gated on a future genuine full native42/runtime audit PASS.
Source/build is not live Linux/native lifetime qualification.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
import audit_segmented_receive as binding
from segmented_write_payload_native_fixture import once

ROOT=binding.ROOT;digest=binding.digest
PARENT='fatal-parent-kernel-build-001'
MODIFIED=['fatal_regs.h','fatal_io.h','fatal_io.c','fatal_parent.c','verbs.c']

POLICY=r'''
/* Device lock held, no notification handler is running. This only permits
 * the existing genuine RQC-certificate/ordered software flush path BEFORE
 * whole-QP STOP. It is not a WC from the FEC record or its ACK, and never
 * clears hw_owned, SQ/other references, global drains or native quarantine.
 */
static int fatal_receive_flush(struct as02_verbs_device *d,struct as02_verbs_qp *q)
{
    struct as02_fatal_verbs *h=d->fatal;
    struct as02_fatal_identity owner;
    if(!h || h->reader.features==AS02_FEC_FEATURE_VALUE ||
       !q->fatal_event_recorded || !q->hw_owned)return 0;
    if(h->reader.features!=AS02_FEC_RQC_CANCEL_FEATURE_VALUE)return -EIO;
    if(h->device!=d || !h->initialized || h->detached || !h->reader.initialized ||
       READ_ONCE(h->reader.detached) || READ_ONCE(h->reader.uncertain) || d->stopping)return -EIO;
    if(!q->fatal_event_notified || q->fatal_event_callback_pending || q->fatal_event_callback_active ||
       !q->initialized || d->qp!=q || !q->pd || !q->pd->live || !q->routed ||
       !q->closing || !q->error_requested || !q->error_pending || q->sq_closed ||
       q->attributes.qp_state!=IB_QPS_ERR)return -ESTALE;
    owner=(struct as02_fatal_identity){.cookie=q->owner.cookie,.epoch=q->owner.epoch,
        .qpn=q->owner.qpn,.pd=q->owner.pd};
    if(q->ibqp.qp_num!=owner.qpn || q->pd->number!=owner.pd ||
       !as02_fatal_identity_matches(&q->fatal_event,&owner))return -ESTALE;
    /* cancel_receive validates/retains the full real RQC nonce/owner/final
     * producer/flags proof, and holds refs under CQ backpressure. It never
     * fabricates a native CQ record or releases an unreported WR reference.
     */
    return as02_sq_flush_receive(d->sq,&q->owner);
}
'''


def derive(files):
    out=dict(files)
    out['fatal_regs.h']=once(out['fatal_regs.h'],'#define AS02_FEC_VISIBLE 1U',
        '#define AS02_FEC_RQC_CANCEL_FEATURE_VALUE 0x0000001fU\n#define AS02_FEC_VISIBLE 1U')
    out['fatal_io.h']=once(out['fatal_io.h'],'    as02_u32 acknowledged;',
        '    as02_u32 acknowledged, features; /* exact immutable attachment15 or31 */')
    out['fatal_io.c']=once(out['fatal_io.c'],
        'abi!=AS02_FEC_ABI_VALUE || features!=AS02_FEC_FEATURE_VALUE',
        'abi!=AS02_FEC_ABI_VALUE || (features!=AS02_FEC_FEATURE_VALUE && features!=AS02_FEC_RQC_CANCEL_FEATURE_VALUE)')
    out['fatal_io.c']=once(out['fatal_io.c'],
        'h->io=io;h->context=context;h->initialized=1;return 0;',
        'h->io=io;h->context=context;h->features=features;h->initialized=1;return 0;')
    out['fatal_parent.c']=once(out['fatal_parent.c'],'    u32 status,seq,ack;',
        '    u32 status,seq,ack,features;')
    out['fatal_parent.c']=once(out['fatal_parent.c'],
        'readl(base+AS02_FEC_FEATURES)!=AS02_FEC_FEATURE_VALUE)',
        '((features=readl(base+AS02_FEC_FEATURES))!=AS02_FEC_FEATURE_VALUE && features!=AS02_FEC_RQC_CANCEL_FEATURE_VALUE))')
    out['verbs.c']=once(out['verbs.c'],'static int progress_error(struct as02_verbs_device *d,struct as02_verbs_qp *q)',
        POLICY+'\nstatic int progress_error(struct as02_verbs_device *d,struct as02_verbs_qp *q)')
    anchor='    ret=as02_sq_prepare_receive_cancel(d->sq,&q->owner);\n    if(ret && ret!=-EOPNOTSUPP)return ret;\n'
    out['verbs.c']=once(out['verbs.c'],anchor,anchor+'    ret=fatal_receive_flush(d,q);if(ret)return ret;\n')
    assert sorted(n for n in files if out[n]!=files[n])==sorted(MODIFIED)
    return out


def inputs():
    names=[PARENT,'fatal-parent-diagnostics-001','fatal-rq-lease-native-full-001',
        'fatal-rq-lease-native-runtime-diagnostics-001']
    records={};ids={}
    for n in names:records[n],ids[n]=binding.bindings(n)
    parent,software,native,runtime=[records[n]for n in names]
    if not all(r.get('pass_test',r.get('audit_passed'))for r in records.values())or \
       parent['actual_total_inputs']!=75 or parent['private_identity']!=[131071,511,13,63,8]or \
       len(native['tests'])!=42 or native['FEC_features']!=31 or \
       not runtime['all40_old_full_outcomes_except_seconds_identical']or \
       set(runtime['actual_fatal_RQC_cases'])!={'FATAL_RQC_ACCESS','FATAL_RQC_PARTIAL'}or \
       not runtime['full19_word_owner_nonce_flags63_consumer_receipts']:
        raise ValueError('actual complete kernel75 and actual native42/full RQC certificates required before generating software')
    base=Path(parent['directory'])
    files={str(Path(n).relative_to(base)):(ROOT/n).read_text()for n in parent['derived_sha256']}
    before={n:digest(ROOT/n)for n in parent['derived_sha256']}
    files=derive(files)
    for p in [Path(__file__).resolve(),*[binding.record(n)for n in names]]:before[str(p.relative_to(ROOT))]=digest(p)
    return files,before,ids
